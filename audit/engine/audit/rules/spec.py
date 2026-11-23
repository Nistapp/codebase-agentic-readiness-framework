# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The check specification type, and the framework anchor of each pack.

A check family module declares its checks with :func:`declare`, beside their implementations. The
registry assembles those declarations into the catalogue. This module imports no check module, so a
check module can import it without an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from audit.findings import Severity, Verdict


@dataclass(frozen=True)
class Anchor:
    """A heading in the framework's documentation that justifies a pack."""

    file: str
    heading: str
    phase: int = 1


#: Where in the framework each pack comes from. Paths are relative to the framework repo root.
PACK_ANCHORS: dict[str, Anchor] = {
    "IDX": Anchor("docs/framework/phased-approach.md", "Phase 1: Agentic Bootstrap"),
    "AGT": Anchor("docs/framework/phased-approach.md", "Phase 1: Agentic Bootstrap"),
    "DOC": Anchor("docs/framework/phased-approach.md", "Key Deliverables"),
    "CMD": Anchor("docs/framework/phased-approach.md", "Activities"),
    "TOOL": Anchor("docs/framework/phased-approach.md", "Key Deliverables"),
    "CI": Anchor("docs/framework/phased-approach.md", "Key Deliverables"),
    "BASE": Anchor("docs/framework/phased-approach.md", "Activities"),
    "CON": Anchor("docs/framework/phased-approach.md", "Key Deliverables"),
    "EXEC": Anchor("docs/framework/phased-approach.md", "Activities"),
    "TST": Anchor("docs/framework/phased-approach.md", "Activities"),
    "NAV": Anchor("docs/framework/phased-approach.md", "Key Deliverables"),
    "SEC": Anchor("docs/framework/phased-approach.md", "Key Deliverables"),
    "HYG": Anchor("docs/framework/phased-approach.md", "Phase 1: Agentic Bootstrap"),
}


@dataclass
class CheckSpec:
    id: str
    title: str
    tier: str  # A (artifact) | B (contract) | C (executed probe)
    severity: Severity
    evidence_rule: str
    phase: int = 1
    scored: bool = True
    ecosystems: tuple[str, ...] = ()  # empty = applies to every stack
    status: str = "planned"  # implemented | planned | blocked
    impl: Callable | None = None

    # -- convenience -----------------------------------------------------
    @property
    def pack(self) -> str:
        return self.id.split("-")[0]

    @property
    def anchor(self) -> Anchor | None:
        return PACK_ANCHORS.get(self.pack)

    def applies_to(self, stack) -> bool:
        return not self.ecosystems or bool(set(self.ecosystems) & stack.ecosystems)

    def run(self, **kwargs):
        """Execute the check, or report it honestly as unimplemented."""
        from audit.evaluate import CheckOutcome

        if self.status == "blocked":
            return CheckOutcome(
                self.id,
                self.title,
                self.tier,
                self.severity,
                self.phase,
                Verdict.UNKNOWN,
                self.status,
                summary="blocked: this ruleset cannot evaluate the check, so it carries weight 0",
            )
        if self.impl is None:
            return CheckOutcome(
                self.id,
                self.title,
                self.tier,
                self.severity,
                self.phase,
                Verdict.UNKNOWN,
                self.status,
                summary=f"not implemented in ruleset {_revision()}",
            )
        return self.impl(spec=self, **kwargs)


def _revision() -> str:
    from audit import __ruleset_revision__

    return __ruleset_revision__


def declare(
    check_id: str,
    title: str,
    tier: str,
    sev: Severity,
    status: str = "planned",
    scored: bool = True,
    rule: str = "",
    ecosystems: tuple[str, ...] = (),
) -> CheckSpec:
    """Declare one check: its id, title, tier, severity and, where the catalogue gives one, its evidence rule."""
    return CheckSpec(
        id=check_id,
        title=title,
        tier=tier,
        severity=sev,
        evidence_rule=rule,
        status=status,
        scored=scored,
        ecosystems=ecosystems,
    )
