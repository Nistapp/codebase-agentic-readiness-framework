# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The state diagram and the checks a change to one item, theme or preference makes before it is written."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import _common
from _progress_state import (
    NEEDS_REASON,
    OWNER_ONLY,
    VERDICT_STATUSES,
    _date,
    find_state,
    read_state,
    short_sha,
    state_file,
    verdict_name,
    workspace_directory,
)


# The state diagram (PLAN.md section 5): where an item may go from each status. `done` is final.
LEGAL: dict[str, tuple[str, ...]] = {
    "queued": ("in_progress", "skipped", "deferred"),
    "in_progress": ("done", "partial", "failed", "blocked"),
    "partial": ("in_progress",),
    "failed": ("in_progress",),
    "blocked": ("queued",),
    "deferred": ("queued",),
    "skipped": ("queued",),
    "done": (),
}
# Moves that have a command of their own, so `set-status` refuses them and names the command.
OWN_COMMAND = {
    ("queued", "skipped"): "skip",
    ("queued", "deferred"): "defer",
    ("skipped", "queued"): "unskip",
    ("deferred", "queued"): "undefer",
}
THEME_ORDER = ("not_started", "branch_open", "pr_open", "merged")
DEBT_FORMAT = re.compile(r"^what=(?P<what>.+?),count=(?P<count>[0-9]+)(?:,baseline=(?P<baseline>.+))?$")
LOG_REASON_CHARS = 200


def _refuse(message: str, hint: str = "") -> _common.UsageError:
    return _common.UsageError(message, hint=hint)


def illegal_transition(finding: str, old: str, new: str) -> _common.UsageError:
    """The refusal for moving `finding` from `old` to `new`. Each kind of illegal move has its own message, and every
    one ends by naming the states `old` may go to."""
    refusal = _illegal_transition(finding, old, new)
    allowed = f"from {old} it may go to: {', '.join(LEGAL[old])}" if LEGAL[old] else f"{old} has no next state"
    hint = f"{refusal.hint}; {allowed}" if refusal.hint else allowed
    return _refuse(str(refusal), hint)


def _illegal_transition(finding: str, old: str, new: str) -> _common.UsageError:
    if old == new:
        return _refuse(f"{finding} is already {old}")
    if old == "done":
        return _refuse(f"{finding} is done and done is final", "a regression is a new finding in the next audit")
    if old == "skipped":
        return _refuse(
            f"{finding} is skipped and only the owner can bring it back", f"unskip {finding} --by owner --phase ..."
        )
    if new in ("skipped", "deferred"):
        return _refuse(
            f"{finding} is {old}; only a queued item can be {new}",
            "bring it back to queued first" if old != "queued" else "",
        )
    if old == "queued":
        return _refuse(f"{finding} is queued and must be in_progress before it can be {new}")
    if old == "deferred":
        return _refuse(f"{finding} is deferred and goes back to queued only with undefer --by owner")
    if old == "in_progress" and new in ("queued", "in_progress"):
        return _refuse(f"{finding} is in_progress; end it as done, partial, failed or blocked")
    if old in ("partial", "failed") and new in ("done", "blocked", "queued", "partial", "failed"):
        return _refuse(f"{finding} is {old} and can only go back to in_progress, then be ended again")
    if old == "blocked":
        return _refuse(f"{finding} is blocked and can only go back to queued")
    return _refuse(
        f"{finding}: {old} to {new} is not allowed; from {old} it may go to {', '.join(LEGAL[old]) or 'nowhere'}"
    )


def short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= LOG_REASON_CHARS else text[: LOG_REASON_CHARS - 3] + "..."


def parse_debt(text: str) -> dict[str, Any]:
    found = DEBT_FORMAT.match(text.strip())
    if not found:
        raise _refuse(f"--debt must look like what=TEXT,count=N[,baseline=FILE], not {text!r}")
    return {"what": found["what"].strip(), "count": int(found["count"]), "baseline_file": found["baseline"]}


def _commit(text: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{7,40}", text):
        raise _refuse(f"--commit must be 7 to 40 lower-case hex digits, not {text!r}")
    return short_sha(text) or text


def find_item(state: dict[str, Any], finding: str) -> dict[str, Any]:
    for item in state["items"]:
        if item["finding"] == finding:
            return item  # type: ignore[no-any-return]
    for entry in state["not_queued"]:
        if entry["finding"] == finding:
            raise _refuse(f"{finding} was rejected in the audit and is never queued")
    raise _refuse(f"no item for {finding}", "see the findings with: progress.py show --workspace DIR --json")


def require_owner(args: Any, action: str) -> None:
    if args.by != "owner":
        raise _refuse(
            f"{action} is an owner decision",
            "ask the owner, then record their answer with --by owner",
        )


def add_note(item: dict[str, Any], args: Any) -> None:
    """`set-status F S` when F is already S: record `--note` and any `--commit`, change nothing else."""
    if not args.note:
        raise _refuse(
            f"{item['finding']} is already {item['status']}", "to add a note or commit without a move, pass --note"
        )
    item["notes"] = (item["notes"] + " " + args.note).strip()
    for sha in args.commit or ():
        if sha not in item["commits"]:
            item["commits"].append(sha)


def apply_status(item: dict[str, Any], new: str, args: Any) -> None:
    """Move `item` to `new` as `set-status` asks. Raises a refusal; changes `item` only when nothing is refused."""
    old = item["status"]
    if old == new:
        add_note(item, args)
        return
    if new not in LEGAL[old] or old == "skipped":
        raise illegal_transition(item["finding"], old, new)
    if (old, new) in OWN_COMMAND:
        command = OWN_COMMAND[(old, new)]
        raise _refuse(f"{item['finding']}: {old} to {new} has its own command", f"use {command} --by owner")
    debt = [dict(entry) for entry in item["debt"]]
    if args.clear_debt:
        debt = []
    for text in args.debt or ():
        entry = parse_debt(text)
        debt = [existing for existing in debt if existing["what"] != entry["what"]] + [entry]
    verification = item["verification"]
    if args.verification_command or args.verification_result:
        if not (args.verification_command and args.verification_result):
            raise _refuse("--verification-command and --verification-result go together")
        verification = {"command": args.verification_command, "result": args.verification_result}
    if new == "done":
        if verification is None:
            raise _refuse(
                f"{item['finding']} cannot be done without a verification",
                "give --verification-command and --verification-result",
            )
        if debt:
            raise _refuse(
                f"{item['finding']} still has {len(debt)} debt entries, and an item with debt is partial, never done",
                "use partial, or --clear-debt if the debt is paid",
            )
    if new == "partial" and not debt:
        raise _refuse(f"{item['finding']} cannot be partial without debt", "give --debt what=..,count=N")
    if new in NEEDS_REASON and not args.reason:
        raise _refuse(f"{item['finding']} cannot be {new} without --reason")
    item["status"] = new
    item["reason"] = args.reason if new in NEEDS_REASON else None
    item["verification"] = verification
    item["debt"] = debt
    for sha in args.commit or ():
        if sha not in item["commits"]:
            item["commits"].append(sha)
    if args.note:
        item["notes"] = (item["notes"] + " " + args.note).strip()


def owner_move(item: dict[str, Any], new: str, args: Any) -> None:
    """`skip`, `defer`, `unskip` and `undefer`: the moves only the owner makes."""
    old = item["status"]
    if new not in LEGAL[old]:
        raise illegal_transition(item["finding"], old, new)
    leaves = {"unskip": "skipped", "undefer": "deferred"}.get(args.command)
    if leaves and old != leaves:
        raise _refuse(f"{item['finding']} is {old}, not {leaves}; {args.command} only brings back a {leaves} item")
    item["status"] = new
    item["reason"] = args.reason if new in OWNER_ONLY else None


def record(state: dict[str, Any], args: Any, event: str) -> None:
    state["log"].append({"date": args.date, "phase": args.phase, "event": event})


def open_state(args: Any) -> tuple[str, Path, dict[str, Any]]:
    args.date = _date(args.date) if args.date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    label, path = find_state(workspace_directory(args.workspace), args.label)
    state = read_state(path)
    if state["repo"]["label"] != label:
        raise _common.ValidationFailed(f"the state in {path.name} is for {state['repo']['label']!r}, not {label!r}")
    return label, path, state


def stamp(item: dict[str, Any], args: Any) -> None:
    item["by"] = args.by
    item["date"] = args.date


def read_verdict(directory: Path, label: str, theme: str) -> tuple[dict[str, Any], str] | None:
    """The theme's lost-pass verdict in the workspace and the first 12 hex digits of its SHA-256; None when absent.

    A verdict that is not what ``check_regressions.py --workspace`` writes is refused (exit 2): it was edited by hand.
    """
    path = state_file(directory, verdict_name(label, theme))
    if not path.exists():
        return None
    raw = path.read_bytes()
    try:
        verdict = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        verdict = None
    if (
        not isinstance(verdict, dict)
        or verdict.get("theme") != theme
        or verdict.get("status") not in VERDICT_STATUSES
        or not isinstance(verdict.get("stops"), list)
    ):
        raise _common.ValidationFailed(
            f"{path.name} is not a check_regressions.py verdict for theme {theme}",
            hint="run check_regressions.py again with --workspace and --theme, or tell the owner it was edited",
        )
    return verdict, hashlib.sha256(raw).hexdigest()[:12]


def acceptance_prefix(theme: str, digest: str) -> str:
    """How the log entry of an owner's acceptance of one lost verdict starts; :func:`run_accept_lost` writes it."""
    return f"theme {theme} lost verdict {digest} accepted by owner"


def lost_checks(verdict: Mapping[str, Any]) -> str:
    return ", ".join(str(row.get("check")) for row in verdict["stops"] if isinstance(row, dict)) or "none listed"


def refuse_unaccepted_loss(state: dict[str, Any], directory: Path, label: str, theme: str, action: str) -> None:
    """Refuse `action` while the theme's latest verdict reads ``lost`` and the owner has not accepted that verdict.

    A theme with no verdict file passes: a run without a base report, or older tools, wrote none (ADR 0005).
    """
    found = read_verdict(directory, label, theme)
    if found is None or found[0]["status"] != "lost":
        return
    verdict, digest = found
    prefix = acceptance_prefix(theme, digest)
    if any(str(entry.get("event", "")).startswith(prefix) for entry in state["log"]):
        return
    raise _refuse(
        f"{action} is refused: theme {theme} lost a pass ({lost_checks(verdict)}) and the owner has not decided",
        "ask the owner: fix it and run check_regressions.py again, accept it with "
        f"accept-lost {theme} --reason TEXT --by owner, or stop the theme",
    )
