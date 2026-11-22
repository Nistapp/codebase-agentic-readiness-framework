# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""BASE-01: Baseline artifact exists."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.checks.base._shared import (
    _DOCS,
    _baseline_artifacts,
    _counting_tools,
    _finding,
    _outcome,
    _recognised,
    _unknown,
)

SPEC = declare("BASE-01", "Baseline artifact exists", "A", Severity.DEGRADER)


#: A documented baseline/suppression *mechanism* (BASE-01), distinct from a comparison step (BASE-03).
_DOC_BASELINE_RE = re.compile(
    r"(?i)(?:quality\s+baseline|baseline\s+(?:file|report|artifact|artefact|count|json)"
    r"|no[- ]new[- ]violations?|violation\s+budget"
    r"|suppress(?:ion|ed)?\s+(?:file|list|count))"
)


def _documented_baseline(inventory: Inventory) -> str | None:
    for rel in _DOCS:
        text = inventory.read(rel)
        if text and _DOC_BASELINE_RE.search(text):
            return rel
    return None


# ===========================================================================
# BASE-01 — baseline artifact exists
# ===========================================================================


def check_base01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    artifacts = _baseline_artifacts(inventory)
    documented = _documented_baseline(inventory)
    if artifacts or documented:
        evidence = artifacts or [documented or "<repository>"]
        return _outcome(
            spec,
            Verdict.PASS,
            f"baseline/suppression mechanism present: "
            f"{', '.join(evidence)}" + ("" if artifacts else f" (documented in {documented})"),
        )

    tools = _counting_tools(inventory, stack)
    if tools:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"quality tooling is configured but no baseline artifact is committed: {', '.join(tools[:6])}",
            [
                _finding(
                    spec,
                    "diff today's findings against an accepted baseline",
                    "quality tooling is configured but no baseline or suppression artifact is committed",
                    Verdict.PARTIAL,
                    [Evidence(rel) for rel in tools[:6]],
                    "Commit a baseline or suppression artifact (for example `baseline.json`, an "
                    "eslint/ruff baseline, or `.gitleaksignore`), or document the equivalent mechanism in "
                    "`AGENTS.md`.",
                )
            ],
        )

    if _recognised(inventory, stack):
        return _outcome(
            spec,
            Verdict.FAIL,
            "no baseline or suppression artifact",
            [
                _finding(
                    spec,
                    "distinguish pre-existing debt from new debt",
                    "no baseline or suppression artifact is committed",
                    Verdict.FAIL,
                    [Evidence("<repository>")],
                    "Commit a baseline/suppression artifact, or document the equivalent mechanism in `AGENTS.md`.",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem or configuration, so a baseline cannot be ruled out")
