# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one DOC check uses."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Finding, Verdict
from audit.scan import Inventory
from audit.rules.payloads import Payload


def _outcome(
    spec, verdict: Verdict, summary: str = "", findings: list[Finding] | None = None, data: Payload | None = None
) -> CheckOutcome:
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=summary,
        data=data,
        findings=findings or [],
    )


def _has_exact(inventory: Inventory, rel: str) -> bool:
    """Exact path membership: unlike ``Inventory.has``, never a suffix match at any depth."""
    return any(f.rel == rel for f in inventory.files)
