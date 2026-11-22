# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""BASE-03: No-new-violations mechanism."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import README, entry_documents
from audit.scan import Inventory
from audit.stack import CI_PROVIDERS
from audit.rules.checks.base._shared import (
    _DOCS,
    _baseline_artifacts,
    _budget_evidence,
    _finding,
    _outcome,
    _recognised,
    _unknown,
)

SPEC = declare("BASE-03", "No-new-violations mechanism", "B", Severity.DEGRADER)


#: A documented *comparison step* (BASE-03): the repo compares a scan against a baseline.
_DOC_RATCHET_RE = re.compile(
    r"(?i)(?:ratchet|no[- ]new[- ]violations?|violation\s+budget"
    r"|(?:compare|comparison|regression)[^\n]{0,48}baseline"
    r"|baseline[^\n]{0,48}(?:compare|comparison|regression))"
)


def _ci_references_baseline(inventory: Inventory, names: set[str]) -> list[str]:
    found: set[str] = set()
    for _provider, globs in CI_PROVIDERS.items():
        for rel in inventory.match(*globs):
            text = inventory.read(rel)
            if text and any(name in text for name in names):
                found.add(rel)
    return sorted(found)


def _ratchet(inventory: Inventory, stack, budgets: list[str]) -> list[str]:
    """Every committed no-new-violations mechanism found, in a deterministic order."""
    if budgets:
        return [f"violation budget ({source})" for source in budgets]

    artifacts = _baseline_artifacts(inventory)
    if artifacts:
        names = {rel.rsplit("/", 1)[-1] for rel in artifacts}
        referenced = _ci_references_baseline(inventory, names)
        if referenced:
            return [f"baseline compared in CI ({rel})" for rel in referenced]

    documented = []
    for rel in entry_documents(inventory, _DOCS + (README, "CONTRIBUTING.md")):
        text = inventory.read(rel)
        if text and _DOC_RATCHET_RE.search(text):
            documented.append(rel)
    return [f"comparison step documented in {rel}" for rel in sorted(set(documented))]


# ===========================================================================
# BASE-03 — no-new-violations mechanism
# ===========================================================================


def check_base03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    ratchet = _ratchet(inventory, stack, _budget_evidence(inventory, stack))
    if ratchet:
        return _outcome(spec, Verdict.PASS, f"ratchet present: {', '.join(ratchet)}")

    artifacts = _baseline_artifacts(inventory)
    if artifacts:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"baseline present but never compared against: {', '.join(artifacts)}",
            [
                _finding(
                    spec,
                    "stop the violation count from growing",
                    f"a baseline is committed ({', '.join(artifacts)}) but nothing compares against it",
                    Verdict.FAIL,
                    [Evidence(rel) for rel in artifacts],
                    "Add a comparison step — a CI job that runs `--baseline <report>`, a violation budget "
                    "in config, or a documented no-new-violations procedure — so the baseline is enforced.",
                )
            ],
        )

    if _recognised(inventory, stack):
        return _outcome(
            spec,
            Verdict.PARTIAL,
            "no ratchet and no baseline yet, so there is nothing to compare against",
            [
                _finding(
                    spec,
                    "stop the violation count from growing",
                    "no baseline, budget or comparison step exists, so the count is not guarded",
                    Verdict.PARTIAL,
                    [Evidence("<repository>")],
                    "Once a baseline exists, wire a comparison step (the audit's own `--baseline REPORT.JSON` "
                    "is the reference pattern) so new findings fail the build.",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem or configuration, so a ratchet cannot be ruled out")
