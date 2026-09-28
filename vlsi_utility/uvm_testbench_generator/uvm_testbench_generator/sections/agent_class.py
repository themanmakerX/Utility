from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from ..utils.generator import generate_files
from ..utils.state import StateManager
from ..utils.ui import CodeNotebook, ScrollableFrame, section_title


class AgentClassForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = scroller.content

        self.state = StateManager.get_instance()

        self.agent_name = tk.StringVar(value="my_agent")
        self.agent_type = tk.StringVar(value="active")
        self.txn_class = tk.StringVar(value="txn_item")

        self.include_sequencer = tk.BooleanVar(value=True)
        self.include_driver = tk.BooleanVar(value=True)
        self.include_monitor = tk.BooleanVar(value=True)

        self.use_custom_code = tk.BooleanVar(value=False)
        self.info_text = tk.StringVar(value="")

        self._load_from_state()
        self.build_ui()

        self.agent_type.trace_add("write", lambda *_: self._apply_intelligence())
        self.include_driver.trace_add("write", lambda *_: self._apply_intelligence())
        self.include_sequencer.trace_add("write", lambda *_: self._apply_intelligence())
        self.include_monitor.trace_add("write", lambda *_: self._apply_intelligence())
        self.use_custom_code.trace_add("write", lambda *_: self._refresh_previews())

        self.state.subscribe_key("transaction", self._on_transaction_change)

        self._apply_intelligence()
        self._refresh_previews()

    def _load_from_state(self) -> None:
        txn = self.state.get("transaction", {}) or {}
        self.txn_class.set(str(txn.get("class_name") or "txn_item"))

        agent = self.state.get("agent", {}) or {}
        if isinstance(agent, dict) and agent:
            self.agent_name.set(str(agent.get("agent_name") or "my_agent"))
            self.agent_type.set(str(agent.get("type") or agent.get("agent_type") or "active"))
            self.txn_class.set(str(agent.get("transaction") or self.txn_class.get() or "txn_item"))

            components = agent.get("include_components")
            if not isinstance(components, dict):
                components = agent.get("components")
            if isinstance(components, dict):
                self.include_sequencer.set(bool(components.get("sequencer", True)))
                self.include_driver.set(bool(components.get("driver", True)))
                self.include_monitor.set(bool(components.get("monitor", True)))

            self.use_custom_code.set(bool(agent.get("use_custom_code", False)))

    def build_ui(self) -> None:
        root = self.content
        root.columnconfigure(0, weight=1)

        row = 0
        section_title(root, "Agent Class Configuration").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        basics = ttk.LabelFrame(root, text="Basics")
        basics.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        basics.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(basics, text="Agent Class Name").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.agent_name).grid(
            row=0, column=1, sticky="ew", padx=10, pady=(10, 6)
        )

        ttk.Label(basics, text="Agent Type").grid(row=1, column=0, sticky="w", padx=10, pady=6)
        ttk.Combobox(basics, textvariable=self.agent_type, values=["active", "passive"], state="readonly").grid(
            row=1, column=1, sticky="w", padx=10, pady=6
        )

        ttk.Label(basics, text="Transaction Class").grid(row=2, column=0, sticky="w", padx=10, pady=(6, 10))
        ttk.Label(basics, textvariable=self.txn_class).grid(row=2, column=1, sticky="w", padx=10, pady=(6, 10))

        include = ttk.LabelFrame(root, text="Included Components")
        include.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        row += 1

        self.cb_sequencer = ttk.Checkbutton(include, text="Sequencer", variable=self.include_sequencer)
        self.cb_driver = ttk.Checkbutton(include, text="Driver", variable=self.include_driver)
        self.cb_monitor = ttk.Checkbutton(include, text="Monitor", variable=self.include_monitor)

        self.cb_sequencer.grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.cb_driver.grid(row=0, column=1, sticky="w", padx=10, pady=8)
        self.cb_monitor.grid(row=0, column=2, sticky="w", padx=10, pady=8)

        info = ttk.Label(root, textvariable=self.info_text, foreground="#8aa4ff")
        info.grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(actions, text="Save Agent", command=self.save_agent).pack(side="left")
        ttk.Button(actions, text="Preview", command=self._refresh_previews).pack(side="left", padx=(8, 0))
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(actions, text="Save Edits", command=self.save_edited_previews).pack(side="left")
        ttk.Button(actions, text="Revert Tab", command=self.revert_current_tab).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Revert All", command=self.revert_all_tabs).pack(side="left", padx=(8, 0))
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Checkbutton(
            actions,
            text="Use saved custom code at generation",
            variable=self.use_custom_code,
        ).pack(side="left")
        row += 1

        preview_frame = ttk.LabelFrame(root, text="Preview (Editable)")
        preview_frame.grid(row=row, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)

        self.notebook = CodeNotebook(preview_frame, height=18)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _on_transaction_change(self, _key, value, _all_state) -> None:
        if isinstance(value, dict):
            self.txn_class.set(str(value.get("class_name") or "txn_item"))
            self._refresh_previews()

    def _apply_intelligence(self) -> None:
        info: list[str] = []

        if self.agent_type.get() == "passive":
            if self.include_driver.get() or self.include_sequencer.get():
                info.append("Passive agent: Driver/Sequencer are disabled automatically.")
            self.include_driver.set(False)
            self.include_sequencer.set(False)
            if not self.include_monitor.get():
                self.include_monitor.set(True)

            self.cb_driver.configure(state="disabled")
            self.cb_sequencer.configure(state="disabled")
        else:
            self.cb_driver.configure(state="normal")
            self.cb_sequencer.configure(state="normal")

            if self.include_driver.get() and not self.include_sequencer.get():
                info.append("Tip: Driver without Sequencer means you must connect sequences manually.")
            if self.include_sequencer.get() and not self.include_driver.get():
                info.append("Tip: Sequencer without Driver is uncommon unless you connect a custom driver elsewhere.")
            if not self.include_monitor.get():
                info.append("Monitor is usually useful even for active agents (coverage/scoreboard).")

        self.info_text.set("  ".join(info))
        self._refresh_previews()

    def _effective_agent_state(self) -> dict:
        return {
            "agent_name": (self.agent_name.get() or "").strip() or "my_agent",
            "type": (self.agent_type.get() or "active").strip(),
            "transaction": (self.txn_class.get() or "txn_item").strip(),
            "include_components": {
                "sequencer": bool(self.include_sequencer.get()),
                "driver": bool(self.include_driver.get()),
                "monitor": bool(self.include_monitor.get()),
            },
            "use_custom_code": bool(self.use_custom_code.get()),
        }

    def save_agent(self) -> None:
        data = self._effective_agent_state()
        # Back-compat for older code paths
        data["agent_type"] = data["type"]
        data["components"] = dict(data["include_components"])

        self.state.set("agent", data)
        messagebox.showinfo("Saved", "Agent configuration saved successfully!", parent=self.winfo_toplevel())
        if hasattr(self.master.master, "footer"):
            self.master.master.footer.mark_done("agent")

    def _refresh_previews(self) -> None:
        tabs = ["Agent"]
        if self.include_driver.get():
            tabs.append("Driver")
        if self.include_monitor.get():
            tabs.append("Monitor")
        if self.include_sequencer.get():
            tabs.append("Sequencer")

        self.notebook.set_tabs(tabs)

        # Render using the real generator so preview matches generation.
        temp_state = self.state.get_all()
        temp_state["agent"] = self._effective_agent_state()

        try:
            files, _warnings = generate_files(temp_state)
        except Exception as exc:
            for tab in tabs:
                w = self.notebook.get_text_widget(tab)
                if w is None:
                    continue
                w.delete("1.0", tk.END)
                w.insert(tk.END, f"// Preview failed:\n// {exc}\n")
            return

        agent_code = self.state.get("agent_code", {}) or {}
        use_custom = bool(self.use_custom_code.get())

        mapping = {
            "Agent": Path("src/agent.sv"),
            "Driver": Path("src/driver.sv"),
            "Monitor": Path("src/monitor.sv"),
            "Sequencer": Path("src/sequencer.sv"),
        }
        agent_key_map = {"Agent": "agent", "Driver": "driver", "Monitor": "monitor", "Sequencer": "sequencer"}

        for tab in tabs:
            path = mapping.get(tab)
            w = self.notebook.get_text_widget(tab)
            if w is None:
                continue

            w.delete("1.0", tk.END)
            key = agent_key_map.get(tab, "")
            if use_custom and key and isinstance(agent_code, dict) and agent_code.get(key):
                w.insert(tk.END, str(agent_code.get(key)))
            else:
                content = files.get(path)
                if content is None:
                    w.insert(tk.END, f"// {path.as_posix()} not generated for current settings.\n")
                else:
                    w.insert(tk.END, content)

    def save_edited_previews(self) -> None:
        code: dict[str, str] = {}
        for tab, key in [("Agent", "agent"), ("Driver", "driver"), ("Monitor", "monitor"), ("Sequencer", "sequencer")]:
            w = self.notebook.get_text_widget(tab)
            if w is None:
                continue
            text = (w.get("1.0", tk.END) or "").strip()
            if text:
                code[key] = text

        self.state.set("agent_code", code)
        self.use_custom_code.set(True)
        self.save_agent()
        messagebox.showinfo("Saved", "Edited code saved. Generation will use custom agent code.", parent=self.winfo_toplevel())

    def revert_current_tab(self) -> None:
        current = self.notebook.current_tab_name()
        if not current:
            return
        key_map = {"Agent": "agent", "Driver": "driver", "Monitor": "monitor", "Sequencer": "sequencer"}
        key = key_map.get(current)
        if not key:
            return

        agent_code = self.state.get("agent_code", {}) or {}
        if not isinstance(agent_code, dict):
            agent_code = {}
        if key in agent_code:
            agent_code.pop(key, None)
            self.state.set("agent_code", agent_code)
        self._refresh_previews()

    def revert_all_tabs(self) -> None:
        self.state.set("agent_code", {})
        self.use_custom_code.set(False)
        self.save_agent()
        self._refresh_previews()

