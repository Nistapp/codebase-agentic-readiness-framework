# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The tables of checks that need attention, the overrides and the evidence in full.

Private to ``render_report.py``. Every function reads a report and returns lines; none writes.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import _summary
from _render_evidence import evidence_cell, evidence_lines
from _render_facts import (
    attention_sentence,
    check_cell,
    decision_cell,
    findings_cite_evidence,
    findings_of,
    fix_cell,
    needs_attention,
    overridden,
    verdict_cell,
)
from _render_terms import BR, DECIDED_BY, NO_EVIDENCE, SEVERITIES
from _render_text import blocks, code, table, text


def attention_rows(report: Mapping[str, Any], severity: str) -> list[list[str]]:
    """One row for each finding of a check that needs attention, and one for such a check that has no finding."""
    grouped = findings_of(report)
    scored_ids = {c["id"] for c in _summary.scored_checks(report["checks"])}
    engine = report["provenance"].get("engine")
    rows: list[list[str]] = []
    first_with_fix: dict[tuple[str, str], str] = {}
    for check in report["checks"]:
        findings = grouped.get(check["id"], [])
        if check["severity"] != severity or not needs_attention(check, findings):
            continue
        entries: list[Mapping[str, Any] | None] = list(findings) if findings else [None]
        for position, finding in enumerate(entries):
            found = text(finding["statement"]) if finding is not None else (text(check["summary"]) or "—")
            if position == 0 and overridden(check):
                found += (
                    BR + f"**Overridden.** The engine's verdict was {check['engine_verdict']}. "
                    f"Reason: {text(check['override_reason'])}"
                )
            items, searches = (check["evidence"], check["searches"])
            if finding is not None and (finding["evidence"] or finding["searches"]):
                items, searches = finding["evidence"], finding["searches"]
                if position == 0 and overridden(check):
                    # The agent's counter-evidence for the override sits beside the engine's evidence.
                    items = [*(i for i in check["evidence"] if i["captured_by"] == "agent" and i not in items), *items]
                    searches = [*(s for s in check["searches"] if s not in searches), *searches]
            proof = evidence_cell(items, searches, engine)
            if not proof:
                unproven = check["verdict"] in ("FAIL", "UNKNOWN") and not findings_cite_evidence(findings)
                proof = NO_EVIDENCE if unproven else "—"
            fix = "—"
            if finding is not None:
                fix = fix_cell(finding)
                earlier = first_with_fix.setdefault((check["id"], fix), finding["id"])
                if earlier != finding["id"]:
                    fix = f"Same as {code(earlier)}"
            rows.append(
                [
                    check_cell(check, finding),
                    verdict_cell(check, check["id"] in scored_ids),
                    found,
                    proof,
                    fix,
                    decision_cell(finding) if finding is not None else "—",
                ]
            )
    return rows


def attention_section(report: Mapping[str, Any]) -> list[str]:
    scored = _summary.scored_checks(report["checks"])
    legend = [f"- **{via}**: {words}" for via, words in DECIDED_BY.items()]
    parts: list[list[str]] = [
        ["## Checks that need attention"],
        [
            "Each row is a finding, or a check that has none. A check is listed when it is not met, was overridden, was "
            "judged by the agent, or raised a finding. Evidence is grouped by who captured it, and a quote or command "
            "output is under Evidence in full. The decision on a finding is one of these:"
        ],
        legend,
    ]
    for severity in SEVERITIES:
        mine = [c for c in scored if c["severity"] == severity]
        rows = attention_rows(report, severity)
        sentence = attention_sentence(severity, len(mine), sum(1 for c in mine if c["verdict"] != "PASS"), len(rows))
        parts.append([f"### {severity.capitalize()} checks"])
        parts.append([sentence])
        if rows:
            parts.append(table(["Check", "Verdict", "What we found", "Evidence", "Fix", "Decision"], rows))
    return blocks(*parts)


def overrides_section(report: Mapping[str, Any]) -> list[str]:
    changed = [check for check in report["checks"] if overridden(check)]
    body = (
        table(
            ["Check", "Engine's verdict", "This report's verdict", "Reason"],
            [[code(c["id"]), c["engine_verdict"], c["verdict"], text(c["override_reason"])] for c in changed],
        )
        if changed
        else ["No engine verdict was overridden."]
    )
    intro = (
        [
            "Where this report's verdict differs from the engine's, the row of the check above shows both, and the "
            "agent's counter-evidence is in its Evidence column or under Evidence in full."
        ]
        if changed
        else []
    )
    return blocks(["## Overrides of the engine's verdicts"], intro, body)


def evidence_in_full_section(report: Mapping[str, Any]) -> list[str]:
    """The quotes and command output that the tables point to, each under the check that cites it."""
    grouped = findings_of(report)
    parts: list[list[str]] = []
    for severity in SEVERITIES:
        for check in report["checks"]:
            findings = grouped.get(check["id"], [])
            if check["severity"] != severity or not needs_attention(check, findings):
                continue
            unique: list[Mapping[str, Any]] = []
            seen: set[str] = set()
            for item in [*check["evidence"], *(item for finding in findings for item in finding["evidence"])]:
                key = json.dumps(item, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    unique.append(item)
            long = [item for item in unique if item.get("quote") or item.get("output_tail")]
            if long:
                parts.append([f"### {check['id']}: {text(check['title'])}"])
                parts.append(evidence_lines(long))
    if not parts:
        return []
    return blocks(
        ["## Evidence in full"],
        ["Quotes and command output that the tables above point to, each under the check that cites it."],
        *parts,
    )
