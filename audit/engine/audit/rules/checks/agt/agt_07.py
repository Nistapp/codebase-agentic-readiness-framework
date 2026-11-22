# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-07: Do-not-do / deny rules present."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import PROHIBITION_LINE_RE, entry_instruction_file, prohibitions_section
from audit.rules.checks.agt._shared import _unknown

SPEC = declare("AGT-07", "Do-not-do / deny rules present", "B", Severity.DEGRADER)


# ---------------------------------------------------------------------------
# AGT-07 — prohibitions / do-not-do rules
# ---------------------------------------------------------------------------

#: The four concerns the framework names for the prohibitions list. Generated build output and
#: transient scratch are treated together: both are machine-produced and must not be hand-edited.
_AGT07_CONCERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("tests", re.compile(r"(?i)\b(tests?|skip|xfail)\b")),
    (
        "generated files",
        re.compile(
            r"(?i)(generated|build output|vendored|artefacts?/|artifacts?/|dist/|__pycache__|"
            r"committed artifact)"
        ),
    ),
    (
        "the default branch",
        re.compile(r"(?i)(default branch|force-?push|rewrite history|protected branch|\bpush\b|\bmain\b)"),
    ),
    ("secrets", re.compile(r"(?i)(secret|credential|api[ -]?key|\.env|redaction|token)")),
)


def check_agt07(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    if prohibitions_section(text) is None:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.FAIL,
            spec.status,
            summary="no prohibitions section",
            findings=[
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement("rely on an explicit do-not list", f"{name} has no prohibitions section"),
                    evidence=[Evidence(name)],
                    remediation="Add an explicit prohibitions section covering tests, generated files, "
                    "the default branch and secrets.",
                )
            ],
        )

    covered: dict[str, int] = {}
    for no, line in enumerate(text.splitlines(), start=1):
        if not PROHIBITION_LINE_RE.search(line):
            continue
        for label, pattern in _AGT07_CONCERNS:
            if label not in covered and pattern.search(line):
                covered[label] = no

    missing = [label for label, _ in _AGT07_CONCERNS if label not in covered]
    if not missing:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.PASS,
            spec.status,
            summary="prohibitions cover tests, generated files, the default branch and secrets",
        )

    verdict = Verdict.PARTIAL if covered else Verdict.FAIL
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=f"not covered: {', '.join(missing)}",
        findings=[
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=verdict,
                statement=statement(
                    "rely on an explicit do-not list", f"{name} does not prohibit edits to {', '.join(missing)}"
                ),
                evidence=[Evidence(name, line=line, note=label) for label, line in covered.items()],
                remediation="Add an explicit prohibition for each of: tests, generated files, the "
                "default branch and secrets.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at

    return Reads(
        where=(*_at(ROOT, "AGENTS.md", "CLAUDE.md"),),
        what=What("word-list"),
        binding="line",
        threshold="all four concerns covered",
        note=(
            "A prohibitions section must exist (a heading word, or three prohibition lines under a heading). "
            "Then any line of the whole file with a prohibition word and a concern word on that line: tests, "
            "generated files, the default branch, secrets."
        ),
    )
