# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-04: Definition of done stated."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import entry_instruction_file
from audit.rules.checks.agt._shared import _unknown

SPEC = declare("AGT-04", "Definition of done stated", "B", Severity.DEGRADER)


# ---------------------------------------------------------------------------
# AGT-04 — definition of done stated
# ---------------------------------------------------------------------------

_CHANGE_SET_RE = re.compile(r"(?i)\bsame changeset\b|\bsame change set\b")
_DOD_TRIGGER_RE = re.compile(
    r"(?i)\b(public interface|observable behaviou?r|architecture|\badr\b|documentation|docs)\b"
)


def check_agt04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    lines = text.splitlines()
    change_line: int | None = None
    tied_line: int | None = None
    for no, line in enumerate(lines, start=1):
        if not _CHANGE_SET_RE.search(line):
            continue
        change_line = change_line or no
        window = "\n".join(lines[max(0, no - 3) : no + 2])
        if _DOD_TRIGGER_RE.search(window):
            tied_line = no
            break

    if tied_line:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.PASS,
            spec.status,
            summary="definition of done ties a doc trigger to the same change set",
        )

    if change_line:
        why = (
            "the same-change-set rule is stated but names no documentation trigger (public "
            "interface, observable behaviour, architecture or an ADR)"
        )
    else:
        why = "no definition-of-done sentence ties a documentation trigger to the same change set"
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
                statement=statement("keep code and its documentation in step", why),
                evidence=[Evidence(name, line=change_line)] if change_line else [],
                remediation="State that a change altering a public interface, observable behaviour, "
                "architecture, a check's semantics or an ADR updates the affected docs and "
                "the ADR index in the same change set.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at

    return Reads(
        where=(*_at(ROOT, "AGENTS.md", "CLAUDE.md"),),
        what=What(
            "phrase",
            (
                "same changeset",
                "same change set",
            ),
        ),
        binding="window",
        window=5,
        note=(
            "A trigger word (public interface, observable behaviour, architecture, ADR, documentation, docs) "
            "must stand within the two lines before or after the phrase: a five-line window."
        ),
    )
