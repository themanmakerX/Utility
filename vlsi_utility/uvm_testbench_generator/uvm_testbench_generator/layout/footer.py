from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageSequence, ImageTk

from ..utils.paths import resource_path
from ..utils.state import StateManager
from ..utils.theme import Theme
from ..utils.workflow import Status, compute_module_statuses

COPYRIGHT_SIGN = "\N{COPYRIGHT SIGN}"


class Footer(tk.Frame):
    def __init__(self, parent, *, show_progress: bool = False):
        super().__init__(parent, bg="#3e4451")
        self.state = StateManager.get_instance()
        self.show_progress = show_progress

        self.theme = "dark"
        self._click_locked = False

        self.active_module: str | None = None
        self.completed_modules: set[str] = set()
        self.save_times: dict[str, str] = {}

        self.display_map: dict[str, str] = {
            "project": "Project",
            "interface": "Interface",
            "transaction": "Transaction",
            "agent": "Agent",
            "scoreboard": "Scoreboard",
            "environment": "Environment",
            "sequence": "Sequence",
            "test": "Test",
            "top": "Top Module",
        }
        self.module_to_section: dict[str, str] = {
            "project": "project_details",
            "interface": "interface_dut",
            "transaction": "transaction_class",
            "agent": "agent_class",
            "scoreboard": "scoreboard_class",
            "environment": "environment_class",
            "sequence": "sequence_class",
            "test": "test_class",
            "top": "top_module",
        }

        self.modules = list(self.display_map.keys())
        self.module_labels: dict[str, tk.Label] = {}
        self.gif_labels: dict[str, tk.Label] = {}
        self.label_vars: dict[str, tk.StringVar] = {}

        self.loader_running = False
        self.loader_frames: list[ImageTk.PhotoImage] = []
        self.loader_index = 0
        self._load_loader_frames()

        self._build_ui()
        self.animate_company_name()

    def _load_loader_frames(self) -> None:
        gif_path = resource_path("logo", "load.gif")
        try:
            loader_img = Image.open(gif_path)
            self.loader_frames = [
                ImageTk.PhotoImage(frame.copy().resize((24, 24), Image.LANCZOS))
                for frame in ImageSequence.Iterator(loader_img)
            ]
        except Exception:
            self.loader_frames = []

    def _build_ui(self) -> None:
        self.footer_inner = tk.Frame(self, bg="#3e4451")
        self.footer_inner.pack(fill="x", padx=10, pady=5)

        if self.show_progress:
            self.section_frame = tk.Frame(self.footer_inner, bg="#3e4451")
            self.section_frame.pack(side="left", padx=(20, 0))

            for key in self.modules:
                mod_frame = tk.Frame(self.section_frame, bg="#3e4451")
                label_var = tk.StringVar(value=f"{self.display_map[key]} [X]")
                label = tk.Label(
                    mod_frame,
                    textvariable=label_var,
                    font=("Segoe UI", 9, "bold"),
                    bg="#6c757d",
                    fg="white",
                    padx=5,
                    cursor="hand2",
                )
                gif_label = tk.Label(mod_frame, bg="#3e4451")

                label.pack(side="left", padx=(0, 2))
                gif_label.pack(side="left")
                mod_frame.pack(side="left", padx=3)

                label.bind("<Button-1>", lambda e, mod=key: self.debounced_click(mod))
                label.bind(
                    "<Enter>",
                    lambda e, k=key: self.status_label.config(
                        text=f"{self.display_map[k]}: Last Saved at {self.save_times.get(k, 'Not saved')}"
                    ),
                )
                label.bind("<Leave>", lambda e: self.refresh_status_indicators())

                self.module_labels[key] = label
                self.gif_labels[key] = gif_label
                self.label_vars[key] = label_var

        self.right_frame = tk.Frame(self.footer_inner, bg="#3e4451")
        self.right_frame.pack(side="right")

        ttk.Button(self.right_frame, text="Theme", command=self.toggle_theme).pack(
            side="right", padx=5
        )

        self.company_info = tk.Frame(self.right_frame, bg="#3e4451")
        self.company_info.pack(side="right")
        self.company_label = tk.Label(
            self.company_info,
            text=f"{COPYRIGHT_SIGN} LetsLearnTechnologies",
            font=("Segoe UI", 10, "bold"),
            bg="#3e4451",
            fg="#99e0ff",
        )
        self.company_label.pack(anchor="e")
        self.tool_info_label = tk.Label(
            self.company_info,
            text="Testbench Ecosystem v1.0 | Developed by Atif Afzal",
            font=("Segoe UI", 9),
            bg="#3e4451",
            fg="#cccccc",
        )
        self.tool_info_label.pack(anchor="e")

        self.bottom_frame = tk.Frame(self, bg="#3e4451")
        self.bottom_frame.pack(fill="x", padx=10)
        self.status_label = tk.Label(
            self.bottom_frame,
            text="Status: Ready",
            font=("Segoe UI", 10),
            bg="#3e4451",
            fg="white",
        )
        self.status_label.pack(side="left", anchor="w")

        if self.show_progress:
            self.legend_frame = tk.Frame(self.bottom_frame, bg="#3e4451")
            self.legend_frame.pack(side="left", anchor="w")

            tk.Label(self.legend_frame, text="  ", bg="#28a745", width=2).pack(
                side="left", padx=(0, 2)
            )
            tk.Label(
                self.legend_frame,
                text="Completed",
                font=("Segoe UI", 8),
                bg="#3e4451",
                fg="white",
            ).pack(side="left", padx=(0, 10))
            tk.Label(self.legend_frame, text="  ", bg="#007bff", width=2).pack(
                side="left", padx=(0, 2)
            )
            tk.Label(
                self.legend_frame,
                text="In Progress",
                font=("Segoe UI", 8),
                bg="#3e4451",
                fg="white",
            ).pack(side="left", padx=(0, 10))
            tk.Label(self.legend_frame, text="  ", bg="#6c757d", width=2).pack(
                side="left", padx=(0, 2)
            )
            tk.Label(
                self.legend_frame,
                text="Not Started",
                font=("Segoe UI", 8),
                bg="#3e4451",
                fg="white",
            ).pack(side="left", padx=(0, 10))

        self.typing_forward = True
        self.full_company_text = f"{COPYRIGHT_SIGN} LetsLearnTechnologies"
        self.company_text_index = 0

    def show_loader_for(self, key: str) -> None:
        if key not in self.module_labels or key in self.completed_modules:
            return

        self.active_module = key
        self.label_vars[key].set(f"{self.display_map[key]} [...]")
        self.module_labels[key].config(bg="#007bff")

        self.stop_loader()
        self.loader_running = True
        self.animate_loader()

    def stop_loader(self) -> None:
        self.loader_running = False
        for label in self.gif_labels.values():
            label.config(image="")

    def animate_loader(self) -> None:
        if not self.loader_running or self.active_module not in self.gif_labels:
            return
        if not self.loader_frames:
            return

        gif_label = self.gif_labels[self.active_module]
        gif_label.config(image=self.loader_frames[self.loader_index])
        self.loader_index = (self.loader_index + 1) % len(self.loader_frames)
        self.after(100, self.animate_loader)

    def mark_done(self, key: str) -> None:
        self.completed_modules.add(key)
        self.save_times[key] = datetime.now().strftime("%H:%M:%S")
        if key in self.label_vars:
            self.label_vars[key].set(f"{self.display_map[key]} [OK]")
        if key in self.module_labels:
            self.module_labels[key].config(bg="#28a745")
            self.pulse_label(key)
        if key in self.gif_labels:
            self.gif_labels[key].config(image="")
        if self.active_module == key:
            self.active_module = None
            self.stop_loader()

        if hasattr(self, "status_label"):
            self.status_label.config(text=f"Saved: {self.display_map.get(key, key)} at {self.save_times[key]}")
            self.after(2000, self.refresh_status_indicators)

    def refresh_status_indicators(self) -> None:
        data = self.state.get_all()

        # Always keep footer status in sync with workflow completion.
        try:
            statuses = compute_module_statuses(data)
            required = [
                "project_details",
                "interface_dut",
                "transaction_class",
                "agent_class",
                "environment_class",
                "sequence_class",
                "test_class",
                "top_module",
            ]
            completed = sum(1 for k in required if statuses.get(k) and statuses[k].status == Status.COMPLETE)
            self.status_label.config(text=f"Workflow: {completed}/{len(required)} complete")
        except Exception:
            self.status_label.config(text="Status: Ready")

        if not self.show_progress:
            return

        for key in self.modules:
            if key in data:
                self.mark_done(key)
            else:
                if key in self.label_vars:
                    self.label_vars[key].set(f"{self.display_map[key]} [X]")
                if key in self.module_labels:
                    self.module_labels[key].config(bg="#6c757d")
                if key in self.gif_labels:
                    self.gif_labels[key].config(image="")

    def pulse_label(self, key: str, count: int = 6) -> None:
        if key not in self.module_labels or count == 0:
            return
        label = self.module_labels[key]
        label.config(bg="#34d058" if count % 2 == 0 else "#28a745")
        self.after(150, lambda: self.pulse_label(key, count - 1))

    def on_label_click(self, key: str) -> None:
        section_name = self.module_to_section.get(key)
        if section_name and hasattr(self.master, "load_section"):
            self.master.load_section(section_name)

    def debounced_click(self, key: str) -> None:
        if self._click_locked:
            return
        self._click_locked = True
        self.after(300, lambda: setattr(self, "_click_locked", False))
        self.on_label_click(key)

    def toggle_theme(self) -> None:
        next_theme = "light" if self.theme == "dark" else "dark"
        self.theme = next_theme
        if hasattr(self.master, "set_theme"):
            try:
                self.master.set_theme(next_theme)
                return
            except Exception:
                pass

    def set_theme(self, theme: Theme) -> None:
        self.configure(bg=theme.border)
        self.footer_inner.configure(bg=theme.border)
        if hasattr(self, "section_frame"):
            self.section_frame.configure(bg=theme.border)
        self.right_frame.configure(bg=theme.border)
        self.company_info.configure(bg=theme.border)
        self.bottom_frame.configure(bg=theme.border)
        if hasattr(self, "legend_frame"):
            self.legend_frame.configure(bg=theme.border)

        self.company_label.configure(bg=theme.border, fg=theme.accent)
        self.tool_info_label.configure(bg=theme.border, fg=theme.fg_muted)
        self.status_label.configure(bg=theme.border, fg=theme.fg)

        if hasattr(self, "section_frame"):
            for mod_frame in self.section_frame.winfo_children():
                try:
                    mod_frame.configure(bg=theme.border)
                except tk.TclError:
                    pass
            for key, label in self.module_labels.items():
                if key in self.completed_modules:
                    continue
                label.configure(bg="#6c757d")

    def animate_company_name(self) -> None:
        if self.typing_forward:
            if self.company_text_index < len(self.full_company_text):
                self.company_text_index += 1
                display_text = self.full_company_text[: self.company_text_index]
                self.company_label.config(text=display_text + "|")
                self.after(150, self.animate_company_name)
            else:
                self.typing_forward = False
                self.after(1000, self.animate_company_name)
        else:
            if self.company_text_index > 0:
                self.company_text_index -= 1
                display_text = self.full_company_text[: self.company_text_index]
                self.company_label.config(text=display_text + "|")
                self.after(80, self.animate_company_name)
            else:
                self.typing_forward = True
                self.after(500, self.animate_company_name)
