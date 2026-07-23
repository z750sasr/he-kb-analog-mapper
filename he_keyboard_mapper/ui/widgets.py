"""Small reusable controls with no keyboard- or controller-specific logic."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .theme import LINE, MINT, MUTED, SURFACE, SURFACE_2


class ToggleSwitch(tk.Canvas):
    """Accessible two-state switch backed by a normal ``BooleanVar``."""

    def __init__(
        self,
        parent,
        variable: tk.BooleanVar,
        command: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            width=52,
            height=28,
            background=SURFACE,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
            **kwargs,
        )
        self.variable = variable
        self.command = command
        self.enabled = True
        self.bind("<Button-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.variable.trace_add("write", lambda *_: self.redraw())
        self.redraw()

    def _toggle(self, _event=None) -> str:
        if self.enabled:
            self.variable.set(not self.variable.get())
            if self.command:
                self.command()
        return "break"

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        self.configure(cursor="hand2" if self.enabled else "arrow")
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        active = bool(self.variable.get())
        track = MINT if active else SURFACE_2
        outline = MINT if active else LINE
        if not self.enabled:
            track, outline = SURFACE_2, LINE
        self.create_oval(2, 2, 26, 26, fill=track, outline=outline)
        self.create_oval(26, 2, 50, 26, fill=track, outline=outline)
        self.create_rectangle(14, 2, 38, 26, fill=track, outline=track)
        center = 38 if active else 14
        knob = "#07130f" if active else "#526275"
        self.create_oval(center - 9, 5, center + 9, 23, fill=knob, outline="")
        if active:
            self.create_text(13, 14, text="✓", fill="#07130f", font=("Segoe UI Semibold", 9))
        else:
            self.create_text(39, 14, text="×", fill=MUTED, font=("Segoe UI Semibold", 10))


class ToggleSetting(ttk.Frame):
    """Title, explanatory text, capability note, and switch in one row."""

    def __init__(
        self,
        parent,
        title: str,
        description: str,
        variable: tk.BooleanVar,
        command: Callable[[], None],
    ) -> None:
        super().__init__(parent, style="Surface.TFrame")
        self.columnconfigure(0, weight=1)
        text = ttk.Frame(self, style="Surface.TFrame")
        text.grid(row=0, column=0, sticky="ew", padx=(0, 18))
        ttk.Label(text, text=title, style="SurfaceHeading.TLabel").pack(anchor="w")
        ttk.Label(
            text,
            text=description,
            style="SurfaceMuted.TLabel",
            wraplength=300,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        self.note_var = tk.StringVar()
        self.note = ttk.Label(
            text,
            textvariable=self.note_var,
            style="Support.TLabel",
            wraplength=300,
            justify="left",
        )
        self.switch = ToggleSwitch(self, variable=variable, command=command)
        self.switch.grid(row=0, column=1, sticky="ne")

    def set_note(self, text: str, error: bool = False) -> None:
        self.note_var.set(text)
        self.note.configure(style="SupportError.TLabel" if error else "Support.TLabel")
        if text:
            self.note.pack(anchor="w", pady=(7, 0))
        else:
            self.note.pack_forget()


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable ttk frame for smaller laptop displays."""

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, background=SURFACE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = ttk.Frame(self.canvas, style="Surface.TFrame")
        self._window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.content.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(self._window, width=event.width),
        )
        self.canvas.bind("<Enter>", lambda _event: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda _event: self._unbind_wheel())
        # The embedded frame covers almost the entire canvas, so bind it too.
        # Without these bindings the wheel can appear to work only in the thin
        # empty border around the settings content.
        self.content.bind("<Enter>", lambda _event: self._bind_wheel(), add="+")
        self.content.bind("<Leave>", lambda _event: self._unbind_wheel(), add="+")

    def _bind_wheel(self) -> None:
        self.canvas.bind_all(
            "<MouseWheel>",
            lambda event: self.canvas.yview_scroll(-int(event.delta / 120), "units"),
        )

    def _unbind_wheel(self) -> None:
        self.canvas.unbind_all("<MouseWheel>")
