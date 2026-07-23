"""Data objects shared by protocol, mapper service, UI, and tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .constants import ACTION_BY_ID, DEFAULT_MAPPINGS
from .hotkeys import normalize_hotkey


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """One HE30 0xA0 report after byte-level decoding."""

    mapping_type: int
    code1: int
    code2: int
    raw_travel: int
    status: int
    report: tuple[int, ...] = ()

    @property
    def signal(self) -> tuple[int, int, int]:
        return self.mapping_type, self.code1, self.code2


@dataclass(frozen=True, slots=True)
class ProfileChangeEvent:
    """Active onboard profile/layer update emitted by a 0xA1 report."""

    profile_index: int
    layer: int
    global_layer: int


@dataclass(slots=True)
class MapperConfig:
    """Versioned user configuration persisted under Windows AppData."""

    version: int = 3
    preferred_keyboard: str = "auto"
    mappings: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MAPPINGS))
    keyboard_mappings: dict[str, dict[str, str]] = field(default_factory=dict)
    deadzone_raw: int = 8
    max_raw: int = 350
    sensitivity: float = 1.0
    curve: str = "linear"
    digital_threshold: float = 0.45
    keyboard_keys_enabled: bool = True
    gamepad_mapping_override: bool = False
    auto_start: bool = True
    start_minimized: bool = False
    start_stop_hotkey: str = ""
    exit_hotkey: str = ""

    @staticmethod
    def _clean_mappings(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {
            str(int(index)): action
            for index, action in value.items()
            if str(index).lstrip("-").isdigit()
            and 0 <= int(index) < 512
            and action in ACTION_BY_ID
            and action != "none"
        }

    def sanitize(self) -> "MapperConfig":
        """Clamp untrusted JSON values and remove unknown mapping actions."""

        self.version = 3
        self.preferred_keyboard = str(self.preferred_keyboard or "auto").strip() or "auto"
        self.deadzone_raw = max(0, min(5000, int(self.deadzone_raw)))
        self.max_raw = max(self.deadzone_raw + 1, min(10000, int(self.max_raw)))
        self.sensitivity = max(0.1, min(3.0, float(self.sensitivity)))
        self.curve = self.curve if self.curve in {"linear", "gentle", "s_curve", "fast"} else "linear"
        self.digital_threshold = max(0.05, min(1.0, float(self.digital_threshold)))
        self.keyboard_keys_enabled = bool(self.keyboard_keys_enabled)
        self.gamepad_mapping_override = bool(self.gamepad_mapping_override)
        self.auto_start = bool(self.auto_start)
        self.start_minimized = bool(self.start_minimized)
        self.start_stop_hotkey = normalize_hotkey(self.start_stop_hotkey)
        self.exit_hotkey = normalize_hotkey(self.exit_hotkey)
        if self.start_stop_hotkey == self.exit_hotkey:
            self.exit_hotkey = ""
        cleaned_sets = {
            str(adapter_id): self._clean_mappings(mapping)
            for adapter_id, mapping in self.keyboard_mappings.items()
            if isinstance(adapter_id, str) and adapter_id.strip() and isinstance(mapping, dict)
        }
        # Version-1 files stored one HE30 mapping dictionary. It becomes the
        # initial adapter-specific set without losing the public ``mappings``
        # attribute used by older scripts.
        he30_mappings = cleaned_sets.setdefault("epomaker_he30", self._clean_mappings(self.mappings))
        self.keyboard_mappings = cleaned_sets
        self.mappings = he30_mappings
        return self

    def mappings_for(self, adapter_id: str) -> dict[str, str]:
        """Return a mutable mapping set isolated to one keyboard adapter."""

        adapter = str(adapter_id or "epomaker_he30")
        mapping = self.keyboard_mappings.setdefault(
            adapter,
            self.mappings if adapter == "epomaker_he30" else {},
        )
        if adapter == "epomaker_he30":
            self.mappings = mapping
        return mapping

    def bound_key_ids(self, adapter_id: str) -> set[int]:
        return {int(key_id) for key_id in self.mappings_for(adapter_id)}

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "MapperConfig":
        if not isinstance(value, dict):
            return cls()
        settings = value.get("settings", value)
        config = cls(
            version=value.get("version", 1),
            preferred_keyboard=value.get("preferred_keyboard", settings.get("preferred_keyboard", "auto")),
            mappings=dict(value.get("mappings", DEFAULT_MAPPINGS)),
            keyboard_mappings=dict(value.get("keyboard_mappings", {})),
            deadzone_raw=settings.get("deadzone_raw", settings.get("deadzone", 8)),
            max_raw=settings.get("max_raw", settings.get("max_pressure", 350)),
            sensitivity=settings.get("sensitivity", 1.0),
            curve=settings.get("curve", "linear"),
            digital_threshold=settings.get("digital_threshold", 0.45),
            keyboard_keys_enabled=settings.get(
                "keyboard_keys_enabled",
                value.get("keyboard_keys_enabled", True),
            ),
            gamepad_mapping_override=settings.get(
                "gamepad_mapping_override",
                value.get("gamepad_mapping_override", False),
            ),
            auto_start=settings.get("auto_start", True),
            start_minimized=settings.get("start_minimized", False),
            start_stop_hotkey=settings.get("start_stop_hotkey", ""),
            exit_hotkey=settings.get("exit_hotkey", ""),
        )
        return config.sanitize()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ServiceEvent:
    """Thread-safe message sent by the background service to UI and tray."""

    kind: str
    message: str = ""
    physical_index: int | None = None
    value: float | None = None
    raw_value: int | None = None
    keyboard_id: str | None = None
    keyboard_name: str | None = None
    layout_id: str | None = None
    digital_output_supported: bool | None = None
