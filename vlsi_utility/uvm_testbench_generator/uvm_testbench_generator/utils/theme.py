from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    panel: str
    panel_alt: str
    fg: str
    fg_muted: str
    border: str
    accent: str
    accent_hover: str
    success: str
    danger: str


DARK = Theme(
    name="dark",
    bg="#1e1e2f",
    panel="#29314f",
    panel_alt="#2c313c",
    fg="#ffffff",
    fg_muted="#cccccc",
    border="#3e4451",
    accent="#61afef",
    accent_hover="#7bc0ff",
    success="#28a745",
    danger="#ff6b6b",
)

LIGHT = Theme(
    name="light",
    bg="#f5f7fb",
    panel="#ffffff",
    panel_alt="#eef2f7",
    fg="#1d2433",
    fg_muted="#4b5565",
    border="#d6dde8",
    accent="#2563eb",
    accent_hover="#3b82f6",
    success="#16a34a",
    danger="#dc2626",
)


THEMES: dict[str, Theme] = {DARK.name: DARK, LIGHT.name: LIGHT}


def apply_theme(root: tk.Misc, theme_name: str) -> Theme:
    theme = THEMES.get(theme_name, DARK)

    try:
        root.configure(bg=theme.bg)
    except tk.TclError:
        pass

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("TFrame", background=theme.bg)
    style.configure("Card.TFrame", background=theme.panel, relief="flat")
    style.configure("Sidebar.TFrame", background=theme.panel_alt)
    style.configure("Header.TFrame", background=theme.panel)
    style.configure("Footer.TFrame", background=theme.border)

    style.configure("TLabel", background=theme.bg, foreground=theme.fg)
    style.configure("Muted.TLabel", background=theme.bg, foreground=theme.fg_muted)
    style.configure("Header.TLabel", background=theme.panel, foreground=theme.fg)
    style.configure("Footer.TLabel", background=theme.border, foreground=theme.fg)

    style.configure(
        "TButton",
        padding=(10, 6),
        background=theme.panel_alt,
        foreground=theme.fg,
        bordercolor=theme.border,
        focusthickness=2,
        focuscolor=theme.accent,
    )
    style.map(
        "TButton",
        background=[("active", theme.accent_hover)],
        foreground=[("active", theme.fg)],
    )

    style.configure(
        "Sidebar.TButton",
        padding=(12, 8),
        background=theme.panel_alt,
        foreground=theme.fg,
        anchor="w",
    )
    style.map(
        "Sidebar.TButton",
        background=[("active", theme.accent_hover)],
    )
    style.configure("SidebarActive.TButton", background=theme.accent, foreground=theme.fg)

    style.configure(
        "Treeview",
        background=theme.panel,
        fieldbackground=theme.panel,
        foreground=theme.fg,
        bordercolor=theme.border,
        rowheight=24,
    )
    style.configure(
        "Treeview.Heading",
        background=theme.panel_alt,
        foreground=theme.fg,
        relief="flat",
    )
    style.map("Treeview", background=[("selected", theme.accent)])

    style.configure(
        "TCombobox",
        padding=(6, 4),
    )

    style.configure(
        "TLabelframe",
        background=theme.bg,
        foreground=theme.fg,
        bordercolor=theme.border,
    )
    style.configure("TLabelframe.Label", background=theme.bg, foreground=theme.fg)

    return theme

