#!/bin/bash
# Tear down the HID gadget created by usb-gadget-up.sh.
#
# configfs requires unbinding, unlinking and removing directories in the exact
# reverse order of creation; rmdir on a still-linked function returns EBUSY.
set -euo pipefail

GADGET_NAME="${GADGET_NAME:-pideck}"
GADGET_DIR="/sys/kernel/config/usb_gadget/${GADGET_NAME}"

if [[ ${EUID} -ne 0 ]]; then
    echo "must run as root" >&2
    exit 1
fi

if [[ ! -d "${GADGET_DIR}" ]]; then
    exit 0
fi

cd "${GADGET_DIR}"

# Unbind from the controller first so the host sees a clean disconnect.
if [[ -s UDC ]]; then
    echo "" > UDC
fi

rm -f configs/c.1/hid.usb0 configs/c.1/hid.usb1
rmdir configs/c.1/strings/0x409 2>/dev/null || true
rmdir configs/c.1 2>/dev/null || true
rmdir functions/hid.usb0 2>/dev/null || true
rmdir functions/hid.usb1 2>/dev/null || true
rmdir strings/0x409 2>/dev/null || true
cd /
rmdir "${GADGET_DIR}"

echo "gadget ${GADGET_NAME} removed"
