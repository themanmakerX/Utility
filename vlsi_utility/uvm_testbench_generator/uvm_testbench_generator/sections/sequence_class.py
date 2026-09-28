from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, ttk

from ..utils.generator import generate_files
from ..utils.state import StateManager
from ..utils.ui import CodePreview, ScrollableFrame, section_title


class SequenceClassForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = scroller.content

        self.state = StateManager.get_instance()

        self.seq_name = tk.StringVar(value="my_sequence")
        self.txn_class = tk.StringVar(value="txn_item")

        self.info_text = tk.StringVar(value="")

        self.steps: list[dict] = []

        self._load_from_state()
        self.build_ui()

        self.state.subscribe_key("transaction", lambda *_: self._sync_txn_class())
        self.state.subscribe_key("agent", lambda *_: self._refresh_info())
        self.state.subscribe_key("custom_files", lambda *_: self.refresh_preview())
        self.state.subscribe_key("custom_files_enabled", lambda *_: self.refresh_preview())

        self._sync_txn_class()
        self.refresh_steps_table()
        self._refresh_info()
        self.refresh_preview()

    def _is_sv_identifier(self, value: str) -> bool:
        value = (value or "").strip()
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value))

    def _txn_fields(self) -> list[dict]:
        txn = self.state.get("transaction", {}) or {}
        fields = txn.get("fields", []) or []
        out: list[dict] = []
        if not isinstance(fields, list):
            return out
        for f in fields:
            if not isinstance(f, dict):
                continue
            name = str(f.get("name") or "").strip()
            if not name:
                continue
            out.append(f)
        return out

    def _sync_txn_class(self) -> None:
        txn = self.state.get("transaction", {}) or {}
        self.txn_class.set(str(txn.get("class_name") or self.txn_class.get() or "txn_item"))
        self.refresh_preview()

    def _agent_has_sequencer(self) -> bool:
        agent = self.state.get("agent", {}) or {}
        include = agent.get("include_components")
        if not isinstance(include, dict):
            include = agent.get("components")
        if isinstance(include, dict):
            return bool(include.get("sequencer", True))
        return True

    def _refresh_info(self) -> None:
        msgs: list[str] = []

        if not self._txn_fields():
            msgs.append("Tip: Import signals into Transaction to see fields for directed steps.")

        agent = self.state.get("agent", {}) or {}
        if isinstance(agent, dict) and agent:
            if not self._agent_has_sequencer():
                msgs.append("Agent Sequencer is disabled. Sequences won't run unless you connect to a sequencer.")

        self.info_text.set("  ".join(msgs))

    def _load_from_state(self) -> None:
        seq = self.state.get("sequence", {}) or {}
        if isinstance(seq, dict) and seq:
            self.seq_name.set(str(seq.get("name") or "my_sequence"))
            self.txn_class.set(str(seq.get("transaction_class") or "txn_item"))
            self.steps = list(seq.get("steps") or [])

    def build_ui(self) -> None:
        root = self.content
        root.columnconfigure(0, weight=1)

        row = 0
        section_title(root, "Sequence Class").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        basics = ttk.LabelFrame(root, text="Basics")
        basics.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        basics.columnconfigure(1, weight=1)
        basics.columnconfigure(3, weight=1)
        row += 1

        ttk.Label(basics, text="Sequence Class Name").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.seq_name).grid(
            row=0, column=1, sticky="ew", padx=10, pady=(10, 6)
        )

        ttk.Label(basics, text="Transaction Class").grid(row=0, column=2, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.txn_class).grid(
            row=0, column=3, sticky="ew", padx=10, pady=(10, 6)
        )

        ttk.Label(root, textvariable=self.info_text, foreground="#8aa4ff").grid(
            row=row, column=0, sticky="w", pady=(0, 10)
        )
        row += 1

        panes = ttk.PanedWindow(root, orient="horizontal")
        panes.grid(row=row, column=0, sticky="nsew", pady=(0, 10))
        root.rowconfigure(row, weight=1)
        row += 1

        # === Steps list ===
        steps_frame = ttk.LabelFrame(panes, text="Steps")
        steps_frame.columnconfigure(0, weight=1)
        steps_frame.rowconfigure(1, weight=1)
        panes.add(steps_frame, weight=2)

        toolbar = ttk.Frame(steps_frame)
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        ttk.Button(toolbar, text="Add", command=self.add_step_popup).pack(side="left")
        ttk.Button(toolbar, text="Edit", command=self.edit_selected_step).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Duplicate", command=self.duplicate_selected_step).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Remove", command=self.remove_selected_step).pack(side="left", padx=(8, 0))

        table_frame = ttk.Frame(steps_frame)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.step_tree = ttk.Treeview(
            table_frame,
            columns=("Name", "Delay", "Repeat", "Mode", "Fields"),
            show="headings",
            height=10,
        )
        for col, w in [("Name", 160), ("Delay", 90), ("Repeat", 70), ("Mode", 100), ("Fields", 120)]:
            self.step_tree.heading(col, text=col)
            self.step_tree.column(col, width=w, stretch=(col in ("Name", "Fields")), anchor="w")
        self.step_tree.column("Delay", anchor="e", stretch=False)
        self.step_tree.column("Repeat", anchor="e", stretch=False)

        y = ttk.Scrollbar(table_frame, orient="vertical", command=self.step_tree.yview)
        x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.step_tree.xview)
        self.step_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.step_tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")

        self.step_tree.bind("<Double-1>", lambda _e: self.edit_selected_step())
        self.step_tree.bind("<Delete>", lambda _e: self.remove_selected_step())

        # === Preview ===
        preview_frame = ttk.LabelFrame(panes, text="Generated Sequence (Editable)")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        panes.add(preview_frame, weight=3)

        preview_toolbar = ttk.Frame(preview_frame)
        preview_toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        ttk.Button(preview_toolbar, text="Save Sequence", command=self.save_sequence).pack(side="left")
        ttk.Button(preview_toolbar, text="Preview", command=self.refresh_preview).pack(side="left", padx=(8, 0))
        ttk.Separator(preview_toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(preview_toolbar, text="Save Preview as Override", command=self.save_preview_override).pack(
            side="left"
        )
        ttk.Button(preview_toolbar, text="Revert Override", command=self.revert_preview_override).pack(
            side="left", padx=(8, 0)
        )

        preview = CodePreview(preview_frame, height=24)
        preview.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.preview_box = preview.text

    def refresh_steps_table(self) -> None:
        self.step_tree.delete(*self.step_tree.get_children())
        for idx, s in enumerate(self.steps):
            name = str(s.get("item_name") or s.get("item") or f"step_{idx}").strip()
            delay = str(s.get("delay") or "0").strip()
            repeat = str(s.get("repeat") or "1").strip()
            randomize = bool(s.get("randomize", True))
            mode = "Randomize" if randomize else "Directed"
            assigns = s.get("assignments", {}) or {}
            field_count = len([k for k, v in assigns.items() if str(v).strip()]) if isinstance(assigns, dict) else 0
            self.step_tree.insert(
                "",
                "end",
                iid=f"s{idx}",
                values=(name, delay, repeat, mode, f"{field_count} set"),
            )

    def _selected_step_index(self) -> int | None:
        sel = self.step_tree.selection()
        if not sel:
            return None
        iid = str(sel[0])
        if not iid.startswith("s"):
            return None
        try:
            return int(iid[1:])
        except Exception:
            return None

    def add_step_popup(self) -> None:
        self._step_editor_popup(None)

    def edit_selected_step(self) -> None:
        idx = self._selected_step_index()
        if idx is None or idx < 0 or idx >= len(self.steps):
            messagebox.showwarning("Select", "Please select a step to edit.", parent=self.winfo_toplevel())
            return
        self._step_editor_popup(idx)

    def duplicate_selected_step(self) -> None:
        idx = self._selected_step_index()
        if idx is None or idx < 0 or idx >= len(self.steps):
            return
        s = dict(self.steps[idx])
        s["item_name"] = f"{s.get('item_name') or s.get('item') or 'step'}_copy"
        self.steps.insert(idx + 1, s)
        self.refresh_steps_table()
        self.refresh_preview()

    def remove_selected_step(self) -> None:
        idx = self._selected_step_index()
        if idx is None or idx < 0 or idx >= len(self.steps):
            return
        if not messagebox.askyesno("Remove", "Remove selected step?", parent=self.winfo_toplevel()):
            return
        self.steps.pop(idx)
        self.refresh_steps_table()
        self.refresh_preview()

    def _step_editor_popup(self, index: int | None) -> None:
        editing = index is not None
        step = dict(self.steps[index]) if editing else {}

        popup = tk.Toplevel(self)
        popup.title("Edit Step" if editing else "Add Step")
        popup.resizable(True, True)
        popup.minsize(720, 420)
        popup.transient(self.winfo_toplevel())

        item_name = tk.StringVar(value=str(step.get("item_name") or step.get("item") or "tx"))
        delay = tk.StringVar(value=str(step.get("delay") or "0"))
        repeat = tk.StringVar(value=str(step.get("repeat") or "1"))
        randomize = tk.BooleanVar(value=bool(step.get("randomize", True)))

        # Preserve assignments, but only for known fields
        existing_assignments = step.get("assignments", {}) or {}
        if not isinstance(existing_assignments, dict):
            existing_assignments = {}

        body = ttk.Frame(popup, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(3, weight=1)

        ttk.Label(body, text="Item Name").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=item_name).grid(row=0, column=1, sticky="ew", pady=4)

        meta = ttk.Frame(body)
        meta.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 10))
        ttk.Label(meta, text="Delay").pack(side="left")
        ttk.Entry(meta, textvariable=delay, width=10).pack(side="left", padx=(8, 18))
        ttk.Label(meta, text="Repeat").pack(side="left")
        ttk.Entry(meta, textvariable=repeat, width=10).pack(side="left", padx=(8, 18))
        ttk.Checkbutton(meta, text="Randomize (use 'with' constraints)", variable=randomize).pack(side="left")

        ttk.Label(body, text="Directed Fields (from Transaction)").grid(row=2, column=0, columnspan=2, sticky="w")

        fields_frame = ttk.Frame(body)
        fields_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(6, 10))
        fields_frame.columnconfigure(0, weight=1)
        fields_frame.rowconfigure(0, weight=1)

        canvas = tk.Canvas(fields_frame, highlightthickness=0)
        scroll = ttk.Scrollbar(fields_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        inner = ttk.Frame(canvas, padding=4)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        txn_fields = self._txn_fields()
        if not txn_fields:
            ttk.Label(inner, text="No transaction fields available.").grid(row=0, column=0, sticky="w", padx=6, pady=6)

        use_vars: dict[str, tk.BooleanVar] = {}
        value_vars: dict[str, tk.StringVar] = {}

        r = 0
        for f in txn_fields:
            fname = str(f.get("name") or "").strip()
            ftype = str(f.get("type") or "bit").strip()
            if not fname:
                continue

            default_value = str(existing_assignments.get(fname, "") or "")
            use_default = bool(default_value.strip())

            use_vars[fname] = tk.BooleanVar(value=use_default)
            value_vars[fname] = tk.StringVar(value=default_value)

            rowf = ttk.Frame(inner)
            rowf.grid(row=r, column=0, sticky="ew", padx=4, pady=2)
            rowf.columnconfigure(2, weight=1)

            ttk.Checkbutton(rowf, variable=use_vars[fname]).grid(row=0, column=0, sticky="w")
            ttk.Label(rowf, text=fname, width=18).grid(row=0, column=1, sticky="w", padx=(6, 10))
            ttk.Entry(rowf, textvariable=value_vars[fname]).grid(row=0, column=2, sticky="ew")
            ttk.Label(rowf, text=ftype, foreground="#9aa3b2").grid(row=0, column=3, sticky="w", padx=(10, 0))
            r += 1

        def select_all_fields():
            for v in use_vars.values():
                v.set(True)

        def clear_all_fields():
            for k in list(use_vars.keys()):
                use_vars[k].set(False)
                value_vars[k].set("")

        field_btns = ttk.Frame(body)
        field_btns.grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Button(field_btns, text="Select All", command=select_all_fields).pack(side="left")
        ttk.Button(field_btns, text="Clear", command=clear_all_fields).pack(side="left", padx=(8, 0))
        ttk.Label(
            field_btns,
            text="Values are SV expressions (ex: 8'hA5, '0, 1).",
            foreground="#9aa3b2",
        ).pack(side="left", padx=(14, 0))

        def on_save():
            item = (item_name.get() or "").strip() or "tx"
            if not self._is_sv_identifier(item):
                messagebox.showwarning(
                    "Invalid",
                    "Item name must be a valid SystemVerilog identifier.",
                    parent=popup,
                )
                return

            assignments: dict[str, str] = {}
            for name, use_var in use_vars.items():
                if not bool(use_var.get()):
                    continue
                val = (value_vars[name].get() or "").strip()
                if not val:
                    continue
                assignments[name] = val

            out = {
                "item_name": item,
                "delay": (delay.get() or "0").strip(),
                "repeat": (repeat.get() or "1").strip(),
                "randomize": bool(randomize.get()),
                "assignments": assignments,
            }

            if editing:
                self.steps[index] = out
            else:
                self.steps.append(out)
            self.refresh_steps_table()
            self.refresh_preview()
            popup.destroy()

        btns = ttk.Frame(body)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=popup.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=on_save).pack(side="right", padx=(0, 8))

    def _effective_sequence_state(self) -> dict:
        return {
            "name": (self.seq_name.get() or "").strip() or "my_sequence",
            "transaction_class": (self.txn_class.get() or "").strip() or "txn_item",
            "steps": self.steps,
        }

    def save_sequence(self) -> None:
        name = (self.seq_name.get() or "").strip()
        if not name or not self._is_sv_identifier(name):
            messagebox.showwarning(
                "Invalid",
                "Sequence class name must be a valid SystemVerilog identifier.",
                parent=self.winfo_toplevel(),
            )
            return
        data = self._effective_sequence_state()
        self.state.set("sequence", data)
        messagebox.showinfo("Saved", "Sequence saved successfully!", parent=self.winfo_toplevel())
        if hasattr(self.master.master, "footer"):
            self.master.master.footer.mark_done("sequence")

    def refresh_preview(self) -> None:
        temp = self.state.get_all()
        temp["sequence"] = self._effective_sequence_state()

        try:
            files, _warnings = generate_files(temp)
            content = files.get(Path("src/sequence.sv"), "")
        except Exception as exc:
            content = f"// Preview failed:\n// {exc}\n"

        custom_files = self.state.get("custom_files", {}) or {}
        enabled = bool(self.state.get("custom_files_enabled", True))
        override = None
        if enabled and isinstance(custom_files, dict):
            override = custom_files.get("src/sequence.sv")

        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert(tk.END, str(override) if override is not None else content)

    def save_preview_override(self) -> None:
        text = (self.preview_box.get("1.0", tk.END) or "").rstrip() + "\n"
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict):
            custom_files = {}
        custom_files["src/sequence.sv"] = text
        self.state.set("custom_files", custom_files)
        self.state.set("custom_files_enabled", True)
        messagebox.showinfo("Saved", "Override saved for src/sequence.sv", parent=self.winfo_toplevel())

    def revert_preview_override(self) -> None:
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict) or "src/sequence.sv" not in custom_files:
            return
        if not messagebox.askyesno(
            "Revert",
            "Revert saved override for src/sequence.sv?",
            parent=self.winfo_toplevel(),
        ):
            return
        custom_files.pop("src/sequence.sv", None)
        self.state.set("custom_files", custom_files)
        self.refresh_preview()

