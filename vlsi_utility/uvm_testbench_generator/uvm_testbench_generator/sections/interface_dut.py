from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ..utils.state import StateManager
from ..utils.ui import CodePreview, ScrollableFrame


class InterfaceDUTForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content_frame = scroller.content

        self.state = StateManager.get_instance()
        self.signals: list[dict] = []
        self.modports: dict[str, dict[str, str]] = {}

        self.build_ui()

    def build_ui(self) -> None:
        root = self.content_frame
        root.columnconfigure(0, weight=1)

        row = 0
        ttk.Label(
            root, text="Interface & DUT Configuration", font=("Segoe UI", 16, "bold")
        ).grid(row=row, column=0, pady=(0, 10), sticky="w")
        row += 1

        # === Basics ===
        basics = ttk.LabelFrame(root, text="Basics")
        basics.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        basics.columnconfigure(1, weight=1)
        row += 1

        self.interface_name = tk.StringVar(value="my_if")
        self.clock_signal = tk.StringVar()
        self.reset_signal = tk.StringVar()

        ttk.Label(basics, text="Interface Name").grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 4)
        )
        ttk.Entry(basics, textvariable=self.interface_name).grid(
            row=0, column=1, sticky="ew", padx=10, pady=(8, 4)
        )

        self.clock_combo = ttk.Combobox(basics, textvariable=self.clock_signal, state="readonly")
        self.reset_combo = ttk.Combobox(basics, textvariable=self.reset_signal, state="readonly")

        ttk.Label(basics, text="Clock Signal").grid(
            row=1, column=0, sticky="w", padx=10, pady=4
        )
        self.clock_combo.grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        ttk.Label(basics, text="Reset Signal").grid(
            row=2, column=0, sticky="w", padx=10, pady=(4, 8)
        )
        self.reset_combo.grid(row=2, column=1, sticky="ew", padx=10, pady=(4, 8))

        # === Signals ===
        signals_frame = ttk.LabelFrame(root, text="Signals")
        signals_frame.grid(row=row, column=0, sticky="nsew", pady=(0, 10))
        signals_frame.columnconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)
        row += 1

        toolbar = ttk.Frame(signals_frame)
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
        toolbar.columnconfigure(1, weight=1)

        ttk.Label(toolbar, text="Filter").grid(row=0, column=0, sticky="w")
        self.signal_filter = tk.StringVar()
        filter_entry = ttk.Entry(toolbar, textvariable=self.signal_filter)
        filter_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        filter_entry.bind("<KeyRelease>", lambda e: self.refresh_signal_table())

        ttk.Button(toolbar, text="Import from DUT", command=self.import_from_dut).grid(
            row=0, column=2, sticky="e"
        )

        sig_tree_frame = ttk.Frame(signals_frame)
        sig_tree_frame.grid(row=1, column=0, sticky="nsew", padx=10)
        sig_tree_frame.rowconfigure(0, weight=1)
        sig_tree_frame.columnconfigure(0, weight=1)
        signals_frame.rowconfigure(1, weight=1)

        self.signal_tree = ttk.Treeview(
            sig_tree_frame, columns=("Direction", "Name", "Width"), show="headings", height=10
        )
        self.signal_tree.heading("Direction", text="Direction")
        self.signal_tree.heading("Name", text="Name")
        self.signal_tree.heading("Width", text="Width")
        self.signal_tree.column("Direction", width=120, stretch=False, anchor="w")
        self.signal_tree.column("Name", width=260, stretch=True, anchor="w")
        self.signal_tree.column("Width", width=80, stretch=False, anchor="e")

        sig_y = ttk.Scrollbar(sig_tree_frame, orient="vertical", command=self.signal_tree.yview)
        self.signal_tree.configure(yscrollcommand=sig_y.set)
        self.signal_tree.grid(row=0, column=0, sticky="nsew")
        sig_y.grid(row=0, column=1, sticky="ns")

        self.signal_tree.bind("<Delete>", lambda e: self.remove_selected_signal())
        self.signal_tree.bind("<Double-1>", lambda e: self.edit_signal_popup())

        sig_btns = ttk.Frame(signals_frame)
        sig_btns.grid(row=2, column=0, sticky="e", padx=10, pady=(6, 8))
        ttk.Button(sig_btns, text="Add", command=self.add_signal_popup).pack(side="left", padx=(0, 8))
        ttk.Button(sig_btns, text="Edit", command=self.edit_signal_popup).pack(side="left", padx=(0, 8))
        ttk.Button(sig_btns, text="Remove", command=self.remove_selected_signal).pack(side="left")

        # === Modports ===
        modports_frame = ttk.LabelFrame(root, text="Modports")
        modports_frame.grid(row=row, column=0, sticky="nsew", pady=(0, 10))
        modports_frame.columnconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)
        row += 1

        self.modport_name = tk.StringVar()
        self.modport_signal = tk.StringVar()
        self.modport_direction = tk.StringVar(value="input")

        mp_form = ttk.Frame(modports_frame)
        mp_form.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
        mp_form.columnconfigure(1, weight=1)
        mp_form.columnconfigure(3, weight=1)

        ttk.Label(mp_form, text="Modport Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(mp_form, textvariable=self.modport_name).grid(
            row=0, column=1, sticky="ew", padx=(8, 8)
        )
        ttk.Button(mp_form, text="Add Modport", command=self.add_modport_entry).grid(row=0, column=2, sticky="w")

        ttk.Label(mp_form, text="Signal").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.modport_signal_cb = ttk.Combobox(
            mp_form, textvariable=self.modport_signal, values=[], state="readonly"
        )
        self.modport_signal_cb.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(6, 0))

        ttk.Label(mp_form, text="Access").grid(row=1, column=2, sticky="w", pady=(6, 0))
        self.modport_dir_cb = ttk.Combobox(
            mp_form,
            textvariable=self.modport_direction,
            values=["input", "output"],
            state="readonly",
            width=10,
        )
        self.modport_dir_cb.grid(row=1, column=3, sticky="w", padx=(8, 8), pady=(6, 0))

        mp_actions = ttk.Frame(modports_frame)
        mp_actions.grid(row=1, column=0, sticky="e", padx=10, pady=(0, 6))
        ttk.Button(mp_actions, text="Add to Modport", command=self.add_to_modport).pack(side="left", padx=(0, 8))
        ttk.Button(mp_actions, text="Remove Selected", command=self.remove_modport_entry).pack(side="left")

        mp_tree_frame = ttk.Frame(modports_frame)
        mp_tree_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        mp_tree_frame.rowconfigure(0, weight=1)
        mp_tree_frame.columnconfigure(0, weight=1)
        modports_frame.rowconfigure(2, weight=1)

        self.modport_tree = ttk.Treeview(
            mp_tree_frame, columns=("Modport", "Signal", "Access"), show="headings", height=8
        )
        for col in ("Modport", "Signal", "Access"):
            self.modport_tree.heading(col, text=col)
        self.modport_tree.column("Modport", width=140, stretch=False, anchor="w")
        self.modport_tree.column("Signal", width=260, stretch=True, anchor="w")
        self.modport_tree.column("Access", width=80, stretch=False, anchor="center")

        mp_y = ttk.Scrollbar(mp_tree_frame, orient="vertical", command=self.modport_tree.yview)
        self.modport_tree.configure(yscrollcommand=mp_y.set)
        self.modport_tree.grid(row=0, column=0, sticky="nsew")
        mp_y.grid(row=0, column=1, sticky="ns")
        self.modport_tree.bind("<Delete>", lambda e: self.remove_modport_entry())

        # === Bottom actions + preview ===
        action_bar = ttk.Frame(root)
        action_bar.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(action_bar, text="Save Interface", command=self.save_interface).pack(side="left")
        ttk.Button(action_bar, text="Preview", command=self.show_preview).pack(side="right")
        row += 1

        preview_frame = ttk.LabelFrame(root, text="Interface Preview")
        preview_frame.grid(row=row, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)

        preview = CodePreview(preview_frame, height=14)
        preview.grid(row=0, column=0, sticky="nsew")
        self.preview_box = preview.text

        # Populate initial signals (if Project has DUT info already)
        self.import_from_dut()

    # === Helper Functions ===
    def _guess_signal(self, candidates: list[str], needles: tuple[str, ...]) -> str | None:
        for needle in needles:
            for c in candidates:
                if needle in str(c).lower():
                    return c
        return None

    def _refresh_signal_dependent_controls(self) -> None:
        all_names = [s.get("name") for s in self.signals if s.get("name")]
        input_names = [
            s.get("name") for s in self.signals if s.get("name") and s.get("direction") == "input"
        ]
        self.modport_signal_cb["values"] = all_names
        self.clock_combo["values"] = input_names
        self.reset_combo["values"] = input_names

    def import_from_dut(self) -> None:
        project = self.state.get("project", {}) or {}
        dut_signals = (project.get("dut_info", {}) or {}).get("signals", []) or []

        # Normalize and copy
        self.signals = [
            {
                "direction": s.get("direction", "input"),
                "name": s.get("name", ""),
                "width": str(s.get("width", "1")),
            }
            for s in dut_signals
        ]
        self._refresh_signal_dependent_controls()
        self.refresh_signal_table()

        inputs = [s.get("name") for s in self.signals if s.get("direction") == "input" and s.get("name")]
        if inputs and not self.clock_signal.get():
            self.clock_signal.set(self._guess_signal(inputs, ("clk", "clock")) or inputs[0])
        if inputs and not self.reset_signal.get():
            self.reset_signal.set(self._guess_signal(inputs, ("rst", "reset")) or inputs[0])

    def refresh_signal_table(self) -> None:
        self._refresh_signal_dependent_controls()
        self.signal_tree.delete(*self.signal_tree.get_children())

        flt = (self.signal_filter.get() or "").strip().lower() if hasattr(self, "signal_filter") else ""
        for sig in self.signals:
            direction = sig.get("direction", "input")
            name = sig.get("name", "")
            width = sig.get("width", "1")
            if flt:
                hay = f"{direction} {name} {width}".lower()
                if flt not in hay:
                    continue
            self.signal_tree.insert("", "end", values=(direction, name, width))

    def refresh_modport_tree(self) -> None:
        self.modport_tree.delete(*self.modport_tree.get_children())
        for mod, signals in self.modports.items():
            for sig, acc in signals.items():
                self.modport_tree.insert("", "end", values=(mod, sig, acc))

    def add_signal_popup(self) -> None:
        self._popup_add_edit_signal(title="Add Signal")

    def edit_signal_popup(self) -> None:
        selected = self.signal_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a signal to edit.")
            return
        item = self.signal_tree.item(selected[0])
        old_direction, old_name, old_width = item["values"]
        self._popup_add_edit_signal(
            title="Edit Signal", old_dir=old_direction, old_name=old_name, old_width=old_width
        )

    def _popup_add_edit_signal(self, title, old_dir=None, old_name=None, old_width=None) -> None:
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.resizable(False, False)

        dir_var = tk.StringVar(value=old_dir if old_dir else "input")
        name_var = tk.StringVar(value=old_name if old_name else "")
        width_var = tk.StringVar(value=str(old_width) if old_width else "1")

        body = ttk.Frame(popup, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="Direction").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            body, textvariable=dir_var, values=["input", "output", "inout"], state="readonly"
        ).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(body, text="Signal Name").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=name_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(body, text="Width").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=width_var).grid(row=2, column=1, sticky="ew", pady=4)

        def on_save():
            new_sig = {
                "direction": dir_var.get(),
                "name": name_var.get().strip(),
                "width": width_var.get().strip() or "1",
            }
            if old_name:
                for i, sig in enumerate(self.signals):
                    if sig.get("name") == old_name and sig.get("direction") == old_dir:
                        self.signals[i] = new_sig
                        break
            else:
                self.signals.append(new_sig)
            self.refresh_signal_table()
            popup.destroy()

        btns = ttk.Frame(body)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel", command=popup.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=on_save).pack(side="right", padx=(0, 8))

    def remove_selected_signal(self) -> None:
        selected = self.signal_tree.selection()
        if not selected:
            return
        to_remove = set()
        for item in selected:
            direction, name, _width = self.signal_tree.item(item)["values"]
            to_remove.add((direction, name))
        self.signals = [
            s
            for s in self.signals
            if (s.get("direction", "input"), s.get("name", "")) not in to_remove
        ]
        self.refresh_signal_table()

    def add_modport_entry(self) -> None:
        name = self.modport_name.get().strip()
        if name and name not in self.modports:
            self.modports[name] = {}
            self.refresh_modport_tree()

    def add_to_modport(self) -> None:
        name = self.modport_name.get().strip()
        sig = self.modport_signal.get().strip()
        access = self.modport_direction.get().strip()
        if not (name and sig and access):
            return
        if name not in self.modports:
            self.modports[name] = {}
        self.modports[name][sig] = access
        self.refresh_modport_tree()

    def remove_modport_entry(self) -> None:
        selected = self.modport_tree.selection()
        if not selected:
            return
        for item in selected:
            modport, signal, _acc = self.modport_tree.item(item)["values"]
            if modport in self.modports and signal in self.modports[modport]:
                del self.modports[modport][signal]
        self.refresh_modport_tree()

    def show_preview(self) -> None:
        intf_name = self.interface_name.get().strip() or "my_if"
        clk = self.clock_signal.get().strip()
        rst = self.reset_signal.get().strip()

        ports = []
        if clk:
            ports.append(f"input {clk}")
        if rst:
            ports.append(f"input {rst}")
        port_clause = f"({', '.join(ports)})" if ports else ""

        code = f"interface {intf_name}{port_clause};\n"
        for sig in self.signals:
            direction = sig.get("direction", "input")
            name = sig.get("name", "")
            width_s = sig.get("width", "1")
            try:
                width = int(str(width_s))
            except Exception:
                width = 1
            if width <= 1:
                code += f"  {direction} logic {name};\n"
            else:
                code += f"  {direction} logic [{width - 1}:0] {name};\n"

        if self.modports:
            code += "\n"
            for mod, sigs in self.modports.items():
                code += f"  modport {mod} (\n"
                entries = [f"    {acc} {sig}" for sig, acc in sigs.items()]
                code += ",\n".join(entries) + "\n  );\n"

        code += f"endinterface : {intf_name}\n"

        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert(tk.END, code)

    def save_interface(self) -> None:
        data = {
            "name": self.interface_name.get(),
            "clock": self.clock_signal.get(),
            "reset": self.reset_signal.get(),
            "signals": self.signals,
            "modports": self.modports,
        }
        self.state.set("interface", data)
        messagebox.showinfo("Saved", "Interface details and modports saved successfully!")
        if hasattr(self.master.master, "footer"):
            self.master.master.footer.mark_done("interface")

