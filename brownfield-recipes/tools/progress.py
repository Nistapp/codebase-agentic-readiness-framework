# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Create, show and render the implement recipe's per-repository state.

    progress.py init --report <final report.json> --target <repo> [--default-branch B] [--phase P] [--date D]
                     [--framework-rev SHA]
    progress.py show --target <repo> [--label LABEL] [--json]
    progress.py render --target <repo> [--label LABEL]

The state is ``docs/agentic-readiness/<label>-agentic-readiness-state.json`` in the target, the source of truth, and
``<label>-agentic-readiness-STATE.md`` beside it, rendered from the JSON. Its format is
``schema/readiness-state.schema.json``; the rules the schema subset cannot express are in :func:`state_rule_errors`.

This is the one tool that writes inside a target, and it writes those two files and nothing else (ADR 0002). Both
are written atomically: a temporary file beside the target file, then a rename, so a reader sees the old file or the
new one and never half of one. The folder must resolve inside the target, and neither file may be a symlink.

``init`` reads a final audit report that ``validate_report.py`` accepts, inside the target. Confirmed and edited
findings become ``queued`` items, a finding the owner deferred during the audit becomes a ``deferred`` item with the
owner's note as its reason, and rejected findings are listed in ``not_queued``. Each item gets the theme of its check
from :data:`THEMES`. ``init`` never replaces a state; the transitions come in a later step.

``render`` is a pure function of the JSON: the same state, in any key order, gives the same bytes.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import _common
import _jsonschema_subset as subset
import validate_report

RECIPE_NAME = "brownfield-implement"
RECIPE_VERSION = "0.2.0-dev"
SCHEMA_VERSION = "0.1"

RECIPES = Path(__file__).resolve().parent.parent
FRAMEWORK_ROOT = RECIPES.parent
STATE_SCHEMA = RECIPES / "schema" / "readiness-state.schema.json"
STATE_DIR = Path("docs") / "agentic-readiness"
STATE_JSON_SUFFIX = "-agentic-readiness-state.json"
STATE_MD_SUFFIX = "-agentic-readiness-STATE.md"
MAX_STATE_BYTES = 8 * 1024 * 1024
GIT_TIMEOUT_S = 10


def _span(prefix: str, first: int, last: int, *, skip: Sequence[int] = ()) -> tuple[str, ...]:
    return tuple(f"{prefix}-{number:02d}" for number in range(first, last + 1) if number not in skip)


# The themes, in dependency order, and the checks each one owns. Every check in catalogue.json has exactly one theme;
# a test holds the two together. CON-04 sits with CON-01..03 until the governance playbooks confirm or move it.
THEMES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("T1", "Command surface and quality tools", _span("CMD", 1, 4) + _span("TOOL", 1, 4)),
    ("T2", "Execution determinism", _span("EXEC", 1, 7, skip=(4,))),
    ("T3", "Secrets and env", _span("SEC", 1, 3) + ("EXEC-04",)),
    ("T4", "CI parity, hooks, commits", _span("CI", 1, 4) + ("TOOL-05", "TOOL-06")),
    ("T5", "Tests and baselines", _span("TST", 1, 5) + _span("BASE", 1, 4)),
    ("T6", "Docs and navigation", _span("DOC", 1, 4) + _span("NAV", 1, 5)),
    ("T7", "AGENTS.md and governance", _span("AGT", 1, 11) + _span("CON", 1, 4)),
    ("T8", "Hygiene and index", _span("HYG", 1, 11) + _span("IDX", 1, 3)),
)
CHECK_THEME: dict[str, str] = {check: theme for theme, _, checks in THEMES for check in checks}
THEME_IDS = tuple(theme for theme, _, _ in THEMES)

ITEM_STATUSES = ("queued", "in_progress", "done", "partial", "failed", "blocked", "deferred", "skipped")
NEEDS_REASON = frozenset({"skipped", "deferred", "failed", "blocked"})
OWNER_ONLY = frozenset({"skipped", "deferred"})

INFO = _common.ToolInfo(
    name="progress",
    summary="Create, show and render the implement recipe's per-repository state from a final audit report.",
    synopsis=(
        "progress.py init --report REPORT --target REPO [--default-branch BRANCH] [--phase PHASE] [--date YYYY-MM-DD]"
        " [--framework-rev SHA]",
        "progress.py show --target REPO [--label LABEL] [--json]",
        "progress.py render --target REPO [--label LABEL]",
    ),
    writes=(
        "Inside the target, and only there: docs/agentic-readiness/<label>-agentic-readiness-state.json (init) and "
        "<label>-agentic-readiness-STATE.md (init, render), each replaced atomically. init never replaces a state; "
        "show writes nothing."
    ),
    writes_inside_target=True,
)


# --- Paths --------------------------------------------------------------------------------------------


def state_names(label: str) -> tuple[str, str]:
    if not _common.EXPLICIT_LABEL.match(label):
        raise _common.UsageError(f"not a repository label: {label!r}")
    return label + STATE_JSON_SUFFIX, label + STATE_MD_SUFFIX


def state_directory(target: Path) -> Path:
    """`docs/agentic-readiness` in `target`, resolved. A folder on the way that leads out of the target is refused."""
    return _common.resolve_within(target, STATE_DIR)


def state_file(directory: Path, name: str) -> Path:
    """`directory / name`, refusing a symlink, so a write can never go through a link to somewhere else."""
    path = directory / name
    if path.is_symlink():
        raise _common.PathNotAllowed(f"refusing a state file that is a symlink: {path}")
    if path.exists() and not path.is_file():
        raise _common.PathNotAllowed(f"the state path is not a file: {path}")
    return path


def find_state(target: Path, label: str | None) -> tuple[str, Path]:
    """The label and the JSON path of the state in `target`. Without `label` there must be exactly one state."""
    directory = state_directory(target)
    if label is None:
        found = sorted(directory.glob("*" + STATE_JSON_SUFFIX)) if directory.is_dir() else []
        labels = [path.name[: -len(STATE_JSON_SUFFIX)] for path in found]
        if not labels:
            raise _common.UsageError(
                f"no state in {directory}", hint="create one with: progress.py init --report <report> --target <repo>"
            )
        if len(labels) > 1:
            raise _common.UsageError(f"{len(labels)} states in {directory}; pick one with --label: {', '.join(labels)}")
        label = labels[0]
    json_name, _ = state_names(label)
    path = state_file(directory, json_name)
    if not path.exists():
        raise _common.UsageError(f"no state for {label!r} in {directory}")
    return label, path


def sweep_temporaries(directory: Path, names: Sequence[str]) -> int:
    """Remove the temporary files an interrupted atomic write of one of `names` left behind. Returns how many."""
    removed = 0
    for name in names:
        for path in sorted(directory.glob(f".{name}.*.tmp")):
            if path.is_file() and not path.is_symlink():
                path.unlink()
                removed += 1
    return removed


# --- Validation ---------------------------------------------------------------------------------------


def schema_validator() -> subset.SubsetValidator:
    return subset.SubsetValidator(json.loads(STATE_SCHEMA.read_text(encoding="utf-8")))


def state_rule_errors(state: dict[str, Any]) -> list[str]:
    """The rules a schema in the subset cannot express. `state` has already passed the schema."""
    errors: list[str] = []
    themes = [theme["id"] for theme in state["themes"]]
    if themes != list(THEME_IDS):
        errors.append(f"/themes: must be {', '.join(THEME_IDS)}, each once and in that order")
    seen: dict[str, str] = {}
    for index, item in enumerate(state["items"]):
        where = f"/items/{index} ({item['finding']})"
        if item["finding"] in seen:
            errors.append(f"{where}: the finding is already at {seen[item['finding']]}")
        seen.setdefault(item["finding"], f"/items/{index}")
        status = item["status"]
        if status in NEEDS_REASON and item["reason"] is None:
            errors.append(f"{where}: status {status} needs a reason")
        if status in OWNER_ONLY and item["by"] != "owner":
            errors.append(f"{where}: only the owner sets status {status}")
        if status == "done" and item["debt"]:
            errors.append(f"{where}: an item with debt is partial, never done")
    for index, entry in enumerate(state["not_queued"]):
        if entry["finding"] in seen:
            errors.append(
                f"/not_queued/{index} ({entry['finding']}): the finding is already at {seen[entry['finding']]}"
            )
        seen.setdefault(entry["finding"], f"/not_queued/{index}")
    keys: set[str] = set()
    for index, preference in enumerate(state["preferences"]):
        if preference["key"] in keys:
            errors.append(f"/preferences/{index}: the key {preference['key']} is already set")
        keys.add(preference["key"])
    paths: set[str] = set()
    for index, report in enumerate(state["source_reports"]):
        if report["path"] in paths:
            errors.append(f"/source_reports/{index}: the report is already listed")
        paths.add(report["path"])
    return errors


def state_errors(state: Any) -> list[str]:
    """Every reason `state` is not a valid state: the schema's first, and the rules only when the schema passes."""
    found = schema_validator().validate(state, limit=200)
    if found:
        return [f"schema: {violation}" for violation in found]
    return [f"rule: {error}" for error in state_rule_errors(state)]


def read_state(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError:
        raise _common.UsageError(f"state not found: {path}") from None
    if size > MAX_STATE_BYTES:
        raise _common.UsageError(f"the state is {size} bytes and the limit is {MAX_STATE_BYTES}: {path}")
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise _common.ValidationFailed("the file is not a state file: it is not UTF-8 text") from None
    state = validate_report.parse_report(text, "state file")
    errors = state_errors(state)
    if errors:
        raise _common.ValidationFailed(f"the state is not valid: {len(errors)} errors", errors=errors)
    if not isinstance(state, dict):  # pragma: no cover - the schema requires an object
        raise _common.ValidationFailed("the state is not an object")
    return state


def encode_state(state: dict[str, Any]) -> str:
    return json.dumps(state, indent=2, ensure_ascii=False) + "\n"


# --- init ---------------------------------------------------------------------------------------------


def _finding_order(finding_id: str) -> tuple[int, str]:
    digits = finding_id[2:]
    return (int(digits) if digits.isdigit() else 0, finding_id)


def framework_revision() -> str | None:
    """HEAD of the framework checkout this tool runs from, read with git; None when it is not a git checkout."""
    try:
        done = subprocess.run(
            ["git", "-C", str(FRAMEWORK_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = done.stdout.strip()
    return sha if done.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha) else None


def build_state(
    report: dict[str, Any],
    *,
    report_path: str,
    default_branch: str,
    phase: str,
    date: str,
    framework_rev: str | None,
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
        "recipe": {"name": RECIPE_NAME, "version": RECIPE_VERSION, "framework_rev": framework_rev},
        "source_reports": [
            {
                "path": report_path,
                "git_sha": provenance["target"]["git_sha"],
                "catalogue_version": provenance["catalogue_version"],
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


def _date(text: str) -> str:
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise _common.UsageError(f"--date must be a date as YYYY-MM-DD, not {text!r}") from None
    return text


def _sha(text: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{7,40}", text):
        raise _common.UsageError(f"--framework-rev must be 7 to 40 lower-case hex digits, not {text!r}")
    return text


def run_init(args: Any) -> _common.Result:
    target = _common.resolve_target(args.target)
    try:
        report_file = Path(args.report).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise _common.UsageError(f"report not found: {args.report}") from None
    if not _common.is_within(target, report_file):
        raise _common.PathNotAllowed(
            f"the report must be inside the target, so the state can point at it: {report_file}"
        )
    report = validate_report.read_report(report_file)
    outcome = validate_report.validate_document(report)
    if outcome.errors:
        raise _common.ValidationFailed(
            f"the report is not valid: {len(outcome.errors)} errors; run validate_report.py on it",
            errors=outcome.errors,
        )
    if report["status"] != "final":
        raise _common.ValidationFailed(
            f"the report is a {report['status']}, not final", hint="finalise it first with: report.py finalise"
        )
    label = report["provenance"]["target"]["label"]
    json_name, md_name = state_names(label)
    directory = state_directory(target)
    json_path, md_path = state_file(directory, json_name), state_file(directory, md_name)
    if json_path.exists():
        raise _common.UsageError(f"a state already exists: {json_path}; init never replaces one")
    default_branch = args.default_branch or report["provenance"]["target"]["branch"] or "main"
    state = build_state(
        report,
        report_path=report_file.relative_to(target).as_posix(),
        default_branch=default_branch,
        phase=args.phase,
        date=_date(args.date) if args.date else datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        framework_rev=_sha(args.framework_rev) if args.framework_rev else framework_revision(),
    )
    errors = state_errors(state)
    if errors:
        raise _common.ToolError(
            "the state built from the report is not valid, which is a bug in the tool", errors=errors
        )
    directory.mkdir(parents=True, exist_ok=True)
    if not _common.is_within(target, directory.resolve()):  # a folder swapped for a link since the check
        raise _common.PathNotAllowed(f"the state folder leaves the target: {directory}")
    swept = sweep_temporaries(directory, (json_name, md_name))
    _common.atomic_write_text(json_path, encode_state(state))
    _common.atomic_write_text(md_path, render(state))
    counts = status_counts(state)
    warnings = [f"removed {swept} temporary files an interrupted write left in {directory}"] if swept else []
    return _common.Result(
        data={
            "state": str(json_path),
            "markdown": str(md_path),
            "label": label,
            "items": len(state["items"]),
            "statuses": counts,
            "not_queued": len(state["not_queued"]),
        },
        summary=(
            f"progress: created the state for {label}: {counts['queued']} queued, {counts['deferred']} deferred, "
            f"{len(state['not_queued'])} not queued"
        ),
        warnings=warnings,
    )


# --- show ---------------------------------------------------------------------------------------------


def status_counts(state: dict[str, Any]) -> dict[str, int]:
    return {status: sum(item["status"] == status for item in state["items"]) for status in ITEM_STATUSES}


def summary_data(state: dict[str, Any]) -> dict[str, Any]:
    themes = []
    for theme in sorted(state["themes"], key=lambda entry: entry["id"]):
        mine = [item for item in state["items"] if item["theme"] == theme["id"]]
        open_items = sum(item["status"] not in ("done", "skipped") for item in mine)
        themes.append({"id": theme["id"], "status": theme["status"], "items": len(mine), "open": open_items})
    skipped = sorted((item["finding"] for item in state["items"] if item["status"] == "skipped"), key=_finding_order)
    return {
        "label": state["repo"]["label"],
        "items": len(state["items"]),
        "statuses": status_counts(state),
        "not_queued": len(state["not_queued"]),
        "preferences": len(state["preferences"]),
        "themes": themes,
        "skipped": skipped,
        "debt": sum(len(item["debt"]) for item in state["items"]),
        "log_entries": len(state["log"]),
    }


# Byte budgets for `show --json`, which together stay under the envelope's item budget.
SHOW_BUDGETS = {"items": 24 * 1024, "preferences": 8 * 1024, "not_queued": 6 * 1024, "log": 8 * 1024}


def run_show(args: Any) -> _common.Result:
    target = _common.resolve_target(args.target)
    label, path = find_state(target, args.label)
    state = read_state(path)
    summary = summary_data(state)
    counts = summary["statuses"]
    line = (
        f"progress: {label}: {summary['items']} items ({', '.join(f'{n} {s}' for s, n in counts.items() if n)}), "
        f"{summary['not_queued']} not queued, {summary['preferences']} preferences"
    )
    if not args.json:
        return _common.Result(data={"state": str(path), **summary}, summary=line)
    shown = dict(state)
    omitted: dict[str, int] = {}
    for key, budget in SHOW_BUDGETS.items():
        entries = list(reversed(state[key])) if key == "log" else state[key]
        kept, left_out = _common.bound_items(entries, limit_bytes=budget)
        shown[key] = list(reversed(kept)) if key == "log" else kept
        if left_out:
            omitted[key] = left_out
    data: dict[str, Any] = {"state_file": str(path), "state": shown}
    warnings = []
    if omitted:
        data["omitted"] = omitted
        warnings.append("lists cut to fit the output; the log keeps its newest entries: read the file for the rest")
    return _common.Result(data=data, summary=line, warnings=warnings, truncated=bool(omitted))


# --- render -------------------------------------------------------------------------------------------


def cell(text: object) -> str:
    """`text` for one Markdown table cell: one line, with the pipe escaped."""
    value = "" if text is None else str(text)
    value = " ".join(value.split())
    return value.replace("\\", "\\\\").replace("|", "\\|") or "-"


def code(text: object) -> str:
    return f"`{text}`" if text not in (None, "") and "`" not in str(text) else cell(text)


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def render(state: dict[str, Any]) -> str:
    """The Markdown view of `state`. It reads keys by name and sorts every list, so key order never changes a byte."""
    label = state["repo"]["label"]
    json_name, _ = state_names(label)
    items = sorted(state["items"], key=lambda item: (item["theme"], _finding_order(item["finding"])))
    themes = sorted(state["themes"], key=lambda theme: theme["id"])
    titles = {theme["id"]: theme["title"] for theme in themes}
    recipe = state["recipe"]
    rev = recipe["framework_rev"]
    out: list[str] = [
        f"# Agentic readiness state: {label}",
        "",
        f"> Generated by `progress.py render` from `{json_name}`.",
        "> Do not edit this file: change the state with `progress.py` and render it again.",
        "",
        "Read this file before changing tooling, CI, docs or `AGENTS.md`.",
        "A skipped finding is final until the owner unskips it, and every preference binds.",
        "",
    ]
    out += _table(
        ("Field", "Value"),
        [
            ("Default branch", code(state["repo"]["default_branch"])),
            (
                "Recipe",
                f"{cell(recipe['name'])} {cell(recipe['version'])}, framework "
                + (code(rev) if rev else "not a git checkout"),
            ),
        ]
        + [
            (
                "Source report",
                f"{code(report['path'])} at {code(report['git_sha']) if report['git_sha'] else 'no commit'}, "
                f"catalogue {cell(report['catalogue_version'])}",
            )
            for report in sorted(state["source_reports"], key=lambda report: report["path"])
        ],
    )
    counts = status_counts(state)
    out += ["", "## Summary", ""]
    out += _table(
        ("Status", "Items"),
        [(status, str(count)) for status, count in counts.items()]
        + [("total", str(len(items))), ("not queued (rejected in the audit)", str(len(state["not_queued"])))],
    )
    out += ["", "## Preferences", ""]
    preferences = sorted(state["preferences"], key=lambda preference: preference["key"])
    if preferences:
        out += _table(
            ("Key", "Value", "Reason", "By", "Date", "Phase"),
            [
                (code(p["key"]), cell(p["value"]), cell(p["reason"]), p["by"], p["date"], cell(p["phase"]))
                for p in preferences
            ],
        )
    else:
        out.append("None recorded.")
    out += ["", "## Themes", ""]
    out += _table(
        ("Theme", "Title", "Status", "Items", "Open", "Phase", "Branch", "PR", "Merged"),
        [
            (
                theme["id"],
                cell(theme["title"]),
                theme["status"],
                str(sum(item["theme"] == theme["id"] for item in items)),
                str(sum(item["theme"] == theme["id"] and item["status"] not in ("done", "skipped") for item in items)),
                cell(theme["phase"]),
                code(theme["branch"]),
                f"#{theme['pr']}" if theme["pr"] is not None else "-",
                code(theme["merged_sha"]),
            )
            for theme in themes
        ],
    )
    out += ["", "## Items by theme"]
    for theme in themes:
        mine = [item for item in items if item["theme"] == theme["id"]]
        out += ["", f"### {theme['id']} {cell(titles[theme['id']])}", ""]
        if not mine:
            out.append("No items.")
            continue
        out += _table(
            ("Finding", "Check", "Severity", "Status", "By", "Date", "Statement"),
            [
                (i["finding"], i["check"], i["severity"], i["status"], i["by"], i["date"], cell(i["statement"]))
                for i in mine
            ],
        )
        details = [item for item in mine if item["reason"] or item["notes"] or item["commits"] or item["verification"]]
        if details:
            out.append("")
        for item in details:
            parts = []
            if item["reason"]:
                parts.append(f"reason: {cell(item['reason'])}")
            if item["notes"]:
                parts.append(f"notes: {cell(item['notes'])}")
            if item["commits"]:
                parts.append("commits: " + ", ".join(code(sha) for sha in item["commits"]))
            if item["verification"]:
                verification = item["verification"]
                parts.append(f"verification: {code(verification['command'])} gave {cell(verification['result'])}")
            out.append(f"- **{item['finding']}**: " + "; ".join(parts))
    for heading, status in (("Skipped", "skipped"), ("Deferred", "deferred")):
        chosen = [item for item in items if item["status"] == status]
        out += ["", f"## {heading}", ""]
        if chosen:
            out += _table(
                ("Finding", "Check", "Theme", "Reason", "By", "Date"),
                [(i["finding"], i["check"], i["theme"], cell(i["reason"]), i["by"], i["date"]) for i in chosen],
            )
        else:
            out.append("None.")
    out += ["", "## Debt", ""]
    debt = [(item, entry) for item in items for entry in item["debt"]]
    if debt:
        out += _table(
            ("Finding", "Check", "What", "Count", "Baseline file"),
            [
                (item["finding"], item["check"], cell(entry["what"]), str(entry["count"]), code(entry["baseline_file"]))
                for item, entry in debt
            ],
        )
    else:
        out.append("None recorded.")
    out += ["", "## Not queued", ""]
    rejected = sorted(state["not_queued"], key=lambda entry: _finding_order(entry["finding"]))
    if rejected:
        out += _table(
            ("Finding", "Check", "Severity", "Audit note"),
            [(e["finding"], e["check"], e["severity"], cell(e["note"])) for e in rejected],
        )
    else:
        out.append("None.")
    out += ["", "## Log", ""]
    out += _table(
        ("Date", "Phase", "Event"),
        [(entry["date"], cell(entry["phase"]), cell(entry["event"])) for entry in state["log"]],
    )
    return "\n".join(out) + "\n"


def run_render(args: Any) -> _common.Result:
    target = _common.resolve_target(args.target)
    label, path = find_state(target, args.label)
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


# --- Arguments ----------------------------------------------------------------------------------------


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="progress.py", description=INFO.summary)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_common.ToolParser)
    init = commands.add_parser("init", help="create the state from a final audit report inside the target")
    init.add_argument("--report", required=True, help="the final audit report (JSON), inside the target")
    init.add_argument("--target", required=True, help="the repository the report audited")
    init.add_argument("--default-branch", help="the branch PRs go into (default: the report's branch, else main)")
    init.add_argument("--phase", default="init", help="the step that creates the state, for the log (default: init)")
    init.add_argument("--date", help="the date to record, YYYY-MM-DD (default: today, UTC)")
    init.add_argument("--framework-rev", help="the framework SHA to record (default: this checkout's HEAD)")
    show = commands.add_parser("show", help="summarise the state; --json prints it")
    show.add_argument("--target", required=True)
    show.add_argument("--label", help="the state to read when the target holds more than one")
    show.add_argument("--json", action="store_true", help="print the state itself, bounded")
    render_command = commands.add_parser("render", help="write the Markdown view from the JSON")
    render_command.add_argument("--target", required=True)
    render_command.add_argument("--label", help="the state to render when the target holds more than one")
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    if args.command == "init":
        return run_init(args)
    if args.command == "show":
        return run_show(args)
    return run_render(args)


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
