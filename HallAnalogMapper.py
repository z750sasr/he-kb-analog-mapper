"""Hall Analog Mapper executable entry point.

Run normally for the tray application or pass ``--headless`` for a console-only
background mapper useful for diagnostics and automated startup scripts.
"""

from __future__ import annotations

import queue
import sys
import time
from contextlib import suppress

from he_keyboard_mapper.config import load_config
from he_keyboard_mapper.service import MapperService


def enable_windows_dpi_awareness() -> None:
    """Ask Windows for crisp, correctly sized drawing on scaled displays.

    Tk still paints its widgets with the CPU/GDI. DPI awareness prevents
    Windows from bitmap-stretching the completed window, which removes blur
    and a common source of trails/artifacts on 125% and 150% displays.
    """

    if sys.platform != "win32":
        return
    import ctypes

    with suppress(Exception):
        # PROCESS_SYSTEM_DPI_AWARE is supported from Windows 8.1 onward and
        # lets Tk read the monitor's real pixel density during construction.
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    with suppress(Exception):
        # Fallback for older Windows installations.
        ctypes.windll.user32.SetProcessDPIAware()


def run_headless() -> None:
    service = MapperService(load_config())
    service.start()
    print("Hall Analog Mapper is running. Press Ctrl+C to exit.")
    try:
        while True:
            try:
                event = service.events.get(timeout=0.5)
                if event.kind != "travel":
                    print(event.message)
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        service.stop()
        time.sleep(0.1)


if __name__ == "__main__":
    if "--headless" in sys.argv or "--noui" in sys.argv:
        run_headless()
    else:
        enable_windows_dpi_awareness()
        from he_keyboard_mapper.ui import run_app

        run_app()
