# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Create, show and render the implement recipe's per-repository state.

    progress.py init --report <final report.json> --target <repo> [--default-branch B] [--phase P] [--date D]
                     [--framework-rev SHA]
    progress.py adopt --target <repo> --workspace <dir> --phase P [--label LABEL] [--date D]
    progress.py show --workspace <dir> [--label LABEL] [--json]
    progress.py render --workspace <dir> [--label LABEL]
    progress.py set-status|skip|unskip|defer|undefer|pref|theme ... --workspace <dir>   (the transitions; see --help)
    progress.py accept-lost <theme> --reason <text> --by owner --workspace <dir> --phase P

The state lives in the workspace: the folder of the final report given to ``init``, normally the audit run's output
folder (ADR 0004). It is ``<label>-agentic-readiness-state.json``, the source of truth, and
``<label>-agentic-readiness-STATE.md`` beside it, rendered from the JSON. Its format is
``schema/readiness-state.schema.json``; the rules the schema subset cannot express are in :func:`state_rule_errors`.
Every command but ``init`` finds the state in the folder ``--workspace`` names. It must exist; a symlink on the way is
followed, and a state file that is a symlink is refused.

The tool writes those two files and nothing else, and never inside the target: ``init`` refuses a workspace that
resolves inside it. Both files are written atomically: a temporary file beside the file, then a rename, so a reader
sees the old file or the new one and never half of one.

``init`` reads a final audit report that ``validate_report.py`` accepts, outside the target. Confirmed and edited
findings become ``queued`` items, a finding the owner deferred during the audit becomes a ``deferred`` item with the
owner's note as its reason, and rejected findings are listed in ``not_queued``. Each item gets the theme of its check
from :data:`THEMES`. ``init`` never replaces a state; the transitions come in a later step.

The transition commands change one thing, check the whole state again, append a log entry and replace the JSON
atomically; ``--render`` replaces the Markdown too. They enforce the state diagram in :data:`LEGAL` and refuse every
other move with a message of its own. Only the owner skips, defers, unskips, undefers and sets preferences, which the
caller states with ``--by owner`` (the agent relays what the owner said; the tool cannot see who is typing).

A lost pass stops the theme (ADR 0005). ``check_regressions.py --workspace`` writes its verdict for a theme to
``<label>-regressions-<theme>.json`` in the workspace. While that verdict reads ``lost``, ``set-status <item> done``
for an item of the theme and ``theme <theme> --status merged`` are refused (exit 1), until the owner accepts that
verdict: ``accept-lost <theme> --reason TEXT --by owner`` logs the acceptance with the verdict's SHA-256, so a new
``lost`` verdict needs a new acceptance. A theme with no verdict file is not refused: a run that took no base report,
or a state from older tools, has none. The tool reads the verdict file and never writes it.

``adopt`` moves a state that older tools kept in ``<target>/docs/agentic-readiness/`` into a workspace. It reads
the target and never writes or deletes there. It refuses a state of another schema version and a report whose
SHA-256 differs from the one recorded; it copies each report (and the Markdown beside it) into the workspace,
rewrites the report paths to the file names, logs one entry and lists the in-repo files the owner may now remove.

The target's history is guarded (ADR 0007). ``init`` and ``adopt`` record the tips of the target's branches, tags and
``origin/*`` branches in ``<label>-ref-tips.json`` beside the state, with read-only git; ``record-refs`` records them
for a state that has none. ``verify-refs``, run at each theme close, exits 2 for a recorded ref that is gone, a branch
whose tip no longer contains its recorded tip, or a tag that points elsewhere. A ref the run created is not recorded,
so it passes. ``accept-ref REF --reason TEXT --by owner`` takes the ref's current tip as its new recorded tip (or drops
a ref that is gone) and logs the owner's reason.

``render`` is a pure function of the JSON: the same state, in any key order, gives the same bytes.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import _audit_tools_path  # noqa: F401  (puts audit/tools on sys.path in a checkout)
import _common
import validate_report
import _progress_cmd_pref
import _progress_cmd_refs
import _progress_cmd_status
import _progress_cmd_theme
from _progress_next import cross_theme_checks as cross_theme_checks, next_step as next_step
from _progress_refs import (
    ref_tips_name as ref_tips_name,
    refuse_existing_ref_tips,
    try_ref_tips,
    write_ref_tips,
)
from _progress_render import WRAP_COLUMNS as WRAP_COLUMNS, render_markdown
from _progress_state import (
    ITEM_STATUSES as ITEM_STATUSES,
    NEEDS_REASON as NEEDS_REASON,
    RECIPES,
    SCHEMA_VERSION as SCHEMA_VERSION,
    STATE_DIR,
    STATE_SCHEMA as STATE_SCHEMA,
    _date,
    _finding_order,
    _sha,
    _sha_option,
    encode_state,
    file_sha256,
    find_state as find_state,
    read_state as read_state,
    refuse_unknown_state_schema as refuse_unknown_state_schema,
    short_sha,
    state_errors as state_errors,
    state_file as state_file,
    state_names,
    state_rule_errors as state_rule_errors,
    status_counts,
    summary_data,
    sweep_temporaries,
    verdict_name as verdict_name,
    workspace_directory as workspace_directory,
)
from _progress_themes import (
    CHECK_THEME as CHECK_THEME,
    THEME_IDS as THEME_IDS,
    THEME_PREDECESSORS as THEME_PREDECESSORS,
    THEMES as THEMES,
)
from _progress_transitions import (
    LEGAL as LEGAL,
    THEME_ORDER,
    _commit,
    record,
)

#: The framework release these tools belong to: the state's `framework.release`. release-please rewrites the line.
FRAMEWORK_RELEASE = "0.4.2"  # x-release-please-version

FRAMEWORK_ROOT = RECIPES.parent


INFO = _common.ToolInfo(
    name="progress",
    summary="Create, show and render the implement recipe's per-repository state from a final audit report.",
    synopsis=(
        "progress.py init --report REPORT --target REPO [--default-branch BRANCH] [--phase PHASE] [--date YYYY-MM-DD]"
        " [--framework-rev SHA]",
        "progress.py adopt --target REPO --workspace DIR --phase PHASE [--label LABEL] [--date YYYY-MM-DD]",
        "progress.py show --workspace DIR [--label LABEL] [--json]",
        "progress.py render --workspace DIR [--label LABEL]",
        "progress.py set-status FINDING STATUS --workspace DIR --phase PHASE [--commit SHA] [--verification-command CMD"
        " --verification-result TEXT] [--debt what=..,count=N[,baseline=FILE]] [--clear-debt] [--reason TEXT]"
        " [--note TEXT] [--by owner|agent] [--date YYYY-MM-DD] [--label LABEL] [--render]",
        "progress.py skip|defer FINDING --reason TEXT --by owner --workspace DIR --phase PHASE [--render]",
        "progress.py unskip|undefer FINDING --by owner --workspace DIR --phase PHASE [--reason TEXT] [--render]",
        "progress.py pref set KEY VALUE --reason TEXT --by owner --workspace DIR --phase PHASE [--render]",
        "progress.py pref unset KEY --reason TEXT --by owner --workspace DIR --phase PHASE [--render]",
        "progress.py theme THEME --status branch_open|pr_open|merged [--branch B] [--pr N] [--merged-sha SHA]"
        " --workspace DIR --phase PHASE [--render]",
        "progress.py accept-lost THEME --reason TEXT --by owner --workspace DIR --phase PHASE [--render]",
        "progress.py record-refs --target REPO --workspace DIR --phase PHASE [--label LABEL] [--render]",
        "progress.py verify-refs --target REPO --workspace DIR [--label LABEL]",
        "progress.py accept-ref REF --target REPO --reason TEXT --by owner --workspace DIR --phase PHASE [--render]",
    ),
    writes=(
        "Only in the workspace, the report's folder, which must be outside the target: "
        "<label>-agentic-readiness-state.json (init, adopt) and <label>-agentic-readiness-STATE.md (init, adopt, "
        "render, and any command given --render), each replaced atomically; adopt also copies the source reports "
        "there, never over a different file. init and adopt never replace a state; show writes nothing; every other "
        "command rewrites the JSON after validating it. set-status, theme and accept-lost read the theme's "
        "LABEL-regressions-THEME.json verdict, which check_regressions.py writes. init, adopt and record-refs also "
        "write LABEL-ref-tips.json, the target's ref tips read with read-only git, and never replace it; accept-ref "
        "replaces one tip in it; verify-refs writes nothing."
    ),
)


# --- init ---------------------------------------------------------------------------------------------


def framework_facts() -> dict[str, Any]:
    """The framework these tools run from: `release`, `revision` (12 digits, checkout only) and `install`."""
    return validate_report.framework_facts(FRAMEWORK_ROOT, FRAMEWORK_RELEASE)


def describe_framework(framework: Mapping[str, Any]) -> str:
    """`v0.3.2 at cafecafecafe`, or `v0.3.2` when no commit is known."""
    return f"v{framework['release']}" + (f" at {framework['revision']}" if framework["revision"] else "")


def track_framework(state: dict[str, Any], args: Any) -> None:
    """Set `last_framework` to these tools, and log the move when it differs from the one that wrote last."""
    facts = framework_facts()
    now = {"release": facts["release"], "revision": facts["revision"]}
    if state["last_framework"] != now:
        record(
            state,
            args,
            f"Framework moved from {describe_framework(state['last_framework'])} to {describe_framework(now)}.",
        )
        state["last_framework"] = now


def build_state(
    report: dict[str, Any],
    *,
    report_path: str,
    default_branch: str,
    phase: str,
    date: str,
    framework: Mapping[str, Any],
    report_sha256: str,
) -> dict[str, Any]:
    """The first state for a final, valid `report`. Raises `ValidationFailed` for a check that has no theme."""
    unmapped = sorted({finding["check"] for finding in report["findings"] if finding["check"] not in CHECK_THEME})
    if unmapped:
        raise _common.ValidationFailed(
            f"the report has findings on checks with no theme: {', '.join(unmapped)}",
            hint="add the checks to THEMES in progress.py",
        )
    items: list[dict[str, Any]] = []
    not_queued: list[dict[str, Any]] = []
    for finding in sorted(report["findings"], key=lambda found: _finding_order(found["id"])):
        disposition = finding["disposition"]
        note = finding.get("disposition_note", "")
        if disposition == "rejected":
            not_queued.append(
                {"finding": finding["id"], "check": finding["check"], "severity": finding["severity"], "note": note}
            )
            continue
        if disposition not in ("confirmed", "edited", "deferred"):
            raise _common.ValidationFailed(f"finding {finding['id']} has disposition {disposition}, not a final one")
        deferred = disposition == "deferred"
        items.append(
            {
                "finding": finding["id"],
                "check": finding["check"],
                "severity": finding["severity"],
                "theme": CHECK_THEME[finding["check"]],
                "statement": finding["statement"],
                "status": "deferred" if deferred else "queued",
                "by": "owner" if deferred else "agent",
                "date": date,
                "reason": (note or "Deferred by the owner during the audit.") if deferred else None,
                "commits": [],
                "verification": None,
                "debt": [],
                "notes": f"Edited during the audit: {note}" if disposition == "edited" and note else "",
            }
        )
    provenance = report["provenance"]
    queued = sum(item["status"] == "queued" for item in items)
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": {"label": provenance["target"]["label"], "default_branch": default_branch},
        "framework": dict(framework),
        "last_framework": {"release": framework["release"], "revision": framework["revision"]},
        "source_reports": [
            {
                "path": report_path,
                "git_sha": short_sha(provenance["target"]["git_sha"]),
                "catalogue_version": provenance["catalogue_version"],
                "release": provenance["framework"]["release"],
                "revision": provenance["framework"]["revision"],
                "sha256": report_sha256,
            }
        ],
        "preferences": [],
        "themes": [
            {
                "id": theme,
                "title": title,
                "status": "not_started",
                "phase": None,
                "branch": None,
                "pr": None,
                "merged_sha": None,
            }
            for theme, title, _ in THEMES
        ],
        "items": items,
        "not_queued": not_queued,
        "log": [
            {
                "date": date,
                "phase": phase,
                "event": (
                    f"State created from {report_path}: {queued} queued, {len(items) - queued} deferred, "
                    f"{len(not_queued)} not queued."
                ),
            }
        ],
    }


def run_init(args: Any) -> _common.Result:
    target = _common.resolve_target(args.target)
    try:
        report_file = Path(args.report).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise _common.UsageError(f"report not found: {args.report}") from None
    workspace = report_file.parent
    if _common.is_within(target, workspace):
        raise _common.PathNotAllowed(
            f"the report's folder is inside the target, and the state is written beside the report: {workspace}",
            hint="keep the report in the audit's output folder, outside the target, and pass that path to --report",
        )
    report = validate_report.read_report(report_file)
    outcome = validate_report.validate_document(report)
    validate_report.refuse_unknown_schema(outcome)
    if outcome.errors:
        raise _common.ValidationFailed(
            f"the report is not valid: {len(outcome.errors)} errors; run validate_report.py on it",
            errors=outcome.errors,
        )
    if report["status"] != "final":
        raise _common.ValidationFailed(
            f"the report is a {report['status']}, not final", hint="finalise it first with: report.py finalise"
        )
    framework = framework_facts()
    if args.framework_rev:
        framework["revision"] = short_sha(_sha(args.framework_rev))
    versions, version_warnings = validate_report.compare_versions(report, FRAMEWORK_RELEASE, framework["revision"])
    label = report["provenance"]["target"]["label"]
    json_name, md_name = state_names(label)
    json_path, md_path = state_file(workspace, json_name), state_file(workspace, md_name)
    if json_path.exists():
        raise _common.UsageError(f"a state already exists: {json_path}; init never replaces one")
    ref_path = refuse_existing_ref_tips(workspace, label)
    default_branch = args.default_branch or report["provenance"]["target"]["branch"] or "main"
    date = _date(args.date) if args.date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tips, history_warning = try_ref_tips(target)
    state = build_state(
        report,
        report_path=report_file.name,
        default_branch=default_branch,
        phase=args.phase,
        date=date,
        framework=framework,
        report_sha256=file_sha256(report_file),
    )
    errors = state_errors(state)
    if errors:
        raise _common.ToolError(
            "the state built from the report is not valid, which is a bug in the tool", errors=errors
        )
    swept = sweep_temporaries(workspace, (json_name, md_name))
    _common.atomic_write_text(json_path, encode_state(state))
    _common.atomic_write_text(md_path, render(state))
    if tips is not None:
        write_ref_tips(ref_path, label, date, tips)
    counts = status_counts(state)
    warnings = [*version_warnings, *history_warning]
    if swept:
        warnings.append(f"removed {swept} temporary files an interrupted write left in {workspace}")
    return _common.Result(
        data={
            "versions": versions,
            "state": str(json_path),
            "markdown": str(md_path),
            "label": label,
            "items": len(state["items"]),
            "statuses": counts,
            "not_queued": len(state["not_queued"]),
            "ref_tips": str(ref_path) if tips is not None else None,
        },
        summary=(
            f"progress: created the state for {label}: {counts['queued']} queued, {counts['deferred']} deferred, "
            f"{len(state['not_queued'])} not queued"
        ),
        warnings=warnings,
    )


# --- adopt --------------------------------------------------------------------------------------------


def _copy_new(source: Path, dest: Path) -> bool:
    """Copy `source` to `dest` through a temporary file. False when `dest` already holds the same bytes."""
    data = source.read_bytes()
    if dest.exists():
        return False
    fd, temp = tempfile.mkstemp(dir=str(dest.parent), prefix=f".{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, dest)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp)
        raise
    return True


def run_adopt(args: Any) -> _common.Result:
    args.date = _date(args.date) if args.date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target = _common.resolve_target(args.target)
    workspace = Path(args.workspace).expanduser().resolve()
    if _common.is_within(target, workspace):
        raise _common.PathNotAllowed(
            f"the workspace is inside the target: {workspace}",
            hint="pick a folder outside the repository, for example the audit run's output folder",
        )
    if workspace.exists() and not workspace.is_dir():
        raise _common.UsageError(f"workspace is not a directory: {workspace}")
    label, source = find_state(_common.resolve_within(target, STATE_DIR), args.label)
    source_rel = source.relative_to(target).as_posix()
    state = read_state(source)
    if state["repo"]["label"] != label:
        raise _common.ValidationFailed(f"the state in {source.name} is for {state['repo']['label']!r}, not {label!r}")
    json_name, md_name = state_names(label)
    json_path, md_path = state_file(workspace, json_name), state_file(workspace, md_name)
    if json_path.exists():
        raise _common.UsageError(
            f"the workspace already holds a state for {label}: {json_path}; adopt never replaces one"
        )
    ref_path = refuse_existing_ref_tips(workspace, label)
    tips, history_warning = try_ref_tips(target)
    copies: list[tuple[Path, Path]] = []
    report_folders: list[str] = []
    for entry in state["source_reports"]:
        report = _common.resolve_within(target, entry["path"])
        if not report.is_file():
            raise _common.UsageError(f"the state lists a report that is not in the target: {entry['path']}")
        if file_sha256(report) != entry["sha256"]:
            raise _common.ValidationFailed(
                f"the report was edited after init: {entry['path']} no longer matches the SHA-256 the state recorded",
                hint="restore the report the state was made from (git log -- <report>), then run adopt again",
            )
        pair = [report] + [md for md in (report.with_suffix(".md"),) if md.is_file()]
        for file in pair:
            dest = workspace / file.name
            if any(dest == planned for _, planned in copies):
                raise _common.UsageError(f"two source reports share the file name {file.name}")
            if dest.is_symlink() or (dest.exists() and dest.read_bytes() != file.read_bytes()):
                raise _common.PathNotAllowed(f"the workspace already holds a different {file.name}: {dest}")
            copies.append((file, dest))
        entry["path"] = report.name
        folder = report.parent.relative_to(target).as_posix() + "/"
        if folder not in report_folders:
            report_folders.append(folder)
    record(state, args, f"State adopted from {source_rel}.")
    track_framework(state, args)
    errors = state_errors(state)
    if errors:
        raise _common.ValidationFailed(f"the adopted state would be invalid: {len(errors)} errors", errors=errors)
    workspace.mkdir(parents=True, exist_ok=True)
    copied = [dest.name for file, dest in copies if _copy_new(file, dest)]
    swept = sweep_temporaries(workspace, (json_name, md_name))
    _common.atomic_write_text(json_path, encode_state(state))
    _common.atomic_write_text(md_path, render(state))
    if tips is not None:
        write_ref_tips(ref_path, label, args.date, tips)
    removable = [STATE_DIR.as_posix() + "/", *report_folders]
    agents = target / "AGENTS.md"
    if agents.is_file() and not agents.is_symlink() and STATE_DIR.as_posix() in agents.read_text(encoding="utf-8"):
        removable.append(f"the line in AGENTS.md that points at {STATE_DIR.as_posix()}/")
    warnings = [f"removed {swept} temporary files an interrupted write left in {workspace}"] if swept else []
    warnings += history_warning
    return _common.Result(
        data={
            "state": str(json_path),
            "markdown": str(md_path),
            "label": label,
            "adopted_from": source_rel,
            "ref_tips": str(ref_path) if tips is not None else None,
            "copied": copied,
            "may_remove": removable,
        },
        summary=(
            f"progress: adopted the state for {label} into {workspace}; the target is unchanged. The owner may now "
            f"remove from the target: {', '.join(removable)}"
        ),
        warnings=warnings,
    )


# --- show ---------------------------------------------------------------------------------------------


# Byte budgets for `show --json`, which together stay under the envelope's item budget.
SHOW_BUDGETS = {"items": 24 * 1024, "preferences": 8 * 1024, "not_queued": 6 * 1024, "log": 8 * 1024}


def run_show(args: Any) -> _common.Result:
    label, path = find_state(workspace_directory(args.workspace), args.label)
    state = read_state(path)
    summary = summary_data(state)
    counts = summary["statuses"]
    line = (
        f"progress: {label}: {summary['items']} items ({', '.join(f'{n} {s}' for s, n in counts.items() if n)}), "
        f"{summary['not_queued']} not queued, {summary['preferences']} preferences"
    )
    facts = framework_facts()
    versions = {
        "created": state["framework"],
        "last": state["last_framework"],
        "tools": {"release": facts["release"], "revision": facts["revision"]},
    }
    if not args.json:
        brief: dict[str, Any] = {"state": str(path), **summary, "versions": versions, "next": next_step(state)}
        return _common.Result(data=brief, summary=line)
    shown = dict(state)
    omitted: dict[str, int] = {}
    for key, budget in SHOW_BUDGETS.items():
        entries = list(reversed(state[key])) if key == "log" else state[key]
        kept, left_out = _common.bound_items(entries, limit_bytes=budget)
        shown[key] = list(reversed(kept)) if key == "log" else kept
        if left_out:
            omitted[key] = left_out
    data: dict[str, Any] = {"state_file": str(path), "state": shown, "versions": versions, "next": next_step(state)}
    warnings = []
    if omitted:
        data["omitted"] = omitted
        warnings.append("lists cut to fit the output; the log keeps its newest entries: read the file for the rest")
    return _common.Result(data=data, summary=line, warnings=warnings, truncated=bool(omitted))


# --- render -------------------------------------------------------------------------------------------


def check_titles() -> dict[str, str]:
    """Each check's ID mapped to its title in the catalogue these tools carry."""
    return {check["id"]: check["title"] for check in validate_report.load_catalogue()["checks"]}


def render(state: dict[str, Any]) -> str:
    """The Markdown view of `state`. It reads keys by name and sorts every list, so key order never changes a byte."""
    return render_markdown(state, check_titles())


def run_render(args: Any) -> _common.Result:
    label, path = find_state(workspace_directory(args.workspace), args.label)
    state = read_state(path)
    if state["repo"]["label"] != label:
        raise _common.ValidationFailed(f"the state in {path.name} is for {state['repo']['label']!r}, not {label!r}")
    json_name, md_name = state_names(label)
    md_path = state_file(path.parent, md_name)
    swept = sweep_temporaries(path.parent, (json_name, md_name))
    text = render(state)
    _common.atomic_write_text(md_path, text)
    warnings = [f"removed {swept} temporary files an interrupted write left in {path.parent}"] if swept else []
    size = len(text.encode("utf-8"))
    return _common.Result(
        data={"markdown": str(md_path), "bytes": size, "label": label},
        summary=f"progress: rendered {md_path.name} ({size} bytes)",
        warnings=warnings,
    )


# --- Transitions --------------------------------------------------------------------------------------


def commit_change(args: Any, label: str, path: Path, state: dict[str, Any], summary: str) -> _common.Result:
    """Check the changed `state` whole, replace the JSON atomically, and the Markdown when `--render` is given.

    Every write records the framework that made it in `last_framework`, with a log entry when that changed.
    """
    track_framework(state, args)
    errors = state_errors(state)
    if errors:
        raise _common.ValidationFailed(f"the change would make the state invalid: {len(errors)} errors", errors=errors)
    json_name, md_name = state_names(label)
    swept = sweep_temporaries(path.parent, (json_name, md_name))
    md_path = state_file(path.parent, md_name)
    _common.atomic_write_text(path, encode_state(state))
    data: dict[str, Any] = {"state": str(path), "label": label, "statuses": status_counts(state)}
    if args.render:
        _common.atomic_write_text(md_path, render(state))
        data["markdown"] = str(md_path)
    warnings = [f"removed {swept} temporary files an interrupted write left in {path.parent}"] if swept else []
    if not args.render:
        warnings.append(f"{md_name} is out of date; run render or pass --render")
    return _common.Result(data=data, summary=f"progress: {summary}", warnings=warnings)


# --- Arguments ----------------------------------------------------------------------------------------


WORKSPACE_HELP = "the folder that holds the state files"
TARGET_HELP = "the repository the state is for (read only)"


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="progress.py", description=INFO.summary)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_common.ToolParser)
    init = commands.add_parser("init", help="create the state beside a final audit report, outside the target")
    init.add_argument(
        "--report",
        required=True,
        help="the final audit report (JSON); its folder, outside the target, is the workspace",
    )
    init.add_argument("--target", required=True, help="the repository the report audited")
    init.add_argument("--default-branch", help="the branch PRs go into (default: the report's branch, else main)")
    init.add_argument("--phase", default="init", help="the step that creates the state, for the log (default: init)")
    init.add_argument("--date", help="the date to record, YYYY-MM-DD (default: today, UTC)")
    init.add_argument("--framework-rev", help="the framework SHA to record (default: this checkout's HEAD)")
    adopt = commands.add_parser(
        "adopt", help="move a state kept in the target's docs/agentic-readiness/ into a workspace"
    )
    adopt.add_argument("--target", required=True, help="the checkout that holds the state (read only)")
    adopt.add_argument("--workspace", required=True, help="the folder outside the target to keep the state in")
    adopt.add_argument("--label", help="the state to adopt when the target holds more than one")
    adopt.add_argument("--phase", required=True, help="the step or session making the move, for the log")
    adopt.add_argument("--date", help="the date to record, YYYY-MM-DD (default: today, UTC)")
    show = commands.add_parser("show", help="summarise the state; --json prints it")
    show.add_argument("--workspace", required=True, help=WORKSPACE_HELP)
    show.add_argument("--label", help="the state to read when the workspace holds more than one")
    show.add_argument("--json", action="store_true", help="print the state itself, bounded")
    render_command = commands.add_parser("render", help="write the Markdown view from the JSON")
    render_command.add_argument("--workspace", required=True, help=WORKSPACE_HELP)
    render_command.add_argument("--label", help="the state to render when the workspace holds more than one")

    def write_options(command: _common.ToolParser, *, by_default: str = "agent") -> None:
        command.add_argument("--workspace", required=True, help=WORKSPACE_HELP)
        command.add_argument("--label", help="the state to change when the workspace holds more than one")
        command.add_argument("--phase", required=True, help="the step or session making the change, for the log")
        command.add_argument(
            "--by", choices=("owner", "agent"), default=by_default, help="who decided (default: agent)"
        )
        command.add_argument("--date", help="the date to record, YYYY-MM-DD (default: today, UTC)")
        command.add_argument("--render", action="store_true", help="also replace the Markdown view")

    set_status = commands.add_parser("set-status", help="move an item to a status the state diagram allows")
    set_status.add_argument("finding")
    set_status.add_argument("status", choices=ITEM_STATUSES)
    set_status.add_argument("--commit", action="append", type=_commit, help="a commit SHA (repeatable)")
    set_status.add_argument("--verification-command", help="the command that verifies the check")
    set_status.add_argument("--verification-result", help="what the command gave")
    set_status.add_argument("--debt", action="append", help="what=TEXT,count=N[,baseline=FILE] (repeatable)")
    set_status.add_argument("--clear-debt", action="store_true", help="drop the recorded debt (it is paid)")
    set_status.add_argument("--reason", help="required for failed and blocked")
    set_status.add_argument("--note", help="text added to the item's notes")
    write_options(set_status)
    for name, needs_reason in (("skip", True), ("unskip", False), ("defer", True), ("undefer", False)):
        owner = commands.add_parser(name, help=f"{name} an item (owner decision, needs --by owner)")
        owner.add_argument("finding")
        owner.add_argument("--reason", required=needs_reason, help="why" if needs_reason else "optional, for the log")
        write_options(owner)
    pref = commands.add_parser("pref", help="set or unset an owner preference (needs --by owner)")
    pref.add_argument("action", choices=("set", "unset"))
    pref.add_argument("key")
    pref.add_argument("value", nargs="?")
    pref.add_argument("--reason", required=True)
    write_options(pref)
    theme = commands.add_parser("theme", help="record a theme's branch, PR and merge")
    theme.add_argument("theme", choices=THEME_IDS)
    theme.add_argument("--status", required=True, choices=THEME_ORDER[1:])
    theme.add_argument("--branch")
    theme.add_argument("--pr", type=int)
    theme.add_argument("--merged-sha", type=_sha_option)
    write_options(theme)
    accept = commands.add_parser(
        "accept-lost", help="record the owner's acceptance of a theme's lost-pass verdict (needs --by owner)"
    )
    accept.add_argument("theme", choices=THEME_IDS)
    accept.add_argument("--reason", required=True, help="the owner's reason")
    write_options(accept)
    record_refs = commands.add_parser(
        "record-refs", help="record the target's ref tips for a state that has none (read-only git)"
    )
    record_refs.add_argument("--target", required=True, help=TARGET_HELP)
    write_options(record_refs)
    verify = commands.add_parser(
        "verify-refs", help="exit 2 when a recorded branch, tag or origin branch lost history (read-only git)"
    )
    verify.add_argument("--target", required=True, help=TARGET_HELP)
    verify.add_argument("--workspace", required=True, help=WORKSPACE_HELP)
    verify.add_argument("--label", help="the state to check when the workspace holds more than one")
    accept_ref = commands.add_parser(
        "accept-ref", help="record the owner's acceptance of a ref that lost history (needs --by owner)"
    )
    accept_ref.add_argument("ref", help="the full ref name verify-refs printed, for example refs/heads/main")
    accept_ref.add_argument("--target", required=True, help=TARGET_HELP)
    accept_ref.add_argument("--reason", required=True, help="the owner's reason")
    write_options(accept_ref)
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    if args.command == "init":
        return run_init(args)
    if args.command == "adopt":
        return run_adopt(args)
    if args.command == "show":
        return run_show(args)
    if args.command == "set-status":
        return _progress_cmd_status.run_set_status(args, commit_change)
    if args.command in ("skip", "unskip", "defer", "undefer"):
        return _progress_cmd_status.run_owner_move(args, commit_change)
    if args.command == "pref":
        return _progress_cmd_pref.run_pref(args, commit_change)
    if args.command == "theme":
        return _progress_cmd_theme.run_theme(args, commit_change)
    if args.command == "accept-lost":
        return _progress_cmd_theme.run_accept_lost(args, commit_change)
    if args.command == "record-refs":
        return _progress_cmd_refs.run_record_refs(args, commit_change)
    if args.command == "verify-refs":
        return _progress_cmd_refs.run_verify_refs(args)
    if args.command == "accept-ref":
        return _progress_cmd_refs.run_accept_ref(args, commit_change)
    return run_render(args)


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
