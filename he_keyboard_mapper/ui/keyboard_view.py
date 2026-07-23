"""Canvas keyboard visualization derived from the HE30 web driver."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from ..constants import ACTION_BY_ID
from ..keyboards import KeyboardLayout
from .theme import BLUE, LINE_STRONG, MINT, MUTED, SURFACE, TEXT


class KeyboardView(tk.Canvas):
    """Render any adapter layout with mapped, selected, and live states."""

    def __init__(
        self,
        parent,
        layout: KeyboardLayout,
        on_select: Callable[[int], None],
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            background=SURFACE,
            highlightthickness=0,
            height=440,
            cursor="hand2",
            **kwargs,
        )
        self.layout = layout
        self.on_select = on_select
        self.selected_key_id = layout.keys[0].key_id
        self.mappings: dict[str, str] = {}
        self.travel: dict[int, float] = {}
        self._boxes: dict[int, tuple[float, float, float, float]] = {}
        self._hovered: int | None = None
        self._redraw_job: str | None = None
        self.bind("<Configure>", self._schedule_redraw)
        self.bind("<Button-1>", self._clicked)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)

    def set_layout(self, layout: KeyboardLayout) -> None:
        self.layout = layout
        if self.selected_key_id not in layout.by_id:
            self.selected_key_id = layout.keys[0].key_id
        self.travel.clear()
        self.redraw()

    def set_mappings(self, mappings: dict[str, str]) -> None:
        self.mappings = mappings
        self.redraw()

    def select(self, key_id: int) -> None:
        if key_id in self.layout.by_id:
            self.selected_key_id = key_id
            self.redraw()

    def set_travel(self, key_id: int, value: float) -> None:
        value = min(1.0, max(0.0, float(value)))
        if value:
            self.travel[key_id] = value
        else:
            self.travel.pop(key_id, None)
        # Hall reports can arrive much faster than a monitor can refresh. One
        # queued redraw keeps the latest state while avoiding dozens of Canvas
        # rebuilds during a single Tk event-loop cycle.
        self._schedule_redraw()

    def _schedule_redraw(self, _event=None) -> None:
        if self._redraw_job is None:
            self._redraw_job = self.after(16, self.redraw)

    @staticmethod
    def _rounded_points(x1: float, y1: float, x2: float, y2: float, radius: float) -> list[float]:
        return [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]

    def _rounded_rectangle(self, box, radius, **options):
        return self.create_polygon(
            self._rounded_points(*box, radius),
            smooth=True,
            splinesteps=18,
            **options,
        )

    def redraw(self) -> None:
        self._redraw_job = None
        self.delete("all")
        self._boxes.clear()
        width = max(320, self.winfo_width())
        padding_x, padding_y = 18, 18
        gap = max(5.0, min(9.0, width / 100))
        row_gap = max(5.0, gap)
        widest_units = max(sum(key.width for key in row) for row in self.layout.rows)
        widest_gaps = max(len(row) - 1 for row in self.layout.rows)
        available = max(280, width - padding_x * 2)
        unit = min(82.0, max(32.0, (available - widest_gaps * gap) / widest_units))
        key_height = min(62.0, max(44.0, unit * 0.74))
        board_width = widest_units * unit + widest_gaps * gap
        board_x = (width - board_width) / 2
        total_height = len(self.layout.rows) * key_height + (len(self.layout.rows) - 1) * row_gap
        self.configure(height=total_height + padding_y * 2 + 16)

        y = padding_y
        for row in self.layout.rows:
            row_width = sum(key.width * unit for key in row) + (len(row) - 1) * gap
            x = board_x
            for key in row:
                key_width = key.width * unit
                box = (x, y, x + key_width, y + key_height)
                self._boxes[key.key_id] = box
                self._draw_key(key, box)
                x += key_width + gap
            y += key_height + row_gap

        self.create_text(
            width / 2,
            total_height + padding_y + 8,
            text=f"{self.layout.name}  ·  mapping label above, physical key below",
            fill=MUTED,
            font=("Segoe UI", 8),
        )

    def _draw_key(self, key, box) -> None:
        x1, y1, x2, y2 = box
        selected = key.key_id == self.selected_key_id
        hovered = key.key_id == self._hovered
        bound = str(key.key_id) in self.mappings
        value = self.travel.get(key.key_id, 0.0)
        outline = MINT if selected or value > 0 else BLUE if bound else LINE_STRONG
        fill = "#11293a" if selected else "#152a3f" if hovered else "#0f2032"
        shadow_box = (x1, y1 + 4, x2, y2 + 4)
        self._rounded_rectangle(shadow_box, 10, fill="#07111f", outline="")
        self._rounded_rectangle(box, 10, fill=fill, outline=outline, width=2 if selected else 1)

        if value > 0:
            fill_top = y2 - max(3, (y2 - y1) * value)
            self.create_rectangle(
                x1 + 2,
                fill_top,
                x2 - 2,
                y2 - 3,
                fill="#1d665a",
                outline="",
            )
            self.create_line(x1 + 4, fill_top, x2 - 4, fill_top, fill=MINT, width=1)

        action_id = self.mappings.get(str(key.key_id), "none")
        action = ACTION_BY_ID.get(action_id, ACTION_BY_ID["none"])
        key_width = x2 - x1
        primary_size = 13 if key_width >= 60 else 10
        physical_text = f"Physical: {key.label}" if key_width >= 110 else key.label
        self.create_text(
            x1 + 10,
            y1 + 19,
            text=action.short,
            anchor="w",
            fill=TEXT,
            font=("Segoe UI Semibold", primary_size),
        )
        self.create_text(
            x1 + 10,
            y2 - 13,
            text=physical_text,
            anchor="w",
            fill=MUTED,
            font=("Segoe UI Semibold", 8 if key_width >= 60 else 7),
        )
        if bound:
            self.create_oval(x1 + 6, y1 + 6, x1 + 11, y1 + 11, fill=MINT, outline="")

    def _key_at(self, x: float, y: float) -> int | None:
        for key_id, (x1, y1, x2, y2) in self._boxes.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return key_id
        return None

    def _clicked(self, event) -> None:
        key_id = self._key_at(event.x, event.y)
        if key_id is not None:
            self.select(key_id)
            self.on_select(key_id)

    def _motion(self, event) -> None:
        hovered = self._key_at(event.x, event.y)
        if hovered != self._hovered:
            self._hovered = hovered
            self.redraw()

    def _leave(self, _event=None) -> None:
        if self._hovered is not None:
            self._hovered = None
            self.redraw()
