from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, ttk

from ..utils.generator import generate_files
from ..utils.state import StateManager
from ..utils.ui import CodePreview, ScrollableFrame, section_title


class TestClassForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = scroller.content

        self.state = StateManager.get_instance()

        self.test_name = tk.StringVar(value="base_test")
        self.base_class = tk.StringVar(value="uvm_test")
        self.create_env = tk.BooleanVar(value=True)

        self.start_sequence = tk.BooleanVar(value=True)
        self.sequence_name = tk.StringVar(value="")
        self.raise_objection = tk.BooleanVar(value=True)
        self.print_topology = tk.BooleanVar(value=True)

        self.info_text = tk.StringVar(value="")

        self._load_from_state()
        self.build_ui()

        self.state.subscribe_key("environment", lambda *_: self._refresh_info_and_preview())
        self.state.subscribe_key("agent", lambda *_: self._refresh_info_and_preview())
        self.state.subscribe_key("sequence", lambda *_: self._refresh_info_and_preview())
        self.state.subscribe_key("custom_files", lambda *_: self.refresh_preview())
        self.state.subscribe_key("custom_files_enabled", lambda *_: self.refresh_preview())

        self.create_env.trace_add("write", lambda *_: self._refresh_info_and_preview())
        self.start_sequence.trace_add("write", lambda *_: self._refresh_info_and_preview())
        self.raise_objection.trace_add("write", lambda *_: self.refresh_preview())
        self.print_topology.trace_add("write", lambda *_: self.refresh_preview())

        self._refresh_info_and_preview()

    def _is_sv_identifier(self, value: str) -> bool:
        value = (value or "").strip()
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value))

    def _env_name(self) -> str:
        env = self.state.get("environment", {}) or {}
        return str(env.get("name") or "env")

    def _sequence_name_default(self) -> str:
        seq = self.state.get("sequence", {}) or {}
        return str(seq.get("name") or "my_sequence")

    def _agent_has_sequencer(self) -> bool:
        agent = self.state.get("agent", {}) or {}
        include = agent.get("include_components")
        if not isinstance(include, dict):
            include = agent.get("components")
        if isinstance(include, dict):
            return bool(include.get("sequencer", True))
        return True

    def _load_from_state(self) -> None:
        test = self.state.get("test", {}) or {}
        if not isinstance(test, dict) or not test:
            return

        self.test_name.set(str(test.get("name") or "base_test"))
        self.base_class.set(str(test.get("base_class") or "uvm_test"))
        self.create_env.set(bool(test.get("create_env", True)))
        self.start_sequence.set(bool(test.get("start_sequence", test.get("start_default_sequence", True))))
        self.sequence_name.set(str(test.get("sequence_name") or test.get("default_sequence") or ""))
        self.raise_objection.set(bool(test.get("raise_objection", True)))
        self.print_topology.set(bool(test.get("print_topology", True)))

    def build_ui(self) -> None:
        root = self.content
        root.columnconfigure(0, weight=1)

        row = 0
        section_title(root, "UVM Test Class").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        basics = ttk.LabelFrame(root, text="Basics")
        basics.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        basics.columnconfigure(1, weight=1)
        basics.columnconfigure(3, weight=1)
        row += 1

        ttk.Label(basics, text="Test Class Name").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.test_name).grid(
            row=0, column=1, sticky="ew", padx=10, pady=(10, 6)
        )

        ttk.Label(basics, text="Base Class").grid(row=0, column=2, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.base_class).grid(
            row=0, column=3, sticky="ew", padx=10, pady=(10, 6)
        )

        env_frame = ttk.LabelFrame(root, text="Environment")
        env_frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        env_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Checkbutton(env_frame, text="Create environment instance", variable=self.create_env).grid(
            row=0, column=0, sticky="w", padx=10, pady=8
        )
        ttk.Label(env_frame, text="Environment Class").grid(row=0, column=1, sticky="e", padx=(10, 8), pady=8)
        ttk.Label(env_frame, text=self._env_name()).grid(row=0, column=2, sticky="w", padx=(0, 10), pady=8)

        seq_frame = ttk.LabelFrame(root, text="Sequence Startup (Intelligent)")
        seq_frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        seq_frame.columnconfigure(2, weight=1)
        row += 1

        ttk.Checkbutton(seq_frame, text="Start a sequence in run_phase", variable=self.start_sequence).grid(
            row=0, column=0, sticky="w", padx=10, pady=8
        )
        ttk.Label(seq_frame, text="Sequence Class").grid(row=0, column=1, sticky="w", padx=(12, 8), pady=8)
        ttk.Entry(seq_frame, textvariable=self.sequence_name).grid(
            row=0, column=2, sticky="ew", padx=(0, 10), pady=8
        )

        extras = ttk.Frame(seq_frame)
        extras.grid(row=1, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 8))
        ttk.Checkbutton(extras, text="Raise/drop objection around sequence", variable=self.raise_objection).pack(
            side="left"
        )
        ttk.Checkbutton(extras, text="Print topology", variable=self.print_topology).pack(side="left", padx=(16, 0))

        ttk.Label(root, textvariable=self.info_text, foreground="#8aa4ff").grid(
            row=row, column=0, sticky="w", pady=(0, 10)
        )
        row += 1

        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="Save Test", command=self.save_test).pack(side="left")
        ttk.Button(actions, text="Save Preview as Override", command=self.save_preview_override).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Revert Override", command=self.revert_preview_override).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Preview Class", command=self.refresh_preview).pack(side="right")
        row += 1

        preview_frame = ttk.LabelFrame(root, text="Generated Test (Editable)")
        preview_frame.grid(row=row, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)

        preview = CodePreview(preview_frame, height=26)
        preview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.preview_box = preview.text

    def _refresh_info_and_preview(self) -> None:
        msgs: list[str] = []

        if self.start_sequence.get():
            if not self._agent_has_sequencer():
                msgs.append("Agent Sequencer is disabled. Sequence start will be skipped in generated code.")
            if not (self.sequence_name.get() or self._sequence_name_default()):
                msgs.append("No sequence configured yet.")

        self.info_text.set("  ".join(msgs))
        self.refresh_preview()

    def _effective_test_state(self) -> dict:
        seq_name = (self.sequence_name.get() or "").strip()
        if not seq_name:
            seq_name = self._sequence_name_default()

        return {
            "name": (self.test_name.get() or "").strip() or "base_test",
            "base_class": (self.base_class.get() or "").strip() or "uvm_test",
            "create_env": bool(self.create_env.get()),
            "start_sequence": bool(self.start_sequence.get()),
            "sequence_name": seq_name,
            "raise_objection": bool(self.raise_objection.get()),
            "print_topology": bool(self.print_topology.get()),
        }

    def save_test(self) -> None:
        name = (self.test_name.get() or "").strip()
        if not name or not self._is_sv_identifier(name):
            messagebox.showwarning(
                "Invalid",
                "Test class name must be a valid SystemVerilog identifier.",
                parent=self.winfo_toplevel(),
            )
            return

        data = self._effective_test_state()
        self.state.set("test", data)
        messagebox.showinfo("Saved", "Test class configuration saved successfully!", parent=self.winfo_toplevel())
        if hasattr(self.master.master, "footer"):
            self.master.master.footer.mark_done("test")

    def refresh_preview(self) -> None:
        temp = self.state.get_all()
        temp["test"] = self._effective_test_state()

        try:
            files, _warnings = generate_files(temp)
            content = files.get(Path("src/test.sv"), "")
        except Exception as exc:
            content = f"// Preview failed:\n// {exc}\n"

        custom_files = self.state.get("custom_files", {}) or {}
        enabled = bool(self.state.get("custom_files_enabled", True))
        override = None
        if enabled and isinstance(custom_files, dict):
            override = custom_files.get("src/test.sv")

        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert(tk.END, str(override) if override is not None else content)

    def save_preview_override(self) -> None:
        text = (self.preview_box.get("1.0", tk.END) or "").rstrip() + "\n"
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict):
            custom_files = {}
        custom_files["src/test.sv"] = text
        self.state.set("custom_files", custom_files)
        self.state.set("custom_files_enabled", True)
        messagebox.showinfo("Saved", "Override saved for src/test.sv", parent=self.winfo_toplevel())

    def revert_preview_override(self) -> None:
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict) or "src/test.sv" not in custom_files:
            return
        if not messagebox.askyesno(
            "Revert",
            "Revert saved override for src/test.sv?",
            parent=self.winfo_toplevel(),
        ):
            return
        custom_files.pop("src/test.sv", None)
        self.state.set("custom_files", custom_files)
        self.refresh_preview()

