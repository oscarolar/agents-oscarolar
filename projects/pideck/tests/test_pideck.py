"""Tests for the parts that must be right before a button is ever pressed:
key resolution, config validation, and the bytes that go on the wire.

Dependency-free (stdlib unittest) so it runs on a fresh Pi with nothing but
python3 and python3-yaml installed. The UI is not imported here -- it needs SDL.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pideck import config as config_module  # noqa: E402
from pideck import hidkeys  # noqa: E402
from pideck.actions import ActionRunner  # noqa: E402
from pideck.hiddev import ConsumerControl, HidWriteError, Keyboard  # noqa: E402

REPO_CONFIG = pathlib.Path(__file__).resolve().parent.parent / "config" / "deck.yaml"


class RecordingEndpoint:
    """Stands in for /dev/hidgN and remembers every report written."""

    def __init__(self, report_length):
        self.report_length = report_length
        self.reports = []

    def send(self, report):
        payload = bytes(report).ljust(self.report_length, b"\x00")
        self.reports.append(payload)

    def release(self):
        self.send(b"\x00" * self.report_length)

    def close(self):
        pass


class FakeBacklight:
    def __init__(self):
        self.level = 100
        self.available = True

    def set(self, percent):
        self.level = max(1, min(100, int(percent)))
        return self.level

    def nudge(self, delta):
        return self.set(self.level + int(delta))


def build_runner():
    keyboard = Keyboard(dry_run=True, tap_seconds=0)
    keyboard.endpoint = RecordingEndpoint(8)
    consumer = ConsumerControl(dry_run=True, tap_seconds=0)
    consumer.endpoint = RecordingEndpoint(2)
    return ActionRunner(keyboard, consumer, FakeBacklight())


class KeyResolutionTests(unittest.TestCase):
    def test_modifiers_combine_into_one_bitmask(self):
        mask, usages = hidkeys.resolve_combo("ctrl+shift+m")
        self.assertEqual(mask, 0x01 | 0x02)
        self.assertEqual(usages, [0x10])

    def test_key_names_are_case_insensitive(self):
        self.assertEqual(hidkeys.resolve_combo("F13"), hidkeys.resolve_combo("f13"))

    def test_right_and_left_modifiers_are_distinct(self):
        self.assertNotEqual(
            hidkeys.resolve_combo("lshift+a")[0], hidkeys.resolve_combo("rshift+a")[0]
        )

    def test_unknown_key_names_are_rejected(self):
        with self.assertRaises(hidkeys.UnknownKeyError):
            hidkeys.resolve_combo("ctrl+nonexistent")

    def test_more_than_six_keys_is_rejected(self):
        with self.assertRaises(hidkeys.UnknownKeyError):
            hidkeys.resolve_combo("a+b+c+d+e+f+g")

    def test_shifted_characters_carry_the_shift_modifier(self):
        self.assertEqual(hidkeys.resolve_char("A"), (0x02, hidkeys.KEYS["a"]))
        self.assertEqual(hidkeys.resolve_char("%"), (0x02, hidkeys.KEYS["5"]))
        self.assertEqual(hidkeys.resolve_char("a"), (0x00, hidkeys.KEYS["a"]))

    def test_characters_outside_the_us_layout_return_none(self):
        self.assertIsNone(hidkeys.resolve_char("ñ"))
        self.assertIsNone(hidkeys.resolve_char("€"))


class ReportTests(unittest.TestCase):
    def test_keyboard_tap_presses_then_releases(self):
        runner = build_runner()
        runner.run({"type": "key", "keys": "ctrl+shift+m"})
        reports = runner.keyboard.endpoint.reports
        self.assertEqual(len(reports), 2)
        self.assertEqual(reports[0], bytes([0x03, 0x00, 0x10, 0, 0, 0, 0, 0]))
        self.assertEqual(reports[1], bytes(8))

    def test_consumer_report_is_little_endian(self):
        runner = build_runner()
        runner.run({"type": "media", "key": "volume_up"})
        reports = runner.consumer.endpoint.reports
        self.assertEqual(reports[0], bytes([0xE9, 0x00]))
        self.assertEqual(reports[1], bytes(2))

    def test_text_action_types_each_character(self):
        runner = build_runner()
        runner.run({"type": "text", "text": "Hi!"})
        # Three characters, each a press and a release.
        self.assertEqual(len(runner.keyboard.endpoint.reports), 6)
        press_h = runner.keyboard.endpoint.reports[0]
        self.assertEqual(press_h[0], 0x02)  # shift for the capital H
        self.assertEqual(press_h[2], hidkeys.KEYS["h"])

    def test_text_action_skips_unmappable_characters(self):
        runner = build_runner()
        runner.run({"type": "text", "text": "añ"})
        # Only 'a' survives: one press, one release.
        self.assertEqual(len(runner.keyboard.endpoint.reports), 2)

    def test_repeat_sends_the_combo_n_times(self):
        runner = build_runner()
        runner.run({"type": "key", "keys": "down", "repeat": 3})
        self.assertEqual(len(runner.keyboard.endpoint.reports), 6)

    def test_sequence_runs_steps_in_order(self):
        runner = build_runner()
        runner.run({
            "type": "sequence",
            "steps": [{"key": "ctrl+k"}, {"key": "s"}, {"delay": 0}],
        })
        reports = runner.keyboard.endpoint.reports
        self.assertEqual(reports[0][0], 0x01)
        self.assertEqual(reports[0][2], hidkeys.KEYS["k"])
        self.assertEqual(reports[2][2], hidkeys.KEYS["s"])

    def test_page_action_returns_a_ui_command(self):
        runner = build_runner()
        self.assertEqual(runner.run({"type": "page", "page": "obs"}), ("page", "obs"))

    def test_brightness_action_moves_the_backlight(self):
        runner = build_runner()
        runner.run({"type": "brightness", "delta": -30})
        self.assertEqual(runner.backlight.level, 70)
        runner.run({"type": "brightness", "level": 100})
        self.assertEqual(runner.backlight.level, 100)

    def test_backlight_never_reaches_zero(self):
        runner = build_runner()
        runner.run({"type": "brightness", "level": 0})
        self.assertEqual(runner.backlight.level, 1)

    def test_unknown_action_type_is_ignored_not_raised(self):
        runner = build_runner()
        self.assertIsNone(runner.run({"type": "teleport"}))


class ShellActionTests(unittest.TestCase):
    def test_shell_command_runs_without_a_shell(self):
        runner = build_runner()
        # No shell means no word splitting surprises and no injection via labels.
        self.assertIsNone(runner.run({"type": "shell", "command": "true"}))

    def test_missing_binary_reports_an_error_instead_of_crashing(self):
        runner = build_runner()
        result = runner.run(
            {"type": "shell", "command": "/nonexistent/pideck-binary"}
        )
        self.assertEqual(result[0], "error")


class FailureRecoveryTests(unittest.TestCase):
    """A USB hiccup must never leave a modifier held down on the host."""

    def test_failed_press_still_attempts_a_release(self):
        runner = build_runner()
        endpoint = runner.keyboard.endpoint
        original_send = endpoint.send
        calls = {"n": 0}

        def failing_send(report):
            calls["n"] += 1
            if calls["n"] == 1:
                raise HidWriteError("simulated write failure")
            original_send(report)

        endpoint.send = failing_send
        result = runner.run({"type": "key", "keys": "ctrl+shift+m"})

        self.assertEqual(result[0], "error")
        # The press never reached the host, and every report that did is an
        # all-keys-up release. Sending it twice (tap's finally, then the
        # runner's panic release) is harmless and deliberate.
        self.assertTrue(endpoint.reports)
        self.assertTrue(all(report == bytes(8) for report in endpoint.reports))

    def test_failure_mid_sequence_reports_an_error(self):
        runner = build_runner()
        endpoint = runner.keyboard.endpoint
        original_send = endpoint.send
        calls = {"n": 0}

        def failing_send(report):
            calls["n"] += 1
            if calls["n"] == 3:
                raise HidWriteError("simulated write failure")
            original_send(report)

        endpoint.send = failing_send
        result = runner.run({
            "type": "sequence",
            "steps": [{"key": "ctrl+k"}, {"key": "s"}],
        })
        self.assertEqual(result[0], "error")
        self.assertEqual(endpoint.reports[-1], bytes(8))


class ConfigTests(unittest.TestCase):
    def minimal(self, **overrides):
        data = {
            "deck": {"columns": 2, "rows": 1},
            "pages": [
                {
                    "id": "main",
                    "buttons": [{"label": "A", "action": {"type": "key", "keys": "a"}}],
                }
            ],
        }
        data.update(overrides)
        return data

    def test_minimal_config_loads(self):
        deck = config_module.from_mapping(self.minimal())
        self.assertEqual(deck.start_page, "main")
        self.assertEqual(deck.pages[0].capacity, 2)

    def test_bad_key_in_a_button_fails_at_load_time(self):
        data = self.minimal()
        data["pages"][0]["buttons"][0]["action"]["keys"] = "ctrl+banana"
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.from_mapping(data)
        self.assertIn("banana", str(caught.exception))

    def test_page_action_pointing_nowhere_is_rejected(self):
        data = self.minimal()
        data["pages"][0]["buttons"][0]["action"] = {"type": "page", "page": "ghost"}
        with self.assertRaises(config_module.ConfigError):
            config_module.from_mapping(data)

    def test_duplicate_page_ids_are_rejected(self):
        data = self.minimal()
        data["pages"].append({"id": "main", "buttons": []})
        with self.assertRaises(config_module.ConfigError):
            config_module.from_mapping(data)

    def test_too_many_buttons_for_the_grid_is_rejected(self):
        data = self.minimal()
        data["pages"][0]["buttons"] = [
            {"label": str(n), "action": {"type": "none"}} for n in range(3)
        ]
        with self.assertRaises(config_module.ConfigError):
            config_module.from_mapping(data)

    def test_colliding_explicit_positions_are_rejected(self):
        data = self.minimal()
        data["pages"][0]["buttons"] = [
            {"label": "A", "action": {"type": "none"}, "position": [0, 0]},
            {"label": "B", "action": {"type": "none"}, "position": [0, 0]},
        ]
        with self.assertRaises(config_module.ConfigError):
            config_module.from_mapping(data)

    def test_position_outside_the_grid_is_rejected(self):
        data = self.minimal()
        data["pages"][0]["buttons"][0]["position"] = [0, 9]
        with self.assertRaises(config_module.ConfigError):
            config_module.from_mapping(data)

    def test_unknown_sequence_step_is_rejected(self):
        data = self.minimal()
        data["pages"][0]["buttons"][0]["action"] = {
            "type": "sequence",
            "steps": [{"summon": "demon"}],
        }
        with self.assertRaises(config_module.ConfigError):
            config_module.from_mapping(data)

    def test_start_page_must_exist(self):
        data = self.minimal()
        data["deck"]["start_page"] = "ghost"
        with self.assertRaises(config_module.ConfigError):
            config_module.from_mapping(data)

    def test_theme_falls_back_to_defaults_for_missing_keys(self):
        data = self.minimal()
        data["deck"]["theme"] = {"accent": "#ff0000"}
        deck = config_module.from_mapping(data)
        self.assertEqual(deck.theme["accent"], "#ff0000")
        self.assertEqual(deck.theme["background"], config_module.DEFAULT_THEME["background"])

    def test_shipped_config_is_valid(self):
        deck = config_module.load(REPO_CONFIG)
        self.assertGreater(len(deck.pages), 1)
        for page in deck.pages:
            self.assertLessEqual(len(page.buttons), page.capacity)

    def test_every_shipped_page_can_be_reached_from_the_start_page(self):
        deck = config_module.load(REPO_CONFIG)
        reachable = {deck.start_page}
        frontier = [deck.start_page]
        while frontier:
            page = deck.page(frontier.pop())
            for button in page.buttons:
                if button.action.get("type") == "page":
                    target = button.action["page"]
                    if target not in reachable:
                        reachable.add(target)
                        frontier.append(target)
        self.assertEqual(reachable, set(deck.page_ids))


if __name__ == "__main__":
    unittest.main()
