# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-02: CODEOWNERS present."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.hyg._shared import _finding, _outcome, _present

SPEC = declare("HYG-02", "CODEOWNERS present", "A", Severity.COSMETIC, scored=False)


# ===========================================================================
# HYG-02 — CODEOWNERS
# ===========================================================================


def check_hyg02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _present(inventory, "CODEOWNERS")
    if found:
        return _outcome(spec, Verdict.PASS, f"CODEOWNERS present at {', '.join(found[:3])}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no CODEOWNERS file",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "know who owns a path before changing it",
                "no CODEOWNERS file exists at the root, under .github/, .gitlab/ or docs/",
                remediation="Add .github/CODEOWNERS mapping paths to owners so review routing is machine-readable.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import REPOSITORY_LEVEL, Reads, What, _at

    return Reads(
        where=(*_at(REPOSITORY_LEVEL, "CODEOWNERS"),),
        what=What("exists"),
        binding="file",
    )
