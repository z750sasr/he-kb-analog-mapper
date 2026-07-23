"""Windows global-hotkey parsing and registration.

The operating-system ``RegisterHotKey`` API is intentionally used instead of
installing a low-level keyboard hook. It works while the window is hidden,
does not require administrator access, and never records ordinary typing.
"""

from __future__ import annotations

import ctypes
import os
import queue
import threading
from ctypes import wintypes
from dataclasses import dataclass


TOGGLE_MAPPING_ACTION = "toggle_mapping"
EXIT_APPLICATION_ACTION = "exit_application"

_MODIFIER_BITS = {
    "Ctrl": 0x0002,
    "Alt": 0x0001,
    "Shift": 0x0004,
    "Win": 0x0008,
}
_MODIFIER_ORDER = tuple(_MODIFIER_BITS)
_MODIFIER_ALIASES = {
    "control": "Ctrl",
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "windows": "Win",
    "super": "Win",
}
_NAMED_KEYS = {
    "Backspace": 0x08,
    "Tab": 0x09,
    "Enter": 0x0D,
    "Pause": 0x13,
    "CapsLock": 0x14,
    "Escape": 0x1B,
    "Space": 0x20,
    "PageUp": 0x21,
    "PageDown": 0x22,
    "End": 0x23,
    "Home": 0x24,
    "Left": 0x25,
    "Up": 0x26,
    "Right": 0x27,
    "Down": 0x28,
    "PrintScreen": 0x2C,
    "Insert": 0x2D,
    "Delete": 0x2E,
    "NumLock": 0x90,
    "ScrollLock": 0x91,
    ";": 0xBA,
    "=": 0xBB,
    ",": 0xBC,
    "-": 0xBD,
    ".": 0xBE,
    "/": 0xBF,
    "`": 0xC0,
    "[": 0xDB,
    "\\": 0xDC,
    "]": 0xDD,
    "'": 0xDE,
}
_KEY_ALIASES = {
    "return": "Enter",
    "backspace": "Backspace",
    "escape": "Escape",
    "esc": "Escape",
    "space": "Space",
    "prior": "PageUp",
    "pageup": "PageUp",
    "next": "PageDown",
    "pagedown": "PageDown",
    "caps_lock": "CapsLock",
    "capslock": "CapsLock",
    "print": "PrintScreen",
    "printscreen": "PrintScreen",
    "num_lock": "NumLock",
    "numlock": "NumLock",
    "scroll_lock": "ScrollLock",
    "scrolllock": "ScrollLock",
    "semicolon": ";",
    "equal": "=",
    "comma": ",",
    "minus": "-",
    "period": ".",
    "slash": "/",
    "grave": "`",
    "bracketleft": "[",
    "backslash": "\\",
    "bracketright": "]",
    "apostrophe": "'",
}
_MODIFIER_KEYSYMS = {
    "Alt_L",
    "Alt_R",
    "Control_L",
    "Control_R",
    "Shift_L",
    "Shift_R",
    "Super_L",
    "Super_R",
    "Win_L",
    "Win_R",
}


def _canonical_key(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Choose a non-modifier key.")
    alias = _KEY_ALIASES.get(stripped.lower())
    if alias:
        return alias
    if len(stripped) == 1 and stripped.isalnum():
        return stripped.upper()
    if stripped.upper().startswith("F") and stripped[1:].isdigit():
        number = int(stripped[1:])
        if 1 <= number <= 24:
            return f"F{number}"
    for name in _NAMED_KEYS:
        if stripped.lower() == name.lower():
            return name
    raise ValueError(f"Unsupported hotkey key: {value}")


def _virtual_key(key: str) -> int:
    if len(key) == 1 and key.isalnum():
        return ord(key)
    if key.startswith("F") and key[1:].isdigit():
        return 0x70 + int(key[1:]) - 1
    return _NAMED_KEYS[key]


@dataclass(frozen=True, slots=True)
class HotkeyBinding:
    """Canonical display text plus values consumed by ``RegisterHotKey``."""

    text: str
    modifiers: int
    virtual_key: int

    @classmethod
    def parse(cls, value: str) -> "HotkeyBinding":
        parts = [part.strip() for part in str(value).split("+") if part.strip()]
        modifiers: set[str] = set()
        keys: list[str] = []
        for part in parts:
            modifier = _MODIFIER_ALIASES.get(part.lower())
            if modifier:
                modifiers.add(modifier)
            else:
                keys.append(part)
        if len(keys) != 1:
            raise ValueError("A hotkey needs exactly one non-modifier key.")
        key = _canonical_key(keys[0])
        ordered = [name for name in _MODIFIER_ORDER if name in modifiers]
        text = "+".join([*ordered, key])
        bits = sum(_MODIFIER_BITS[name] for name in ordered)
        return cls(text, bits, _virtual_key(key))


def normalize_hotkey(value: object) -> str:
    """Return a canonical hotkey, or an empty string for blank/invalid input."""

    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return HotkeyBinding.parse(text).text
    except ValueError:
        return ""


def hotkey_from_tk_event(keysym: str, state: int) -> str:
    """Translate one Tk keypress into the same canonical format as saved JSON."""

    if keysym in _MODIFIER_KEYSYMS:
        return ""
    key = _canonical_key(keysym)
    modifiers: list[str] = []
    if state & 0x0004:
        modifiers.append("Ctrl")
    if state & 0x0008 or state & 0x20000:
        modifiers.append("Alt")
    if state & 0x0001:
        modifiers.append("Shift")
    return HotkeyBinding.parse("+".join([*modifiers, key])).text


class GlobalHotkeyManager:
    """Register app actions on a small dedicated Windows message-pump thread."""

    _WM_HOTKEY = 0x0312
    _WM_QUIT = 0x0012
    _MOD_NOREPEAT = 0x4000

    def __init__(self, actions: queue.SimpleQueue[str]) -> None:
        self.actions = actions
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._bindings: dict[str, HotkeyBinding] = {}
        self._errors: dict[str, str] = {}

    def configure(self, values: dict[str, str]) -> dict[str, str]:
        """Replace every registration and return per-action error messages."""

        self.stop()
        self._errors = {}
        self._bindings = {}
        seen: set[str] = set()
        for action, value in values.items():
            if not str(value or "").strip():
                continue
            try:
                binding = HotkeyBinding.parse(value)
            except ValueError as error:
                self._errors[action] = str(error)
                continue
            if binding.text in seen:
                self._errors[action] = "This combination is already assigned."
                continue
            seen.add(binding.text)
            self._bindings[action] = binding

        if not self._bindings or os.name != "nt":
            if self._bindings and os.name != "nt":
                for action in self._bindings:
                    self._errors[action] = "Global hotkeys are available on Windows only."
            return dict(self._errors)

        self._ready.clear()
        self._thread = threading.Thread(
            target=self._message_loop,
            name="Hall mapper global hotkeys",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(1.0)
        return dict(self._errors)

    def stop(self) -> None:
        thread = self._thread
        if thread and thread.is_alive() and self._thread_id:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW(self._thread_id, self._WM_QUIT, 0, 0)
            thread.join(1.0)
        self._thread = None
        self._thread_id = 0
        self._ready.clear()

    def _message_loop(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.UnregisterHotKey.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = (
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        )
        user32.GetMessageW.restype = wintypes.BOOL

        self._thread_id = int(kernel32.GetCurrentThreadId())
        message = wintypes.MSG()
        # Force creation of this thread's message queue before another thread
        # can ask it to stop with PostThreadMessage.
        user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
        actions_by_id: dict[int, str] = {}
        try:
            for hotkey_id, (action, binding) in enumerate(self._bindings.items(), start=1):
                registered = user32.RegisterHotKey(
                    None,
                    hotkey_id,
                    binding.modifiers | self._MOD_NOREPEAT,
                    binding.virtual_key,
                )
                if registered:
                    actions_by_id[hotkey_id] = action
                else:
                    code = ctypes.get_last_error()
                    self._errors[action] = (
                        "Windows could not register this combination"
                        + (f" (error {code})." if code else ".")
                    )
            self._ready.set()
            while actions_by_id:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                if message.message == self._WM_HOTKEY:
                    action = actions_by_id.get(int(message.wParam))
                    if action:
                        self.actions.put(action)
        finally:
            for hotkey_id in actions_by_id:
                user32.UnregisterHotKey(None, hotkey_id)
            self._ready.set()

