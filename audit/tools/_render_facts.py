# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Facts about checks, findings and one report's headline numbers, and the table cells built from them.

Private to ``render_report.py``. Every function is pure.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import _summary
import validate_report as vr
from _render_terms import BR, COMMIT_CHARS, EFFORT_ORDER, FIRST_ACTIONS, SEVERITIES, UNMET
from _render_text import code, count, joined, text


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


def framework_text(framework: Mapping[str, Any]) -> str:
    """The release, then how it was installed: `v0.3.2, checkout `fcd5c7fcbff1``, `v0.3.2, installed as a bundle`."""
    release = code(f"v{framework['release']}")
    if framework["install"] == "checkout":
        revision = framework["revision"]
        return (
            f"{release}, checkout {code(revision[:COMMIT_CHARS])}" if revision else f"{release}, checkout (no revision)"
        )
    if framework["install"] == "bundle":
        return f"{release}, installed as a bundle"
    return f"{release}, a copy with no git history"


def open_findings(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The findings still to act on: every one but those a person rejected or deferred."""
    return [finding for finding in report["findings"] if finding["disposition"] not in ("rejected", "deferred")]


def first_actions(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The open findings in the order to work them, first `FIRST_ACTIONS` only.

    Severity first. Then a finding whose `depends_on` findings are all closed comes before one that waits on an open
    finding. Then the smaller `effort` (S, M, L, then none), then the check ID and the finding ID, so the order is fixed.
    """
    findings = open_findings(report)
    still_open = {finding["id"] for finding in findings}

    def rank(finding: Mapping[str, Any]) -> tuple[int, int, int, str, str]:
        remediation = finding["remediation"]
        waits = any(dependency in still_open for dependency in remediation.get("depends_on") or [])
        effort = EFFORT_ORDER.get(remediation.get("effort", ""), len(EFFORT_ORDER))
        return (SEVERITIES.index(finding["severity"]), int(waits), effort, finding["check"], finding["id"])

    return sorted(findings, key=rank)[:FIRST_ACTIONS]


def check_titles(report: Mapping[str, Any]) -> dict[str, str]:
    """Each check's ID mapped to its title, so no check ID is printed without its name."""
    return {check["id"]: check["title"] for check in report["checks"]}


def named_check(check_id: str, titles: Mapping[str, str]) -> str:
    """The check ID in a code span and its title beside it; the ID alone when the report has no such check."""
    title = titles.get(check_id)
    return f"{code(check_id)} {text(title)}" if title else code(check_id)


def family_heading(family: str) -> str:
    """The family's full name from the catalogue with its code, or the code alone for a family it does not name."""
    names = {entry["id"]: entry["name"] for entry in vr.load_catalogue().get("families", [])}
    name = names.get(family)
    return f"{text(name)} ({code(family)})" if name else code(family)


def action_row(number: int, finding: Mapping[str, Any], titles: Mapping[str, str]) -> list[str]:
    waiting = " **Awaits a decision.**" if finding["disposition"] == "pending" else ""
    return [
        str(number),
        f"{finding['id']}: {named_check(finding['check'], titles)}",
        finding["severity"],
        finding["remediation"].get("effort", "—"),
        text(finding["statement"]),
        text(finding["remediation"]["summary"]) + waiting,
    ]


def blocker_findings(report: Mapping[str, Any]) -> int:
    """The findings of BLOCKER severity, by their own severity, that a person has not rejected as false positives.

    A deferred finding is still real, so it counts. A finding may carry a lower severity than its check, so this
    number can differ from the blockers remaining, which counts checks (spec/readiness-summary.md).
    """
    return sum(
        1 for finding in report["findings"] if finding["severity"] == "BLOCKER" and finding["disposition"] != "rejected"
    )


def blockers_phrase(blockers: Mapping[str, int], findings: int | None = None) -> str:
    """The blockers remaining, by state. When the BLOCKER findings number differently, the phrase names both counts."""
    states = [f"{blockers[state]} {state.upper()}" for state in _summary.BLOCKER_STATES if blockers[state]]
    by_state = f": {', '.join(states)}" if states else ""
    if findings is None or findings == blockers["total"]:
        return f"{count(blockers['total'], 'blocker')} remaining{by_state}"
    return f"{count(blockers['total'], 'BLOCKER check')} unmet{by_state} ({count(findings, 'BLOCKER finding')})"


def credit_text(verdict: str) -> str:
    """What a verdict earns in the score, from the same table that computes the score."""
    half = _summary.HALF_CREDITS.get(verdict)
    return "outside the score" if half is None else f"{half / 2:g}"


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


#: (payload kind, phrase naming the section that renders it) — used only to keep the appendix's
#: "payloads are in the JSON report" sentence accurate as more payload kinds get their own section
#: (backlog item 13); add a row here when one does.
_RENDERED_PAYLOAD_KINDS: tuple[tuple[str, str], ...] = (
    ("verb_surface", "the command surface"),
    ("credential_matrix", "the credential-shaped-lines total"),
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
            "The engine's structured payloads (the command surface, the credential-shaped-lines total, "
            "missing secret-shape ignore rules, and so on) are in the JSON report only, for now."
        )
    above = _and_join(rendered)
    above = above[0].upper() + above[1:]
    verb = "is" if len(rendered) == 1 else "are"
    return (
        f"{above} above {verb} rendered from the engine's structured payloads; other payloads (env-key "
        "inventories, harness-reach matrices, and so on) are in the JSON report only, for now."
    )
