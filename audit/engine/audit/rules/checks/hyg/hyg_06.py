# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-06: SECURITY present."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.hyg._shared import _finding, _named_documents, _outcome

SPEC = declare("HYG-06", "SECURITY present", "A", Severity.COSMETIC, scored=False)


# ===========================================================================
# HYG-06 — SECURITY
# ===========================================================================


def check_hyg06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("security",))
    if found:
        return _outcome(spec, Verdict.PASS, f"SECURITY present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no SECURITY document",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "report a vulnerability responsibly",
                "no SECURITY document exists at the root, under .github/, .gitlab/ or docs/",
                remediation="Add SECURITY.md with a private disclosure channel and a response expectation.",
            ),
        ],
    )
