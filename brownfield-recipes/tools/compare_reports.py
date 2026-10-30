# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Compare two audit reports of the same repository: what moved, and which moves the readiness state explains.

    compare_reports.py <before.json> <after.json> [--state <state.json>] [--json]

Reads both reports (each must validate) and, optionally, the implement recipe's state file. It writes nothing.

Checks are matched by id. A check is ``improved`` or ``regressed`` when its verdict moves along FAIL < PARTIAL < PASS;
a move to or from UNKNOWN or NOT_APPLICABLE is ``changed`` (no order exists), and a check present in only one report
is ``added`` or ``removed``. Findings are matched by their ``key``. A key in ``before`` only is ``closed``, a key in
``after`` only is ``new``, a key in both is ``moved`` when its severity differs and ``unchanged`` otherwise. Findings
whose disposition is ``rejected`` were never confirmed gaps and are left out on both sides (counted in the summary).

With ``--state`` every move gets a label. The state's items name findings of the *before* report, so an item is read
only when its check agrees with that report. ``explained:done`` and ``explained:partial`` follow from an item that
reached that status; any other status, a finding with no item, a regression and a new finding are ``unexplained``.
Without ``--state`` the label is ``-``. The tool judges nothing else: it does not know which engine defects
distorted a verdict (the caller annotates those).

The output is deterministic. By default ``data`` holds ``summary`` and ``markdown``; with ``--json`` it holds
``summary``, ``checks`` and ``findings`` instead.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import _common
import progress
import validate_report

INFO = _common.ToolInfo(
    name="compare_reports",
    summary="Compare two audit reports: which checks and findings moved, and which moves the readiness state explains.",
    synopsis=("compare_reports.py BEFORE AFTER [--state STATE] [--json]",),
    writes="nothing",
)

RANK = {"FAIL": 0, "PARTIAL": 1, "PASS": 2}
NO_LABEL = "-"
UNEXPLAINED = "unexplained"
EXPLAINING = ("done", "partial")


def check_move(before: str | None, after: str | None) -> str:
    if before is None:
        return "added"
    if after is None:
        return "removed"
    if before == after:
        return "unchanged"
    if before in RANK and after in RANK:
        return "improved" if RANK[after] > RANK[before] else "regressed"
    return "changed"


def items_by_finding(state: Mapping[str, Any] | None, before: Mapping[str, Any]) -> tuple[dict[str, str], list[str]]:
    """Status of each state item that belongs to the before report, and a warning for each one that does not."""
    if state is None:
        return {}, []
    checks = {finding["id"]: finding["check"] for finding in before["findings"]}
    statuses: dict[str, str] = {}
    warnings: list[str] = []
    for item in state["items"]:
        if checks.get(item["finding"]) == item["check"]:
            statuses[item["finding"]] = item["status"]
        else:
            warnings.append(
                f"state item {item['finding']} ({item['check']}) does not match the before report; it explains nothing"
            )
    return statuses, warnings


def label_closed(statuses: Mapping[str, str], finding_id: str) -> str:
    status = statuses.get(finding_id)
    if status in EXPLAINING:
        return f"explained:{status}"
    return UNEXPLAINED if status is None else f"{UNEXPLAINED}:{status}"


def compare_checks(
    before: Mapping[str, Any], after: Mapping[str, Any], statuses: Mapping[str, str], with_state: bool
) -> list[dict[str, Any]]:
    old = {check["id"]: check["verdict"] for check in before["checks"]}
    new = {check["id"]: check["verdict"] for check in after["checks"]}
    findings_of: dict[str, list[str]] = {}
    for finding in before["findings"]:
        if finding["disposition"] != "rejected":
            findings_of.setdefault(finding["check"], []).append(finding["id"])
    rows: list[dict[str, Any]] = []
    for check_id in sorted(set(old) | set(new)):
        move = check_move(old.get(check_id), new.get(check_id))
        label = NO_LABEL
        if with_state and move != "unchanged":
            reached = sorted({statuses[f] for f in findings_of.get(check_id, []) if statuses.get(f) in EXPLAINING})
            label = f"explained:{'+'.join(reached)}" if move == "improved" and reached else UNEXPLAINED
        rows.append(
            {"check": check_id, "before": old.get(check_id), "after": new.get(check_id), "move": move, "label": label}
        )
    return rows


def compare_findings(
    before: Mapping[str, Any], after: Mapping[str, Any], statuses: Mapping[str, str], with_state: bool
) -> tuple[list[dict[str, Any]], int]:
    kept_before = {f["key"]: f for f in before["findings"] if f["disposition"] != "rejected"}
    kept_after = {f["key"]: f for f in after["findings"] if f["disposition"] != "rejected"}
    rejected = len(before["findings"]) - len(kept_before) + len(after["findings"]) - len(kept_after)
    rows: list[dict[str, Any]] = []
    for key in sorted(set(kept_before) | set(kept_after)):
        old, new = kept_before.get(key), kept_after.get(key)
        row: dict[str, Any] = {"key": key, "check": (old or new or {})["check"]}
        if old is not None and new is None:
            row.update(move="closed", before=old["id"], after=None, severity=old["severity"])
            row["label"] = label_closed(statuses, old["id"]) if with_state else NO_LABEL
        elif old is None and new is not None:
            row.update(move="new", before=None, after=new["id"], severity=new["severity"])
            row["label"] = UNEXPLAINED if with_state else NO_LABEL
        elif old is not None and new is not None:
            moved = old["severity"] != new["severity"]
            row.update(move="moved" if moved else "unchanged", before=old["id"], after=new["id"])
            row["severity"] = f"{old['severity']} -> {new['severity']}" if moved else new["severity"]
            row["label"] = NO_LABEL
            if with_state and moved:
                row["label"] = (
                    UNEXPLAINED if statuses.get(old["id"]) not in EXPLAINING else f"explained:{statuses[old['id']]}"
                )
            if with_state and not moved:
                state_status = statuses.get(old["id"])
                row["state"] = state_status
        rows.append(row)
    return rows, rejected


def counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[row["move"]] = out.get(row["move"], 0) + 1
    return dict(sorted(out.items()))


def table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def cell(value: object) -> str:
    text = "-" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def score(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    return f"{summary['phase1_score']} ({summary['blockers_remaining']['total']} blockers)"


def render(
    summary: Mapping[str, Any],
    checks: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
    omitted: Mapping[str, int],
) -> str:
    lines = [
        f"# Audit comparison: {summary['label']}",
        "",
        f"- Before: `{summary['before']['report']}` at `{summary['before']['git_sha']}`, score {summary['before']['score']}",
        f"- After: `{summary['after']['report']}` at `{summary['after']['git_sha']}`, score {summary['after']['score']}",
        f"- State: {'used' if summary['state_used'] else 'not given, labels are `-`'}",
        f"- Checks: {_counts_text(summary['checks'])}",
        f"- Findings: {_counts_text(summary['findings'])}; {summary['rejected_ignored']} rejected ignored",
        f"- Unexplained moves: {summary['unexplained']}",
        "",
        "## Checks that moved",
        "",
    ]
    moved = [row for row in checks if row["move"] != "unchanged"]
    if moved:
        lines += table(
            ["Check", "Before", "After", "Move", "Label"],
            [[cell(r["check"]), cell(r["before"]), cell(r["after"]), r["move"], cell(r["label"])] for r in moved],
        )
    else:
        lines.append("None.")
    lines += ["", "## Findings that moved", ""]
    changed = [row for row in findings if row["move"] != "unchanged"]
    if changed:
        lines += table(
            ["Key", "Check", "Move", "Before", "After", "Severity", "Label"],
            [
                [
                    cell(r["key"]),
                    cell(r["check"]),
                    r["move"],
                    cell(r["before"]),
                    cell(r["after"]),
                    cell(r["severity"]),
                    cell(r["label"]),
                ]
                for r in changed
            ],
        )
    else:
        lines.append("None.")
    still = [row for row in findings if row["move"] == "unchanged"]
    lines += ["", "## Findings still open", ""]
    if still:
        lines += table(
            ["Key", "Check", "Before", "After", "Severity", "State"],
            [
                [
                    cell(r["key"]),
                    cell(r["check"]),
                    cell(r["before"]),
                    cell(r["after"]),
                    cell(r["severity"]),
                    cell(r.get("state")),
                ]
                for r in still
            ],
        )
    else:
        lines.append("None.")
    for name, count in omitted.items():
        lines += ["", f"{count} {name} rows left out to fit the output; use the report files for the rest."]
    return "\n".join(lines) + "\n"


def _counts_text(values: Mapping[str, int]) -> str:
    return ", ".join(f"{count} {name}" for name, count in values.items()) or "none"


def read_valid(path: str, which: str) -> Any:
    document = validate_report.read_report(Path(path).expanduser(), f"{which} report")
    outcome = validate_report.validate_document(document)
    if outcome.errors:
        count = len(outcome.errors)
        raise _common.ValidationFailed(
            f"the {which} report is not valid: {count} error{'' if count == 1 else 's'} in the {outcome.stage} stage",
            errors=outcome.errors,
        )
    return document


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="compare_reports.py", description=INFO.summary)
    parser.add_argument("before", help="the earlier audit report (JSON)")
    parser.add_argument("after", help="the later audit report (JSON)")
    parser.add_argument("--state", help="the readiness state (JSON) that tracked the work between the two audits")
    parser.add_argument("--json", action="store_true", help="return the structured comparison instead of the Markdown")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    before = read_valid(args.before, "before")
    after = read_valid(args.after, "after")
    state = progress.read_state(Path(args.state).expanduser()) if args.state else None
    warnings: list[str] = []
    labels = {before["provenance"]["target"]["label"], after["provenance"]["target"]["label"]}
    if len(labels) > 1:
        warnings.append(f"the reports are for different repositories: {', '.join(sorted(labels))}")
    statuses, state_warnings = items_by_finding(state, before)
    warnings += state_warnings
    with_state = state is not None
    checks = compare_checks(before, after, statuses, with_state)
    findings, rejected = compare_findings(before, after, statuses, with_state)
    unexplained = sum(1 for row in [*checks, *findings] if row["label"].startswith(UNEXPLAINED))
    summary: dict[str, Any] = {
        "label": after["provenance"]["target"]["label"],
        "before": {
            "report": Path(args.before).name,
            "git_sha": before["provenance"]["target"]["git_sha"],
            "score": score(before),
        },
        "after": {
            "report": Path(args.after).name,
            "git_sha": after["provenance"]["target"]["git_sha"],
            "score": score(after),
        },
        "state_used": with_state,
        "checks": counts(checks),
        "findings": counts(findings),
        "rejected_ignored": rejected,
        "unexplained": unexplained,
    }
    line = (
        f"compare_reports: {_counts_text(summary['checks'])} (checks); {_counts_text(summary['findings'])} (findings)"
    )
    if with_state:
        line += f"; {unexplained} unexplained"
    if args.json:
        kept_checks, omitted_checks = _common.bound_items(checks)
        kept_findings, omitted_findings = _common.bound_items(findings)
        data: dict[str, Any] = {"summary": summary, "checks": kept_checks, "findings": kept_findings}
        omitted = {"checks": omitted_checks, "findings": omitted_findings}
        if any(omitted.values()):
            data["omitted"] = {name: count for name, count in omitted.items() if count}
        return _common.Result(data=data, summary=line, warnings=warnings, truncated=any(omitted.values()))
    kept_checks, omitted_checks = _common.bound_items(checks, limit_bytes=_common.ITEM_BUDGET_BYTES // 3)
    kept_findings, omitted_findings = _common.bound_items(findings, limit_bytes=_common.ITEM_BUDGET_BYTES // 3)
    omitted_rows = {name: count for name, count in (("check", omitted_checks), ("finding", omitted_findings)) if count}
    markdown = render(summary, kept_checks, kept_findings, omitted_rows)
    return _common.Result(
        data={"summary": summary, "markdown": markdown}, summary=line, warnings=warnings, truncated=bool(omitted_rows)
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
