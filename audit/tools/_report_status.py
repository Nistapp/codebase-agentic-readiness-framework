# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The draft's progress for `report.py`: which checks are missing, which findings wait, what stops a final report and
what the recipe does next. `report.py` re-exports every name.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Mapping, Sequence

import validate_report as vr
from _report_checks import accounted_checks
from _report_draft import expected_checks


LISTED_IDS = 20

SEVERITY_ORDER = {"BLOCKER": 0, "DEGRADER": 1, "COSMETIC": 2}


def family_of(check_id: str) -> str:
    return check_id.split("-", 1)[0]


def missing_checks(document: Mapping[str, Any]) -> dict[str, list[str]]:
    """The expected checks that the draft does not hold, by family, in catalogue order."""
    recorded = accounted_checks(document)
    missing: dict[str, list[str]] = {}
    for check in expected_checks():
        if check["id"] not in recorded:
            missing.setdefault(family_of(check["id"]), []).append(check["id"])
    return missing


def pending_findings(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The findings still waiting for a decision, blockers first, then in the order they were recorded."""
    waiting = [finding for finding in document["findings"] if finding["disposition"] == "pending"]
    return sorted(waiting, key=lambda finding: SEVERITY_ORDER[finding["severity"]])


def undecided_blockers(document: Mapping[str, Any]) -> list[str]:
    """The ids of the BLOCKER findings that have a decision, but not one a person gave for that finding alone.

    ``confirmed_via: "policy"`` is excluded: it is reachable only under `accept-all`, which is itself legal only
    in eval mode (no person to ask), so a policy-confirmed BLOCKER is decided by design, not left undecided.
    """
    return [
        finding["id"]
        for finding in document["findings"]
        if finding["severity"] == "BLOCKER"
        and finding["disposition"] != "pending"
        and finding.get("confirmed_via") not in ("interactive", "policy")
    ]


def blocking_reasons(document: Mapping[str, Any]) -> list[str]:
    """What stands between this draft and a final report, in a few words each. Empty when nothing does."""
    if document["status"] == "final":
        return ["the report is already final"]
    reasons: list[str] = []
    if document["run_context"]["eval_mode"]:
        reasons.append("this is an eval-mode run, and its report is never final")
    absent = sum(len(ids) for ids in missing_checks(document).values())
    if absent:
        reasons.append(f"{absent} of {len(expected_checks())} checks are not recorded")
    waiting = len(pending_findings(document))
    if waiting:
        reasons.append(f"{waiting} finding{'' if waiting == 1 else 's'} {'is' if waiting == 1 else 'are'} pending")
    undecided = len(undecided_blockers(document))
    if undecided:
        reasons.append(f"{undecided} BLOCKER finding{'' if undecided == 1 else 's'} not decided interactively")
    return reasons


#: How a command the recipe runs names a tool: by its path from the folder that holds the recipe (audit/SKILL.md, Tools).
REPORT_TOOL = ("python3", "audit/tools/report.py")


def engine_arguments(document: Mapping[str, Any], out_dir: Path) -> list[str]:
    """The `engine.py` arguments Stage 2, step 1 of audit/SKILL.md names, from what the draft's intake recorded.

    The label is the draft's, so every file of the run carries one. `--no-user-config` and `--emit-baseline` are always
    passed. The excluded paths are passed as `--exclude`, and each allowed probe verb as `--allow-probe`, with
    `--run-gates` and the recorded per-command timeout only when at least one verb is allowed.
    """
    target = document["provenance"]["target"]
    context = document["run_context"]
    argv = [target["path"], "--out-dir", str(out_dir), "--repo-label", target["label"], "--no-user-config"]
    for pattern in context["excluded"]:
        argv += ["--exclude", pattern]
    verbs = context["probes"]["allowed"]
    if verbs:
        argv.append("--run-gates")
        for verb in verbs:
            argv += ["--allow-probe", verb]
        argv += ["--timeout", str(context["probes"]["timeout_s"])]
    argv.append("--emit-baseline")
    return argv


def command_line(tool: Sequence[str], *arguments: str) -> str:
    """One command as a person types it in a POSIX shell, every argument quoted where it needs to be."""
    return shlex.join([*tool, *arguments])


def next_step(path: Path, document: Mapping[str, Any]) -> tuple[str, str | None]:
    """What the audit recipe does next with this draft, and the command that does it (None when there is none).

    The text starts with the stage and the step of audit/SKILL.md. The rule is the recipe's "Resuming" section: no
    engine import yet is Stage 2, step 1; a family with a check not recorded is Stage 2, step 3, for the first such
    family in the catalogue's order; findings pending are Stage 4; a draft ready to finalise is Stage 5. An eval-mode
    draft whose families are all done follows the eval-mode lines of Stages 4 and 5: it stops at the draft. Paths in
    the command are absolute.
    """
    draft = str(path.expanduser().resolve())
    if document["status"] == "final":
        return "Nothing: the report is final. To implement it, give its path to the implement recipe.", None
    if "engine" not in document["provenance"]:
        command = command_line(REPORT_TOOL, "run-engine", draft, "--out-dir", str(Path(draft).parent))
        return "Stage 2, steps 1 and 2: run the engine with the intake's flags and bring its report in.", command
    missing = missing_checks(document)
    if missing:
        family = next(iter(missing))
        names = {entry["id"]: entry["name"] for entry in vr.load_catalogue()["families"]}
        count = len(missing[family])
        return (
            f"Stage 2, step 3: assess the {names.get(family, family)} ({family}) family, check by check; "
            f"{count} check{'' if count == 1 else 's'} not recorded.",
            command_line(REPORT_TOOL, "add-check", draft, "--from", "-"),
        )
    if document["run_context"]["eval_mode"]:
        return (
            "Stage 5, step 1: eval mode, so stop at the draft; it is this run's result, and finalise refuses it.",
            None,
        )
    waiting = pending_findings(document)
    if waiting and waiting[0]["severity"] == "BLOCKER":
        finding = waiting[0]["id"]
        return (
            f"Stage 4, step 2: ask the person about BLOCKER finding {finding}, on its own.",
            command_line(REPORT_TOOL, "set-disposition", draft, "--via", "interactive", "--finding", finding)
            + " --disposition <disposition>",
        )
    if waiting:
        return (
            f"Stage 4, step 3: ask the person about the {len(waiting)} other pending findings, in batches.",
            command_line(REPORT_TOOL, "set-disposition", draft, "--via", "batch", "--from", "-"),
        )
    undecided = undecided_blockers(document)
    if undecided:
        return (
            f"Stage 4, step 2: ask the person about BLOCKER finding {undecided[0]} again; no person decided it alone.",
            command_line(REPORT_TOOL, "set-disposition", draft, "--via", "interactive", "--finding", undecided[0])
            + " --disposition <disposition>",
        )
    return "Stage 5, step 3: finalise the draft.", command_line(REPORT_TOOL, "finalise", draft)


def listed(ids: Sequence[str]) -> str:
    """The first `LISTED_IDS` ids, and how many more there are."""
    shown = " ".join(ids[:LISTED_IDS])
    return shown if len(ids) <= LISTED_IDS else f"{shown} and {len(ids) - LISTED_IDS} more"


def finalisation_errors(document: Mapping[str, Any]) -> list[str]:
    """Everything that stops a draft becoming final, one problem to a line, the same facts `status` summarises."""
    errors: list[str] = []
    if document["run_context"]["eval_mode"]:
        errors.append("this is an eval-mode run, and its report is never final")
    for family, ids in missing_checks(document).items():
        errors.append(f"checks not recorded in {family}: {' '.join(ids)}")
    waiting = [finding["id"] for finding in pending_findings(document)]
    if waiting:
        errors.append(f"{len(waiting)} finding{'' if len(waiting) == 1 else 's'} still pending: {listed(waiting)}")
    undecided = undecided_blockers(document)
    if undecided:
        errors.append(f"BLOCKER findings not decided interactively: {listed(undecided)}")
    return errors
