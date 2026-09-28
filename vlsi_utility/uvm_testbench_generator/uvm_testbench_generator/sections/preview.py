from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..utils.generator import generate_files
from ..utils.state import StateManager
from ..utils.ui import CodeNotebook, ScrollableFrame, section_title


class PreviewPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.content = scroller.content
        self.state = StateManager.get_instance()

        self.use_overrides = tk.BooleanVar(value=bool(self.state.get("custom_files_enabled", True)))

        self._file_cache: dict[str, str] = {}
        self._files: list[str] = []
        self._iid_to_name: dict[str, str] = {}
        self.file_filter = tk.StringVar()

        self.build_ui()
        self.refresh_preview()

    def build_ui(self) -> None:
        root = self.content
        root.columnconfigure(0, weight=1)

        row = 0
        section_title(root, "Full Testbench Preview").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(actions, text="Refresh", command=self.refresh_preview).pack(side="left")
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(actions, text="Save Tab Override", command=self.save_current_override).pack(side="left")
        ttk.Button(actions, text="Save All Overrides", command=self.save_all_overrides).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Revert Tab", command=self.revert_current_override).pack(side="left", padx=(16, 0))
        ttk.Button(actions, text="Revert All", command=self.revert_all_overrides).pack(side="left", padx=(8, 0))
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(actions, text="Export Tab", command=self.export_current_tab).pack(side="left")
        ttk.Button(actions, text="Copy Tab", command=self.copy_current_tab).pack(side="left", padx=(8, 0))
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Checkbutton(
            actions,
            text="Use saved overrides during generation",
            variable=self.use_overrides,
            command=self._on_use_overrides_toggle,
        ).pack(side="left")
        row += 1

        preview_frame = ttk.LabelFrame(root, text="Files (Editable)")
        preview_frame.grid(row=row, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)

        panes = ttk.PanedWindow(preview_frame, orient="horizontal")
        panes.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=4)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        ttk.Label(left, text="Files").grid(row=0, column=0, sticky="w")
        self.file_count = ttk.Label(left, text="0", foreground="#9aa3b2")
        self.file_count.grid(row=0, column=0, sticky="e")

        filter_entry = ttk.Entry(left, textvariable=self.file_filter)
        filter_entry.grid(row=1, column=0, sticky="ew", pady=(6, 6))
        filter_entry.bind("<KeyRelease>", lambda _e: self._refresh_file_list())

        tree_frame = ttk.Frame(left)
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.file_tree = ttk.Treeview(tree_frame, columns=("File",), show="headings", height=16)
        self.file_tree.heading("File", text="File")
        self.file_tree.column("File", width=220, stretch=True, anchor="w")
        y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=y.set)
        self.file_tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")

        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_tree_select)

        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.notebook = CodeNotebook(right, height=32)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.notebook.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

    def _on_use_overrides_toggle(self) -> None:
        self.state.set("custom_files_enabled", bool(self.use_overrides.get()))
        self.refresh_preview()

    def _refresh_file_list(self) -> None:
        flt = (self.file_filter.get() or "").strip().lower()
        self.file_tree.delete(*self.file_tree.get_children())
        self._iid_to_name = {}

        shown = 0
        for idx, name in enumerate(self._files):
            if flt and flt not in name.lower():
                continue
            iid = f"f{idx}"
            self._iid_to_name[iid] = name
            self.file_tree.insert("", "end", iid=iid, values=(name,))
            shown += 1

        self.file_count.config(text=f"{shown}/{len(self._files)}")

    def _on_file_tree_select(self, _event=None) -> None:
        sel = self.file_tree.selection()
        if not sel:
            return
        name = self._iid_to_name.get(str(sel[0]))
        if not name:
            return
        self.notebook.select_tab(name)

    def _on_notebook_tab_changed(self, _event=None) -> None:
        name = self.notebook.current_tab_name()
        if not name or name == "WARNINGS":
            return
        # Ensure tree selection tracks tab selection even if tab text is truncated in the UI.
        for iid, fname in self._iid_to_name.items():
            if fname == name:
                try:
                    self.file_tree.selection_set(iid)
                    self.file_tree.see(iid)
                except Exception:
                    pass
                break

    def refresh_preview(self) -> None:
        previous = self.notebook.current_tab_name()
        data = self.state.get_all()
        try:
            files, warnings = generate_files(data)
        except Exception as exc:
            files = {Path("PREVIEW_ERROR.txt"): f"Preview failed:\n{exc}\n"}
            warnings = []

        tabs: list[str] = []
        if warnings:
            tabs.append("WARNINGS")
        file_paths = sorted(files.keys(), key=lambda p: str(p))
        tabs.extend([p.as_posix() for p in file_paths])
        self.notebook.set_tabs(tabs)

        # Cache the generated content so we can revert even if overrides exist.
        self._file_cache = {p.as_posix(): files[p] for p in file_paths}
        self._files = [p.as_posix() for p in file_paths if p.as_posix() != "WARNINGS"]
        self._refresh_file_list()

        custom_files = self.state.get("custom_files", {}) or {}
        enabled = bool(self.use_overrides.get())

        if warnings:
            w = self.notebook.get_text_widget("WARNINGS")
            if w is not None:
                w.delete("1.0", tk.END)
                w.insert(tk.END, "\n".join([f"- {msg}" for msg in warnings]) + "\n")

        for p in file_paths:
            name = p.as_posix()
            w = self.notebook.get_text_widget(name)
            if w is None:
                continue
            w.delete("1.0", tk.END)

            override = None
            if enabled and isinstance(custom_files, dict):
                override = custom_files.get(name)

            w.insert(tk.END, str(override) if override is not None else files[p])

        # Restore selection for better UX.
        if previous and previous in self.notebook.tab_names():
            self.notebook.select_tab(previous)
        elif self._files:
            self.notebook.select_tab(self._files[0])

    def _current_filename(self) -> str | None:
        tab = self.notebook.current_tab_name()
        if not tab or tab == "WARNINGS":
            return None
        return tab

    def save_current_override(self) -> None:
        name = self._current_filename()
        if not name:
            return
        w = self.notebook.get_text_widget(name)
        if w is None:
            return
        text = (w.get("1.0", tk.END) or "").rstrip() + "\n"

        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict):
            custom_files = {}
        custom_files[name] = text
        self.state.set("custom_files", custom_files)
        self.use_overrides.set(True)
        self.state.set("custom_files_enabled", True)
        messagebox.showinfo("Saved", f"Override saved for:\n{name}", parent=self.winfo_toplevel())

    def save_all_overrides(self) -> None:
        custom_files: dict[str, str] = {}
        for name in self.notebook.tab_names():
            if name == "WARNINGS":
                continue
            w = self.notebook.get_text_widget(name)
            if w is None:
                continue
            custom_files[name] = (w.get("1.0", tk.END) or "").rstrip() + "\n"

        self.state.set("custom_files", custom_files)
        self.use_overrides.set(True)
        self.state.set("custom_files_enabled", True)
        messagebox.showinfo("Saved", "Overrides saved for all tabs.", parent=self.winfo_toplevel())

    def revert_current_override(self) -> None:
        name = self._current_filename()
        if not name:
            return

        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict) or name not in custom_files:
            return

        if not messagebox.askyesno("Revert", f"Revert saved override for:\n{name}?", parent=self.winfo_toplevel()):
            return

        custom_files.pop(name, None)
        self.state.set("custom_files", custom_files)

        w = self.notebook.get_text_widget(name)
        if w is not None:
            w.delete("1.0", tk.END)
            w.insert(tk.END, self._file_cache.get(name, ""))

    def revert_all_overrides(self) -> None:
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict) or not custom_files:
            return
        if not messagebox.askyesno("Revert", "Revert all saved overrides?", parent=self.winfo_toplevel()):
            return
        self.state.set("custom_files", {})
        self.refresh_preview()

    def export_current_tab(self) -> None:
        name = self._current_filename()
        if not name:
            return
        w = self.notebook.get_text_widget(name)
        if w is None:
            return

        default = Path(name).name
        file_path = filedialog.asksaveasfilename(
            initialfile=default,
            defaultextension=Path(default).suffix or ".txt",
            filetypes=[("All Files", "*.*")],
        )
        if not file_path:
            return
        try:
            Path(file_path).write_text(w.get("1.0", tk.END), encoding="utf-8", newline="\n")
            messagebox.showinfo("Exported", "Tab exported successfully.", parent=self.winfo_toplevel())
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to export:\n{exc}", parent=self.winfo_toplevel())

    def copy_current_tab(self) -> None:
        name = self._current_filename()
        if not name:
            return
        w = self.notebook.get_text_widget(name)
        if w is None:
            return
        self.clipboard_clear()
        self.clipboard_append(w.get("1.0", tk.END))
        self.update()
        messagebox.showinfo("Copied", "Tab copied to clipboard.", parent=self.winfo_toplevel())
