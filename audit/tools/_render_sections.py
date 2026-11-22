# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The sections of the rendered report, from the title to the appendix, except the tables of checks that need attention.

Private to ``render_report.py``. Every function reads a report and returns lines; none writes.
"""

from __future__ import annotations

from typing import Any, Mapping

import _summary
from _render_facts import (
    _payloads_note,
    action_row,
    agent_text,
    blocker_findings,
    blockers_phrase,
    check_titles,
    credit_text,
    engine_text,
    family_heading,
    first_actions,
    framework_text,
    named_check,
    open_findings,
)
from _render_terms import (
    COMMIT_CHARS,
    DISPOSITION_MEANINGS,
    SEVERITIES,
    SEVERITY_MEANINGS,
    UNKNOWN_LISTED,
    VERDICTS,
    VERDICT_MEANINGS,
)
from _render_text import blocks, code, count, joined, prose, score_text, table, text, yes_no


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
