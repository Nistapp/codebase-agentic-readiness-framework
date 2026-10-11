# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Convert an engine report (schema v2) into the parts of an audit draft.

`report.py import-engine` reads the engine's JSON report and calls `convert`; this module holds no I/O, so the same
report always converts to the same parts. The rules are the tables "Verdicts: engine to report" and "Engine schema v2
mapping" in schema/SCHEMA.md, and the engine's own report model is deterministic-audit/audit/report/model.py.

The adapter reads the fields it needs and no others, and checks only what it indexes: an engine report that breaks
that shape is refused, with every problem listed, and never fails with a `KeyError`. What the report schema limits
(lengths, patterns) is left to the validator, which `report.py` runs on the result before it writes anything.

Failure behaviour: `convert` raises `ValidationFailed` for an engine report that is not schema v2, is not for phase 1,
or does not have the shape the mapping reads.

Standard library only. This file must parse as Python 3.9.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn, Sequence

import _common
import _jsonschema_subset as subset
import validate_report as vr

ENGINE_SCHEMA_VERSION = "2"
PHASE = 1

# The shape the adapter reads, and no more. The report schema's own limits apply to what is carried.
ENGINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["provenance"],
    "properties": {
        "provenance": {
            "type": "object",
            "required": ["tool", "version", "ruleset_hash", "target", "phase"],
            "properties": {
                "tool": {"type": "string"},
                "version": {"type": "string"},
                "ruleset_revision": {"type": "string"},
                "ruleset_hash": {"type": "string"},
                "scanned_at": {"type": "string"},
                "target": {"type": "string"},
                "git_sha": {"type": ["string", "null"]},
                "phase": {"type": "integer"},
            },
        },
    },
}


@dataclass(frozen=True)
class Conversion:
    """What an engine report becomes: the engine's own record, and the target it says it scanned."""

    engine: dict[str, Any]
    target_path: str
    git_sha: str | None


def refuse(message: str, errors: Sequence[str]) -> NoReturn:
    raise _common.ValidationFailed(message, errors=errors)


def check_engine_report(engine: Any) -> None:
    """Refuse a report that is not schema v2 for phase 1, or that lacks a field the mapping reads."""
    if not isinstance(engine, dict):
        refuse("the engine report is not a JSON object", ["engine report: the top level must be an object"])
    found = engine.get("schema_version")
    if found != ENGINE_SCHEMA_VERSION:
        refuse(
            f"the engine report has schema_version {found!r}, and the adapter reads only {ENGINE_SCHEMA_VERSION!r}",
            [f"engine report: /schema_version: expected {ENGINE_SCHEMA_VERSION!r}, found {found!r}"],
        )
    problems = [
        f"engine report: {violation}"
        for violation in subset.SubsetValidator(ENGINE_SCHEMA).validate(engine, limit=vr.MAX_SCHEMA_ERRORS)
    ]
    if problems:
        count = len(problems)
        refuse(f"the engine report has the wrong shape: {count} error{'' if count == 1 else 's'}", problems)
    phase = engine["provenance"]["phase"]
    if phase != PHASE:
        refuse(
            f"the engine report is for phase {phase}, and a 0.1 report covers phase {PHASE}",
            [f"engine report: /provenance/phase: expected {PHASE}, found {phase}"],
        )


def engine_record(provenance: dict[str, Any]) -> dict[str, Any]:
    """`provenance.engine`: the engine that produced the automated verdicts, in the order of the schema."""
    record: dict[str, Any] = {"name": provenance["tool"], "version": provenance["version"]}
    if "ruleset_revision" in provenance:
        record["ruleset_revision"] = provenance["ruleset_revision"]
    record["ruleset_hash"] = provenance["ruleset_hash"]
    if "scanned_at" in provenance:
        record["scanned_at"] = provenance["scanned_at"]
    return record


def convert(engine: Any) -> Conversion:
    """The parts of a draft that `engine` stands for. Raises `ValidationFailed` for a report it cannot read."""
    check_engine_report(engine)
    provenance = engine["provenance"]
    return Conversion(
        engine=engine_record(provenance),
        target_path=provenance["target"],
        git_sha=provenance.get("git_sha"),
    )
