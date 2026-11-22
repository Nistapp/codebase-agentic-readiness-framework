# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The decision half of `report.py`: what a `set-disposition` request is, which decisions are refused, and how they are
applied to a draft. `report.py` re-exports every name.
"""

from __future__ import annotations

import argparse
from typing import Any, Mapping, Sequence

import _common
import _jsonschema_subset as subset
from _report_draft import Change, fragment_errors, in_schema_order, read_fragment, report_schema


DISPOSITIONS = ("pending", "confirmed", "rejected", "deferred", "edited")
VIA = ("interactive", "batch", "policy")
MAX_DECISIONS = 2000


def decisions_validator() -> subset.SubsetValidator:
    """A validator for a list of decisions, each field with the report schema's own rule."""
    schema = report_schema()
    finding = schema["$defs"]["finding"]["properties"]
    return subset.SubsetValidator(
        {
            "$defs": schema["$defs"],
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_DECISIONS,
            "items": {
                "type": "object",
                "required": ["finding", "disposition"],
                "additionalProperties": False,
                "properties": {
                    "finding": {"$ref": "#/$defs/findingId"},
                    "disposition": finding["disposition"],
                    "note": finding["disposition_note"],
                },
            },
        }
    )


def read_decisions(args: argparse.Namespace) -> list[dict[str, Any]]:
    """The decisions asked for: one from the arguments, or a list from a file or stdin."""
    if args.source is not None:
        if args.finding is not None or args.disposition is not None or args.note is not None:
            raise _common.UsageError("--from cannot be combined with --finding, --disposition or --note")
        decisions = read_fragment(args.source, "decision list")
    else:
        if args.finding is None or args.disposition is None:
            raise _common.UsageError("give --finding and --disposition, or give a list with --from")
        item = {"finding": args.finding, "disposition": args.disposition}
        if args.note is not None:
            item["note"] = args.note
        decisions = [item]
    problems = fragment_errors(decisions_validator(), decisions)
    if problems:
        count = len(problems)
        raise _common.ValidationFailed(
            f"the decisions are not valid: {count} error{'' if count == 1 else 's'}", errors=problems
        )
    checked: list[dict[str, Any]] = decisions
    return checked


def refused_decisions(
    document: Mapping[str, Any], decisions: Sequence[Mapping[str, Any]], via: str | None
) -> list[str]:
    """What stops these decisions, as a list of problems, or an empty list.

    The validator checks most of this too, in the rules, but only after the fact and in the rules' words. These are
    the ways a decision can claim something false about who made it: a person where there is none, a batch for a
    finding that must be decided alone, a policy that does not decide.
    """
    context = document["run_context"]
    findings = {finding["id"]: finding for finding in document["findings"]}
    problems: list[str] = []
    seen: set[str] = set()
    for number, decision in enumerate(decisions):
        name = decision["finding"]
        finding = findings.get(name)
        if finding is None:
            problems.append(f"fragment: /{number}/finding: {name} is not a finding in this draft")
            continue
        if name in seen:
            problems.append(f"fragment: /{number}/finding: {name} appears twice in the list")
        seen.add(name)
        if decision["disposition"] != "pending" and via == "batch" and finding["severity"] == "BLOCKER":
            problems.append(f"{name} is a BLOCKER, so a person decides on it alone: use --via interactive")
    if any(decision["disposition"] != "pending" for decision in decisions):
        if context["eval_mode"] and via != "policy":
            problems.append("this is an eval-mode run, which has no person to decide: only --via policy is allowed")
        if via == "policy" and context["confirmation_policy"] != "accept-all":
            problems.append(
                f"--via policy needs the 'accept-all' confirmation policy, and this run's is {context['confirmation_policy']!r}"
            )
    return problems


def apply_decisions(document: dict[str, Any], decisions: Sequence[Mapping[str, Any]], via: str | None) -> Change:
    """Set the dispositions, all or none. `pending` takes a decision back, so it keeps no `via` and no note."""
    problems = refused_decisions(document, decisions, via)
    if problems:
        raise _common.ValidationFailed(
            f"the decisions are refused: {len(problems)} problem{'' if len(problems) == 1 else 's'}", errors=problems
        )
    index = {finding["id"]: number for number, finding in enumerate(document["findings"])}
    counts: dict[str, int] = {}
    for decision in decisions:
        finding = dict(document["findings"][index[decision["finding"]]])
        for name in ("confirmed_via", "disposition_note"):
            finding.pop(name, None)
        finding["disposition"] = decision["disposition"]
        if decision["disposition"] != "pending":
            finding["confirmed_via"] = via
            if "note" in decision:
                finding["disposition_note"] = decision["note"]
        document["findings"][index[decision["finding"]]] = in_schema_order(finding, "finding")
        counts[decision["disposition"]] = counts.get(decision["disposition"], 0) + 1
    return Change(data={"updated": len(decisions), "by_disposition": dict(sorted(counts.items()))})


def decision_counts(document: Mapping[str, Any]) -> dict[str, int]:
    pending = [finding for finding in document["findings"] if finding["disposition"] == "pending"]
    return {
        "findings": len(document["findings"]),
        "findings_pending": len(pending),
        "blockers_pending": sum(1 for finding in pending if finding["severity"] == "BLOCKER"),
    }
