from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from he_keyboard_mapper.config import load_config, save_config
from he_keyboard_mapper.models import MapperConfig


class ConfigTests(unittest.TestCase):
    def test_round_trip_and_sanitization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            config = MapperConfig(
                mappings={"9": "left_stick_up", "10": "not_real", "999": "button_a"},
                deadzone_raw=-4,
                max_raw=0,
                sensitivity=99,
                digital_threshold=5,
            )
            save_config(config, path)
            loaded = load_config(path)
            self.assertEqual(loaded.mappings, {"9": "left_stick_up"})
            self.assertEqual(loaded.deadzone_raw, 0)
            self.assertEqual(loaded.max_raw, 1)
            self.assertEqual(loaded.sensitivity, 3.0)
            self.assertEqual(loaded.digital_threshold, 1.0)

    def test_missing_file_uses_useful_defaults(self) -> None:
        config = load_config(Path("definitely-not-present.json"))
        self.assertEqual(config.mappings["9"], "left_stick_up")

    def test_mappings_are_isolated_per_keyboard_adapter(self) -> None:
        config = MapperConfig().sanitize()
        other = config.mappings_for("example_other_keyboard")
        other["1"] = "button_b"
        self.assertNotIn("1", config.mappings_for("epomaker_he30"))
        restored = MapperConfig.from_dict(config.to_dict())
        self.assertEqual(restored.mappings_for("example_other_keyboard"), {"1": "button_b"})

    def test_output_policy_preferences_round_trip(self) -> None:
        config = MapperConfig(
            keyboard_keys_enabled=False,
            gamepad_mapping_override=True,
            preferred_keyboard="example_other_keyboard",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_config(config, path)
            loaded = load_config(path)
        self.assertFalse(loaded.keyboard_keys_enabled)
        self.assertTrue(loaded.gamepad_mapping_override)
        self.assertEqual(loaded.preferred_keyboard, "example_other_keyboard")

    def test_global_hotkeys_are_normalized_and_round_trip(self) -> None:
        config = MapperConfig(
            start_stop_hotkey=" shift + ctrl + m ",
            exit_hotkey="Ctrl+Alt+F12",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_config(config, path)
            loaded = load_config(path)
        self.assertEqual(loaded.start_stop_hotkey, "Ctrl+Shift+M")
        self.assertEqual(loaded.exit_hotkey, "Ctrl+Alt+F12")

    def test_duplicate_or_invalid_hotkeys_are_cleared(self) -> None:
        duplicate = MapperConfig(
            start_stop_hotkey="Ctrl+M",
            exit_hotkey="Ctrl+M",
        ).sanitize()
        invalid = MapperConfig(start_stop_hotkey="Ctrl+DefinitelyNotAKey").sanitize()
        self.assertEqual(duplicate.start_stop_hotkey, "Ctrl+M")
        self.assertEqual(duplicate.exit_hotkey, "")
        self.assertEqual(invalid.start_stop_hotkey, "")


if __name__ == "__main__":
    unittest.main()
