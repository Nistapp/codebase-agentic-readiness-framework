# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Convert an engine report (schema v2) into the parts of an audit draft.

`report.py import-engine` reads the engine's JSON report and calls `convert`; this module reads nothing but the report
schema, so the same report always converts to the same parts. The rules are the tables "Verdicts: engine to report"
and "Engine schema v2 mapping" in schema/SCHEMA.md, and the engine's own report model is
deterministic-audit/audit/report/model.py.

The adapter reads the fields it needs and no others, and checks only what it indexes: an engine report that breaks
that shape is refused, with every problem listed, and never fails with a `KeyError`. What the report schema limits
(patterns, the rules) is left to the validator, which `report.py` runs on the result before it writes anything. A text
the report schema limits in length is cut to the limit and the cut is a warning, because a long engine sentence is
no reason to refuse a whole audit. Nothing the engine said is dropped without a warning.

Failure behaviour: `convert` raises `ValidationFailed` for an engine report that is not schema v2, is not for phase 1,
does not have the shape the mapping reads, or holds a check or a finding the report cannot place.

Standard library only. This file must parse as Python 3.9.
"""

from __future__ import annotations

import copy
import json
import re
import shlex
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Collection, Mapping, NoReturn, Sequence

import _common
import _jsonschema_subset as subset
import validate_report as vr

ENGINE_SCHEMA_VERSION = "2"
PHASE = 1
SEVERITIES = ["BLOCKER", "DEGRADER", "COSMETIC"]
VERDICTS = ["PASS", "PARTIAL", "FAIL", "UNKNOWN", "ATTEST"]
CUT_MARK = "…"
KEY_ROOM = 8
NO_REMEDIATION = "The engine gave no remediation for this finding."
UNATTESTED_METHOD = "attested"
# The check that runs each probe verb. The engine's probe records do not name a check, and today only TST-02 runs one
# (`session.run` in audit/rules/checks/tst.py); a test holds this table to the engine's source.
PROBE_CHECKS = {"test": "TST-02"}
# The engine's five fixed unattested items and the requirements they became (spec/traceability.md, D15 item 7).
UNATTESTED_REQUIREMENTS = {
    "index-in-use": "REQ-SH-004",
    "baseline-adequacy": "REQ-BF-004",
    "suite-trustworthiness": "REQ-SH-050",
    "doc-accuracy": "REQ-SH-020",
    "gate-honoured": "REQ-SH-026",
}
NOT_APPLICABLE_SUMMARY = "The engine did not run this check: it does not apply to the detected stack."
BLOCKED_SUMMARY = "The engine did not evaluate this check: its ruleset had blocked it."

STACK_LISTS = ("ecosystems", "package_managers", "ci_providers", "test_frameworks", "hook_managers")

# The shape the adapter reads, and no more. The report schema's own limits apply to what is carried.
_TEXT = {"type": "string"}
_ENGINE_EVIDENCE = {
    "type": "object",
    "required": ["path"],
    "properties": {"path": _TEXT, "line": {"type": ["integer", "null"]}, "note": {"type": ["string", "null"]}},
}
ENGINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "provenance",
        "stack",
        "inventory",
        "components",
        "candidate_components",
        "checks",
        "findings",
        "not_applicable",
        "unattested",
        "probes",
    ],
    "properties": {
        "provenance": {
            "type": "object",
            "required": ["tool", "version", "ruleset_hash", "target", "phase"],
            "properties": {
                "tool": _TEXT,
                "version": _TEXT,
                "ruleset_revision": _TEXT,
                "ruleset_hash": _TEXT,
                "scanned_at": _TEXT,
                "target": _TEXT,
                "git_sha": {"type": ["string", "null"]},
                "phase": {"type": "integer"},
            },
        },
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "severity", "phase", "scored", "status", "verdict", "summary"],
                "properties": {
                    "id": _TEXT,
                    "title": _TEXT,
                    "severity": {"enum": SEVERITIES},
                    "phase": {"type": "integer"},
                    "scored": {"type": "boolean"},
                    "status": _TEXT,
                    "verdict": {"enum": VERDICTS},
                    "summary": _TEXT,
                    "data": {"type": "object"},
                },
            },
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "check", "severity", "statement", "evidence"],
                "properties": {
                    "id": _TEXT,
                    "check": _TEXT,
                    "severity": {"enum": SEVERITIES},
                    "statement": _TEXT,
                    "remediation": {"type": ["string", "null"]},
                    "evidence": {"type": "array", "items": _ENGINE_EVIDENCE},
                },
            },
        },
        "summary": {"type": "object", "properties": {"phase1_score": {"type": ["number", "null"]}}},
        "stack": {
            "type": "object",
            "required": list(STACK_LISTS),
            "properties": {name: {"type": "array", "items": _TEXT} for name in (*STACK_LISTS, "notes")},
        },
        "inventory": {
            "type": "object",
            "required": ["files_inspected", "files_skipped", "truncated"],
            "properties": {
                "files_inspected": {"type": "integer"},
                "files_skipped": {"type": "integer"},
                "truncated": {"type": "boolean"},
            },
        },
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "path"],
                "properties": {
                    "name": _TEXT,
                    "path": _TEXT,
                    "declared": {"type": "boolean"},
                    "declared_by": {"type": ["string", "null"]},
                    "manifest": {"type": ["string", "null"]},
                    "agents_md": _TEXT,
                },
            },
        },
        "candidate_components": {"type": "array", "items": _TEXT},
        "not_applicable": {"type": "array", "items": _TEXT},
        "unattested": {"type": "array", "items": _TEXT},
        "probes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["verb", "command", "exit_code", "duration_s", "timed_out"],
                "properties": {
                    "verb": _TEXT,
                    "command": {"type": "array", "items": _TEXT},
                    "exit_code": {"type": ["integer", "null"]},
                    "duration_s": {"type": "number"},
                    "timed_out": {"type": "boolean"},
                    "output_tail": _TEXT,
                    "refused_reason": {"type": ["string", "null"]},
                    "redactions": {"type": "integer"},
                },
            },
        },
    },
}


# --- The report schema's limits, read from the schema and never copied ------------------------------------


@lru_cache(maxsize=1)
def report_schema() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(vr.REPORT_SCHEMA.read_text(encoding="utf-8"))
    return document


def definitions() -> dict[str, Any]:
    defs: dict[str, Any] = report_schema()["$defs"]
    return defs


def maximum(definition: str, name: str, keyword: str = "maxLength") -> int:
    """A limit of one field of a `$defs` object, such as the longest `summary` a check may have.

    A field that is a `$ref` (a path, a key) takes its limit from the definition it names.
    """
    node: dict[str, Any] = definitions()[definition]["properties"][name]
    while "$ref" in node:
        node = definitions()[node["$ref"].rsplit("/", 1)[1]]
    return int(node[keyword])


def fit_tail(text: str, limit: int) -> str:
    """`text` as it is, or its last `limit` characters with a mark at the start: the end of an output is what matters."""
    return text if len(text) <= limit else CUT_MARK + text[len(text) - (limit - 1) :]


def maximum_why() -> int:
    """The longest `why` an unattested item may have."""
    return int(report_schema()["properties"]["unattested"]["items"]["properties"]["why"]["maxLength"])


def fit(text: str, limit: int) -> str:
    """`text` as it is, or cut to `limit` characters with a mark at the end when it is longer."""
    return text if len(text) <= limit else text[: limit - 1] + CUT_MARK


# --- Where a piece of evidence points ---------------------------------------------------------------------

PLACEHOLDER = re.compile(r"\(.*\)|<[^<>]*>")
ANNOTATED = re.compile(r"(?P<path>[^\s\[\]]+) \[(?P<tag>[^\[\]]+)\]")


@dataclass(frozen=True)
class Located:
    """A path inside the repository and, when the engine's text said more than the path, what it said."""

    path: str
    note: str | None


@dataclass(frozen=True)
class NotCarried:
    """An engine path that names no file in the repository, and why it is left out.

    A placeholder is `quiet`: it holds nothing that the report could lose, so leaving it out needs no warning.
    """

    reason: str
    quiet: bool = False


def locate(text: str) -> Located | NotCarried:
    """The path and note an engine evidence path stands for, or the reason it is not carried.

    The engine's `path` is not always a path. A text in parentheses is a placeholder (`(no example file)`) and names
    nothing, and neither does a text in angle brackets, the engine's mark for the repository as a whole
    (`<repository>`). A path that is absolute or climbs out of the repository names a place outside it (the index
    store that `IDX-02` cites). A `file:key` form (`package.json:lint`) and a `file [tag]` form (`pyproject.toml [mypy/pyright]`) are
    split into the file and a note that holds the rest, without saying what the rest means, because the engine uses
    the first form for a key that is set and for a key that is not.
    """
    text = text.strip()
    if not text or PLACEHOLDER.fullmatch(text):
        return NotCarried("it is a placeholder, and names no file", quiet=True)
    reason = vr.leaves_target(text)
    if reason is not None:
        return NotCarried(f"the path {reason}, so it is outside the repository")
    annotated = ANNOTATED.fullmatch(text)
    if annotated is not None:
        return Located(annotated.group("path"), annotated.group("tag"))
    head, colon, tail = text.partition(":")
    if colon and head and tail:
        reason = vr.leaves_target(head)
        if reason is not None:
            return NotCarried(f"the path {reason}, so it is outside the repository")
        return Located(head, tail)
    return Located(text, None)


def safe_key(engine_id: str) -> str:
    """An engine finding id with each whitespace character as `%` and its UTF-8 bytes in hexadecimal.

    A finding's key may not hold whitespace (the report schema), and the engine's id holds a file's path.
    """
    return "".join(
        "".join(f"%{byte:02X}" for byte in char.encode("utf-8")) if char.isspace() else char for char in engine_id
    )


# --- The conversion -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Conversion:
    """What an engine report becomes: the engine's own record, the target it says it scanned, and the checks.

    A finding has no `id` and no disposition yet: the builder assigns them, as `add-finding` does.
    """

    engine: dict[str, Any]
    target_path: str
    git_sha: str | None
    checks: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    unattested: list[dict[str, Any]]
    stack: dict[str, Any]
    components: list[dict[str, Any]]
    inventory: dict[str, Any]
    engine_score: float | None
    warnings: list[str]
    evidence_not_carried: int
    probes_carried: int


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


def engine_record(provenance: Mapping[str, Any]) -> dict[str, Any]:
    """`provenance.engine`: the engine that produced the automated verdicts, in the order of the schema."""
    record: dict[str, Any] = {"name": provenance["tool"], "version": provenance["version"]}
    if "ruleset_revision" in provenance:
        record["ruleset_revision"] = provenance["ruleset_revision"]
    record["ruleset_hash"] = provenance["ruleset_hash"]
    if "scanned_at" in provenance:
        record["scanned_at"] = provenance["scanned_at"]
    return record


class Converter:
    """One conversion: the engine's tool, the catalogue, the finding keys already taken, and what has gone wrong."""

    def __init__(
        self,
        engine: Mapping[str, Any],
        catalogue: Mapping[str, Any],
        taken_keys: Collection[str],
        meanings: Mapping[str, str],
    ) -> None:
        self.engine = engine
        self.meanings = meanings
        self.tool = engine["provenance"]["tool"]
        self.tool_version = engine["provenance"]["version"]
        self.entries = {entry["id"]: entry for entry in catalogue["checks"]}
        self.attested = {check["id"] for check in engine["checks"] if check["verdict"] == "ATTEST"}
        self.check_ids = {check["id"] for check in engine["checks"]} - self.attested
        self.taken = set(taken_keys)
        self.warnings: list[str] = []
        self.problems: list[str] = []
        self.not_carried = 0
        self.probes_carried = 0

    def cut(self, text: str, limit: int, where: str, what: str) -> str:
        if len(text) > limit:
            self.warnings.append(
                f"{where}: the {what} is {len(text)} characters and the report allows {limit}, so it was cut"
            )
        return fit(text, limit)

    def limited(self, items: Sequence[Any], limit: int, where: str, what: str) -> list[Any]:
        """The first `limit` of `items`, with a warning for the rest."""
        if len(items) > limit:
            self.warnings.append(
                f"{where}: {len(items)} {what}, and the report allows {limit}, so the rest are left out"
            )
        return list(items[:limit])

    def capped(self, items: list[dict[str, Any]], limit: int, where: str) -> list[dict[str, Any]]:
        """The first `limit` evidence items, with a warning for the rest."""
        self.not_carried += max(len(items) - limit, 0)
        return list(self.limited(items, limit, where, "evidence items"))

    def evidence_item(self, raw: Mapping[str, Any], where: str) -> dict[str, Any] | None:
        """One of an engine finding's evidence items as the report's `file` evidence, or None when it is not carried."""
        found = locate(raw["path"])
        if isinstance(found, Located) and len(found.path) > maximum("evidence", "path"):
            found = NotCarried(f"the path is {len(found.path)} characters long")
        if isinstance(found, NotCarried):
            if not found.quiet:
                self.warnings.append(f"{where}: the evidence path {raw['path']!r} is not carried: {found.reason}")
                self.not_carried += 1
            return None
        note = ": ".join(part for part in (found.note, raw.get("note")) if part)
        item: dict[str, Any] = {
            "kind": "file",
            "captured_by": "tool",
            "tool": self.tool,
            "tool_version": self.tool_version,
            "path": found.path,
        }
        line = raw.get("line")
        if line is not None and line > 0:
            item["lines"] = str(line)
        if note:
            item["note"] = self.cut(note, maximum("evidence", "note"), where, "note")
        return item

    def unused_key(self, engine_id: str) -> str:
        """The finding's key: the engine's id, with `:2`, `:3` and so on after it when an earlier finding has it.

        The engine's id is the check and a path, and is not always unique (`AGT-08` can raise two findings with no
        path), so the later finding takes the next number. A path too long for a key is cut, leaving room for the number.
        """
        base = safe_key(engine_id)[: maximum("finding", "key") - KEY_ROOM]
        key, number = base, 1
        while key in self.taken:
            number += 1
            key = f"{base}:{number}"
        self.taken.add(key)
        return key

    def finding(self, number: int, raw: Mapping[str, Any]) -> dict[str, Any] | None:
        engine_id, check = raw["id"], raw["check"]
        where = f"/findings/{number}"
        if check in self.attested:
            self.problems.append(
                f"engine report: {where}/check: {check} has the verdict ATTEST, which is no verdict, so it holds no findings"
            )
            return None
        if check not in self.check_ids:
            self.problems.append(f"engine report: {where}/check: {check} is not a check in this report")
            return None
        if not engine_id.startswith(check):
            self.problems.append(f"engine report: {where}/id: {engine_id} does not start with its check, {check}")
            return None
        items = (self.evidence_item(item, engine_id) for item in raw["evidence"])
        evidence = self.capped(
            [item for item in items if item is not None], maximum("finding", "evidence", "maxItems"), engine_id
        )
        remediation = raw.get("remediation") or NO_REMEDIATION
        return {
            "key": self.unused_key(engine_id),
            "check": check,
            "severity": raw["severity"],
            "statement": self.cut(raw["statement"], maximum("finding", "statement"), engine_id, "statement"),
            "evidence": evidence,
            "searches": [],
            "remediation": {
                "summary": self.cut(remediation, maximum("remediation", "summary"), engine_id, "remediation")
            },
        }

    def command_evidence(self, probe: Mapping[str, Any]) -> dict[str, Any] | None:
        """A probe the engine ran, as `command` evidence. The engine redacted its output when it captured it."""
        where = f"probe {probe['verb']}"
        command = shlex.join(probe["command"])
        if not command:
            self.warnings.append(f"{where}: the engine gave no command, so the probe is not carried")
            return None
        item: dict[str, Any] = {
            "kind": "command",
            "captured_by": "tool",
            "tool": self.tool,
            "tool_version": self.tool_version,
            "command": self.cut(command, maximum("evidence", "command"), where, "command"),
            "exit_code": probe["exit_code"],
        }
        tail = probe.get("output_tail")
        if tail:
            limit = maximum("evidence", "output_tail")
            if len(tail) > limit:
                self.warnings.append(
                    f"{where}: the output is {len(tail)} characters and the report allows {limit}, so its start was cut"
                )
            item["output_tail"] = fit_tail(tail, limit)
        item["timed_out"] = probe["timed_out"]
        item["duration_s"] = probe["duration_s"]
        if "redactions" in probe:
            item["redactions"] = probe["redactions"]
        return item

    def probe_evidence(self) -> dict[str, list[dict[str, Any]]]:
        """The probes the engine ran, as command evidence for the check that ran each.

        A probe the engine refused ran nothing, and the check's own summary says why, so it is not carried.
        """
        by_check: dict[str, list[dict[str, Any]]] = {}
        for probe in self.engine["probes"]:
            if probe.get("refused_reason"):
                continue
            check_id = PROBE_CHECKS.get(probe["verb"])
            if check_id is None:
                self.warnings.append(f"probe {probe['verb']}: no check is known to run it, so it is not carried")
                continue
            item = self.command_evidence(probe)
            if item is not None:
                by_check.setdefault(check_id, []).append(item)
        return by_check

    def check(
        self,
        number: int,
        raw: Mapping[str, Any],
        findings: Sequence[Mapping[str, Any]],
        commands: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any] | None:
        """An engine check as an automated check. Its evidence is its findings' evidence, gathered, then its probes."""
        check_id, where = raw["id"], f"/checks/{number}"
        entry = self.entries.get(check_id)
        if entry is None:
            self.problems.append(f"engine report: {where}/id: {check_id} is not a check in catalogue.json")
            return None
        if entry["method"] != "automated":
            self.problems.append(
                f"engine report: {where}/id: {check_id} is a check that only an agent can judge, so the engine cannot report it"
            )
            return None
        data = raw.get("data")
        if data and "kind" not in data:
            self.problems.append(f"engine report: {where}/data: the payload of {check_id} has no kind")
            return None
        gathered = [dict(item) for finding in findings for item in finding["evidence"]]
        blocked = raw["status"] == "blocked"
        if blocked:
            self.warnings.append(
                f"{check_id}: the engine's ruleset did not evaluate it, so it is recorded as UNKNOWN and is scored "
                "as the catalogue scores it"
            )
        check: dict[str, Any] = {
            "id": check_id,
            "title": self.cut(raw["title"], maximum("check", "title"), check_id, "title"),
            "phase": raw["phase"],
            "severity": raw["severity"],
            "scored": entry["scored"] if blocked else raw["scored"],
            "method": "automated",
            "verdict": raw["verdict"],
            "engine_verdict": raw["verdict"],
            "summary": BLOCKED_SUMMARY
            if blocked
            else self.cut(raw["summary"], maximum("check", "summary"), check_id, "summary"),
            "evidence": self.capped(gathered, maximum("check", "evidence", "maxItems") - len(commands), check_id)
            + [dict(item) for item in commands],
            "searches": [],
        }
        if data:
            check["data"] = copy.deepcopy(data)
        return check

    def not_applicable(self, number: int, check_id: str) -> dict[str, Any] | None:
        """A check the engine left out because it does not apply: the catalogue's entry, with no verdict of its own."""
        entry = self.entries.get(check_id)
        if entry is None:
            self.problems.append(
                f"engine report: /not_applicable/{number}: {check_id} is not a check in catalogue.json"
            )
            return None
        if entry["method"] != "automated":
            self.problems.append(
                f"engine report: /not_applicable/{number}: {check_id} is a check that only an agent can judge, so the engine cannot report it"
            )
            return None
        return {
            "id": check_id,
            "title": entry["title"],
            "phase": entry["phase"],
            "severity": entry["severity"],
            "scored": entry["scored"],
            "method": "automated",
            "verdict": "NOT_APPLICABLE",
            "engine_verdict": "NOT_APPLICABLE",
            "summary": NOT_APPLICABLE_SUMMARY,
            "evidence": [],
            "searches": [],
        }

    def inventory(self) -> dict[str, Any]:
        """The engine's file counts, in the report's order. A scan the engine cut short is said."""
        raw = self.engine["inventory"]
        if raw["truncated"]:
            self.warnings.append("the engine's scan was cut short, so what it did not reach is not in the report")
        return {name: raw[name] for name in ("files_inspected", "files_skipped", "truncated")}

    def stack(self) -> dict[str, Any]:
        """What the scan detected, under the engine's names. A name or note over the report's limit is cut."""
        raw = self.engine["stack"]
        name_limit = report_schema()["$defs"]["nameList"]["items"]["maxLength"]
        stack: dict[str, Any] = {}
        for name in STACK_LISTS:
            listed = self.limited(raw[name], report_schema()["$defs"]["nameList"]["maxItems"], f"stack {name}", "names")
            stack[name] = [self.cut(item, name_limit, f"stack {name}", "name") for item in listed]
        notes = raw.get("notes")
        if notes:
            note_schema = report_schema()["properties"]["stack"]["properties"]["notes"]
            listed = self.limited(notes, note_schema["maxItems"], "stack notes", "notes")
            stack["notes"] = [
                self.cut(item, note_schema["items"]["maxLength"], "stack notes", "note") for item in listed
            ]
        return stack

    def components(self) -> list[dict[str, Any]]:
        """The declared components, then the candidates: a path that looks like one and that nothing declares."""
        schema = report_schema()["properties"]["components"]
        item = schema["items"]["properties"]
        made: list[dict[str, Any]] = []
        for raw in self.engine["components"]:
            component: dict[str, Any] = {
                "name": self.cut(raw["name"], item["name"]["maxLength"], raw["path"], "component name"),
                "path": raw["path"],
                "declared": raw.get("declared", True),
            }
            for field_name in ("declared_by", "manifest", "agents_md"):
                if field_name in raw:
                    limit = item[field_name].get("maxLength")
                    value = raw[field_name]
                    component[field_name] = (
                        value if limit is None or value is None else self.cut(value, limit, raw["path"], field_name)
                    )
            made.append(component)
        for path in self.engine["candidate_components"]:
            made.append({"name": path, "path": path, "declared": False})
        return self.limited(made, schema["maxItems"], "components", "components")

    def attest(self, number: int, raw: Mapping[str, Any]) -> list[dict[str, Any]]:
        """The requirements of a check the engine marks ATTEST, as unattested items. Such a check has no verdict."""
        check_id = raw["id"]
        entry = self.entries.get(check_id)
        if entry is None or entry["method"] != "automated":
            kind = "not a check in catalogue.json" if entry is None else "a check that only an agent can judge"
            self.problems.append(f"engine report: /checks/{number}/id: {check_id} is {kind}")
            return []
        why = self.cut(raw["summary"] or raw["title"], maximum_why(), check_id, "summary")
        return [
            {"requirement": requirement, "method": UNATTESTED_METHOD, "property": check_id.lower(), "why": why}
            for requirement in entry["req_ids"]
        ]

    def unattested_items(self) -> list[dict[str, Any]]:
        """The engine's fixed unattested items as the requirements they stand for. One it has no requirement for is said."""
        items: list[dict[str, Any]] = []
        for name in self.engine["unattested"]:
            requirement = UNATTESTED_REQUIREMENTS.get(name)
            if requirement is None:
                self.warnings.append(
                    f"the engine lists the unattested item {name!r}, which maps to no requirement, so it is not carried"
                )
                continue
            why = self.meanings.get(name) or f"The engine cannot settle {name} by scanning."
            items.append(
                {
                    "requirement": requirement,
                    "method": UNATTESTED_METHOD,
                    "property": name,
                    "why": self.cut(why, maximum_why(), name, "description"),
                }
            )
        return items

    def run(self) -> Conversion:
        raw_checks: list[Mapping[str, Any]] = self.engine["checks"]
        listed = [raw["id"] for raw in raw_checks] + list(self.engine["not_applicable"])
        for check_id in sorted({i for i in listed if listed.count(i) > 1}):
            self.problems.append(
                f"engine report: {check_id} appears more than once among the checks and not_applicable"
            )
        findings = []
        for number, raw_finding in enumerate(self.engine["findings"]):
            converted = self.finding(number, raw_finding)
            if converted is not None:
                findings.append(converted)
        by_check: dict[str, list[dict[str, Any]]] = {}
        for converted in findings:
            by_check.setdefault(converted["check"], []).append(converted)
        commands = self.probe_evidence()
        checks = []
        attested: list[dict[str, Any]] = []
        for number, raw_check in enumerate(raw_checks):
            if raw_check["verdict"] == "ATTEST":
                attested.extend(self.attest(number, raw_check))
                continue
            made = self.check(number, raw_check, by_check.get(raw_check["id"], []), commands.get(raw_check["id"], ()))
            if made is not None:
                checks.append(made)
                self.probes_carried += len(commands.get(raw_check["id"], ()))
        for number, check_id in enumerate(self.engine["not_applicable"]):
            skipped = self.not_applicable(number, check_id)
            if skipped is not None:
                checks.append(skipped)
        for check_id in sorted(set(commands) - {made["id"] for made in checks if made["verdict"] != "NOT_APPLICABLE"}):
            self.warnings.append(f"probe: {check_id} ran it, and the report holds no such check, so it is not carried")
        if self.problems:
            count = len(self.problems)
            refuse(
                f"the engine report cannot be imported: {count} problem{'' if count == 1 else 's'}",
                self.problems[: vr.MAX_SCHEMA_ERRORS],
            )
        provenance = self.engine["provenance"]
        return Conversion(
            engine=engine_record(provenance),
            target_path=provenance["target"],
            git_sha=provenance.get("git_sha"),
            checks=checks,
            findings=findings,
            unattested=self.unattested_items() + attested,
            stack=self.stack(),
            components=self.components(),
            inventory=self.inventory(),
            engine_score=(self.engine.get("summary") or {}).get("phase1_score"),
            warnings=self.warnings,
            evidence_not_carried=self.not_carried,
            probes_carried=self.probes_carried,
        )


def convert(
    engine: Any,
    *,
    catalogue: Mapping[str, Any],
    taken_keys: Collection[str] = (),
    meanings: Mapping[str, str] | None = None,
) -> Conversion:
    """The parts of a draft that `engine` stands for. Raises `ValidationFailed` for a report it cannot read.

    `taken_keys` are the keys of the findings the draft already holds, so that an imported finding never repeats one.
    `meanings` is the engine's own wording for each unattested item, which the caller takes from the engine.
    """
    check_engine_report(engine)
    return Converter(engine, catalogue, taken_keys, meanings or {}).run()
