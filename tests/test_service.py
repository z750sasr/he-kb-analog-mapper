from __future__ import annotations

import threading
import time
import unittest

from he30_mapper.controller import ControllerState
from he30_mapper.keyboards import (
    DigitalOutputPolicy,
    KeyboardAdapter,
    KeyboardCapabilities,
    KeyboardIdentity,
    KeyboardKey,
    KeyboardLayout,
    KeyboardRegistry,
    KeyTravelEvent,
)
from he30_mapper.models import MapperConfig
from he30_mapper.service import MapperService


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


class MapperServiceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
