# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The `record-refs`, `verify-refs` and `accept-ref` commands (ADR 0007)."""

from __future__ import annotations

from typing import Any, Callable

import _common
from _progress_refs import (
    recorded_ref_tips,
    ref_problems,
    ref_tips_name,
    refuse_existing_ref_tips,
    target_outside_workspace,
    target_ref_tips,
    write_ref_tips,
)
from _progress_state import find_state, read_state, state_file, workspace_directory
from _progress_transitions import _refuse, open_state, record, require_owner, short


def run_record_refs(args: Any, commit: Callable[..., _common.Result]) -> _common.Result:
    """`record-refs`: record the target's ref tips for a state that has none, such as one made by older tools."""
    label, path, state = open_state(args)
    target = target_outside_workspace(args, path.parent)
    ref_path = refuse_existing_ref_tips(path.parent, label)
    tips = target_ref_tips(target)
    write_ref_tips(ref_path, label, args.date, tips)
    record(state, args, f"ref tips recorded for {len(tips)} refs of the target")
    result = commit(args, label, path, state, f"recorded the tips of {len(tips)} refs")
    result.data["ref_tips"] = str(ref_path)
    return result


def run_verify_refs(args: Any) -> _common.Result:
    """`verify-refs`: exit 2 when a recorded ref lost history. Reads the target with read-only git; writes nothing."""
    label, path = find_state(workspace_directory(args.workspace), args.label)
    read_state(path)
    target = _common.resolve_target(args.target)
    recorded = recorded_ref_tips(path.parent, label)
    current = target_ref_tips(target)
    problems = ref_problems(target, recorded["refs"], current)
    if problems:
        refs = ", ".join(problem["ref"] for problem in problems)
        raise _common.ValidationFailed(
            short(f"{len(problems)} recorded refs lost history since {recorded['recorded']}: {refs}"),
            errors=[problem["line"] for problem in problems],
            hint="stop and ask the owner: restore the ref, accept it with "
            "accept-ref REF --reason TEXT --by owner, or stop the theme",
        )
    new = sorted(set(current) - set(recorded["refs"]))
    return _common.Result(
        data={"status": "clean", "label": label, "checked": len(recorded["refs"]), "new": len(new)},
        summary=(
            f"progress: {len(recorded['refs'])} recorded refs keep their history; {len(new)} refs are new since "
            f"{recorded['recorded']}"
        ),
    )


def run_accept_ref(args: Any, commit: Callable[..., _common.Result]) -> _common.Result:
    """`accept-ref`: the owner accepts one ref's lost history; its current tip becomes the recorded one."""
    require_owner(args, "accept-ref")
    label, path, state = open_state(args)
    target = target_outside_workspace(args, path.parent)
    recorded = recorded_ref_tips(path.parent, label)
    tips: dict[str, str] = recorded["refs"]
    if args.ref not in tips:
        raise _refuse(
            f"{args.ref} is not a recorded ref; a ref the run created needs no acceptance",
            "name the ref as verify-refs prints it, for example refs/heads/main",
        )
    problem = next(iter(ref_problems(target, {args.ref: tips[args.ref]}, target_ref_tips(target))), None)
    if problem is None:
        raise _refuse(f"{args.ref} still holds its recorded tip {tips[args.ref]}; there is nothing to accept")
    if problem["now"] is None:
        del tips[args.ref]
    else:
        tips[args.ref] = problem["now"]
    now = problem["now"] or "gone"
    record(
        state,
        args,
        f"ref {args.ref} {problem['what']} accepted by owner (recorded {problem['recorded']}, now {now}): "
        f"{short(args.reason)}",
    )
    result = commit(args, label, path, state, f"ref {args.ref} {problem['what']} accepted by owner")
    write_ref_tips(state_file(path.parent, ref_tips_name(label)), label, recorded["recorded"], tips)
    return result
