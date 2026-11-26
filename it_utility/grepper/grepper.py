"""
Grepper: a fast, GUI-based search tool for folders and files.

This project is designed to be published as a small GitHub repo and can be run as
`python grepper.py` (or installed as a console script when packaged).
"""

import os
import sys
import re
import fnmatch
import json
import time
import threading
import subprocess
import csv
import logging
import stat
import shutil
import queue
from dataclasses import dataclass, field
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

__all__ = ["main", "__version__"]
__version__ = "0.1.1"


# ---------- Utilities ----------
class ToolTip:
    def __init__(self, widget, text: str, *, delay_ms: int = 500):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _e=None):
        if not self.text:
            return
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _e=None):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._hide()

    def _show(self):
        if self._tip is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        except Exception:
            return
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        frm = ttk.Frame(self._tip, padding=(8, 6))
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=self.text, justify="left", wraplength=420).pack()

    def _hide(self):
        if self._tip is None:
            return
        try:
            self._tip.destroy()
        except Exception:
            pass
        self._tip = None


def fmt_size(num_bytes: int) -> str:
    try:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if num_bytes < 1024.0:
                return f"{num_bytes:.1f} {unit}" if unit != 'B' else f"{num_bytes} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} PB"
    except Exception:
        return "N/A"


def fmt_time(ts: float) -> str:
    try:
        import datetime as _dt
        return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "N/A"


def is_binary_quick(path: str) -> bool:
    try:
        with open(path, "rb") as fb:
            chunk = fb.read(2048)
            return b"\x00" in chunk
    except Exception:
        return True  # treat unreadable as binary/skip


def is_hidden_path(path: str) -> bool:
    name = os.path.basename(path.rstrip("\\/"))
    if name.startswith("."):
        return True
    if sys.platform.startswith("win"):
        try:
            attrs = os.stat(path).st_file_attributes
            return bool(attrs & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))
        except Exception:
            return False
    return False


def load_gitignore_rules(base_dir: str) -> list[tuple[str, bool, bool]]:
    """
    Very small subset of .gitignore:
    - blank lines and # comments ignored
    - !negation supported
    - patterns with / are matched against the relative posix path
    - patterns without / are matched against the basename
    - patterns ending with / only apply to directories
    """
    rules: list[tuple[str, bool, bool]] = []
    path = os.path.join(base_dir, ".gitignore")
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                negated = line.startswith("!")
                if negated:
                    line = line[1:].strip()
                    if not line:
                        continue
                dir_only = line.endswith("/")
                pat = line.rstrip("/")
                rules.append((pat, negated, dir_only))
    except Exception:
        return []
    return rules


def gitignore_ignored(rel_posix_path: str, is_dir: bool, rules: list[tuple[str, bool, bool]]) -> bool:
    if not rules:
        return False
    ignored = False
    rel_posix_path = rel_posix_path.strip("/")
    name = rel_posix_path.rsplit("/", 1)[-1]
    for pat, negated, dir_only in rules:
        if dir_only and not is_dir:
            continue
        target = rel_posix_path if ("/" in pat) else name
        matched = fnmatch.fnmatchcase(target, pat)
        if dir_only and "/" in pat:
            matched = matched or target.startswith(pat.rstrip("/") + "/")
        if matched:
            ignored = not negated
    return ignored


def default_open(path: str):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("Open Error", str(e))


# ---------- Tab State ----------
@dataclass
class TabState:
    # widgets
    frame: ttk.Frame
    status_label: ttk.Label

    # mode
    mode: tk.StringVar

    # common controls
    dir_entry: ttk.Entry
    include_entry: ttk.Entry
    exclude_entry: ttk.Entry
    max_mb_entry: ttk.Entry
    depth_entry: ttk.Entry
    skip_hidden_var: tk.BooleanVar
    respect_gitignore_var: tk.BooleanVar

    # text-mode controls
    text_group: ttk.Frame
    search_entry: ttk.Entry
    filetype_combo: ttk.Combobox
    chk_regex: tk.BooleanVar
    chk_case: tk.BooleanVar
    chk_word: tk.BooleanVar
    context_lines_var: tk.IntVar
    first_match_per_file_var: tk.BooleanVar
    use_ripgrep_var: tk.BooleanVar

    # file-mode controls
    file_group: ttk.Frame
    fname_entry: ttk.Entry
    fname_chk_regex: tk.BooleanVar
    fname_chk_case: tk.BooleanVar
    fname_chk_word: tk.BooleanVar
    content_filter_var: tk.BooleanVar
    content_entry: ttk.Entry
    content_chk_regex: tk.BooleanVar
    content_chk_case: tk.BooleanVar
    content_chk_word: tk.BooleanVar

    # folder-mode controls
    folder_group: ttk.Frame
    folder_entry: ttk.Entry
    folder_chk_regex: tk.BooleanVar
    folder_chk_case: tk.BooleanVar
    folder_chk_word: tk.BooleanVar
    folder_content_filter_var: tk.BooleanVar
    folder_content_entry: ttk.Entry
    folder_content_chk_regex: tk.BooleanVar
    folder_content_chk_case: tk.BooleanVar
    folder_content_chk_word: tk.BooleanVar

    # results and logs
    result_tree: ttk.Treeview
    log_text: tk.Text
    preview_text: tk.Text
    btn_search: ttk.Button
    btn_pause: ttk.Button
    btn_stop: ttk.Button
    processing_nb: ttk.Notebook
    processing_preview_tab: ttk.Frame
    summary_label: ttk.Label
    progress_bar: ttk.Progressbar
    engine_label: ttk.Label

    # runtime
    pause_event: threading.Event = field(default_factory=threading.Event)
    stop_event: threading.Event = field(default_factory=threading.Event)
    result_q: queue.Queue = field(default_factory=queue.Queue)
    log_q: queue.Queue = field(default_factory=queue.Queue)
    start_ts: float = 0.0
    paused_at: float = 0.0
    total_paused_sec: float = 0.0
    paused_files_snapshot: int = 0
    paused_matches_snapshot: int = 0
    files_scanned: int = 0
    matches_found: int = 0
    current_columns: tuple = field(default_factory=tuple)
    preview_highlight_re: re.Pattern | None = None
    outcome: str = "idle"
    last_progress_log_ts: float = 0.0
    closed: bool = False
    active_mode: str = "Text"


class Grepper:
    def __init__(self, root, parent=None):
        self.root = root
        self.parent = parent
        self.root.title("Grepper")
        self.root.geometry("1360x840")
        self.root.minsize(1050, 680)
        self.root.configure(bg="#EEF2FF")

        self.tabs: dict[str, TabState] = {}
        self.logging_enabled = tk.BooleanVar(value=False)
        self._logger = logging.getLogger("grepper")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._log_handler: logging.Handler | None = None
        self._rg_path = shutil.which("rg")
        self._settings = self._load_settings()

        self._build_styles()
        self._build_main_ui()
        self.root.after_idle(self._maximize_window)

    def _maximize_window(self):
        """Use the available desktop while keeping a portable fallback."""
        try:
            self.root.state("zoomed")
            return
        except Exception:
            pass
        try:
            width = int(self.root.winfo_screenwidth() * 0.92)
            height = int(self.root.winfo_screenheight() * 0.88)
            self.root.geometry(f"{width}x{height}+20+20")
        except Exception:
            pass

    # ---------- Styles ----------
    def _build_styles(self):
        style = ttk.Style()
        try:
            # Use a modern theme if available
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        # Base colors
        bg = "#F5F7FF"
        fg = "#172554"
        accent = "#5B5FEF"
        accent_hover = "#4338CA"
        muted = "#EEF2FF"
        muted2 = "#DDE5FF"
        border = "#C7D2FE"
        success = "#059669"
        warn = "#D97706"
        danger = "#E11D48"
        surface = "#FFFFFF"
        subtle = "#64748B"
        cyan = "#06B6D4"

        self.colors = dict(bg=bg, fg=fg, accent=accent, accent_hover=accent_hover,
                           muted=muted, muted2=muted2, border=border,
                           success=success, warn=warn, danger=danger, surface=surface, subtle=subtle, cyan=cyan)

        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground=accent)
        style.configure("TEntry", fieldbackground="#FFFFFF", foreground=fg, padding=6)
        style.configure("TCombobox", padding=5)
        style.configure("TCheckbutton", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("TRadiobutton", background=bg, foreground=fg, font=("Segoe UI", 10))

        style.configure("TButton",
                        background=muted,
                        foreground=fg,
                        bordercolor=border,
                        focusthickness=3,
                        focuscolor=accent,
                        padding=(14, 8),
                        font=("Segoe UI", 10, "bold"))
        style.map("TButton",
                  background=[("disabled", "#E2E8F0"), ("active", muted)],
                  foreground=[("disabled", "#94A3B8"), ("active", fg)])

        style.configure("Accent.TButton",
                        background=accent,
                        foreground="#FFFFFF")
        style.map("Accent.TButton",
                  background=[("disabled", "#CBD5E1"), ("active", accent)],
                  foreground=[("disabled", "#94A3B8"), ("active", "#FFFFFF")])

        style.configure("Pause.TButton", background=warn, foreground="#FFFFFF")
        style.map("Pause.TButton",
                  background=[("disabled", "#E2E8F0"), ("active", warn)],
                  foreground=[("disabled", "#94A3B8"), ("active", "#FFFFFF")])

        style.configure("Resume.TButton", background=success, foreground="#FFFFFF")
        style.map("Resume.TButton",
                  background=[("disabled", "#E2E8F0"), ("active", success)],
                  foreground=[("disabled", "#94A3B8"), ("active", "#FFFFFF")])

        style.configure("Danger.TButton", background=danger, foreground="#FFFFFF")
        style.map("Danger.TButton",
                  background=[("disabled", "#E2E8F0"), ("active", danger)],
                  foreground=[("disabled", "#94A3B8"), ("active", "#FFFFFF")])

        style.configure("TLabelframe", background=surface, bordercolor=border, relief="solid")
        style.configure("TLabelframe.Label", background=surface, foreground=accent, font=("Segoe UI", 11, "bold"))
        style.configure("Card.TFrame", background=surface)
        style.configure("Engine.TLabel", background="#E0F2FE", foreground="#0369A1", padding=(10, 5), font=("Segoe UI", 9, "bold"))
        style.configure("Success.TLabel", background="#D1FAE5", foreground="#047857", padding=(10, 5), font=("Segoe UI", 9, "bold"))
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=muted2, foreground=fg, padding=(16, 9), font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", surface), ("active", "#E0E7FF")], foreground=[("selected", accent)])
        style.configure("Horizontal.TProgressbar", background=cyan, troughcolor=muted2, bordercolor=muted2, lightcolor=cyan, darkcolor=cyan)

        style.configure("Treeview",
                        background=surface,
                        fieldbackground=surface,
                        foreground=fg,
                        bordercolor=border,
                        rowheight=29,
                        font=("Consolas", 10))
        style.configure("Treeview.Heading",
                        background=muted,
                        foreground=fg,
                        relief="flat",
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview.Heading",
                  background=[("active", muted2)])

        style.configure("Status.TLabel", background="#E0E7FF", foreground="#3730A3", padding=(10, 7), font=("Segoe UI", 10, "bold"))

        # Treeview selection
        try:
            style.map("Treeview",
                      background=[("selected", "#DBEAFE")],
                      foreground=[("selected", fg)])
        except Exception:
            pass

    # ---------- Main UI ----------
    def _build_main_ui(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(6, 8))

        # Shortcuts
        self.root.bind_all("<Control-n>", self._shortcut_new_tab, add="+")
        self.root.bind_all("<Control-N>", self._shortcut_new_tab, add="+")
        self.root.bind_all("<Control-w>", self._shortcut_close_tab, add="+")
        self.root.bind_all("<Control-W>", self._shortcut_close_tab, add="+")

        # Context menu for tabs (close)
        self.tab_menu = tk.Menu(self.root, tearoff=0)
        self.tab_menu.add_command(label="Close Tab", command=self._close_current_tab)

        self.notebook.bind("<Button-3>", self._on_tab_right_click)
        self.notebook.bind("<Button-1>", self._on_tab_left_click, add="+")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Add persistent ➕ tab and one real tab
        self._ensure_plus_tab()
        self.add_search_tab()

    def _toggle_logging(self):
        if self.logging_enabled.get():
            if self._log_handler is not None:
                return
            try:
                handler = logging.FileHandler("search.log", encoding="utf-8")
                handler.setLevel(logging.INFO)
                handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
                self._logger.addHandler(handler)
                self._log_handler = handler
                self._logger.info("Logging enabled.")
            except Exception as e:
                self._log_handler = None
                messagebox.showerror("Logging Error", str(e))
        else:
            if self._log_handler is None:
                return
            try:
                self._logger.info("Logging disabled.")
                self._logger.removeHandler(self._log_handler)
                try:
                    self._log_handler.close()
                finally:
                    self._log_handler = None
            except Exception:
                self._log_handler = None

    def _log_exception(self, msg: str, exc: Exception):
        try:
            enabled = bool(self.logging_enabled.get())
        except Exception:
            # Worker threads must not depend on a Tk variable read. Presence of
            # the handler is a safe mirror of the enabled state.
            enabled = self._log_handler is not None
        if not enabled:
            return
        try:
            self._logger.error("%s: %s", msg, exc, exc_info=True)
        except Exception:
            pass

    def _toggle_logging_from_menu(self):
        try:
            self.logging_enabled.set(not self.logging_enabled.get())
        except Exception:
            return
        self._toggle_logging()

    def _settings_path(self) -> str:
        base = os.getenv("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "Grepper", "settings.json")

    def _load_settings(self) -> dict:
        path = self._settings_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_settings(self):
        path = self._settings_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log_exception("Failed to save settings", e)

    def _apply_settings_to_tab(self, state: TabState):
        s = (self._settings or {}).get("defaults", {})
        try:
            directory = s.get("directory")
            if directory:
                state.dir_entry.delete(0, tk.END)
                state.dir_entry.insert(0, directory)

            state.include_entry.delete(0, tk.END)
            state.include_entry.insert(0, s.get("include_globs", ""))

            state.exclude_entry.delete(0, tk.END)
            state.exclude_entry.insert(0, s.get("exclude_globs", ".git;__pycache__"))

            state.max_mb_entry.delete(0, tk.END)
            state.max_mb_entry.insert(0, str(s.get("max_mb", "0")))

            state.depth_entry.delete(0, tk.END)
            state.depth_entry.insert(0, str(s.get("depth_limit", "")))

            state.skip_hidden_var.set(bool(s.get("skip_hidden", True)))
            state.respect_gitignore_var.set(bool(s.get("respect_gitignore", True)))

            mode = s.get("mode", "Text")
            state.mode.set(mode if mode in ("Text", "File", "Folder") else "Text")

            # Text mode
            state.search_entry.delete(0, tk.END)
            state.search_entry.insert(0, s.get("text_pattern", ""))
            state.filetype_combo.set(s.get("filetype", "All"))
            state.chk_regex.set(bool(s.get("text_regex", False)))
            state.chk_case.set(bool(s.get("text_case", False)))
            state.chk_word.set(bool(s.get("text_whole", False)))
            try:
                state.context_lines_var.set(int(s.get("context_lines", 2)))
            except Exception:
                state.context_lines_var.set(2)
            state.first_match_per_file_var.set(bool(s.get("first_match_per_file", False)))
            state.use_ripgrep_var.set(bool(s.get("use_ripgrep", bool(self._rg_path))))

            # File mode
            state.fname_entry.delete(0, tk.END)
            state.fname_entry.insert(0, s.get("fname_pattern", ""))
            state.fname_chk_regex.set(bool(s.get("fname_regex", False)))
            state.fname_chk_case.set(bool(s.get("fname_case", False)))
            state.fname_chk_word.set(bool(s.get("fname_whole", False)))

            state.content_filter_var.set(bool(s.get("content_filter_on", False)))
            state.content_entry.delete(0, tk.END)
            state.content_entry.insert(0, s.get("content_pattern", ""))
            state.content_chk_regex.set(bool(s.get("content_regex", False)))
            state.content_chk_case.set(bool(s.get("content_case", False)))
            state.content_chk_word.set(bool(s.get("content_whole", False)))

            # Folder mode
            state.folder_entry.delete(0, tk.END)
            state.folder_entry.insert(0, s.get("folder_pattern", ""))
            state.folder_chk_regex.set(bool(s.get("folder_regex", False)))
            state.folder_chk_case.set(bool(s.get("folder_case", False)))
            state.folder_chk_word.set(bool(s.get("folder_whole", False)))

            state.folder_content_filter_var.set(bool(s.get("folder_content_filter_on", False)))
            state.folder_content_entry.delete(0, tk.END)
            state.folder_content_entry.insert(0, s.get("folder_content_pattern", ""))
            state.folder_content_chk_regex.set(bool(s.get("folder_content_regex", False)))
            state.folder_content_chk_case.set(bool(s.get("folder_content_case", False)))
            state.folder_content_chk_word.set(bool(s.get("folder_content_whole", False)))
        except Exception:
            pass

    def _update_settings_from_tab(self, state: TabState):
        try:
            defaults = {
                "directory": state.dir_entry.get().strip(),
                "include_globs": state.include_entry.get().strip(),
                "exclude_globs": state.exclude_entry.get().strip(),
                "max_mb": state.max_mb_entry.get().strip(),
                "depth_limit": state.depth_entry.get().strip(),
                "skip_hidden": state.skip_hidden_var.get(),
                "respect_gitignore": state.respect_gitignore_var.get(),
                "mode": state.mode.get(),

                "text_pattern": state.search_entry.get(),
                "filetype": state.filetype_combo.get(),
                "text_regex": state.chk_regex.get(),
                "text_case": state.chk_case.get(),
                "text_whole": state.chk_word.get(),
                "context_lines": int(state.context_lines_var.get()),
                "first_match_per_file": state.first_match_per_file_var.get(),
                "use_ripgrep": state.use_ripgrep_var.get(),

                "fname_pattern": state.fname_entry.get(),
                "fname_regex": state.fname_chk_regex.get(),
                "fname_case": state.fname_chk_case.get(),
                "fname_whole": state.fname_chk_word.get(),
                "content_filter_on": state.content_filter_var.get(),
                "content_pattern": state.content_entry.get(),
                "content_regex": state.content_chk_regex.get(),
                "content_case": state.content_chk_case.get(),
                "content_whole": state.content_chk_word.get(),

                "folder_pattern": state.folder_entry.get(),
                "folder_regex": state.folder_chk_regex.get(),
                "folder_case": state.folder_chk_case.get(),
                "folder_whole": state.folder_chk_word.get(),
                "folder_content_filter_on": state.folder_content_filter_var.get(),
                "folder_content_pattern": state.folder_content_entry.get(),
                "folder_content_regex": state.folder_content_chk_regex.get(),
                "folder_content_case": state.folder_content_chk_case.get(),
                "folder_content_whole": state.folder_content_chk_word.get(),
            }
            self._settings = {"defaults": defaults}
        except Exception:
            pass

    def _on_close(self):
        for state in self.tabs.values():
            state.closed = True
            if state.outcome == "running":
                state.outcome = "cancelled"
            state.stop_event.set()
        try:
            self._save_settings()
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass

    # ---------- Tabs ----------
    def _ensure_plus_tab(self):
        # If last tab isn't the plus tab, add it
        for tab_id in self.notebook.tabs():
            if self.notebook.tab(tab_id, "text") == "+":
                # move it to the end if needed
                self.notebook.forget(tab_id)
                self.notebook.add(self._build_plus_tab(), text="+")
                return
        self.notebook.add(self._build_plus_tab(), text="+")

    def _build_plus_tab(self):
        frame = ttk.Frame(self.notebook, padding=20)
        ttk.Label(frame, text="Click + to add a new search tab.", style="Header.TLabel").pack()
        return frame

    def _on_tab_changed(self, _):
        current = self.notebook.select()
        if self.notebook.tab(current, "text") == "+":
            self.add_search_tab()

    def _on_tab_left_click(self, event):
        try:
            i = self.notebook.index(f"@{event.x},{event.y}")
            tab_id = self.notebook.tabs()[i]
            if self.notebook.tab(tab_id, "text") == "+":
                return
            bbox = self.notebook.bbox(i)
            if not bbox:
                return
            x0, y0, w, h = bbox
            # Click on the close glyph area (right edge of tab)
            if event.x >= (x0 + w - 18):
                self.notebook.select(i)
                self._close_current_tab()
                return "break"
        except Exception:
            return

    def _on_tab_right_click(self, event):
        # Show close menu only for real tabs
        try:
            x, y = event.x, event.y
            i = self.notebook.index(f"@{x},{y}")
            tab_id = self.notebook.tabs()[i]
            if self.notebook.tab(tab_id, "text") == "+":
                return
            self.notebook.select(i)
            self.tab_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tab_menu.grab_release()

    def _close_current_tab(self):
        tab_id = self.notebook.select()
        if self.notebook.tab(tab_id, "text") == "+":
            return
        # Don't close if this is the last real tab
        real_tabs = [t for t in self.notebook.tabs() if self.notebook.tab(t, "text") != "+"]
        if len(real_tabs) <= 1:
            return
        # Stop background work before destroying widgets. The queue pump checks
        # the closed flag so already-scheduled callbacks become harmless.
        state = self.tabs.pop(tab_id, None)
        if state is not None:
            state.closed = True
            if state.outcome == "running":
                state.outcome = "cancelled"
            state.stop_event.set()
        self.notebook.forget(tab_id)
        self._ensure_plus_tab()

    def _shortcut_new_tab(self, _event=None):
        self.add_search_tab()
        return "break"

    def _shortcut_close_tab(self, _event=None):
        self._close_current_tab()
        return "break"

    def add_search_tab(self):
        # Insert before ➕ tab
        plus_index = len(self.notebook.tabs())
        if plus_index > 0:
            plus_index -= 1

        tab_frame = ttk.Frame(self.notebook, padding=8)
        self.notebook.insert(plus_index, tab_frame, text=f"Search {plus_index + 1}  ×")

        # Main content + footer (per-tab)
        content = ttk.Frame(tab_frame)
        content.pack(fill="both", expand=True)

        # Options
        options = ttk.Labelframe(content, text="  Search workspace  ", padding=10)
        options.pack(fill="x")

        # Mode is kept on the directory row to preserve vertical workspace.
        mode_var = tk.StringVar(value="Text")

        # Primary controls
        row = 1
        ttk.Label(options, text="Folder:").grid(row=row, column=0, sticky="e", padx=5, pady=4)
        dir_entry = ttk.Entry(options, width=60)
        dir_entry.grid(row=row, column=1, columnspan=3, sticky="we", padx=5, pady=4)
        btn_browse = ttk.Button(options, text="Choose folder", command=lambda: self._pick_folder(dir_entry))
        btn_browse.grid(row=row, column=4, padx=5, pady=4)
        self._add_hover(btn_browse)
        ttk.Label(options, text="Mode:").grid(row=row, column=5, sticky="e", padx=(10, 4), pady=4)
        mode_combo = ttk.Combobox(options, textvariable=mode_var, values=("Text", "File", "Folder"), state="readonly", width=10)
        mode_combo.grid(row=row, column=6, sticky="we", padx=4, pady=4)
        ToolTip(mode_combo, "Choose whether to search file contents, filenames, or folder names.")

        row += 1
        include_label = ttk.Label(options, text="Include:")
        include_label.grid(row=row, column=0, sticky="e", padx=5, pady=4)
        include_entry = ttk.Entry(options, width=40)
        include_entry.insert(0, "")
        include_entry.grid(row=row, column=1, sticky="we", padx=5, pady=4)
        ToolTip(include_entry, "Semicolon-separated glob patterns to include (e.g. *.py;*.txt). Leave blank for all.")

        exclude_label = ttk.Label(options, text="Exclude:")
        exclude_label.grid(row=row, column=2, sticky="e", padx=5, pady=4)
        exclude_entry = ttk.Entry(options, width=40)
        exclude_entry.insert(0, ".git;__pycache__")
        exclude_entry.grid(row=row, column=3, sticky="we", padx=5, pady=4)
        ToolTip(exclude_entry, "Semicolon-separated globs to exclude (folders or files), e.g. .git;__pycache__;node_modules;*.png")

        max_size_label = ttk.Label(options, text="Max MB:")
        max_size_label.grid(row=row, column=4, sticky="e", padx=5, pady=4)
        max_mb_entry = ttk.Entry(options, width=8)
        max_mb_entry.insert(0, "0")
        max_mb_entry.grid(row=row, column=5, sticky="we", padx=5, pady=4)
        ToolTip(max_mb_entry, "Skip files larger than this size in MB. Use 0 for unlimited.")

        depth_label = ttk.Label(options, text="Depth:")
        depth_label.grid(row=row, column=6, sticky="e", padx=5, pady=4)
        depth_entry = ttk.Entry(options, width=6)
        depth_entry.insert(0, "")  # blank = unlimited
        depth_entry.grid(row=row, column=7, sticky="we", padx=5, pady=4)
        ToolTip(depth_entry, "Maximum folder depth to scan from the base directory. Blank = unlimited.")

        row += 1
        flags = ttk.Frame(options)
        flags.grid(row=row, column=0, columnspan=8, sticky="w", padx=5, pady=(4, 0))
        skip_hidden_var = tk.BooleanVar(value=True)
        respect_gitignore_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(flags, text="Skip hidden", variable=skip_hidden_var).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(flags, text="Respect .gitignore", variable=respect_gitignore_var).pack(side="left", padx=(0, 10))
        ToolTip(flags, "Skip hidden folders/files and optionally apply .gitignore rules from the base directory.")

        # ---- Text mode group ----
        text_group = ttk.Frame(options)
        row += 1
        text_group.grid(row=row, column=0, columnspan=6, sticky="we", pady=(4, 0))

        ttk.Label(text_group, text="Search string:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        search_entry = ttk.Entry(text_group, width=60)
        search_entry.grid(row=0, column=1, columnspan=3, sticky="we", padx=5, pady=4)

        ttk.Label(text_group, text="File Type:").grid(row=0, column=4, sticky="e", padx=5, pady=4)
        filetype_combo = ttk.Combobox(text_group, values=['All', '.txt', '.xml', '.py', '.log', '.csv'])
        filetype_combo.set('All')
        filetype_combo.grid(row=0, column=5, sticky="we", padx=5, pady=4)

        chk_regex = tk.BooleanVar(value=False)
        chk_case = tk.BooleanVar(value=False)
        chk_word = tk.BooleanVar(value=False)
        context_lines_var = tk.IntVar(value=2)
        first_match_per_file_var = tk.BooleanVar(value=False)
        use_ripgrep_var = tk.BooleanVar(value=bool(self._rg_path))
        cbx = ttk.Frame(text_group)
        cbx.grid(row=1, column=1, columnspan=5, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(cbx, text="Regex", variable=chk_regex).pack(side="left", padx=5)
        ttk.Checkbutton(cbx, text="Case sensitive", variable=chk_case).pack(side="left", padx=5)
        ttk.Checkbutton(cbx, text="Whole word", variable=chk_word).pack(side="left", padx=5)
        ttk.Checkbutton(cbx, text="First match per file", variable=first_match_per_file_var).pack(side="left", padx=(15, 5))
        ttk.Label(cbx, text="Context:").pack(side="left", padx=(15, 4))
        ttk.Spinbox(cbx, from_=0, to=50, width=4, textvariable=context_lines_var).pack(side="left")
        cb_rg = ttk.Checkbutton(cbx, text="Use ripgrep (rg)", variable=use_ripgrep_var)
        cb_rg.pack(side="left", padx=(15, 5))
        if not self._rg_path:
            cb_rg.configure(state="disabled")

        # Compact accordion-style dropdown. A native menu is unsuitable here
        # because include/exclude patterns and numeric limits need real inputs.
        advanced_open = tk.BooleanVar(value=False)
        advanced_common_widgets = (
            include_label, include_entry, exclude_label, exclude_entry,
            max_size_label, max_mb_entry, depth_label, depth_entry, flags,
        )

        def toggle_advanced_filters():
            if advanced_open.get():
                for widget in advanced_common_widgets:
                    widget.grid()
                if mode_var.get() == "Text":
                    cbx.grid()
                advanced_btn.configure(text="Advanced filters  ^")
            else:
                for widget in advanced_common_widgets:
                    widget.grid_remove()
                cbx.grid_remove()
                advanced_btn.configure(text="Advanced filters  v")

        def flip_advanced_filters():
            advanced_open.set(not advanced_open.get())
            toggle_advanced_filters()

        advanced_btn = ttk.Button(options, text="Advanced filters  v", command=flip_advanced_filters)
        advanced_btn.grid(row=1, column=7, sticky="e", padx=(8, 2))
        ToolTip(advanced_btn, "Show include/exclude patterns, limits, hidden-file rules, regex, context, and engine options.")
        toggle_advanced_filters()

        # ---- File mode group ----
        file_group = ttk.Frame(options)
        # initially hidden; placed in same grid cell as text_group
        file_group.grid(row=row, column=0, columnspan=6, sticky="we", pady=(4, 0))
        file_group.grid_remove()

        ttk.Label(file_group, text="Filename pattern:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        fname_entry = ttk.Entry(file_group, width=60)
        fname_entry.grid(row=0, column=1, columnspan=3, sticky="we", padx=5, pady=4)

        fname_chk_regex = tk.BooleanVar(value=False)
        fname_chk_case = tk.BooleanVar(value=False)
        fname_chk_word = tk.BooleanVar(value=False)

        fbox = ttk.Frame(file_group)
        fbox.grid(row=0, column=4, columnspan=3, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(fbox, text="Regex", variable=fname_chk_regex).pack(side="left", padx=5)
        ttk.Checkbutton(fbox, text="Case sensitive", variable=fname_chk_case).pack(side="left", padx=5)
        ttk.Checkbutton(fbox, text="Whole word", variable=fname_chk_word).pack(side="left", padx=5)

        content_filter_var = tk.BooleanVar(value=False)
        cbox = ttk.Frame(file_group)
        cbox.grid(row=1, column=0, columnspan=7, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(cbox, text="Also filter by file content", variable=content_filter_var,
                        command=lambda: self._toggle_content_controls(content_filter_var, content_entry, content_opts)).pack(side="left", padx=5)

        ttk.Label(file_group, text="Content pattern:").grid(row=2, column=0, sticky="e", padx=5, pady=4)
        content_entry = ttk.Entry(file_group, width=60)
        content_entry.grid(row=2, column=1, columnspan=3, sticky="we", padx=5, pady=4)
        content_opts = ttk.Frame(file_group)
        content_opts.grid(row=2, column=4, columnspan=3, sticky="w", padx=5, pady=2)
        content_chk_regex = tk.BooleanVar(value=False)
        content_chk_case = tk.BooleanVar(value=False)
        content_chk_word = tk.BooleanVar(value=False)
        ttk.Checkbutton(content_opts, text="Regex", variable=content_chk_regex).pack(side="left", padx=5)
        ttk.Checkbutton(content_opts, text="Case sensitive", variable=content_chk_case).pack(side="left", padx=5)
        ttk.Checkbutton(content_opts, text="Whole word", variable=content_chk_word).pack(side="left", padx=5)
        # disable initially
        self._toggle_content_controls(content_filter_var, content_entry, content_opts)

        # ---- Folder mode group ----
        folder_group = ttk.Frame(options)
        folder_group.grid(row=row, column=0, columnspan=6, sticky="we", pady=(4, 0))
        folder_group.grid_remove()

        ttk.Label(folder_group, text="Folder name pattern:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        folder_entry = ttk.Entry(folder_group, width=60)
        folder_entry.grid(row=0, column=1, columnspan=3, sticky="we", padx=5, pady=4)

        folder_chk_regex = tk.BooleanVar(value=False)
        folder_chk_case = tk.BooleanVar(value=False)
        folder_chk_word = tk.BooleanVar(value=False)

        fldr_opts = ttk.Frame(folder_group)
        fldr_opts.grid(row=0, column=4, columnspan=3, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(fldr_opts, text="Regex", variable=folder_chk_regex).pack(side="left", padx=5)
        ttk.Checkbutton(fldr_opts, text="Case sensitive", variable=folder_chk_case).pack(side="left", padx=5)
        ttk.Checkbutton(fldr_opts, text="Whole word", variable=folder_chk_word).pack(side="left", padx=5)

        folder_content_filter_var = tk.BooleanVar(value=False)
        folder_cbox = ttk.Frame(folder_group)
        folder_cbox.grid(row=1, column=0, columnspan=7, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(
            folder_cbox,
            text="Also filter folders by file content (files directly inside each matched folder)",
            variable=folder_content_filter_var,
            command=lambda: self._toggle_content_controls(folder_content_filter_var, folder_content_entry, folder_content_opts),
        ).pack(side="left", padx=5)

        ttk.Label(folder_group, text="Content pattern:").grid(row=2, column=0, sticky="e", padx=5, pady=4)
        folder_content_entry = ttk.Entry(folder_group, width=60)
        folder_content_entry.grid(row=2, column=1, columnspan=3, sticky="we", padx=5, pady=4)
        folder_content_opts = ttk.Frame(folder_group)
        folder_content_opts.grid(row=2, column=4, columnspan=3, sticky="w", padx=5, pady=2)
        folder_content_chk_regex = tk.BooleanVar(value=False)
        folder_content_chk_case = tk.BooleanVar(value=False)
        folder_content_chk_word = tk.BooleanVar(value=False)
        ttk.Checkbutton(folder_content_opts, text="Regex", variable=folder_content_chk_regex).pack(side="left", padx=5)
        ttk.Checkbutton(folder_content_opts, text="Case sensitive", variable=folder_content_chk_case).pack(side="left", padx=5)
        ttk.Checkbutton(folder_content_opts, text="Whole word", variable=folder_content_chk_word).pack(side="left", padx=5)
        self._toggle_content_controls(folder_content_filter_var, folder_content_entry, folder_content_opts)

        # Buttons
        btns = ttk.Frame(options)
        btns.grid(row=row, column=6, columnspan=2, sticky="e", padx=(8, 0), pady=(4, 0))

        # Placeholders for lambdas; we'll wire after building state
        btn_search = ttk.Button(btns, text="Start search", style="Accent.TButton")
        btn_search.grid(row=0, column=0, padx=(0, 8))
        self._add_hover(btn_search)

        btn_pause = ttk.Button(btns, text="Pause", style="Pause.TButton")
        btn_pause.grid(row=0, column=1, padx=(0, 8))
        self._add_hover(btn_pause)

        btn_stop = ttk.Button(btns, text="Cancel", style="Danger.TButton")
        btn_stop.grid(row=0, column=2, padx=(0, 8))
        self._add_hover(btn_stop)

        more_btn = ttk.Menubutton(btns, text="More")
        more_btn.grid(row=0, column=3, padx=(0, 0))

        # Wide workspace: Results and Details share the full available height.
        paned = ttk.Panedwindow(content, orient="horizontal")
        paned.pack(fill='both', expand=True, pady=10)

        result_frame = ttk.Labelframe(paned, text="  Results  ")
        processing_frame = ttk.Labelframe(paned, text="  Details  ")
        paned.add(result_frame, weight=5)
        paned.add(processing_frame, weight=3)

        # Results summary strip
        summary_bar = ttk.Frame(result_frame, padding=(6, 6, 6, 0))
        summary_bar.pack(fill="x")
        summary_label = ttk.Label(summary_bar, text="Ready.", foreground=self.colors["subtle"])
        summary_label.pack(side="left")
        workspace_expanded = tk.BooleanVar(value=True)

        def set_initial_split():
            try:
                width = paned.winfo_width()
                if width > 400:
                    paned.sashpos(0, int(width * 0.68))
            except Exception:
                pass

        def toggle_workspace():
            if workspace_expanded.get():
                options.pack_forget()
                workspace_expanded.set(False)
                focus_btn.configure(text="Show filters")
            else:
                options.pack(fill="x", before=paned)
                workspace_expanded.set(True)
                focus_btn.configure(text="Focus workspace")
            self.root.after(80, set_initial_split)

        focus_btn = ttk.Button(summary_bar, text="Focus workspace", command=toggle_workspace)
        focus_btn.pack(side="right", padx=(8, 0))
        ToolTip(focus_btn, "Hide search filters to give Results and Details the full window; click again to restore them.")
        engine_label = ttk.Label(summary_bar, text="ENGINE  READY", style="Engine.TLabel")
        engine_label.pack(side="right")
        progress_bar = ttk.Progressbar(summary_bar, mode="indeterminate", length=150, style="Horizontal.TProgressbar")
        progress_bar.pack(side="right", padx=(8, 12))

        # Results tree
        columns_text = ('filepath', 'line_no', 'line_text')
        tree_wrap = ttk.Frame(result_frame, padding=(6, 6, 6, 6))
        tree_wrap.pack(fill="both", expand=True)
        tree_scroll_y = ttk.Scrollbar(tree_wrap, orient="vertical")
        tree_scroll_x = ttk.Scrollbar(tree_wrap, orient="horizontal")
        result_tree = ttk.Treeview(
            tree_wrap,
            columns=columns_text,
            show='headings',
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
        )
        tree_scroll_y.configure(command=result_tree.yview)
        tree_scroll_x.configure(command=result_tree.xview)
        self._configure_tree_columns(result_tree, mode="Text")
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")
        result_tree.pack(side="left", fill="both", expand=True)
        self._apply_tree_stripes(result_tree)
        self._attach_tree_behaviors(result_tree)

        # Processing toolbar + notebook: Logs + Preview
        proc_toolbar = ttk.Frame(processing_frame, padding=(6, 6, 6, 0))
        proc_toolbar.pack(fill="x")
        btn_clear_logs = ttk.Button(proc_toolbar, text="Clear Logs")
        btn_clear_logs.pack(side="right")

        processing_nb = ttk.Notebook(processing_frame)
        processing_nb.pack(fill="both", expand=True, padx=6, pady=6)
        log_tab = ttk.Frame(processing_nb, padding=6)
        preview_tab = ttk.Frame(processing_nb, padding=6)
        processing_nb.add(preview_tab, text="Preview")
        processing_nb.add(log_tab, text="Activity")

        # Log Text
        log_wrap = ttk.Frame(log_tab)
        log_wrap.pack(fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_wrap, orient="vertical")
        log_text = tk.Text(
            log_wrap,
            height=6,
            bg=self.colors["surface"],
            fg=self.colors["fg"],
            font=("Consolas", 10),
            yscrollcommand=log_scroll.set,
            wrap="none",
        )
        log_scroll.configure(command=log_text.yview)
        log_scroll.pack(side="right", fill="y")
        log_text.pack(side="left", fill="both", expand=True)

        # Preview Text
        preview_wrap = ttk.Frame(preview_tab)
        preview_wrap.pack(fill="both", expand=True)
        preview_scroll = ttk.Scrollbar(preview_wrap, orient="vertical")
        preview_text = tk.Text(
            preview_wrap,
            height=6,
            bg=self.colors["surface"],
            fg=self.colors["fg"],
            font=("Consolas", 10),
            yscrollcommand=preview_scroll.set,
            wrap="none",
        )
        preview_scroll.configure(command=preview_text.yview)
        preview_scroll.pack(side="right", fill="y")
        preview_text.pack(side="left", fill="both", expand=True)
        preview_text.tag_configure("match", background="#FEF08A", foreground=self.colors["fg"])
        preview_text.insert("1.0", "Select a result to preview it.\n")
        preview_text.configure(state="disabled")

        # Footer status strip (Dynamic Island)
        footer = ttk.Frame(tab_frame)
        footer.pack(side="bottom", fill="x", pady=(6, 0))
        status_label = ttk.Label(footer, text="Status: Idle", style="Status.TLabel")
        status_label.pack(fill="x")

        # Create per-tab state
        state = TabState(
            frame=tab_frame,
            status_label=status_label,
            mode=mode_var,
            dir_entry=dir_entry,
            include_entry=include_entry,
            exclude_entry=exclude_entry,
            max_mb_entry=max_mb_entry,
            depth_entry=depth_entry,
            skip_hidden_var=skip_hidden_var,
            respect_gitignore_var=respect_gitignore_var,
            text_group=text_group,
            search_entry=search_entry,
            filetype_combo=filetype_combo,
            chk_regex=chk_regex,
            chk_case=chk_case,
            chk_word=chk_word,
            context_lines_var=context_lines_var,
            first_match_per_file_var=first_match_per_file_var,
            use_ripgrep_var=use_ripgrep_var,
            file_group=file_group,
            fname_entry=fname_entry,
            fname_chk_regex=fname_chk_regex,
            fname_chk_case=fname_chk_case,
            fname_chk_word=fname_chk_word,
            content_filter_var=content_filter_var,
            content_entry=content_entry,
            content_chk_regex=content_chk_regex,
            content_chk_case=content_chk_case,
            content_chk_word=content_chk_word,
            folder_group=folder_group,
            folder_entry=folder_entry,
            folder_chk_regex=folder_chk_regex,
            folder_chk_case=folder_chk_case,
            folder_chk_word=folder_chk_word,
            folder_content_filter_var=folder_content_filter_var,
            folder_content_entry=folder_content_entry,
            folder_content_chk_regex=folder_content_chk_regex,
            folder_content_chk_case=folder_content_chk_case,
            folder_content_chk_word=folder_content_chk_word,
            result_tree=result_tree,
            log_text=log_text,
            preview_text=preview_text,
            btn_search=btn_search,
            btn_pause=btn_pause,
            btn_stop=btn_stop,
            processing_nb=processing_nb,
            processing_preview_tab=preview_tab,
            summary_label=summary_label,
            progress_bar=progress_bar,
            engine_label=engine_label,
            current_columns=columns_text
        )
        state.pause_event.set()

        # stash
        tab_id = self.notebook.tabs()[plus_index]
        self.tabs[tab_id] = state

        # Wire buttons with state
        btn_search.configure(command=lambda s=state: self.start_search_for_tab(s))
        btn_pause.configure(command=lambda s=state: self.toggle_pause_resume(s))
        btn_stop.configure(command=lambda s=state: self.stop_search(s))
        btn_clear_logs.configure(command=lambda s=state: self.clear_logs(s))
        state.result_tree.bind("<<TreeviewSelect>>", lambda _e, s=state: self._on_result_select(s))

        # More menu
        more_menu = tk.Menu(more_btn, tearoff=0)
        more_menu.add_command(label="Clear Results", command=lambda s=state: self.clear_results(s))
        more_menu.add_command(label="Export CSV", command=lambda s=state: self.export_csv(s))
        more_menu.add_separator()
        more_menu.add_command(label="Clear Logs", command=lambda s=state: self.clear_logs(s))
        more_menu.add_separator()
        more_menu.add_command(label="Toggle Logging", command=self._toggle_logging_from_menu)
        more_btn.configure(menu=more_menu)

        # Mode switch behavior
        def on_mode_change(*_):
            if state.outcome == "running" and state.mode.get() != state.active_mode:
                state.mode.set(state.active_mode)
                return
            if state.mode.get() == "Text":
                state.file_group.grid_remove()
                state.folder_group.grid_remove()
                state.text_group.grid()
                self._reconfigure_tree_for_mode(state, "Text")
            elif state.mode.get() == "File":
                state.text_group.grid_remove()
                state.folder_group.grid_remove()
                state.file_group.grid()
                self._reconfigure_tree_for_mode(state, "File")
            else:
                state.text_group.grid_remove()
                state.file_group.grid_remove()
                state.folder_group.grid()
                self._reconfigure_tree_for_mode(state, "Folder")
        mode_var.trace_add("write", on_mode_change)

        # Apply persisted defaults (if any)
        self._apply_settings_to_tab(state)
        self._toggle_content_controls(content_filter_var, content_entry, content_opts)
        self._toggle_content_controls(folder_content_filter_var, folder_content_entry, folder_content_opts)
        on_mode_change()

        # Initial button state
        self._set_search_controls(state, "idle")

        # Make columns expand nicely (favor input columns; keep labels compact)
        options.grid_columnconfigure(0, weight=0)
        options.grid_columnconfigure(1, weight=4)
        options.grid_columnconfigure(2, weight=0)
        options.grid_columnconfigure(3, weight=4)
        options.grid_columnconfigure(4, weight=0)
        options.grid_columnconfigure(5, weight=1)
        options.grid_columnconfigure(6, weight=0)
        options.grid_columnconfigure(7, weight=1)

        # Sub-frames: let their input columns expand
        for grp in (text_group, file_group, folder_group):
            for c in range(0, 8):
                try:
                    grp.grid_columnconfigure(c, weight=0)
                except Exception:
                    pass
            try:
                grp.grid_columnconfigure(1, weight=4)
                grp.grid_columnconfigure(2, weight=1)
                grp.grid_columnconfigure(3, weight=1)
                grp.grid_columnconfigure(5, weight=2)
            except Exception:
                pass

        self._ensure_plus_tab()
        self.notebook.select(tab_id)
        self.root.after(180, set_initial_split)

    # ---------- Helpers for UI ----------
    def _add_hover(self, btn: ttk.Button):
        # Styles intentionally remain stable on hover so colour communicates
        # application state, not pointer position.
        return

    def _set_search_controls(self, state: TabState, phase: str):
        """Apply one consistent visual and interactive state to search actions."""
        if phase == "running":
            state.btn_search.configure(state="disabled", style="Accent.TButton")
            state.btn_pause.configure(state="normal", text="Pause", style="Pause.TButton")
            state.btn_stop.configure(state="normal", text="Cancel", style="Danger.TButton")
        elif phase == "paused":
            state.btn_search.configure(state="disabled", style="Accent.TButton")
            state.btn_pause.configure(state="normal", text="Resume", style="Resume.TButton")
            state.btn_stop.configure(state="normal", text="Cancel", style="Danger.TButton")
        elif phase == "cancelling":
            state.btn_search.configure(state="disabled", style="Accent.TButton")
            state.btn_pause.configure(state="disabled", text="Pause", style="Pause.TButton")
            state.btn_stop.configure(state="disabled", text="Cancelling", style="Danger.TButton")
        else:
            state.btn_search.configure(state="normal", style="Accent.TButton")
            state.btn_pause.configure(state="disabled", text="Pause", style="Pause.TButton")
            state.btn_stop.configure(state="disabled", text="Cancel", style="Danger.TButton")

    def _pick_folder(self, entry: ttk.Entry):
        d = filedialog.askdirectory()
        if d:
            entry.delete(0, tk.END)
            entry.insert(0, d)

    def _build_highlight_regex(self, pattern: str, use_regex: bool, case: bool, whole: bool) -> re.Pattern | None:
        flags = 0 if case else re.IGNORECASE
        expr = pattern if use_regex else re.escape(pattern)
        if whole:
            expr = rf"\b(?:{expr})\b"
        try:
            return re.compile(expr, flags)
        except Exception:
            return None

    def _set_preview_text(self, state: TabState, text: str):
        try:
            state.preview_text.configure(state="normal")
            state.preview_text.delete("1.0", tk.END)
            state.preview_text.insert("1.0", text)
            state.preview_text.configure(state="disabled")
        except Exception:
            pass

    def _show_empty_results(self, state: TabState):
        try:
            if state.result_tree.get_children():
                return
            cols = list(state.result_tree["columns"])
            values = [""] * len(cols)
            mode = state.mode.get()
            if state.outcome == "completed":
                values[0] = "No matches found. Adjust the query or filters and try again."
            elif mode == "Text":
                values[0] = "No results yet. Enter a search string and click Search."
            elif mode == "File":
                values[0] = "No results yet. Enter a filename pattern and click Search."
            else:
                values[0] = "No results yet. Enter a folder name pattern and click Search."
            state.result_tree.insert("", "end", iid="__empty__", values=values, tags=("emptyrow",))
        except Exception:
            pass

    def _read_context_lines(self, path: str, center_line: int, context: int) -> list[tuple[int, str]]:
        start = max(1, center_line - context)
        end = center_line + context
        out: list[tuple[int, str]] = []
        try:
            with open(path, "r", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    if i < start:
                        continue
                    if i > end:
                        break
                    out.append((i, line.rstrip("\n")))
        except Exception as e:
            self._log_exception(f"Error previewing {path}", e)
        return out

    def _on_result_select(self, state: TabState):
        sel = state.result_tree.selection()
        if not sel:
            return
        vals = state.result_tree.item(sel[0], "values")
        if not vals:
            return

        mode = state.mode.get()
        if mode != "Text":
            fp = vals[0]
            self._set_preview_text(state, fp)
            try:
                state.processing_nb.select(state.processing_preview_tab)
            except Exception:
                pass
            return

        fp = vals[0]
        try:
            line_no = int(vals[1])
        except Exception:
            self._set_preview_text(state, fp)
            return

        context = 2
        try:
            context = int(state.context_lines_var.get())
        except Exception:
            context = 2

        lines = self._read_context_lines(fp, line_no, context)
        if not lines:
            self._set_preview_text(state, f"{fp}\n\n(No preview available.)\n")
            return

        pat = state.preview_highlight_re
        if pat is None:
            pat = self._build_highlight_regex(
                state.search_entry.get(),
                state.chk_regex.get(),
                state.chk_case.get(),
                state.chk_word.get(),
            )

        try:
            state.preview_text.configure(state="normal")
            state.preview_text.delete("1.0", tk.END)
            header = f"{fp}:{line_no}\n\n"
            state.preview_text.insert("1.0", header)

            display_line = 3  # 1=header, 2=blank, 3=first content line
            for i, text in lines:
                marker = ">" if i == line_no else " "
                prefix = f"{i:6d}{marker} "
                state.preview_text.insert(tk.END, prefix + text + "\n")

                if pat is not None:
                    try:
                        for m in pat.finditer(text):
                            start = f"{display_line}.{len(prefix) + m.start()}"
                            end = f"{display_line}.{len(prefix) + m.end()}"
                            state.preview_text.tag_add("match", start, end)
                    except Exception:
                        pass

                display_line += 1

            state.preview_text.see(f"{context + 3}.0")
            state.preview_text.configure(state="disabled")
        except Exception:
            self._set_preview_text(state, f"{fp}:{line_no}\n")
        finally:
            try:
                state.processing_nb.select(state.processing_preview_tab)
            except Exception:
                pass

    def _configure_tree_columns(self, tree: ttk.Treeview, mode: str):
        for col in tree["columns"]:
            tree.heading(col, text="")
            tree.column(col, width=0)
        if mode == "Text":
            tree["columns"] = ('filepath', 'line_no', 'line_text')
            tree.heading('filepath', text='File Path')
            tree.heading('line_no', text='Line')
            tree.heading('line_text', text='Line Text')
            tree.column('filepath', width=520, anchor="w")
            tree.column('line_no', width=60, anchor="e")
            tree.column('line_text', width=520, anchor="w")
        elif mode == "File":
            tree["columns"] = ('filepath', 'size', 'modified', 'matched')
            tree.heading('filepath', text='File Path')
            tree.heading('size', text='Size')
            tree.heading('modified', text='Modified')
            tree.heading('matched', text='Matched')
            tree.column('filepath', width=700, anchor="w")
            tree.column('size', width=100, anchor="e")
            tree.column('modified', width=160, anchor="center")
            tree.column('matched', width=80, anchor="center")
        else:
            tree["columns"] = ('folderpath', 'modified', 'matched', 'files')
            tree.heading('folderpath', text='Folder Path')
            tree.heading('modified', text='Modified')
            tree.heading('matched', text='Matched')
            tree.heading('files', text='Files')
            tree.column('folderpath', width=700, anchor="w")
            tree.column('modified', width=160, anchor="center")
            tree.column('matched', width=80, anchor="center")
            tree.column('files', width=80, anchor="e")

    def _apply_tree_stripes(self, tree: ttk.Treeview):
        tree.tag_configure("oddrow", background=self.colors["muted"])
        tree.tag_configure("evenrow", background=self.colors["surface"])
        tree.tag_configure("emptyrow", foreground=self.colors.get("subtle", "#64748B"))

    def _attach_tree_behaviors(self, tree: ttk.Treeview):
        # Context menu
        menu = tk.Menu(tree, tearoff=0)
        menu.add_command(label="Copy File Path", command=lambda: self._copy_filepath(tree))
        menu.add_command(label="Copy Line Text", command=lambda: self._copy_line_text(tree))
        menu.add_separator()
        menu.add_command(label="Open File", command=lambda: self._open_file(tree))
        menu.add_command(label="Open Directory", command=lambda: self._open_directory(tree))

        def show_menu(e):
            iid = tree.identify_row(e.y)
            if iid:
                tree.selection_set(iid)
                menu.tk_popup(e.x_root, e.y_root)
        tree.bind("<Button-3>", show_menu)
        tree.bind("<Double-1>", lambda _event: self._open_file(tree))

    def _toggle_content_controls(self, flag_var, entry, opts_frame):
        if flag_var.get():
            entry.configure(state="normal")
            for c in opts_frame.winfo_children():
                c.configure(state="normal")
        else:
            entry.delete(0, tk.END)
            entry.configure(state="disabled")
            for c in opts_frame.winfo_children():
                c.configure(state="disabled")

    def _reconfigure_tree_for_mode(self, state: TabState, mode: str):
        state.result_tree.delete(*state.result_tree.get_children())
        self._configure_tree_columns(state.result_tree, mode)
        state.current_columns = tuple(state.result_tree["columns"])
        state.matches_found = 0
        state.files_scanned = 0
        state.status_label.configure(text="Status: Idle")
        try:
            state.summary_label.configure(text="Ready.")
        except Exception:
            pass
        state.preview_highlight_re = None
        self._set_preview_text(state, "Select a result to preview it.\n")
        self._show_empty_results(state)

    # ---------- Actions ----------
    def start_search_for_tab(self, state: TabState):
        directory = state.dir_entry.get().strip()
        include_globs = [g.strip() for g in state.include_entry.get().split(";") if g.strip()]
        exclude_globs = [g.strip() for g in state.exclude_entry.get().split(";") if g.strip()]
        try:
            max_mb = float(state.max_mb_entry.get().strip() or "0")
        except ValueError:
            max_mb = 0.0
        depth_limit = state.depth_entry.get().strip()
        try:
            depth_limit = int(depth_limit) if depth_limit else None
        except ValueError:
            depth_limit = None

        skip_hidden = state.skip_hidden_var.get()
        respect_gitignore = state.respect_gitignore_var.get()

        if not directory:
            messagebox.showerror("Input Error", "Please select a directory.")
            return
        if not os.path.isdir(directory):
            messagebox.showerror("Input Error", "The selected directory does not exist or is not accessible.")
            return

        # Mode validation
        mode = state.mode.get()
        state.active_mode = mode
        if mode == "Text":
            pattern = state.search_entry.get()
            if not pattern:
                messagebox.showerror("Input Error", "Please enter a search string.")
                return
        elif mode == "File":
            fname_pat = state.fname_entry.get().strip()
            if not fname_pat:
                messagebox.showerror("Input Error", "Please enter a filename pattern.")
                return
            if state.content_filter_var.get() and not state.content_entry.get():
                messagebox.showerror("Input Error", "Please enter a content pattern for content filter.")
                return
        else:
            folder_pat = state.folder_entry.get().strip()
            if not folder_pat:
                messagebox.showerror("Input Error", "Please enter a folder name pattern.")
                return
            if state.folder_content_filter_var.get() and not state.folder_content_entry.get():
                messagebox.showerror("Input Error", "Please enter a content pattern for folder content filter.")
                return

        # Reset runtime
        state.stop_event = threading.Event()
        state.pause_event.set()
        state.result_q = queue.Queue()
        state.log_q = queue.Queue()
        state.files_scanned = 0
        state.matches_found = 0
        state.start_ts = time.time()
        state.paused_at = 0.0
        state.total_paused_sec = 0.0
        state.paused_files_snapshot = 0
        state.paused_matches_snapshot = 0
        state.outcome = "running"
        state.last_progress_log_ts = 0.0
        state.result_tree.delete(*state.result_tree.get_children())
        state.log_text.delete("1.0", tk.END)
        self._set_preview_text(state, "Searching…\n")
        state.status_label.config(text="Status: Searching…", foreground=self.colors["accent"])
        try:
            state.progress_bar.start(12)
            engine = "RIPGREP" if mode == "Text" and state.use_ripgrep_var.get() and self._rg_path else "PYTHON"
            state.engine_label.configure(text=f"ENGINE  {engine}", style="Engine.TLabel")
        except Exception:
            pass
        self._set_search_controls(state, "running")

        # Persist defaults
        self._update_settings_from_tab(state)
        self._save_settings()

        # Spawn worker
        if mode == "Text":
            state.preview_highlight_re = self._build_highlight_regex(
                state.search_entry.get(),
                state.chk_regex.get(),
                state.chk_case.get(),
                state.chk_word.get(),
            )
            gitignore_rules = load_gitignore_rules(directory) if respect_gitignore else []
            args = (
                state, directory, include_globs, exclude_globs, max_mb, depth_limit, skip_hidden, respect_gitignore, gitignore_rules,
                state.use_ripgrep_var.get(), state.first_match_per_file_var.get(),
                state.search_entry.get(),
                state.chk_regex.get(), state.chk_case.get(), state.chk_word.get(),
                state.filetype_combo.get()
            )
            worker = threading.Thread(target=self._run_worker, args=(state, self._worker_text, args), daemon=True)
        elif mode == "File":
            gitignore_rules = load_gitignore_rules(directory) if respect_gitignore else []
            args = (
                state, directory, include_globs, exclude_globs, max_mb, depth_limit, skip_hidden, gitignore_rules,
                state.fname_entry.get(), state.fname_chk_regex.get(), state.fname_chk_case.get(), state.fname_chk_word.get(),
                state.content_filter_var.get(), state.content_entry.get(),
                state.content_chk_regex.get(), state.content_chk_case.get(), state.content_chk_word.get()
            )
            worker = threading.Thread(target=self._run_worker, args=(state, self._worker_file, args), daemon=True)
        else:
            gitignore_rules = load_gitignore_rules(directory) if respect_gitignore else []
            args = (
                state, directory, include_globs, exclude_globs, max_mb, depth_limit, skip_hidden, gitignore_rules,
                state.folder_entry.get(), state.folder_chk_regex.get(), state.folder_chk_case.get(), state.folder_chk_word.get(),
                state.folder_content_filter_var.get(), state.folder_content_entry.get(),
                state.folder_content_chk_regex.get(), state.folder_content_chk_case.get(), state.folder_content_chk_word.get(),
            )
            worker = threading.Thread(target=self._run_worker, args=(state, self._worker_folder, args), daemon=True)

        worker.start()
        self._pump_queues(state)

    def pause_search(self, state: TabState):
        if not state.pause_event.is_set() or state.outcome != "running":
            return
        state.pause_event.clear()
        state.paused_at = time.time()
        # Freeze visible metrics immediately. A worker may have crossed one
        # cooperative checkpoint, but that in-flight work must not make the
        # paused UI appear active.
        state.paused_files_snapshot = state.files_scanned
        state.paused_matches_snapshot = state.matches_found
        state.progress_bar.stop()
        state.status_label.config(text="Status: Paused", foreground=self.colors["warn"])
        state.log_q.put("Paused.\n")
        self._set_search_controls(state, "paused")

    def resume_search(self, state: TabState):
        if state.pause_event.is_set() or state.outcome != "running":
            return
        if state.paused_at > 0:
            state.total_paused_sec += max(0.0, time.time() - state.paused_at)
            state.paused_at = 0.0
        state.pause_event.set()
        state.progress_bar.start(12)
        state.status_label.config(text="Status: Running…", foreground=self.colors["success"])
        state.log_q.put("Resumed.\n")
        self._set_search_controls(state, "running")

    def toggle_pause_resume(self, state: TabState):
        if state.stop_event.is_set():
            return
        if state.pause_event.is_set():
            self.pause_search(state)
        else:
            self.resume_search(state)

    def stop_search(self, state: TabState):
        state.outcome = "cancelled"
        state.stop_event.set()
        state.progress_bar.stop()
        state.status_label.config(text="Status: Cancelling…", foreground=self.colors["danger"])
        state.log_q.put("Cancellation requested…\n")
        self._set_search_controls(state, "cancelling")

    def clear_results(self, state: TabState):
        state.result_tree.delete(*state.result_tree.get_children())
        if state.outcome == "running":
            self._set_preview_text(state, "Searching…\n")
            state.log_q.put("Visible results cleared; search is still running.\n")
            return
        state.status_label.config(text="Status: Cleared → Idle", foreground=self.colors["fg"])
        self._set_preview_text(state, "Select a result to preview it.\n")
        self._show_empty_results(state)
        state.log_q.put("Cleared results.\n")
        state.files_scanned = 0
        state.matches_found = 0
        state.paused_at = 0.0
        state.total_paused_sec = 0.0
        state.paused_files_snapshot = 0
        state.paused_matches_snapshot = 0
        state.outcome = "idle"
        try:
            state.progress_bar.stop()
            state.engine_label.configure(text="ENGINE  READY", style="Engine.TLabel")
        except Exception:
            pass
        self._set_search_controls(state, "idle")

    def clear_logs(self, state: TabState):
        try:
            state.log_text.delete("1.0", tk.END)
        except Exception:
            pass

    def export_csv(self, state: TabState):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[('CSV files', '*.csv')])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            # headers based on current columns
            headers = []
            for c in state.current_columns:
                if c == "filepath": headers.append("File Path")
                elif c == "folderpath": headers.append("Folder Path")
                elif c == "line_no": headers.append("Line")
                elif c == "line_text": headers.append("Line Text")
                elif c == "size": headers.append("Size")
                elif c == "modified": headers.append("Modified")
                elif c == "matched": headers.append("Matched")
                elif c == "files": headers.append("Files")
                else: headers.append(c)
            w.writerow(headers)
            for iid in state.result_tree.get_children():
                if iid == "__empty__":
                    continue
                w.writerow(state.result_tree.item(iid)['values'])
        state.status_label.config(text=f"Saved CSV → {path}", foreground=self.colors["fg"])

    # ---------- Queue pump ----------
    def _pump_queues(self, state: TabState):
        if state.closed:
            return
        drained = False

        # Smaller batches keep resizing, scrolling, and cancellation responsive
        # even when a fast rg search produces thousands of matches at once.
        max_results_per_tick = 300
        max_logs_per_tick = 100

        # On stop/cancel, always flush queued items even when the search was paused.
        if state.pause_event.is_set() or state.stop_event.is_set():
            idx = len(state.result_tree.get_children())
            if "__empty__" in state.result_tree.get_children():
                try:
                    state.result_tree.delete("__empty__")
                except Exception:
                    pass
                idx = len(state.result_tree.get_children())
            n = 0
            while n < max_results_per_tick and not state.result_q.empty():
                drained = True
                try:
                    values = state.result_q.get_nowait()
                except queue.Empty:
                    break
                tag = "oddrow" if idx % 2 else "evenrow"
                state.result_tree.insert("", "end", values=values, tags=(tag,))
                idx += 1
                n += 1

            n = 0
            while n < max_logs_per_tick and not state.log_q.empty():
                drained = True
                try:
                    msg = state.log_q.get_nowait()
                except queue.Empty:
                    break
                state.log_text.insert(tk.END, msg)
                n += 1
            if drained:
                state.log_text.see(tk.END)

        # Update status metrics
        paused = not state.pause_event.is_set() and state.paused_at > 0
        metric_ts = state.paused_at if paused else time.time()
        elapsed = max(0.0, metric_ts - state.start_ts - state.total_paused_sec)
        display_files = state.paused_files_snapshot if paused else state.files_scanned
        display_matches = state.paused_matches_snapshot if paused else state.matches_found
        fps = (display_files / elapsed) if elapsed > 0 else 0.0
        mode = state.mode.get()
        scanned_label = "Folders" if mode == "Folder" else "Files"
        match_label = "Matches" if mode == "Text" else ("Folders matched" if mode == "Folder" else "Files matched")
        rate_label = "folders/s" if mode == "Folder" else "files/s"
        summary = f"{scanned_label}: {display_files}   {match_label}: {display_matches}   Elapsed: {elapsed:.1f}s   {fps:.1f} {rate_label}"
        label = (f"Status: {'Paused' if not state.pause_event.is_set() else 'Running'} | "
                 f"{scanned_label}: {display_files} | "
                 f"{match_label}: {display_matches} | "
                 f"Elapsed: {elapsed:.1f}s | {fps:.1f} {rate_label}")
        try:
            state.summary_label.configure(text=summary)
        except Exception:
            pass
        state.status_label.config(text=label,
                                  foreground=self.colors["warn"] if not state.pause_event.is_set() else self.colors["success"])

        # Continue pumping until fully stopped and queues drained
        has_backlog = (not state.result_q.empty()) or (not state.log_q.empty())
        if not state.stop_event.is_set() or drained or has_backlog:
            self.root.after(8 if has_backlog else 120, lambda: self._pump_queues(state))
        else:
            try:
                state.progress_bar.stop()
            except Exception:
                pass
            if state.outcome == "cancelled":
                final_text, final_color = "Status: Cancelled", self.colors["danger"]
                try:
                    state.engine_label.configure(text="SEARCH  CANCELLED", style="Engine.TLabel")
                except Exception:
                    pass
            elif state.outcome == "failed":
                final_text, final_color = "Status: Failed — see Activity", self.colors["danger"]
                try:
                    state.engine_label.configure(text="SEARCH  FAILED", style="Engine.TLabel")
                except Exception:
                    pass
            else:
                state.outcome = "completed"
                final_text, final_color = "Status: Completed", self.colors["success"]
                try:
                    state.engine_label.configure(text="SEARCH  COMPLETE", style="Success.TLabel")
                except Exception:
                    pass
            if state.matches_found == 0:
                self._show_empty_results(state)
            state.status_label.config(text=final_text, foreground=final_color)
            self._set_search_controls(state, "idle")

    # ---------- Workers ----------
    def _run_worker(self, state: TabState, worker_fn, args):
        """Guarantee that unexpected worker failures always release the UI."""
        try:
            worker_fn(*args)
        except Exception as exc:
            if state.outcome != "cancelled":
                state.outcome = "failed"
            state.log_q.put(f"Search failed: {exc}\n")
            self._log_exception("Unhandled search worker error", exc)
            state.stop_event.set()

    def _queue_scan_progress(self, state: TabState, root: str):
        """Keep activity useful without flooding Tk with one log entry per directory."""
        now = time.monotonic()
        if now - state.last_progress_log_ts >= 0.35:
            state.last_progress_log_ts = now
            state.log_q.put(f"Scanning: {root}\n")

    def _walk_with_depth(self, base_dir: str, depth_limit, *, skip_hidden: bool, gitignore_rules: list[tuple[str, bool, bool]]):
        base_dir = os.path.abspath(base_dir)
        base_depth = base_dir.rstrip(os.sep).count(os.sep)
        for root, dirs, files in os.walk(base_dir):
            if depth_limit is not None:
                cur_depth = root.rstrip(os.sep).count(os.sep) - base_depth
                if cur_depth >= depth_limit:
                    dirs[:] = []

            if skip_hidden:
                dirs[:] = [d for d in dirs if not is_hidden_path(os.path.join(root, d))]
                files = [f for f in files if not is_hidden_path(os.path.join(root, f))]

            if gitignore_rules:
                kept_dirs = []
                for d in dirs:
                    rel = os.path.relpath(os.path.join(root, d), base_dir).replace(os.sep, "/")
                    if not gitignore_ignored(rel, is_dir=True, rules=gitignore_rules):
                        kept_dirs.append(d)
                dirs[:] = kept_dirs

                kept_files = []
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), base_dir).replace(os.sep, "/")
                    if not gitignore_ignored(rel, is_dir=False, rules=gitignore_rules):
                        kept_files.append(f)
                files = kept_files

            yield root, dirs, files

    def _worker_text(self, state: TabState, directory, include_globs, exclude_globs, max_mb, depth_limit, skip_hidden, respect_gitignore, gitignore_rules,
                     use_ripgrep, first_match_per_file, pattern, use_regex, case, whole, filetype):
        if use_ripgrep and self._rg_path:
            self._worker_text_ripgrep(
                state=state,
                directory=directory,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                max_mb=max_mb,
                depth_limit=depth_limit,
                skip_hidden=skip_hidden,
                respect_gitignore=respect_gitignore,
                first_match_per_file=first_match_per_file,
                pattern=pattern,
                use_regex=use_regex,
                case=case,
                whole=whole,
                filetype=filetype,
            )
            return
        elif use_ripgrep and not self._rg_path:
            state.log_q.put("ripgrep (rg) not found; falling back to Python scanner.\n")

        # Prep matcher
        flags = 0 if case else re.IGNORECASE
        if use_regex:
            try:
                pat = re.compile(pattern if not whole else rf"\b{pattern}\b", flags)
                def is_match(line): return pat.search(line) is not None
            except re.error as e:
                state.log_q.put(f"Invalid regex: {e}\n")
                state.outcome = "failed"
                state.stop_event.set()
                return
        else:
            needle = pattern if case else pattern.lower()
            def is_match(line):
                hay = line if case else line.lower()
                if whole:
                    return re.search(rf"\b{re.escape(needle)}\b", hay) is not None
                return needle in hay

        for root, dirs, files in self._walk_with_depth(directory, depth_limit, skip_hidden=skip_hidden, gitignore_rules=gitignore_rules):
            if state.stop_event.is_set(): break
            # Apply folder excludes
            if exclude_globs:
                dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, g) for g in exclude_globs)]

            self._queue_scan_progress(state, root)

            for fname in files:
                if state.stop_event.is_set(): break
                # pause loop
                while not state.pause_event.is_set():
                    if state.stop_event.is_set(): break
                    time.sleep(0.05)

                # File type filter
                if filetype != "All" and not fname.lower().endswith(filetype.lower()):
                    continue
                # include/exclude globs
                if include_globs and not any(fnmatch.fnmatch(fname, g) for g in include_globs):
                    continue
                if exclude_globs and any(fnmatch.fnmatch(fname, g) for g in exclude_globs):
                    continue

                fpath = os.path.join(root, fname)
                try:
                    if max_mb > 0 and (os.path.getsize(fpath) > max_mb * 1024 * 1024):
                        continue
                except Exception:
                    continue

                state.files_scanned += 1

                # Binary guard
                if is_binary_quick(fpath):
                    continue

                try:
                    matched_this_file = False
                    with open(fpath, "r", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if state.stop_event.is_set(): break
                            while not state.pause_event.is_set():
                                if state.stop_event.is_set(): break
                                time.sleep(0.01)
                            if is_match(line):
                                state.matches_found += 1
                                state.result_q.put((fpath, i, line.rstrip("\n")))
                                matched_this_file = True
                                if first_match_per_file:
                                    break
                    if first_match_per_file and matched_this_file:
                        continue
                except Exception as e:
                    self._log_exception(f"Error reading {fpath}", e)

        if state.outcome == "running":
            state.outcome = "completed"
        state.stop_event.set()

    def _worker_text_ripgrep(
        self,
        *,
        state: TabState,
        directory: str,
        include_globs: list[str],
        exclude_globs: list[str],
        max_mb: float,
        depth_limit,
        skip_hidden: bool,
        respect_gitignore: bool,
        first_match_per_file: bool,
        pattern: str,
        use_regex: bool,
        case: bool,
        whole: bool,
        filetype: str,
    ):
        state.log_q.put("Using ripgrep (rg) backend.\n")

        cmd: list[str] = [self._rg_path, "--json"]
        if not use_regex:
            cmd.append("-F")
        if not case:
            cmd.append("-i")
        if whole:
            cmd.append("-w")
        if first_match_per_file:
            cmd.extend(["-m", "1"])
        if depth_limit is not None:
            cmd.extend(["--max-depth", str(depth_limit)])
        if max_mb and max_mb > 0:
            cmd.extend(["--max-filesize", f"{max_mb:g}M"])
        if not skip_hidden:
            cmd.append("--hidden")
        if not respect_gitignore:
            cmd.append("--no-ignore")

        if filetype and filetype != "All":
            cmd.extend(["--glob", f"*{filetype}"])

        for g in include_globs:
            cmd.extend(["--glob", g])

        for g in exclude_globs:
            if not g:
                continue
            has_wildcards = any(ch in g for ch in ("*", "?", "[")) or ("/" in g) or ("\\" in g)
            if has_wildcards:
                cmd.extend(["--glob", f"!{g}"])
                continue
            # treat plain names as potential directories and files
            cmd.extend(["--glob", f"!{g}"])
            cmd.extend(["--glob", f"!**/{g}/**"])

        cmd.extend(["--", pattern, directory])

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            state.log_q.put(f"Failed to start rg: {e}\n")
            state.outcome = "failed"
            state.stop_event.set()
            return

        files_searched = None
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                if state.stop_event.is_set():
                    break
                while not state.pause_event.is_set():
                    if state.stop_event.is_set():
                        break
                    time.sleep(0.05)

                try:
                    obj = json.loads(raw)
                except Exception:
                    continue

                t = obj.get("type")
                if t == "match":
                    data = obj.get("data", {})
                    path = data.get("path", {}).get("text")
                    line_no = data.get("line_number")
                    line_text = (data.get("lines", {}) or {}).get("text", "").rstrip("\n")
                    if path is None or line_no is None:
                        continue
                    state.matches_found += 1
                    state.result_q.put((path, int(line_no), line_text))
                elif t == "summary":
                    stats = (obj.get("data", {}) or {}).get("stats", {}) or {}
                    files_searched = stats.get("files_searched")

            if state.stop_event.is_set() and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        finally:
            try:
                out, err = proc.communicate(timeout=2)
                if err:
                    # rg prints some errors to stderr even with exit code 0 (e.g., permission issues)
                    state.log_q.put(err)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        try:
            if isinstance(files_searched, int):
                state.files_scanned = files_searched
        except Exception:
            pass

        if state.outcome == "running":
            state.outcome = "completed"
        state.stop_event.set()

    def _worker_file(self, state: TabState, directory, include_globs, exclude_globs, max_mb, depth_limit, skip_hidden, gitignore_rules,
                     fname_pat, fname_regex, fname_case, fname_whole,
                     content_filter_on, content_pat, content_regex, content_case, content_whole):
        # Filename matcher
        if fname_regex:
            try:
                fname_flags = 0 if fname_case else re.IGNORECASE
                rname = re.compile(fname_pat if not fname_whole else rf"\b{fname_pat}\b", fname_flags)
                def match_name(name): return rname.search(name) is not None
            except re.error as e:
                state.log_q.put(f"Invalid filename regex: {e}\n")
                state.outcome = "failed"
                state.stop_event.set()
                return
        else:
            needle = fname_pat if fname_case else fname_pat.lower()
            def match_name(name):
                hay = name if fname_case else name.lower()
                if fname_whole:
                    return re.search(rf"\b{re.escape(needle)}\b", hay) is not None
                return needle in hay

        # Content matcher (optional)
        if content_filter_on:
            if content_regex:
                try:
                    cflags = 0 if content_case else re.IGNORECASE
                    rc = re.compile(content_pat if not content_whole else rf"\b{content_pat}\b", cflags)
                    def match_content(line): return rc.search(line) is not None
                except re.error as e:
                    state.log_q.put(f"Invalid content regex: {e}\n")
                    state.outcome = "failed"
                    state.stop_event.set()
                    return
            else:
                needlec = content_pat if content_case else content_pat.lower()
                def match_content(line):
                    hay = line if content_case else line.lower()
                    if content_whole:
                        return re.search(rf"\b{re.escape(needlec)}\b", hay) is not None
                    return needlec in hay
        else:
            def match_content(_): return True  # bypass

        for root, dirs, files in self._walk_with_depth(directory, depth_limit, skip_hidden=skip_hidden, gitignore_rules=gitignore_rules):
            if state.stop_event.is_set(): break
            # Apply folder excludes
            if exclude_globs:
                dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, g) for g in exclude_globs)]

            self._queue_scan_progress(state, root)

            for fname in files:
                if state.stop_event.is_set(): break
                while not state.pause_event.is_set():
                    if state.stop_event.is_set(): break
                    time.sleep(0.05)

                # include/exclude filename globs
                if include_globs and not any(fnmatch.fnmatch(fname, g) for g in include_globs):
                    continue
                if exclude_globs and any(fnmatch.fnmatch(fname, g) for g in exclude_globs):
                    continue

                fpath = os.path.join(root, fname)

                # size cap
                try:
                    size = os.path.getsize(fpath)
                    if max_mb > 0 and size > max_mb * 1024 * 1024:
                        continue
                except Exception:
                    continue

                state.files_scanned += 1

                # filename pattern match
                if not match_name(fname):
                    continue

                # content filter if requested
                content_matched = False
                if content_filter_on:
                    if is_binary_quick(fpath):
                        continue
                    try:
                        with open(fpath, "r", errors="ignore") as f:
                            for line in f:
                                if state.stop_event.is_set(): break
                                while not state.pause_event.is_set():
                                    if state.stop_event.is_set(): break
                                    time.sleep(0.01)
                                if match_content(line):
                                    content_matched = True
                                    break
                    except Exception as e:
                        self._log_exception(f"Error reading {fpath}", e)
                        continue
                    if not content_matched:
                        continue

                # Passed
                state.matches_found += 1
                try:
                    mtime = os.path.getmtime(fpath)
                except Exception:
                    mtime = time.time()
                state.result_q.put((fpath, fmt_size(size), fmt_time(mtime), "Y" if content_filter_on else "—"))

        if state.outcome == "running":
            state.outcome = "completed"
        state.stop_event.set()

    def _worker_folder(
        self,
        state: TabState,
        directory,
        include_globs,
        exclude_globs,
        max_mb,
        depth_limit,
        skip_hidden,
        gitignore_rules,
        folder_pat,
        folder_regex,
        folder_case,
        folder_whole,
        content_filter_on,
        content_pat,
        content_regex,
        content_case,
        content_whole,
    ):
        base_dir = os.path.abspath(directory)

        # Folder name matcher
        if folder_regex:
            try:
                folder_flags = 0 if folder_case else re.IGNORECASE
                rfolder = re.compile(folder_pat if not folder_whole else rf"\b{folder_pat}\b", folder_flags)

                def match_folder(name): return rfolder.search(name) is not None
            except re.error as e:
                state.log_q.put(f"Invalid folder regex: {e}\n")
                state.outcome = "failed"
                state.stop_event.set()
                return
        else:
            needle = folder_pat if folder_case else folder_pat.lower()

            def match_folder(name):
                hay = name if folder_case else name.lower()
                if folder_whole:
                    return re.search(rf"\b{re.escape(needle)}\b", hay) is not None
                return needle in hay

        # Content matcher (optional)
        if content_filter_on:
            if content_regex:
                try:
                    cflags = 0 if content_case else re.IGNORECASE
                    rc = re.compile(content_pat if not content_whole else rf"\b{content_pat}\b", cflags)

                    def match_content(line): return rc.search(line) is not None
                except re.error as e:
                    state.log_q.put(f"Invalid content regex: {e}\n")
                    state.outcome = "failed"
                    state.stop_event.set()
                    return
            else:
                needlec = content_pat if content_case else content_pat.lower()

                def match_content(line):
                    hay = line if content_case else line.lower()
                    if content_whole:
                        return re.search(rf"\b{re.escape(needlec)}\b", hay) is not None
                    return needlec in hay
        else:

            def match_content(_): return True  # bypass

        def folder_content_matches(folder_path: str) -> tuple[bool, int]:
            matched = False
            files_seen = 0
            try:
                for entry in os.scandir(folder_path):
                    if state.stop_event.is_set():
                        break
                    while not state.pause_event.is_set():
                        if state.stop_event.is_set():
                            break
                        time.sleep(0.05)

                    if not entry.is_file():
                        continue

                    if skip_hidden and is_hidden_path(entry.path):
                        continue

                    fname = entry.name
                    if include_globs and not any(fnmatch.fnmatch(fname, g) for g in include_globs):
                        continue
                    if exclude_globs and any(fnmatch.fnmatch(fname, g) for g in exclude_globs):
                        continue

                    if gitignore_rules:
                        rel = os.path.relpath(entry.path, base_dir).replace(os.sep, "/")
                        if gitignore_ignored(rel, is_dir=False, rules=gitignore_rules):
                            continue

                    try:
                        size = entry.stat().st_size
                        if max_mb > 0 and size > max_mb * 1024 * 1024:
                            continue
                    except Exception:
                        continue

                    files_seen += 1
                    if not content_filter_on:
                        continue

                    if is_binary_quick(entry.path):
                        continue
                    try:
                        with open(entry.path, "r", errors="ignore") as f:
                            for line in f:
                                if state.stop_event.is_set():
                                    break
                                while not state.pause_event.is_set():
                                    if state.stop_event.is_set():
                                        break
                                    time.sleep(0.01)
                                if match_content(line):
                                    matched = True
                                    return True, files_seen
                    except Exception as e:
                        self._log_exception(f"Error reading {entry.path}", e)
                        continue
            except Exception:
                return False, 0
            return matched, files_seen

        for root, dirs, files in self._walk_with_depth(directory, depth_limit, skip_hidden=skip_hidden, gitignore_rules=gitignore_rules):
            if state.stop_event.is_set():
                break

            if exclude_globs:
                dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, g) for g in exclude_globs)]

            self._queue_scan_progress(state, root)

            for dname in list(dirs):
                if state.stop_event.is_set():
                    break
                while not state.pause_event.is_set():
                    if state.stop_event.is_set():
                        break
                    time.sleep(0.05)

                state.files_scanned += 1
                if not match_folder(dname):
                    continue
                folder_path = os.path.join(root, dname)
                matched, files_seen = folder_content_matches(folder_path)
                if content_filter_on and not matched:
                    continue

                state.matches_found += 1
                try:
                    mtime = os.path.getmtime(folder_path)
                except Exception:
                    mtime = time.time()
                state.result_q.put((folder_path, fmt_time(mtime), "Y" if content_filter_on else "—", str(files_seen)))

        if state.outcome == "running":
            state.outcome = "completed"
        state.stop_event.set()

    # ---------- Tree actions ----------
    def _copy_filepath(self, tree: ttk.Treeview):
        sel = tree.selection()
        if not sel:
            return
        fp = tree.item(sel[0], "values")[0]
        self.root.clipboard_clear()
        self.root.clipboard_append(fp)
        self.root.update()
        messagebox.showinfo("Copied", fp)

    def _copy_line_text(self, tree: ttk.Treeview):
        sel = tree.selection()
        if not sel:
            return
        vals = tree.item(sel[0], "values")
        if len(vals) >= 3:
            txt = vals[2]
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
            self.root.update()
            messagebox.showinfo("Copied", "Line text copied.")

    def _open_file_at_line(self, fp: str, line_no: int):
        # Best-effort editor integrations on Windows/macOS/Linux
        try:
            if shutil.which("code"):
                subprocess.Popen(["code", "-g", f"{fp}:{line_no}"])
                return
        except Exception:
            pass
        try:
            npp = shutil.which("notepad++.exe") or shutil.which("notepad++")
            if npp:
                subprocess.Popen([npp, f"-n{line_no}", fp])
                return
        except Exception:
            pass
        try:
            if shutil.which("gvim"):
                subprocess.Popen(["gvim", f"+{line_no}", fp])
                return
        except Exception:
            pass
        default_open(fp)

    def _open_file(self, tree: ttk.Treeview):
        sel = tree.selection()
        if not sel or sel[0] == "__empty__":
            return
        vals = tree.item(sel[0], "values")
        if not vals or not vals[0]:
            return
        fp = vals[0]
        try:
            line_no = int(vals[1])
            self._open_file_at_line(fp, line_no)
        except Exception:
            default_open(fp)

    def _open_directory(self, tree: ttk.Treeview):
        sel = tree.selection()
        if not sel:
            return
        fp = tree.item(sel[0], "values")[0]
        target = fp if os.path.isdir(fp) else os.path.dirname(fp)
        default_open(target)


# ---------- Main ----------
def main() -> None:
    root = tk.Tk()
    Grepper(root)
    root.mainloop()


if __name__ == "__main__":
    main()
