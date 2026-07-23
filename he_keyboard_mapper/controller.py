"""Analog response processing and direct ViGEm Xbox-controller output.

The signal-processing classes are platform independent and easy to unit test.
Only :class:`VirtualXboxController` touches the Windows ViGEm client DLL.
Keeping that boundary narrow also prevents package installers from modifying a
machine while the application itself is being built.
"""

from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .constants import DIGITAL_BUTTON_ENUMS
from .models import MapperConfig


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Limit a numeric value to an inclusive range."""

    return min(maximum, max(minimum, float(value)))


class SignalProcessor:
    """Apply response shaping after an adapter normalizes its Hall value."""

    @staticmethod
    def process(raw: int, config: MapperConfig) -> float:
        """Compatibility raw conversion used by older callers and core tests."""

        if raw <= config.deadzone_raw:
            return 0.0
        span = max(1, config.max_raw - config.deadzone_raw)
        value = clamp((raw - config.deadzone_raw) / span, 0.0, 1.0)
        return SignalProcessor.process_normalized(value, config)

    @staticmethod
    def process_normalized(value: float, config: MapperConfig) -> float:
        """Shape a keyboard-specific linear value without assuming raw units."""

        value = clamp(value, 0.0, 1.0)
        if config.curve == "gentle":
            value = value * value
        elif config.curve == "s_curve":
            value = 3 * value * value - 2 * value * value * value
        elif config.curve == "fast":
            value = 1 - (1 - value) * (1 - value)
        return clamp(value * config.sensitivity, 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class ControllerState:
    """Complete desired XInput state after aggregating all active keys."""

    left_x: float = 0.0
    left_y: float = 0.0
    right_x: float = 0.0
    right_y: float = 0.0
    left_trigger: float = 0.0
    right_trigger: float = 0.0
    buttons: frozenset[str] = field(default_factory=frozenset)


class ControllerOutput(Protocol):
    """Small interface used by the background service and test doubles."""

    def apply(self, state: ControllerState) -> None: ...
    def reset(self) -> None: ...
    def close(self) -> None: ...


class MappingEngine:
    """Aggregate physical-key pressures into axes, triggers, and buttons."""

    def __init__(self, config: MapperConfig, keyboard_id: str = "epomaker_he30") -> None:
        self.config = config
        self.keyboard_id = keyboard_id
        self.values: dict[int, float] = {}

    def update_config(self, config: MapperConfig) -> None:
        self.config = config

    def update_keyboard(self, keyboard_id: str) -> None:
        if keyboard_id != self.keyboard_id:
            self.values.clear()
            self.keyboard_id = keyboard_id

    def update_key(self, physical_index: int, raw_travel: int) -> tuple[float, ControllerState]:
        value = SignalProcessor.process(raw_travel, self.config)
        return self._store_value(physical_index, value)

    def update_value(self, physical_index: int, normalized_travel: float) -> tuple[float, ControllerState]:
        value = SignalProcessor.process_normalized(normalized_travel, self.config)
        return self._store_value(physical_index, value)

    def _store_value(self, physical_index: int, value: float) -> tuple[float, ControllerState]:
        if value > 0:
            self.values[physical_index] = value
        else:
            self.values.pop(physical_index, None)
        return value, self.state()

    def clear(self) -> ControllerState:
        self.values.clear()
        return ControllerState()

    def state(self) -> ControllerState:
        strengths: dict[str, float] = {}
        mappings = self.config.mappings_for(self.keyboard_id)
        for physical_index, value in self.values.items():
            action = mappings.get(str(physical_index), "none")
            strengths[action] = max(strengths.get(action, 0.0), value)

        def direction(positive: str, negative: str) -> float:
            return clamp(strengths.get(positive, 0.0) - strengths.get(negative, 0.0), -1.0, 1.0)

        buttons = frozenset(
            action
            for action in DIGITAL_BUTTON_ENUMS
            if strengths.get(action, 0.0) >= self.config.digital_threshold
        )
        return ControllerState(
            left_x=direction("left_stick_right", "left_stick_left"),
            left_y=direction("left_stick_up", "left_stick_down"),
            right_x=direction("right_stick_right", "right_stick_left"),
            right_y=direction("right_stick_up", "right_stick_down"),
            left_trigger=strengths.get("left_trigger", 0.0),
            right_trigger=strengths.get("right_trigger", 0.0),
            buttons=buttons,
        )


# Values from the public XInput XUSB_BUTTON bit mask. Constants stay here so
# the rest of the application never needs to import a Windows-only package.
_XUSB_BUTTON_BITS = {
    "XUSB_GAMEPAD_DPAD_UP": 0x0001,
    "XUSB_GAMEPAD_DPAD_DOWN": 0x0002,
    "XUSB_GAMEPAD_DPAD_LEFT": 0x0004,
    "XUSB_GAMEPAD_DPAD_RIGHT": 0x0008,
    "XUSB_GAMEPAD_START": 0x0010,
    "XUSB_GAMEPAD_BACK": 0x0020,
    "XUSB_GAMEPAD_LEFT_THUMB": 0x0040,
    "XUSB_GAMEPAD_RIGHT_THUMB": 0x0080,
    "XUSB_GAMEPAD_LEFT_SHOULDER": 0x0100,
    "XUSB_GAMEPAD_RIGHT_SHOULDER": 0x0200,
    "XUSB_GAMEPAD_GUIDE": 0x0400,
    "XUSB_GAMEPAD_A": 0x1000,
    "XUSB_GAMEPAD_B": 0x2000,
    "XUSB_GAMEPAD_X": 0x4000,
    "XUSB_GAMEPAD_Y": 0x8000,
}

_VIGEM_ERROR_NONE = 0x20000000


class _XUSBReport(ctypes.Structure):
    """Binary report layout expected by ``vigem_target_x360_update``."""

    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


def _client_dll_path() -> Path:
    """Find the bundled client DLL in source and PyInstaller executions."""

    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "ViGEmClient.dll"
    return Path(__file__).resolve().parents[1] / "vendor" / "ViGEmClient.dll"


class _ViGEmXboxDevice:
    """Minimal ctypes binding for one virtual Xbox 360 controller."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("Virtual controller output is supported on Windows only.")
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            raise RuntimeError("This build includes the 64-bit ViGEm client and requires 64-bit Windows/Python.")

        dll_path = _client_dll_path()
        if not dll_path.is_file():
            raise RuntimeError(f"Missing virtual-controller client: {dll_path}")
        try:
            self.dll = ctypes.CDLL(str(dll_path))
        except OSError as error:
            raise RuntimeError(f"Could not load {dll_path.name}: {error}") from error

        self._configure_functions()
        self.client: int | None = None
        self.target: int | None = None
        try:
            self.client = self.dll.vigem_alloc()
            if not self.client:
                raise RuntimeError("ViGEm could not allocate a client connection.")
            self._check(self.dll.vigem_connect(self.client), "connect to ViGEmBus")
            self.target = self.dll.vigem_target_x360_alloc()
            if not self.target:
                raise RuntimeError("ViGEm could not allocate an Xbox controller.")
            self._check(self.dll.vigem_target_add(self.client, self.target), "attach the Xbox controller")
        except Exception:
            self.close()
            raise

    def _configure_functions(self) -> None:
        pointer = ctypes.c_void_p
        self.dll.vigem_alloc.argtypes = ()
        self.dll.vigem_alloc.restype = pointer
        self.dll.vigem_free.argtypes = (pointer,)
        self.dll.vigem_free.restype = None
        self.dll.vigem_connect.argtypes = (pointer,)
        self.dll.vigem_connect.restype = ctypes.c_uint
        self.dll.vigem_disconnect.argtypes = (pointer,)
        self.dll.vigem_disconnect.restype = None
        self.dll.vigem_target_x360_alloc.argtypes = ()
        self.dll.vigem_target_x360_alloc.restype = pointer
        self.dll.vigem_target_add.argtypes = (pointer, pointer)
        self.dll.vigem_target_add.restype = ctypes.c_uint
        self.dll.vigem_target_remove.argtypes = (pointer, pointer)
        self.dll.vigem_target_remove.restype = ctypes.c_uint
        self.dll.vigem_target_free.argtypes = (pointer,)
        self.dll.vigem_target_free.restype = None
        self.dll.vigem_target_x360_update.argtypes = (pointer, pointer, _XUSBReport)
        self.dll.vigem_target_x360_update.restype = ctypes.c_uint

    @staticmethod
    def _check(result: int, operation: str) -> None:
        if result != _VIGEM_ERROR_NONE:
            if result == 0xE0000001:
                raise RuntimeError("ViGEmBus was not found. Install its Windows driver, then restart this app.")
            raise RuntimeError(f"Could not {operation} (ViGEm error 0x{result:08X}).")

    def update(self, report: _XUSBReport) -> None:
        if not self.client or not self.target:
            raise RuntimeError("The virtual Xbox controller is closed.")
        self._check(
            self.dll.vigem_target_x360_update(self.client, self.target, report),
            "send the Xbox controller report",
        )

    def close(self) -> None:
        """Detach and free native objects; safe to call more than once."""

        target, client = self.target, self.client
        self.target = None
        self.client = None
        if target:
            if client:
                try:
                    self.dll.vigem_target_remove(client, target)
                except Exception:
                    pass
            self.dll.vigem_target_free(target)
        if client:
            self.dll.vigem_disconnect(client)
            self.dll.vigem_free(client)


class VirtualXboxController:
    """Translate application states into reports for the direct ViGEm binding."""

    def __init__(self) -> None:
        try:
            self.device = _ViGEmXboxDevice()
        except RuntimeError:
            raise
        except Exception as error:  # pragma: no cover - hardware/driver dependent.
            raise RuntimeError(f"Could not create the virtual Xbox controller: {error}") from error
        self._state = ControllerState()
        self.device.update(self._report(self._state))

    @staticmethod
    def _report(state: ControllerState) -> _XUSBReport:
        buttons = 0
        for action in state.buttons:
            enum_name = DIGITAL_BUTTON_ENUMS.get(action)
            if enum_name:
                buttons |= _XUSB_BUTTON_BITS[enum_name]
        return _XUSBReport(
            wButtons=buttons,
            bLeftTrigger=round(clamp(state.left_trigger, 0.0, 1.0) * 255),
            bRightTrigger=round(clamp(state.right_trigger, 0.0, 1.0) * 255),
            sThumbLX=round(clamp(state.left_x, -1.0, 1.0) * 32767),
            sThumbLY=round(clamp(state.left_y, -1.0, 1.0) * 32767),
            sThumbRX=round(clamp(state.right_x, -1.0, 1.0) * 32767),
            sThumbRY=round(clamp(state.right_y, -1.0, 1.0) * 32767),
        )

    def apply(self, state: ControllerState) -> None:
        if state == self._state:
            return
        self.device.update(self._report(state))
        self._state = state

    def reset(self) -> None:
        self._state = ControllerState()
        self.device.update(self._report(self._state))

    def close(self) -> None:
        self.device.close()

    def __del__(self) -> None:  # pragma: no cover - interpreter shutdown path.
        try:
            self.close()
        except Exception:
            pass
