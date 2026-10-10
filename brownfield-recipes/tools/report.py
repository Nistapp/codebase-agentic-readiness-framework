# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Build the audit report. This tool is the only writer of the draft: the agent never edits the JSON by hand.

    report.py init <intake>

``init`` reads the intake file, captures the target's provenance (commit, branch, whether the working tree is
dirty), and creates ``<label>.audit-draft.<stamp>.json`` in the intake's ``output_dir``. It never replaces a file: a
second run on the same repository starts a second draft, and the earlier one stays as it was.

The shape of the report is ``schema/audit-report.schema.json`` and the rules a schema cannot express are in
``schema/SCHEMA.md``. Every file this tool writes is validated first with ``validate_report.validate_document``, and
the readiness ``summary`` is computed by ``_summary.py``, never taken from a caller.

Failure behaviour: a bad argument, a missing file or an output directory inside the target is exit 1. An intake that
fails its schema or its rules is exit 2, with every error in ``data.errors``.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import _common
import _jsonschema_subset as subset
import _summary
import validate_report as vr

INFO = _common.ToolInfo(
    name="report",
    summary="Build the audit report: the only writer of the draft, and every write is validated.",
    synopsis=("report.py init <intake>",),
    writes=(
        "A new draft, <label>.audit-draft.<stamp>.json, in the intake's output_dir, which must be outside the target. "
        "A name that is taken is never replaced."
    ),
)

RECIPE_NAME = "brownfield-audit"
RECIPE_VERSION = "0.1.0"
SCHEMA_VERSION = "0.1"
DRAFT_KIND = "audit-draft"
DEFAULT_PROBE_TIMEOUT_S = 120

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


# --- The command line ---------------------------------------------------------------------------------


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="report.py", description=INFO.summary)
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    start = commands.add_parser("init", help="start a draft from an intake file", allow_abbrev=False)
    start.add_argument("intake", help="the intake file, audit-intake.<label>.json")
    return parser


HANDLERS = {"init": run_init}


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    return HANDLERS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
