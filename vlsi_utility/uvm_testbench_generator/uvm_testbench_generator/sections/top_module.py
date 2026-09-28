from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..utils.generator import generate_files
from ..utils.state import StateManager
from ..utils.ui import CodePreview, ScrollableFrame, section_title


def _strip_sv_comments(text: str) -> str:
    # remove /* */ then // comments
    text = re.sub(r"/\\*.*?\\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    return text


def _extract_module_name(text: str) -> str | None:
    m = re.search(r"\\bmodule\\s+([A-Za-z_][A-Za-z0-9_]*)\\b", _strip_sv_comments(text))
    return m.group(1) if m else None


def _extract_module_ports(text: str, module_name: str) -> list[str]:
    cleaned = _strip_sv_comments(text)
    m = re.search(
        rf"\\bmodule\\s+{re.escape(module_name)}\\b\\s*(?:#\\s*\\(.*?\\)\\s*)?\\((.*?)\\)\\s*;",
        cleaned,
        flags=re.S,
    )
    if not m:
        return []
    block = m.group(1)

    # split on commas at top-level (good enough for common headers)
    parts = [p.strip() for p in block.replace("\\n", " ").split(",") if p.strip()]
    ports: list[str] = []
    for part in parts:
        tokens = [t for t in re.split(r"\\s+", part.strip()) if t]
        if not tokens:
            continue
        name = tokens[-1]
        name = name.strip().rstrip(")")
        name = re.sub(r"\\[[^\\]]+\\]$", "", name).strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            ports.append(name)
    # unique, keep order
    seen = set()
    out: list[str] = []
    for p in ports:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


@dataclass(frozen=True)
class DutAnalysis:
    module_name: str = ""
    ports: tuple[str, ...] = ()


class TopModuleForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        scroller = ScrollableFrame(self, padding=12)
        scroller.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = scroller.content

        self.state = StateManager.get_instance()

        self.top_name = tk.StringVar(value="top_tb")
        self.dut_path = tk.StringVar(value="")
        self.dut_module = tk.StringVar(value="")

        self.interface_name = tk.StringVar(value="my_if")
        self.test_class = tk.StringVar(value="base_test")

        self.info_text = tk.StringVar(value="")
        self._analysis = DutAnalysis()

        self._load_from_state()
        self.build_ui()

        self.state.subscribe_key("interface", lambda *_: self._refresh_info_and_preview())
        self.state.subscribe_key("test", lambda *_: self._refresh_info_and_preview())
        self.state.subscribe_key("custom_files", lambda *_: self.refresh_preview())
        self.state.subscribe_key("custom_files_enabled", lambda *_: self.refresh_preview())

        self._refresh_info_and_preview()

    def _load_from_state(self) -> None:
        top = self.state.get("top", {}) or {}
        if isinstance(top, dict) and top:
            self.top_name.set(str(top.get("name") or "top_tb"))
            self.dut_path.set(str(top.get("dut_path") or ""))
            self.dut_module.set(str(top.get("dut_module") or ""))

        interface = self.state.get("interface", {}) or {}
        self.interface_name.set(str(interface.get("name") or "my_if"))

        test = self.state.get("test", {}) or {}
        self.test_class.set(str(test.get("name") or "base_test"))

        if self.dut_path.get() and not self.dut_module.get():
            self.analyze_dut()

    def build_ui(self) -> None:
        root = self.content
        root.columnconfigure(0, weight=1)

        row = 0
        section_title(root, "Top Module").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        basics = ttk.LabelFrame(root, text="Basics")
        basics.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        basics.columnconfigure(1, weight=1)
        basics.columnconfigure(3, weight=1)
        row += 1

        ttk.Label(basics, text="Top Module Name").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        ttk.Entry(basics, textvariable=self.top_name).grid(row=0, column=1, sticky="ew", padx=10, pady=(10, 6))

        ttk.Label(basics, text="DUT File Path").grid(row=1, column=0, sticky="w", padx=10, pady=6)
        ttk.Entry(basics, textvariable=self.dut_path).grid(row=1, column=1, sticky="ew", padx=10, pady=6)
        ttk.Button(basics, text="Browse", command=self.browse_dut).grid(row=1, column=2, sticky="w", padx=(0, 10), pady=6)
        ttk.Button(basics, text="Analyze", command=self.analyze_dut).grid(row=1, column=3, sticky="w", padx=(0, 10), pady=6)

        ttk.Label(basics, text="Detected DUT Module").grid(row=2, column=0, sticky="w", padx=10, pady=(6, 10))
        ttk.Entry(basics, textvariable=self.dut_module).grid(row=2, column=1, sticky="ew", padx=10, pady=(6, 10))

        refs = ttk.LabelFrame(root, text="Detected References")
        refs.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        refs.columnconfigure(1, weight=1)
        refs.columnconfigure(3, weight=1)
        row += 1

        ttk.Label(refs, text="Interface").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        ttk.Label(refs, textvariable=self.interface_name).grid(row=0, column=1, sticky="w", padx=10, pady=8)
        ttk.Label(refs, text="Test").grid(row=0, column=2, sticky="w", padx=10, pady=8)
        ttk.Label(refs, textvariable=self.test_class).grid(row=0, column=3, sticky="w", padx=10, pady=8)

        ttk.Label(root, textvariable=self.info_text, foreground="#8aa4ff").grid(row=row, column=0, sticky="w", pady=(0, 10))
        row += 1

        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="Save Top Module", command=self.save_top).pack(side="left")
        ttk.Button(actions, text="Preview", command=self.refresh_preview).pack(side="left", padx=(8, 0))
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(actions, text="Save Preview as Override", command=self.save_preview_override).pack(side="left")
        ttk.Button(actions, text="Revert Override", command=self.revert_preview_override).pack(side="left", padx=(8, 0))
        row += 1

        preview_frame = ttk.LabelFrame(root, text="Generated Top Module (Editable)")
        preview_frame.grid(row=row, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        root.rowconfigure(row, weight=1)

        preview = CodePreview(preview_frame, height=26)
        preview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.preview_box = preview.text

    def browse_dut(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("SystemVerilog", "*.sv"), ("All Files", "*.*")])
        if not file_path:
            return
        self.dut_path.set(file_path)
        self.analyze_dut()

    def analyze_dut(self) -> None:
        path = (self.dut_path.get() or "").strip()
        if not path:
            self._analysis = DutAnalysis()
            self._refresh_info_and_preview()
            return

        p = Path(path)
        if not p.exists():
            messagebox.showwarning("Missing", "DUT file not found.", parent=self.winfo_toplevel())
            self._analysis = DutAnalysis()
            self._refresh_info_and_preview()
            return

        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to read DUT file:\n{exc}", parent=self.winfo_toplevel())
            self._analysis = DutAnalysis()
            self._refresh_info_and_preview()
            return

        module_name = (self.dut_module.get() or "").strip() or (_extract_module_name(text) or "")
        ports: list[str] = []
        if module_name:
            ports = _extract_module_ports(text, module_name)

        self.dut_module.set(module_name)
        self._analysis = DutAnalysis(module_name=module_name, ports=tuple(ports))
        self._refresh_info_and_preview()

    def _refresh_info_and_preview(self) -> None:
        interface = self.state.get("interface", {}) or {}
        self.interface_name.set(str(interface.get("name") or "my_if"))
        test = self.state.get("test", {}) or {}
        self.test_class.set(str(test.get("name") or "base_test"))

        msgs: list[str] = []

        sigs = interface.get("signals", []) or []
        sig_names = [str(s.get("name") or "").strip() for s in sigs if isinstance(s, dict)]
        sig_names = [n for n in sig_names if n]
        sig_set = set(sig_names)

        if self._analysis.ports:
            ports = list(self._analysis.ports)
            matched = [p for p in ports if p in sig_set or p in {(interface.get("clock") or "").strip(), (interface.get("reset") or "").strip()}]
            missing = [p for p in ports if p not in matched]
            msgs.append(f"DUT ports: {len(ports)}  matched: {len(matched)}  missing: {len(missing)}")
        else:
            if (self.dut_path.get() or "").strip():
                msgs.append("DUT ports not detected (generator will connect by interface signal names).")
            else:
                msgs.append("Select a DUT file to enable port detection and smarter connections.")

        self.info_text.set("  ".join(msgs))
        self.refresh_preview()

    def _effective_top_state(self) -> dict:
        return {
            "name": (self.top_name.get() or "").strip() or "top_tb",
            "dut_module": (self.dut_module.get() or "").strip(),
            "dut_path": (self.dut_path.get() or "").strip(),
            "interface": (self.interface_name.get() or "").strip() or "my_if",
            "test": (self.test_class.get() or "").strip() or "base_test",
        }

    def save_top(self) -> None:
        data = self._effective_top_state()
        self.state.set("top", data)
        messagebox.showinfo("Saved", "Top module configuration saved.", parent=self.winfo_toplevel())
        if hasattr(self.master.master, "footer"):
            self.master.master.footer.mark_done("top")

    def refresh_preview(self) -> None:
        temp = self.state.get_all()
        temp["top"] = self._effective_top_state()
        try:
            files, _warnings = generate_files(temp)
            content = files.get(Path("src/top.sv"), "")
        except Exception as exc:
            content = f"// Preview failed:\n// {exc}\n"

        custom_files = self.state.get("custom_files", {}) or {}
        enabled = bool(self.state.get("custom_files_enabled", True))
        override = None
        if enabled and isinstance(custom_files, dict):
            override = custom_files.get("src/top.sv")

        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert(tk.END, str(override) if override is not None else content)

    def save_preview_override(self) -> None:
        text = (self.preview_box.get("1.0", tk.END) or "").rstrip() + "\n"
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict):
            custom_files = {}
        custom_files["src/top.sv"] = text
        self.state.set("custom_files", custom_files)
        self.state.set("custom_files_enabled", True)
        messagebox.showinfo("Saved", "Override saved for src/top.sv", parent=self.winfo_toplevel())

    def revert_preview_override(self) -> None:
        custom_files = self.state.get("custom_files", {}) or {}
        if not isinstance(custom_files, dict) or "src/top.sv" not in custom_files:
            return
        if not messagebox.askyesno(
            "Revert",
            "Revert saved override for src/top.sv?",
            parent=self.winfo_toplevel(),
        ):
            return
        custom_files.pop("src/top.sv", None)
        self.state.set("custom_files", custom_files)
        self.refresh_preview()

