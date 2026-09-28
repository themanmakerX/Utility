from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from .layout.header import Header
from .layout.footer import Footer
from .layout.sidebar import Sidebar

from .sections.project_details import ProjectDetailsForm
from .sections.interface_dut import InterfaceDUTForm
from .sections.transaction_class import TransactionClassForm
from .sections.agent_class import AgentClassForm
from .sections.scoreboard_class import ScoreboardClassForm
from .sections.environment_class import EnvironmentClassForm
from .sections.test_class import TestClassForm
from .sections.sequence_class import SequenceClassForm
from .sections.preview import PreviewPage
from .sections.top_module import TopModuleForm
from .sections.state_machine import StateMachineViewer
from .sections.dashboard import DashboardPage
from .utils.splashscreen import SplashScreen
from .utils.theme import apply_theme
from .utils.state import StateManager
from .utils.workflow import compute_module_statuses

__all__ = ["main"]


class TestbenchEcosystemApp(tk.Tk):
    SECTION_WIDGETS: dict[str, type[tk.Widget]] = {
        "dashboard": DashboardPage,
        "project_details": ProjectDetailsForm,
        "interface_dut": InterfaceDUTForm,
        "transaction_class": TransactionClassForm,
        "agent_class": AgentClassForm,
        "scoreboard_class": ScoreboardClassForm,
        "environment_class": EnvironmentClassForm,
        "test_class": TestClassForm,
        "top_module": TopModuleForm,
        "state_machine": StateMachineViewer,
        "sequence_class": SequenceClassForm,
        "preview": PreviewPage,
    }

    FOOTER_SECTION_KEYS: dict[str, str] = {
        "project_details": "project",
        "interface_dut": "interface",
        "transaction_class": "transaction",
        "agent_class": "agent",
        "scoreboard_class": "scoreboard",
        "environment_class": "environment",
        "sequence_class": "sequence",
        "test_class": "test",
        "top_module": "top",
    }

    def __init__(self) -> None:
        super().__init__()

        self.withdraw()  # Hide main window initially

        self.title("Testbench Ecosystem")
        self._app_dir = Path(__file__).resolve().parent
        self._section_cache: dict[str, tk.Widget] = {}
        self._theme_name = "dark"
        self._theme = apply_theme(self, self._theme_name)

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"{screen_width}x{screen_height}")
        # self.geometry("1200x700")
        self.configure(bg=self._theme.bg)

        self._build_menubar()
        self._bind_shortcuts()
        self._state = StateManager.get_instance()
        self._state.subscribe(self._on_state_change)

        # Show animated splash screen (expected to call parent.start_main_app())
        self.splash = SplashScreen(self)

    def start_main_app(self) -> None:
        splash_exists = False
        if hasattr(self, "splash"):
            try:
                splash_exists = bool(self.splash.winfo_exists())
            except tk.TclError:
                splash_exists = False

        if splash_exists:
            try:
                self.splash.destroy()
            except tk.TclError:
                pass

        self._build_layout()
        self.after_idle(self._set_window_icon)
        self.deiconify()
        self.lift()
        self.focus_force()

    def _set_window_icon(self) -> None:
        icon_path = self._app_dir / "logo" / "icon.ico"
        if not icon_path.exists():
            return

        try:
            self.iconbitmap(str(icon_path))
        except tk.TclError:
            pass

    def _build_layout(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.header = Header(self)
        self.header.grid(row=0, column=0, columnspan=2, sticky="nsew")

        self.sidebar = Sidebar(self, self.load_section)
        self.sidebar.grid(row=1, column=0, sticky="nsew")

        self.main_frame = ttk.Frame(self)
        self.main_frame.grid(row=1, column=1, sticky="nsew")

        self.footer = Footer(self)
        self.footer.grid(row=2, column=0, columnspan=2, sticky="nsew")

        self.load_section("dashboard")
        self.set_theme(self._theme_name)
        self._refresh_workflow_ui()

    def _on_state_change(self, key, value, snapshot) -> None:
        # Called from StateManager.set(); keep it UI-safe via after.
        try:
            self.after(0, self._refresh_workflow_ui)
        except tk.TclError:
            pass

    def _refresh_workflow_ui(self) -> None:
        snapshot = self._state.get_all()

        if hasattr(self, "footer"):
            try:
                self.footer.refresh_status_indicators()
            except Exception:
                pass

        if hasattr(self, "sidebar"):
            try:
                self.sidebar.set_statuses(compute_module_statuses(snapshot))
            except Exception:
                pass

    def _build_menubar(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.destroy, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Theme", command=self.toggle_theme, accelerator="Ctrl+T")
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _show_about(self) -> None:
        about = tk.Toplevel(self)
        about.title("About")
        about.resizable(False, False)
        frame = ttk.Frame(about, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Testbench Ecosystem", font=("Segoe UI", 14, "bold")).pack(
            anchor="w"
        )
        ttk.Label(frame, text="Version 1.0").pack(anchor="w", pady=(4, 0))
        ttk.Label(frame, text="Developed by Atif Afzal").pack(anchor="w", pady=(0, 8))
        ttk.Button(frame, text="Close", command=about.destroy).pack(anchor="e")

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-q>", lambda e: self.destroy())
        self.bind_all("<Control-t>", lambda e: self.toggle_theme())

        self.bind_all("<Alt-d>", lambda e: self.load_section("dashboard"))
        self.bind_all("<Alt-p>", lambda e: self.load_section("project_details"))
        self.bind_all("<Alt-i>", lambda e: self.load_section("interface_dut"))
        self.bind_all("<Alt-t>", lambda e: self.load_section("transaction_class"))

    def set_theme(self, theme_name: str) -> None:
        self._theme_name = theme_name
        self._theme = apply_theme(self, theme_name)
        self.configure(bg=self._theme.bg)

        if hasattr(self, "header") and hasattr(self.header, "set_theme"):
            self.header.set_theme(self._theme)
        if hasattr(self, "sidebar") and hasattr(self.sidebar, "set_theme"):
            self.sidebar.set_theme(self._theme)
        if hasattr(self, "footer") and hasattr(self.footer, "set_theme"):
            self.footer.set_theme(self._theme)

    def toggle_theme(self) -> None:
        next_theme = "light" if self._theme_name == "dark" else "dark"
        self.set_theme(next_theme)

    def _hide_active_section_widgets(self) -> None:
        for widget in self.main_frame.winfo_children():
            widget.pack_forget()

    def load_section(self, section_name: str) -> None:
        self._hide_active_section_widgets()

        widget_cls = self.SECTION_WIDGETS.get(section_name)
        if widget_cls is None:
            widget = tk.Label(
                self.main_frame,
                text=f"Unknown section: {section_name}",
                font=("Segoe UI", 16),
                bg="#282c34",
                fg="#ffffff",
            )
            widget.pack(fill="both", expand=True, padx=20, pady=20)
            return

        widget = self._section_cache.get(section_name)
        if widget is None:
            try:
                widget = widget_cls(self.main_frame)
            except Exception as exc:
                error_widget = tk.Label(
                    self.main_frame,
                    text=f"Failed to load '{section_name}': {exc}",
                    font=("Segoe UI", 14),
                    bg="#282c34",
                    fg="#ff6b6b",
                    justify="left",
                    wraplength=900,
                )
                error_widget.pack(fill="both", expand=True, padx=20, pady=20)
                return

            self._section_cache[section_name] = widget

        widget.pack(fill="both", expand=True)

        if hasattr(self, "sidebar") and hasattr(self.sidebar, "set_active"):
            self.sidebar.set_active(section_name)

        module_key = self.FOOTER_SECTION_KEYS.get(section_name)
        if module_key is not None and hasattr(self, "footer"):
            self.footer.show_loader_for(module_key)


def main() -> None:
    app = TestbenchEcosystemApp()
    app.mainloop()


if __name__ == "__main__":
    main()
