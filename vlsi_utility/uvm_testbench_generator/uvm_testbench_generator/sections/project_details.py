import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from ..utils.state import StateManager
from ..utils.verilog_parser import extract_parameters, extract_signals, extract_module_info
from tkinter import messagebox

class ProjectDetailsForm(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.state = StateManager.get_instance()
        self.configure(padding=10)
        self.build_ui()
        self.make_treeview_editable(self.param_tree)
        self.make_treeview_editable(self.signal_tree)        

    def build_ui(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        left_frame = ttk.Frame(self)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.columnconfigure(1, weight=1)

        row = 0
        def add_labeled_entry(label, var):
            nonlocal row
            ttk.Label(left_frame, text=label).grid(row=row, column=0, sticky="w")
            entry = ttk.Entry(left_frame, textvariable=var, width=40)
            entry.grid(row=row, column=1, sticky="ew", pady=2)
            row += 1
            return entry

        self.project_name = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.prefix = tk.StringVar()
        self.owner_name = tk.StringVar()
        self.dut_path = tk.StringVar()
        self.uvm_version = tk.StringVar(value="UVM 1.2")
        self.language = tk.StringVar(value="SystemVerilog")
        self.project_mode = tk.StringVar(value="Full Testbench")
        self.enable_coverage = tk.BooleanVar()
        self.include_scoreboard = tk.BooleanVar()
        self.use_virtual_seq = tk.BooleanVar()
        self.include_monitor = tk.BooleanVar()

        add_labeled_entry("Project Name:", self.project_name)
        add_labeled_entry("Output Directory:", self.output_dir)
        ttk.Button(left_frame, text="Browse", command=self.browse_output).grid(row=row-1, column=2)
        add_labeled_entry("Global Prefix/Tag:", self.prefix)
        add_labeled_entry("Owner Name:", self.owner_name)
        add_labeled_entry("DUT File Path:", self.dut_path)
        ttk.Button(left_frame, text="Browse", command=self.browse_dut).grid(row=row-1, column=2)

        ttk.Label(left_frame, text="UVM Version:").grid(row=row, column=0, sticky="w")
        ttk.Combobox(left_frame, textvariable=self.uvm_version, values=["UVM 1.1d", "UVM 1.2", "UVM 1.3"], state="readonly").grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Label(left_frame, text="Target Language:").grid(row=row, column=0, sticky="w")
        ttk.Combobox(left_frame, textvariable=self.language, values=["SystemVerilog", "Verilog"], state="readonly").grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Label(left_frame, text="Project Mode:").grid(row=row, column=0, sticky="w")
        ttk.Combobox(left_frame, textvariable=self.project_mode, values=["Full Testbench", "Lightweight", "Regression-ready"], state="readonly").grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Label(left_frame, text="Features:").grid(row=row, column=0, sticky="w")
        features = ttk.Frame(left_frame)
        features.grid(row=row, column=1, sticky="w")
        ttk.Checkbutton(features, text="Coverage", variable=self.enable_coverage).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(features, text="Scoreboard", variable=self.include_scoreboard).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(features, text="Virtual Sequences", variable=self.use_virtual_seq).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(features, text="Monitor", variable=self.include_monitor).grid(row=3, column=0, sticky="w")
        row += 1

        ttk.Label(left_frame, text="License/Header:").grid(row=row, column=0, sticky="nw")
        self.license_input = scrolledtext.ScrolledText(left_frame, width=30, height=4)
        self.license_input.grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        ttk.Label(left_frame, text="Notes:").grid(row=row, column=0, sticky="nw")
        self.notes_input = scrolledtext.ScrolledText(left_frame, width=30, height=4)
        self.notes_input.grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        ttk.Button(left_frame, text="Save Project", command=self.save_project_details).grid(row=row, column=1, pady=10, sticky="e")

        self.right_frame = ttk.LabelFrame(self, text="Saved Project Info")
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(0, weight=1)
        self.right_frame.rowconfigure(1, weight=0)
        self.right_frame.rowconfigure(2, weight=1)

        self.right_text = scrolledtext.ScrolledText(self.right_frame, width=50, height=15, state="disabled")
        self.right_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.param_tree = ttk.Treeview(self.right_frame, columns=("Name", "Value"), show="headings", height=5)
        self.param_tree.heading("Name", text="Name")
        self.param_tree.heading("Value", text="Value")
        self.param_tree.column("Name", width=150, stretch=True)
        self.param_tree.column("Value", width=200, stretch=True)
        self.param_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.signal_tree = ttk.Treeview(self.right_frame, columns=("Direction", "Name", "Width", "Derived From"), show="headings", height=8)
        for col in ["Direction", "Name", "Width", "Derived From"]:
            self.signal_tree.heading(col, text=col)
            self.signal_tree.column(col, width=120, stretch=True)
        self.signal_tree.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Button(self.right_frame, text="Save Changes", command=self.save_treeview_edits_to_state).grid(row=3, column=0, sticky="e", padx=5, pady=(5, 10))        

    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def browse_dut(self):
        path = filedialog.askopenfilename(filetypes=[("SystemVerilog Files", "*.sv"), ("All files", "*.*")])
        if path:
            self.dut_path.set(path)

    def save_project_details(self):
        data = {
            "project_name": self.project_name.get(),
            "output_dir": self.output_dir.get(),
            "prefix": self.prefix.get(),
            "owner_name": self.owner_name.get(),
            "dut_path": self.dut_path.get(),
            "uvm_version": self.uvm_version.get(),
            "language": self.language.get(),
            "project_mode": self.project_mode.get(),
            "enable_coverage": self.enable_coverage.get(),
            "include_scoreboard": self.include_scoreboard.get(),
            "use_virtual_seq": self.use_virtual_seq.get(),
            "include_monitor": self.include_monitor.get(),
            "license": self.license_input.get("1.0", tk.END).strip(),
            "notes": self.notes_input.get("1.0", tk.END).strip()
        }
    
        if data["dut_path"]:
            dut_info = extract_module_info(data["dut_path"])
            data["dut_info"] = dut_info
            data["module_name"] = dut_info["module_name"]
            self.populate_treeviews(dut_info["parameters"], dut_info["signals"])
        else:
            self.populate_treeviews({}, [])
    
        self.state.set("project", data)
        self.update_preview(data)
        if hasattr(self.master.master, 'footer'):
           self.master.master.footer.mark_done("project")

    def update_preview(self, data):
        self.right_text.config(state="normal")
        self.right_text.delete("1.0", tk.END)
        for key, val in data.items():
            if key not in ("dut_info", "signals", "parameters"):            
                self.right_text.insert(tk.END, f"{key.replace('_', ' ').title()}: {val}\n")
        self.right_text.config(state="disabled")

    def populate_treeviews(self, parameters, signals):
        self.param_tree.delete(*self.param_tree.get_children())
        self.signal_tree.delete(*self.signal_tree.get_children())

        for k, v in parameters.items():
            self.param_tree.insert("", "end", values=(k, v))

        for sig in signals:
            derived_from = "parameter" if any(p in sig["raw"] for p in parameters.keys()) else "literal"
            self.signal_tree.insert("", "end", values=(sig["direction"], sig["name"], sig["width"], derived_from))

    def make_treeview_editable(self,tree):
        def on_double_click(event):
            region = tree.identify("region", event.x, event.y)
            if region != "cell":
                return
    
            row_id = tree.identify_row(event.y)
            col_id = tree.identify_column(event.x)
            col_num = int(col_id.replace("#", "")) - 1
            col_name = tree["columns"][col_num]
            cell_value = tree.item(row_id)["values"][col_num]
    
            x, y, width, height = tree.bbox(row_id, col_id)
            entry = tk.Entry(tree)
            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, cell_value)
            entry.focus()
    
            def on_save(event=None):
                new_value = entry.get()
                values = list(tree.item(row_id)["values"])
                values[col_num] = new_value
                tree.item(row_id, values=values)
                entry.destroy()
    
            entry.bind("<Return>", on_save)
            entry.bind("<FocusOut>", lambda e: entry.destroy())
    
        tree.bind("<Double-1>", on_double_click)

    def save_treeview_edits_to_state(self):
        updated_params = {}
        for row_id in self.param_tree.get_children():
            values = self.param_tree.item(row_id)["values"]
            if len(values) == 2:
                updated_params[values[0]] = values[1]
    
        updated_signals = []
        for row_id in self.signal_tree.get_children():
            values = self.signal_tree.item(row_id)["values"]
            if len(values) == 4:
                updated_signals.append({
                    "direction": values[0],
                    "name": values[1],
                    "width": values[2],
                    "raw": values[2],  # Use width as raw if not changed
                })
    
        # Get current state and update
        data = self.state.get("project", {})
        if "dut_info" not in data:
            data["dut_info"] = {}
    
        data["dut_info"]["parameters"] = updated_params
        data["dut_info"]["signals"] = updated_signals
    
        self.state.set("project", data)
        self.update_preview(data)
    
        messagebox.showinfo("Saved", "Edited parameters and signals have been saved to state.")
