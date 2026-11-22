# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The finding half of `report.py`: what an `add-finding` fragment is, a finding's key and id, and how a finding is
recorded in a draft. `report.py` re-exports every name.
"""

from __future__ import annotations

import posixpath
import re
from typing import Any, Mapping, Sequence

import _common
import _jsonschema_subset as subset
import validate_report as vr
from _report_draft import Change, fragment_validator, in_schema_order


FINDING_FIELDS = ("check", "severity", "statement", "evidence", "searches", "remediation")
FINDING_REQUIRED = ("check", "statement", "remediation")
SCOPE_SCHEMA = {
    "description": "A path or a component that tells apart two findings of one check. It becomes part of the key.",
    "type": "string",
    "minLength": 1,
    "maxLength": 300,
}


def finding_validator() -> subset.SubsetValidator:
    return fragment_validator(FINDING_FIELDS, FINDING_REQUIRED, "finding", {"scope": SCOPE_SCHEMA})


def normal_scope(scope: str) -> str | None:
    """A scope in the one spelling every run gives it, or None when it names the whole check.

    A key must be the same for the same finding in any run (R-14), so `./src//a.ts`, `src\\a.ts` and `src/a.ts`
    are one scope. A scope that leaves the target is not a path inside it and cannot name a finding there.
    """
    if not scope.strip():
        raise _common.ValidationFailed(
            "the finding's scope is not usable", errors=["fragment: /scope: the scope is empty; leave it out"]
        )
    text = posixpath.normpath(scope.strip().replace("\\", "/"))
    if text == ".":
        return None
    reason = vr.leaves_target(text)
    if reason is not None:
        raise _common.ValidationFailed(
            "the finding's scope is not usable", errors=[f"fragment: /scope: the scope {reason}"]
        )
    if re.search(r"\s", text):
        raise _common.ValidationFailed(
            "the finding's scope is not usable", errors=["fragment: /scope: the scope must not contain whitespace"]
        )
    return text


def finding_key(check_id: str, scope: str | None) -> str:
    return check_id if scope is None else f"{check_id}:{scope}"


def next_finding_id(findings: Sequence[Mapping[str, Any]]) -> str:
    """`F-001`, `F-002`, and so on: one more than the highest in use, so an id is never reused."""
    highest = max((int(finding["id"][2:]) for finding in findings), default=0)
    return f"F-{highest + 1:03d}"


def finding_counts(document: Mapping[str, Any]) -> dict[str, int]:
    findings = document["findings"]
    return {
        "findings": len(findings),
        "findings_pending": sum(1 for finding in findings if finding["disposition"] == "pending"),
    }


def initial_decision(document: Mapping[str, Any]) -> dict[str, str]:
    """What a new finding starts with: `pending`, or `confirmed` by policy when the run's policy is `accept-all`."""
    if document["run_context"]["confirmation_policy"] == "accept-all":
        return {"disposition": "confirmed", "confirmed_via": "policy"}
    return {"disposition": "pending"}


def apply_finding(document: dict[str, Any], fragment: Mapping[str, Any]) -> Change:
    """Record an issue a check raised.

    The tool computes the key, assigns the id and sets the disposition: `pending` until a person decides, or
    `confirmed` by policy when the run's policy is `accept-all`. A finding the agent already recorded is replaced
    while it is `pending`. One that has a decision is not the agent's to change.
    """
    check = next((c for c in document["checks"] if c["id"] == fragment["check"]), None)
    if check is None:
        raise _common.ValidationFailed(
            f"{fragment['check']} is not a check in this draft",
            errors=[
                f"fragment: /check: record {fragment['check']} first, with add-check or by importing the engine's report"
            ],
        )
    key = finding_key(fragment["check"], normal_scope(fragment["scope"]) if "scope" in fragment else None)
    index = next((i for i, f in enumerate(document["findings"]) if f["key"] == key), None)
    current = None if index is None else document["findings"][index]
    if current is not None and current["disposition"] != "pending":
        raise _common.ValidationFailed(
            f"{current['id']} ({key}) already has a decision, so the agent cannot rewrite it",
            errors=[
                f"{current['id']} is {current['disposition']}. To record it again, set its disposition back to "
                "pending with set-disposition first, or use another scope for a different finding."
            ],
        )
    finding: dict[str, Any] = {
        "id": next_finding_id(document["findings"]) if current is None else current["id"],
        "key": key,
        "check": fragment["check"],
        "severity": fragment.get("severity", check["severity"]),
        "statement": fragment["statement"],
        "evidence": fragment.get("evidence", []),
        "searches": fragment.get("searches", []),
        "remediation": fragment["remediation"],
        **initial_decision(document),
    }
    if index is None:
        index = len(document["findings"])
        document["findings"].append({})
    document["findings"][index] = in_schema_order(finding, "finding")
    return Change(
        data={
            "finding": finding["id"],
            "key": key,
            "action": "added" if current is None else "replaced",
            "check": finding["check"],
            "severity": finding["severity"],
            "disposition": finding["disposition"],
        },
        touched=[f"/findings/{index}/"],
    )
