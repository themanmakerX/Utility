import tkinter as tk
from tkinter import ttk, messagebox
import threading

from ..utils.state import StateManager
from ..utils.generator import generate_project
from ..utils.workflow import compute_module_statuses, Status

class DashboardPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.state = StateManager.get_instance()
        self.configure(padding=10, style="DarkBG.TFrame")

        self.build_ui()
        self.refresh_dashboard()
        self.state.subscribe(self._on_state_change)

    def _on_state_change(self, _key, _value, _snapshot) -> None:
        try:
            self.after(0, self.refresh_dashboard)
        except Exception:
            pass

    def build_ui(self):
        style = ttk.Style()
        style.configure("Custom.TProgressbar", thickness=15, troughcolor="#444", background="#4CAF50")
        style.layout("Custom.TProgressbar", style.layout("Horizontal.TProgressbar"))

        style.configure("DarkBG.TFrame", background="#1e1f26")
        style.configure("Card.TLabelframe", background="#2b2c37", foreground="white", padding=10, font=("Segoe UI", 10, "bold"), borderwidth=2, relief="ridge")
        style.configure("Card.TFrame", background="#2b2c37", borderwidth=1, relief="groove")
        style.configure("Label.TLabel", background="#2b2c37", foreground="white", font=("Segoe UI", 10))
        style.configure("Custom.TButton", font=("Segoe UI", 10, "bold"), padding=6)

        canvas = tk.Canvas(self, bg="#1e1f26", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.scroll_frame = ttk.Frame(canvas, style="DarkBG.TFrame")
        self.scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

        self.grid_wrapper = ttk.Frame(self.scroll_frame, style="DarkBG.TFrame")
        self.grid_wrapper.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)
        self.grid_wrapper.columnconfigure(0, weight=1)
        self.grid_wrapper.columnconfigure(1, weight=1)

        self.cards = {}

        def grid_card(widget, row, col):
            widget.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)

        proj_frame = ttk.LabelFrame(self.grid_wrapper, text="Project Summary", style="Card.TLabelframe")
        self.cards['proj'] = proj_frame
        self.proj_summary = ttk.Label(proj_frame, text="", style="Label.TLabel", justify="left")
        self.proj_summary.pack(padx=10, pady=10, anchor="w")
        grid_card(proj_frame, 0, 0)

        progress_frame = ttk.LabelFrame(self.grid_wrapper, text="Progress Tracker", style="Card.TLabelframe")
        self.cards['progress'] = progress_frame
        self.progress_status = ttk.Label(progress_frame, text="", style="Label.TLabel", justify="left", anchor="w")
        self.progress_status.pack(padx=10, pady=(10, 5), anchor="w")
        self.progress_var = tk.DoubleVar()
        progress_row = ttk.Frame(progress_frame, style="Card.TFrame")
        progress_row.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Progressbar(progress_row, maximum=100, variable=self.progress_var, style="Custom.TProgressbar").pack(side="left", fill="x", expand=True)
        self.progress_label = ttk.Label(progress_row, text="0%", style="Label.TLabel")
        self.progress_label.pack(side="right", padx=10)
        grid_card(progress_frame, 0, 1)

        quick_frame = ttk.LabelFrame(self.grid_wrapper, text="Quick Actions", style="Card.TLabelframe")
        self.cards['quick'] = quick_frame
        actions = ttk.Frame(quick_frame, style="Card.TFrame")
        actions.pack(padx=10, pady=10)
        ttk.Button(actions, text="Export Testbench", command=self.export_testbench, style="Custom.TButton").pack(side="left", padx=5)
        ttk.Button(actions, text="Reset Project", command=self.reset_project, style="Custom.TButton").pack(side="left", padx=5)
        ttk.Button(actions, text="View Preview", command=self.view_preview, style="Custom.TButton").pack(side="left", padx=5)
        grid_card(quick_frame, 1, 0)

        diag_frame = ttk.LabelFrame(self.grid_wrapper, text="Diagnostics", style="Card.TLabelframe")
        self.cards['diag'] = diag_frame
        diag_container = ttk.Frame(diag_frame, style="Card.TFrame")
        diag_container.pack(fill="both", expand=True)
        self.diagnostics_text = tk.Text(diag_container, height=8, wrap="word", font=("Segoe UI", 10), fg="#ffffff", bg="#2c303a", bd=1, relief="flat", highlightthickness=1, highlightbackground="#444", padx=10, pady=5)
        self.diagnostics_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        diag_scrollbar = ttk.Scrollbar(diag_container, orient="vertical", command=self.diagnostics_text.yview)
        self.diagnostics_text.configure(yscrollcommand=diag_scrollbar.set)
        diag_scrollbar.pack(side="right", fill="y")
        grid_card(diag_frame, 1, 1)

        generate_btn = ttk.Button(self.grid_wrapper, text="Generate Testbench", command=self.generate_testbench, style="Custom.TButton")
        self.cards['generate'] = generate_btn
        generate_btn.grid(row=2, column=0, columnspan=2, pady=10)

    def refresh_dashboard(self):
        data = self.state.get_all()

        project = data.get("project", {})
        if project:
            self.proj_summary.config(
                text=(
                    f"Project Name: {project.get('project_name', '-')}\n"
                    f"Owner: {project.get('owner_name', '-')}\n"
                    f"Output Dir: {project.get('output_dir', '-')}\n"
                    f"UVM Version: {project.get('uvm_version', '-')}\n"
                    f"Language: {project.get('language', '-')}\n"
                    f"DUT File: {project.get('dut_path', '-')}\n"
                )
            )
        else:
            self.proj_summary.config(text="No project loaded yet.")

        statuses = compute_module_statuses(data)
        order = [
            ("Project Details", "project_details"),
            ("Interface & DUT", "interface_dut"),
            ("Transaction", "transaction_class"),
            ("Agent", "agent_class"),
            ("Scoreboard (Optional)", "scoreboard_class"),
            ("Environment", "environment_class"),
            ("Sequence", "sequence_class"),
            ("Test", "test_class"),
            ("Top Module", "top_module"),
        ]

        progress_lines: list[str] = []
        completed_required = 0
        required_keys = [
            "project_details",
            "interface_dut",
            "transaction_class",
            "agent_class",
            "environment_class",
            "sequence_class",
            "test_class",
            "top_module",
        ]

        for label, key in order:
            st = statuses.get(key)
            if not st:
                progress_lines.append(f"[TODO] {label}")
                continue

            if st.status == Status.COMPLETE:
                progress_lines.append(f"[OK] {label}")
            elif st.status == Status.BLOCKED:
                missing = ", ".join(st.missing) if st.missing else "dependencies"
                progress_lines.append(f"[BLOCKED] {label}  (missing: {missing})")
            else:
                missing = ", ".join(st.missing) if st.missing else ""
                suffix = f"  (missing: {missing})" if missing else ""
                progress_lines.append(f"[TODO] {label}{suffix}")

        for k in required_keys:
            if statuses.get(k) and statuses[k].status == Status.COMPLETE:
                completed_required += 1

        self.progress_status.config(text="\n".join(progress_lines))
        percent = int((completed_required / len(required_keys)) * 100)
        self.progress_var.set(percent)
        self.progress_label.config(text=f"{percent}%")

        diagnostics: list[str] = []
        for label, key in order:
            st = statuses.get(key)
            if not st:
                continue
            if st.status == Status.COMPLETE:
                continue
            if st.status == Status.BLOCKED:
                missing = ", ".join(st.missing) if st.missing else "dependencies"
                diagnostics.append(f"- {label} is BLOCKED (missing: {missing}).\n")
            else:
                missing = ", ".join(st.missing) if st.missing else "pending"
                diagnostics.append(f"- {label} is TODO (missing: {missing}).\n")
            if st.hint:
                diagnostics.append(f"  Hint: {st.hint}\n")

        diag_text = "".join(diagnostics) if diagnostics else "OK: All required modules complete. Ready to generate.\n"
        self.diagnostics_text.config(state="normal")
        self.diagnostics_text.delete("1.0", tk.END)
        self.diagnostics_text.insert(tk.END, diag_text)
        self.diagnostics_text.config(state="disabled")

    def generate_testbench(self):
        data = self.state.get_all()

        def worker():
            try:
                result = generate_project(data)
            except Exception as exc:
                err_text = str(exc)
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Generate Failed", f"Generation failed:\n\n{err_text}"
                    ),
                )
                return

            def done():
                msg = f"Generated {len(result.files_written)} files in:\n{result.output_root}"
                if result.warnings:
                    msg += "\n\nWarnings:\n" + "\n".join(f"- {w}" for w in result.warnings)
                messagebox.showinfo("Generate Complete", msg)

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def export_testbench(self):
        data = self.state.get_all()
        project = data.get("project", {}) or {}
        output_dir = (project.get("output_dir") or "").strip()
        project_name = (project.get("project_name") or "").strip()
        if not output_dir or not project_name:
            messagebox.showwarning(
                "Export",
                "Please save Project Details first (Project Name + Output Directory).",
            )
            return
        messagebox.showinfo(
            "Export",
            "Use Generate Testbench to write the multi-file project into the Output Directory.",
        )

    def reset_project(self):
        self.state.clear()
        self.refresh_dashboard()
        messagebox.showinfo("Reset", "Project reset successfully.")

    def view_preview(self):
        if hasattr(self.master.master, "load_section"):
            self.master.master.load_section("preview")
        else:
            messagebox.showinfo("Preview", "Open the Preview page from the sidebar.")

