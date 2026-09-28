from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def app_bg(widget: tk.Misc, fallback: str = "#f5f7fb") -> str:
    try:
        return str(widget.winfo_toplevel().cget("bg"))
    except Exception:
        return fallback


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, *, padding: int = 12):
        super().__init__(parent)

        bg = app_bg(self)
        self._canvas = tk.Canvas(self, highlightthickness=0, bg=bg)
        self._scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.content = ttk.Frame(self, padding=padding)
        self._window = self._canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._on_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mousewheel(self._canvas)
        self._bind_mousewheel(self.content)

    def _on_configure(self, event=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self._canvas.itemconfig(self._window, width=event.width)

    def _bind_mousewheel(self, widget: tk.Misc) -> None:
        # Windows / Mac / Linux support
        widget.bind("<MouseWheel>", self._on_mousewheel, add=True)
        widget.bind("<Button-4>", self._on_mousewheel_linux, add=True)
        widget.bind("<Button-5>", self._on_mousewheel_linux, add=True)

    def _on_mousewheel(self, event) -> None:
        try:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _on_mousewheel_linux(self, event) -> None:
        try:
            if event.num == 4:
                self._canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self._canvas.yview_scroll(1, "units")
        except Exception:
            pass


def section_title(parent, text: str) -> ttk.Label:
    return ttk.Label(parent, text=text, font=("Segoe UI", 16, "bold"))


def code_text(parent, *, height: int = 20) -> tk.Text:
    return tk.Text(
        parent,
        height=height,
        bg="#1e1e1e",
        fg="white",
        insertbackground="white",
        font=("Consolas", 10),
        wrap="none",
        undo=True,
    )


class CodePreview(ttk.Frame):
    def __init__(self, parent, *, height: int = 20):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.text = code_text(self, height=height)
        self.scroll_y = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.scroll_x = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.corner = ttk.Frame(self, width=16)

        self.text.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)

        self.text.grid(row=0, column=0, sticky="nsew")
        self.scroll_y.grid(row=0, column=1, sticky="ns")
        self.scroll_x.grid(row=1, column=0, sticky="ew")
        self.corner.grid(row=1, column=1, sticky="nsew")


class CodeNotebook(ttk.Frame):
    def __init__(self, parent, *, height: int = 20):
        super().__init__(parent)
        self.height = height
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self._tabs: dict[str, CodePreview] = {}

    def set_tabs(self, tabs: list[str]) -> None:
        existing = set(self._tabs.keys())
        desired = list(dict.fromkeys([t for t in tabs if t]))  # unique, keep order

        for name in list(existing):
            if name not in desired:
                widget = self._tabs.pop(name)
                try:
                    self.notebook.forget(widget)
                except Exception:
                    pass

        for name in desired:
            if name in self._tabs:
                continue
            frame = CodePreview(self.notebook, height=self.height)
            self._tabs[name] = frame
            self.notebook.add(frame, text=name)

    def tab_names(self) -> list[str]:
        return list(self._tabs.keys())

    def get_text_widget(self, tab_name: str) -> tk.Text | None:
        widget = self._tabs.get(tab_name)
        return None if widget is None else widget.text

    def current_tab_name(self) -> str | None:
        try:
            current_id = self.notebook.select()
        except Exception:
            return None
        if not current_id:
            return None
        for name, widget in self._tabs.items():
            if str(widget) == str(current_id):
                return name
        return None

    def select_tab(self, tab_name: str) -> None:
        widget = self._tabs.get(tab_name)
        if widget is None:
            return
        try:
            self.notebook.select(widget)
        except Exception:
            pass
