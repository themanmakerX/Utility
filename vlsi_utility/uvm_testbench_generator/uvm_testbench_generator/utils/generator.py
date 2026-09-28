from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
import tempfile
from typing import Iterable


@dataclass(frozen=True)
class GenerationResult:
    output_root: Path
    files_written: tuple[Path, ...]
    warnings: tuple[str, ...] = ()


def _safe_name(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if not value:
        return fallback
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value.strip("_") or fallback


def _safe_rel_path(value: str) -> Path | None:
    raw = (value or "").strip()
    if not raw:
        return None
    raw = raw.replace("\\", "/")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        return None
    p = Path(raw)
    if p.is_absolute():
        return None
    for part in p.parts:
        if part in ("..", ""):
            return None
    return p


def validate_state(state: dict) -> list[str]:
    errors: list[str] = []
    project = state.get("project", {}) or {}

    if not (project.get("project_name") or "").strip():
        errors.append("Project Name is required.")
    if not (project.get("output_dir") or "").strip():
        errors.append("Output Directory is required.")

    if "interface" not in state:
        errors.append("Interface is missing.")
    if "transaction" not in state:
        errors.append("Transaction is missing.")
    if "agent" not in state:
        errors.append("Agent is missing.")
    if "environment" not in state:
        errors.append("Environment is missing.")
    if "test" not in state:
        errors.append("Test is missing.")
    if "top" not in state:
        errors.append("Top Module is missing.")

    return errors


def _vector_decl(width: str) -> str:
    try:
        w = int(str(width).strip())
    except Exception:
        return ""
    if w <= 1:
        return ""
    return f"[{w - 1}:0] "


def _read_text_best_effort(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def _strip_sv_comments(text: str) -> str:
    text = re.sub(r"/\\*.*?\\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    return text


def _extract_module_ports_from_file(path: Path, module_name: str) -> list[str]:
    if not module_name:
        return []
    text = _read_text_best_effort(path)
    if not text:
        return []
    cleaned = _strip_sv_comments(text)
    m = re.search(
        rf"\\bmodule\\s+{re.escape(module_name)}\\b\\s*(?:#\\s*\\(.*?\\)\\s*)?\\((.*?)\\)\\s*;",
        cleaned,
        flags=re.S,
    )
    if not m:
        return []
    block = m.group(1)
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
    seen = set()
    out: list[str] = []
    for p in ports:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _render_interface(state: dict) -> str:
    interface = state.get("interface", {}) or {}
    name = _safe_name(interface.get("name", "my_if"), "my_if")
    clk = (interface.get("clock") or "").strip()
    rst = (interface.get("reset") or "").strip()

    header_ports: list[str] = []
    if clk:
        header_ports.append(f"input logic {clk}")
    if rst:
        header_ports.append(f"input logic {rst}")
    ports = ", ".join(header_ports)
    port_clause = f"({ports})" if ports else ""

    lines: list[str] = [f"interface {name}{port_clause};", ""]

    for sig in interface.get("signals", []) or []:
        direction = (sig.get("direction") or "input").strip()
        sig_name = _safe_name(sig.get("name", ""), "sig")
        vec = _vector_decl(sig.get("width", "1"))
        lines.append(f"  {direction} logic {vec}{sig_name};")

    modports: dict = interface.get("modports", {}) or {}
    if modports:
        lines.append("")
        for mod_name, sigs in modports.items():
            mod_name_s = _safe_name(str(mod_name), "mp")
            entries = []
            for sig_name, access in (sigs or {}).items():
                entries.append(f"    {access} {sig_name}")
            joined = ",\n".join(entries) if entries else ""
            lines.append(f"  modport {mod_name_s} (\n{joined}\n  );")

    lines.append("")
    lines.append(f"endinterface : {name}")
    return "\n".join(lines) + "\n"


def _field_macro(type_str: str) -> str:
    t = (type_str or "").lower()
    if "enum" in t:
        return "uvm_field_enum"
    if "string" in t:
        return "uvm_field_string"
    if "class" in t or "*" in t or "handle" in t:
        return "uvm_field_object"
    return "uvm_field_int"


def _render_transaction(state: dict) -> str:
    txn = state.get("transaction", {}) or {}
    class_name = _safe_name(txn.get("class_name", "txn_item"), "txn_item")
    base = _safe_name(txn.get("base_class", "uvm_sequence_item"), "uvm_sequence_item")
    fields = txn.get("fields", []) or []
    constraints = txn.get("constraints", []) or []

    lines = [f"class {class_name} extends {base};", f"  `uvm_object_utils({class_name})", ""]
    for f in fields:
        rand = "rand " if bool(f.get("rand")) else ""
        type_str = (f.get("type") or "bit").strip()
        name = _safe_name(f.get("name", ""), "field")
        lines.append(f"  {rand}{type_str} {name};")

    lines.append("")
    for c in constraints:
        c_name = _safe_name(c.get("name", "c"), "c")
        body = (c.get("body") or "").strip().rstrip(";")
        if body:
            lines.append(f"  constraint {c_name} {{ {body}; }}")

    lines.append("")
    lines.append(f"  function new(string name = \"{class_name}\");")
    lines.append("    super.new(name);")
    lines.append("  endfunction")
    lines.append("")
    lines.append(f"  `uvm_object_utils_begin({class_name})")
    for f in fields:
        name = _safe_name(f.get("name", ""), "field")
        macro = _field_macro(f.get("type", ""))
        lines.append(f"    `{macro}({name}, UVM_ALL_ON)")
    lines.append("  `uvm_object_utils_end")
    lines.append("")
    lines.append(f"endclass : {class_name}")
    return "\n".join(lines) + "\n"


def _render_sequence(state: dict) -> str:
    seq = state.get("sequence", {}) or {}
    name = _safe_name(seq.get("name", "my_sequence"), "my_sequence")
    txn_class = _safe_name(seq.get("transaction_class", "txn_item"), "txn_item")
    steps = seq.get("steps", []) or []

    lines = [f"class {name} extends uvm_sequence #({txn_class});", f"  `uvm_object_utils({name})", ""]
    lines.append(f"  function new(string name = \"{name}\");")
    lines.append("    super.new(name);")
    lines.append("  endfunction")
    lines.append("")
    lines.append("  virtual task body();")

    def render_step(step: dict, *, idx: int) -> list[str]:
        out: list[str] = []
        if not isinstance(step, dict):
            return out

        delay = str(step.get("delay") or "0").strip()
        repeat_raw = str(step.get("repeat") or "1").strip()
        try:
            repeat_n = int(repeat_raw)
        except Exception:
            repeat_n = 1
        if repeat_n < 1:
            repeat_n = 1

        item_name = _safe_name(step.get("item_name") or step.get("item") or f"tx_{idx}", f"tx_{idx}")
        randomize = bool(step.get("randomize", True))
        assigns = step.get("assignments", {}) or {}
        assigns = assigns if isinstance(assigns, dict) else {}

        indent = "    "
        if repeat_n > 1:
            out.append(f"{indent}repeat ({repeat_n}) begin")
            indent = "      "

        if delay and delay != "0":
            out.append(f"{indent}#({delay});")

        out.append(f"{indent}{txn_class} tx;")
        out.append(f"{indent}tx = {txn_class}::type_id::create(\"{item_name}\");")
        out.append(f"{indent}start_item(tx);")

        # Directed assignments / constraints
        pairs: list[tuple[str, str]] = []
        for k, v in assigns.items():
            key = _safe_name(str(k), "field")
            val = str(v).strip()
            if not val:
                continue
            pairs.append((key, val))

        if pairs:
            if randomize:
                out.append(f"{indent}if (!tx.randomize() with {{")
                for k, v in pairs:
                    out.append(f"{indent}  {k} == ({v});")
                out.append(f"{indent}}}) begin")
                out.append(f"{indent}  `uvm_error(\"SEQ\", \"Randomization failed\")")
                out.append(f"{indent}end")
            else:
                for k, v in pairs:
                    out.append(f"{indent}tx.{k} = ({v});")

        out.append(f"{indent}finish_item(tx);")

        if repeat_n > 1:
            out.append("    end")

        return out

    if not steps:
        steps = [{"item_name": "tx", "delay": "0", "repeat": "1", "randomize": True, "assignments": {}}]

    for idx, step in enumerate(steps):
        block = render_step(step, idx=idx)
        if not block:
            continue
        lines.extend(block)
        lines.append("")

    lines.append("  endtask")
    lines.append("")
    lines.append(f"endclass : {name}")
    return "\n".join(lines) + "\n"


def _render_agent_and_components(state: dict) -> dict[str, str]:
    agent_cfg = state.get("agent", {}) or {}
    txn = _safe_name(agent_cfg.get("transaction", "txn_item"), "txn_item")
    agent_name = _safe_name(agent_cfg.get("agent_name", "my_agent"), "my_agent")
    is_active = (agent_cfg.get("type") or "active").strip() == "active"
    include = (agent_cfg.get("include_components") or {}) if isinstance(agent_cfg.get("include_components"), dict) else {}
    inc_seqr = bool(include.get("sequencer", True))
    inc_drv = bool(include.get("driver", True))
    inc_mon = bool(include.get("monitor", True))

    # Allow user-edited code to win if enabled
    agent_code = state.get("agent_code", {}) or {}
    use_custom = bool(agent_cfg.get("use_custom_code", False))
    out: dict[str, str] = {}
    if use_custom and isinstance(agent_code, dict) and agent_code:
        for k, v in agent_code.items():
            if isinstance(v, str) and v.strip():
                out[f"{k}.sv"] = v.strip() + "\n"
        if out:
            return out

    agent_lines = [f"class {agent_name} extends uvm_agent;", f"  `uvm_component_utils({agent_name})", ""]
    if inc_seqr:
        agent_lines.append(f"  uvm_sequencer #({txn}) seqr;")
    if inc_drv:
        agent_lines.append(f"  uvm_driver #({txn}) drv;")
    if inc_mon:
        agent_lines.append(f"  {agent_name}_monitor mon;")
    agent_lines.append("")
    agent_lines.append("  function new(string name, uvm_component parent);")
    agent_lines.append("    super.new(name, parent);")
    agent_lines.append("  endfunction")
    agent_lines.append("")
    agent_lines.append("  function void build_phase(uvm_phase phase);")
    agent_lines.append("    super.build_phase(phase);")
    if is_active:
        if inc_seqr:
            agent_lines.append(
                f"    seqr = uvm_sequencer #({txn})::type_id::create(\"seqr\", this);"
            )
        if inc_drv:
            agent_lines.append(
                f"    drv = uvm_driver #({txn})::type_id::create(\"drv\", this);"
            )
    if inc_mon:
        agent_lines.append(f"    mon = {agent_name}_monitor::type_id::create(\"mon\", this);")
    agent_lines.append("  endfunction")
    agent_lines.append("")
    agent_lines.append("  function void connect_phase(uvm_phase phase);")
    agent_lines.append("    super.connect_phase(phase);")
    if inc_seqr and inc_drv:
        agent_lines.append("    if (seqr != null && drv != null) drv.seq_item_port.connect(seqr.seq_item_export);")
    agent_lines.append("  endfunction")
    agent_lines.append("")
    agent_lines.append(f"endclass : {agent_name}")

    out["agent.sv"] = "\n".join(agent_lines) + "\n"

    if inc_drv:
        drv_name = f"{agent_name}_driver"
        out["driver.sv"] = (
            "\n".join(
                [
                    f"class {drv_name} extends uvm_driver #({txn});",
                    f"  `uvm_component_utils({drv_name})",
                    "",
                    "  function new(string name, uvm_component parent);",
                    "    super.new(name, parent);",
                    "  endfunction",
                    "",
                    "  task run_phase(uvm_phase phase);",
                    "    super.run_phase(phase);",
                    "    // Drive logic here",
                    "  endtask",
                    "",
                    f"endclass : {drv_name}",
                    "",
                ]
            )
        )

    if inc_mon:
        mon_name = f"{agent_name}_monitor"
        out["monitor.sv"] = (
            "\n".join(
                [
                    f"class {mon_name} extends uvm_monitor;",
                    f"  `uvm_component_utils({mon_name})",
                    "",
                    f"  uvm_analysis_port #({txn}) ap;",
                    "",
                    "  function new(string name, uvm_component parent);",
                    "    super.new(name, parent);",
                    "    ap = new(\"ap\", this);",
                    "  endfunction",
                    "",
                    "  task run_phase(uvm_phase phase);",
                    "    super.run_phase(phase);",
                    f"    // Sample bus and publish {txn} on ap",
                    "  endtask",
                    "",
                    f"endclass : {mon_name}",
                    "",
                ]
            )
        )

    if inc_seqr:
        seqr_name = f"{agent_name}_sequencer"
        out["sequencer.sv"] = (
            "\n".join(
                [
                    f"class {seqr_name} extends uvm_sequencer #({txn});",
                    f"  `uvm_component_utils({seqr_name})",
                    "",
                    "  function new(string name, uvm_component parent);",
                    "    super.new(name, parent);",
                    "  endfunction",
                    "",
                    f"endclass : {seqr_name}",
                    "",
                ]
            )
        )

    return out


def _render_scoreboard(state: dict) -> str:
    sb = state.get("scoreboard", {}) or {}
    name = _safe_name(sb.get("name", "my_scoreboard"), "my_scoreboard")
    txn = _safe_name(sb.get("transaction", "txn_item"), "txn_item")
    use_queue = bool(sb.get("use_expected_queue", sb.get("use_queue", True)))
    use_cov = bool(sb.get("enable_coverage", sb.get("use_coverage", False)))
    compare_mode = (sb.get("compare_mode") or "uvm_compare").strip()
    selected_fields = sb.get("fields", []) or []
    if not isinstance(selected_fields, list):
        selected_fields = []

    txn_cfg = state.get("transaction", {}) or {}
    txn_fields = txn_cfg.get("fields", []) or []
    txn_type_by_name: dict[str, str] = {}
    if isinstance(txn_fields, list):
        for f in txn_fields:
            if not isinstance(f, dict):
                continue
            n = str(f.get("name") or "").strip()
            if not n:
                continue
            txn_type_by_name[n] = str(f.get("type") or "")

    def is_integral_type(type_str: str) -> bool:
        t = (type_str or "").lower()
        if "string" in t:
            return False
        if "class" in t or "handle" in t or "*" in t:
            return False
        if "uvm_object" in t or "uvm_" in t:
            return False
        return True

    lines = [f"class {name} extends uvm_component;", f"  `uvm_component_utils({name})", ""]
    lines.append(f"  uvm_analysis_imp #({txn}, {name}) ap;")
    if use_queue:
        lines.append(f"  {txn} expected_q[$];")
    lines.append("  int unsigned pass_count;")
    lines.append("  int unsigned fail_count;")
    if use_queue:
        lines.append("  int unsigned expected_count;")
    lines.append("")

    cov_fields = [n for n in selected_fields if is_integral_type(txn_type_by_name.get(n, ""))] if use_cov else []
    if use_cov:
        lines.append("  // Coverage (auto-generated)")
        lines.append(f"  covergroup cg_t with function sample({txn} t);")
        if cov_fields:
            for n in cov_fields:
                safe_n = _safe_name(n, "sig")
                lines.append(f"    coverpoint t.{safe_n};")
        else:
            lines.append("    // No integral fields selected for coverage")
        lines.append("  endgroup")
        lines.append("")
        lines.append("  cg_t cg;")
        lines.append("")

    lines.append("  function new(string name, uvm_component parent);")
    lines.append("    super.new(name, parent);")
    lines.append("    ap = new(\"ap\", this);")
    if use_cov:
        lines.append("    cg = new();")
    lines.append("  endfunction")
    lines.append("")

    if use_queue:
        lines.append(f"  function void expect({txn} exp);")
        lines.append("    expected_q.push_back(exp);")
        lines.append("    expected_count++;")
        lines.append("  endfunction")
        lines.append("")

    lines.append(f"  function void write({txn} tx);")
    if use_cov:
        lines.append("    cg.sample(tx);")
        lines.append("")

    if use_queue:
        lines.append("    if (expected_q.size() == 0) begin")
        lines.append("      `uvm_error(\"SB\", \"Received tx but expected_q is empty\")")
        lines.append("      fail_count++;")
        lines.append("      return;")
        lines.append("    end")
        lines.append("")
        lines.append(f"    {txn} exp;")
        lines.append("    exp = expected_q.pop_front();")
        lines.append("")

        if compare_mode == "manual" and selected_fields:
            lines.append("    bit ok = 1;")
            for field_name in selected_fields:
                safe_n = _safe_name(field_name, "field")
                lines.append(f"    if (tx.{safe_n} !== exp.{safe_n}) begin")
                lines.append(
                    f"      `uvm_error(\"SB\", $sformatf(\"Mismatch {safe_n}: act=%0h exp=%0h\", tx.{safe_n}, exp.{safe_n}))"
                )
                lines.append("      ok = 0;")
                lines.append("    end")
            lines.append("    if (ok) pass_count++; else fail_count++;")
        else:
            lines.append("    uvm_comparer cmp = new();")
            lines.append("    if (!tx.compare(exp, cmp)) begin")
            lines.append("      `uvm_error(\"SB\", \"Transaction compare failed\")")
            lines.append("      fail_count++;")
            lines.append("    end else begin")
            lines.append("      pass_count++;")
            lines.append("    end")
    else:
        lines.append("    // Add checks here (no expected queue)")
        lines.append("    pass_count++;")

    lines.append("  endfunction")
    lines.append("")

    lines.append("  function void report_phase(uvm_phase phase);")
    lines.append("    super.report_phase(phase);")
    if use_queue:
        lines.append(
            "    `uvm_info(\"SB\", $sformatf(\"pass=%0d fail=%0d expected_seen=%0d pending_expected=%0d\", pass_count, fail_count, expected_count, expected_q.size()), UVM_LOW)"
        )
    else:
        lines.append(
            "    `uvm_info(\"SB\", $sformatf(\"pass=%0d fail=%0d\", pass_count, fail_count), UVM_LOW)"
        )
    lines.append("  endfunction")
    lines.append("")
    lines.append(f"endclass : {name}")
    return "\n".join(lines) + "\n"


def _render_environment(state: dict) -> str:
    env = state.get("environment", {}) or {}
    name = _safe_name(env.get("name", "env"), "env")
    include_agent = bool(env.get("include_agent", True))
    include_sb = bool(env.get("include_scoreboard", True))

    agent_cfg = state.get("agent", {}) or {}
    agent_name = _safe_name(agent_cfg.get("agent_name", "my_agent"), "my_agent")
    include_components = (
        agent_cfg.get("include_components")
        if isinstance(agent_cfg.get("include_components"), dict)
        else agent_cfg.get("components")
    )
    has_monitor = True
    if isinstance(include_components, dict):
        has_monitor = bool(include_components.get("monitor", True))

    sb_cfg = state.get("scoreboard", {}) or {}
    sb_name = _safe_name(sb_cfg.get("name", "my_scoreboard"), "my_scoreboard")

    lines = [f"class {name} extends uvm_env;", f"  `uvm_component_utils({name})", ""]
    if include_agent:
        lines.append(f"  {agent_name} agent;")
    if include_sb:
        lines.append(f"  {sb_name} sb;")
    lines.append("")
    lines.append("  function new(string name, uvm_component parent);")
    lines.append("    super.new(name, parent);")
    lines.append("  endfunction")
    lines.append("")
    lines.append("  function void build_phase(uvm_phase phase);")
    lines.append("    super.build_phase(phase);")
    if include_agent:
        lines.append(f"    agent = {agent_name}::type_id::create(\"agent\", this);")
    if include_sb:
        lines.append(f"    sb = {sb_name}::type_id::create(\"sb\", this);")
    lines.append("  endfunction")
    lines.append("")
    lines.append("  function void connect_phase(uvm_phase phase);")
    lines.append("    super.connect_phase(phase);")
    if include_agent and include_sb:
        if has_monitor:
            lines.append("    // Connect monitor analysis port to scoreboard")
            lines.append("    agent.mon.ap.connect(sb.ap);")
        else:
            lines.append("    // Monitor disabled in agent; no auto-connect to scoreboard")
    lines.append("  endfunction")
    lines.append("")
    lines.append(f"endclass : {name}")
    return "\n".join(lines) + "\n"


def _render_test(state: dict) -> str:
    test = state.get("test", {}) or {}
    name = _safe_name(test.get("name", "base_test"), "base_test")
    base = _safe_name(test.get("base_class", "uvm_test"), "uvm_test")
    create_env = bool(test.get("create_env", True))
    env_name = _safe_name((state.get("environment", {}) or {}).get("name", "env"), "env")

    start_sequence = bool(test.get("start_sequence", False))
    sequence_name = _safe_name(test.get("sequence_name", (state.get("sequence", {}) or {}).get("name", "my_sequence")), "my_sequence")
    raise_objection = bool(test.get("raise_objection", True))
    print_topology = bool(test.get("print_topology", False))

    agent_cfg = state.get("agent", {}) or {}
    agent_name = _safe_name(agent_cfg.get("agent_name", "my_agent"), "my_agent")
    include_components = (
        agent_cfg.get("include_components")
        if isinstance(agent_cfg.get("include_components"), dict)
        else agent_cfg.get("components")
    )
    has_sequencer = True
    if isinstance(include_components, dict):
        has_sequencer = bool(include_components.get("sequencer", True))

    env_cfg = state.get("environment", {}) or {}
    env_includes_agent = bool(env_cfg.get("include_agent", True))

    lines = [f"class {name} extends {base};", f"  `uvm_component_utils({name})", ""]
    if create_env:
        lines.append(f"  {env_name} env_h;")
        lines.append("")
    lines.append("  function new(string name, uvm_component parent);")
    lines.append("    super.new(name, parent);")
    lines.append("  endfunction")
    lines.append("")
    lines.append("  function void build_phase(uvm_phase phase);")
    lines.append("    super.build_phase(phase);")
    if create_env:
        lines.append(f"    env_h = {env_name}::type_id::create(\"env_h\", this);")
    lines.append("  endfunction")
    lines.append("")

    if print_topology:
        lines.append("  function void end_of_elaboration_phase(uvm_phase phase);")
        lines.append("    super.end_of_elaboration_phase(phase);")
        lines.append("    uvm_top.print_topology();")
        lines.append("  endfunction")
        lines.append("")

    lines.append("  task run_phase(uvm_phase phase);")
    lines.append("    super.run_phase(phase);")

    if start_sequence:
        lines.append("")
        if not create_env:
            lines.append("    // NOTE: start_sequence enabled but create_env is disabled")
        elif not env_includes_agent:
            lines.append("    // NOTE: environment does not include an agent; cannot start sequence")
        elif not has_sequencer:
            lines.append("    // NOTE: agent sequencer disabled; cannot start sequence")
        else:
            if raise_objection:
                lines.append("    phase.raise_objection(this);")
            lines.append(f"    {sequence_name} seq;")
            lines.append(f"    seq = {sequence_name}::type_id::create(\"seq\");")
            # The generator agent uses handle name "seqr" if included.
            lines.append("    seq.start(env_h.agent.seqr);")
            if raise_objection:
                lines.append("    phase.drop_objection(this);")
    lines.append("  endtask")
    lines.append("")
    lines.append(f"endclass : {name}")
    return "\n".join(lines) + "\n"


def _render_top(state: dict) -> str:
    project = state.get("project", {}) or {}
    top = state.get("top", {}) or {}
    interface = state.get("interface", {}) or {}
    test = state.get("test", {}) or {}

    top_name = _safe_name(top.get("name", "top_tb"), "top_tb")
    dut_module = (top.get("dut_module") or "").strip() or (project.get("module_name") or "").strip() or "dut"
    intf_name = _safe_name(interface.get("name", "my_if"), "my_if")
    test_name = _safe_name(test.get("name", "base_test"), "base_test")
    clk = (interface.get("clock") or "").strip()
    rst = (interface.get("reset") or "").strip()

    signals = interface.get("signals", []) or []
    sig_names = [str(s.get("name") or "").strip() for s in signals if isinstance(s, dict) and s.get("name")]
    sig_names = [n for n in sig_names if n]
    sig_set = set(sig_names)

    vif = "vif"

    dut_ports: list[str] = []
    dut_path = (top.get("dut_path") or "").strip()
    if dut_path:
        ports = _extract_module_ports_from_file(Path(dut_path), dut_module)
        if ports:
            dut_ports = ports

    conns: list[str] = []
    missing: list[str] = []
    if dut_ports:
        for p in dut_ports:
            if clk and p == clk:
                conns.append(f"    .{p}({clk})")
            elif rst and p == rst:
                conns.append(f"    .{p}({rst})")
            elif p in sig_set:
                conns.append(f"    .{p}({vif}.{p})")
            else:
                missing.append(p)
    else:
        # Fallback: connect by interface signal names (best effort)
        conns = [f"    .{n}({vif}.{n})" for n in sig_names]

    port_map = ",\n".join(conns)

    lines: list[str] = []
    lines.append("`timescale 1ns/1ps")
    lines.append("")
    lines.append("module " + top_name + ";")
    lines.append("")
    if clk:
        lines.append(f"  logic {clk};")
    if rst:
        lines.append(f"  logic {rst};")
    lines.append("")
    if clk or rst:
        conn = []
        if clk:
            conn.append(f".{clk}({clk})")
        if rst:
            conn.append(f".{rst}({rst})")
        lines.append(f"  {intf_name} {vif}({', '.join(conn)});")
    else:
        lines.append(f"  {intf_name} {vif}();")
    lines.append("")
    lines.append(f"  {dut_module} dut_inst (")
    lines.append(port_map if port_map else "    // TODO: connect DUT ports")
    lines.append("  );")
    lines.append("")
    if missing:
        lines.append("  // Unconnected DUT ports (not auto-matched):")
        for p in missing:
            lines.append(f"  // - {p}")
        lines.append("")
    if clk:
        lines.append("  initial begin")
        lines.append(f"    {clk} = 0;")
        lines.append("    forever #5 " + clk + " = ~" + clk + ";")
        lines.append("  end")
        lines.append("")
    if rst:
        lines.append("  initial begin")
        lines.append(f"    {rst} = 1;")
        lines.append("    #20;")
        lines.append(f"    {rst} = 0;")
        lines.append("  end")
        lines.append("")
    lines.append("  initial begin")
    lines.append("    run_test(\"" + test_name + "\");")
    lines.append("  end")
    lines.append("")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def _render_pkg(file_names: Iterable[str]) -> str:
    lines = ["package tb_pkg;", "  import uvm_pkg::*;", "  `include \"uvm_macros.svh\"", ""]
    for name in file_names:
        lines.append(f"  `include \"{name}\"")
    lines.append("")
    lines.append("endpackage : tb_pkg")
    return "\n".join(lines) + "\n"


def generate_files(state: dict) -> tuple[dict[Path, str], list[str]]:
    warnings: list[str] = []

    agent_files = _render_agent_and_components(state)
    src_files: dict[str, str] = {
        "interface.sv": _render_interface(state),
        "transaction.sv": _render_transaction(state),
        "sequence.sv": _render_sequence(state),
        "scoreboard.sv": _render_scoreboard(state),
        "environment.sv": _render_environment(state),
        "test.sv": _render_test(state),
        "top.sv": _render_top(state),
        **agent_files,
    }

    include_order = ["transaction.sv", "sequence.sv", "agent.sv"]
    for extra in [
        "driver.sv",
        "monitor.sv",
        "sequencer.sv",
        "scoreboard.sv",
        "environment.sv",
        "test.sv",
    ]:
        if extra in src_files and extra not in include_order:
            include_order.append(extra)

    src_files["tb_pkg.sv"] = _render_pkg([n for n in include_order if n in src_files])

    project = state.get("project", {}) or {}
    project_name = _safe_name(project.get("project_name", "testbench"), "testbench")
    payload = {
        "project_name": project_name,
        "generated_files": sorted(src_files.keys()),
    }

    files: dict[Path, str] = {}
    files[Path("manifest.json")] = json.dumps(payload, indent=2) + "\n"
    filelist_entries = [f"src/{n}" for n in ("interface.sv", "tb_pkg.sv", "top.sv") if n in src_files]
    files[Path("filelist.f")] = "\n".join(filelist_entries) + "\n"
    files[Path("README.md")] = (
        f"# {project_name}\n\nGenerated by Testbench Ecosystem.\n\n"
        "## Files\n\n- `src/tb_pkg.sv`\n- `src/top.sv`\n"
    )
    for filename, content in src_files.items():
        files[Path("src") / filename] = content

    # Optional user overrides (editable from Preview page)
    custom_files = state.get("custom_files", {}) or {}
    enabled = bool(state.get("custom_files_enabled", True))
    if enabled and isinstance(custom_files, dict) and custom_files:
        for k, v in custom_files.items():
            rel = _safe_rel_path(str(k))
            if rel is None:
                warnings.append(f"Ignored override with unsafe path: {k!r}")
                continue
            try:
                content = str(v)
            except Exception:
                warnings.append(f"Ignored override (non-string content) for: {rel.as_posix()}")
                continue
            if content and not content.endswith("\n"):
                content += "\n"
            files[rel] = content

    return files, warnings


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", newline="\n", dir=str(path.parent)) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def generate_project(state: dict) -> GenerationResult:
    errors = validate_state(state)
    if errors:
        raise ValueError("\n".join(errors))

    project = state.get("project", {}) or {}
    output_dir = Path(str(project.get("output_dir", "")).strip())
    project_name = _safe_name(project.get("project_name", "testbench"), "testbench")
    output_root = output_dir / project_name

    files, warnings = generate_files(state)
    written: list[Path] = []
    for rel_path, content in files.items():
        abs_path = output_root / rel_path
        _atomic_write(abs_path, content)
        written.append(abs_path)

    return GenerationResult(output_root=output_root, files_written=tuple(written), warnings=tuple(warnings))


def render_preview(state: dict) -> str:
    files, warnings = generate_files(state)
    parts: list[str] = []
    if warnings:
        parts.append("// WARNINGS:\n" + "\n".join([f"// - {w}" for w in warnings]) + "\n\n")
    for path in sorted(files.keys(), key=lambda p: str(p)):
        if str(path).endswith(".sv"):
            parts.append(f"// ===== {path.as_posix()} =====\n")
            parts.append(files[path])
            parts.append("\n")
    return "".join(parts)
