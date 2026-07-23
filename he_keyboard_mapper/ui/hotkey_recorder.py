"""Small UI control that records a key or key combination from Tk events."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ..hotkeys import hotkey_from_tk_event


class HotkeyRecorder(ttk.Frame):
    """Read-only value, Record/Clear buttons, and registration-status note."""

    def __init__(
        self,
        parent,
        title: str,
        description: str,
        variable: tk.StringVar,
        on_change: Callable[[str], None],
        on_recording_changed: Callable[[bool], None],
    ) -> None:
        super().__init__(parent, style="Surface.TFrame")
        self.variable = variable
        self.on_change = on_change
        self.on_recording_changed = on_recording_changed
        self._binding_id: str | None = None
        self._previous_value = ""

        ttk.Label(self, text=title, style="SurfaceHeading.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text=description,
            style="SurfaceMuted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))
        row = ttk.Frame(self, style="Surface.TFrame")
        row.pack(fill="x")
        ttk.Entry(row, textvariable=variable, state="readonly").pack(
            side="left",
            fill="x",
            expand=True,
        )
        self.record_button = ttk.Button(row, text="Record", command=self.start_recording)
        self.record_button.pack(side="left", padx=(8, 4))
        # A compact symbol keeps the row usable in the half-width settings tab.
        ttk.Button(row, text="×", width=3, command=self.clear).pack(side="left")
        self.note_var = tk.StringVar()
        self.note = ttk.Label(
            self,
            textvariable=self.note_var,
            style="Support.TLabel",
            wraplength=320,
            justify="left",
        )
        self.note.pack(anchor="w", pady=(7, 0))

    def start_recording(self) -> None:
        if self._binding_id:
            return
        self._previous_value = self.variable.get()
        self.variable.set("Press a combination…")
        self.record_button.configure(text="Listening…", state="disabled")
        self.on_recording_changed(True)
        top = self.winfo_toplevel()
        self._binding_id = top.bind("<KeyPress>", self._key_pressed, add="+")
        top.focus_force()

    def _key_pressed(self, event) -> str:
        if event.keysym == "Escape":
            self._finish(self._previous_value, changed=False)
            return "break"
        try:
            value = hotkey_from_tk_event(event.keysym, int(event.state))
        except ValueError as error:
            self.set_note(str(error), error=True)
            return "break"
        if value:
            self._finish(value, changed=True)
        return "break"

    def _finish(self, value: str, changed: bool) -> None:
        top = self.winfo_toplevel()
        if self._binding_id:
            top.unbind("<KeyPress>", self._binding_id)
            self._binding_id = None
        self.record_button.configure(text="Record", state="normal")
        self.variable.set(value)
        if changed:
            self.on_change(value)
        self.on_recording_changed(False)

    def clear(self) -> None:
        if self._binding_id:
            self._finish("", changed=True)
            return
        self.variable.set("")
        self.on_change("")

    def set_note(self, text: str, error: bool = False) -> None:
        self.note_var.set(text)
        self.note.configure(style="SupportError.TLabel" if error else "Support.TLabel")
