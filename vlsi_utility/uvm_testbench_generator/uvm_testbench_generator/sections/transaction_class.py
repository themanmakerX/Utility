from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk

from ..utils.state import StateManager
from ..utils.ui import CodePreview, ScrollableFrame, code_text, section_title


class TransactionClassForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = scroller.content

        self.state = StateManager.get_instance()

        self.class_name = tk.StringVar(value="txn_item")
        self.base_class = tk.StringVar(value="uvm_sequence_item")
        self.field_filter = tk.StringVar()

        self.fields: list[dict] = []
        self.constraints: list[dict] = []

        existing = self.state.get("transaction", {}) or {}
        if isinstance(existing, dict) and existing:
            self.class_name.set(str(existing.get("class_name") or "txn_item"))
            self.base_class.set(str(existing.get("base_class") or "uvm_sequence_item"))
            self.fields = list(existing.get("fields") or [])
            self.constraints = list(existing.get("constraints") or [])

        self.build_ui()
        self.refresh_field_table()
        self.refresh_constraint_table()
        self.update_constraint_display()

    def _is_sv_identifier(self, value: str) -> bool:
        value = (value or "").strip()
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value))

    def _get_selected_field_indices(self) -> list[int]:
        indices: list[int] = []
        for iid in self.field_tree.selection():
            iid_str = str(iid)
            if not iid_str.startswith("f"):
                continue
            try:
                idx = int(iid_str[1:])
            except Exception:
                continue
            if 0 <= idx < len(self.fields):
                indices.append(idx)
        return sorted(set(indices))

    def _get_selected_constraint_indices(self) -> list[int]:
        indices: list[int] = []
        for iid in self.constraint_tree.selection():
            iid_str = str(iid)
            if not iid_str.startswith("c"):
                continue
            try:
                idx = int(iid_str[1:])
            except Exception:
                continue
            if 0 <= idx < len(self.constraints):
                indices.append(idx)
        return sorted(set(indices))

    def build_ui(self) -> None:
        root = self.content
        root.columnconfigure(0, weight=1)

        row = 0
        section_title(root, "Transaction Class Details").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        basics = ttk.LabelFrame(root, text="Basics")
        basics.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        basics.columnconfigure(1, weight=1)
        basics.columnconfigure(3, weight=1)
        basics.columnconfigure(4, weight=1)
        row += 1

        ttk.Label(basics, text="Class Name").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.class_name).grid(
            row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 6)
        )

        ttk.Label(basics, text="Base Class").grid(row=0, column=2, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.base_class).grid(
            row=0, column=3, sticky="ew", padx=(0, 10), pady=(10, 6)
        )

        ttk.Button(basics, text="Import from Interface", command=self.import_from_interface).grid(
            row=0, column=4, sticky="e", padx=10, pady=(10, 6)
        )

        panes = ttk.PanedWindow(root, orient="horizontal")
        panes.grid(row=row, column=0, sticky="nsew", pady=(0, 10))
        root.rowconfigure(row, weight=1)
        row += 1

        fields_frame = ttk.LabelFrame(panes, text="Fields")
        fields_frame.columnconfigure(0, weight=1)
        fields_frame.rowconfigure(1, weight=1)
        panes.add(fields_frame, weight=3)

        fields_toolbar = ttk.Frame(fields_frame)
        fields_toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        fields_toolbar.columnconfigure(1, weight=1)

        ttk.Label(fields_toolbar, text="Filter").grid(row=0, column=0, sticky="w")
        filter_entry = ttk.Entry(fields_toolbar, textvariable=self.field_filter)
        filter_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        filter_entry.bind("<KeyRelease>", lambda _e: self.refresh_field_table())

        ttk.Button(fields_toolbar, text="Add Field", command=self.add_field_popup).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(fields_toolbar, text="Edit", command=self.edit_selected_field).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(fields_toolbar, text="Remove", command=self.remove_selected_field).grid(row=0, column=4)

        fields_tree_frame = ttk.Frame(fields_frame)
        fields_tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        fields_tree_frame.rowconfigure(0, weight=1)
        fields_tree_frame.columnconfigure(0, weight=1)

        self.field_tree = ttk.Treeview(
            fields_tree_frame, columns=("Rand", "Type", "Name", "Default"), show="headings", height=12
        )
        self.field_tree.heading("Rand", text="Rand")
        self.field_tree.heading("Type", text="Type")
        self.field_tree.heading("Name", text="Name")
        self.field_tree.heading("Default", text="Default")
        self.field_tree.column("Rand", width=70, stretch=False, anchor="center")
        self.field_tree.column("Type", width=170, stretch=False, anchor="w")
        self.field_tree.column("Name", width=220, stretch=True, anchor="w")
        self.field_tree.column("Default", width=120, stretch=False, anchor="w")

        field_y = ttk.Scrollbar(fields_tree_frame, orient="vertical", command=self.field_tree.yview)
        field_x = ttk.Scrollbar(fields_tree_frame, orient="horizontal", command=self.field_tree.xview)
        self.field_tree.configure(yscrollcommand=field_y.set, xscrollcommand=field_x.set)
        self.field_tree.grid(row=0, column=0, sticky="nsew")
        field_y.grid(row=0, column=1, sticky="ns")
        field_x.grid(row=1, column=0, sticky="ew")

        self.field_tree.bind("<Delete>", lambda _e: self.remove_selected_field())
        self.field_tree.bind("<Double-1>", lambda _e: self.edit_selected_field())

        constraints_frame = ttk.LabelFrame(panes, text="Constraints")
        constraints_frame.columnconfigure(0, weight=1)
        constraints_frame.rowconfigure(1, weight=1)
        panes.add(constraints_frame, weight=2)

        c_toolbar = ttk.Frame(constraints_frame)
        c_toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        ttk.Button(c_toolbar, text="Add", command=self.add_constraint_popup).pack(side="left", padx=(0, 8))
        ttk.Button(c_toolbar, text="Edit", command=self.edit_selected_constraint).pack(side="left", padx=(0, 8))
        ttk.Button(c_toolbar, text="Remove", command=self.remove_selected_constraint).pack(side="left", padx=(0, 8))
        ttk.Button(c_toolbar, text="Sync", command=self.sync_constraints).pack(side="left")

        c_tree_frame = ttk.Frame(constraints_frame)
        c_tree_frame.grid(row=1, column=0, sticky="nsew", padx=10)
        c_tree_frame.rowconfigure(0, weight=1)
        c_tree_frame.columnconfigure(0, weight=1)

        self.constraint_tree = ttk.Treeview(c_tree_frame, columns=("Name", "Body"), show="headings", height=8)
        self.constraint_tree.heading("Name", text="Name")
        self.constraint_tree.heading("Body", text="Body")
        self.constraint_tree.column("Name", width=140, stretch=False, anchor="w")
        self.constraint_tree.column("Body", width=320, stretch=True, anchor="w")

        c_y = ttk.Scrollbar(c_tree_frame, orient="vertical", command=self.constraint_tree.yview)
        c_x = ttk.Scrollbar(c_tree_frame, orient="horizontal", command=self.constraint_tree.xview)
        self.constraint_tree.configure(yscrollcommand=c_y.set, xscrollcommand=c_x.set)
        self.constraint_tree.grid(row=0, column=0, sticky="nsew")
        c_y.grid(row=0, column=1, sticky="ns")
        c_x.grid(row=1, column=0, sticky="ew")

        self.constraint_tree.bind("<Delete>", lambda _e: self.remove_selected_constraint())
        self.constraint_tree.bind("<Double-1>", lambda _e: self.edit_selected_constraint())

        ttk.Label(constraints_frame, text="Constraint Preview", font=("Segoe UI", 10, "bold")).grid(
            row=2, column=0, sticky="w", padx=10, pady=(8, 4)
        )
        self.constraint_preview = CodePreview(constraints_frame, height=7)
        self.constraint_preview.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.constraint_display = self.constraint_preview.text
        self.constraint_display.configure(state="disabled")

        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="Save Transaction", command=self.save_transaction).pack(side="left")
        ttk.Button(actions, text="Preview Class", command=self.preview_class).pack(side="right")
        row += 1

        preview_frame = ttk.LabelFrame(root, text="Class Preview")
        preview_frame.grid(row=row, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)

        preview = CodePreview(preview_frame, height=18)
        preview.grid(row=0, column=0, sticky="nsew")
        self.preview_box = preview.text

    def import_from_interface(self) -> None:
        interface = self.state.get("interface", {}) or {}
        signals = interface.get("signals", []) or []

        self.fields = []
        for sig in signals:
            try:
                width_int = int(str(sig.get("width", "1")))
                type_str = "bit" if width_int == 1 else f"bit [{width_int - 1}:0]"
            except Exception:
                type_str = f"bit {sig.get('width', '1')}"

            rand = sig.get("direction") == "input"
            self.fields.append(
                {
                    "rand": bool(rand),
                    "type": type_str,
                    "name": str(sig.get("name", "") or ""),
                    "default": "0",
                }
            )

        self.refresh_field_table()

    def refresh_field_table(self) -> None:
        flt = (self.field_filter.get() or "").strip().lower()
        self.field_tree.delete(*self.field_tree.get_children())

        for idx, field in enumerate(self.fields):
            rand_mark = "Yes" if field.get("rand") else ""
            type_str = str(field.get("type") or "")
            name = str(field.get("name") or "")
            default = str(field.get("default") or "")

            if flt and flt not in f"{rand_mark} {type_str} {name} {default}".lower():
                continue

            self.field_tree.insert("", "end", iid=f"f{idx}", values=(rand_mark, type_str, name, default))

    def refresh_constraint_table(self) -> None:
        self.constraint_tree.delete(*self.constraint_tree.get_children())
        for idx, c in enumerate(self.constraints):
            self.constraint_tree.insert("", "end", iid=f"c{idx}", values=(c.get("name", ""), c.get("body", "")))

    def update_constraint_display(self) -> None:
        self.constraint_display.configure(state="normal")
        self.constraint_display.delete("1.0", tk.END)

        if not self.constraints:
            self.constraint_display.insert(tk.END, "No active constraints defined.")
        else:
            for c in self.constraints:
                name = (c.get("name") or "").strip() or "c"
                body = (c.get("body") or "").strip()
                self.constraint_display.insert(tk.END, f"{name}: {body}\n")

        self.constraint_display.configure(state="disabled")

    def sync_constraints(self) -> None:
        self.refresh_constraint_table()
        self.update_constraint_display()
        messagebox.showinfo("Synced", "Constraints synced.", parent=self.winfo_toplevel())

    def add_field_popup(self) -> None:
        popup = tk.Toplevel(self)
        popup.title("Add Field")
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())

        rand_var = tk.BooleanVar(value=True)
        type_var = tk.StringVar(value="bit")
        name_var = tk.StringVar()
        default_var = tk.StringVar(value="0")

        body = ttk.Frame(popup, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        ttk.Checkbutton(body, text="Rand", variable=rand_var).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(body, text="Type").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=type_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="Name").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=name_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="Default").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=default_var).grid(row=3, column=1, sticky="ew", pady=4)

        def on_add():
            name_value = (name_var.get() or "").strip()
            if not name_value:
                messagebox.showwarning("Missing", "Field name is required.", parent=popup)
                return
            if not self._is_sv_identifier(name_value):
                messagebox.showwarning(
                    "Invalid", "Field name must be a valid SystemVerilog identifier.", parent=popup
                )
                return

            self.fields.append(
                {
                    "rand": bool(rand_var.get()),
                    "type": (type_var.get() or "bit").strip(),
                    "name": name_value,
                    "default": (default_var.get() or "0").strip(),
                }
            )
            self.refresh_field_table()
            popup.destroy()

        btns = ttk.Frame(body)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel", command=popup.destroy).pack(side="right")
        ttk.Button(btns, text="Add", command=on_add).pack(side="right", padx=(0, 8))

    def edit_selected_field(self) -> None:
        indices = self._get_selected_field_indices()
        if len(indices) != 1:
            messagebox.showwarning("Select", "Please select a single field to edit.", parent=self.winfo_toplevel())
            return

        index = indices[0]
        field = self.fields[index]

        popup = tk.Toplevel(self)
        popup.title("Edit Field")
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())

        rand_var = tk.BooleanVar(value=bool(field.get("rand")))
        type_var = tk.StringVar(value=str(field.get("type") or "bit"))
        name_var = tk.StringVar(value=str(field.get("name") or ""))
        default_var = tk.StringVar(value=str(field.get("default") or "0"))

        body = ttk.Frame(popup, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        ttk.Checkbutton(body, text="Rand", variable=rand_var).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(body, text="Type").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=type_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="Name").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=name_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="Default").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=default_var).grid(row=3, column=1, sticky="ew", pady=4)

        def on_edit():
            name_value = (name_var.get() or "").strip()
            if not name_value:
                messagebox.showwarning("Missing", "Field name is required.", parent=popup)
                return
            if not self._is_sv_identifier(name_value):
                messagebox.showwarning(
                    "Invalid", "Field name must be a valid SystemVerilog identifier.", parent=popup
                )
                return

            self.fields[index] = {
                "rand": bool(rand_var.get()),
                "type": (type_var.get() or "bit").strip(),
                "name": name_value,
                "default": (default_var.get() or "0").strip(),
            }
            self.refresh_field_table()
            popup.destroy()

        btns = ttk.Frame(body)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel", command=popup.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=on_edit).pack(side="right", padx=(0, 8))

    def remove_selected_field(self) -> None:
        indices = self._get_selected_field_indices()
        if not indices:
            return

        if not messagebox.askyesno(
            "Remove",
            f"Remove {len(indices)} selected field(s)?",
            parent=self.winfo_toplevel(),
        ):
            return

        for idx in sorted(indices, reverse=True):
            self.fields.pop(idx)

        self.refresh_field_table()

    def _constraint_body_editor(self, parent: ttk.Frame, *, initial: str = "") -> tuple[ttk.Frame, tk.Text]:
        frame = ttk.Frame(parent)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        text = code_text(frame, height=8)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        if initial:
            text.insert("1.0", initial)

        return frame, text

    def add_constraint_popup(self) -> None:
        popup = tk.Toplevel(self)
        popup.title("Add Constraint")
        popup.resizable(True, True)
        popup.minsize(520, 260)
        popup.transient(self.winfo_toplevel())

        name_var = tk.StringVar()

        body = ttk.Frame(popup, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="Name").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=name_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="Body").grid(row=1, column=0, sticky="nw", pady=4)

        editor_frame, body_text = self._constraint_body_editor(body)
        editor_frame.grid(row=1, column=1, sticky="nsew", pady=4)

        def on_add():
            name_value = (name_var.get() or "").strip()
            if not name_value:
                messagebox.showwarning("Missing", "Constraint name is required.", parent=popup)
                return
            if not self._is_sv_identifier(name_value):
                messagebox.showwarning(
                    "Invalid", "Constraint name must be a valid SystemVerilog identifier.", parent=popup
                )
                return

            body_value = (body_text.get("1.0", tk.END) or "").strip()
            if not body_value:
                messagebox.showwarning("Missing", "Constraint body is required.", parent=popup)
                return

            self.constraints.append({"name": name_value, "body": body_value})
            self.refresh_constraint_table()
            self.update_constraint_display()
            popup.destroy()

        btns = ttk.Frame(body)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel", command=popup.destroy).pack(side="right")
        ttk.Button(btns, text="Add", command=on_add).pack(side="right", padx=(0, 8))

    def edit_selected_constraint(self) -> None:
        indices = self._get_selected_constraint_indices()
        if len(indices) != 1:
            messagebox.showwarning(
                "Select", "Please select a single constraint to edit.", parent=self.winfo_toplevel()
            )
            return

        index = indices[0]
        c = self.constraints[index]

        popup = tk.Toplevel(self)
        popup.title("Edit Constraint")
        popup.resizable(True, True)
        popup.minsize(520, 260)
        popup.transient(self.winfo_toplevel())

        name_var = tk.StringVar(value=str(c.get("name") or ""))
        old_body = str(c.get("body") or "")

        body = ttk.Frame(popup, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="Name").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=name_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="Body").grid(row=1, column=0, sticky="nw", pady=4)

        editor_frame, body_text = self._constraint_body_editor(body, initial=old_body)
        editor_frame.grid(row=1, column=1, sticky="nsew", pady=4)

        def on_edit():
            name_value = (name_var.get() or "").strip()
            if not name_value:
                messagebox.showwarning("Missing", "Constraint name is required.", parent=popup)
                return
            if not self._is_sv_identifier(name_value):
                messagebox.showwarning(
                    "Invalid", "Constraint name must be a valid SystemVerilog identifier.", parent=popup
                )
                return

            body_value = (body_text.get("1.0", tk.END) or "").strip()
            if not body_value:
                messagebox.showwarning("Missing", "Constraint body is required.", parent=popup)
                return

            self.constraints[index] = {"name": name_value, "body": body_value}
            self.refresh_constraint_table()
            self.update_constraint_display()
            popup.destroy()

        btns = ttk.Frame(body)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel", command=popup.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=on_edit).pack(side="right", padx=(0, 8))

    def remove_selected_constraint(self) -> None:
        indices = self._get_selected_constraint_indices()
        if not indices:
            return

        if not messagebox.askyesno(
            "Remove",
            f"Remove {len(indices)} selected constraint(s)?",
            parent=self.winfo_toplevel(),
        ):
            return

        for idx in sorted(indices, reverse=True):
            self.constraints.pop(idx)

        self.refresh_constraint_table()
        self.update_constraint_display()

    def preview_class(self) -> None:
        class_name = (self.class_name.get() or "").strip() or "txn_item"
        base = (self.base_class.get() or "").strip() or "uvm_sequence_item"

        if not self._is_sv_identifier(class_name):
            messagebox.showwarning(
                "Invalid",
                "Class name must be a valid SystemVerilog identifier.",
                parent=self.winfo_toplevel(),
            )
            return

        code = f"class {class_name} extends {base};\n"
        code += f"  `uvm_object_utils({class_name})\n\n"

        for field in self.fields:
            rand_str = "rand " if field.get("rand") else ""
            type_str = str(field.get("type") or "bit")
            name = str(field.get("name") or "field")
            code += f"  {rand_str}{type_str} {name};\n"

        if self.constraints:
            code += "\n"
            for c in self.constraints:
                cname = str(c.get("name") or "c").strip() or "c"
                body = (c.get("body") or "").strip().rstrip(";")
                if body:
                    code += f"  constraint {cname} {{ {body}; }}\n"

        code += "\n"
        for field in self.fields:
            name = str(field.get("name") or "field")
            code += f"  `uvm_field_int({name}, UVM_ALL_ON)\n"

        code += f"\n  function new(string name = \"{class_name}\");\n"
        code += "    super.new(name);\n"
        code += "  endfunction\n\n"
        code += f"endclass : {class_name}\n"

        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert(tk.END, code)

    def save_transaction(self) -> None:
        class_name = (self.class_name.get() or "").strip()
        base = (self.base_class.get() or "").strip() or "uvm_sequence_item"

        if not class_name or not self._is_sv_identifier(class_name):
            messagebox.showwarning(
                "Invalid",
                "Class name must be a valid SystemVerilog identifier.",
                parent=self.winfo_toplevel(),
            )
            return

        data = {
            "class_name": class_name,
            "base_class": base,
            "fields": self.fields,
            "constraints": self.constraints,
        }
        self.state.set("transaction", data)

        messagebox.showinfo("Saved", "Transaction class saved successfully!", parent=self.winfo_toplevel())
        if hasattr(self.master.master, "footer"):
            self.master.master.footer.mark_done("transaction")
