# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Build the audit report. This tool is the only writer of the draft: the agent never edits the JSON by hand.

    report.py init <intake>
    report.py import-engine <draft> <engine report>
    report.py run-engine <draft> --out-dir DIR
    report.py add-check <draft> --from FILE|-
    report.py add-finding <draft> --from FILE|-
    report.py set-disposition <draft> --via VIA (--finding ID --disposition D [--note TEXT] | --from FILE|-)
    report.py status <draft> [--all] [--severity BLOCKER|DEGRADER|COSMETIC]
    report.py finalise <draft>

``init`` reads the intake file, captures the target's provenance (commit, branch, whether the working tree is
dirty), and creates ``<label>.audit-draft.<stamp>.json`` in the intake's ``output_dir``. It never replaces a file: a
second run on the same repository starts a second draft, and the earlier one stays as it was.

``import-engine`` reads the engine's JSON report (schema v2, phase 1) and brings its checks, findings, stack,
components, file counts, probes and unattested items into the draft, with the engine recorded in the provenance. It does
so once, and only for the repository and the commit that the draft was started for: the report of another repository is
refused, and so is a second import. The conversion is `_engine_adapter.py`, a pure function of the engine's report;
what the report cannot hold is a warning, and nothing is dropped without one.

``run-engine`` runs ``engine.py`` with the flags the draft's intake recorded (Stage 2, step 1 of the audit recipe), then
does what ``import-engine`` does with the report it wrote.

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
import os
import time
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

import _common
import _summary
import engine as engine_launcher
import render_report
import validate_report as vr
from _report_draft import (
    SCHEMA_VERSION as SCHEMA_VERSION,
    DEFAULT_PROBE_TIMEOUT_S as DEFAULT_PROBE_TIMEOUT_S,
    MAX_FRAGMENT_CHARS as MAX_FRAGMENT_CHARS,
    INTAKE_SCHEMA as INTAKE_SCHEMA,
    GIT_SHA as GIT_SHA,
    SHORT_SHA_CHARS as SHORT_SHA_CHARS,
    dumps as dumps,
    git_toplevel as git_toplevel,
    git_facts as git_facts,
    same_commit as same_commit,
    intake_validator as intake_validator,
    intake_rule_errors as intake_rule_errors,
    read_intake as read_intake,
    new_draft as new_draft,
    report_schema as report_schema,
    schema_order as schema_order,
    in_schema_order as in_schema_order,
    expected_checks as expected_checks,
    Change as Change,
    read_valid_report as read_valid_report,
    read_draft as read_draft,
    target_directory as target_directory,
    refuse_inside_target as refuse_inside_target,
    read_fragment as read_fragment,
    fragment_validator as fragment_validator,
    fragment_errors as fragment_errors,
    agent_evidence as agent_evidence,
    checked_fragment as checked_fragment,
)
from _report_checks import (
    CHECK_FIELDS as CHECK_FIELDS,
    CHECK_REQUIRED as CHECK_REQUIRED,
    check_validator as check_validator,
    recorded_checks as recorded_checks,
    accounted_checks as accounted_checks,
    check_counts as check_counts,
    apply_check as apply_check,
    override_check as override_check,
)
from _report_findings import (
    FINDING_FIELDS as FINDING_FIELDS,
    FINDING_REQUIRED as FINDING_REQUIRED,
    SCOPE_SCHEMA as SCOPE_SCHEMA,
    finding_validator as finding_validator,
    normal_scope as normal_scope,
    finding_key as finding_key,
    next_finding_id as next_finding_id,
    finding_counts as finding_counts,
    initial_decision as initial_decision,
    apply_finding as apply_finding,
)
from _report_decisions import (
    DISPOSITIONS as DISPOSITIONS,
    VIA as VIA,
    MAX_DECISIONS as MAX_DECISIONS,
    decisions_validator as decisions_validator,
    read_decisions as read_decisions,
    refused_decisions as refused_decisions,
    apply_decisions as apply_decisions,
    decision_counts as decision_counts,
)
from _report_import import (
    resolved_path as resolved_path,
    agree_with_target as agree_with_target,
    engine_meanings as engine_meanings,
    score_differences as score_differences,
    apply_import as apply_import,
)
from _report_status import (
    SEVERITY_ORDER as SEVERITY_ORDER,
    family_of as family_of,
    missing_checks as missing_checks,
    pending_findings as pending_findings,
    undecided_blockers as undecided_blockers,
    blocking_reasons as blocking_reasons,
    REPORT_TOOL as REPORT_TOOL,
    engine_arguments as engine_arguments,
    command_line as command_line,
    next_step as next_step,
    LISTED_IDS as LISTED_IDS,
    listed as listed,
    finalisation_errors as finalisation_errors,
)

INFO = _common.ToolInfo(
    name="report",
    summary="Build the audit report: the only writer of the draft, and every write is validated.",
    synopsis=(
        "report.py init <intake>",
        "report.py import-engine <draft> <engine report>",
        "report.py run-engine <draft> --out-dir DIR",
        "report.py add-check <draft> --from FILE|-",
        "report.py add-finding <draft> --from FILE|-",
        "report.py set-disposition <draft> --via VIA (--finding ID --disposition D [--note TEXT] | --from FILE|-)",
        "report.py set-stack-profile <draft> <id> [--derived] [--confirmed]",
        "report.py status <draft> [--all] [--severity BLOCKER|DEGRADER|COSMETIC]",
        "report.py finalise <draft>",
    ),
    writes=(
        "init: a new draft, <label>.audit-draft.<stamp>.json, in the intake's output_dir, which must be outside the "
        "target; a name that is taken is never replaced. The run-engine subcommand writes what engine.py writes in --out-dir, "
        "outside the target, then changes the draft as import-engine does. import-engine, add-check, add-finding, set-disposition and set-stack-profile: that "
        "draft, in place and atomically, and no other file. status: nothing. finalise: a new final report, "
        "<label>.audit-report.<stamp>.json, and its Markdown, <label>.audit-report.<stamp>.md, beside the draft, "
        "which it leaves as it was."
    ),
)

#: The framework release these tools belong to: `provenance.framework.release`. release-please rewrites the line.
FRAMEWORK_RELEASE = "0.4.1"  # x-release-please-version
DRAFT_KIND = "audit-draft"
FINAL_KIND = "audit-report"
STATUS_LINE_BUDGET = 40
PENDING_SHOWN = 8

# The ids of the profiles in stacks/ (a test holds this tuple and the folder together; the bundle has no stacks/ beside
# the tools). A profile outside it is "derived": the agent worked from the check files' stack-neutral rubrics.
SHIPPED_STACK_PROFILES = ("java", "python", "typescript-node")
STACK_PROFILE_ID = re.compile(r"^[a-z][a-z0-9-]{0,40}\Z")


# --- Time and JSON ------------------------------------------------------------------------------------


def utc_now() -> datetime:
    """The current UTC time to the second. Tests replace this."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def framework_facts(root: Path | None = None) -> dict[str, Any]:
    """`provenance.framework`: the release, the commit (checkout only) and the install of the framework at `root`."""
    return vr.framework_facts(root or vr.RECIPES.parent, FRAMEWORK_RELEASE)


LOCK_WAIT_S = 30


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


def update_draft(argument: str, change: Callable[[dict[str, Any]], Change]) -> _common.Result:
    """Apply `change` to the draft named by `argument`: validate, then write atomically, or write nothing.

    The path is resolved first, so that a link to a draft changes the draft and does not replace the link.
    """
    path = Path(argument).expanduser().resolve()
    directory = path.parent
    if not directory.is_dir():
        raise _common.UsageError(f"draft not found: {path}")
    with write_lock(directory):
        working = read_draft(path)
        target = target_directory(working)
        refuse_inside_target(target, path)
        made = change(working)
        working["summary"] = _summary.compute_summary(working)
        outcome = vr.validate_document(working, target=target, check_lines=True)
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
        framework=framework_facts(),
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


def run_import_engine(args: argparse.Namespace) -> _common.Result:
    engine_path = Path(args.engine_report).expanduser()
    engine = vr.read_report(engine_path, "engine report")
    warnings: list[str] = []

    def change(document: dict[str, Any]) -> Change:
        made, found = apply_import(document, engine)
        warnings.extend(found)
        return made

    result = update_draft(args.draft, change)
    kept, omitted = _common.bound_items(warnings)
    result.data["engine_report"] = str(engine_path.resolve())
    result.warnings = kept + result.warnings
    if omitted:
        result.data["warnings_omitted"] = result.data.get("warnings_omitted", 0) + omitted
        result.truncated = True
    result.summary = (
        f"report: imported {result.data['checks_imported']} checks and {result.data['findings_imported']} findings "
        f"from {result.data['engine']['name']} {result.data['engine']['version']}"
    )
    return result


def run_run_engine(args: argparse.Namespace) -> _common.Result:
    """Run `engine.py` with the flags the draft's intake recorded, then `import-engine` its report into the draft.

    The flags are :func:`engine_arguments`. A draft that is final, or that already holds an engine report, is refused
    before the engine runs, so no report is written for nothing. `engine.py` refuses an output folder inside the target.
    """
    path = Path(args.draft).expanduser()
    document = read_valid_report(path, when="to run the engine for")
    if document["status"] != "draft":
        raise _common.UsageError(f"{path.name} is a final report; only a draft can take an engine report")
    if "engine" in document["provenance"]:
        held = document["provenance"]["engine"]
        raise _common.ValidationFailed(
            f"this draft already holds an engine report (ruleset {held['ruleset_hash']})",
            errors=["the engine was not run; start a new draft with init to audit again"],
        )
    ran = engine_launcher.handler(engine_arguments(document, Path(args.out_dir).expanduser()))
    result = run_import_engine(argparse.Namespace(draft=args.draft, engine_report=ran.data["report"]))
    result.data = {"engine_run": ran.data, **result.data}
    result.warnings = ran.warnings + result.warnings
    result.summary = (
        f"report: the engine wrote {Path(ran.data['report']).name}; {result.summary.removeprefix('report: ')}"
    )
    return result


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


def run_set_stack_profile(args: argparse.Namespace) -> _common.Result:
    """Record `run_context.stack_profile`: which profile the audit used, shipped or derived, and whether the user agreed."""
    profile = args.profile
    if not STACK_PROFILE_ID.match(profile):
        raise _common.UsageError(f"not a profile id: {profile!r}", hint="lower case letters, digits and hyphens")
    shipped = profile in SHIPPED_STACK_PROFILES
    if args.derived and shipped:
        raise _common.UsageError(f"{profile} is a shipped profile; drop --derived")
    if not args.derived and not shipped:
        raise _common.UsageError(
            f"no shipped stack profile {profile!r}; the shipped ones are {', '.join(SHIPPED_STACK_PROFILES)}",
            hint="for a stack with no profile, name it and pass --derived",
        )
    entry = {"id": profile, "source": "derived" if args.derived else "shipped", "confirmed_by_user": args.confirmed}

    def change(document: dict[str, Any]) -> Change:
        document["run_context"]["stack_profile"] = entry
        return Change(data=dict(entry))

    result = update_draft(args.draft, change)
    result.summary = f"report: stack profile {profile} ({entry['source']}) recorded"
    return result


def envelope_lines(data: Mapping[str, Any]) -> int:
    """How many lines the envelope for `data` takes on stdout."""
    text = _common.encode_envelope(_common.make_envelope(INFO, ok=True, data=dict(data)))
    return len(text.splitlines())


def status_data(
    path: Path, document: Mapping[str, Any], *, show_all: bool = False, severity: str | None = None
) -> dict[str, Any]:
    """The state of a draft, in at most `STATUS_LINE_BUDGET` lines of envelope.

    The families come in the catalogue's order, which is the order the audit works in, and in one map, so their
    number is bounded by the catalogue's. The pending findings are what is
    left to fit: as many as the budget allows, up to `PENDING_SHOWN`, blockers first, and the rest are counted.
    `severity` keeps only the pending findings of that severity in the list. `show_all` lifts the line budget and
    `PENDING_SHOWN`: the list then holds every pending finding that fits the output budget (`bound_items`).
    """
    missing = missing_checks(document)
    families = list(dict.fromkeys(family_of(check["id"]) for check in expected_checks()))
    counts = decision_counts(document)
    reasons = blocking_reasons(document)
    step, command = next_step(path, document)
    waiting = [
        f"{f['id']} {f['severity']} {f['key']}"
        for f in pending_findings(document)
        if severity is None or f["severity"] == severity
    ]
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
        "next": step,
        "next_command": command,
    }
    if severity is not None:
        data["pending_severity"] = severity
    if show_all:
        data["pending"], omitted = _common.bound_items(waiting)
        if omitted:
            data["pending_omitted"] = omitted
        return data
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
    data = status_data(path, document, show_all=args.all, severity=args.severity)
    counts = check_counts(document)
    state = "ready to finalise" if data["ready_to_finalise"] else f"not ready to finalise: {data['blocking']}"
    return _common.Result(
        data=data,
        summary=f"report: {counts['checks_recorded']} of {counts['checks_expected']} checks recorded; {state}",
        truncated="pending_omitted" in data,
    )


def run_finalise(args: argparse.Namespace) -> _common.Result:
    """Write the final report and its Markdown as new files, beside the draft, which stays exactly as it was.

    Every earlier file is left alone: a second `finalise` writes a second pair, with `-2` after the stamp. The two
    files take one name apart from the extension, so a taken name for either moves both. The final report is the
    draft with `status: final` and the time it was finalised, and nothing else: the summary is already the one the
    tools computed, and validating the result checks that. The Markdown is `render_report.render` of that report, made
    before anything is written, so a failure leaves nothing behind.
    """
    path = Path(args.draft).expanduser().resolve()
    directory = path.parent
    if not directory.is_dir():
        raise _common.UsageError(f"draft not found: {path}")
    moment = utc_now()
    with write_lock(directory):
        final = read_draft(path)
        target = target_directory(final)
        refuse_inside_target(target, path)
        problems = finalisation_errors(final)
        if problems:
            count = len(problems)
            raise _common.ValidationFailed(
                f"the draft cannot be finalised: {count} problem{'' if count == 1 else 's'}", errors=problems
            )
        final["status"] = "final"
        final["provenance"]["finalised_at"] = moment.isoformat()
        outcome = vr.validate_document(final, target=target, check_lines=True)
        if outcome.errors:
            count = len(outcome.errors)
            raise _common.ValidationFailed(
                f"the final report would not be valid, so nothing was written: {count} error{'' if count == 1 else 's'}",
                errors=outcome.errors,
            )
        label = final["provenance"]["target"]["label"]
        markdown = render_report.render(final)
        try:
            written, written_markdown = _common.create_new_group(
                directory,
                label,
                FINAL_KIND,
                _common.utc_stamp(moment),
                [("json", dumps(final)), ("md", markdown)],
            )
        except OSError as exc:
            raise _common.UsageError(f"cannot write the final report in {directory}: {exc.strerror or exc}") from None
    kept, omitted = _common.bound_items(outcome.warnings)
    data: dict[str, Any] = {
        "report": str(written),
        "markdown": str(written_markdown),
        "draft": str(path),
        "status": final["status"],
        "finalised_at": final["provenance"]["finalised_at"],
        "checks": len(final["checks"]),
        "findings": len(final["findings"]),
        "summary": final["summary"],
    }
    if omitted:
        data["warnings_omitted"] = omitted
    score = final["summary"]["phase1_score"]
    return _common.Result(
        data=data,
        summary=(
            f"report: wrote {written.name} and {written_markdown.name} "
            f"(phase-1 score {score}, {len(final['findings'])} findings)"
        ),
        warnings=kept,
        truncated=bool(omitted),
    )


# --- The command line ---------------------------------------------------------------------------------


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="report.py", description=INFO.summary)
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    start = commands.add_parser("init", help="start a draft from an intake file", allow_abbrev=False)
    start.add_argument("intake", help="the intake file, audit-intake.<label>.json")
    bring = commands.add_parser("import-engine", help="bring in the engine's report", allow_abbrev=False)
    bring.add_argument("draft", help="the draft to change; it must not hold an engine report yet")
    bring.add_argument("engine_report", help="the engine's JSON report, as tools/engine.py wrote it")
    scan = commands.add_parser(
        "run-engine", help="run the engine with the intake's flags, then import its report", allow_abbrev=False
    )
    scan.add_argument("draft", help="the draft to change; it must not hold an engine report yet")
    scan.add_argument("--out-dir", required=True, help="where the engine's report goes; outside the target")
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
    stack = commands.add_parser(
        "set-stack-profile", help="record which stack profile the audit used", allow_abbrev=False
    )
    stack.add_argument("draft", help="the draft to change")
    stack.add_argument(
        "profile", help=f"a shipped profile id ({', '.join(SHIPPED_STACK_PROFILES)}), or any id with --derived"
    )
    stack.add_argument("--derived", action="store_true", help="no profile ships for this stack; guidance was derived")
    stack.add_argument(
        "--confirmed", action="store_true", help="the user confirmed the choice (default: not confirmed)"
    )
    describe = commands.add_parser(
        "status", help="say what is done, what remains and what awaits a decision", allow_abbrev=False
    )
    describe.add_argument("draft", help="the draft to describe")
    describe.add_argument(
        "--all", action="store_true", help="list every pending finding that fits the output, not the first 8"
    )
    describe.add_argument(
        "--severity", choices=tuple(SEVERITY_ORDER), help="list only the pending findings of this severity"
    )
    finish = commands.add_parser("finalise", help="write the final report from a finished draft", allow_abbrev=False)
    finish.add_argument("draft", help="the draft to finalise; it is left as it is")
    return parser


HANDLERS = {
    "init": run_init,
    "import-engine": run_import_engine,
    "run-engine": run_run_engine,
    "add-check": run_add_check,
    "add-finding": run_add_finding,
    "set-disposition": run_set_disposition,
    "set-stack-profile": run_set_stack_profile,
    "status": run_status,
    "finalise": run_finalise,
}


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    return HANDLERS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
