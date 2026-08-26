#!/bin/bash
# Create the composite USB HID gadget that makes the Pi look like a keyboard.
#
# Two functions are exposed:
#   /dev/hidg0 - 8-byte boot keyboard (modifiers + 6 keys)
#   /dev/hidg1 - 2-byte consumer control (volume, play/pause, ...)
#
# Requires dtoverlay=dwc2 in /boot/firmware/config.txt and a data-capable cable
# in the Pi's USB-C port. Run as root.
set -euo pipefail

GADGET_NAME="${GADGET_NAME:-pideck}"
GADGET_DIR="/sys/kernel/config/usb_gadget/${GADGET_NAME}"

if [[ ${EUID} -ne 0 ]]; then
    echo "must run as root" >&2
    exit 1
fi

modprobe libcomposite

if [[ ! -d /sys/kernel/config/usb_gadget ]]; then
    mount -t configfs none /sys/kernel/config
fi

if [[ -d "${GADGET_DIR}" ]]; then
    echo "gadget ${GADGET_NAME} already exists; nothing to do"
    exit 0
fi

mkdir -p "${GADGET_DIR}"
cd "${GADGET_DIR}"

# 0x1d6b/0x0104 is the Linux Foundation "Multifunction Composite Gadget" pair.
# Using it means every host OS already has a matching in-box driver.
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
# Serial number is derived from the Pi's own CPU serial so two decks on one host
# do not collide.
SERIAL="$(awk '/^Serial/ {print $3}' /proc/cpuinfo 2>/dev/null || true)"
echo "${SERIAL:-0000000000000001}" > strings/0x409/serialnumber
echo "PiDeck" > strings/0x409/manufacturer
echo "PiDeck Macro Keyboard" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "HID keyboard + consumer control" > configs/c.1/strings/0x409/configuration
# 500 mA, expressed in the 2 mA units the descriptor uses.
echo 250 > configs/c.1/MaxPower

# --- Keyboard: standard HID boot-protocol descriptor -------------------------
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol   # 1 = keyboard
echo 1 > functions/hid.usb0/subclass   # 1 = boot interface
echo 8 > functions/hid.usb0/report_length
printf '%b' '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' \
    > functions/hid.usb0/report_desc

# --- Consumer control: one 16-bit usage per report ---------------------------
mkdir -p functions/hid.usb1
echo 0 > functions/hid.usb1/protocol
echo 0 > functions/hid.usb1/subclass
echo 2 > functions/hid.usb1/report_length
printf '%b' '\x05\x0c\x09\x01\xa1\x01\x15\x00\x26\xff\x03\x19\x00\x2a\xff\x03\x75\x10\x95\x01\x81\x00\xc0' \
    > functions/hid.usb1/report_desc

ln -s functions/hid.usb0 configs/c.1/
ln -s functions/hid.usb1 configs/c.1/

UDC="$(ls /sys/class/udc | head -n1)"
if [[ -z "${UDC}" ]]; then
    echo "no UDC found. Check that dtoverlay=dwc2 is set in /boot/firmware/config.txt and that you rebooted." >&2
    exit 1
fi
echo "${UDC}" > UDC

echo "gadget ${GADGET_NAME} bound to ${UDC}"
