from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, ttk

from ..utils.generator import generate_files
from ..utils.state import StateManager
from ..utils.ui import CodePreview, ScrollableFrame, section_title


class ScoreboardClassForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = scroller.content

        self.state = StateManager.get_instance()

        self.scoreboard_name = tk.StringVar(value="my_scoreboard")
        self.use_expected_queue = tk.BooleanVar(value=True)
        self.compare_mode = tk.StringVar(value="uvm_compare")  # uvm_compare | manual
        self.enable_coverage = tk.BooleanVar(value=False)

        self.info_text = tk.StringVar(value="")
        self._field_vars: dict[str, tk.BooleanVar] = {}

        self._load_from_state()
        self.build_ui()

        self.state.subscribe_key("transaction", lambda *_: self._rebuild_fields())
        self.state.subscribe_key("agent", lambda *_: self._refresh_info())
        self.state.subscribe_key("interface", lambda *_: self._refresh_info())

        self.compare_mode.trace_add("write", lambda *_: self.refresh_preview())
        self.use_expected_queue.trace_add("write", lambda *_: self.refresh_preview())
        self.enable_coverage.trace_add("write", lambda *_: self.refresh_preview())

        self._rebuild_fields()
        self._refresh_info()
        self.refresh_preview()

    def _is_sv_identifier(self, value: str) -> bool:
        value = (value or "").strip()
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value))

    def _txn_class_name(self) -> str:
        txn = self.state.get("transaction", {}) or {}
        return str(txn.get("class_name") or "txn_item")

    def _txn_fields(self) -> list[dict]:
        txn = self.state.get("transaction", {}) or {}
        fields = txn.get("fields", []) or []
        out: list[dict] = []
        for f in fields:
            if not isinstance(f, dict):
                continue
            name = str(f.get("name") or "").strip()
            if not name:
                continue
            out.append(f)
        return out

    def _load_from_state(self) -> None:
        sb = self.state.get("scoreboard", {}) or {}
        if not isinstance(sb, dict) or not sb:
            return

        self.scoreboard_name.set(str(sb.get("name") or "my_scoreboard"))
        self.use_expected_queue.set(bool(sb.get("use_expected_queue", sb.get("use_queue", True))))
        self.enable_coverage.set(bool(sb.get("enable_coverage", sb.get("use_coverage", False))))
        self.compare_mode.set(str(sb.get("compare_mode") or "uvm_compare"))

        selected = sb.get("fields")
        if isinstance(selected, list):
            for n in selected:
                if isinstance(n, str) and n.strip():
                    self._field_vars[n.strip()] = tk.BooleanVar(value=True)

    def build_ui(self) -> None:
        root = self.content
        root.columnconfigure(0, weight=1)

        row = 0
        section_title(root, "Scoreboard Class").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        basics = ttk.LabelFrame(root, text="Basics")
        basics.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        basics.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(basics, text="Scoreboard Class Name").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.scoreboard_name).grid(
            row=0, column=1, sticky="ew", padx=10, pady=(10, 6)
        )

        ttk.Label(basics, text="Transaction Class").grid(row=1, column=0, sticky="w", padx=10, pady=(6, 10))
        ttk.Label(basics, text=self._txn_class_name()).grid(row=1, column=1, sticky="w", padx=10, pady=(6, 10))

        opts = ttk.LabelFrame(root, text="Options")
        opts.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        row += 1

        ttk.Checkbutton(opts, text="Use expected queue", variable=self.use_expected_queue).grid(
            row=0, column=0, sticky="w", padx=10, pady=8
        )
        ttk.Label(opts, text="Compare mode").grid(row=0, column=1, sticky="w", padx=(18, 8), pady=8)
        ttk.Combobox(
            opts,
            textvariable=self.compare_mode,
            values=["uvm_compare", "manual"],
            state="readonly",
            width=16,
        ).grid(row=0, column=2, sticky="w", padx=(0, 10), pady=8)
        ttk.Checkbutton(opts, text="Enable coverage", variable=self.enable_coverage).grid(
            row=0, column=3, sticky="w", padx=(18, 10), pady=8
        )

        ttk.Label(root, textvariable=self.info_text, foreground="#8aa4ff").grid(
            row=row, column=0, sticky="w", pady=(0, 10)
        )
        row += 1

        fields_frame = ttk.LabelFrame(root, text="Fields (auto-detected from Transaction)")
        fields_frame.grid(row=row, column=0, sticky="nsew", pady=(0, 10))
        fields_frame.columnconfigure(0, weight=1)
        row += 1

        toolbar = ttk.Frame(fields_frame)
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        ttk.Button(toolbar, text="Select Outputs (non-rand)", command=self.select_outputs).pack(side="left")
        ttk.Button(toolbar, text="Select All", command=self.select_all).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Clear", command=self.clear_selection).pack(side="left", padx=(8, 0))
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(toolbar, text="Refresh Preview", command=self.refresh_preview).pack(side="left")

        list_frame = ttk.Frame(fields_frame)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        fields_frame.rowconfigure(1, weight=1)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self._fields_canvas = tk.Canvas(list_frame, highlightthickness=0)
        self._fields_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self._fields_canvas.yview)
        self._fields_canvas.configure(yscrollcommand=self._fields_scroll.set)
        self._fields_canvas.grid(row=0, column=0, sticky="nsew")
        self._fields_scroll.grid(row=0, column=1, sticky="ns")

        self._fields_inner = ttk.Frame(self._fields_canvas, padding=4)
        self._fields_window = self._fields_canvas.create_window((0, 0), window=self._fields_inner, anchor="nw")
        self._fields_inner.bind("<Configure>", lambda _e: self._fields_canvas.configure(scrollregion=self._fields_canvas.bbox("all")))
        self._fields_canvas.bind(
            "<Configure>",
            lambda e: self._fields_canvas.itemconfig(self._fields_window, width=e.width),
        )

        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="Save Scoreboard", command=self.save_scoreboard).pack(side="left")
        ttk.Button(actions, text="Save Preview as Override", command=self.save_preview_override).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Revert Override", command=self.revert_preview_override).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Preview Class", command=self.refresh_preview).pack(side="right")
        row += 1

        preview_frame = ttk.LabelFrame(root, text="Generated Scoreboard (Editable)")
        preview_frame.grid(row=row, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)

        preview = CodePreview(preview_frame, height=24)
        preview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.preview_box = preview.text

    def _refresh_info(self) -> None:
        msgs: list[str] = []

        agent = self.state.get("agent", {}) or {}
        include = agent.get("include_components")
        if not isinstance(include, dict):
            include = agent.get("components")
        mon_enabled = True
        if isinstance(include, dict):
            mon_enabled = bool(include.get("monitor", True))

        if not mon_enabled:
            msgs.append("Monitor is disabled in Agent. Scoreboard will not receive transactions.")

        txn_fields = self._txn_fields()
        if not txn_fields:
            msgs.append("No transaction fields found yet. Import signals into Transaction to enable field intelligence.")

        self.info_text.set("  ".join(msgs))

    def _rebuild_fields(self) -> None:
        # clear UI
        for child in list(self._fields_inner.winfo_children()):
            child.destroy()

        txn_fields = self._txn_fields()
        existing_selected = set(k for k, v in self._field_vars.items() if bool(v.get()))
        self._field_vars = {}

        if not txn_fields:
            ttk.Label(self._fields_inner, text="No fields available.").grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return

        # Default: outputs (non-rand). If user had selections saved, keep them.
        has_saved = bool(existing_selected)
        for f in txn_fields:
            name = str(f.get("name") or "").strip()
            if not name:
                continue
            is_output = not bool(f.get("rand"))
            default_on = (name in existing_selected) if has_saved else is_output
            self._field_vars[name] = tk.BooleanVar(value=default_on)

        r = 0
        for name, var in sorted(self._field_vars.items(), key=lambda kv: kv[0].lower()):
            ttk.Checkbutton(self._fields_inner, text=name, variable=var, command=self.refresh_preview).grid(
                row=r, column=0, sticky="w", padx=6, pady=2
            )
            r += 1

        self._refresh_info()
        self.refresh_preview()

    def selected_fields(self) -> list[str]:
        return [name for name, var in self._field_vars.items() if bool(var.get())]

    def select_outputs(self) -> None:
        txn_fields = {str(f.get("name") or "").strip(): f for f in self._txn_fields()}
        for name, var in self._field_vars.items():
            f = txn_fields.get(name, {})
            var.set(not bool(f.get("rand")))
        self.refresh_preview()

    def select_all(self) -> None:
        for var in self._field_vars.values():
            var.set(True)
        self.refresh_preview()

    def clear_selection(self) -> None:
        for var in self._field_vars.values():
            var.set(False)
        self.refresh_preview()

    def _effective_scoreboard_state(self) -> dict:
        txn = self._txn_class_name()
        return {
            "name": (self.scoreboard_name.get() or "").strip() or "my_scoreboard",
            "transaction": txn,
            "use_expected_queue": bool(self.use_expected_queue.get()),
            "compare_mode": (self.compare_mode.get() or "uvm_compare").strip(),
            "enable_coverage": bool(self.enable_coverage.get()),
            "fields": self.selected_fields(),
        }

    def save_scoreboard(self) -> None:
        name = (self.scoreboard_name.get() or "").strip()
        if not name or not self._is_sv_identifier(name):
            messagebox.showwarning(
                "Invalid",
                "Scoreboard class name must be a valid SystemVerilog identifier.",
                parent=self.winfo_toplevel(),
            )
            return

        data = self._effective_scoreboard_state()
        # Back-compat for generator/state
        data["use_queue"] = data["use_expected_queue"]
        data["use_coverage"] = data["enable_coverage"]

        self.state.set("scoreboard", data)
        messagebox.showinfo("Saved", "Scoreboard configuration saved successfully!", parent=self.winfo_toplevel())
        if hasattr(self.master.master, "footer"):
            self.master.master.footer.mark_done("scoreboard")

    def refresh_preview(self) -> None:
        temp = self.state.get_all()
        temp["scoreboard"] = self._effective_scoreboard_state()

        try:
            files, _warnings = generate_files(temp)
            content = files.get(Path("src/scoreboard.sv"), "")
        except Exception as exc:
            content = f"// Preview failed:\n// {exc}\n"

        # If override exists and overrides enabled, show override (with a note)
        custom_files = self.state.get("custom_files", {}) or {}
        enabled = bool(self.state.get("custom_files_enabled", True))
        override = None
        if enabled and isinstance(custom_files, dict):
            override = custom_files.get("src/scoreboard.sv")

        self.preview_box.delete("1.0", tk.END)
        if override is not None:
            self.preview_box.insert(tk.END, str(override))
        else:
            self.preview_box.insert(tk.END, content)

    def save_preview_override(self) -> None:
        text = (self.preview_box.get("1.0", tk.END) or "").rstrip() + "\n"
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict):
            custom_files = {}
        custom_files["src/scoreboard.sv"] = text
        self.state.set("custom_files", custom_files)
        self.state.set("custom_files_enabled", True)
        messagebox.showinfo("Saved", "Override saved for src/scoreboard.sv", parent=self.winfo_toplevel())

    def revert_preview_override(self) -> None:
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict) or "src/scoreboard.sv" not in custom_files:
            return
        if not messagebox.askyesno(
            "Revert",
            "Revert saved override for src/scoreboard.sv?",
            parent=self.winfo_toplevel(),
        ):
            return
        custom_files.pop("src/scoreboard.sv", None)
        self.state.set("custom_files", custom_files)
        self.refresh_preview()

