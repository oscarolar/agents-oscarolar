"""USB HID usage tables for the keyboard and consumer-control gadgets.

Codes come from the USB HID Usage Tables spec: keyboard usages are page 0x07,
consumer-control usages are page 0x0C. Only the subset a macro pad realistically
needs is mapped -- if a name is missing, `resolve_combo` raises with the full
list of accepted names rather than silently sending nothing.
"""

MODIFIERS = {
    "ctrl": 0x01,
    "lctrl": 0x01,
    "shift": 0x02,
    "lshift": 0x02,
    "alt": 0x04,
    "lalt": 0x04,
    "gui": 0x08,
    "lgui": 0x08,
    "win": 0x08,
    "cmd": 0x08,
    "super": 0x08,
    "meta": 0x08,
    "rctrl": 0x10,
    "rshift": 0x20,
    "ralt": 0x40,
    "altgr": 0x40,
    "rgui": 0x80,
    "rwin": 0x80,
}

KEYS = {
    "a": 0x04, "b": 0x05, "c": 0x06, "d": 0x07, "e": 0x08, "f": 0x09,
    "g": 0x0A, "h": 0x0B, "i": 0x0C, "j": 0x0D, "k": 0x0E, "l": 0x0F,
    "m": 0x10, "n": 0x11, "o": 0x12, "p": 0x13, "q": 0x14, "r": 0x15,
    "s": 0x16, "t": 0x17, "u": 0x18, "v": 0x19, "w": 0x1A, "x": 0x1B,
    "y": 0x1C, "z": 0x1D,
    "1": 0x1E, "2": 0x1F, "3": 0x20, "4": 0x21, "5": 0x22,
    "6": 0x23, "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27,
    "enter": 0x28, "return": 0x28,
    "esc": 0x29, "escape": 0x29,
    "backspace": 0x2A,
    "tab": 0x2B,
    "space": 0x2C,
    "minus": 0x2D, "equal": 0x2E,
    "leftbracket": 0x2F, "rightbracket": 0x30,
    "backslash": 0x31,
    "semicolon": 0x33, "apostrophe": 0x34, "grave": 0x35,
    "comma": 0x36, "period": 0x37, "slash": 0x38,
    "capslock": 0x39,
    "f1": 0x3A, "f2": 0x3B, "f3": 0x3C, "f4": 0x3D, "f5": 0x3E, "f6": 0x3F,
    "f7": 0x40, "f8": 0x41, "f9": 0x42, "f10": 0x43, "f11": 0x44, "f12": 0x45,
    "printscreen": 0x46, "scrolllock": 0x47, "pause": 0x48,
    "insert": 0x49, "home": 0x4A, "pageup": 0x4B,
    "delete": 0x4C, "end": 0x4D, "pagedown": 0x4E,
    "right": 0x4F, "left": 0x50, "down": 0x51, "up": 0x52,
    "numlock": 0x53,
    "kp_slash": 0x54, "kp_asterisk": 0x55, "kp_minus": 0x56, "kp_plus": 0x57,
    "kp_enter": 0x58,
    "kp1": 0x59, "kp2": 0x5A, "kp3": 0x5B, "kp4": 0x5C, "kp5": 0x5D,
    "kp6": 0x5E, "kp7": 0x5F, "kp8": 0x60, "kp9": 0x61, "kp0": 0x62,
    "kp_period": 0x63,
    "menu": 0x65, "application": 0x65,
    # F13-F24 are the sweet spot for a macro pad: almost no application binds
    # them by default, so they never collide with an existing shortcut.
    "f13": 0x68, "f14": 0x69, "f15": 0x6A, "f16": 0x6B, "f17": 0x6C,
    "f18": 0x6D, "f19": 0x6E, "f20": 0x6F, "f21": 0x70, "f22": 0x71,
    "f23": 0x72, "f24": 0x73,
}

# Consumer control usages (page 0x0C), sent as a 2-byte little-endian report.
CONSUMER = {
    "play_pause": 0x00CD,
    "stop": 0x00B7,
    "next": 0x00B5,
    "previous": 0x00B6,
    "prev": 0x00B6,
    "fast_forward": 0x00B3,
    "rewind": 0x00B4,
    "mute": 0x00E2,
    "volume_up": 0x00E9,
    "volume_down": 0x00EA,
    "brightness_up": 0x006F,
    "brightness_down": 0x0070,
}

# US layout: printable character -> (needs_shift, keyboard usage).
_UNSHIFTED = {
    "-": "minus", "=": "equal", "[": "leftbracket", "]": "rightbracket",
    "\\": "backslash", ";": "semicolon", "'": "apostrophe", "`": "grave",
    ",": "comma", ".": "period", "/": "slash", " ": "space",
    "\n": "enter", "\t": "tab",
}
_SHIFTED = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6",
    "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "minus", "+": "equal", "{": "leftbracket", "}": "rightbracket",
    "|": "backslash", ":": "semicolon", '"': "apostrophe", "~": "grave",
    "<": "comma", ">": "period", "?": "slash",
}


class UnknownKeyError(ValueError):
    """Raised when a combo names a key or modifier that has no HID usage."""


def resolve_combo(combo):
    """Turn ``"ctrl+shift+m"`` into ``(modifier_bitmask, [usage, ...])``.

    Modifiers may appear in any order and any case. Everything that is not a
    modifier is treated as a regular key; the HID boot-keyboard report carries
    at most six of those at once.
    """
    if not isinstance(combo, str) or not combo.strip():
        raise UnknownKeyError("key combo must be a non-empty string")

    modifier_mask = 0
    usages = []
    for raw_part in combo.split("+"):
        part = raw_part.strip().lower()
        if not part:
            raise UnknownKeyError(f"empty segment in key combo {combo!r}")
        if part in MODIFIERS:
            modifier_mask |= MODIFIERS[part]
        elif part in KEYS:
            usages.append(KEYS[part])
        else:
            raise UnknownKeyError(
                f"unknown key {part!r} in combo {combo!r}. "
                f"Known keys: {', '.join(sorted(KEYS))}. "
                f"Known modifiers: {', '.join(sorted(MODIFIERS))}."
            )

    if len(usages) > 6:
        raise UnknownKeyError(
            f"combo {combo!r} holds {len(usages)} non-modifier keys; "
            "the HID boot keyboard report supports at most 6"
        )
    return modifier_mask, usages


def resolve_char(char):
    """Map one printable character to ``(modifier_bitmask, usage)``.

    Returns ``None`` for characters outside the US layout (accents, emoji),
    which the caller should skip rather than mistype.
    """
    if char in _UNSHIFTED:
        return 0, KEYS[_UNSHIFTED[char]]
    if char in _SHIFTED:
        return MODIFIERS["shift"], KEYS[_SHIFTED[char]]
    if char.isupper() and char.lower() in KEYS:
        return MODIFIERS["shift"], KEYS[char.lower()]
    if char in KEYS:
        return 0, KEYS[char]
    return None


def resolve_consumer(name):
    """Look up a consumer-control usage by name."""
    key = str(name).strip().lower()
    if key not in CONSUMER:
        raise UnknownKeyError(
            f"unknown media key {name!r}. Known: {', '.join(sorted(CONSUMER))}."
        )
    return CONSUMER[key]
