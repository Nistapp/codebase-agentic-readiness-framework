# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Build the audit report. This tool is the only writer of the draft: the agent never edits the JSON by hand.

    report.py init <intake>
    report.py add-check <draft> --from FILE|-
    report.py add-finding <draft> --from FILE|-
    report.py set-disposition <draft> --via VIA (--finding ID --disposition D [--note TEXT] | --from FILE|-)
    report.py status <draft>

``init`` reads the intake file, captures the target's provenance (commit, branch, whether the working tree is
dirty), and creates ``<label>.audit-draft.<stamp>.json`` in the intake's ``output_dir``. It never replaces a file: a
second run on the same repository starts a second draft, and the earlier one stays as it was.

Every other subcommand changes the draft in place, and only its own draft. A change is one read-modify-write under a
lock on the output folder: the draft is read and validated, the change is made on a copy, the summary is recomputed,
the copy is validated, and only then is it written, atomically. A change that would leave the draft invalid writes
nothing and exits 2 with the errors. The agent supplies a fragment (JSON, from a file or from stdin), and the tool
fills in everything it can compute: catalogue metadata, ids, keys and the summary.

The shape of the report is ``schema/audit-report.schema.json`` and the rules a schema cannot express are in
``schema/SCHEMA.md``. Every file this tool writes is validated first with ``validate_report.validate_document``, and
the readiness ``summary`` is computed by ``_summary.py``, never taken from a caller.

Failure behaviour: a bad argument, a missing file or an output directory inside the target is exit 1. An intake that
fails its schema or its rules is exit 2, with every error in ``data.errors``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import posixpath
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import _common
import _jsonschema_subset as subset
import _summary
import validate_report as vr

INFO = _common.ToolInfo(
    name="report",
    summary="Build the audit report: the only writer of the draft, and every write is validated.",
    synopsis=(
        "report.py init <intake>",
        "report.py add-check <draft> --from FILE|-",
        "report.py add-finding <draft> --from FILE|-",
        "report.py set-disposition <draft> --via VIA (--finding ID --disposition D [--note TEXT] | --from FILE|-)",
        "report.py status <draft>",
    ),
    writes=(
        "init: a new draft, <label>.audit-draft.<stamp>.json, in the intake's output_dir, which must be outside the "
        "target; a name that is taken is never replaced. add-check, add-finding and set-disposition: that draft, in "
        "place and atomically, and no other file. status: nothing."
    ),
)

RECIPE_NAME = "brownfield-audit"
RECIPE_VERSION = "0.1.0"
SCHEMA_VERSION = "0.1"
DRAFT_KIND = "audit-draft"
DEFAULT_PROBE_TIMEOUT_S = 120
MAX_FRAGMENT_CHARS = 1024 * 1024
LOCK_WAIT_S = 30
STATUS_LINE_BUDGET = 40
PENDING_SHOWN = 8

INTAKE_SCHEMA = vr.RECIPES / "schema" / "audit-intake.schema.json"
GIT_SHA = re.compile(r"^[0-9a-f]{40}\Z")


# --- Time and JSON ------------------------------------------------------------------------------------


def utc_now() -> datetime:
    """The current UTC time to the second. Tests replace this."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def dumps(document: Mapping[str, Any]) -> str:
    """A report as text: two-space indent, the order of the keys kept, non-ASCII characters kept, one final newline."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


# --- The target's provenance --------------------------------------------------------------------------


def git_toplevel(path: Path) -> Path | None:
    """The root of the git working tree that holds `path`, or None when it is in none or git cannot say."""
    done = vr.git_output(path, ["rev-parse", "--show-toplevel"])
    if done is None or done.returncode != 0 or not done.stdout.strip():
        return None
    return Path(done.stdout.strip()).resolve()


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
            sha = found
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


def framework_revision() -> str | None:
    """The commit of the framework repository these tools run from, or None when they are not in a checkout of it."""
    root = vr.RECIPES.parent.resolve()
    if shutil.which("git") is None or git_toplevel(root) != root:
        return None
    head = vr.git_output(root, ["rev-parse", "HEAD"])
    if head is None or head.returncode != 0 or not GIT_SHA.match(head.stdout.strip()):
        return None
    return head.stdout.strip()


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
    framework: str | None,
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
            "recipe": {"name": RECIPE_NAME, "version": RECIPE_VERSION},
            "framework_revision": framework,
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


def run_init(args: argparse.Namespace) -> _common.Result:
    intake = read_intake(Path(args.intake).expanduser())
    target = _common.resolve_target(intake["target_path"])
    directory = _common.output_directory(intake["output_dir"], target=target)
    label = _common.repo_label(target, intake.get("repo_label"))
    moment = utc_now()
    git, warnings = git_facts(target)
    document = new_draft(
        intake,
        label=label,
        target=target,
        git=git,
        catalogue_version=str(vr.load_catalogue()["catalogue_version"]),
        framework=framework_revision(),
        started_at=moment.isoformat(),
    )
    outcome = vr.validate_document(document)
    if outcome.errors:
        raise _common.ValidationFailed("the new draft would not be valid", errors=outcome.errors)
    path = _common.create_new(directory, label, DRAFT_KIND, _common.utc_stamp(moment), "json", dumps(document))
    data = {
        "draft": str(path),
        "label": label,
        "target": {"path": str(target), **git},
        "status": document["status"],
    }
    return _common.Result(data=data, summary=f"report: started {path.name} for {label}", warnings=warnings)


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


def lock_directory(descriptor: int, directory: Path) -> None:
    """Take an exclusive lock on an open folder, waiting up to `LOCK_WAIT_S`. A platform without `flock` takes none."""
    try:
        import fcntl
    except ImportError:
        return
    deadline = time.monotonic() + LOCK_WAIT_S
    while True:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise _common.UsageError(
                    f"another report command has held the lock on {directory} for {LOCK_WAIT_S} seconds",
                    hint="run the commands one at a time, and run this one again",
                ) from None
            time.sleep(0.05)


@contextlib.contextmanager
def write_lock(directory: Path) -> Iterator[None]:
    """Make the commands that change drafts in `directory` take turns.

    Two commands that run at once would each read the draft, each add their part, and the second write would lose
    the first's part. The lock is on the folder, which no command replaces, and the system drops it when the
    process ends, so a crash leaves nothing behind that would stop a resume.
    """
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        lock_directory(descriptor, directory)
        yield
    finally:
        os.close(descriptor)


@dataclass
class Change:
    """What a change made: the data to report, and the pointers of the items it touched (for cited-file warnings)."""

    data: dict[str, Any]
    touched: list[str] = field(default_factory=list)


def read_valid_report(path: Path, *, when: str) -> dict[str, Any]:
    """The report at `path`, draft or final, which must be valid. `when` says what the caller was about to do."""
    document = vr.read_report(path, "draft")
    outcome = vr.validate_document(document)
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


def update_draft(argument: str, change: Callable[[dict[str, Any]], Change]) -> _common.Result:
    """Apply `change` to the draft named by `argument`: validate, then write atomically, or write nothing."""
    path = Path(argument).expanduser()
    directory = path.parent.resolve()
    if not directory.is_dir():
        raise _common.UsageError(f"draft not found: {path}")
    with write_lock(directory):
        working = read_draft(path)
        target = target_directory(working)
        if target is not None and _common.is_within(target, path.resolve().parent):
            raise _common.PathNotAllowed(f"refusing to write inside the target: {path.resolve().parent}")
        made = change(working)
        working["summary"] = _summary.compute_summary(working)
        outcome = vr.validate_document(working, target=target)
        if outcome.errors:
            count = len(outcome.errors)
            raise _common.ValidationFailed(
                f"the change would leave the draft invalid, so nothing was written: {count} error{'' if count == 1 else 's'}",
                errors=outcome.errors,
            )
        try:
            _common.atomic_write_text(path, dumps(working))
        except OSError as exc:
            raise _common.UsageError(f"cannot write the draft {path}: {exc.strerror or exc}") from None
    warnings = [w for w in outcome.warnings if any(w.startswith(prefix) for prefix in made.touched)]
    kept, omitted = _common.bound_items(warnings)
    data = {"draft": str(path), **made.data}
    if omitted:
        data["warnings_omitted"] = omitted
    return _common.Result(data=data, summary="", warnings=kept, truncated=bool(omitted))


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


# --- add-check -------------------------------------------------------------------------------------------

CHECK_FIELDS = ("id", "verdict", "summary", "confidence", "evidence", "searches", "override_reason")
CHECK_REQUIRED = ("id", "verdict", "summary")


def check_validator() -> subset.SubsetValidator:
    return fragment_validator(CHECK_FIELDS, CHECK_REQUIRED, "check")


def recorded_checks(document: Mapping[str, Any]) -> dict[str, int]:
    return {check["id"]: index for index, check in enumerate(document["checks"])}


def check_counts(document: Mapping[str, Any]) -> dict[str, int]:
    wanted = {check["id"] for check in expected_checks()}
    return {"checks_recorded": len(wanted & set(recorded_checks(document))), "checks_expected": len(wanted)}


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


def run_add_check(args: argparse.Namespace) -> _common.Result:
    fragment = checked_fragment(args.source, "check fragment", check_validator())
    counts: dict[str, int] = {}

    def change(document: dict[str, Any]) -> Change:
        made = apply_check(document, fragment)
        counts.update(check_counts(document))
        return made

    result = update_draft(args.draft, change)
    result.data.update(counts)
    result.summary = f"report: {result.data['check']} {result.data['action']} as {result.data['verdict']}"
    return result


# --- add-finding -----------------------------------------------------------------------------------------

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
        "disposition": "pending",
    }
    if document["run_context"]["confirmation_policy"] == "accept-all":
        finding.update(disposition="confirmed", confirmed_via="policy")
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


def run_add_finding(args: argparse.Namespace) -> _common.Result:
    fragment = checked_fragment(args.source, "finding fragment", finding_validator())
    counts: dict[str, int] = {}

    def change(document: dict[str, Any]) -> Change:
        made = apply_finding(document, fragment)
        counts.update(finding_counts(document))
        return made

    result = update_draft(args.draft, change)
    result.data.update(counts)
    result.summary = f"report: {result.data['finding']} {result.data['action']} for {result.data['key']}"
    return result


# --- set-disposition ---------------------------------------------------------------------------------------

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


def run_set_disposition(args: argparse.Namespace) -> _common.Result:
    decisions = read_decisions(args)
    if args.via is None and any(decision["disposition"] != "pending" for decision in decisions):
        raise _common.UsageError("--via is required when a finding gets a decision: interactive, batch or policy")
    counts: dict[str, int] = {}

    def change(document: dict[str, Any]) -> Change:
        made = apply_decisions(document, decisions, args.via)
        counts.update(decision_counts(document))
        return made

    result = update_draft(args.draft, change)
    result.data.update(counts)
    result.summary = f"report: {result.data['updated']} decision{'' if result.data['updated'] == 1 else 's'} recorded, {counts['findings_pending']} finding{'' if counts['findings_pending'] == 1 else 's'} pending"
    return result


# --- status ------------------------------------------------------------------------------------------------

SEVERITY_ORDER = {"BLOCKER": 0, "DEGRADER": 1, "COSMETIC": 2}


def family_of(check_id: str) -> str:
    return check_id.split("-", 1)[0]


def missing_checks(document: Mapping[str, Any]) -> dict[str, list[str]]:
    """The expected checks that the draft does not hold, by family, in catalogue order."""
    recorded = set(recorded_checks(document))
    missing: dict[str, list[str]] = {}
    for check in expected_checks():
        if check["id"] not in recorded:
            missing.setdefault(family_of(check["id"]), []).append(check["id"])
    return missing


def pending_findings(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The findings still waiting for a decision, blockers first, then in the order they were recorded."""
    waiting = [finding for finding in document["findings"] if finding["disposition"] == "pending"]
    return sorted(waiting, key=lambda finding: SEVERITY_ORDER[finding["severity"]])


def blocking_reasons(document: Mapping[str, Any]) -> list[str]:
    """What stands between this draft and a final report, in a few words each. Empty when nothing does."""
    if document["status"] == "final":
        return ["the report is already final"]
    reasons: list[str] = []
    if document["run_context"]["eval_mode"]:
        reasons.append("this is an eval-mode run, and its report is never final")
    absent = sum(len(ids) for ids in missing_checks(document).values())
    if absent:
        reasons.append(f"{absent} of {len(expected_checks())} checks are not recorded")
    waiting = len(pending_findings(document))
    if waiting:
        reasons.append(f"{waiting} finding{'' if waiting == 1 else 's'} {'is' if waiting == 1 else 'are'} pending")
    undecided = sum(
        1
        for finding in document["findings"]
        if finding["severity"] == "BLOCKER"
        and finding["disposition"] != "pending"
        and finding.get("confirmed_via") != "interactive"
    )
    if undecided:
        reasons.append(f"{undecided} BLOCKER finding{'' if undecided == 1 else 's'} not decided interactively")
    return reasons


def envelope_lines(data: Mapping[str, Any]) -> int:
    """How many lines the envelope for `data` takes on stdout."""
    text = _common.encode_envelope(_common.make_envelope(INFO, ok=True, data=dict(data)))
    return len(text.splitlines())


def status_data(path: Path, document: Mapping[str, Any]) -> dict[str, Any]:
    """The state of a draft, in at most `STATUS_LINE_BUDGET` lines of envelope.

    The families come in the catalogue's order, which is the order the audit works in, and in one map, so their
    number is bounded by the catalogue's. The pending findings are what is
    left to fit: as many as the budget allows, up to `PENDING_SHOWN`, blockers first, and the rest are counted.
    """
    missing = missing_checks(document)
    families = list(dict.fromkeys(family_of(check["id"]) for check in expected_checks()))
    counts = decision_counts(document)
    reasons = blocking_reasons(document)
    waiting = [f"{f['id']} {f['severity']} {f['key']}" for f in pending_findings(document)]
    data: dict[str, Any] = {
        "draft": str(path),
        "status": document["status"],
        "eval_mode": document["run_context"]["eval_mode"],
        "confirmation_policy": document["run_context"]["confirmation_policy"],
        **check_counts(document),
        "families_done": " ".join(family for family in families if family not in missing),
        "families_remaining": {family: " ".join(ids) for family, ids in missing.items()},
        **counts,
        "ready_to_finalise": not reasons,
        "blocking": "; ".join(reasons),
    }
    for shown in range(min(len(waiting), PENDING_SHOWN), -1, -1):
        data["pending"] = waiting[:shown]
        if shown < len(waiting):
            data["pending_omitted"] = len(waiting) - shown
        if envelope_lines(data) <= STATUS_LINE_BUDGET:
            break
    return data


def run_status(args: argparse.Namespace) -> _common.Result:
    path = Path(args.draft).expanduser()
    document = read_valid_report(path, when="to report on")
    data = status_data(path, document)
    counts = check_counts(document)
    state = "ready to finalise" if data["ready_to_finalise"] else f"not ready to finalise: {data['blocking']}"
    return _common.Result(
        data=data,
        summary=f"report: {counts['checks_recorded']} of {counts['checks_expected']} checks recorded; {state}",
        truncated="pending_omitted" in data,
    )


# --- The command line ---------------------------------------------------------------------------------


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="report.py", description=INFO.summary)
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    start = commands.add_parser("init", help="start a draft from an intake file", allow_abbrev=False)
    start.add_argument("intake", help="the intake file, audit-intake.<label>.json")
    record = commands.add_parser("add-check", help="record the result of one check", allow_abbrev=False)
    record.add_argument("draft", help="the draft to change")
    record.add_argument(
        "--from", dest="source", required=True, help="a JSON file with the check's result, or - for stdin"
    )
    finding = commands.add_parser("add-finding", help="record an issue that a check raised", allow_abbrev=False)
    finding.add_argument("draft", help="the draft to change")
    finding.add_argument("--from", dest="source", required=True, help="a JSON file with the finding, or - for stdin")
    decide = commands.add_parser("set-disposition", help="record a person's decision on findings", allow_abbrev=False)
    decide.add_argument("draft", help="the draft to change")
    decide.add_argument("--via", choices=VIA, help="how the decision was made; not needed to take one back (pending)")
    decide.add_argument("--finding", help="the id of the finding, such as F-003")
    decide.add_argument("--disposition", choices=DISPOSITIONS, help="the decision")
    decide.add_argument("--note", help="why, in the person's words")
    decide.add_argument("--from", dest="source", help="a JSON list of decisions, from a file or - for stdin")
    describe = commands.add_parser(
        "status", help="say what is done, what remains and what awaits a decision", allow_abbrev=False
    )
    describe.add_argument("draft", help="the draft to describe")
    return parser


HANDLERS = {
    "init": run_init,
    "add-check": run_add_check,
    "add-finding": run_add_finding,
    "set-disposition": run_set_disposition,
    "status": run_status,
}


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    return HANDLERS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
