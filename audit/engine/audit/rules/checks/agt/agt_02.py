# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-02: Component coverage by instruction files."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.payloads import Ratio
from audit.rules.checks.agt._shared import instruction_paths

SPEC = declare("AGT-02", "Component coverage by instruction files", "A", Severity.DEGRADER)


# ---------------------------------------------------------------------------
# AGT-02 — component coverage
# ---------------------------------------------------------------------------


def check_agt02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    members = [c for c in components.declared if not c.is_root]
    if not members:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.PASS,
            spec.status,
            summary=(
                f"no declared components; {len(components.candidates)} candidate component(s) are not scored "
                f"(ADR-0003): {', '.join(components.candidates[:6])}"
                if components.candidates
                else "single-root repository: no component-level instruction files required"
            ),
        )

    covered: list[str] = []
    uncovered: list[str] = []
    for component in members:
        candidate = f"{component.path}/AGENTS.md"
        if inventory.has(candidate) or any(
            p.endswith(f"{component.path}/AGENTS.md") for p in instruction_paths(inventory)
        ):
            covered.append(component.path)
        else:
            uncovered.append(component.path)

    ratio = len(covered) / len(members)
    findings: list[Finding] = []
    if uncovered:
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "get component-scoped rules when it enters a component",
                    f"{len(uncovered)} of {len(members)} declared components have no AGENTS.md "
                    f"({', '.join(uncovered[:6])}{'…' if len(uncovered) > 6 else ''}), so the root file "
                    f"is the only guidance available",
                ),
                remediation="Add a short AGENTS.md per component stating what is local to it — "
                "ownership, entry points, test verb overrides.",
            )
        )
    verdict = Verdict.PASS if ratio == 1.0 else (Verdict.FAIL if ratio == 0 else Verdict.PARTIAL)
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=f"coverage {len(covered)}/{len(members)}",
        data=Ratio(
            numerator=len(covered),
            denominator=len(members),
            unit="components",
            method="declared AGENTS.md per component",
        ),
        findings=findings,
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import COMPONENTS, GLOB, ROOT, Reads, What, _at

    return Reads(
        where=(
            *_at(GLOB, "*/**/AGENTS.md"),
            *_at(
                ROOT,
                "package.json",
                "pnpm-workspace.yaml",
                "pom.xml",
                "settings.gradle",
                "settings.gradle.kts",
                "go.work",
                "Cargo.toml",
                via=COMPONENTS,
            ),
        ),
        what=What("exists"),
        binding="file",
        threshold="every declared component has an AGENTS.md",
        note=(
            "The root manifests declare the components (components.py); for each one <component>/AGENTS.md "
            "must exist, matched as a path suffix at any depth. The root component is left out, so the root "
            "AGENTS.md never counts. The suffix test runs over agt.instruction_paths, which scans every "
            "instruction file name, but only a path ending in <component>/AGENTS.md counts, so the other names "
            "are never read for this check."
        ),
    )
