from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

from ..utils.state import StateManager
from ..utils.ui import CodePreview, ScrollableFrame, section_title
from ..utils.workflow import Status, compute_module_statuses


class StateMachineViewer(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.state = StateManager.get_instance()

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = scroller.content

        self._raw_cache: dict = {}
        self._workflow_cache: dict = {}

        self.build_ui()
        self.refresh_all()

        self.state.subscribe(self._on_state_change)

    def _on_state_change(self, _key, _value, _snapshot) -> None:
        try:
            self.after(0, self.refresh_all)
        except Exception:
            pass

    def build_ui(self) -> None:
        root = self.content
        root.columnconfigure(0, weight=1)

        row = 0
        section_title(root, "Workflow & State Machine").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(actions, text="Refresh", command=self.refresh_all).pack(side="left")
        ttk.Button(actions, text="Clear State", command=self.clear_state).pack(side="left", padx=(8, 0))
        row += 1

        self.nb = ttk.Notebook(root)
        self.nb.grid(row=row, column=0, sticky="nsew")
        root.rowconfigure(row, weight=1)

        self.workflow_tab = ttk.Frame(self.nb, padding=10)
        self.raw_tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(self.workflow_tab, text="Workflow")
        self.nb.add(self.raw_tab, text="Raw State")

        self._build_workflow_tab(self.workflow_tab)
        self._build_raw_tab(self.raw_tab)

    def _build_workflow_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        panes = ttk.PanedWindow(parent, orient="horizontal")
        panes.grid(row=0, column=0, sticky="nsew")

        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        cols = ("Module", "Status", "Missing")
        self.workflow_tree = ttk.Treeview(left, columns=cols, show="headings", height=16)
        for col, w in [("Module", 180), ("Status", 90), ("Missing", 240)]:
            self.workflow_tree.heading(col, text=col)
            self.workflow_tree.column(col, width=w, stretch=(col != "Status"), anchor="w")
        self.workflow_tree.column("Status", anchor="center", stretch=False)

        y = ttk.Scrollbar(left, orient="vertical", command=self.workflow_tree.yview)
        x = ttk.Scrollbar(left, orient="horizontal", command=self.workflow_tree.xview)
        self.workflow_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.workflow_tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")

        self.workflow_tree.bind("<<TreeviewSelect>>", self._show_workflow_detail)

        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        preview = CodePreview(right, height=26)
        preview.grid(row=0, column=0, sticky="nsew")
        self.workflow_detail = preview.text

    def _build_raw_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        panes = ttk.PanedWindow(parent, orient="horizontal")
        panes.grid(row=0, column=0, sticky="nsew")

        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.raw_tree = ttk.Treeview(left, columns=("Key", "Value"), show="headings", height=16)
        self.raw_tree.heading("Key", text="Key")
        self.raw_tree.heading("Value", text="Value")
        self.raw_tree.column("Key", width=180, anchor="w", stretch=False)
        self.raw_tree.column("Value", width=480, anchor="w", stretch=True)

        y = ttk.Scrollbar(left, orient="vertical", command=self.raw_tree.yview)
        x = ttk.Scrollbar(left, orient="horizontal", command=self.raw_tree.xview)
        self.raw_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.raw_tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")

        self.raw_tree.bind("<<TreeviewSelect>>", self._show_raw_detail)

        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        preview = CodePreview(right, height=26)
        preview.grid(row=0, column=0, sticky="nsew")
        self.raw_detail = preview.text

    def refresh_all(self) -> None:
        snapshot = self.state.get_all()
        self._raw_cache = snapshot
        self._workflow_cache = compute_module_statuses(snapshot)

        self._refresh_workflow_tree()
        self._refresh_raw_tree()

    def _refresh_workflow_tree(self) -> None:
        self.workflow_tree.delete(*self.workflow_tree.get_children())

        order = [
            ("Dashboard", "dashboard"),
            ("Project Details", "project_details"),
            ("Interface & DUT", "interface_dut"),
            ("Transaction", "transaction_class"),
            ("Agent", "agent_class"),
            ("Scoreboard", "scoreboard_class"),
            ("Environment", "environment_class"),
            ("Sequence", "sequence_class"),
            ("Test", "test_class"),
            ("Top Module", "top_module"),
            ("Preview", "preview"),
            ("State Machine", "state_machine"),
        ]

        def status_text(s: Status) -> str:
            if s == Status.COMPLETE:
                return "OK"
            if s == Status.BLOCKED:
                return "BLOCKED"
            return "TODO"

        for label, key in order:
            st = self._workflow_cache.get(key)
            if not st:
                continue
            missing = ", ".join(st.missing) if st.missing else ""
            self.workflow_tree.insert("", "end", iid=key, values=(label, status_text(st.status), missing))

        self.workflow_detail.delete("1.0", tk.END)
        self.workflow_detail.insert(
            tk.END,
            "Select a module to see:\n- status\n- missing requirements\n- hint\n- related saved state\n",
        )

    def _refresh_raw_tree(self) -> None:
        self.raw_tree.delete(*self.raw_tree.get_children())
        for k in sorted(self._raw_cache.keys(), key=lambda s: str(s)):
            v = self._raw_cache.get(k)
            one_line = str(v).replace("\n", " ")
            if len(one_line) > 200:
                one_line = one_line[:200] + "..."
            self.raw_tree.insert("", "end", iid=str(k), values=(k, one_line))

        self.raw_detail.delete("1.0", tk.END)
        self.raw_detail.insert(tk.END, "Select a key to see the full value.\n")

    def _show_workflow_detail(self, _event=None) -> None:
        sel = self.workflow_tree.selection()
        if not sel:
            return
        key = str(sel[0])
        st = self._workflow_cache.get(key)
        if not st:
            return

        related_state_key = {
            "project_details": "project",
            "interface_dut": "interface",
            "transaction_class": "transaction",
            "agent_class": "agent",
            "scoreboard_class": "scoreboard",
            "environment_class": "environment",
            "sequence_class": "sequence",
            "test_class": "test",
            "top_module": "top",
        }.get(key)

        related = self._raw_cache.get(related_state_key, {}) if related_state_key else {}

        payload = {
            "module": key,
            "status": st.status.value,
            "missing": list(st.missing),
            "hint": st.hint,
            "state_key": related_state_key,
            "state_value": related,
        }

        self.workflow_detail.delete("1.0", tk.END)
        self.workflow_detail.insert(tk.END, json.dumps(payload, indent=2))

    def _show_raw_detail(self, _event=None) -> None:
        sel = self.raw_tree.selection()
        if not sel:
            return
        key = str(sel[0])
        value = self._raw_cache.get(key, "")
        self.raw_detail.delete("1.0", tk.END)
        try:
            self.raw_detail.insert(tk.END, json.dumps(value, indent=2))
        except Exception:
            self.raw_detail.insert(tk.END, str(value))

    def clear_state(self) -> None:
        if not messagebox.askyesno("Confirm", "Clear all saved state data?", parent=self.winfo_toplevel()):
            return
        self.state.clear()
        self.refresh_all()

