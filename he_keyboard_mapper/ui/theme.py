"""One edit point for the application's colors, typography, and ttk styles."""

from __future__ import annotations

from tkinter import ttk


# Palette follows the HE30 web driver so desktop and browser tools feel related.
BG = "#060d18"
SURFACE = "#0c1726"
SURFACE_2 = "#111f31"
SURFACE_3 = "#17283c"
LINE = "#20364d"
LINE_STRONG = "#31506d"
TEXT = "#eef7ff"
MUTED = "#8ba1b6"
MINT = "#66f7c2"
MINT_DARK = "#103d35"
BLUE = "#5b8cff"
AMBER = "#ffc66d"
RED = "#ff7e8a"

FONT = "Segoe UI"
FONT_SEMIBOLD = "Segoe UI Semibold"


def configure_styles(root) -> None:
    """Install every ttk style used by the app.

    Designers can restyle the whole desktop application from this file without
    touching device, mapping, or event-handling code.
    """

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure("TFrame", background=BG)
    style.configure("Surface.TFrame", background=SURFACE)
    style.configure("Surface2.TFrame", background=SURFACE_2)
    style.configure("TLabel", background=BG, foreground=TEXT, font=(FONT, 10))
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Title.TLabel", foreground=TEXT, font=(FONT_SEMIBOLD, 23))
    style.configure("Eyebrow.TLabel", foreground=MINT, font=(FONT_SEMIBOLD, 8))
    style.configure("Status.TLabel", foreground=MINT, font=(FONT_SEMIBOLD, 10))
    style.configure("Error.Status.TLabel", foreground=RED, font=(FONT_SEMIBOLD, 10))
    style.configure("Surface.TLabel", background=SURFACE, foreground=TEXT)
    style.configure("SurfaceMuted.TLabel", background=SURFACE, foreground=MUTED)
    style.configure("SurfaceHeading.TLabel", background=SURFACE, foreground=TEXT, font=(FONT_SEMIBOLD, 14))
    style.configure("SurfaceSelected.TLabel", background=SURFACE, foreground=TEXT, font=(FONT_SEMIBOLD, 15))
    style.configure("Support.TLabel", background=SURFACE, foreground=AMBER, font=(FONT_SEMIBOLD, 9))
    style.configure("SupportError.TLabel", background=SURFACE, foreground=RED, font=(FONT_SEMIBOLD, 9))
    style.configure("TButton", background=SURFACE_3, foreground=TEXT, padding=(11, 8), borderwidth=1)
    style.map("TButton", background=[("active", "#213650")])
    style.configure("Primary.TButton", background=MINT, foreground="#07130f", font=(FONT_SEMIBOLD, 10))
    style.map("Primary.TButton", background=[("active", "#8fffd8")])
    style.configure(
        "ControllerIcon.TButton",
        background=SURFACE_2,
        foreground=MUTED,
        font=(FONT_SEMIBOLD, 7),
        padding=(1, 2),
        borderwidth=1,
        anchor="center",
    )
    style.map(
        "ControllerIcon.TButton",
        background=[("active", SURFACE_3)],
        foreground=[("active", TEXT)],
    )
    style.configure(
        "Selected.ControllerIcon.TButton",
        background=MINT_DARK,
        foreground=MINT,
        font=(FONT_SEMIBOLD, 7),
        padding=(1, 2),
        borderwidth=2,
        anchor="center",
    )
    style.map(
        "Selected.ControllerIcon.TButton",
        background=[("active", "#174c40")],
        foreground=[("active", MINT)],
    )
    style.configure("TCheckbutton", background=SURFACE, foreground=TEXT)
    style.configure("TCombobox", fieldbackground=SURFACE_2, background=SURFACE_2, foreground=TEXT)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE_2)])
    style.configure("TEntry", fieldbackground="#091522", foreground=TEXT, insertcolor=TEXT)
    style.configure("Horizontal.TProgressbar", troughcolor="#091522", background=MINT)
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED, padding=(14, 9))
    style.map(
        "TNotebook.Tab",
        background=[("selected", MINT_DARK), ("active", SURFACE_3)],
        foreground=[("selected", MINT), ("active", TEXT)],
    )
