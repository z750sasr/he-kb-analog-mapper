"""Minimal registry glue plus the keyboard's raw-to-analog conversion."""

from he30_mapper.keyboards.base import KeyboardAdapter, TravelCalibration

from .layout import LAYOUT
from .protocol import BrandProtocol


class BrandAdapter(KeyboardAdapter):
    adapter_id = "brand_model"
    display_name = "Brand Model"
    layout = LAYOUT

    def __init__(self, hid_backend=None):
        super().__init__(hid_backend)
        self.protocol = BrandProtocol()

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
