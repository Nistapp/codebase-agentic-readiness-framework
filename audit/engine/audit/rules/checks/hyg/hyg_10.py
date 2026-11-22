# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-10: License present."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.hyg._shared import _finding, _named_documents, _outcome

SPEC = declare("HYG-10", "License present", "A", Severity.COSMETIC, scored=False)


# ===========================================================================
# HYG-10 — license
# ===========================================================================


def check_hyg10(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("license", "licence", "copying", "copyright", "unlicense"), root_only=True)
    if found:
        return _outcome(spec, Verdict.PASS, f"license present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no license file at the repository root",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "know the terms under which the code may be used",
                "no LICENSE (or COPYING) file exists at the repository root",
                remediation="Add a LICENSE file; choose one deliberately rather than defaulting "
                "to all rights reserved.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import GLOB, Reads, What, _at

    return Reads(
        where=(*_at(GLOB, "LICENSE*", "LICENCE*", "COPYING*", "COPYRIGHT*", "UNLICENSE*"),),
        what=What("exists"),
        binding="file",
        note="Root files only, any case, with a doc suffix or none.",
    )
