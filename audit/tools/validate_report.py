# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Check an audit report against its schema and against the rules a schema cannot express.

    validate_report.py <report> [--target <repo>]

The check has two stages. The first applies ``schema/audit-report.schema.json`` with the subset validator. A report
that fails it is returned at once, because the rules read fields the schema guarantees. The second applies the rules
in ``schema/SCHEMA.md``, "Rules beyond the schema", each numbered as there: an error says ``rule 6`` and where.

A valid report exits 0 and any warnings are in the envelope. An invalid one exits 2, with every error in
``data.errors`` (bounded, in rule order and then document order) and no warnings: fix the errors first. A file that is
missing or too large is exit 1. A file that is not JSON, or that repeats a key or holds ``NaN``, is a report that fails
validation, so exit 2.

With ``--target`` the tool also looks for the cited files and warns about each one that is not in the target at the
recorded commit (rule 12). It reads the target with ``git cat-file`` and never writes to it.

An error never repeats the value it found, so a credential in a quote does not travel into the error list (rule 11).
"""

from __future__ import annotations

import importlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import _common
import _jsonschema_subset as subset
import _summary
import engine

INFO = _common.ToolInfo(
    name="validate_report",
    summary="Check an audit report against its schema and the rules a schema cannot express.",
    synopsis=("validate_report.py <report> [--target <repo>]",),
    writes="nothing",
)

RECIPES = Path(__file__).resolve().parent.parent
REPORT_SCHEMA = RECIPES / "schema" / "audit-report.schema.json"
CATALOGUE = RECIPES / "catalogue.json"

MAX_REPORT_BYTES = 32 * 1024 * 1024
MAX_SCHEMA_ERRORS = 500
GIT_TIMEOUT_S = 30
CLIP_CHARS = 80

SEVERITY_RANK = {"COSMETIC": 0, "DEGRADER": 1, "BLOCKER": 2}
CATALOGUE_FIELDS = ("title", "phase", "severity", "scored", "method")


@dataclass
class Outcome:
    """What validation found. `stage` is `schema` when the schema stopped it, and `rules` when the rules ran."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stage: str = "rules"

    def error(self, rule: int, pointer: str, message: str) -> None:
        self.errors.append(f"rule {rule}: {pointer or '/'}: {message}")


@dataclass(frozen=True)
class Context:
    """What the rules compare a report with: the catalogue, and the credential patterns of rule 11."""

    catalogue: Mapping[str, Any]
    patterns: Sequence[re.Pattern[str]]

    @property
    def checks(self) -> dict[str, Mapping[str, Any]]:
        return {check["id"]: check for check in self.catalogue["checks"]}

    @property
    def playbooks(self) -> set[str]:
        return {name for check in self.catalogue["checks"] for name in check["playbooks"]}


def clip(text: str, width: int = CLIP_CHARS) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."


# --- Loading ------------------------------------------------------------------------------------------


def _refuse_repeated_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"the object repeats the key {clip(key)!r}")
        seen[key] = value
    return seen


def _refuse_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def _a(what: str) -> str:
    """`what` with its indefinite article: a report, an intake."""
    return f"{'an' if what[:1] in 'aeiou' else 'a'} {what}"


def parse_report(text: str, what: str = "report") -> Any:
    """The JSON in `text`. A repeated key, `NaN` or `Infinity` is refused, because the file would mean two things.

    `what` names the document in the messages, so that the report builder can read an intake with the same code.
    """
    try:
        return json.loads(text, object_pairs_hook=_refuse_repeated_keys, parse_constant=_refuse_constant)
    except RecursionError:
        raise _common.ValidationFailed(f"the file is not {_a(what)}: its JSON is nested too deeply") from None
    except ValueError as exc:
        raise _common.ValidationFailed(f"the file is not {_a(what)}: it is not valid JSON ({exc})") from None


def read_report(path: Path, what: str = "report") -> Any:
    try:
        size = path.stat().st_size
    except OSError:
        raise _common.UsageError(f"{what} not found: {path}") from None
    if not path.is_file():
        raise _common.UsageError(f"the {what} is not a file: {path}")
    if size > MAX_REPORT_BYTES:
        raise _common.UsageError(f"the {what} is {size} bytes and the limit is {MAX_REPORT_BYTES}: {path}")
    try:
        text = path.read_bytes().decode("utf-8")
    except OSError as exc:
        raise _common.UsageError(f"cannot read the {what} {path}: {exc.strerror or exc}") from None
    except UnicodeDecodeError:
        raise _common.ValidationFailed(f"the file is not {_a(what)}: it is not UTF-8 text") from None
    return parse_report(text, what)


@lru_cache(maxsize=1)
def schema_validator() -> subset.SubsetValidator:
    return subset.SubsetValidator(json.loads(REPORT_SCHEMA.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def load_catalogue() -> Mapping[str, Any]:
    try:
        catalogue: Mapping[str, Any] = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _common.UsageError(f"cannot read the check catalogue {CATALOGUE}: {exc}") from None
    return catalogue


@lru_cache(maxsize=1)
def redaction_patterns() -> tuple[re.Pattern[str], ...]:
    """The engine's credential patterns. They come from the engine and are never copied here (ADR 0001)."""
    engine.load_engine()
    probes = importlib.import_module("audit.probes")
    return tuple(probes.REDACTION_PATTERNS)


# --- Walking a report ---------------------------------------------------------------------------------


def evidence_items(report: Mapping[str, Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
    """Every evidence item on a check or a finding, with its pointer, in document order."""
    for owner in ("checks", "findings"):
        for index, item in enumerate(report[owner]):
            for number, evidence in enumerate(item["evidence"]):
                yield f"/{owner}/{index}/evidence/{number}", evidence


def dependency_cycles(findings: Sequence[Mapping[str, Any]]) -> Iterator[list[str]]:
    """Each cycle of `depends_on` that a depth-first walk meets, as a list of finding IDs that ends where it began."""
    graph: dict[str, list[str]] = {}
    for finding in findings:
        graph.setdefault(finding["id"], list(finding["remediation"].get("depends_on", [])))
    state: dict[str, int] = {}  # 1 while on the path, 2 when finished
    for start in graph:
        if start in state:
            continue
        state[start] = 1
        path = [start]
        stack = [iter(graph[start])]
        while stack:
            for dep in stack[-1]:
                if dep not in graph:
                    continue
                if state.get(dep) == 1:
                    yield path[path.index(dep) :] + [dep]
                elif dep not in state:
                    state[dep] = 1
                    path.append(dep)
                    stack.append(iter(graph[dep]))
                    break
            else:
                state[path.pop()] = 2
                stack.pop()


def leaves_target(path: str) -> str | None:
    """Why `path` is not a path inside the target, or None when it is one."""
    if "\x00" in path:
        return "contains a NUL character"
    text = path.replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return "is absolute"
    normal = posixpath.normpath(text)
    if normal == ".." or normal.startswith("../"):
        return "climbs out of the target"
    return None


# --- The rules ----------------------------------------------------------------------------------------
#
# Each function is one rule of "Rules beyond the schema" in schema/SCHEMA.md and has the number given there.


def rule_1_unique_and_resolved(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    first_check: dict[str, int] = {}
    for index, check in enumerate(report["checks"]):
        if check["id"] in first_check:
            out.error(
                1,
                f"/checks/{index}/id",
                f"the check ID {check['id']} is already used at /checks/{first_check[check['id']]}",
            )
        else:
            first_check[check["id"]] = index
    first_id: dict[str, int] = {}
    first_key: dict[str, int] = {}
    for index, finding in enumerate(report["findings"]):
        if finding["id"] in first_id:
            out.error(
                1,
                f"/findings/{index}/id",
                f"the finding ID {finding['id']} is already used at /findings/{first_id[finding['id']]}",
            )
        else:
            first_id[finding["id"]] = index
        if finding["key"] in first_key:
            out.error(
                1,
                f"/findings/{index}/key",
                f"the key {clip(finding['key'])} is already used at /findings/{first_key[finding['key']]}",
            )
        else:
            first_key[finding["key"]] = index
    for index, finding in enumerate(report["findings"]):
        if finding["check"] not in first_check:
            out.error(1, f"/findings/{index}/check", f"{finding['check']} is not a check in this report")
        elif finding["key"].split(":", 1)[0] != finding["check"]:
            out.error(
                1,
                f"/findings/{index}/key",
                f"the key {clip(finding['key'])} does not start with its check, {finding['check']}",
            )
        for number, dep in enumerate(finding["remediation"].get("depends_on", [])):
            if dep not in first_id:
                out.error(
                    1, f"/findings/{index}/remediation/depends_on/{number}", f"{dep} is not a finding in this report"
                )
    for cycle in dependency_cycles(report["findings"]):
        out.error(1, "/findings", f"the dependencies form a cycle: {' -> '.join(cycle)}")


def rule_2_catalogue(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    known = context.checks
    for index, check in enumerate(report["checks"]):
        entry = known.get(check["id"])
        if entry is None:
            out.error(2, f"/checks/{index}/id", f"{check['id']} is not in the catalogue")
            continue
        for name in CATALOGUE_FIELDS:
            if check[name] != entry[name]:
                out.error(
                    2,
                    f"/checks/{index}/{name}",
                    f"{clip(json.dumps(check[name]))} differs from the catalogue's {clip(json.dumps(entry[name]))}",
                )
    playbooks = context.playbooks
    for index, finding in enumerate(report["findings"]):
        name = finding["remediation"].get("playbook")
        if name is not None and name not in playbooks:
            out.error(2, f"/findings/{index}/remediation/playbook", f"the catalogue names no playbook {clip(name)}")


def rule_3_evidence_by_kind(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    needs = {"file": ("path",), "command": ("command",), "index_query": ("index_tool", "query")}
    for pointer, evidence in evidence_items(report):
        for name in needs[evidence["kind"]]:
            if name not in evidence:
                out.error(3, pointer, f"{evidence['kind']} evidence needs {name!r}")
        if "lines" in evidence and "path" not in evidence:
            out.error(3, pointer, "'lines' is given without a 'path'")
        if "path" in evidence:
            reason = leaves_target(evidence["path"])
            if reason is not None:
                out.error(3, f"{pointer}/path", f"the path must be relative to the target, and it {reason}")


def rule_4_who_captured_it(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    for pointer, evidence in evidence_items(report):
        named = [name for name in ("tool", "tool_version") if name in evidence]
        if evidence["captured_by"] == "tool":
            for name in ("tool", "tool_version"):
                if name not in named:
                    out.error(4, pointer, f"evidence captured by a tool must name {name!r}")
        elif named:
            out.error(4, pointer, f"evidence captured by the agent must not name {' or '.join(map(repr, named))}")


def rule_5_methods(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    has_engine = "engine" in report["provenance"]
    for index, check in enumerate(report["checks"]):
        pointer = f"/checks/{index}"
        if "engine_verdict" in check and check["method"] != "automated":
            out.error(5, pointer, f"{check['id']} has an engine_verdict, so its method must be 'automated'")
        if check["method"] == "agent" and check["verdict"] in ("PASS", "PARTIAL") and not check["evidence"]:
            out.error(
                5,
                f"{pointer}/evidence",
                f"{check['id']} is an agent check with the verdict {check['verdict']} and has no evidence",
            )
    if not has_engine and any("engine_verdict" in check for check in report["checks"]):
        out.error(5, "/provenance", "a check has an engine_verdict, so provenance.engine must be present")


def rule_6_overrides(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    for index, check in enumerate(report["checks"]):
        pointer = f"/checks/{index}"
        engine_verdict = check.get("engine_verdict")
        if engine_verdict is not None and check["verdict"] != engine_verdict:
            if "override_reason" not in check:
                out.error(
                    6,
                    pointer,
                    f"{check['id']} overrides the engine's {engine_verdict} with {check['verdict']} and gives no override_reason",
                )
            if not any(item["captured_by"] == "agent" for item in check["evidence"]):
                out.error(
                    6,
                    f"{pointer}/evidence",
                    f"{check['id']} overrides the engine and has no evidence that the agent captured",
                )
        elif "override_reason" in check:
            why = (
                "its verdict matches the engine's"
                if engine_verdict is not None
                else "it has no engine_verdict to override"
            )
            out.error(6, f"{pointer}/override_reason", f"{check['id']} has an override_reason, but {why}")


def rule_7_findings(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    checks = {check["id"]: check for check in report["checks"]}
    for index, finding in enumerate(report["findings"]):
        pointer = f"/findings/{index}"
        check = checks.get(finding["check"])
        if check is not None:
            if SEVERITY_RANK[finding["severity"]] > SEVERITY_RANK[check["severity"]]:
                out.error(
                    7,
                    f"{pointer}/severity",
                    f"{finding['severity']} is higher than {check['id']}'s {check['severity']}",
                )
            if check["verdict"] in ("PASS", "NOT_APPLICABLE") and finding["disposition"] != "rejected":
                out.error(
                    7, f"{pointer}/disposition", f"{check['id']} is {check['verdict']}, so its finding must be rejected"
                )
        pending = finding["disposition"] == "pending"
        if pending and "confirmed_via" in finding:
            out.error(7, f"{pointer}/confirmed_via", "a pending finding has no confirmed_via")
        if not pending and "confirmed_via" not in finding:
            out.error(7, pointer, f"a {finding['disposition']} finding needs confirmed_via")


def rule_8_final_reports(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    if report["status"] != "final":
        return
    if "finalised_at" not in report["provenance"]:
        out.error(8, "/provenance", "a final report needs finalised_at")
    if report["run_context"]["eval_mode"]:
        out.error(8, "/run_context/eval_mode", "an eval-mode report is never final")
    for index, finding in enumerate(report["findings"]):
        pointer = f"/findings/{index}"
        if finding["disposition"] == "pending":
            out.error(8, f"{pointer}/disposition", "a final report has no pending finding")
        if finding["severity"] == "BLOCKER" and finding.get("confirmed_via") != "interactive":
            out.error(
                8, f"{pointer}/confirmed_via", "a BLOCKER finding in a final report must be confirmed_via 'interactive'"
            )


def rule_9_policy(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    policy = report["run_context"]["confirmation_policy"]
    eval_mode = report["run_context"]["eval_mode"]
    if policy == "accept-all" and not eval_mode:
        out.error(9, "/run_context/confirmation_policy", "'accept-all' is allowed only in eval mode")
    if eval_mode and policy == "interactive":
        out.error(9, "/run_context/confirmation_policy", "an eval-mode run cannot be 'interactive'")
    if policy == "interactive":
        for index, finding in enumerate(report["findings"]):
            if finding.get("confirmed_via") == "policy":
                out.error(
                    9,
                    f"/findings/{index}/confirmed_via",
                    "'policy' needs a confirmation policy other than 'interactive'",
                )


def flatten_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """The summary as one level of `/summary/...` pointers, so that each differing number can be named."""
    flat: dict[str, Any] = {}
    for name, value in summary.items():
        if isinstance(value, Mapping):
            flat.update({f"{name}/{inner}": number for inner, number in value.items()})
        else:
            flat[name] = value
    return flat


def rule_10_summary(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    stored = flatten_summary(report["summary"])
    computed = flatten_summary(_summary.compute_summary(report))
    for name, expected in computed.items():
        if stored[name] != expected:
            out.error(
                10, f"/summary/{name}", f"the report says {stored[name]} and its checks and findings give {expected}"
            )


def rule_11_no_secrets(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    for pointer, evidence in evidence_items(report):
        for name in ("quote", "output_tail"):
            text = evidence.get(name)
            if text is None:
                continue
            for number, pattern in enumerate(context.patterns, start=1):
                if pattern.search(text):
                    out.error(
                        11,
                        f"{pointer}/{name}",
                        f"it looks like a credential (the engine's redaction pattern {number}); shorten it or leave it out",
                    )
                    break


RULES = (
    rule_1_unique_and_resolved,
    rule_2_catalogue,
    rule_3_evidence_by_kind,
    rule_4_who_captured_it,
    rule_5_methods,
    rule_6_overrides,
    rule_7_findings,
    rule_8_final_reports,
    rule_9_policy,
    rule_10_summary,
    rule_11_no_secrets,
)


def warn_about_catalogue_version(report: Mapping[str, Any], context: Context, out: Outcome) -> None:
    """Rule 2, as a warning: the report was built against another catalogue than this one."""

    def minor(version: str) -> tuple[str, str]:
        major, minor_number = version.split(".")[:2]
        return major, minor_number

    ours = str(context.catalogue["catalogue_version"])
    theirs = report["provenance"]["catalogue_version"]
    if minor(ours) != minor(theirs):
        out.warnings.append(
            f"the report was built against catalogue {theirs}, and this is {ours}; the checks may differ"
        )


# --- Rule 12: the cited files exist at the recorded commit ---------------------------------------------


def git_output(target: Path, args: Sequence[str], stdin: str | None = None) -> subprocess.CompletedProcess[str] | None:
    """Run a read-only git command in the target. None when git cannot run or does not finish in time."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    try:
        return subprocess.run(
            ["git", "-C", str(target), *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def cited_paths(report: Mapping[str, Any]) -> dict[str, str]:
    """Each repository path that `file` evidence cites, with the pointer of the first item that cites it."""
    paths: dict[str, str] = {}
    for pointer, evidence in evidence_items(report):
        path = evidence.get("path")
        if evidence["kind"] == "file" and path is not None and leaves_target(path) is None:
            paths.setdefault(path, pointer)
    return paths


def missing_in_commit(target: Path, sha: str, paths: Sequence[str]) -> list[str] | str:
    """The paths that are not in the target's commit `sha`, or the reason they could not be checked."""
    if shutil.which("git") is None:
        return "git is not installed"
    probe = git_output(target, ["cat-file", "-e", f"{sha}^{{commit}}"])
    if probe is None or probe.returncode != 0:
        return f"the target does not hold the commit {sha[:12]}"
    # A path with a newline cannot be sent through the line protocol, and no real file evidence has one.
    askable = [path for path in paths if "\n" not in path]
    # git's <tree>:<path> syntax does not resolve a bare "." to the root tree (it looks for a path literally
    # named "."), even though "." is a legitimate citation of the repository root itself. "" and "./" both
    # resolve correctly, so ask git with "" for that one spelling while still reporting on the original path.
    queries = ["" if path == "." else path for path in askable]
    answer = git_output(target, ["cat-file", "--batch-check"], stdin="".join(f"{sha}:{query}\n" for query in queries))
    if answer is None or answer.returncode != 0 or len(answer.stdout.splitlines()) != len(askable):
        return "git could not look the paths up"
    missing = {path for path, line in zip(askable, answer.stdout.splitlines()) if line.endswith(" missing")}
    return [path for path in paths if path in missing or "\n" in path]


def missing_in_tree(target: Path, paths: Sequence[str]) -> list[str]:
    missing = []
    for path in paths:
        try:
            found = os.path.lexists(_common.resolve_within(target, path))
        except _common.PathNotAllowed:
            found = False
        if not found:
            missing.append(path)
    return missing


def rule_12_cited_files(report: Mapping[str, Any], target: Path, out: Outcome) -> None:
    paths = cited_paths(report)
    if not paths:
        return
    sha = report["provenance"]["target"]["git_sha"]
    if sha is None:
        missing = missing_in_tree(target, list(paths))
        where = "in the target"
    else:
        found = missing_in_commit(target, sha, list(paths))
        if isinstance(found, str):
            out.warnings.append(f"the cited files were not checked: {found}")
            return
        missing = found
        where = f"in the target at {sha[:12]}"
    for path in missing:
        out.warnings.append(f"{paths[path]}: the file {clip(path)} is not {where}")


# --- Putting it together ------------------------------------------------------------------------------


def validate_document(
    document: Any,
    *,
    target: Path | None = None,
    catalogue: Mapping[str, Any] | None = None,
    patterns: Sequence[re.Pattern[str]] | None = None,
) -> Outcome:
    """Validate a parsed report. The target, the catalogue and the credential patterns default to the real ones."""
    out = Outcome()
    found = schema_validator().validate(document, limit=MAX_SCHEMA_ERRORS)
    if found:
        out.stage = "schema"
        out.errors = [f"schema: {violation}" for violation in found]
        if len(found) >= MAX_SCHEMA_ERRORS:
            out.errors.append(f"schema: stopped after {MAX_SCHEMA_ERRORS} errors; there may be more")
        return out
    context = Context(
        catalogue=load_catalogue() if catalogue is None else catalogue,
        patterns=redaction_patterns() if patterns is None else patterns,
    )
    for rule in RULES:
        rule(document, context, out)
    if out.errors:
        return out
    warn_about_catalogue_version(document, context, out)
    if target is not None:
        rule_12_cited_files(document, target, out)
    return out


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="validate_report.py", description=INFO.summary)
    parser.add_argument("report", help="the audit report to check")
    parser.add_argument("--target", help="the audited repository, to check that the cited files exist in it")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    target = _common.resolve_target(args.target) if args.target is not None else None
    path = Path(args.report).expanduser()
    document = read_report(path)
    outcome = validate_document(document, target=target)
    if outcome.errors:
        count = len(outcome.errors)
        raise _common.ValidationFailed(
            f"the report is not valid: {count} error{'' if count == 1 else 's'} in the {outcome.stage} stage",
            errors=outcome.errors,
        )
    kept, omitted = _common.bound_items(outcome.warnings)
    data: dict[str, Any] = {
        "valid": True,
        "report": str(path),
        "schema_version": document["schema_version"],
        "status": document["status"],
        "checks": len(document["checks"]),
        "findings": len(document["findings"]),
        "target_checked": target is not None,
    }
    if omitted:
        data["warnings_omitted"] = omitted
    return _common.Result(
        data=data,
        summary=f"validate_report: valid ({data['checks']} checks, {data['findings']} findings, {len(outcome.warnings)} warnings)",
        warnings=kept,
        truncated=bool(omitted),
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
