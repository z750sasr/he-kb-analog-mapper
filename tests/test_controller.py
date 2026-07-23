from __future__ import annotations

import unittest

from he30_mapper.controller import ControllerState, MappingEngine, SignalProcessor, VirtualXboxController
from he30_mapper.models import MapperConfig


class SignalProcessorTests(unittest.TestCase):
    def test_deadzone_and_linear_normalization(self) -> None:
        config = MapperConfig(deadzone_raw=10, max_raw=110, sensitivity=1.0)
        self.assertEqual(SignalProcessor.process(10, config), 0.0)
        self.assertAlmostEqual(SignalProcessor.process(60, config), 0.5)
        self.assertEqual(SignalProcessor.process(200, config), 1.0)

    def test_fast_curve_increases_partial_pressure(self) -> None:
        linear = MapperConfig(deadzone_raw=0, max_raw=100, curve="linear")
        fast = MapperConfig(deadzone_raw=0, max_raw=100, curve="fast")
        self.assertGreater(SignalProcessor.process(50, fast), SignalProcessor.process(50, linear))


class MappingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MapperConfig(
            mappings={
                "9": "left_stick_up",
                "15": "left_stick_down",
                "14": "left_stick_left",
                "16": "left_stick_right",
                "28": "button_a",
            },
            deadzone_raw=0,
            max_raw=100,
            digital_threshold=0.5,
        )
        self.engine = MappingEngine(self.config)

    def test_analog_directions_are_combined(self) -> None:
        _, state = self.engine.update_key(9, 75)
        self.assertAlmostEqual(state.left_y, 0.75)
        _, state = self.engine.update_key(15, 25)
        self.assertAlmostEqual(state.left_y, 0.5)
        _, state = self.engine.update_key(14, 40)
        self.assertAlmostEqual(state.left_x, -0.4)

    def test_digital_button_uses_threshold_and_releases(self) -> None:
        _, state = self.engine.update_key(28, 49)
        self.assertNotIn("button_a", state.buttons)
        _, state = self.engine.update_key(28, 50)
        self.assertIn("button_a", state.buttons)
        _, state = self.engine.update_key(28, 0)
        self.assertNotIn("button_a", state.buttons)


class XboxReportTests(unittest.TestCase):
    def test_state_is_encoded_without_loading_windows_driver(self) -> None:
        report = VirtualXboxController._report(
            ControllerState(
                left_x=-1.0,
                left_y=0.5,
                right_trigger=1.0,
                buttons=frozenset({"button_a", "dpad_up"}),
            )
        )
        self.assertEqual(report.wButtons, 0x1001)
        self.assertEqual(report.bRightTrigger, 255)
        self.assertEqual(report.sThumbLX, -32767)
        self.assertEqual(report.sThumbLY, 16384)


if __name__ == "__main__":
    unittest.main()
