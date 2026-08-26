"""Execute the action attached to a button.

Every action returns a small command tuple for the UI (or ``None``), which is
how a button asks to switch pages without the runner reaching into the UI.
"""

import logging
import shlex
import subprocess
import time

from . import hidkeys
from .hiddev import HidWriteError

log = logging.getLogger(__name__)

SHELL_TIMEOUT_SECONDS = 10

# Inter-character delay when typing a string. Fast enough to feel instant,
# slow enough that hosts do not drop characters.
TYPE_DELAY_SECONDS = 0.008


class ActionRunner:
    def __init__(self, keyboard, consumer, backlight):
        self.keyboard = keyboard
        self.consumer = consumer
        self.backlight = backlight

    def run(self, action):
        """Run one action. Returns a UI command tuple or None."""
        action_type = action.get("type", "none")
        try:
            handler = getattr(self, f"_run_{action_type}")
        except AttributeError:
            log.warning("ignoring unknown action type %r", action_type)
            return None

        try:
            return handler(action)
        except HidWriteError as exc:
            log.error("HID write failed: %s", exc)
            self._panic_release()
            return ("error", str(exc))
        except hidkeys.UnknownKeyError as exc:
            log.error("bad key in action: %s", exc)
            self._panic_release()
            return ("error", str(exc))

    def _panic_release(self):
        """Best-effort 'all keys up' after an action died half-finished."""
        try:
            self.keyboard.release()
        except HidWriteError:
            pass

    def _run_none(self, action):
        return None

    def _run_key(self, action):
        modifier_mask, usages = hidkeys.resolve_combo(action["keys"])
        repeat = max(1, min(20, int(action.get("repeat", 1))))
        for _ in range(repeat):
            self.keyboard.tap(modifier_mask, usages)
        return None

    def _run_media(self, action):
        self.consumer.tap(hidkeys.resolve_consumer(action["key"]))
        return None

    def _run_text(self, action):
        self._type(action["text"])
        return None

    def _run_sequence(self, action):
        for step in action["steps"]:
            kind, value = next(iter(step.items()))
            if kind == "key":
                self.keyboard.tap(*hidkeys.resolve_combo(value))
            elif kind == "media":
                self.consumer.tap(hidkeys.resolve_consumer(value))
            elif kind == "text":
                self._type(value)
            elif kind == "delay":
                time.sleep(float(value))
        return None

    def _run_page(self, action):
        return ("page", action["page"])

    def _run_brightness(self, action):
        if "level" in action:
            self.backlight.set(action["level"])
        else:
            self.backlight.nudge(action["delta"])
        return ("brightness", self.backlight.level)

    def _run_shell(self, action):
        """Run a command on the Pi itself -- not on the host PC.

        Used for local housekeeping (restart the service, reboot, toggle Wi-Fi).
        The command is split with shlex and run without a shell so a label
        containing quotes cannot turn into an injection.
        """
        command = action["command"]
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            log.error("cannot parse shell command %r: %s", command, exc)
            return ("error", f"bad command: {exc}")
        if not argv:
            return None

        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=SHELL_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError:
            log.error("command not found: %s", argv[0])
            return ("error", f"not found: {argv[0]}")
        except subprocess.TimeoutExpired:
            log.error("command timed out after %ss: %s", SHELL_TIMEOUT_SECONDS, command)
            return ("error", "command timed out")

        if completed.returncode != 0:
            log.warning(
                "command %r exited %s: %s",
                command, completed.returncode, completed.stderr.strip(),
            )
        return None

    def _type(self, text):
        for char in text:
            resolved = hidkeys.resolve_char(char)
            if resolved is None:
                log.warning("skipping character %r: not on the US HID layout", char)
                continue
            modifier_mask, usage = resolved
            self.keyboard.tap(modifier_mask, [usage])
            time.sleep(TYPE_DELAY_SECONDS)

    def close(self):
        self.keyboard.close()
        self.consumer.close()
