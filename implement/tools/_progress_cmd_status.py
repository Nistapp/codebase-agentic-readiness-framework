# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The `set-status`, `skip`, `unskip`, `defer` and `undefer` commands."""

from __future__ import annotations

from typing import Any, Callable

import _common
from _progress_state import OWNER_ONLY
from _progress_transitions import (
    _refuse,
    apply_status,
    find_item,
    open_state,
    owner_move,
    record,
    refuse_unaccepted_loss,
    require_owner,
    short,
    stamp,
)


def run_set_status(args: Any, commit: Callable[..., _common.Result]) -> _common.Result:
    label, path, state = open_state(args)
    item = find_item(state, args.finding)
    old = item["status"]
    apply_status(item, args.status, args)
    if args.status == "done" and old != "done":
        refuse_unaccepted_loss(state, path.parent, label, item["theme"], f"{args.finding} to done")
    stamp(item, args)
    if old == args.status:
        record(state, args, f"{args.finding} note added by {args.by}: {short(args.note)}")
        return commit(args, label, path, state, f"{args.finding} note added at {old}")
    why = f": {short(args.reason)}" if args.reason else ""
    record(state, args, f"{args.finding} {old} to {args.status} by {args.by}{why}")
    return commit(args, label, path, state, f"{args.finding} {old} to {args.status}")


def run_owner_move(args: Any, commit: Callable[..., _common.Result]) -> _common.Result:
    new = {"skip": "skipped", "unskip": "queued", "defer": "deferred", "undefer": "queued"}[args.command]
    require_owner(args, args.command)
    if new in OWNER_ONLY and not args.reason:
        raise _refuse(f"{args.command} needs --reason")
    label, path, state = open_state(args)
    item = find_item(state, args.finding)
    old = item["status"]
    owner_move(item, new, args)
    stamp(item, args)
    why = f": {short(args.reason)}" if args.reason else ""
    record(state, args, f"{args.finding} {old} to {new} by owner{why}")
    return commit(args, label, path, state, f"{args.finding} {old} to {new}")
