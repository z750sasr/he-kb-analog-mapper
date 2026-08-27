"""Stable interfaces shared by every Hall-effect keyboard implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
from typing import Any


class KeyboardUnavailable(RuntimeError):
    """An adapter could not find or open one of its supported keyboards."""


@dataclass(frozen=True, slots=True)
class KeyboardKey:
    """One physical switch in a visual layout.

    ``key_id`` is the stable value emitted by the adapter. It does not need to
    be a HID key code; firmware matrix indexes are usually a better choice.
    Width is expressed in ordinary keyboard units (1u, 1.25u, 2.25u, ...).
    """

    key_id: int
    label: str
    width: float = 1.0
    hid_code: int | None = None

    @property
    def index(self) -> int:
        """Compatibility alias for the first HE30-only version of the app."""

        return self.key_id


@dataclass(frozen=True, slots=True)
class KeyboardLayout:
    """Brand-independent rows used by both configuration and live travel UI."""

    layout_id: str
    name: str
    rows: tuple[tuple[KeyboardKey, ...], ...]

    def __post_init__(self) -> None:
        keys = self.keys
        ids = [key.key_id for key in keys]
        if not self.layout_id.strip() or not self.name.strip():
            raise ValueError("A keyboard layout requires a stable id and name.")
        if not keys or len(ids) != len(set(ids)):
            raise ValueError("A keyboard layout must contain unique physical key ids.")
        if any(key.width <= 0 or not key.label for key in keys):
            raise ValueError("Every keyboard key requires a label and positive width.")

    @property
    def keys(self) -> tuple[KeyboardKey, ...]:
        return tuple(key for row in self.rows for key in row)

    @property
    def by_id(self) -> dict[int, KeyboardKey]:
        return {key.key_id: key for key in self.keys}


@dataclass(frozen=True, slots=True)
class TravelCalibration:
    """User-tunable raw range supplied to a keyboard's conversion function."""

    deadzone_raw: int
    full_scale_raw: int


@dataclass(frozen=True, slots=True)
class KeyTravelEvent:
    """A raw Hall sample already resolved to one physical layout key."""

    key_id: int
    raw_value: int
    status: int = 0


@dataclass(frozen=True, slots=True)
class LayerChangeEvent:
    """Optional onboard profile/layer event exposed consistently to the UI."""

    profile_index: int
    layer_index: int
    display_layer: int


@dataclass(frozen=True, slots=True)
class DigitalOutputPolicy:
    """Wooting-compatible semantics for ordinary keyboard output.

    When ``keyboard_keys_enabled`` is false, no physical keys should type.
    When override is true, only controller-bound keys should stop typing.
    Implementations must be device-specific; a process-wide Windows key hook is
    deliberately not used because it would block unrelated keyboards too.
    """

    keyboard_keys_enabled: bool = True
    gamepad_mapping_override: bool = False


@dataclass(frozen=True, slots=True)
class KeyboardCapabilities:
    """Optional behavior a protocol can advertise to reusable UI components."""

    digital_output_policy: bool = False
    profiles: bool = False
    layers: bool = False


def device_fingerprint(info: dict[str, Any]) -> str:
    """Return a short stable token for one HID collection path."""

    path = info.get("path", b"")
    if isinstance(path, bytes):
        source = path
    else:
        source = str(path).encode("utf-8", errors="replace")
    return hashlib.sha1(source).hexdigest()[:8].upper()


def device_selection_id(adapter_id: str, info: dict[str, Any]) -> str:
    """Build the UI/config identifier for one physical keyboard instance."""

    return f"{adapter_id}:{device_fingerprint(info)}"


@dataclass(frozen=True, slots=True)
class KeyboardDeviceDescriptor:
    """One selectable physical keyboard discovered before opening the mapper."""

    adapter_id: str
    selection_id: str
    display_name: str
    layout_id: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KeyboardIdentity:
    """Detected device metadata shown without leaking raw hidapi dictionaries."""

    adapter_id: str
    model_name: str
    layout_id: str
    device_id: str | None = None
    device_name: str | None = None
    profile_count: int = 1
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def settings_id(self) -> str:
        """Settings follow the physical device when available."""

        return self.device_id or self.adapter_id


class KeyboardAdapter(ABC):
    """The only interface the background mapper needs from a keyboard brand."""

    adapter_id: str
    display_name: str
    layout: KeyboardLayout
    priority: int = 100
    capabilities = KeyboardCapabilities()

    def __init__(self, hid_backend: Any | None = None, preferred_id: str = "auto") -> None:
        self.hid_backend = hid_backend
        self.preferred_id = preferred_id

    def enumerate_devices(self) -> tuple[KeyboardDeviceDescriptor, ...]:
        """Return selectable connected devices for this adapter, if supported."""

        return ()

    @abstractmethod
    def connect(self) -> KeyboardIdentity:
        """Auto-detect and open one compatible normal-mode interface."""

    @abstractmethod
    def prepare(self) -> None:
        """Enable/read whatever is required before streaming Hall samples."""

    @abstractmethod
    def read_event(self, timeout_ms: int = 100) -> KeyTravelEvent | LayerChangeEvent | None:
        """Return one resolved event, or ``None`` on a normal timeout."""

    @abstractmethod
    def normalize_travel(self, raw_value: int, calibration: TravelCalibration) -> float:
        """Convert this device's raw Hall unit to a linear 0.0-1.0 value."""

    def apply_digital_output_policy(
        self,
        policy: DigitalOutputPolicy,
        bound_key_ids: set[int],
    ) -> tuple[bool, str]:
        """Apply optional firmware-level typing suppression.

        Returning ``False`` is an explicit capability result, not an error. A
        future adapter can override this method and safely configure its device.
        """

        del policy, bound_key_ids
        return False, f"{self.display_name} does not expose digital-output control through this adapter."

    def diagnostics(self) -> dict[str, int | str | bool]:
        """Return optional adapter-specific counters for status messages."""

        return {}

    @abstractmethod
    def close(self) -> None:
        """Restore temporary device state and close the transport."""
