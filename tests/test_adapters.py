from __future__ import annotations

import unittest

from he_keyboard_mapper.keyboards import (
    KeyboardAdapter,
    KeyboardCapabilities,
    KeyboardDeviceDescriptor,
    KeyboardIdentity,
    KeyboardKey,
    KeyboardLayout,
    KeyboardRegistry,
    TravelCalibration,
)
from he_keyboard_mapper.keyboards.base import device_selection_id
from he_keyboard_mapper.keyboards.base import KeyboardUnavailable
from he_keyboard_mapper.keyboards.he30.adapter import HE30Adapter
from he_keyboard_mapper.keyboards.everglide_ae64pro.adapter import EverglideAE64ProAdapter
from he_keyboard_mapper.keyboards.everglide_ae64pro.layout import AE64_LAYOUT, KEY_ID_BY_POSITION


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


class DeviceListAdapter(PresentAdapter):
    adapter_id = "device_list"
    display_name = "Device list keyboard"

    def enumerate_devices(self):
        first = {"path": b"same-model-1"}
        second = {"path": b"same-model-2"}
        return (
            KeyboardDeviceDescriptor(
                self.adapter_id,
                device_selection_id(self.adapter_id, first),
                "Device list keyboard #1",
                self.layout.layout_id,
            ),
            KeyboardDeviceDescriptor(
                self.adapter_id,
                device_selection_id(self.adapter_id, second),
                "Device list keyboard #2",
                self.layout.layout_id,
            ),
        )


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

    def test_registry_lists_distinct_physical_devices_for_same_model(self) -> None:
        registry = KeyboardRegistry((DeviceListAdapter,))
        devices = registry.enumerate_devices()
        self.assertEqual(len(devices), 2)
        self.assertNotEqual(devices[0].selection_id, devices[1].selection_id)
        self.assertTrue(devices[0].selection_id.startswith("device_list:"))

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

    def test_ae64_layout_preserves_the_64_key_firmware_matrix(self) -> None:
        self.assertEqual(len(AE64_LAYOUT.keys), 64)
        self.assertEqual(KEY_ID_BY_POSITION[(1, 0)], 0)  # Esc
        self.assertEqual(KEY_ID_BY_POSITION[(5, 8)], 63)  # Right arrow

    def test_ae64_adapter_is_discovered_without_a_central_registry_edit(self) -> None:
        adapter_type = KeyboardRegistry().adapter_type("everglide_ae64pro")
        self.assertIs(adapter_type, EverglideAE64ProAdapter)

    def test_ae64_uses_four_millimetres_when_he30_defaults_are_loaded(self) -> None:
        adapter = EverglideAE64ProAdapter()
        he30_defaults = TravelCalibration(deadzone_raw=8, full_scale_raw=350)
        self.assertAlmostEqual(adapter.normalize_travel(2004, he30_defaults), 0.5, places=3)
        ae64_scale = TravelCalibration(deadzone_raw=0, full_scale_raw=3000)
        self.assertAlmostEqual(adapter.normalize_travel(1500, ae64_scale), 0.5)


if __name__ == "__main__":
    unittest.main()
