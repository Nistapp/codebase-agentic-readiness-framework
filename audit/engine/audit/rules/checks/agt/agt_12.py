# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-12: Communication rules stated."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import entry_instruction_file
from audit.scan import Inventory
from audit.rules.checks.agt._shared import _unknown, _MD_HEADING_RE, _MD_FENCE_RE

SPEC = declare("AGT-12", "Communication rules stated", "B", Severity.COSMETIC)


# ---------------------------------------------------------------------------
# AGT-12 — communication rules stated
# ---------------------------------------------------------------------------

#: A heading that opens the rules for writing to people: "How to write for people", "Communication",
#: "Reporting", "Talking to the user". A heading inside a fenced block is not a heading.
_COMMUNICATION_HEADING_RE = re.compile(
    r"(?i)\b(communicat\w*|writ(?:e|ing) for (?:people|humans|readers|the reader)|how to write|reporting"
    r"|talking to (?:people|humans|users?|the (?:user|owner|team))|messages to (?:people|users?|the user))\b"
)
#: A Markdown file the instruction file names, in a link target or a code span, whose name says "communication".
_COMMUNICATION_FILE_RE = re.compile(r"(?i)(?:\]\(|`)\s*(?:\./)?([\w./-]*communicat[\w.-]*\.md)(?:#[^)`]*)?\s*[)`]")
#: The three things the rules must cover, in order: who the reader is, how to report, how to ask for a decision.
_COMMUNICATION_ELEMENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "the reader",
        re.compile(
            r"(?i)\b(readers?|audience|persona|write for|writing for|new (?:engineer|contributor)s?|newcomers?)\b"
        ),
    ),
    ("how to report", re.compile(r"(?i)\b(reports?|reporting|status|summary|bottom line|what changed)\b")),
    ("how to ask for a decision", re.compile(r"(?i)\b(decisions?|decide|recommend\w*|trade-?offs?)\b")),
)


def _communication_sections(text: str) -> list[tuple[int, str, str]]:
    """Each communication section of ``text``: its heading line, its heading and its body (subsections included)."""
    lines = text.splitlines()
    headings: list[tuple[int, int, str]] = []
    in_fence = False
    for number, line in enumerate(lines, start=1):
        if _MD_FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        match = None if in_fence else _MD_HEADING_RE.match(line)
        if match:
            headings.append((number, len(match.group(1)), match.group(2)))
    sections: list[tuple[int, str, str]] = []
    for index, (number, level, title) in enumerate(headings):
        if not _COMMUNICATION_HEADING_RE.search(title):
            continue
        end = next((n for n, lvl, _ in headings[index + 1 :] if lvl <= level), len(lines) + 1)
        sections.append((number, title, "\n".join(lines[number : end - 1])))
    return sections


def _linked_rules_files(text: str, inventory: Inventory) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """The communication files the instruction file names: those in the inventory and those missing, with lines."""
    present: list[tuple[str, int]] = []
    missing: list[tuple[str, int]] = []
    seen: set[str] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        for match in _COMMUNICATION_FILE_RE.finditer(line):
            rel = match.group(1).lstrip("/")
            if rel in seen:
                continue
            seen.add(rel)
            (present if inventory.read(rel) else missing).append((rel, number))
    return present, missing


def check_agt12(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    sections = _communication_sections(text)
    present, missing_files = _linked_rules_files(text, inventory)
    evidence = [Evidence(name, line=number, note=f"section: {title}") for number, title, _ in sections]
    evidence += [Evidence(rel, note=f"rules file named at {name}:{number}") for rel, number in present]

    if not sections and not present and not missing_files:
        why = f"{name} has no section on writing for people and names no communication rules file"
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.FAIL,
            spec.status,
            summary=why,
            findings=[
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement("report to people or ask them for a decision in a form they expect", why),
                    remediation="Add a short section to the instruction file, for example 'How to write for "
                    "people': who the reader is, the bottom line first and the layout of a report, and how to "
                    "ask for a decision (the options, a recommendation and a default). Link a longer rules file "
                    "if the repository has one.",
                ),
            ],
        )

    rules = "\n".join([body for _, _, body in sections] + [inventory.read(rel) or "" for rel, _ in present])
    uncovered = [label for label, pattern in _COMMUNICATION_ELEMENTS if not pattern.search(rules)]
    where = [f"{name} § {title}" for _, title, _ in sections] + [rel for rel, _ in present]

    if not uncovered and not missing_files:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.PASS,
            spec.status,
            summary=f"communication rules ({'; '.join(where)}) name the reader, reports and decisions",
        )

    gaps: list[str] = []
    if missing_files:
        gaps.append(f"{name} names {', '.join(rel for rel, _ in missing_files)}, which does not exist")
    if uncovered:
        source = "; ".join(where) if where else "the named rules file"
        gaps.append(f"the rules ({source}) do not say {', '.join(uncovered)}")
    why = "; ".join(gaps)
    evidence += [Evidence(name, line=number, note=f"names missing {rel}") for rel, number in missing_files]
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        Verdict.PARTIAL,
        spec.status,
        summary=why,
        findings=[
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement("report to people or ask them for a decision in a form they expect", why),
                evidence=evidence,
                remediation="Complete the communication rules: name the reader (for example 'a new engineer who "
                "knows the stack but not this repository'), the layout of a status or done report, and how "
                "to ask for a decision (the options, a recommendation and a default).",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import FOLD, GLOB, ROOT, Reads, What, _at

    return Reads(
        where=(
            *_at(ROOT, "AGENTS.md", "CLAUDE.md"),
            *_at(GLOB, "**/*communicat*.md", case=FOLD),
        ),
        what=What("word-list"),
        binding="section",
        threshold="the reader, how to report and how to ask for a decision",
        note=(
            "A heading outside a fence that matches communicat*, write for people, how to write, reporting "
            "and others opens a section with its subsections; a Markdown file whose name holds communicat, "
            "named in a link or code span, is read whole. Three element word groups must appear in those "
            "bodies and files together."
        ),
    )
