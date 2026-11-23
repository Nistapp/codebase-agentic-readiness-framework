# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""DOC-01: docs/ exists."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.target import Target
from audit.rules.checks.doc._shared import _outcome

SPEC = declare("DOC-01", "docs/ exists", "A", Severity.DEGRADER)


# ===========================================================================
# DOC-01 — docs/ exists with markdown
# ===========================================================================


def check_doc01(*, spec, target: Target, inventory, stack, components, session) -> CheckOutcome:
    markdown = sorted(
        f.rel for f in inventory.files if f.rel.startswith("docs/") and f.rel.lower().endswith((".md", ".markdown"))
    )
    if markdown:
        return _outcome(spec, Verdict.PASS, f"{len(markdown)} markdown file(s) under docs/")

    if (target.path / "docs").is_dir():
        return _outcome(
            spec,
            Verdict.PARTIAL,
            "docs/ exists but holds no markdown file",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "read the project's documentation", "docs/ exists but contains no markdown file"
                    ),
                    evidence=[Evidence("docs/")],
                    remediation="Add the canonical documentation pages to docs/ — a project overview "
                    "and the style guide at minimum.",
                ),
            ],
        )

    return _outcome(
        spec,
        Verdict.FAIL,
        "no docs/ directory",
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement("find the project's documentation", "no docs/ directory exists in the repository"),
                remediation="Create docs/ as the canonical home for permanent knowledge, with "
                "docs/STYLE_GUIDE.md holding the authoring rules.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import GLOB, ROOT, Reads, What, _at

    return Reads(
        where=(
            *_at(GLOB, "docs/**/*.md", "docs/**/*.markdown"),
            *_at(ROOT, "docs"),
        ),
        what=What("exists"),
        binding="file",
        threshold="one or more Markdown files under docs/",
        note=("With no Markdown file, the folder docs is looked for on disk: present is PARTIAL, absent is FAIL."),
    )
