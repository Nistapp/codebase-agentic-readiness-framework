# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The readiness summary of a report, computed from its checks and findings.

The definition is spec/readiness-summary.md and the field list is "summary" in schema/SCHEMA.md. The validator
recomputes the summary with this code and fails on a difference, the report builder writes it with this code, and the
renderer shows it, so the three cannot disagree. The model never writes a summary.

The function reads a report that has passed the schema. It does not fail on a dangling reference (a finding whose
check is missing): rule 1 of the validator reports that, and the summary must still come out so that every rule runs.

Standard library only. This file must parse as Python 3.9.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# What an unmet check costs: the severity's weight in the score.
WEIGHTS = {"BLOCKER": 3, "DEGRADER": 2, "COSMETIC": 1}

# Credit per verdict, counted in halves so that the sums stay whole numbers: PASS 1, PARTIAL 0.5, FAIL 0, UNKNOWN 0.
HALF_CREDITS = {"PASS": 2, "PARTIAL": 1, "FAIL": 0, "UNKNOWN": 0}

SCORE_PLACES = 4
BLOCKER_STATES = ("fail", "partial", "unknown")


def scored_checks(checks: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The checks the score covers: scored, of phase 1, and with a verdict. NOT_APPLICABLE has none, so it is left out."""
    return [
        check for check in checks if check["scored"] and check["phase"] == 1 and check["verdict"] != "NOT_APPLICABLE"
    ]


def open_blockers(checks: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The scored BLOCKER checks whose verdict is not PASS: FAIL, PARTIAL or UNKNOWN. "Blockers remaining" counts them."""
    return [check for check in scored_checks(checks) if check["severity"] == "BLOCKER" and check["verdict"] != "PASS"]


def compute_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    """The five summary fields, in the schema's order."""
    scored = scored_checks(report["checks"])
    weight = sum(WEIGHTS[check["severity"]] for check in scored)
    earned = sum(WEIGHTS[check["severity"]] * HALF_CREDITS[check["verdict"]] for check in scored)
    score = round(earned / (2 * weight), SCORE_PLACES) if weight else 0.0

    unmet = open_blockers(report["checks"])
    blockers: dict[str, int] = {"total": len(unmet)}
    for state in BLOCKER_STATES:
        blockers[state] = sum(1 for check in unmet if check["verdict"] == state.upper())

    agent_checks = {check["id"] for check in report["checks"] if check["method"] == "agent"}
    unconfirmed = sum(
        1 for finding in report["findings"] if finding["check"] in agent_checks and finding["disposition"] == "pending"
    )
    return {
        "phase1_score": score,
        "scored_checks": len(scored),
        "blockers_remaining": blockers,
        "unknown_scored_checks": sum(1 for check in scored if check["verdict"] == "UNKNOWN"),
        "unconfirmed_agent_findings": unconfirmed,
    }
