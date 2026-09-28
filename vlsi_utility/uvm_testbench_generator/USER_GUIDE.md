# Testbench Ecosystem — User Guide

## 1. Overview

Testbench Ecosystem is a GUI workflow for generating a UVM-style SystemVerilog testbench. It stores your inputs in an internal app state, shows progress across modules, and generates a structured output folder with a consistent set of files.

## 2. System requirements

- Windows + Python 3.x
- Tkinter available (usually included with the standard Windows Python installer)
- Python package dependency: Pillow

Install dependencies:

```bash
pip install -r requirements.txt
```

## 3. Start the app

Run:

```bash
python testbench_generator.py
```

You should see a splash screen, then the main window with:

- Header (logo + title)
- Sidebar (navigation)
- Main content area (forms/pages)
- Footer (workflow / loader indicators)

## 4. Sidebar modules (what each one does)

The sidebar sections are the app’s navigation contract. Fill them in order for the smoothest experience:

### Dashboard

Shows a high-level status summary and quick actions. Use it to:

- See which modules are complete / blocked / missing fields
- Generate the testbench once required modules are complete

### Project Details

Defines project-wide settings and the DUT source file.

Key fields:

- **Project Name**: Output folder name.
- **Output Directory**: Parent directory for generated output.
- **DUT File Path**: Path to the DUT `*.sv` file.
- **UVM Version / Target Language / Project Mode / Features**: Stored in state and may affect generation depending on section settings.
- **License/Header**: Text stored in state (can be used for headers in future templates).

When you click **Save Project**, the app also attempts to parse the DUT:

- Extracts module name
- Extracts parameters and signals
- Populates the parameter/signal tables

Tip: You can double-click table cells to edit values and save them back into state.

### Interface & DUT

Builds the interface definition and imports signals from the DUT state. Typical flow:

1) Click **Import from DUT** (uses DUT parsing from Project Details).
2) Select clock/reset names (if your DUT uses them).
3) Save.

### Transaction

Defines the sequence item (transaction) class and its fields. Usually you import fields derived from interface signals and then adjust:

- Class name
- Base class (defaults to `uvm_sequence_item`)
- Field list and field types

### Agent

Generates an agent and (optionally) subcomponents. Common outputs include:

- `agent.sv`
- Optional `driver.sv`, `monitor.sv`, `sequencer.sv` (if enabled in the UI)

### Scoreboard (optional)

Adds a scoreboard implementation and connects analysis flow. If you don’t need a scoreboard, you can skip it and still generate a valid scaffold.

### Environment

Creates the UVM environment, instantiates the agent/scoreboard as selected, and wires analysis connections where applicable.

### Sequence

Defines a sequence class that runs on the sequencer.

Note: The generator currently includes some fixed timing defaults in the generated `top.sv` clock/reset logic (for example, `forever #5` and `#20` reset deassert). If you need these configurable, update generator settings or use overrides (see §6).

### Test

Defines the UVM test class and can print topology. It also determines the `run_test("...")` name used by the top module.

### Top Module

Creates the SV top, instantiates DUT + interface, attempts a basic port map, and calls `run_test("...")`.

If port mapping cannot be fully inferred, the generated `top.sv` includes TODO comments listing unconnected ports.

### State Machine

Shows workflow state and hints (which modules are blocked, what’s missing, and recommended next actions).

### Preview

Shows every generated file as an editable tab before you write anything to disk.

Actions:

- **Refresh**: Regenerate preview from current state.
- **Save Tab Override / Save All Overrides**: Persist your edited content into app state.
- **Revert Tab / Revert All**: Remove overrides and restore generated defaults.
- **Export Tab**: Save the current tab to a file anywhere on disk.
- **Copy Tab**: Copy the current tab to clipboard.
- **Use saved overrides during generation**: When enabled, your saved overrides are applied when writing the final project folder.

## 5. Generate the testbench

Go to **Dashboard** and click **Generate Testbench**.

The generator writes into:

`<Output Directory>/<Project Name>/`

It creates:

- `manifest.json` (metadata)
- `filelist.f` (minimal compile list)
- `README.md`
- `src/` containing the SystemVerilog/UVM scaffold (e.g., `tb_pkg.sv`, `top.sv`, etc.)

If overrides are enabled, any saved override tabs (like `src/sequence.sv`) will replace the default content in the generated output.

## 6. Customization (overrides)

Use **Preview** when you want to hand-edit generated files but still keep the UI workflow for everything else.

Recommended pattern:

1) Fill all modules normally.
2) Open **Preview** and locate the file you want to customize (example: `src/sequence.sv`).
3) Edit the content.
4) Click **Save Tab Override**.
5) Ensure **Use saved overrides during generation** is enabled.
6) Generate again from Dashboard.

## 7. Troubleshooting

- **App doesn’t start / import error for PIL**: run `pip install -r requirements.txt`.
- **Buttons show but images are missing**: ensure the `logo/` folder exists with `icon.png`, `icon.ico`, `load.gif`, `a_logo.png`, `c_logo.png`.
- **Generate fails with “missing Project Name / Output Directory / DUT File Path”**: go back to **Project Details** and click **Save Project**.
- **Port mapping incomplete**: check `src/top.sv` and connect remaining ports; the generator leaves a TODO list for unconnected ports.

## 8. Repo notes (for publishing)

- Entrypoint: `testbench_generator.py`
- Primary code: `layout/`, `sections/`, `utils/`
- This repo may include older/alternate UI modules that are not used by the current entrypoint unless you wire them in.

