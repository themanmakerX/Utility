from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    BLOCKED = "blocked"
    READY = "ready"
    COMPLETE = "complete"


@dataclass(frozen=True)
class ModuleStatus:
    status: Status
    missing: tuple[str, ...] = ()
    hint: str = ""


def _has_text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def compute_module_statuses(state: dict) -> dict[str, ModuleStatus]:
    project = state.get("project", {}) or {}
    interface = state.get("interface", {}) or {}
    transaction = state.get("transaction", {}) or {}
    agent = state.get("agent", {}) or {}
    scoreboard = state.get("scoreboard", {}) or {}
    environment = state.get("environment", {}) or {}
    sequence = state.get("sequence", {}) or {}
    test = state.get("test", {}) or {}
    top = state.get("top", {}) or {}

    statuses: dict[str, ModuleStatus] = {}

    missing_project = []
    if not _has_text(project.get("project_name", "")):
        missing_project.append("Project Name")
    if not _has_text(project.get("output_dir", "")):
        missing_project.append("Output Directory")
    if not _has_text(project.get("dut_path", "")):
        missing_project.append("DUT File Path")
    statuses["project_details"] = (
        ModuleStatus(Status.COMPLETE)
        if not missing_project and "project" in state
        else ModuleStatus(Status.READY, tuple(missing_project), "Fill project basics and save.")
    )

    missing_interface = []
    if "project" not in state:
        statuses["interface_dut"] = ModuleStatus(
            Status.BLOCKED, ("Project Details",), "Save Project Details first."
        )
    else:
        if not _has_text(interface.get("name", "")):
            missing_interface.append("Interface Name")
        if not interface.get("signals"):
            missing_interface.append("Signals")
        if not _has_text(interface.get("clock", "")):
            missing_interface.append("Clock Signal")
        if not _has_text(interface.get("reset", "")):
            missing_interface.append("Reset Signal")
        statuses["interface_dut"] = (
            ModuleStatus(Status.COMPLETE)
            if not missing_interface and "interface" in state
            else ModuleStatus(
                Status.READY,
                tuple(missing_interface),
                "Import signals from DUT and choose clock/reset.",
            )
        )

    if "interface" not in state:
        statuses["transaction_class"] = ModuleStatus(
            Status.BLOCKED, ("Interface",), "Define Interface first (then Import fields)."
        )
    else:
        missing_txn = []
        if not _has_text(transaction.get("class_name", "")):
            missing_txn.append("Class Name")
        if not transaction.get("fields"):
            missing_txn.append("Fields")
        statuses["transaction_class"] = (
            ModuleStatus(Status.COMPLETE)
            if not missing_txn and "transaction" in state
            else ModuleStatus(Status.READY, tuple(missing_txn), "Import from Interface.")
        )

    if "transaction" not in state:
        statuses["agent_class"] = ModuleStatus(
            Status.BLOCKED, ("Transaction",), "Define Transaction first."
        )
    else:
        missing_agent = []
        if not _has_text(agent.get("agent_name", "")):
            missing_agent.append("Agent Name")
        statuses["agent_class"] = (
            ModuleStatus(Status.COMPLETE)
            if not missing_agent and "agent" in state
            else ModuleStatus(Status.READY, tuple(missing_agent), "Configure agent components.")
        )

    # Scoreboard is optional, but mark ready when transaction exists.
    if "transaction" not in state:
        statuses["scoreboard_class"] = ModuleStatus(
            Status.BLOCKED, ("Transaction",), "Define Transaction first."
        )
    else:
        missing_sb = []
        if scoreboard and not _has_text(scoreboard.get("name", "")):
            missing_sb.append("Scoreboard Name")
        statuses["scoreboard_class"] = (
            ModuleStatus(Status.COMPLETE)
            if "scoreboard" in state and not missing_sb
            else ModuleStatus(Status.READY, tuple(missing_sb), "Optional: add scoreboard.")
        )

    if "agent" not in state:
        statuses["environment_class"] = ModuleStatus(
            Status.BLOCKED, ("Agent",), "Configure Agent first."
        )
    else:
        missing_env = []
        if not _has_text(environment.get("name", "")):
            missing_env.append("Environment Name")
        statuses["environment_class"] = (
            ModuleStatus(Status.COMPLETE)
            if not missing_env and "environment" in state
            else ModuleStatus(Status.READY, tuple(missing_env), "Include agent/scoreboard as needed.")
        )

    if "transaction" not in state:
        statuses["sequence_class"] = ModuleStatus(
            Status.BLOCKED, ("Transaction",), "Define Transaction first."
        )
    else:
        missing_seq = []
        if not _has_text(sequence.get("name", "")):
            missing_seq.append("Sequence Name")
        statuses["sequence_class"] = (
            ModuleStatus(Status.COMPLETE)
            if not missing_seq and "sequence" in state
            else ModuleStatus(Status.READY, tuple(missing_seq), "Add steps and preview.")
        )

    if "environment" not in state:
        statuses["test_class"] = ModuleStatus(
            Status.BLOCKED, ("Environment",), "Define Environment first."
        )
    else:
        missing_test = []
        if not _has_text(test.get("name", "")):
            missing_test.append("Test Name")
        statuses["test_class"] = (
            ModuleStatus(Status.COMPLETE)
            if not missing_test and "test" in state
            else ModuleStatus(Status.READY, tuple(missing_test), "Create env instance if needed.")
        )

    if "test" not in state or "interface" not in state:
        statuses["top_module"] = ModuleStatus(
            Status.BLOCKED, ("Test", "Interface"), "Define Test and Interface first."
        )
    else:
        missing_top = []
        if not _has_text(top.get("name", "")):
            missing_top.append("Top Name")
        if not _has_text(top.get("dut_module", "")) and not _has_text(
            project.get("module_name", "")
        ):
            missing_top.append("DUT Module")
        statuses["top_module"] = (
            ModuleStatus(Status.COMPLETE)
            if not missing_top and "top" in state
            else ModuleStatus(Status.READY, tuple(missing_top), "Detect DUT module and preview.")
        )

    # Preview and state machine pages are always accessible
    statuses["preview"] = ModuleStatus(Status.READY)
    statuses["state_machine"] = ModuleStatus(Status.READY)
    statuses["dashboard"] = ModuleStatus(Status.READY)

    return statuses

