"""Windows notification-area integration kept separate from the main window."""

from __future__ import annotations

import threading
from typing import Any


def tray_image(connected: bool = False) -> Any:
    """Draw the app icon in memory so themes do not depend on bitmap assets."""

    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64), (6, 13, 24, 255))
    draw = ImageDraw.Draw(image)
    accent = (102, 247, 194, 255) if connected else (91, 140, 255, 255)
    draw.rounded_rectangle((5, 10, 59, 54), radius=10, fill=(12, 23, 38, 255), outline=accent, width=4)
    for row in range(3):
        for column in range(5):
            left = 11 + column * 9
            top = 17 + row * 9
            draw.rounded_rectangle((left, top, left + 6, top + 6), radius=1, fill=accent)
    draw.rounded_rectangle((20, 44, 45, 49), radius=2, fill=accent)
    return image


class TrayController:
    """Forward pystray callbacks onto Tk's single UI thread."""

    def __init__(self, app) -> None:
        self.app = app
        self.icon: Any | None = None
        self.available = False

    def start(self) -> None:
        try:
            import pystray

            menu = pystray.Menu(
                pystray.MenuItem("Open Hall Analog Mapper", lambda *_: self._tk(self.app.show_window), default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Start mapping", lambda *_: self._tk(self.app.start_mapping)),
                pystray.MenuItem("Stop mapping", lambda *_: self._tk(self.app.stop_mapping)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", lambda *_: self._tk(self.app.exit_application)),
            )
            self.icon = pystray.Icon("HallAnalogMapper", tray_image(), "Hall Analog Mapper", menu)
            threading.Thread(target=self.icon.run, name="Hall mapper tray", daemon=True).start()
            self.available = True
        except Exception as error:
            self.available = False
            self.app.set_status(f"Tray unavailable: {error}", error=True)

    def _tk(self, callback) -> None:
        self.app.after(0, callback)

    def update(self, connected: bool, title: str) -> None:
        if self.icon is not None:
            self.icon.icon = tray_image(connected)
            self.icon.title = title

    def stop(self) -> None:
        if self.icon is not None:
            self.icon.stop()
            self.icon = None
