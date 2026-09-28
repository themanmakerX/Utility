from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, ttk

from ..utils.generator import generate_files
from ..utils.state import StateManager
from ..utils.ui import CodePreview, ScrollableFrame, section_title


class EnvironmentClassForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = scroller.content

        self.state = StateManager.get_instance()

        self.env_name = tk.StringVar(value="env")
        self.include_agent = tk.BooleanVar(value=True)
        self.include_scoreboard = tk.BooleanVar(value=True)

        self.info_text = tk.StringVar(value="")

        self._load_from_state()
        self.build_ui()

        self.state.subscribe_key("agent", lambda *_: self._refresh_info_and_preview())
        self.state.subscribe_key("scoreboard", lambda *_: self._refresh_info_and_preview())
        self.state.subscribe_key("custom_files", lambda *_: self._refresh_info_and_preview())
        self.state.subscribe_key("custom_files_enabled", lambda *_: self._refresh_info_and_preview())

        self.include_agent.trace_add("write", lambda *_: self._refresh_info_and_preview())
        self.include_scoreboard.trace_add("write", lambda *_: self._refresh_info_and_preview())

        self._refresh_info_and_preview()

    def _load_from_state(self) -> None:
        env = self.state.get("environment", {}) or {}
        if isinstance(env, dict) and env:
            self.env_name.set(str(env.get("name") or "env"))
            self.include_agent.set(bool(env.get("include_agent", True)))
            self.include_scoreboard.set(bool(env.get("include_scoreboard", True)))

    def _is_sv_identifier(self, value: str) -> bool:
        value = (value or "").strip()
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value))

    def _agent_name(self) -> str:
        agent = self.state.get("agent", {}) or {}
        return str(agent.get("agent_name") or "my_agent")

    def _sb_name(self) -> str:
        sb = self.state.get("scoreboard", {}) or {}
        return str(sb.get("name") or "my_scoreboard")

    def _agent_has_monitor(self) -> bool:
        agent = self.state.get("agent", {}) or {}
        include = agent.get("include_components")
        if not isinstance(include, dict):
            include = agent.get("components")
        if isinstance(include, dict):
            return bool(include.get("monitor", True))
        return True

    def _refresh_info_and_preview(self) -> None:
        msgs: list[str] = []

        if self.include_scoreboard.get() and not self.state.get("scoreboard", {}):
            msgs.append("Scoreboard is not configured yet. Environment will still compile, but scoreboard may be placeholder.")

        if self.include_agent.get() and not self.state.get("agent", {}):
            msgs.append("Agent is not configured yet. Environment will still compile, but agent may be placeholder.")

        if self.include_agent.get() and self.include_scoreboard.get():
            if not self._agent_has_monitor():
                msgs.append("Agent Monitor is disabled, so auto-connect to scoreboard is skipped.")
            else:
                msgs.append("Auto-connect: agent.mon.ap -> sb.ap")

        self.info_text.set("  ".join(msgs))
        self.refresh_preview()

    def build_ui(self) -> None:
        root = self.content
        root.columnconfigure(0, weight=1)

        row = 0
        section_title(root, "Environment Class").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        basics = ttk.LabelFrame(root, text="Basics")
        basics.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        basics.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(basics, text="Environment Class Name").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.env_name).grid(
            row=0, column=1, sticky="ew", padx=10, pady=(10, 6)
        )

        include = ttk.LabelFrame(root, text="Include Components")
        include.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        row += 1

        ttk.Checkbutton(include, text="Include Agent", variable=self.include_agent).grid(
            row=0, column=0, sticky="w", padx=10, pady=8
        )
        ttk.Checkbutton(include, text="Include Scoreboard", variable=self.include_scoreboard).grid(
            row=0, column=1, sticky="w", padx=10, pady=8
        )

        ttk.Label(root, textvariable=self.info_text, foreground="#8aa4ff").grid(
            row=row, column=0, sticky="w", pady=(0, 10)
        )
        row += 1

        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="Save Environment", command=self.save_environment).pack(side="left")
        ttk.Button(actions, text="Save Preview as Override", command=self.save_preview_override).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Revert Override", command=self.revert_preview_override).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Preview Class", command=self.refresh_preview).pack(side="right")
        row += 1

        preview_frame = ttk.LabelFrame(root, text="Generated Environment (Editable)")
        preview_frame.grid(row=row, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)

        preview = CodePreview(preview_frame, height=24)
        preview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.preview_box = preview.text

    def _effective_environment_state(self) -> dict:
        return {
            "name": (self.env_name.get() or "").strip() or "env",
            "include_agent": bool(self.include_agent.get()),
            "include_scoreboard": bool(self.include_scoreboard.get()),
        }

    def save_environment(self) -> None:
        name = (self.env_name.get() or "").strip()
        if not name or not self._is_sv_identifier(name):
            messagebox.showwarning(
                "Invalid",
                "Environment class name must be a valid SystemVerilog identifier.",
                parent=self.winfo_toplevel(),
            )
            return

        data = self._effective_environment_state()
        self.state.set("environment", data)
        messagebox.showinfo("Saved", "Environment configuration saved successfully!", parent=self.winfo_toplevel())
        if hasattr(self.master.master, "footer"):
            self.master.master.footer.mark_done("environment")

    def refresh_preview(self) -> None:
        temp = self.state.get_all()
        temp["environment"] = self._effective_environment_state()

        try:
            files, _warnings = generate_files(temp)
            content = files.get(Path("src/environment.sv"), "")
        except Exception as exc:
            content = f"// Preview failed:\n// {exc}\n"

        custom_files = self.state.get("custom_files", {}) or {}
        enabled = bool(self.state.get("custom_files_enabled", True))
        override = None
        if enabled and isinstance(custom_files, dict):
            override = custom_files.get("src/environment.sv")

        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert(tk.END, str(override) if override is not None else content)

    def save_preview_override(self) -> None:
        text = (self.preview_box.get("1.0", tk.END) or "").rstrip() + "\n"
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict):
            custom_files = {}
        custom_files["src/environment.sv"] = text
        self.state.set("custom_files", custom_files)
        self.state.set("custom_files_enabled", True)
        messagebox.showinfo("Saved", "Override saved for src/environment.sv", parent=self.winfo_toplevel())

    def revert_preview_override(self) -> None:
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict) or "src/environment.sv" not in custom_files:
            return
        if not messagebox.askyesno(
            "Revert",
            "Revert saved override for src/environment.sv?",
            parent=self.winfo_toplevel(),
        ):
            return
        custom_files.pop("src/environment.sv", None)
        self.state.set("custom_files", custom_files)
        self.refresh_preview()

