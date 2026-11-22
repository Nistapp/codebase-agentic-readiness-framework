# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-04: Issue templates present."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.hyg._shared import _finding, _outcome

SPEC = declare("HYG-04", "Issue templates present", "A", Severity.COSMETIC, scored=False)


# ===========================================================================
# HYG-04 — issue templates
# ===========================================================================


def check_hyg04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = sorted(
        f.rel
        for f in inventory.files
        if f.rel.startswith(".github/ISSUE_TEMPLATE/") or f.rel == ".github/ISSUE_TEMPLATE.md"
    )
    if found:
        return _outcome(spec, Verdict.PASS, f"{len(found)} issue template(s) present")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no issue templates",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "report a bug or request in a structured way",
                "no .github/ISSUE_TEMPLATE entry exists",
                remediation="Add at least one file under .github/ISSUE_TEMPLATE/ (a bug report "
                "and a feature request are a good start).",
            ),
        ],
    )
