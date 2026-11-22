# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The `theme` and `accept-lost` commands."""

from __future__ import annotations

from typing import Any, Callable

import _common
from _progress_transitions import (
    THEME_ORDER,
    _refuse,
    acceptance_prefix,
    lost_checks,
    open_state,
    read_verdict,
    record,
    refuse_unaccepted_loss,
    require_owner,
    short,
)


def run_theme(args: Any, commit: Callable[..., _common.Result]) -> _common.Result:
    label, path, state = open_state(args)
    theme = next(entry for entry in state["themes"] if entry["id"] == args.theme)
    old, new = theme["status"], args.status
    if THEME_ORDER.index(new) <= THEME_ORDER.index(old):
        raise _refuse(
            f"theme {args.theme} is {old} and a theme only moves forward ({' to '.join(THEME_ORDER)})",
            "" if old != new else "it is already there",
        )
    branch = args.branch or theme["branch"]
    pr = args.pr if args.pr is not None else theme["pr"]
    merged_sha = args.merged_sha or theme["merged_sha"]
    if branch is None:
        raise _refuse(f"theme {args.theme} to {new} needs --branch")
    if new in ("pr_open", "merged") and pr is None:
        raise _refuse(f"theme {args.theme} to {new} needs --pr")
    if new == "merged" and merged_sha is None:
        raise _refuse(f"theme {args.theme} to merged needs --merged-sha")
    if new != "merged" and args.merged_sha:
        raise _refuse("--merged-sha belongs to the merged status")
    if new == "merged":
        refuse_unaccepted_loss(state, path.parent, label, args.theme, f"theme {args.theme} to merged")
    theme.update(status=new, phase=args.phase, branch=branch, pr=pr, merged_sha=merged_sha if new == "merged" else None)
    detail = ", ".join(
        part
        for part in (
            f"branch {branch}",
            f"PR #{pr}" if pr else "",
            f"merged as {merged_sha}" if merged_sha and new == "merged" else "",
        )
        if part
    )
    record(state, args, f"theme {args.theme} {old} to {new}: {detail}")
    return commit(args, label, path, state, f"theme {args.theme} {old} to {new}")


def run_accept_lost(args: Any, commit: Callable[..., _common.Result]) -> _common.Result:
    """`accept-lost`: the owner accepts the theme's latest ``lost`` verdict, with a reason, in one log entry."""
    require_owner(args, "accept-lost")
    label, path, state = open_state(args)
    found = read_verdict(path.parent, label, args.theme)
    if found is None:
        raise _refuse(f"theme {args.theme} has no verdict to accept", "run check_regressions.py with --workspace")
    verdict, digest = found
    if verdict["status"] != "lost":
        raise _refuse(f"theme {args.theme}'s verdict is {verdict['status']}; there is no lost pass to accept")
    prefix = acceptance_prefix(args.theme, digest)
    if any(str(entry.get("event", "")).startswith(prefix) for entry in state["log"]):
        raise _refuse(f"the owner already accepted theme {args.theme}'s verdict {digest}")
    record(state, args, f"{prefix} ({short(lost_checks(verdict))}): {short(args.reason)}")
    return commit(args, label, path, state, f"theme {args.theme} lost verdict {digest} accepted by owner")
