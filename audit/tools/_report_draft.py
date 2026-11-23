# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The shared helpers of `report.py`: the draft's text, the target's provenance, the intake, a new draft, the
schema, the lock, the change cycle and the fragments the agent supplies. `report.py` re-exports every name.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import _common
import _jsonschema_subset as subset
import _summary
import validate_report as vr


SCHEMA_VERSION = "0.2"
DEFAULT_PROBE_TIMEOUT_S = 120
MAX_FRAGMENT_CHARS = 1024 * 1024

INTAKE_SCHEMA = vr.RECIPES / "schema" / "audit-intake.schema.json"
GIT_SHA = re.compile(r"^[0-9a-f]{40}\Z")
#: A report records commits in this many hex digits, never the full 40. A full commit id is exactly the shape that
#: secret scanners (gitleaks' default rules) read as an access token, so a committed report would fail the scan.
SHORT_SHA_CHARS = 12


def dumps(document: Mapping[str, Any]) -> str:
    """A report as text: two-space indent, the order of the keys kept, non-ASCII characters kept, one final newline."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


# --- The target's provenance --------------------------------------------------------------------------


git_toplevel = vr.git_toplevel


def git_facts(target: Path) -> tuple[dict[str, Any], list[str]]:
    """The target's commit, branch and dirty flag, and warnings. Every git call here only reads.

    A value that cannot be known is None, which the schema allows, and a target that is not the root of its
    repository records nothing, because a commit id says nothing about a subfolder.
    """
    unknown: dict[str, Any] = {"git_sha": None, "branch": None, "dirty": None}
    if shutil.which("git") is None:
        return unknown, ["git is not installed, so the target's commit, branch and state are not recorded"]
    top = git_toplevel(target)
    if top is None:
        return unknown, []
    if top != target:
        return unknown, [
            f"the target is inside the repository at {top}, not at its root, so its commit is not recorded"
        ]
    warnings: list[str] = []
    sha: str | None = None
    head = vr.git_output(target, ["rev-parse", "HEAD"])
    if head is not None and head.returncode == 0:
        found = head.stdout.strip()
        if GIT_SHA.match(found):
            sha = found[:SHORT_SHA_CHARS]
        else:
            warnings.append("the target's commit id is not 40 hexadecimal digits, so it is not recorded")
    branch: str | None = None
    named = vr.git_output(target, ["symbolic-ref", "--short", "-q", "HEAD"])
    if named is not None and named.returncode == 0 and named.stdout.strip():
        branch = named.stdout.strip()
    dirty: bool | None = None
    state = vr.git_output(target, ["status", "--porcelain"])
    if state is not None and state.returncode == 0:
        dirty = bool(state.stdout.strip())
    else:
        warnings.append("git could not say whether the target's working tree is dirty")
    return {"git_sha": sha, "branch": branch, "dirty": dirty}, warnings


def same_commit(recorded: str, scanned: str) -> bool:
    """True when two commit ids name one commit: the report keeps a short id, the engine reports the full one."""
    return scanned.startswith(recorded) or recorded.startswith(scanned)


# --- The intake ---------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def intake_validator() -> subset.SubsetValidator:
    return subset.SubsetValidator(json.loads(INTAKE_SCHEMA.read_text(encoding="utf-8")))


def intake_rule_errors(intake: Mapping[str, Any]) -> list[str]:
    """The intake rules at the end of "Rules beyond the schema" that need no file system.

    `target_path` being a directory and `output_dir` being outside it are checked where the paths are resolved.
    """
    errors: list[str] = []
    eval_mode = intake.get("eval_mode", False)
    policy = intake["confirmation_policy"]
    if policy == "accept-all" and not eval_mode:
        errors.append("intake rule: /confirmation_policy: 'accept-all' is allowed only with eval_mode set to true")
    if eval_mode and policy == "interactive":
        errors.append("intake rule: /confirmation_policy: an eval-mode run cannot be 'interactive'")
    index = intake["index"]
    if index["kind"] != "none" and "name" not in index:
        errors.append(f"intake rule: /index/name: the index kind is {index['kind']!r}, so the index needs a name")
    return errors


def read_intake(path: Path) -> dict[str, Any]:
    """The intake file, parsed and checked against its schema and its rules. Raises `ValidationFailed`."""
    intake = vr.read_report(path, "intake")
    found = intake_validator().validate(intake, limit=vr.MAX_SCHEMA_ERRORS)
    if found:
        count = len(found)
        raise _common.ValidationFailed(
            f"the intake is not valid: {count} error{'' if count == 1 else 's'} in the schema stage",
            errors=[f"schema: {violation}" for violation in found],
        )
    problems = intake_rule_errors(intake)
    if problems:
        count = len(problems)
        raise _common.ValidationFailed(
            f"the intake is not valid: {count} rule error{'' if count == 1 else 's'}", errors=problems
        )
    checked: dict[str, Any] = intake
    return checked


# --- Starting a draft ---------------------------------------------------------------------------------


def new_draft(
    intake: Mapping[str, Any],
    *,
    label: str,
    target: Path,
    git: Mapping[str, Any],
    catalogue_version: str,
    framework: Mapping[str, Any],
    started_at: str,
) -> dict[str, Any]:
    """An empty draft: provenance and run context from the intake, no checks, no findings.

    Keys are in the order of the schema, so every draft reads the same way. `allow_install` and `output_dir` are
    instructions to the run and not results, so they stay in the intake.
    """
    index = {name: value for name, value in intake["index"].items() if name != "allow_install"}
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "draft",
        "provenance": {
            "framework": dict(framework),
            "catalogue_version": catalogue_version,
            "agent": {"harness": intake["harness"], "model": intake["model"]},
            "target": {
                "label": label,
                "path": str(target),
                "git_sha": git["git_sha"],
                "branch": git["branch"],
                "dirty": git["dirty"],
            },
            "started_at": started_at,
        },
        "run_context": {
            "eval_mode": intake.get("eval_mode", False),
            "confirmation_policy": intake["confirmation_policy"],
            "provider_exposure_acknowledged": True,
            "index": index,
            "probes": intake.get("probes", {"allowed": [], "timeout_s": DEFAULT_PROBE_TIMEOUT_S}),
            "excluded": list(intake.get("excluded", [])),
            "known_components": list(intake.get("known_components", [])),
        },
        "stack": {
            "ecosystems": [],
            "package_managers": [],
            "ci_providers": [],
            "test_frameworks": [],
            "hook_managers": [],
        },
        "components": [],
        "checks": [],
        "findings": [],
        "summary": {},
        "unattested": [],
        "coverage": {"scopes_examined": [], "scopes_skipped": []},
    }
    document["summary"] = _summary.compute_summary(document)
    return document


# --- The draft: load, change, validate, write ----------------------------------------------------------


@lru_cache(maxsize=1)
def report_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(vr.REPORT_SCHEMA.read_text(encoding="utf-8"))
    return schema


def schema_order(definition: str) -> list[str]:
    """The names of a `$defs` object's properties in the schema's order, which is the order every report uses."""
    return list(report_schema()["$defs"][definition]["properties"])


def in_schema_order(item: Mapping[str, Any], definition: str) -> dict[str, Any]:
    order = schema_order(definition)
    return {name: item[name] for name in order if name in item}


def expected_checks() -> list[Mapping[str, Any]]:
    """The checks a complete phase-1 audit records: every phase-1 check of the catalogue."""
    return [check for check in vr.load_catalogue()["checks"] if check["phase"] == 1]


@dataclass
class Change:
    """What a change made: the data to report, and the pointers of the items it touched (for cited-file warnings)."""

    data: dict[str, Any]
    touched: list[str] = field(default_factory=list)


def read_valid_report(path: Path, *, when: str) -> dict[str, Any]:
    """The report at `path`, draft or final, which must be valid. `when` says what the caller was about to do."""
    document = vr.read_report(path, "draft")
    outcome = vr.validate_document(document)
    vr.refuse_unknown_schema(outcome)
    if outcome.errors:
        count = len(outcome.errors)
        raise _common.ValidationFailed(
            f"the draft is not valid {when}: {count} error{'' if count == 1 else 's'} in the {outcome.stage} stage",
            errors=outcome.errors,
        )
    checked: dict[str, Any] = document
    return checked


def read_draft(path: Path) -> dict[str, Any]:
    """The draft at `path`, which must be a valid report with the status `draft`."""
    document = read_valid_report(path, when="before the change")
    if document["status"] != "draft":
        raise _common.UsageError(f"{path.name} is a final report; only a draft can be changed")
    return document


def target_directory(document: Mapping[str, Any]) -> Path | None:
    """The target the draft names, when it is there. The draft's own folder must not be inside it."""
    named = Path(document["provenance"]["target"]["path"])
    return named.resolve() if named.is_dir() else None


def refuse_inside_target(target: Path | None, path: Path) -> None:
    """A draft that sits inside its own target is refused: the tools never write inside the repository they audit."""
    if target is not None and _common.is_within(target, path.resolve().parent):
        raise _common.PathNotAllowed(f"refusing to write inside the target: {path.resolve().parent}")


# --- Fragments: what the agent supplies ----------------------------------------------------------------


def read_fragment(source: str, what: str) -> Any:
    """The JSON fragment in the file `source`, or on stdin when `source` is `-`."""
    if source == "-":
        text = sys.stdin.read(MAX_FRAGMENT_CHARS + 1)
        if len(text) > MAX_FRAGMENT_CHARS:
            raise _common.UsageError(f"the {what} on stdin is over {MAX_FRAGMENT_CHARS} characters")
        return vr.parse_report(text, what)
    return vr.read_report(Path(source).expanduser(), what)


def fragment_validator(
    fields: Sequence[str], required: Sequence[str], definition: str, extra: Mapping[str, Any] | None = None
) -> subset.SubsetValidator:
    """A validator for a fragment, made from the report schema's own definition of the same item.

    A fragment holds some of the fields of a check or a finding, and none of the ones the tool computes, so
    the schema refuses those as unknown fields. Each field's rule is the report schema's, never a copy of it.
    `extra` adds fields that the report does not have, such as the scope that becomes part of a finding's key.
    """
    schema = report_schema()
    properties = schema["$defs"][definition]["properties"]
    chosen = {field_name: properties[field_name] for field_name in fields}
    chosen.update(extra or {})
    return subset.SubsetValidator(
        {
            "$defs": schema["$defs"],
            "type": "object",
            "required": list(required),
            "additionalProperties": False,
            "properties": chosen,
        }
    )


def fragment_errors(validator: subset.SubsetValidator, fragment: Any) -> list[str]:
    return [f"fragment: {violation}" for violation in validator.validate(fragment, limit=vr.MAX_SCHEMA_ERRORS)]


def agent_evidence(fragment: dict[str, Any]) -> list[str]:
    """Make the evidence in a fragment the agent's, and say what in it claims otherwise.

    An agent writes `captured_by: agent` or leaves it out. Evidence that a tool captured is written by a tool, so a
    fragment cannot carry it: the report must never show a deterministic source for something a model typed.
    """
    problems: list[str] = []
    items = fragment.get("evidence")
    if not isinstance(items, list):
        return problems
    for number, item in enumerate(items):
        if not isinstance(item, dict) or "kind" not in item:
            continue
        claimed = item.get("captured_by", "agent")
        if claimed != "agent" or "tool" in item or "tool_version" in item:
            problems.append(
                f"fragment: /evidence/{number}: the agent cannot record tool-captured evidence; "
                "leave out captured_by, tool and tool_version"
            )
            continue
        items[number] = {
            "kind": item["kind"],
            "captured_by": "agent",
            **{k: v for k, v in item.items() if k not in ("kind", "captured_by")},
        }
    return problems


def checked_fragment(source: str, what: str, validator: subset.SubsetValidator) -> dict[str, Any]:
    """The fragment from `source`, with its evidence made the agent's, or `ValidationFailed` with every problem."""
    fragment = read_fragment(source, what)
    problems = (agent_evidence(fragment) if isinstance(fragment, dict) else []) + fragment_errors(validator, fragment)
    if problems:
        count = len(problems)
        raise _common.ValidationFailed(
            f"the {what} is not valid: {count} error{'' if count == 1 else 's'}", errors=problems
        )
    checked: dict[str, Any] = fragment
    return checked
