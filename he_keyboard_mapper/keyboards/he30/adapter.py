"""Adapter that translates HE30-specific reports into framework events."""

from __future__ import annotations

from typing import Any

from ...models import ProfileChangeEvent, TelemetryEvent
from ..base import (
    DigitalOutputPolicy,
    KeyboardAdapter,
    KeyboardCapabilities,
    KeyboardDeviceDescriptor,
    KeyboardIdentity,
    KeyTravelEvent,
    LayerChangeEvent,
    TravelCalibration,
    device_fingerprint,
    device_selection_id,
)
from .layout import HE30_LAYOUT, HE30_MODELS
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

    def __init__(self, hid_backend: Any | None = None, preferred_id: str = "auto") -> None:
        super().__init__(hid_backend, preferred_id)
        self.protocol = HE30Protocol(hid_backend=hid_backend, preferred_id=self.preferred_id)
        self.identity: KeyboardIdentity | None = None
        self.telemetry_reports = 0
        self.profile_reports = 0
        self.unresolved_reports = 0

    def enumerate_devices(self) -> tuple[KeyboardDeviceDescriptor, ...]:
        devices: list[KeyboardDeviceDescriptor] = []
        for info in self.protocol.enumerate_candidates():
            selection_id = device_selection_id(self.adapter_id, info)
            probe = HE30Protocol(
                hid_backend=self.hid_backend,
                timeout_ms=120,
                preferred_id=selection_id,
            )
            try:
                info = probe.connect()
            except Exception:
                continue
            finally:
                probe.close()
            selection_id = device_selection_id(self.adapter_id, info)
            model_name = HE30_MODELS.get(
                (int(info.get("vendor_id", 0)), int(info.get("product_id", 0))),
                ("EPOMAKER HE30", 1),
            )[0]
            fingerprint = device_fingerprint(info)
            devices.append(
                KeyboardDeviceDescriptor(
                    adapter_id=self.adapter_id,
                    selection_id=selection_id,
                    display_name=f"{model_name} #{fingerprint}",
                    layout_id=self.layout.layout_id,
                    details={
                        "vendor_id": int(info.get("vendor_id", 0)),
                        "product_id": int(info.get("product_id", 0)),
                        "interface_number": info.get("interface_number"),
                    },
                )
            )
        return tuple(devices)

    def connect(self) -> KeyboardIdentity:
        info = self.protocol.connect()
        selection_id = device_selection_id(self.adapter_id, info)
        fingerprint = device_fingerprint(info)
        device_name = f"{self.protocol.model_name} #{fingerprint}"
        self.identity = KeyboardIdentity(
            adapter_id=self.adapter_id,
            model_name=self.protocol.model_name,
            layout_id=self.layout.layout_id,
            device_id=selection_id,
            device_name=device_name,
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
            self.profile_reports += 1
            return LayerChangeEvent(event.profile_index, event.layer, event.global_layer)
        if not isinstance(event, TelemetryEvent):
            return None
        self.telemetry_reports += 1
        key_id = self.protocol.resolve_physical(event)
        if key_id is None:
            self.unresolved_reports += 1
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

    def diagnostics(self) -> dict[str, int | str | bool]:
        return {
            "telemetry_reports": self.telemetry_reports,
            "profile_reports": self.profile_reports,
            "unresolved_reports": self.unresolved_reports,
            "active_profile": self.protocol.active_profile,
            "active_layer": self.protocol.active_layer,
        }

    def close(self) -> None:
        self.protocol.close()


ADAPTER_CLASS = HE30Adapter
