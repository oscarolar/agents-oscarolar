"""Backlight control for the official Raspberry Pi touch display.

The DSI panel exposes a sysfs backlight device whose name has changed across
kernels (``rpi_backlight`` on older ones, ``10-0045`` on current Bookworm and
Trixie kernels), so the device is discovered by globbing rather than hardcoded.
Everything degrades to a no-op when no backlight is present, which is what
happens when developing on a laptop.
"""

import glob
import logging
import pathlib

log = logging.getLogger(__name__)


class Backlight:
    def __init__(self, sysfs_glob="/sys/class/backlight/*"):
        self.device = None
        self.max_brightness = 0
        self._level = 100

        for candidate in sorted(glob.glob(sysfs_glob)):
            path = pathlib.Path(candidate)
            try:
                self.max_brightness = int((path / "max_brightness").read_text().strip())
            except (OSError, ValueError):
                continue
            if self.max_brightness > 0:
                self.device = path
                break

        if self.device is None:
            log.info("no sysfs backlight found; brightness control disabled")

    @property
    def available(self):
        return self.device is not None

    @property
    def level(self):
        """Current brightness as a percentage."""
        return self._level

    def set(self, percent):
        """Set brightness to a percentage, clamped to 1-100.

        Zero is deliberately excluded: a fully dark panel on a device whose only
        input is its own touchscreen is indistinguishable from a crash.
        """
        target = max(1, min(100, int(percent)))
        self._level = target
        if not self.available:
            return target

        raw = max(1, round(self.max_brightness * target / 100))
        try:
            (self.device / "brightness").write_text(str(raw))
        except OSError as exc:
            log.warning("cannot set brightness: %s", exc)
        return target

    def nudge(self, delta):
        return self.set(self._level + int(delta))
