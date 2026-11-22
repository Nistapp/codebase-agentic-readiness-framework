# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-05: CONTRIBUTING present."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.hyg._shared import _finding, _named_documents, _outcome

SPEC = declare("HYG-05", "CONTRIBUTING present", "A", Severity.COSMETIC, scored=False)


# ===========================================================================
# HYG-05 — CONTRIBUTING
# ===========================================================================


def check_hyg05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("contributing",))
    if found:
        return _outcome(spec, Verdict.PASS, f"CONTRIBUTING present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no CONTRIBUTING document",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "contribute without reverse-engineering the process",
                "no CONTRIBUTING document exists",
                remediation="Add CONTRIBUTING.md covering setup, the gate, and the review flow.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import REPOSITORY_LEVEL, Reads, What, _at

    return Reads(
        where=(*_at(REPOSITORY_LEVEL, "CONTRIBUTING*"),),
        what=What("exists"),
        binding="file",
        note=(
            "The base name starts with contributing, any case, and has a doc suffix (.md, .rst, .txt, "
            ".markdown, .adoc) or none."
        ),
    )
