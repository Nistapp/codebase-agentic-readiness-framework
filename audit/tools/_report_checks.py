# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The check half of `report.py`: what an `add-check` fragment is, the counts of recorded checks, and how a check is
recorded or disputed in a draft. `report.py` re-exports every name.
"""

from __future__ import annotations

from typing import Any, Mapping

import _common
import _jsonschema_subset as subset
import validate_report as vr
from _report_draft import Change, expected_checks, fragment_validator, in_schema_order


CHECK_FIELDS = ("id", "verdict", "summary", "confidence", "evidence", "searches", "override_reason")
CHECK_REQUIRED = ("id", "verdict", "summary")


def check_validator() -> subset.SubsetValidator:
    return fragment_validator(CHECK_FIELDS, CHECK_REQUIRED, "check")


def recorded_checks(document: Mapping[str, Any]) -> dict[str, int]:
    return {check["id"]: index for index, check in enumerate(document["checks"])}


def accounted_checks(document: Mapping[str, Any]) -> set[str]:
    """The checks the draft has dealt with: the recorded ones, and those the engine marked ATTEST.

    A check marked ATTEST has no verdict, so it is not recorded; it is listed in `unattested` with its lower-case id as
    the `property`, and a draft that lists it has not left it out.
    """
    attested = {item["property"].upper() for item in document["unattested"] if "property" in item}
    return set(recorded_checks(document)) | attested


def check_counts(document: Mapping[str, Any]) -> dict[str, int]:
    wanted = {check["id"] for check in expected_checks()}
    return {"checks_recorded": len(wanted & accounted_checks(document)), "checks_expected": len(wanted)}


def apply_check(document: dict[str, Any], fragment: Mapping[str, Any]) -> Change:
    """Record the agent's result for one check.

    A check the agent evaluates is added from the catalogue's entry, so the agent never writes its title, phase,
    severity, `scored` or method. Recording it again replaces it. A check the engine ran is the engine's: the agent
    can dispute its verdict, which keeps `engine_verdict` and the engine's evidence and adds the agent's reason
    and evidence, but it cannot create such a check or change what the engine recorded.
    """
    check_id = fragment["id"]
    entry = {check["id"]: check for check in vr.load_catalogue()["checks"]}.get(check_id)
    if entry is None:
        raise _common.ValidationFailed(
            f"{check_id} is not a check in the catalogue",
            errors=[f"fragment: /id: {check_id} is not in catalogue.json"],
        )
    index = recorded_checks(document).get(check_id)
    if index is None:
        if entry["method"] != "agent":
            raise _common.ValidationFailed(
                f"{check_id} is an automated check, so its verdict comes from the engine and an agent cannot add it",
                errors=[
                    f"{check_id} is recorded by importing the engine's report; an agent can only dispute that "
                    "verdict afterwards, with a reason and evidence"
                ],
            )
        base = entry
        action = "added"
    else:
        current = document["checks"][index]
        if "engine_verdict" in current:
            return override_check(document, index, fragment)
        if current["method"] != "agent":
            raise _common.ValidationFailed(
                f"{check_id} is an automated check with no engine verdict, so it cannot be changed here"
            )
        base = current
        action = "replaced"
    check: dict[str, Any] = {name: base[name] for name in ("id", "title", "phase", "severity", "scored", "method")}
    check.update({name: fragment[name] for name in CHECK_FIELDS if name in fragment and name != "id"})
    check.setdefault("evidence", [])
    check.setdefault("searches", [])
    if index is None:
        index = len(document["checks"])
        document["checks"].append({})
    document["checks"][index] = in_schema_order(check, "check")
    return Change(
        data={"check": check_id, "action": action, "verdict": check["verdict"]}, touched=[f"/checks/{index}/"]
    )


def override_check(document: dict[str, Any], index: int, fragment: Mapping[str, Any]) -> Change:
    """The agent's verdict for a check the engine ran.

    The engine's evidence stays, and the agent's evidence replaces any it gave before, so recording the same dispute
    twice does not pile up. A verdict equal to the engine's clears an earlier dispute.
    """
    current = document["checks"][index]
    check = dict(current)
    check["verdict"] = fragment["verdict"]
    check["summary"] = fragment["summary"]
    for name in ("confidence", "override_reason"):
        if name in fragment:
            check[name] = fragment[name]
        else:
            check.pop(name, None)
    check["evidence"] = [e for e in current["evidence"] if e["captured_by"] == "tool"] + list(
        fragment.get("evidence", [])
    )
    check["searches"] = list(fragment.get("searches", []))
    document["checks"][index] = in_schema_order(check, "check")
    action = "overridden" if check["verdict"] != current["engine_verdict"] else "agreed"
    return Change(
        data={
            "check": check["id"],
            "action": action,
            "verdict": check["verdict"],
            "engine_verdict": current["engine_verdict"],
        },
        touched=[f"/checks/{index}/"],
    )
