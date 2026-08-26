"""Writers for the two USB HID gadget endpoints.

The gadget created by ``scripts/usb-gadget-up.sh`` exposes two character
devices: ``/dev/hidg0`` is an 8-byte boot keyboard and ``/dev/hidg1`` is a
2-byte consumer-control device. Writing a report is literally writing those
bytes; releasing a key means writing an all-zero report afterwards.
"""

import logging
import os
import time

log = logging.getLogger(__name__)

KEYBOARD_REPORT_LENGTH = 8
CONSUMER_REPORT_LENGTH = 2

# The host's HID stack needs a moment between press and release, otherwise fast
# applications coalesce them and the keystroke is dropped.
DEFAULT_TAP_SECONDS = 0.02


class HidWriteError(RuntimeError):
    """Raised when a report cannot be delivered to the gadget device."""


class HidEndpoint:
    """A single ``/dev/hidgN`` device, opened lazily and reopened on failure."""

    def __init__(self, path, report_length, dry_run=False):
        self.path = path
        self.report_length = report_length
        self.dry_run = dry_run
        self._fd = None

    def _open(self):
        if self._fd is not None:
            return self._fd
        try:
            self._fd = os.open(self.path, os.O_WRONLY)
        except OSError as exc:
            raise HidWriteError(
                f"cannot open HID gadget {self.path}: {exc}. "
                "Is pideck-gadget.service running, and is this user in the "
                "'input' group?"
            ) from exc
        return self._fd

    def send(self, report):
        """Write one report, padding or rejecting to the exact report length."""
        if len(report) > self.report_length:
            raise HidWriteError(
                f"report of {len(report)} bytes exceeds the {self.report_length}-byte "
                f"report length of {self.path}"
            )
        payload = bytes(report).ljust(self.report_length, b"\x00")

        if self.dry_run:
            log.info("dry-run %s <- %s", self.path, payload.hex(" "))
            return

        try:
            os.write(self._open(), payload)
        except OSError as exc:
            # A disconnected or re-enumerated host invalidates the fd. Drop it so
            # the next call reopens instead of failing forever.
            self.close()
            raise HidWriteError(f"write to {self.path} failed: {exc}") from exc

    def release(self):
        """Send the all-zero report that tells the host every key is up."""
        self.send(b"\x00" * self.report_length)

    def close(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None


class Keyboard:
    """Boot-keyboard view of ``/dev/hidg0``."""

    def __init__(self, path="/dev/hidg0", dry_run=False, tap_seconds=DEFAULT_TAP_SECONDS):
        self.endpoint = HidEndpoint(path, KEYBOARD_REPORT_LENGTH, dry_run=dry_run)
        self.tap_seconds = tap_seconds

    def press(self, modifier_mask, usages):
        """Hold a chord: modifier byte, reserved byte, then up to six usages."""
        report = bytearray(KEYBOARD_REPORT_LENGTH)
        report[0] = modifier_mask & 0xFF
        for index, usage in enumerate(usages[:6]):
            report[2 + index] = usage & 0xFF
        self.endpoint.send(report)

    def release(self):
        self.endpoint.release()

    def tap(self, modifier_mask, usages):
        try:
            self.press(modifier_mask, usages)
            time.sleep(self.tap_seconds)
        finally:
            # Always try to lift the keys. A press that made it to the host but
            # whose release did not would leave a modifier stuck down there.
            self.release()

    def close(self):
        self.endpoint.close()


class ConsumerControl:
    """Media-key view of ``/dev/hidg1``."""

    def __init__(self, path="/dev/hidg1", dry_run=False, tap_seconds=DEFAULT_TAP_SECONDS):
        self.endpoint = HidEndpoint(path, CONSUMER_REPORT_LENGTH, dry_run=dry_run)
        self.tap_seconds = tap_seconds

    def tap(self, usage):
        try:
            self.endpoint.send(bytes([usage & 0xFF, (usage >> 8) & 0xFF]))
            time.sleep(self.tap_seconds)
        finally:
            self.endpoint.release()

    def close(self):
        self.endpoint.close()
