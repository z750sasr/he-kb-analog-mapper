"""Everglide AE64 Pro glue for the brand-independent mapper service."""

from __future__ import annotations

from typing import Any

from ..base import (
    DigitalOutputPolicy,
    KeyboardAdapter,
    KeyboardCapabilities,
    KeyboardDeviceDescriptor,
    KeyboardIdentity,
    KeyTravelEvent,
    TravelCalibration,
    device_fingerprint,
    device_selection_id,
)
from .layout import AE64_LAYOUT, AE64_MODELS
from .protocol import AE64Protocol


class EverglideAE64ProAdapter(KeyboardAdapter):
    """Poll read-only AE64 Hall route data and translate it into controller input."""

    adapter_id = "everglide_ae64pro"
    display_name = "Everglide AE64 Pro"
    layout = AE64_LAYOUT
    priority = 20
    capabilities = KeyboardCapabilities(digital_output_policy=False, profiles=True, layers=True)

    def __init__(self, hid_backend: Any | None = None, preferred_id: str = "auto") -> None:
        super().__init__(hid_backend, preferred_id)
        self.protocol = AE64Protocol(hid_backend=hid_backend, preferred_id=self.preferred_id)
        self.identity: KeyboardIdentity | None = None

    def enumerate_devices(self) -> tuple[KeyboardDeviceDescriptor, ...]:
        devices: list[KeyboardDeviceDescriptor] = []
        for info in self.protocol.enumerate_candidates():
            selection_id = device_selection_id(self.adapter_id, info)
            model_name = AE64_MODELS.get(
                (int(info.get("vendor_id", 0)), int(info.get("product_id", 0))),
                self.display_name,
            )
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
                "firmware": info.get("firmware"),
                "board_id": info.get("board_id"),
            },
        )
        return self.identity

    def prepare(self) -> None:
        self.protocol.prepare_stream()

    def read_event(self, timeout_ms: int = 100) -> KeyTravelEvent | None:
        return self.protocol.read_event(timeout_ms)

    def normalize_travel(self, raw_value: int, calibration: TravelCalibration) -> float:
        """Convert AE64 route distance (thousandths of a millimetre) to 0..1.

        The mapper's historic default full-scale (350) is for the HE30. Keep
        that default harmless on a newly detected AE64 by using its documented
        four-millimetre scale until the user supplies an AE64-scale value
        (typically 3,000–4,000) in Response settings.
        """

        if raw_value <= calibration.deadzone_raw:
            return 0.0
        full_scale = calibration.full_scale_raw if calibration.full_scale_raw >= 1000 else 4000
        return min(
            1.0,
            max(0.0, (raw_value - calibration.deadzone_raw) / max(1, full_scale - calibration.deadzone_raw)),
        )

    def apply_digital_output_policy(
        self,
        policy: DigitalOutputPolicy,
        bound_key_ids: set[int],
    ) -> tuple[bool, str]:
        del policy, bound_key_ids
        return (
            False,
            "AE64 Pro controller emulation reads Hall travel only; this adapter does not alter keyboard typing output.",
        )

    def close(self) -> None:
        self.protocol.close()


ADAPTER_CLASS = EverglideAE64ProAdapter
