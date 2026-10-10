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

import re
import sys
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

import _common
import _summary
import validate_report as vr

INFO = _common.ToolInfo(
    name="render_report",
    summary="Render an audit report to Markdown. The Markdown is a pure function of the JSON report.",
    synopsis=("render_report.py <report> --out <md>",),
    writes=(
        "<md>, the path given by --out: a new file, never a replacement, and never inside the audited target. "
        "The report is only read."
    ),
)

NO_EVIDENCE = "We did not find any evidence."
SEVERITIES = ("BLOCKER", "DEGRADER", "COSMETIC")
VERDICTS = ("PASS", "PARTIAL", "FAIL", "UNKNOWN", "NOT_APPLICABLE")
COMMIT_CHARS = 12

# What a verdict and a severity mean, in the report's own words. The JSON carries the words PASS and BLOCKER; the
# meaning is editorial and lives here.
VERDICT_MEANINGS = {
    "PASS": "The requirement is met. Full credit.",
    "PARTIAL": "Part of the requirement is met. Half credit.",
    "FAIL": "The requirement is not met. No credit.",
    "UNKNOWN": "The evidence could not be gathered. No credit, and never read as a pass.",
    "NOT_APPLICABLE": "The check does not apply to this repository. It is outside the score.",
}
SEVERITY_MEANINGS = {
    "BLOCKER": "Agent work is impossible, unsafe or unverifiable. Fix before onboarding agents.",
    "DEGRADER": "Agent work is possible but unreliable or wasteful.",
    "COSMETIC": "Hygiene. Fix when convenient.",
}
DECIDED_BY = {
    "interactive": "Decided by the person, on this finding alone.",
    "batch": "Decided by the person, as one of a group of findings that are not blockers.",
    "policy": "Set by the confirmation policy, not by a person.",
}


# --- Text: untrusted input becomes safe Markdown -----------------------------------------------------------------

# Characters that always mean something in the middle of a line, and an underscore that is not between two letters or
# digits (inside a word it is plain text, but `__tests__` would be bold).
_SPECIAL = re.compile(r"[\\`*\[\]<|]|(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])")
_BLOCK_START = re.compile(r"^(?:([#>+=~-])|(\d+)([.)]))")
_BACKTICKS = re.compile(r"`+")


def clean(value: str) -> str:
    """`value` with line ends as `\\n` and each control or format character written out as `{U+XXXX}`.

    Newline and tab stay. A line or paragraph separator becomes a newline. The format characters include the ones that
    reorder or hide text (right-to-left override, zero-width space), which can make a path read as another path.
    """
    out: list[str] = []
    for char in value.replace("\r\n", "\n").replace("\r", "\n"):
        category = unicodedata.category(char)
        if char in ("\n", "\t"):
            out.append(char)
        elif category in ("Zl", "Zp"):
            out.append("\n")
        elif category in ("Cc", "Cf"):
            out.append(f"{{U+{ord(char):04X}}}")
        else:
            out.append(char)
    return "".join(out)


def flat(value: str) -> str:
    """`clean` text on one line, with each run of white space as one space."""
    return " ".join(clean(value).split())


def text(value: str) -> str:
    """Prose from the report, on one line, with every Markdown special character escaped."""
    return _SPECIAL.sub(lambda found: "\\" + found.group(0), flat(value))


def prose(value: str) -> str:
    """`text` for a paragraph that starts with the value: a first character that Markdown would read as a heading, a
    quote, a list item or a rule is escaped too."""
    escaped = text(value)
    return _BLOCK_START.sub(
        lambda found: f"\\{found.group(1)}" if found.group(1) else f"{found.group(2)}\\{found.group(3)}", escaped
    )


def delimiter(content: str, *, least: int = 1) -> str:
    """A run of backticks longer than any run in `content`, so that nothing inside can close the span or the fence."""
    longest = max((len(run) for run in _BACKTICKS.findall(content)), default=0)
    return "`" * max(least, longest + 1)


def code(value: str) -> str:
    """A code span for a path, a command or a name. An empty value is shown as a dash."""
    content = flat(value)
    if not content:
        return "—"
    mark = delimiter(content)
    pad = " " if content.startswith("`") or content.endswith("`") else ""
    return f"{mark}{pad}{content}{pad}{mark}"


def fenced(value: str, indent: str = "") -> list[str]:
    """A fenced block for a quote or an output tail, indented to sit inside a list item. Nothing if it is blank."""
    body = clean(value).rstrip("\n")
    if not body.strip():
        return []
    mark = delimiter(body, least=3)
    lines = [f"{indent}{mark}text"]
    lines += [f"{indent}{line}" if line else "" for line in body.split("\n")]
    lines.append(f"{indent}{mark}")
    return lines


def cell(markup: str) -> str:
    """A table cell: any `|` that is not already escaped is escaped, so that a value cannot add a column."""
    out: list[str] = []
    index = 0
    while index < len(markup):
        char = markup[index]
        if char == "\\":
            out.append(markup[index : index + 2])
            index += 2
            continue
        out.append("\\|" if char == "|" else char)
        index += 1
    return "".join(out)


def table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(item) for item in row) + " |" for row in rows]
    return lines


def blocks(*parts: Sequence[str]) -> list[str]:
    """The non-empty blocks of lines with one blank line between each pair."""
    lines: list[str] = []
    for part in parts:
        if part:
            if lines:
                lines.append("")
            lines.extend(part)
    return lines


def count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def joined(values: Sequence[str], empty: str = "—") -> str:
    return ", ".join(code(value) for value in values) if values else empty


def yes_no(flag: bool) -> str:
    return "yes" if flag else "no"


def score_text(score: float) -> str:
    """The score to two decimal places, half up. The report stores it to four places and the spec shows it to two."""
    return str(Decimal(repr(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# --- Facts about checks and findings ---------------------------------------------------------------------------------


def overridden(check: Mapping[str, Any]) -> bool:
    engine_verdict = check.get("engine_verdict")
    return engine_verdict is not None and engine_verdict != check["verdict"]


def findings_of(report: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for finding in report["findings"]:
        grouped.setdefault(finding["check"], []).append(finding)
    return grouped


def shows_evidence(check: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]) -> bool:
    """Whether the report cites any evidence or any search for a check, on the check or on one of its findings."""
    if check["evidence"] or check["searches"]:
        return True
    return any(finding["evidence"] or finding["searches"] for finding in findings)


def needs_detail(check: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]) -> bool:
    """Whether a check gets a block of its own. A passing check that a tool settled has only its row in the table."""
    unmet = check["verdict"] in ("PARTIAL", "FAIL", "UNKNOWN")
    return unmet or overridden(check) or check["method"] == "agent" or bool(findings)


# --- Evidence ---------------------------------------------------------------------------------------------------------


def captured(item: Mapping[str, Any]) -> str:
    if item["captured_by"] == "tool":
        return f"captured by tool {code(item['tool'])} {text(item['tool_version'])}"
    return "captured by agent"


def evidence_lines(items: Sequence[Mapping[str, Any]]) -> list[str]:
    """One list item for each piece of evidence, with its quote or output in a fenced block under it."""
    lines: list[str] = []
    for item in items:
        kind = item["kind"]
        extra: list[str] = []
        if kind == "file":
            where = item["path"] + (f":{item['lines']}" if item.get("lines") else "")
            head = code(where)
            if item.get("note"):
                head += f" — {text(item['note'])}"
            tail = item.get("quote", "")
        elif kind == "command":
            head = f"Command {code(item['command'])}"
            if item.get("exit_code") is not None:
                extra.append(f"exit {item['exit_code']}")
            if item.get("timed_out"):
                extra.append("timed out")
            if item.get("duration_s") is not None:
                extra.append(f"{item['duration_s']:g} s")
            if item.get("redactions"):
                extra.append(count(item["redactions"], "redaction"))
            if extra:
                head += f" ({', '.join(extra)})"
            tail = item.get("output_tail", "")
        else:
            head = f"Index query {code(item['query'])} through {code(item['index_tool'])}"
            if item.get("result_summary"):
                head += f": {text(item['result_summary'])}"
            tail = ""
        lines.append(f"- {head} · {captured(item)}")
        lines += fenced(tail, indent="  ")
    return lines


def search_lines(searches: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        f"- `{search['tool']}` search for {code(search['pattern'])} in {code(search['scope'])}: "
        f"{count(search['hits'], 'hit') if search['hits'] else 'no hits'}"
        for search in searches
    ]


# --- Sections --------------------------------------------------------------------------------------------------------


def target_sentence(report: Mapping[str, Any]) -> str:
    target = report["provenance"]["target"]
    commit = f"at commit {code(target['git_sha'][:COMMIT_CHARS])}" if target["git_sha"] else "with no commit recorded"
    branch = f" on branch {code(target['branch'])}" if target["branch"] else ""
    tree = {True: " (uncommitted changes)", False: " (clean working tree)", None: ""}[target["dirty"]]
    return f"Repository {code(target['label'])} {commit}{branch}{tree}."


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
    return blocks(*parts)


def title_section(report: Mapping[str, Any]) -> list[str]:
    provenance = report["provenance"]
    when = provenance.get("finalised_at") or provenance["started_at"]
    return blocks(
        [f"# Agentic readiness audit: {text(provenance['target']['label'])}"],
        [f"{target_sentence(report)} {'Finalised' if 'finalised_at' in provenance else 'Started'} {code(when)}."],
        banners(report),
    )


def blockers_phrase(blockers: Mapping[str, int]) -> str:
    states = [f"{blockers[state]} {state.upper()}" for state in _summary.BLOCKER_STATES if blockers[state]]
    return f"{count(blockers['total'], 'blocker')} remaining" + (f": {', '.join(states)}" if states else "")


def summary_section(report: Mapping[str, Any], summary: Mapping[str, Any]) -> list[str]:
    scored, unknown = summary["scored_checks"], summary["unknown_scored_checks"]
    unconfirmed = summary["unconfirmed_agent_findings"]
    weights = ", ".join(f"{name} {_summary.WEIGHTS[name]}" for name in SEVERITIES)
    unattested = report["unattested"]
    headline = [
        f"- **Phase-1 score: {score_text(summary['phase1_score'])}**, over {count(scored, 'scored check')}",
        f"- **{blockers_phrase(summary['blockers_remaining'])}**",
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


def blockers_section(report: Mapping[str, Any]) -> list[str]:
    unmet = _summary.open_blockers(report["checks"])
    body = (
        table(
            ["Check", "Title", "Verdict", "Summary"],
            [[code(c["id"]), text(c["title"]), c["verdict"], text(c["summary"]) or "—"] for c in unmet],
        )
        if unmet
        else ["No scored BLOCKER check is open."]
    )
    return blocks(["## Blockers remaining"], body)


def overrides_section(report: Mapping[str, Any]) -> list[str]:
    changed = [check for check in report["checks"] if overridden(check)]
    body = (
        table(
            ["Check", "Engine's verdict", "This report's verdict", "Reason"],
            [
                [
                    code(c["id"]),
                    c["engine_verdict"],
                    c["verdict"],
                    text(c["override_reason"]),
                ]
                for c in changed
            ],
        )
        if changed
        else ["No engine verdict was overridden."]
    )
    intro = (
        [
            "Where this report's verdict differs from the engine's, the agent's counter-evidence is under the check, "
            "in the details below."
        ]
        if changed
        else []
    )
    return blocks(["## Overrides of the engine's verdicts"], intro, body)


def checks_section(report: Mapping[str, Any]) -> list[str]:
    checks = report["checks"]
    scored_ids = {c["id"] for c in _summary.scored_checks(checks)}
    tally = [f"{sum(1 for c in checks if c['verdict'] == v)} {v}" for v in VERDICTS]
    tally = [entry for entry in tally if not entry.startswith("0 ")]
    rows = [
        [
            code(c["id"]),
            text(c["title"]),
            c["severity"],
            c["method"],
            yes_no(c["id"] in scored_ids),
            c["verdict"],
            c.get("engine_verdict", "—"),
            text(c["summary"]) or "—",
        ]
        for c in checks
    ]
    legend = [f"- **{name}**: {VERDICT_MEANINGS[name]}" for name in VERDICTS] + [
        f"- **{name}**: {SEVERITY_MEANINGS[name]}" for name in SEVERITIES
    ]
    return blocks(
        ["## Checks"],
        [f"{count(len(checks), 'check')}: {', '.join(tally)}." if checks else "No check is recorded."],
        legend,
        table(["Check", "Title", "Severity", "Method", "Scored", "Verdict", "Engine", "Summary"], rows),
    )


def finding_lines(finding: Mapping[str, Any], check: Mapping[str, Any]) -> list[str]:
    """One finding: its statement, the fix, the decision on it, and its evidence."""
    remediation = finding["remediation"]
    head = f"**{finding['id']}** · {finding['severity']} · key {code(finding['key'])}"
    if finding["severity"] != check["severity"]:
        head += f" · on a {check['severity']} check"
    details: list[str] = []
    if remediation.get("playbook"):
        details.append(f"Playbook {code(remediation['playbook'])}")
    if remediation.get("effort"):
        details.append(f"Effort {remediation['effort']}")
    if remediation.get("depends_on"):
        details.append(f"Depends on {joined(remediation['depends_on'])}")
    if remediation.get("touches"):
        details.append(f"Touches {joined(remediation['touches'])}")
    if finding["disposition"] == "pending":
        decision = "**Awaiting a decision.**"
    else:
        decision = f"**{finding['disposition'].capitalize()}.** {DECIDED_BY[finding['confirmed_via']]}"
        if finding.get("disposition_note"):
            decision += f" Note: {text(finding['disposition_note'])}"
    proof: list[str] = []
    if finding["evidence"]:
        if finding["evidence"] == check["evidence"]:
            proof = ["Evidence: the same as under the check."]
        else:
            proof = blocks([f"Evidence for {finding['id']}:"], evidence_lines(finding["evidence"]))
    looked: list[str] = []
    if finding["searches"]:
        if finding["searches"] == check["searches"]:
            looked = ["Searches: the same as under the check."]
        else:
            looked = blocks([f"Searches for {finding['id']}:"], search_lines(finding["searches"]))
    return blocks(
        [head],
        [prose(finding["statement"])],
        [f"**Fix.** {text(remediation['summary'])}"],
        [" · ".join(details)] if details else [],
        [decision],
        proof,
        looked,
    )


def check_lines(check: Mapping[str, Any], findings: Sequence[Mapping[str, Any]], scored: bool) -> list[str]:
    """One check that needs detail: its verdict, any override, its evidence and searches, and its findings."""
    facts = [
        f"**{check['verdict']}**",
        check["severity"],
        check["method"],
        "scored" if scored else "not scored",
    ]
    if check.get("confidence"):
        facts.append(f"confidence {check['confidence']}")
    override: list[str] = []
    if overridden(check):
        override = [
            f"**Overridden.** The engine's verdict was **{check['engine_verdict']}**. This report says "
            f"**{check['verdict']}**. Reason: {text(check['override_reason'])}"
        ]
    if check["evidence"]:
        proof = blocks(["**Evidence**"], evidence_lines(check["evidence"]))
    elif check["verdict"] in ("FAIL", "UNKNOWN") and not shows_evidence(check, findings):
        proof = [f"**Evidence.** {NO_EVIDENCE}"]
    else:
        proof = []
    looked = blocks(["**Searches**"], search_lines(check["searches"])) if check["searches"] else []
    payload: list[str] = []
    if check.get("data"):
        of_kind = f", of kind {code(check['data']['kind'])}," if check["data"].get("kind") else ""
        payload = [f"The engine's payload for this check{of_kind} is in the JSON report."]
    return blocks(
        [f"#### {check['id']}: {text(check['title'])}"],
        [" · ".join(facts)],
        [prose(check["summary"])] if check["summary"] else [],
        override,
        proof,
        looked,
        payload,
        *(finding_lines(finding, check) for finding in findings),
    )


def details_section(report: Mapping[str, Any]) -> list[str]:
    grouped = findings_of(report)
    scored_ids = {c["id"] for c in _summary.scored_checks(report["checks"])}
    shown = [c for c in report["checks"] if needs_detail(c, grouped.get(c["id"], []))]
    parts: list[list[str]] = [["## Check details"]]
    if not shown:
        parts.append(["No check needs detail."])
    else:
        parts.append(
            [
                "Each check below is one that is not met, was overridden, was judged by the agent, or raised a finding, "
                "in order of severity. A check that passed and was settled by a tool has only its row in the table "
                "above; its evidence is in the JSON report."
            ]
        )
    for severity in SEVERITIES:
        group = [c for c in shown if c["severity"] == severity]
        if group:
            parts.append([f"### {severity} checks"])
            parts.extend(check_lines(c, grouped.get(c["id"], []), c["id"] in scored_ids) for c in group)
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
                    c["agents_md"],
                ]
                for c in components
            ],
        )
        if components
        else ["No component is recorded."]
    )
    notes = [f"- {prose(note)}" for note in stack.get("notes", [])]
    return blocks(["## Stack and components"], table(["Stack", "Detected"], rows), notes, listing)


def engine_text(engine: Mapping[str, Any]) -> str:
    parts = [f"{code(engine['name'])} {text(engine['version'])}"]
    if engine.get("ruleset_revision"):
        parts.append(f"ruleset {code(engine['ruleset_revision'])}")
    parts.append(f"ruleset hash {code(engine['ruleset_hash'])}")
    if engine.get("scanned_at"):
        parts.append(f"scanned {code(engine['scanned_at'])}")
    return ", ".join(parts)


def provenance_section(report: Mapping[str, Any]) -> list[str]:
    provenance = report["provenance"]
    target = provenance["target"]
    engine = provenance.get("engine")
    revision = provenance["framework_revision"]
    rows = [
        ["Report status", report["status"]],
        ["Schema version", code(report["schema_version"])],
        ["Repository label", code(target["label"])],
        ["Path", code(target["path"])],
        ["Commit", code(target["git_sha"]) if target["git_sha"] else "none recorded"],
        ["Branch", code(target["branch"]) if target["branch"] else "—"],
        ["Started", code(provenance["started_at"])],
        ["Finalised", code(provenance["finalised_at"]) if "finalised_at" in provenance else "—"],
        ["Recipe", f"{code(provenance['recipe']['name'])} {text(provenance['recipe']['version'])}"],
        ["Catalogue version", code(provenance["catalogue_version"])],
        ["Framework revision", code(revision[:COMMIT_CHARS]) if revision else "—"],
        ["Engine", engine_text(engine) if engine else "No engine report is part of this report."],
        [
            "Agent (self-reported)",
            f"{code(provenance['agent']['harness'])} with {code(provenance['agent']['model'])}",
        ],
    ]
    return blocks(["## Provenance"], table(["Field", "Value"], rows))


def run_context_section(report: Mapping[str, Any]) -> list[str]:
    context = report["run_context"]
    index = context["index"]
    probes = context["probes"]
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
        [
            "Probes",
            f"{joined(probes['allowed'])}, timeout {probes['timeout_s']} s"
            if probes["allowed"]
            else "none: no command of the target was run",
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
        summary_section(report, summary),
        blockers_section(report),
        overrides_section(report),
        checks_section(report),
        details_section(report),
        coverage_section(report),
        stack_section(report),
        provenance_section(report),
        run_context_section(report),
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
