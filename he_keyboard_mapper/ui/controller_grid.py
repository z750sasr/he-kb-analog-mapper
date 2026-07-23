"""Reusable responsive controller-output picker backed by the icon pack."""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageTk

from ..constants import ACTION_BY_ID, CONTROLLER_ACTIONS


def _asset_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "controller_icons"
    return Path(__file__).resolve().parents[2] / "controller_icons"


class ControllerActionGrid(ttk.Frame):
    """Keyboard-accessible icon buttons with one selected controller action."""

    def __init__(
        self,
        parent,
        on_select: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(parent, style="Surface.TFrame", **kwargs)
        self.on_select = on_select
        self.selected_action = "none"
        self.buttons: dict[str, ttk.Button] = {}
        self.images: dict[str, ImageTk.PhotoImage] = {}
        # Reserve icon space for Unassigned with a fully transparent image.
        # The button stays aligned without displaying a misleading logo.
        self.blank_image = tk.PhotoImage(width=24, height=24)
        # Six columns turn 26 actions into five compact rows, keeping the
        # entire picker—including the final text-only Off tile—on one screen.
        self.columns = 6
        for column in range(self.columns):
            self.columnconfigure(column, weight=1, uniform="controller-actions")
        self._build()

    def _build(self) -> None:
        asset_dir = _asset_directory()
        for index, action in enumerate(CONTROLLER_ACTIONS):
            image = None
            path = asset_dir / action.icon if action.icon else None
            if path and path.is_file():
                with Image.open(path) as source:
                    # Resizing happens once during window construction. Compact
                    # icons let every action remain visible without scrolling.
                    icon = source.convert("RGBA").resize((24, 24), Image.Resampling.LANCZOS)
                    image = ImageTk.PhotoImage(icon)
                self.images[action.value] = image
            if image is None:
                image = self.blank_image
            button = ttk.Button(
                self,
                text=action.short,
                image=image,
                compound="top",
                style="ControllerIcon.TButton",
                command=lambda value=action.value: self.select(value, notify=True),
                takefocus=True,
            )
            button.grid(
                row=index // self.columns,
                column=index % self.columns,
                sticky="nsew",
                padx=2,
                pady=2,
            )
            self.buttons[action.value] = button

    def select(self, action_id: str, notify: bool = False) -> None:
        selected = action_id if action_id in ACTION_BY_ID else "none"
        self.selected_action = selected
        for value, button in self.buttons.items():
            button.configure(
                style="Selected.ControllerIcon.TButton"
                if value == selected
                else "ControllerIcon.TButton"
            )
        if notify:
            self.on_select(selected)
