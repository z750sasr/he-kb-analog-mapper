"""Hall Analog Mapper executable entry point.

Run normally for the tray application or pass ``--headless`` for a console-only
background mapper useful for diagnostics and automated startup scripts.
"""

from __future__ import annotations

import queue
import sys
import time

from he30_mapper.config import load_config
from he30_mapper.service import MapperService


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
        from he30_mapper.ui import run_app

        run_app()
