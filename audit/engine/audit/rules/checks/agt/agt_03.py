# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-03: Documentation contract named."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import entry_instruction_file
from audit.rules.checks.agt._shared import _unknown, _first_line

SPEC = declare("AGT-03", "Documentation contract named", "B", Severity.DEGRADER)


# ---------------------------------------------------------------------------
# AGT-03 — documentation contract named
# ---------------------------------------------------------------------------

_DOCS_NAME_RE = re.compile(r"(?<![\w/])docs/|\bdocs\b")
_STYLE_GUIDE_RE = re.compile(r"STYLE_GUIDE\.md")
_SCRATCH_DIR_RE = re.compile(r"\bartefacts?/|\bartifacts?/")


def check_agt03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    wanted = {
        "docs/": _first_line(text, _DOCS_NAME_RE),
        "docs/STYLE_GUIDE.md": _first_line(text, _STYLE_GUIDE_RE),
        "artefacts/": _first_line(text, _SCRATCH_DIR_RE),
    }
    missing = [label for label, line in wanted.items() if line is None]
    if not missing:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.PASS,
            spec.status,
            summary="docs/, the style guide and the scratch contract are named",
        )

    covered = {label: line for label, line in wanted.items() if line is not None}
    verdict = Verdict.PARTIAL if covered else Verdict.FAIL
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=f"does not name {', '.join(missing)}",
        findings=[
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=verdict,
                statement=statement(
                    "know where permanent and scratch documentation live", f"{name} does not name {', '.join(missing)}"
                ),
                evidence=[Evidence(name, line=line, note=label) for label, line in covered.items()],
                remediation="Name docs/ as the canonical home for permanent knowledge, "
                "docs/STYLE_GUIDE.md as the authoring rules, and artefacts/ as off-limits "
                "scratch.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at

    return Reads(
        where=(*_at(ROOT, "AGENTS.md", "CLAUDE.md"),),
        what=What(
            "word-list",
            (
                "docs/",
                "docs",
                "STYLE_GUIDE.md",
                "artefact/",
                "artefacts/",
                "artifact/",
                "artifacts/",
            ),
        ),
        binding="file",
        threshold="all three named",
        note=(
            "Three items, each on any line: docs, the style guide name and the scratch folder. CLAUDE.md is "
            "read only when the root AGENTS.md is missing or empty."
        ),
    )
