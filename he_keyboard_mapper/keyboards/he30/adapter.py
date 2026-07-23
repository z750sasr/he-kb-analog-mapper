"""Adapter that translates HE30-specific reports into framework events."""

from __future__ import annotations

from typing import Any

from ...models import ProfileChangeEvent, TelemetryEvent
from ..base import (
    DigitalOutputPolicy,
    KeyboardAdapter,
    KeyboardCapabilities,
    KeyboardIdentity,
    KeyTravelEvent,
    LayerChangeEvent,
    TravelCalibration,
)
from .layout import HE30_LAYOUT
from .protocol import HE30Protocol


class HE30Adapter(KeyboardAdapter):
    """EPOMAKER HE30/GT60 normal-mode configuration interface."""

    adapter_id = "epomaker_he30"
    display_name = "EPOMAKER HE30 family"
    layout = HE30_LAYOUT
    priority = 10
    capabilities = KeyboardCapabilities(
        digital_output_policy=False,
        profiles=True,
        layers=True,
    )

    def __init__(self, hid_backend: Any | None = None) -> None:
        super().__init__(hid_backend)
        self.protocol = HE30Protocol(hid_backend=hid_backend)
        self.identity: KeyboardIdentity | None = None

    def connect(self) -> KeyboardIdentity:
        info = self.protocol.connect()
        self.identity = KeyboardIdentity(
            adapter_id=self.adapter_id,
            model_name=self.protocol.model_name,
            layout_id=self.layout.layout_id,
            profile_count=self.protocol.profile_count,
            details={
                "vendor_id": int(info.get("vendor_id", 0)),
                "product_id": int(info.get("product_id", 0)),
                "interface_number": info.get("interface_number"),
                "usage_page": info.get("usage_page"),
                "usage": info.get("usage"),
            },
        )
        return self.identity

    def prepare(self) -> None:
        self.protocol.prepare_stream()

    def read_event(self, timeout_ms: int = 100) -> KeyTravelEvent | LayerChangeEvent | None:
        event = self.protocol.read_event(timeout_ms)
        if isinstance(event, ProfileChangeEvent):
            return LayerChangeEvent(event.profile_index, event.layer, event.global_layer)
        if not isinstance(event, TelemetryEvent):
            return None
        key_id = self.protocol.resolve_physical(event)
        if key_id is None:
            return None
        return KeyTravelEvent(key_id=key_id, raw_value=event.raw_travel, status=event.status)

    def normalize_travel(self, raw_value: int, calibration: TravelCalibration) -> float:
        """Convert the HE30's approximately 0-350 raw range to 0.0-1.0."""

        if raw_value <= calibration.deadzone_raw:
            return 0.0
        span = max(1, calibration.full_scale_raw - calibration.deadzone_raw)
        return min(1.0, max(0.0, (raw_value - calibration.deadzone_raw) / span))

    def apply_digital_output_policy(
        self,
        policy: DigitalOutputPolicy,
        bound_key_ids: set[int],
    ) -> tuple[bool, str]:
        del bound_key_ids
        if policy.keyboard_keys_enabled and not policy.gamepad_mapping_override:
            return False, "Normal HE30 keyboard output remains enabled; suppression is unavailable."
        return (
            False,
            "HE30 firmware does not expose safe gamepad typing suppression. "
            "Its Hall report contains the current mapping instead of a physical sensor id, "
            "so unmapping keys would also make analog keys indistinguishable.",
        )

    def close(self) -> None:
        self.protocol.close()


ADAPTER_CLASS = HE30Adapter
