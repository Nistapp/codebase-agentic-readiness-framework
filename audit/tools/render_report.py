# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Render an audit report to Markdown. The Markdown is a pure function of the JSON report.

    render_report.py <report> --out <md>

``render`` takes a report and returns text. It reads nothing but the report, writes nothing, and never looks at a
clock, so one report always gives the same bytes, whatever order its keys come in. The readiness summary is computed
with ``_summary.py``, the code that the validator and the report builder use, and not taken from the file. Editorial
wording, such as what a verdict means, lives here and never in the JSON, so nothing in the Markdown is absent from the
JSON apart from that wording (``schema/SCHEMA.md``, "Summary").

The text of a report comes from a repository, through a model, so it is untrusted. Free text is written with
Markdown's special characters escaped, so that a statement cannot become a link, an image or a heading. A path or a
command sits in a code span and a quote in a fenced block, each with a delimiter longer than any run of backticks
inside it. Control characters, and the characters that reorder or hide text, are written out as ``{U+XXXX}``.

The command line reads a report, validates it with ``validate_report.validate_document``, and refuses one that is
not valid: the renderer reads fields that only a valid report guarantees. It writes the Markdown to ``--out`` as a
new file, never replaces one, and refuses a path inside the audited target. A draft renders too, with a banner that
says it is a draft.

Failure behaviour: a bad argument, a missing report, an ``--out`` that exists or has no folder, or one inside the
target is exit 1. A report that fails the schema or a rule, and a file that is not JSON, is exit 2 with the errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import _common
import _summary
import validate_report as vr
from _render_terms import (
    NO_EVIDENCE as NO_EVIDENCE,
    SEVERITIES as SEVERITIES,
    VERDICTS as VERDICTS,
    COMMIT_CHARS as COMMIT_CHARS,
    BR as BR,
    EVIDENCE_IN_CELL as EVIDENCE_IN_CELL,
    UNMET as UNMET,
    VERDICT_MEANINGS as VERDICT_MEANINGS,
    SEVERITY_MEANINGS as SEVERITY_MEANINGS,
    DISPOSITION_MEANINGS as DISPOSITION_MEANINGS,
    FIRST_ACTIONS as FIRST_ACTIONS,
    UNKNOWN_LISTED as UNKNOWN_LISTED,
    EFFORT_ORDER as EFFORT_ORDER,
    DECIDED_BY as DECIDED_BY,
)
from _render_text import (
    _SPECIAL as _SPECIAL,
    _BLOCK_START as _BLOCK_START,
    _BACKTICKS as _BACKTICKS,
    clean as clean,
    flat as flat,
    text as text,
    prose as prose,
    delimiter as delimiter,
    code as code,
    fenced as fenced,
    cell as cell,
    ALIGNMENTS as ALIGNMENTS,
    table as table,
    blocks as blocks,
    count as count,
    joined as joined,
    yes_no as yes_no,
    score_text as score_text,
)
from _render_evidence import (
    captured as captured,
    evidence_lines as evidence_lines,
    search_text as search_text,
    evidence_item_text as evidence_item_text,
    capped as capped,
    evidence_cell as evidence_cell,
)
from _render_facts import (
    overridden as overridden,
    findings_of as findings_of,
    findings_cite_evidence as findings_cite_evidence,
    needs_attention as needs_attention,
    engine_text as engine_text,
    agent_text as agent_text,
    framework_text as framework_text,
    open_findings as open_findings,
    first_actions as first_actions,
    check_titles as check_titles,
    named_check as named_check,
    family_heading as family_heading,
    action_row as action_row,
    blocker_findings as blocker_findings,
    blockers_phrase as blockers_phrase,
    credit_text as credit_text,
    check_cell as check_cell,
    verdict_cell as verdict_cell,
    fix_cell as fix_cell,
    decision_cell as decision_cell,
    attention_sentence as attention_sentence,
    _RENDERED_PAYLOAD_KINDS as _RENDERED_PAYLOAD_KINDS,
    _and_join as _and_join,
    _payloads_note as _payloads_note,
)

INFO = _common.ToolInfo(
    name="render_report",
    summary="Render an audit report to Markdown. The Markdown is a pure function of the JSON report.",
    synopsis=("render_report.py <report> --out <md>",),
    writes=(
        "<md>, the path given by --out: a new file, never a replacement, and never inside the audited target. "
        "The report is only read."
    ),
)


# --- Sections --------------------------------------------------------------------------------------------------------


def banners(report: Mapping[str, Any]) -> list[str]:
    context = report["run_context"]
    parts: list[list[str]] = []
    if context["eval_mode"]:
        parts.append(
            [
                "> [!WARNING]",
                "> **Evaluation run.** This report was produced to measure the audit recipe, not to guide work on the "
                f"repository. Its confirmation policy was {code(context['confirmation_policy'])}, so no person "
                "decided on its findings, and it can never be final.",
            ]
        )
    if report["status"] == "draft":
        waiting = sum(1 for finding in report["findings"] if finding["disposition"] == "pending")
        parts.append(
            [
                "> [!NOTE]",
                "> **Draft.** This report is not final and can still change. "
                f"{count(waiting, 'finding')} {'awaits' if waiting == 1 else 'await'} a decision.",
            ]
        )
    parts.append(
        [
            "> [!NOTE]",
            "> This audit reports; it does not gate. A check that could not be settled is UNKNOWN: it earns no "
            "credit and is never shown as a pass.",
        ]
    )
    return blocks(*parts)


def title_section(report: Mapping[str, Any]) -> list[str]:
    return blocks([f"# Agentic readiness audit: {text(report['provenance']['target']['label'])}"], banners(report))


def bottom_line_section(report: Mapping[str, Any], summary: Mapping[str, Any]) -> list[str]:
    """The answer first: the blockers left, the first actions, and what the scan could not settle."""
    actions = first_actions(report)
    left_open = len(open_findings(report))
    titles = check_titles(report)
    unknown = [check["id"] for check in report["checks"] if check["verdict"] == "UNKNOWN"]
    listed = "; ".join(named_check(check_id, titles) for check_id in unknown[:UNKNOWN_LISTED]) + (
        f" and {len(unknown) - UNKNOWN_LISTED} more" if len(unknown) > UNKNOWN_LISTED else ""
    )
    unattested = len(report["unattested"])
    could_not = [
        f"{count(len(unknown), 'check')} {'is' if len(unknown) == 1 else 'are'} UNKNOWN: {listed}."
        if unknown
        else "No check is UNKNOWN.",
        f"{count(unattested, 'requirement')} {'is' if unattested == 1 else 'are'} unattested: no check settles them."
        if unattested
        else "No requirement is unattested.",
    ]
    if actions:
        intro = f"**First actions** ({len(actions)} of {count(left_open, 'open finding')}):"
        listing = table(
            ["#", "Finding", "Severity", "Effort", "What it blocks", "Fix"],
            [action_row(number, finding, titles) for number, finding in enumerate(actions, start=1)],
            ["right", "left", "left", "center", "left", "left"],
        )
    else:
        intro, listing = "**First actions:** none. No finding is open.", []
    return blocks(
        ["## Bottom line"],
        [
            f"- **{blockers_phrase(summary['blockers_remaining'], blocker_findings(report))}.**",
            "- **Not settled by this scan:**",
            *(f"  - {line}" for line in could_not),
        ],
        [intro],
        listing,
    )


def terms_section() -> list[str]:
    """The words the report uses, from the same tables the sections above use."""
    rows = [[verdict, "verdict", VERDICT_MEANINGS[verdict]] for verdict in VERDICTS]
    rows += [[severity, "severity", SEVERITY_MEANINGS[severity]] for severity in SEVERITIES]
    rows += [[name, "decision on a finding", words] for name, words in DISPOSITION_MEANINGS.items()]
    return blocks(["## Terms"], table(["Term", "Kind", "Meaning"], rows))


def provenance_section(report: Mapping[str, Any]) -> list[str]:
    """What was audited, with what, and when: the first section after the bottom line."""
    provenance = report["provenance"]
    target = provenance["target"]
    engine = provenance.get("engine")
    probes = report["run_context"]["probes"]
    if target["git_sha"]:
        commit = code(target["git_sha"][:COMMIT_CHARS])
        if target["branch"]:
            commit += f" on {code(target['branch'])}"
        commit += {True: " — **dirty working tree**", False: " — clean working tree", None: ""}[target["dirty"]]
    else:
        commit = "none recorded"
    rows = [
        ["Framework", framework_text(provenance["framework"])],
        ["Target", code(target["path"])],
        ["Commit", commit],
        ["Status", report["status"] + (" (evaluation run)" if report["run_context"]["eval_mode"] else "")],
        ["Started", code(provenance["started_at"])],
        ["Finalised", code(provenance["finalised_at"]) if "finalised_at" in provenance else "—"],
        ["Catalogue", code(provenance["catalogue_version"])],
        ["Engine", engine_text(engine) if engine else "No engine report is part of this report."],
        ["Agent (self-reported)", agent_text(provenance["agent"])],
        [
            "Probes",
            f"{joined(probes['allowed'])}, timeout {probes['timeout_s']} s"
            if probes["allowed"]
            else "none: no command of the target was run",
        ],
        ["Report schema", code(report["schema_version"])],
    ]
    return blocks(["## Provenance"], table(["Field", "Value"], rows))


def summary_section(report: Mapping[str, Any], summary: Mapping[str, Any]) -> list[str]:
    scored, unknown = summary["scored_checks"], summary["unknown_scored_checks"]
    unconfirmed = summary["unconfirmed_agent_findings"]
    weights = ", ".join(f"{name} {_summary.WEIGHTS[name]}" for name in SEVERITIES)
    unattested = report["unattested"]
    headline = [
        f"- **Phase-1 score: {score_text(summary['phase1_score'])}**, over {count(scored, 'scored check')}",
        f"- **{blockers_phrase(summary['blockers_remaining'], blocker_findings(report))}**",
        f"- **Unattested:** {count(len(unattested), 'requirement')} that no check settles, listed below",
    ]
    qualifiers = [
        (
            f"{unknown} of the {count(scored, 'scored check')} {'is' if unknown == 1 else 'are'} UNKNOWN. An UNKNOWN "
            "check earns no credit, so the score understates what is true of the repository and does not certify it."
            if unknown
            else "No scored check is UNKNOWN."
        ),
        (
            f"{count(unconfirmed, 'agent finding')} still {'awaits' if unconfirmed == 1 else 'await'} a person's "
            "decision."
            if unconfirmed
            else "No agent finding is waiting for a person's decision."
        ),
    ]
    method = (
        "The score is the weighted share of the scored checks that the repository meets. "
        f"The weights are {weights}; PASS earns full credit, PARTIAL half, and FAIL and UNKNOWN none. "
        "The framework sets no pass mark, and a score says nothing about whether agents will write correct code."
    )
    listing = (
        table(
            ["Requirement", "Method", "Property", "Why"],
            [
                [
                    code(item["requirement"]),
                    item["method"],
                    code(item["property"]) if "property" in item else "—",
                    text(item["why"]),
                ]
                for item in unattested
            ],
        )
        if unattested
        else ["No unattested requirement is recorded in this report."]
    )
    return blocks(
        ["## Readiness summary"],
        headline,
        [f"{qualifiers[0]} {qualifiers[1]}"],
        [method],
        ["### Unattested requirements"],
        [
            "A person's review or the owner's declaration verifies these requirements, so no check gives them a "
            "verdict, and they are outside the score. One leaves this list only when a person records an outcome "
            "or the owner declares it."
        ],
        listing,
    )


def verdicts_section(report: Mapping[str, Any]) -> list[str]:
    """How many checks have each verdict, and how many scored checks of each severity are not met."""
    checks = report["checks"]
    scored = _summary.scored_checks(checks)
    verdict_rows = [
        [
            verdict,
            str(sum(1 for c in checks if c["verdict"] == verdict)),
            credit_text(verdict),
            VERDICT_MEANINGS[verdict],
        ]
        for verdict in VERDICTS
    ]
    verdict_rows.append(["**Total**", f"**{len(checks)}**", "", ""])
    severity_rows = []
    for severity in SEVERITIES:
        mine = [c for c in scored if c["severity"] == severity]
        severity_rows.append(
            [
                severity,
                str(_summary.WEIGHTS[severity]),
                SEVERITY_MEANINGS[severity],
                str(len(mine)),
                str(sum(1 for c in mine if c["verdict"] != "PASS")),
            ]
        )
    return blocks(
        ["## Checks by verdict and severity"],
        ["The first table counts every check in the report. The second counts the scored checks only."],
        table(["Verdict", "Checks", "Credit", "Meaning"], verdict_rows, ["left", "right", "right", "left"]),
        table(
            ["Severity", "Weight", "Meaning", "Scored checks", "Not met"],
            severity_rows,
            ["left", "right", "left", "right", "right"],
        ),
    )


def command_surface_section(report: Mapping[str, Any]) -> list[str]:
    """The seven-verb command surface, verb by verb, from CMD-01's structured payload (backlog item 13a).
    Nothing if CMD-01 is not yet recorded or carries no such payload — the appendix still names every check."""
    check = next((c for c in report["checks"] if c["id"] == "CMD-01"), None)
    data = (check or {}).get("data") or {}
    if data.get("kind") != "verb_surface":
        return []
    verbs = data.get("verbs") or []
    missing = data.get("missing") or []
    rows = [
        [
            code(entry["verb"]),
            "yes" if entry["resolved"] else "**no**",
            code(entry["runner"]) if entry.get("runner") else "—",
            code(entry["command"]) if entry.get("command") else "—",
        ]
        for entry in verbs
    ]
    return blocks(
        ["## Command surface"],
        [
            "The framework's seven verbs, resolved verb by verb on the target's runners — CMD-01's structured "
            "payload; CMD-02, AGT-05 and CI-02 read the same surface."
        ],
        [
            f"{count(data.get('resolved_count', 0), 'verb')} of {count(len(verbs), 'verb')} resolve."
            + (f" Missing: {joined(missing)}." if missing else " Every verb resolves.")
        ],
        table(["Verb", "Resolved", "Runner", "Command"], rows, ["left", "center", "left", "left"]),
    )


def credential_total_section(report: Mapping[str, Any]) -> list[str]:
    """The credential_matrix payload's total (SEC-02's structured payload, backlog item 13c). The per-file,
    per-line detail is already in the attention tables above (one finding per file); this adds only the
    total the payload computes, not a second table duplicating that detail."""
    check = next((c for c in report["checks"] if (c.get("data") or {}).get("kind") == "credential_matrix"), None)
    data = (check or {}).get("data") or {}
    if data.get("kind") != "credential_matrix":
        return []
    files = data.get("files") or []
    return blocks(
        ["## Credential-shaped lines"],
        [
            f"{count(data.get('total', 0), 'credential-shaped line')} across {count(len(files), 'file')} in "
            f"{text(data['source']) if data.get('source') else 'the repository'}. The file-by-file detail is "
            "in the attention tables above; the report never records the value itself."
        ],
    )


def secret_shapes_section(report: Mapping[str, Any]) -> list[str]:
    """Secret-shape ignore-rule coverage, merged from SEC-01's and SEC-03's structured payloads (backlog item
    13b). A shape both checks name keeps SEC-01's row, the first found in catalogue order, matching how the
    engine's own renderer merges the same payload kind. Nothing if neither check carries one yet."""
    merged: dict[str, Mapping[str, Any]] = {}
    for check in report["checks"]:
        data = check.get("data") or {}
        if data.get("kind") != "secret_shapes":
            continue
        for shape in data.get("shapes") or []:
            merged.setdefault(shape["label"], shape)
    if not merged:
        return []
    rows = [
        [
            text(shape["label"]),
            "covered" if shape["covered"] else "**missing**",
            code(shape["suggested"]) if shape.get("suggested") else "—",
        ]
        for shape in merged.values()
    ]
    return blocks(
        ["## Missing secret-shape ignore rules"],
        [
            "The secret shapes SEC-01 and SEC-03 check for, and whether the repository's ignore rules cover "
            "each one. The suggested entry is paste-ready into `.gitignore` for a shape that is missing."
        ],
        table(["Shape", "Status", "Suggested `.gitignore` entry"], rows, ["left", "center", "left"]),
    )


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


def appendix_section(report: Mapping[str, Any]) -> list[str]:
    """Every check, grouped by family, including the passes that the tables above leave out."""
    checks = report["checks"]
    scored_ids = {c["id"] for c in _summary.scored_checks(checks)}
    families: dict[str, list[list[str]]] = {}
    for check in checks:
        families.setdefault(check["id"].split("-")[0], []).append(
            [
                code(check["id"]),
                text(check["title"]),
                check["severity"],
                check["method"],
                yes_no(check["id"] in scored_ids),
                check["verdict"],
                check.get("engine_verdict", "—"),
                text(check["summary"]) or "—",
            ]
        )
    payloads_note = _payloads_note(checks)
    parts: list[list[str]] = [["## Appendix — all checks"]]
    if not checks:
        parts.append(["No check is recorded."])
    else:
        parts.append([f"All {count(len(checks), 'check')}, grouped by family. {payloads_note}"])
    for family, rows in families.items():
        parts.append([f"### {family_heading(family)}"])
        parts.append(table(["Check", "Title", "Severity", "Method", "Scored", "Verdict", "Engine", "Summary"], rows))
    return blocks(*parts)


def coverage_section(report: Mapping[str, Any]) -> list[str]:
    coverage = report["coverage"]
    skipped = coverage["scopes_skipped"]
    inventory = coverage.get("inventory")
    return blocks(
        ["## Coverage"],
        [f"**Examined:** {joined(coverage['scopes_examined'], 'nothing is recorded')}"],
        table(["Skipped", "Why"], [[code(s["scope"]), text(s["reason"])] for s in skipped])
        if skipped
        else ["No scope was skipped."],
        [
            f"**Files:** {count(inventory['files_inspected'], 'file')} inspected, {inventory['files_skipped']} skipped; "
            f"the scan {'was cut short' if inventory['truncated'] else 'was not cut short'}."
        ]
        if inventory
        else [],
    )


def stack_section(report: Mapping[str, Any]) -> list[str]:
    stack = report["stack"]
    rows = [
        ["Ecosystems", joined(stack["ecosystems"])],
        ["Package managers", joined(stack["package_managers"])],
        ["CI providers", joined(stack["ci_providers"])],
        ["Test frameworks", joined(stack["test_frameworks"])],
        ["Hook managers", joined(stack["hook_managers"])],
    ]
    components = report["components"]
    listing = (
        table(
            ["Component", "Path", "Declared", "Declared by", "Manifest", "AGENTS.md"],
            [
                [
                    text(c["name"]),
                    code(c["path"]),
                    yes_no(c["declared"]),
                    text(c["declared_by"]) if c.get("declared_by") else "—",
                    code(c["manifest"]) if c.get("manifest") else "—",
                    c.get("agents_md", "—"),
                ]
                for c in components
            ],
        )
        if components
        else ["No component is recorded."]
    )
    notes = [f"- {prose(note)}" for note in stack.get("notes", [])]
    return blocks(["## Stack and components"], table(["Stack", "Detected"], rows), notes, listing)


def run_context_section(report: Mapping[str, Any]) -> list[str]:
    context = report["run_context"]
    index = context["index"]
    profile = context.get("stack_profile")
    rows = [
        ["Evaluation mode", yes_no(context["eval_mode"])],
        ["Confirmation policy", code(context["confirmation_policy"])],
        ["Provider exposure acknowledged", "yes: the model provider receives what the agent reads from the target"],
        [
            "Code index",
            code(index["kind"])
            + (f" {code(index['name'])}" if index.get("name") else "")
            + (f" — {text(index['notes'])}" if index.get("notes") else ""),
        ],
        ["Excluded", joined(context["excluded"], "none")],
        ["Known components", joined(context["known_components"], "none")],
        [
            "Stack profile",
            f"{code(profile['id'])}, {profile['source']}, "
            f"{'confirmed' if profile['confirmed_by_user'] else 'not confirmed'} by the user"
            if profile
            else "—",
        ],
    ]
    return blocks(["## Run context"], table(["Field", "Value"], rows))


def render(report: Mapping[str, Any]) -> str:
    """The Markdown for a valid report. It reads only `report`, changes nothing, and gives one text for one report."""
    summary = _summary.compute_summary(report)
    body = blocks(
        title_section(report),
        bottom_line_section(report, summary),
        provenance_section(report),
        summary_section(report, summary),
        verdicts_section(report),
        command_surface_section(report),
        credential_total_section(report),
        secret_shapes_section(report),
        attention_section(report),
        overrides_section(report),
        evidence_in_full_section(report),
        coverage_section(report),
        stack_section(report),
        run_context_section(report),
        appendix_section(report),
        terms_section(),
        ["---", "", "Rendered from the JSON report by `render_report.py`. The JSON report is the record."],
    )
    return "\n".join(body) + "\n"


# --- The command line ---------------------------------------------------------------------------------------------


def refuse_inside_target(report: Mapping[str, Any], out: Path) -> None:
    """The tools never write inside the repository they audit. The check needs the target to be on this machine."""
    named = Path(report["provenance"]["target"]["path"])
    if named.is_dir() and _common.is_within(named.resolve(), out.parent.resolve()):
        raise _common.PathNotAllowed(f"refusing to write inside the target: {out.parent.resolve()}")


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="render_report.py", description=INFO.summary)
    parser.add_argument("report", help="the audit report, draft or final, to render")
    parser.add_argument("--out", required=True, help="the Markdown file to create; it must not exist")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    source = Path(args.report).expanduser()
    document = vr.read_report(source)
    outcome = vr.validate_document(document)
    vr.refuse_unknown_schema(outcome)
    if outcome.errors:
        total = len(outcome.errors)
        raise _common.ValidationFailed(
            f"the report is not valid, so it was not rendered: {count(total, 'error')} in the {outcome.stage} stage",
            errors=outcome.errors,
        )
    out = Path(args.out).expanduser()
    if not out.parent.is_dir():
        raise _common.UsageError(f"the folder for --out does not exist: {out.parent}")
    refuse_inside_target(document, out)
    markdown = render(document)
    try:
        written = _common.create_file(out, markdown)
    except OSError as exc:
        raise _common.UsageError(f"cannot write {out}: {exc.strerror or exc}") from None
    kept, omitted = _common.bound_items(outcome.warnings)
    data: dict[str, Any] = {
        "markdown": str(written),
        "report": str(source),
        "status": document["status"],
        "lines": len(markdown.splitlines()),
        "bytes": len(markdown.encode("utf-8")),
    }
    if omitted:
        data["warnings_omitted"] = omitted
    return _common.Result(
        data=data,
        summary=f"render_report: wrote {written.name} ({data['lines']} lines)",
        warnings=kept,
        truncated=bool(omitted),
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
