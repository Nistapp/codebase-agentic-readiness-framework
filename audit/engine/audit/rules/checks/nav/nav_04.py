# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""NAV-04: Architecture orientation artifact."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks.nav._shared import _outcome

SPEC = declare("NAV-04", "Architecture orientation artifact", "A", Severity.COSMETIC, scored=False)


# ===========================================================================
# NAV-04 — architecture orientation artifact (informational)
# ===========================================================================

_DIAGRAM_SUFFIXES = (".mmd", ".puml", ".drawio", ".excalidraw", ".svg", ".png")


def check_nav04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    has_arch = any(f.rel.startswith("docs/architecture/") for f in inventory.files)
    has_adr = any(f.rel.startswith(("docs/architecture/adrs/", "docs/adr/")) for f in inventory.files)
    diagrams = sorted(f.rel for f in inventory.files if f.rel.lower().endswith(_DIAGRAM_SUFFIXES))

    if has_arch or has_adr or diagrams:
        parts = []
        if has_arch:
            parts.append("docs/architecture/")
        if has_adr:
            parts.append("an ADR directory")
        if diagrams:
            parts.append(f"{len(diagrams)} diagram(s)")
        return _outcome(spec, Verdict.PASS, "; ".join(parts))

    return _outcome(
        spec,
        Verdict.FAIL,
        "no architecture orientation artifact",
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "orient itself from a map instead of exploring blindly",
                    "no docs/architecture/, ADR directory or diagram exists",
                ),
                remediation="Add a short architecture page (with a diagram) so an agent can orient before it explores.",
            ),
        ],
    )
