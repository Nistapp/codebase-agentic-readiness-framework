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
BR = "<br>"
EVIDENCE_IN_CELL = 8
UNMET = ("PARTIAL", "FAIL", "UNKNOWN")

# What a verdict and a severity mean, in the report's own words. The JSON carries the words PASS and BLOCKER; the
# meaning is editorial and lives here.
VERDICT_MEANINGS = {
    "PASS": "The requirement is met.",
    "PARTIAL": "Part of the requirement is met.",
    "FAIL": "The requirement is not met.",
    "UNKNOWN": "The evidence could not be gathered. It is never read as a pass.",
    "NOT_APPLICABLE": "The check does not apply to this repository.",
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


ALIGNMENTS = {"left": "---", "center": ":---:", "right": "---:"}


def table(headers: Sequence[str], rows: Sequence[Sequence[str]], aligns: Sequence[str] | None = None) -> list[str]:
    """A GFM table. A cell is made safe by `cell`, so `<br>` in a value would be the renderer's own line break."""
    marks = [ALIGNMENTS[a] for a in aligns] if aligns else ["---"] * len(headers)
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(marks) + "|"]
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


def findings_cite_evidence(findings: Sequence[Mapping[str, Any]]) -> bool:
    """Whether any finding of a check cites evidence or a search.

    The row of a check or finding that has none of its own falls back to the check's, so a row with an empty cell
    already belongs to a check with none, and what is left to ask is whether one of its findings has some.
    """
    return any(finding["evidence"] or finding["searches"] for finding in findings)


def needs_attention(check: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]) -> bool:
    """Whether a check has a row in the tables of checks that need attention.

    It does when it is not met, was overridden, was judged by the agent, or raised a finding. A passing check that a
    tool settled has only its line in the appendix.
    """
    return check["verdict"] in UNMET or overridden(check) or check["method"] == "agent" or bool(findings)


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
            tail = item.get("quote", "")
        lines.append(f"- {head} · {captured(item)}")
        lines += fenced(tail, indent="  ")
    return lines


def search_text(search: Mapping[str, Any]) -> str:
    hits = count(search["hits"], "hit") if search["hits"] else "no hits"
    return f"`{search['tool']}` for {code(search['pattern'])} in {code(search['scope'])}: {hits}"


def evidence_item_text(item: Mapping[str, Any]) -> str:
    """One piece of evidence on one line, for a table cell. A quote or command output is left to "Evidence in full"."""
    notes: list[str] = []
    if item["kind"] == "file":
        head = code(item["path"] + (f":{item['lines']}" if item.get("lines") else ""))
        if item.get("note"):
            notes.append(text(item["note"]))
        if item.get("quote"):
            notes.append("quote in Evidence in full")
    elif item["kind"] == "command":
        head = f"command {code(item['command'])}"
        if item.get("exit_code") is not None:
            notes.append(f"exit {item['exit_code']}")
        if item.get("timed_out"):
            notes.append("timed out")
        if item.get("duration_s") is not None:
            notes.append(f"{item['duration_s']:g} s")
        if item.get("redactions"):
            notes.append(count(item["redactions"], "redaction"))
        if item.get("output_tail"):
            notes.append("output in Evidence in full")
    else:
        head = f"{code(item['query'])} through {code(item['index_tool'])}"
        if item.get("result_summary"):
            notes.append(text(item["result_summary"]))
    return head + (f" ({'; '.join(notes)})" if notes else "")


def capped(lines: Sequence[str], total: int) -> list[str]:
    """The first `EVIDENCE_IN_CELL` lines, and a line that says how many more the JSON report holds."""
    shown = list(lines[:EVIDENCE_IN_CELL])
    if total > EVIDENCE_IN_CELL:
        shown.append(f"and {total - EVIDENCE_IN_CELL} more, in the JSON report")
    return shown


def evidence_cell(
    items: Sequence[Mapping[str, Any]], searches: Sequence[Mapping[str, Any]], engine: Mapping[str, Any] | None
) -> str:
    """The evidence and searches of one row, grouped by who captured them, one per line. Empty when there are none.

    A tool's name and version are named only when they are not the engine's, which the provenance already names.
    """
    expected = f"{engine['name']} {engine['version']}" if engine else None
    lines: list[str] = []
    for who in ("tool", "agent"):
        mine = [item for item in items if item["captured_by"] == who]
        if not mine:
            continue
        identity = ""
        if who == "tool":
            names = sorted({f"{item['tool']} {item['tool_version']}" for item in mine})
            if names != [expected]:
                identity = f" ({', '.join(code(name) for name in names)})"
        shown = capped([evidence_item_text(item) for item in mine], len(mine))
        shown[0] = f"**{who}**{identity} {shown[0]}"
        lines += shown
    if searches:
        shown = capped([search_text(search) for search in searches], len(searches))
        shown[0] = f"**searches** {shown[0]}"
        lines += shown
    return BR.join(lines)


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


def engine_text(engine: Mapping[str, Any]) -> str:
    parts = [f"{code(engine['name'])} {text(engine['version'])}"]
    if engine.get("ruleset_revision"):
        parts.append(f"ruleset {code(engine['ruleset_revision'])}")
    parts.append(f"ruleset hash {code(engine['ruleset_hash'])}")
    if engine.get("scanned_at"):
        parts.append(f"scanned {code(engine['scanned_at'])}")
    return ", ".join(parts)


def agent_text(agent: Mapping[str, Any]) -> str:
    if agent["harness"] == "none" and agent["model"] == "none":
        return "none: no agent took part"
    return f"{code(agent['harness'])} with {code(agent['model'])}"


def provenance_section(report: Mapping[str, Any]) -> list[str]:
    """What was audited, with what, and when: the first thing a reader sees after the title."""
    provenance = report["provenance"]
    target = provenance["target"]
    engine = provenance.get("engine")
    revision = provenance["framework_revision"]
    probes = report["run_context"]["probes"]
    if target["git_sha"]:
        commit = code(target["git_sha"][:COMMIT_CHARS])
        if target["branch"]:
            commit += f" on {code(target['branch'])}"
        commit += {True: " — **dirty working tree**", False: " — clean working tree", None: ""}[target["dirty"]]
    else:
        commit = "none recorded"
    rows = [
        ["Target", code(target["path"])],
        ["Commit", commit],
        ["Status", report["status"] + (" (evaluation run)" if report["run_context"]["eval_mode"] else "")],
        ["Started", code(provenance["started_at"])],
        ["Finalised", code(provenance["finalised_at"]) if "finalised_at" in provenance else "—"],
        [
            "Recipe",
            f"{code(provenance['recipe']['name'])} {text(provenance['recipe']['version'])}, "
            f"catalogue {code(provenance['catalogue_version'])}",
        ],
        ["Engine", engine_text(engine) if engine else "No engine report is part of this report."],
        ["Framework revision", code(revision[:COMMIT_CHARS]) if revision else "—"],
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


def blockers_phrase(blockers: Mapping[str, int]) -> str:
    states = [f"{blockers[state]} {state.upper()}" for state in _summary.BLOCKER_STATES if blockers[state]]
    return f"{count(blockers['total'], 'blocker')} remaining" + (f": {', '.join(states)}" if states else "")


def credit_text(verdict: str) -> str:
    """What a verdict earns in the score, from the same table that computes the score."""
    half = _summary.HALF_CREDITS.get(verdict)
    return "outside the score" if half is None else f"{half / 2:g}"


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


def check_cell(check: Mapping[str, Any], finding: Mapping[str, Any] | None) -> str:
    facts: list[str] = []
    if finding is not None:
        lower = f", severity {finding['severity']}" if finding["severity"] != check["severity"] else ""
        facts.append(f"finding {code(finding['id'])}{lower}")
    if check["method"] == "agent":
        facts.append("agent" + (f", confidence {check['confidence']}" if check.get("confidence") else ""))
    first = f"{code(check['id'])} {text(check['title'])}"
    return BR.join([first, " · ".join(facts)] if facts else [first])


def verdict_cell(check: Mapping[str, Any], scored: bool) -> str:
    lines = [f"**{check['verdict']}**"]
    if overridden(check):
        lines.append(f"engine: {check['engine_verdict']}")
    if not scored:
        lines.append("not scored")
    return BR.join(lines)


def fix_cell(finding: Mapping[str, Any]) -> str:
    remediation = finding["remediation"]
    details: list[str] = []
    if remediation.get("playbook"):
        details.append(f"Playbook {code(remediation['playbook'])}")
    if remediation.get("effort"):
        details.append(f"Effort {remediation['effort']}")
    if remediation.get("depends_on"):
        details.append(f"Depends on {joined(remediation['depends_on'])}")
    if remediation.get("touches"):
        details.append(f"Touches {joined(remediation['touches'])}")
    return BR.join([text(remediation["summary"]), " · ".join(details)] if details else [text(remediation["summary"])])


def decision_cell(finding: Mapping[str, Any]) -> str:
    if finding["disposition"] == "pending":
        return "**Awaiting a decision**"
    decided = f"**{finding['disposition'].capitalize()}** ({finding['confirmed_via']})"
    if finding.get("disposition_note"):
        decided += BR + f"Note: {text(finding['disposition_note'])}"
    return decided


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


def attention_sentence(severity: str, scored: int, unmet: int, listed: int) -> str:
    if scored and listed:
        return f"{unmet} of the {count(scored, f'scored {severity} check')} {'is' if unmet == 1 else 'are'} not met."
    if scored:
        return (
            f"All {count(scored, f'scored {severity} check')} {'is' if scored == 1 else 'are'} met, and none was "
            "overridden, judged by the agent or the subject of a finding."
        )
    if listed:
        return f"There is no scored {severity} check; the table lists the checks that are not scored."
    return f"There is no {severity} check in this report."


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


#: (payload kind, phrase naming the section that renders it) — used only to keep the appendix's
#: "payloads are in the JSON report" sentence accurate as more payload kinds get their own section
#: (backlog item 13); add a row here when one does.
_RENDERED_PAYLOAD_KINDS: tuple[tuple[str, str], ...] = (
    ("verb_surface", "the command surface"),
    ("secret_shapes", "the missing secret-shape ignore rules"),
)


def _and_join(phrases: Sequence[str]) -> str:
    if not phrases:
        return ""
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + f" and {phrases[-1]}"


def _payloads_note(checks: Sequence[Mapping[str, Any]]) -> str:
    kinds = {(c.get("data") or {}).get("kind") for c in checks}
    rendered = [phrase for kind, phrase in _RENDERED_PAYLOAD_KINDS if kind in kinds]
    if not rendered:
        return (
            "The engine's structured payloads (the command surface, missing secret-shape ignore rules, "
            "credential-shaped lines, and so on) are in the JSON report only, for now."
        )
    above = _and_join(rendered)
    above = above[0].upper() + above[1:]
    verb = "is" if len(rendered) == 1 else "are"
    return (
        f"{above} above {verb} rendered from the engine's structured payloads; the rest (credential-shaped "
        "lines, and so on) are in the JSON report only, for now."
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
        parts.append([f"### {family}"])
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
        provenance_section(report),
        summary_section(report, summary),
        verdicts_section(report),
        command_surface_section(report),
        secret_shapes_section(report),
        attention_section(report),
        overrides_section(report),
        evidence_in_full_section(report),
        coverage_section(report),
        stack_section(report),
        run_context_section(report),
        appendix_section(report),
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
