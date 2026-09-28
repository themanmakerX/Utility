# Testbench Ecosystem

Tkinter-based UVM testbench generator that guides you from DUT import to a complete SystemVerilog scaffold. Configure interface, transaction, agent, scoreboard, environment, sequences, tests, and top; track workflow status, preview every generated file, and export a structured project folder (src/, tb_pkg.sv, top.sv, filelist.f, manifest.json). SV!

## What this is

This project is a desktop GUI that helps you build a multi-file UVM-style testbench starting from a DUT (`*.sv`) file. The app walks you through the typical UVM building blocks (interface → transaction → agent → environment → test → top), then generates a structured output folder ready to compile/simulate.

## Quick start

1) Install Python (3.9+) with Tkinter available.
2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Run the app:

```bash
python testbench_generator.py
```

Badges

- Build: [![CI](https://github.com/atifafzal786/UVM-Testbench-Generator/actions/workflows/python-ci.yml/badge.svg)](https://github.com/atifafzal786/UVM-Testbench-Generator/actions)

Docs & support

See `USAGE.md` and `USER_GUIDE.md` for full documentation and walkthroughs.

## Output structure (generated)

When you click **Generate Testbench**, the app writes into:

`<Output Directory>/<Project Name>/`

Common files:

- `manifest.json` (what was generated)
- `filelist.f` (minimal compile list)
- `README.md` (generated project README)
- `src/interface.sv`
- `src/transaction.sv`
- `src/sequence.sv`
- `src/agent.sv` (plus optional `driver.sv`, `monitor.sv`, `sequencer.sv`)
- `src/scoreboard.sv`
- `src/environment.sv`
- `src/test.sv`
- `src/tb_pkg.sv`
- `src/top.sv`

## Docs

- `USAGE.md` — fast workflow steps
- `USER_GUIDE.md` — detailed user manual
- `GITHUB_DESCRIPTION.txt` — 350-character repo description

## Notes

- The runnable app entrypoint is `testbench_generator.py`.
- This repo may contain older/alternate UI modules (extra splash screens, footers, dashboards). They are not used by the current entrypoint unless you wire them in.

