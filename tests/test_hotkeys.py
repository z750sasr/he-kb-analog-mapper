from __future__ import annotations

import unittest

from he_keyboard_mapper.hotkeys import HotkeyBinding, hotkey_from_tk_event, normalize_hotkey


class HotkeyTests(unittest.TestCase):
    def test_parser_canonicalizes_modifier_order(self) -> None:
        binding = HotkeyBinding.parse("shift + alt + ctrl + f8")
        self.assertEqual(binding.text, "Ctrl+Alt+Shift+F8")
        self.assertEqual(binding.virtual_key, 0x77)

    def test_tk_keypress_translation(self) -> None:
        self.assertEqual(hotkey_from_tk_event("m", 0x0004 | 0x0001), "Ctrl+Shift+M")
        self.assertEqual(hotkey_from_tk_event("Control_L", 0x0004), "")

    def test_invalid_hotkey_normalizes_to_disabled(self) -> None:
        self.assertEqual(normalize_hotkey("Ctrl+NotARealKey"), "")


if __name__ == "__main__":
    unittest.main()
