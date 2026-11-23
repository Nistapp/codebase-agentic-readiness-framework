# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""DOC-02: docs/STYLE_GUIDE.md exists."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.checks.doc._shared import _has_exact, _outcome

SPEC = declare("DOC-02", "docs/STYLE_GUIDE.md exists", "A", Severity.DEGRADER)


STYLE_GUIDE = "docs/STYLE_GUIDE.md"


def _instruction_text(inventory: Inventory) -> tuple[str, str]:
    """The entry instruction file and its text: canonical first, then the CLAUDE.md fallback."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = inventory.read(name)
        if text:
            return name, text
    return "", ""


# ===========================================================================
# DOC-02 — docs/STYLE_GUIDE.md exists and is named
# ===========================================================================


def check_doc02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if not _has_exact(inventory, STYLE_GUIDE):
        return _outcome(
            spec,
            Verdict.FAIL,
            f"{STYLE_GUIDE} is not present",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "find the canonical authoring rules for documentation", f"{STYLE_GUIDE} does not exist"
                    ),
                    remediation="Create docs/STYLE_GUIDE.md and name it from the instruction file so "
                    "writers have one set of authoring rules.",
                ),
            ],
        )

    name, text = _instruction_text(inventory)
    if name and re.search(r"STYLE_GUIDE\.md", text):
        return _outcome(spec, Verdict.PASS, f"{STYLE_GUIDE} present and named in {name}")

    if name:
        why = f"{STYLE_GUIDE} exists but {name} does not name it"
    else:
        why = f"{STYLE_GUIDE} exists but no instruction file names it"
    return _outcome(
        spec,
        Verdict.PARTIAL,
        why,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement("know which authoring rules govern documentation", why),
                evidence=[Evidence(STYLE_GUIDE)],
                remediation=f"Name {STYLE_GUIDE} as canonical from the instruction file (see AGT-03).",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at

    return Reads(
        where=(*_at(ROOT, "docs/STYLE_GUIDE.md", "AGENTS.md", "CLAUDE.md"),),
        what=What("exists"),
        binding="file",
        threshold="present and named",
        note=(
            "The exact path docs/STYLE_GUIDE.md, never a suffix match. The entry file (the DOC-02 module's own reader) "
            "must hold STYLE_GUIDE.md on any line, else PARTIAL."
        ),
    )
