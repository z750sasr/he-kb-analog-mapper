from __future__ import annotations

import unittest

from he_keyboard_mapper.keyboards import (
    KeyboardAdapter,
    KeyboardCapabilities,
    KeyboardIdentity,
    KeyboardKey,
    KeyboardLayout,
    KeyboardRegistry,
    TravelCalibration,
)
from he_keyboard_mapper.keyboards.base import KeyboardUnavailable
from he_keyboard_mapper.keyboards.he30.adapter import HE30Adapter


TEST_LAYOUT = KeyboardLayout(
    "test_layout",
    "Test layout",
    ((KeyboardKey(0, "A"), KeyboardKey(1, "B", 1.5)),),
)


class MissingAdapter(KeyboardAdapter):
    adapter_id = "missing"
    display_name = "Missing keyboard"
    layout = TEST_LAYOUT
    priority = 1

    def connect(self):
        raise KeyboardUnavailable("not connected")

    def prepare(self):
        pass

    def read_event(self, timeout_ms=100):
        return None

    def normalize_travel(self, raw_value, calibration):
        return 0.0

    def close(self):
        pass


class PresentAdapter(MissingAdapter):
    adapter_id = "present"
    display_name = "Present keyboard"
    priority = 2
    capabilities = KeyboardCapabilities(digital_output_policy=True)

    def connect(self):
        return KeyboardIdentity(self.adapter_id, self.display_name, self.layout.layout_id)


class AdapterFrameworkTests(unittest.TestCase):
    def test_layout_rejects_duplicate_key_ids(self) -> None:
        with self.assertRaises(ValueError):
            KeyboardLayout(
                "duplicate",
                "Duplicate layout",
                ((KeyboardKey(1, "A"), KeyboardKey(1, "B")),),
            )

    def test_registry_auto_detection_falls_through_adapters(self) -> None:
        registry = KeyboardRegistry((MissingAdapter, PresentAdapter))
        adapter, identity = registry.connect()
        self.assertIsInstance(adapter, PresentAdapter)
        self.assertEqual(identity.adapter_id, "present")

    def test_preferred_adapter_does_not_probe_other_brands(self) -> None:
        registry = KeyboardRegistry((MissingAdapter, PresentAdapter))
        with self.assertRaises(KeyboardUnavailable):
            registry.connect("missing")

    def test_he30_owns_its_raw_travel_conversion(self) -> None:
        adapter = HE30Adapter()
        calibration = TravelCalibration(deadzone_raw=10, full_scale_raw=110)
        self.assertEqual(adapter.normalize_travel(10, calibration), 0.0)
        self.assertAlmostEqual(adapter.normalize_travel(60, calibration), 0.5)
        self.assertEqual(adapter.normalize_travel(999, calibration), 1.0)

    def test_he30_reports_digital_output_limitation(self) -> None:
        adapter = HE30Adapter()
        self.assertFalse(adapter.capabilities.digital_output_policy)


if __name__ == "__main__":
    unittest.main()
