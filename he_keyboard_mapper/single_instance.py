"""Small Windows single-instance guard for the desktop mapper.

The mapper owns HID streams and virtual Xbox controllers. Running two copies at
the same time can make Windows show extra controllers and can leave one process
waiting for Hall reports that another process already consumed. A named mutex is
the simplest app-wide "only one copy" lock on Windows.
"""

from __future__ import annotations

import ctypes
import os
from contextlib import suppress


ERROR_ALREADY_EXISTS = 183
MB_ICONINFORMATION = 0x00000040
MB_OK = 0x00000000
MUTEX_NAME = "Local\\HallAnalogMapperSingleInstance"


class SingleInstance:
    """Hold a named Windows mutex for the lifetime of the process."""

    def __init__(self, name: str = MUTEX_NAME) -> None:
        self.name = name
        self.handle: int | None = None
        self.already_running = False

    def acquire(self) -> bool:
        """Return ``True`` when this process owns the mapper instance lock."""

        if os.name != "nt":
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            return True
        self.handle = int(handle)
        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        return not self.already_running

    def release(self) -> None:
        """Release the mutex when the process exits."""

        if os.name != "nt" or not self.handle:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        with suppress(Exception):
            kernel32.ReleaseMutex(self.handle)
        with suppress(Exception):
            kernel32.CloseHandle(self.handle)
        self.handle = None


def show_already_running_message() -> None:
    """Tell the user why the second app copy is exiting."""

    if os.name != "nt":
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MessageBoxW(
        None,
        (
            "Hall Analog Mapper is already running.\n\n"
            "Open it from the taskbar tray, or exit the existing copy before launching it again."
        ),
        "Hall Analog Mapper",
        MB_OK | MB_ICONINFORMATION,
    )
