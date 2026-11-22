# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""BASE-02: Current violation counts measured."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.base._shared import (
    _baseline_artifacts,
    _budget_evidence,
    _counting_tools,
    _finding,
    _outcome,
    _recognised,
    _unknown,
)

SPEC = declare("BASE-02", "Current violation counts measured", "B", Severity.DEGRADER)


# ===========================================================================
# BASE-02 — current violation counts measured
# ===========================================================================

_METHOD = "static configuration scan; the target's own tools are never run"


def check_base02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    budgets = _budget_evidence(inventory, stack)
    if budgets:
        return _outcome(spec, Verdict.PASS, f"violation count configured: {', '.join(budgets)}; method: {_METHOD}")

    surface = sorted(set(_counting_tools(inventory, stack)) | set(_baseline_artifacts(inventory)))
    if surface:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"counting surface present but no committed count/budget: {', '.join(surface[:6])}; method: {_METHOD}",
            [
                _finding(
                    spec,
                    "state how many violations exist today",
                    "a counting surface exists but no numeric violation budget or count is committed",
                    Verdict.PARTIAL,
                    [Evidence(rel) for rel in surface[:6]],
                    "Commit the count or configure a budget (`--max-warnings N`, `max-issues`, or a "
                    "`violation budget`) so a regression has a baseline number to compare against.",
                )
            ],
        )

    if _recognised(inventory, stack):
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"no violation-count mechanism found; method: {_METHOD}",
            [
                _finding(
                    spec,
                    "state how many violations exist today",
                    "no violation-counting tooling, budget or artifact is configured",
                    Verdict.PARTIAL,
                    [Evidence("<repository>")],
                    "Add linters/type-checkers/security scanners and commit the count they produce, so "
                    "debt is measured rather than guessed.",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem or counting configuration, so a count cannot be ruled out")
