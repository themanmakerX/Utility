from __future__ import annotations

import tkinter as tk

from ..utils.theme import Theme, DARK
from ..utils.workflow import ModuleStatus, Status


class Sidebar(tk.Frame):
    def __init__(self, parent, callback):
        super().__init__(parent, bg=DARK.panel_alt)
        self._callback = callback

        self._theme: Theme = DARK
        self._rows: dict[str, tk.Frame] = {}
        self._indicators: dict[str, tk.Frame] = {}
        self._labels: dict[str, tk.Label] = {}
        self._badges: dict[str, tk.Label] = {}
        self._active_key: str | None = None
        self._statuses: dict[str, ModuleStatus] = {}

        self.buttons = [
            "dashboard",
            "project_details",
            "interface_dut",
            "transaction_class",
            "agent_class",
            "scoreboard_class",
            "environment_class",
            "sequence_class",
            "test_class",
            "top_module",
            "preview",
            "state_machine",
        ]

        for key in self.buttons:
            row = tk.Frame(self, bg=self._theme.panel_alt)
            row.pack(fill="x", padx=10, pady=4)

            indicator = tk.Frame(row, bg=self._theme.panel_alt, width=4, height=28)
            indicator.pack(side="left", fill="y")

            label = tk.Label(
                row,
                text=key.replace("_", " ").title(),
                font=("Segoe UI", 10, "bold"),
                bg=self._theme.panel_alt,
                fg=self._theme.fg,
                padx=10,
                pady=6,
                anchor="w",
                cursor="hand2",
            )
            label.pack(side="left", fill="x", expand=True)

            badge = tk.Label(
                row,
                text="",
                font=("Segoe UI", 9, "bold"),
                bg=self._theme.panel_alt,
                fg=self._theme.fg_muted,
                padx=8,
                pady=6,
                anchor="e",
                cursor="hand2",
            )
            badge.pack(side="right")

            for widget in (row, indicator, label):
                widget.bind("<Button-1>", lambda e, k=key: self._on_click(k))
                widget.bind("<Enter>", lambda e, k=key: self._on_hover(k, True))
                widget.bind("<Leave>", lambda e, k=key: self._on_hover(k, False))
            badge.bind("<Button-1>", lambda e, k=key: self._on_click(k))
            badge.bind("<Enter>", lambda e, k=key: self._on_hover(k, True))
            badge.bind("<Leave>", lambda e, k=key: self._on_hover(k, False))

            self._rows[key] = row
            self._indicators[key] = indicator
            self._labels[key] = label
            self._badges[key] = badge

        self.set_active("dashboard")

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_alt)
        for key in self.buttons:
            self._rows[key].configure(bg=theme.panel_alt)
            self._labels[key].configure(bg=theme.panel_alt, fg=theme.fg)
            self._badges[key].configure(bg=theme.panel_alt, fg=theme.fg_muted)
            self._indicators[key].configure(bg=theme.panel_alt)
        if self._active_key:
            self._apply_active_styles(self._active_key)

    def _on_click(self, key: str) -> None:
        status = self._statuses.get(key)
        if status and status.status == Status.BLOCKED:
            self.bell()
            return
        self.set_active(key)
        self._callback(key)

    def _on_hover(self, key: str, hovering: bool) -> None:
        if key == self._active_key:
            return
        bg = self._theme.panel if hovering else self._theme.panel_alt
        self._labels[key].configure(bg=bg)
        self._rows[key].configure(bg=bg)

    def _apply_active_styles(self, key: str) -> None:
        for k in self.buttons:
            is_active = k == key
            row_bg = self._theme.panel if is_active else self._theme.panel_alt
            self._rows[k].configure(bg=row_bg)
            self._labels[k].configure(bg=row_bg, fg=self._theme.fg)
            if is_active:
                self._indicators[k].configure(bg=self._theme.accent)
            else:
                self._indicators[k].configure(bg=self._indicator_color(k))
            self._badges[k].configure(bg=row_bg)

    def set_active(self, key: str) -> None:
        if key not in self._rows:
            return
        self._active_key = key
        self._apply_active_styles(key)

    def _indicator_color(self, key: str) -> str:
        status = self._statuses.get(key)
        if not status:
            return self._theme.panel_alt
        if status.status == Status.COMPLETE:
            return self._theme.success
        if status.status == Status.BLOCKED:
            return self._theme.danger
        return self._theme.accent_hover

    def set_statuses(self, statuses: dict[str, ModuleStatus]) -> None:
        self._statuses = dict(statuses)
        for key in self.buttons:
            status = self._statuses.get(key)
            if not status:
                self._badges[key].configure(text="")
                continue
            if status.status == Status.COMPLETE:
                self._badges[key].configure(text="OK", fg=self._theme.success)
            elif status.status == Status.BLOCKED:
                self._badges[key].configure(text="BLOCKED", fg=self._theme.danger)
            else:
                self._badges[key].configure(text="TODO" if status.missing else "", fg=self._theme.fg_muted)

        if self._active_key:
            self._apply_active_styles(self._active_key)
