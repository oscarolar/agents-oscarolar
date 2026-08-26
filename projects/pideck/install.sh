#!/bin/bash
# Install PiDeck on a Raspberry Pi: dependencies, USB gadget overlay, config,
# udev rules and systemd units. Safe to re-run -- it never overwrites an
# existing /etc/pideck/deck.yaml.
set -euo pipefail

PREFIX="${PREFIX:-/opt/pideck}"
CONFIG_DIR="/etc/pideck"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${SUDO_USER:-${USER:-root}}"

usage() {
    cat <<USAGE
Usage: sudo ./install.sh [--user USER] [--prefix DIR]

  --user USER    account the deck service runs as (default: ${TARGET_USER})
  --prefix DIR   install location (default: ${PREFIX})
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user) TARGET_USER="$2"; shift 2 ;;
        --prefix) PREFIX="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $1" >&2; usage; exit 1 ;;
    esac
done

if [[ ${EUID} -ne 0 ]]; then
    echo "run with sudo" >&2
    exit 1
fi

if ! id -u "${TARGET_USER}" >/dev/null 2>&1; then
    echo "user ${TARGET_USER} does not exist" >&2
    exit 1
fi

echo "==> Installing dependencies"
apt-get update -qq
apt-get install -y --no-install-recommends python3 python3-yaml python3-pygame

echo "==> Enabling the dwc2 USB peripheral overlay"
# Bookworm and later keep the firmware config in /boot/firmware; older images
# use /boot directly.
BOOT_CONFIG="/boot/firmware/config.txt"
[[ -f "${BOOT_CONFIG}" ]] || BOOT_CONFIG="/boot/config.txt"
if [[ ! -f "${BOOT_CONFIG}" ]]; then
    echo "cannot find config.txt; is this a Raspberry Pi?" >&2
    exit 1
fi

REBOOT_NEEDED=0
if grep -qE '^\s*dtoverlay=dwc2' "${BOOT_CONFIG}"; then
    echo "    dwc2 overlay already present in ${BOOT_CONFIG}"
else
    printf '\n# Added by PiDeck: put the USB-C port in peripheral mode.\ndtoverlay=dwc2,dr_mode=peripheral\n' >> "${BOOT_CONFIG}"
    echo "    added dtoverlay=dwc2 to ${BOOT_CONFIG}"
    REBOOT_NEEDED=1
fi

echo "==> Installing files to ${PREFIX}"
install -d "${PREFIX}" "${PREFIX}/scripts" "${CONFIG_DIR}"
cp -r "${SOURCE_DIR}/src" "${PREFIX}/"
install -m 0755 "${SOURCE_DIR}/scripts/usb-gadget-up.sh" "${PREFIX}/scripts/"
install -m 0755 "${SOURCE_DIR}/scripts/usb-gadget-down.sh" "${PREFIX}/scripts/"

if [[ -f "${CONFIG_DIR}/deck.yaml" ]]; then
    echo "    keeping your existing ${CONFIG_DIR}/deck.yaml"
    install -m 0644 "${SOURCE_DIR}/config/deck.yaml" "${CONFIG_DIR}/deck.yaml.example"
else
    install -m 0644 "${SOURCE_DIR}/config/deck.yaml" "${CONFIG_DIR}/deck.yaml"
    echo "    installed ${CONFIG_DIR}/deck.yaml"
fi

echo "==> Installing udev rules"
install -m 0644 "${SOURCE_DIR}/udev/99-pideck.rules" /etc/udev/rules.d/99-pideck.rules
udevadm control --reload-rules

echo "==> Installing systemd units"
for unit in pideck-gadget.service pideck.service; do
    sed -e "s|__PIDECK_DIR__|${PREFIX}|g" \
        -e "s|__PIDECK_USER__|${TARGET_USER}|g" \
        "${SOURCE_DIR}/systemd/${unit}" > "/etc/systemd/system/${unit}"
done
systemctl daemon-reload

echo "==> Adding ${TARGET_USER} to the video, render and input groups"
for group in video render input; do
    getent group "${group}" >/dev/null && usermod -aG "${group}" "${TARGET_USER}"
done

echo "==> Validating the installed config"
PYTHONPATH="${PREFIX}/src" python3 -m pideck --config "${CONFIG_DIR}/deck.yaml" --check

echo "==> Enabling services"
systemctl enable pideck-gadget.service pideck.service

echo
if [[ ${REBOOT_NEEDED} -eq 1 ]]; then
    echo "Done. Reboot to load the dwc2 overlay, then connect the Pi's USB-C"
    echo "port to your computer with a data cable:"
    echo "    sudo reboot"
else
    echo "Done. Start it now with:"
    echo "    sudo systemctl start pideck-gadget.service pideck.service"
fi
echo
echo "Power the Pi from the GPIO 5V pins or a PoE HAT -- the USB-C port is now"
echo "carrying data, and a host USB port cannot reliably supply a Pi 4 plus the"
echo "display."
