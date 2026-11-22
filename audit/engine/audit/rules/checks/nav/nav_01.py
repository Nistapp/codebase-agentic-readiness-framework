# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""NAV-01: Declared component boundaries."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks.nav._shared import _outcome, _unknown

SPEC = declare("NAV-01", "Declared component boundaries", "A", Severity.DEGRADER)


# ===========================================================================
# NAV-01 — declared component boundaries
# ===========================================================================


def check_nav01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    members = [c for c in components.declared if not c.is_root]
    if members:
        detail = ", ".join(f"{c.path} (by {c.declared_by})" for c in members[:6])
        return _outcome(spec, Verdict.PASS, f"{len(members)} declared component(s): {detail}")

    if components.candidates:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"{len(components.candidates)} candidate component(s), none declared",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "scope work to a bounded component",
                        f"{', '.join(components.candidates[:6])} look like components but no build "
                        f"manifest declares them",
                    ),
                    evidence=[Evidence(path) for path in components.candidates[:12]],
                    remediation="Declare the components in a workspace manifest (npm workspaces, "
                    "pnpm-workspace.yaml, Maven modules, Gradle includes) so blast radius "
                    "is scoped.",
                ),
            ],
        )

    root = next((c for c in components.declared if c.is_root), None)
    if root is not None and root.manifest:
        return _outcome(spec, Verdict.PASS, f"single-root repository declares {root.manifest}")

    if stack.ecosystems:
        return _unknown(
            spec,
            "no build manifest the component detector reads declares a component; ecosystems: "
            + ", ".join(sorted(stack.ecosystems)),
        )
    return _unknown(spec, "no build manifest declares a component; stack not recognised")
