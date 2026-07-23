"""Physical HE30 layout copied from the alternate web driver's visualization."""

from __future__ import annotations

from ..base import KeyboardKey, KeyboardLayout


HE30_ROWS: tuple[tuple[KeyboardKey, ...], ...] = (
    (
        KeyboardKey(0, "Esc", hid_code=0x29),
        KeyboardKey(30, "F1", hid_code=0x3A),
        KeyboardKey(31, "F2", hid_code=0x3B),
        KeyboardKey(32, "F3", hid_code=0x3C),
        KeyboardKey(33, "F4", hid_code=0x3D),
        KeyboardKey(34, "F5", hid_code=0x3E),
        KeyboardKey(35, "F6", hid_code=0x3F),
    ),
    (
        KeyboardKey(29, "`", hid_code=0x35),
        KeyboardKey(1, "1", hid_code=0x1E),
        KeyboardKey(2, "2", hid_code=0x1F),
        KeyboardKey(3, "3", hid_code=0x20),
        KeyboardKey(4, "4", hid_code=0x21),
        KeyboardKey(5, "5", hid_code=0x22),
        KeyboardKey(6, "6", hid_code=0x23),
    ),
    (
        KeyboardKey(7, "Tab", 1.5, 0x2B),
        KeyboardKey(8, "Q", hid_code=0x14),
        KeyboardKey(9, "W", hid_code=0x1A),
        KeyboardKey(10, "E", hid_code=0x08),
        KeyboardKey(11, "R", hid_code=0x15),
        KeyboardKey(12, "T", hid_code=0x17),
    ),
    (
        KeyboardKey(13, "Caps", 1.75, 0x39),
        KeyboardKey(14, "A", hid_code=0x04),
        KeyboardKey(15, "S", hid_code=0x16),
        KeyboardKey(16, "D", hid_code=0x07),
        KeyboardKey(17, "F", hid_code=0x09),
        KeyboardKey(18, "G", hid_code=0x0A),
    ),
    (
        KeyboardKey(19, "Shift", 2.25, 0xE1),
        KeyboardKey(20, "Z", hid_code=0x1D),
        KeyboardKey(21, "X", hid_code=0x1B),
        KeyboardKey(22, "C", hid_code=0x06),
        KeyboardKey(23, "V", hid_code=0x19),
        KeyboardKey(24, "B", hid_code=0x05),
    ),
    (
        KeyboardKey(25, "Ctrl", 1.25, 0xE0),
        KeyboardKey(26, "Fn", 1.25),
        KeyboardKey(27, "Alt", 1.25, 0xE2),
        KeyboardKey(28, "Space", 2.75, 0x2C),
    ),
)

HE30_LAYOUT = KeyboardLayout("he30_36", "HE30 36-key layout", HE30_ROWS)
PHYSICAL_KEYS = HE30_LAYOUT.keys
PHYSICAL_BY_INDEX = HE30_LAYOUT.by_id
PHYSICAL_BY_HID = {key.hid_code: key.key_id for key in PHYSICAL_KEYS if key.hid_code is not None}

# Normal configuration interfaces only; updater and bootloader IDs stay absent.
HE30_MODELS = {
    (0x19F5, 0xFB4C): ("EPOMAKER HE30", 3),
}
