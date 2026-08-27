from __future__ import annotations

import threading
import time
import unittest

from he_keyboard_mapper.controller import ControllerState
from he_keyboard_mapper.keyboards import (
    DigitalOutputPolicy,
    KeyboardAdapter,
    KeyboardCapabilities,
    KeyboardDeviceDescriptor,
    KeyboardIdentity,
    KeyboardKey,
    KeyboardLayout,
    KeyboardRegistry,
    KeyTravelEvent,
)
from he_keyboard_mapper.models import MapperConfig
from he_keyboard_mapper.service import MapperService


SERVICE_LAYOUT = KeyboardLayout("service_test", "Service test", ((KeyboardKey(1, "A"),),))


class StreamingAdapter(KeyboardAdapter):
    adapter_id = "streaming"
    display_name = "Streaming keyboard"
    layout = SERVICE_LAYOUT
    capabilities = KeyboardCapabilities(digital_output_policy=True)
    last_instance = None

    def __init__(self, hid_backend=None):
        super().__init__(hid_backend)
        type(self).last_instance = self
        self.sent = False
        self.closed = False
        self.policy = None

    def connect(self):
        return KeyboardIdentity(self.adapter_id, self.display_name, self.layout.layout_id)

    def prepare(self):
        pass

    def read_event(self, timeout_ms=100):
        if not self.sent:
            self.sent = True
            return KeyTravelEvent(1, 75)
        time.sleep(min(timeout_ms, 10) / 1000)
        return None

    def normalize_travel(self, raw_value, calibration):
        return raw_value / 100

    def apply_digital_output_policy(self, policy, bound_key_ids):
        self.policy = (policy, set(bound_key_ids))
        return True, "Policy applied"

    def close(self):
        self.closed = True


class RecordingController:
    def __init__(self):
        self.states = []
        self.travel_received = threading.Event()
        self.closed = False

    def apply(self, state: ControllerState):
        self.states.append(state)
        if "button_a" in state.buttons:
            self.travel_received.set()

    def reset(self):
        self.states.append(ControllerState())

    def close(self):
        self.closed = True


class FirstSwitchAdapter(StreamingAdapter):
    adapter_id = "first_switch"
    display_name = "First switch keyboard"
    last_instance = None


class SecondSwitchAdapter(StreamingAdapter):
    adapter_id = "second_switch"
    display_name = "Second switch keyboard"
    last_instance = None


class MultiDeviceAdapter(KeyboardAdapter):
    adapter_id = "multi"
    display_name = "Multi keyboard"
    layout = SERVICE_LAYOUT
    instances: list["MultiDeviceAdapter"] = []

    def __init__(self, hid_backend=None, preferred_id="auto"):
        super().__init__(hid_backend, preferred_id)
        self.sent = False
        self.closed = False
        type(self).instances.append(self)

    def enumerate_devices(self):
        return (
            KeyboardDeviceDescriptor(self.adapter_id, "multi:first", "Multi keyboard #FIRST", self.layout.layout_id),
            KeyboardDeviceDescriptor(self.adapter_id, "multi:second", "Multi keyboard #SECOND", self.layout.layout_id),
        )

    def connect(self):
        return KeyboardIdentity(
            self.adapter_id,
            "Multi keyboard",
            self.layout.layout_id,
            device_id=self.preferred_id,
            device_name=self.preferred_id,
        )

    def prepare(self):
        pass

    def read_event(self, timeout_ms=100):
        if not self.sent:
            self.sent = True
            return KeyTravelEvent(1, 100)
        time.sleep(min(timeout_ms, 10) / 1000)
        return None

    def normalize_travel(self, raw_value, calibration):
        return raw_value / 100

    def close(self):
        self.closed = True


class MapperServiceTests(unittest.TestCase):
    def test_service_owns_a_versioned_config_snapshot(self) -> None:
        original = MapperConfig(sensitivity=1.0).sanitize()
        service = MapperService(
            original,
            registry=KeyboardRegistry((StreamingAdapter,)),
            controller_factory=RecordingController,
        )
        snapshot, revision = service._config_snapshot()
        original.sensitivity = 3.0
        self.assertEqual(snapshot.sensitivity, 1.0)
        self.assertEqual(revision, 0)

        service.update_config(original)
        updated, next_revision = service._config_snapshot()
        self.assertEqual(updated.sensitivity, 3.0)
        self.assertEqual(next_revision, 1)

    def test_adapter_policy_and_travel_flow_through_shared_service(self) -> None:
        config = MapperConfig(
            mappings={},
            keyboard_mappings={"streaming": {"1": "button_a"}},
            keyboard_keys_enabled=True,
            gamepad_mapping_override=True,
            auto_start=False,
        ).sanitize()
        registry = KeyboardRegistry((StreamingAdapter,))
        controller = RecordingController()
        service = MapperService(config, registry=registry, controller_factory=lambda: controller)
        service.start()
        self.assertTrue(controller.travel_received.wait(1.0))
        service.stop()

        adapter = StreamingAdapter.last_instance
        self.assertIsNotNone(adapter)
        policy, bound = adapter.policy
        self.assertEqual(policy, DigitalOutputPolicy(True, True))
        self.assertEqual(bound, {1})
        self.assertTrue(adapter.closed)
        self.assertTrue(controller.closed)

    def test_preferred_keyboard_change_reconnects_without_manual_restart(self) -> None:
        FirstSwitchAdapter.last_instance = None
        SecondSwitchAdapter.last_instance = None
        config = MapperConfig(
            preferred_keyboard="first_switch",
            mappings={},
            keyboard_mappings={
                "first_switch": {"1": "button_a"},
                "second_switch": {"1": "button_b"},
            },
            auto_start=False,
        ).sanitize()
        registry = KeyboardRegistry((FirstSwitchAdapter, SecondSwitchAdapter))
        controller = RecordingController()
        service = MapperService(config, registry=registry, controller_factory=lambda: controller)

        service.start()
        self.assertTrue(controller.travel_received.wait(1.0))

        config.preferred_keyboard = "second_switch"
        service.update_config(config)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not any("button_b" in state.buttons for state in controller.states):
            time.sleep(0.01)
        service.stop()

        self.assertIsNotNone(FirstSwitchAdapter.last_instance)
        self.assertIsNotNone(SecondSwitchAdapter.last_instance)
        self.assertTrue(FirstSwitchAdapter.last_instance.closed)
        self.assertTrue(SecondSwitchAdapter.last_instance.closed)
        self.assertTrue(any("button_b" in state.buttons for state in controller.states))

    def test_auto_detection_creates_one_controller_per_physical_keyboard(self) -> None:
        MultiDeviceAdapter.instances = []
        config = MapperConfig(
            mappings={},
            keyboard_mappings={
                "multi:first": {"1": "button_a"},
                "multi:second": {"1": "button_b"},
            },
            auto_start=False,
        ).sanitize()
        registry = KeyboardRegistry((MultiDeviceAdapter,))
        controllers: list[RecordingController] = []

        def controller_factory():
            controller = RecordingController()
            controllers.append(controller)
            return controller

        service = MapperService(config, registry=registry, controller_factory=controller_factory)
        service.start()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and len(controllers) < 2:
            time.sleep(0.01)
        service.stop()

        self.assertEqual(len(controllers), 2)
        button_sets = [set().union(*(state.buttons for state in controller.states)) for controller in controllers]
        self.assertIn({"button_a"}, button_sets)
        self.assertIn({"button_b"}, button_sets)
        self.assertTrue(all(controller.closed for controller in controllers))

    def test_disabled_physical_keyboard_does_not_create_controller(self) -> None:
        MultiDeviceAdapter.instances = []
        config = MapperConfig(
            mappings={},
            keyboard_mappings={
                "multi:first": {"1": "button_a"},
                "multi:second": {"1": "button_b"},
            },
            auto_start=False,
        ).sanitize()
        config.settings_for("multi:second").controller_enabled = False
        registry = KeyboardRegistry((MultiDeviceAdapter,))
        controllers: list[RecordingController] = []

        def controller_factory():
            controller = RecordingController()
            controllers.append(controller)
            return controller

        service = MapperService(config, registry=registry, controller_factory=controller_factory)
        service.start()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and len(controllers) < 1:
            time.sleep(0.01)
        service.stop()

        self.assertEqual(len(controllers), 1)
        button_sets = [set().union(*(state.buttons for state in controller.states)) for controller in controllers]
        self.assertEqual(button_sets, [{"button_a"}])


if __name__ == "__main__":
    unittest.main()
