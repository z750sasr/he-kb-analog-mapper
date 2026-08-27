"""Hall Analog Mapper executable entry point.

Run normally for the tray application or pass ``--headless`` for a console-only
background mapper useful for diagnostics and automated startup scripts.
"""

from __future__ import annotations

import queue
import sys
import time
from contextlib import suppress
from datetime import datetime

from he_keyboard_mapper.config import config_directory, load_config
from he_keyboard_mapper.keyboards.base import device_selection_id
from he_keyboard_mapper.keyboards.he30.protocol import (
    HE30Protocol,
    decode_profile_change_report,
    decode_telemetry_report,
)
from he_keyboard_mapper.service import MapperService
from he_keyboard_mapper.single_instance import SingleInstance, show_already_running_message


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


def diagnose_he30(seconds: float = 15.0) -> None:
    """Print raw HE30 live-report evidence for support/debugging."""

    log_dir = config_directory()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"he30-diagnostic-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    log_file = log_path.open("w", encoding="utf-8")

    def log(*values: object) -> None:
        text = " ".join(str(value) for value in values)
        print(text)
        log_file.write(text + "\n")
        log_file.flush()

    protocol = HE30Protocol(timeout_ms=700)
    try:
        log("HE30 diagnostic log:", log_path)
        log("HE30 candidates:")
        for info in protocol.enumerate_candidates():
            details = dict(info)
            log(
                " ",
                device_selection_id("epomaker_he30", details),
                "interface",
                details.get("interface_number"),
                "usage",
                details.get("usage_page"),
                details.get("usage"),
            )
        info = protocol.connect()
        log("Connected:", device_selection_id("epomaker_he30", info))
        protocol.prepare_stream()
        log(f"Prepared profile {protocol.active_profile}, layer {protocol.active_layer}.")
        log(f"Press HE30 keys for {seconds:.0f} seconds...")
        deadline = time.monotonic() + seconds
        reports = telemetry = profiles = unresolved = 0
        while time.monotonic() < deadline:
            report = protocol._read(200)
            if not report:
                continue
            reports += 1
            travel = decode_telemetry_report(report)
            if travel:
                telemetry += 1
                key_id = protocol.resolve_physical(travel)
                unresolved += int(key_id is None)
                log("HE30 travel", "signal", travel.signal, "raw", travel.raw_travel, "status", travel.status, "key", key_id)
                continue
            profile = decode_profile_change_report(report)
            if profile:
                profiles += 1
                log("HE30 profile", profile)
                continue
            log("Other report:", tuple(report[:16]))
        log(
            "Summary:",
            f"reports={reports}",
            f"telemetry={telemetry}",
            f"profile={profiles}",
            f"unresolved={unresolved}",
        )
    finally:
        protocol.close()
        log_file.close()
        if sys.platform == "win32":
            from he_keyboard_mapper.single_instance import MB_ICONINFORMATION, MB_OK

            with suppress(Exception):
                user32 = __import__("ctypes").WinDLL("user32", use_last_error=True)
                user32.MessageBoxW(None, f"HE30 diagnostic saved to:\n{log_path}", "Hall Analog Mapper", MB_OK | MB_ICONINFORMATION)


if __name__ == "__main__":
    instance = SingleInstance()
    if not instance.acquire():
        show_already_running_message()
        sys.exit(0)
    try:
        if "--diagnose-he30" in sys.argv:
            diagnose_he30()
        elif "--headless" in sys.argv or "--noui" in sys.argv:
            run_headless()
        else:
            enable_windows_dpi_awareness()
            from he_keyboard_mapper.ui import run_app

            run_app()
    finally:
        instance.release()
