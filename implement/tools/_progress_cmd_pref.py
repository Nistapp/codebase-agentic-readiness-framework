# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The `pref` command: the owner's preferences."""

from __future__ import annotations

import re
from typing import Any, Callable

import _common
from _progress_transitions import _refuse, open_state, record, require_owner, short


PREF_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def run_pref(args: Any, commit: Callable[..., _common.Result]) -> _common.Result:
    require_owner(args, f"pref {args.action}")
    if not PREF_KEY.match(args.key):
        raise _common.ValidationFailed(
            f"the change would make the state invalid: {args.key!r} is not a preference key",
            hint="keys are lower case letters, digits, dot, underscore and hyphen (at most 64, not starting with a "
            "symbol), for example node.version-file",
        )
    if args.action == "set" and args.value is None:
        raise _refuse("pref set needs a value: pref set KEY VALUE --reason TEXT")
    if args.action == "unset" and args.value is not None:
        raise _refuse("pref unset takes only the key")
    label, path, state = open_state(args)
    existing = next((pref for pref in state["preferences"] if pref["key"] == args.key), None)
    if args.action == "unset":
        if existing is None:
            raise _refuse(f"there is no preference {args.key}")
        state["preferences"].remove(existing)
        record(state, args, f"preference {args.key} unset: {short(args.reason)}")
        return commit(args, label, path, state, f"unset preference {args.key}")
    entry = {
        "key": args.key,
        "value": args.value,
        "reason": args.reason,
        "by": "owner",
        "date": args.date,
        "phase": args.phase,
    }
    if existing is None:
        state["preferences"].append(entry)
        record(state, args, f"preference {args.key} set to {short(args.value)}: {short(args.reason)}")
    else:
        if existing["value"] == args.value:
            raise _refuse(f"preference {args.key} already has that value")
        state["preferences"][state["preferences"].index(existing)] = entry
        record(
            state,
            args,
            f"preference {args.key} changed from {short(existing['value'])} to {short(args.value)}: "
            f"{short(args.reason)}",
        )
    return commit(args, label, path, state, f"set preference {args.key}")
