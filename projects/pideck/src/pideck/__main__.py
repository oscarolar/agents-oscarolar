"""Command-line entry point: ``python -m pideck``."""

import argparse
import logging
import pathlib
import sys

from . import __version__, config as config_module, hidkeys
from .actions import ActionRunner
from .backlight import Backlight
from .hiddev import ConsumerControl, Keyboard

CONFIG_SEARCH_PATH = [
    pathlib.Path("config/deck.yaml"),
    pathlib.Path("~/.config/pideck/deck.yaml").expanduser(),
    pathlib.Path("/etc/pideck/deck.yaml"),
]


def find_config(explicit=None):
    if explicit:
        return pathlib.Path(explicit).expanduser()
    for candidate in CONFIG_SEARCH_PATH:
        if candidate.is_file():
            return candidate
    raise config_module.ConfigError(
        "no deck.yaml found. Looked in: "
        + ", ".join(str(p) for p in CONFIG_SEARCH_PATH)
        + ". Pass one with --config."
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="pideck",
        description="Touchscreen macro deck that acts as a USB keyboard.",
    )
    parser.add_argument("-c", "--config", help="path to deck.yaml")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the config and exit without opening a window",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="run in a window instead of fullscreen KMS (for development)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="log HID reports instead of writing them to the gadget devices",
    )
    parser.add_argument(
        "--list-keys",
        action="store_true",
        help="print every key and media name accepted in deck.yaml, then exit",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"pideck {__version__}")
    return parser


def print_keys():
    print("Modifiers:")
    print("  " + ", ".join(sorted(hidkeys.MODIFIERS)))
    print("\nKeys:")
    print("  " + ", ".join(sorted(hidkeys.KEYS)))
    print("\nMedia keys (action type: media):")
    print("  " + ", ".join(sorted(hidkeys.CONSUMER)))


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.list_keys:
        print_keys()
        return 0

    try:
        config_path = find_config(args.config)
        deck_config = config_module.load(config_path)
    except config_module.ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        total = sum(len(page.buttons) for page in deck_config.pages)
        print(
            f"{config_path}: OK - {len(deck_config.pages)} page(s), "
            f"{total} button(s), starting on {deck_config.start_page!r}"
        )
        return 0

    # Imported here so --check and --list-keys work on a machine with no
    # display and no SDL installed.
    from .ui import Deck

    backlight = Backlight()
    runner = ActionRunner(
        keyboard=Keyboard(deck_config.keyboard_device, dry_run=args.dry_run),
        consumer=ConsumerControl(deck_config.consumer_device, dry_run=args.dry_run),
        backlight=backlight,
    )

    try:
        Deck(deck_config, runner, backlight, windowed=args.windowed).run()
    except KeyboardInterrupt:
        return 0
    finally:
        runner.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
