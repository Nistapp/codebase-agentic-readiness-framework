# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The state file's names, paths, schema checks and reading: the pure helpers `progress.py` builds its commands on."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import _common
import _jsonschema_subset as subset
import validate_report
from _progress_themes import THEME_IDS


SCHEMA_VERSION = "0.3"


RECIPES = Path(__file__).resolve().parent.parent
FRAMEWORK_ROOT = RECIPES.parent


# The schemas sit beside the tools in the implement skill bundle (`scripts/schema/`) and in `audit/schema/` in a
# framework checkout.
_SCHEMA_DIR = next(
    (d for d in (RECIPES / "schema", FRAMEWORK_ROOT / "audit" / "schema") if d.is_dir()), RECIPES / "schema"
)
STATE_SCHEMA = _SCHEMA_DIR / "readiness-state.schema.json"
STATE_DIR = Path("docs") / "agentic-readiness"
STATE_JSON_SUFFIX = "-agentic-readiness-state.json"
STATE_MD_SUFFIX = "-agentic-readiness-STATE.md"
MAX_STATE_BYTES = 8 * 1024 * 1024
VERDICT_INFIX = "-regressions-"
VERDICT_STATUSES = ("lost", "clean")
REF_TIPS_SUFFIX = "-ref-tips.json"
#: The refs whose tips `init` records and `verify-refs` checks (ADR 0007): branches, tags and the origin's branches.
REF_NAMESPACES = ("refs/heads", "refs/tags", "refs/remotes/origin")
MAX_REF_TIPS_BYTES = 8 * 1024 * 1024


ITEM_STATUSES = ("queued", "in_progress", "done", "partial", "failed", "blocked", "deferred", "skipped")
NEEDS_REASON = frozenset({"skipped", "deferred", "failed", "blocked"})
OWNER_ONLY = frozenset({"skipped", "deferred"})


# --- Paths --------------------------------------------------------------------------------------------


def state_names(label: str) -> tuple[str, str]:
    if not _common.EXPLICIT_LABEL.match(label):
        raise _common.UsageError(f"not a repository label: {label!r}")
    return label + STATE_JSON_SUFFIX, label + STATE_MD_SUFFIX


def state_file(directory: Path, name: str) -> Path:
    """`directory / name`, refusing a symlink, so a write can never go through a link to somewhere else."""
    path = directory / name
    if path.is_symlink():
        raise _common.PathNotAllowed(f"refusing a state file that is a symlink: {path}")
    if path.exists() and not path.is_file():
        raise _common.PathNotAllowed(f"the state path is not a file: {path}")
    return path


def workspace_directory(path: str | Path) -> Path:
    """The workspace folder `--workspace` names, resolved. It must exist and be a directory."""
    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _common.UsageError(f"workspace not found: {candidate}") from None
    if not resolved.is_dir():
        raise _common.UsageError(f"workspace is not a directory: {resolved}")
    return resolved


def find_state(directory: Path, label: str | None) -> tuple[str, Path]:
    """The label and the JSON path of the state in `directory`. Without `label` there must be exactly one state."""
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


def verdict_name(label: str, theme: str) -> str:
    """The file name of the lost-pass verdict `check_regressions.py --workspace` writes for one theme of a state."""
    state_names(label)  # refuses a label that is not a file name
    if theme not in THEME_IDS:
        raise _common.UsageError(f"no theme {theme!r}; the themes are {', '.join(THEME_IDS)}")
    return f"{label}{VERDICT_INFIX}{theme}.json"


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


def refuse_unknown_state_schema(state: Any) -> None:
    """Raise `ValidationFailed` with a plain message when the state's `schema_version` is not the one these tools read."""
    if not isinstance(state, dict) or state.get("schema_version", SCHEMA_VERSION) == SCHEMA_VERSION:
        return
    found = state["schema_version"]
    release = (state.get("framework") or {}).get("release") or (state.get("recipe") or {}).get("version")
    made_by = f"framework v{release}" if isinstance(release, str) else "an unknown framework release"
    raise _common.ValidationFailed(
        f"the state has schema {found!r} (made by {made_by}); these tools read schema {SCHEMA_VERSION!r}. Move the "
        f"old state files aside and run init again from a final report (recommended), or use {made_by} to resume it."
    )


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
    refuse_unknown_state_schema(state)
    errors = state_errors(state)
    if errors:
        raise _common.ValidationFailed(f"the state is not valid: {len(errors)} errors", errors=errors)
    if not isinstance(state, dict):  # pragma: no cover - the schema requires an object
        raise _common.ValidationFailed("the state is not an object")
    return state


def encode_state(state: dict[str, Any]) -> str:
    return json.dumps(state, indent=2, ensure_ascii=False) + "\n"


def _finding_order(finding_id: str) -> tuple[int, str]:
    digits = finding_id[2:]
    return (int(digits) if digits.isdigit() else 0, finding_id)


def short_sha(sha: str | None) -> str | None:
    """A commit id cut to the 12 digits a state records (`validate_report.SHORT_SHA_CHARS`)."""
    return sha[: validate_report.SHORT_SHA_CHARS] if sha else None


def file_sha256(path: Path) -> str:
    """SHA-256 of the file's bytes, as 64 lower-case hex digits."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _sha_option(text: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{7,40}", text):
        raise _common.UsageError(f"--merged-sha must be 7 to 40 lower-case hex digits, not {text!r}")
    return short_sha(text) or text


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
