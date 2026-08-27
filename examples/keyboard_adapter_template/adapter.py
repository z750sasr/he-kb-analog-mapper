"""Minimal registry glue plus the keyboard's raw-to-analog conversion."""

from he_keyboard_mapper.keyboards.base import (
    KeyboardAdapter,
    KeyboardDeviceDescriptor,
    TravelCalibration,
    device_fingerprint,
    device_selection_id,
)

from .layout import LAYOUT
from .protocol import BrandProtocol


class BrandAdapter(KeyboardAdapter):
    adapter_id = "brand_model"
    display_name = "Brand Model"
    layout = LAYOUT

    def __init__(self, hid_backend=None, preferred_id="auto"):
        super().__init__(hid_backend, preferred_id)
        self.protocol = BrandProtocol(hid_backend=hid_backend, preferred_id=preferred_id)

    def enumerate_devices(self):
        devices = []
        for info in self.protocol.enumerate_candidates():
            selection_id = device_selection_id(self.adapter_id, info)
            fingerprint = device_fingerprint(info)
            devices.append(
                KeyboardDeviceDescriptor(
                    self.adapter_id,
                    selection_id,
                    f"{self.display_name} #{fingerprint}",
                    self.layout.layout_id,
                )
            )
        return tuple(devices)

    def connect(self):
        return self.protocol.connect()

    def prepare(self):
        self.protocol.prepare()

    def read_event(self, timeout_ms=100):
        return self.protocol.read_event(timeout_ms)

    def normalize_travel(self, raw_value: int, calibration: TravelCalibration) -> float:
        span = max(1, calibration.full_scale_raw - calibration.deadzone_raw)
        return min(1.0, max(0.0, (raw_value - calibration.deadzone_raw) / span))

    def close(self):
        self.protocol.close()


ADAPTER_CLASS = BrandAdapter
