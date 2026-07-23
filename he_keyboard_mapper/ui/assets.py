"""Optional application artwork shared by Tk, the tray, and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def asset_path(relative_path: str) -> Path | None:
    """Find a bundled, source-tree, or beside-the-EXE optional asset."""

    relative = Path(relative_path)
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.extend(
            (
                Path(getattr(sys, "_MEIPASS")) / relative,
                Path(sys.executable).resolve().parent / relative,
            )
        )
    else:
        candidates.append(Path(__file__).resolve().parents[2] / relative)
    return next((path for path in candidates if path.is_file()), None)


def load_app_icon(size: int = 64) -> Image.Image | None:
    """Load ``images/icon.png`` without making the app depend on its presence."""

    path = asset_path("images/icon.png")
    if path is None:
        return None
    try:
        with Image.open(path) as source:
            icon = source.convert("RGBA")
            icon.thumbnail((size, size), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.alpha_composite(
                icon,
                ((size - icon.width) // 2, (size - icon.height) // 2),
            )
            return canvas
    except (OSError, ValueError):
        return None
