"""Data objects shared by protocol, mapper service, UI, and tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .constants import ACTION_BY_ID, DEFAULT_MAPPINGS
from .hotkeys import normalize_hotkey


def base_keyboard_id(keyboard_id: str) -> str:
    """Return the adapter portion of a physical keyboard settings id."""

    return str(keyboard_id or "epomaker_he30").split(":", 1)[0]


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
class KeyboardSettings:
    """Per-keyboard mapping and response settings.

    Global app settings such as auto-start and hotkeys stay on MapperConfig.
    Everything here can differ between two brands, or between two plugged-in
    copies of the same model.
    """

    mappings: dict[str, str] = field(default_factory=dict)
    deadzone_raw: int = 8
    max_raw: int = 350
    sensitivity: float = 1.0
    curve: str = "linear"
    digital_threshold: float = 0.45
    keyboard_keys_enabled: bool = True
    gamepad_mapping_override: bool = False
    controller_enabled: bool = True

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "KeyboardSettings":
        if not isinstance(value, dict):
            return cls()
        return cls(
            mappings=MapperConfig._clean_mappings(value.get("mappings", {})),
            deadzone_raw=value.get("deadzone_raw", value.get("deadzone", 8)),
            max_raw=value.get("max_raw", value.get("max_pressure", 350)),
            sensitivity=value.get("sensitivity", 1.0),
            curve=value.get("curve", "linear"),
            digital_threshold=value.get("digital_threshold", 0.45),
            keyboard_keys_enabled=value.get("keyboard_keys_enabled", True),
            gamepad_mapping_override=value.get("gamepad_mapping_override", False),
            controller_enabled=value.get("controller_enabled", True),
        ).sanitize()

    def sanitize(self) -> "KeyboardSettings":
        self.mappings = MapperConfig._clean_mappings(self.mappings)
        self.deadzone_raw = max(0, min(5000, int(self.deadzone_raw)))
        self.max_raw = max(self.deadzone_raw + 1, min(10000, int(self.max_raw)))
        self.sensitivity = max(0.1, min(3.0, float(self.sensitivity)))
        self.curve = self.curve if self.curve in {"linear", "gentle", "s_curve", "fast"} else "linear"
        self.digital_threshold = max(0.05, min(1.0, float(self.digital_threshold)))
        self.keyboard_keys_enabled = bool(self.keyboard_keys_enabled)
        self.gamepad_mapping_override = bool(self.gamepad_mapping_override)
        self.controller_enabled = bool(self.controller_enabled)
        return self


@dataclass(slots=True)
class MapperConfig:
    """Versioned user configuration persisted under Windows AppData."""

    version: int = 5
    preferred_keyboard: str = "auto"
    known_keyboards: dict[str, str] = field(default_factory=dict)
    mappings: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MAPPINGS))
    keyboard_mappings: dict[str, dict[str, str]] = field(default_factory=dict)
    keyboard_settings: dict[str, KeyboardSettings] = field(default_factory=dict)
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

        self.version = 5
        self.preferred_keyboard = str(self.preferred_keyboard or "auto").strip() or "auto"
        self.known_keyboards = {
            str(keyboard_id): str(label)
            for keyboard_id, label in self.known_keyboards.items()
            if isinstance(keyboard_id, str)
            and keyboard_id.strip()
            and isinstance(label, str)
            and label.strip()
        }
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
        cleaned_settings: dict[str, KeyboardSettings] = {}
        for keyboard_id, settings in self.keyboard_settings.items():
            if isinstance(keyboard_id, str) and keyboard_id.strip():
                cleaned_settings[keyboard_id] = (
                    settings if isinstance(settings, KeyboardSettings) else KeyboardSettings.from_dict(settings)
                ).sanitize()
        for keyboard_id, mappings in cleaned_sets.items():
            cleaned_settings.setdefault(keyboard_id, self._legacy_settings(mappings))
        self.keyboard_settings = cleaned_settings
        self.keyboard_mappings = {
            keyboard_id: settings.mappings
            for keyboard_id, settings in self.keyboard_settings.items()
        }
        self.mappings = self.keyboard_settings.get("epomaker_he30", self._legacy_settings(he30_mappings)).mappings
        return self

    def _legacy_settings(self, mappings: dict[str, str]) -> KeyboardSettings:
        return KeyboardSettings(
            mappings=dict(mappings),
            deadzone_raw=self.deadzone_raw,
            max_raw=self.max_raw,
            sensitivity=self.sensitivity,
            curve=self.curve,
            digital_threshold=self.digital_threshold,
            keyboard_keys_enabled=self.keyboard_keys_enabled,
            gamepad_mapping_override=self.gamepad_mapping_override,
            controller_enabled=True,
        ).sanitize()

    def mappings_for(self, adapter_id: str) -> dict[str, str]:
        """Return a mutable mapping set isolated to one keyboard adapter."""

        mapping = self.settings_for(adapter_id).mappings
        if base_keyboard_id(adapter_id) == "epomaker_he30":
            self.mappings = mapping
        return mapping

    def bound_key_ids(self, adapter_id: str) -> set[int]:
        return {int(key_id) for key_id in self.mappings_for(adapter_id)}

    def settings_for(self, keyboard_id: str) -> KeyboardSettings:
        """Return a mutable per-keyboard setting bucket, seeding old defaults."""

        key = str(keyboard_id or "epomaker_he30")
        settings = self.keyboard_settings.get(key)
        if settings is not None:
            return settings
        base_key = base_keyboard_id(key)
        seed = self.keyboard_settings.get(base_key)
        if seed is not None:
            settings = KeyboardSettings.from_dict(asdict(seed))
        elif base_key == "epomaker_he30":
            settings = self._legacy_settings(self._clean_mappings(self.mappings))
        else:
            settings = self._legacy_settings({})
        self.keyboard_settings[key] = settings
        self.keyboard_mappings[key] = settings.mappings
        return settings

    def remember_keyboard(self, keyboard_id: str, display_name: str) -> None:
        """Persist a friendly label for one physical keyboard instance.

        This lets the UI manage a keyboard's saved data even after that board is
        unplugged. The hardware-specific id remains the source of truth; the
        label is only for humans.
        """

        key = str(keyboard_id or "").strip()
        label = str(display_name or "").strip()
        if key and label:
            self.known_keyboards[key] = label
            self.settings_for(key)

    def forget_keyboard(self, keyboard_id: str) -> None:
        """Remove all saved state for one registered physical keyboard."""

        key = str(keyboard_id or "").strip()
        if not key:
            return
        self.known_keyboards.pop(key, None)
        self.keyboard_settings.pop(key, None)
        self.keyboard_mappings.pop(key, None)
        if self.preferred_keyboard == key:
            self.preferred_keyboard = "auto"

    def apply_settings_for(self, keyboard_id: str) -> "MapperConfig":
        """Load one keyboard's bucket into legacy fields used by the engine/UI."""

        settings = self.settings_for(keyboard_id).sanitize()
        self.mappings = settings.mappings
        self.deadzone_raw = settings.deadzone_raw
        self.max_raw = settings.max_raw
        self.sensitivity = settings.sensitivity
        self.curve = settings.curve
        self.digital_threshold = settings.digital_threshold
        self.keyboard_keys_enabled = settings.keyboard_keys_enabled
        self.gamepad_mapping_override = settings.gamepad_mapping_override
        return self

    def update_settings_for(self, keyboard_id: str) -> KeyboardSettings:
        """Store the current response/policy fields into one keyboard bucket."""

        settings = KeyboardSettings(
            mappings=self._clean_mappings(self.mappings_for(keyboard_id)),
            deadzone_raw=self.deadzone_raw,
            max_raw=self.max_raw,
            sensitivity=self.sensitivity,
            curve=self.curve,
            digital_threshold=self.digital_threshold,
            keyboard_keys_enabled=self.keyboard_keys_enabled,
            gamepad_mapping_override=self.gamepad_mapping_override,
            controller_enabled=self.settings_for(keyboard_id).controller_enabled,
        ).sanitize()
        key = str(keyboard_id or "epomaker_he30")
        self.keyboard_settings[key] = settings
        self.keyboard_mappings[key] = settings.mappings
        if base_keyboard_id(key) == "epomaker_he30":
            self.mappings = settings.mappings
        return settings

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "MapperConfig":
        if not isinstance(value, dict):
            return cls()
        settings = value.get("settings", value)
        config = cls(
            version=value.get("version", 1),
            preferred_keyboard=value.get("preferred_keyboard", settings.get("preferred_keyboard", "auto")),
            known_keyboards=dict(value.get("known_keyboards", {})),
            mappings=dict(value.get("mappings", DEFAULT_MAPPINGS)),
            keyboard_mappings=dict(value.get("keyboard_mappings", {})),
            keyboard_settings=dict(value.get("keyboard_settings", {})),
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
    device_id: str | None = None
    device_name: str | None = None
    layout_id: str | None = None
    digital_output_supported: bool | None = None
