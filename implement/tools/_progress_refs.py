# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The ref tips of the target's history (ADR 0007): recording them, reading them and finding the refs that lost history."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

import _common
import validate_report
from _progress_state import (
    MAX_REF_TIPS_BYTES,
    REF_NAMESPACES,
    REF_TIPS_SUFFIX,
    state_file,
    state_names,
    sweep_temporaries,
)
from _progress_transitions import _refuse


def try_ref_tips(target: Path) -> tuple[dict[str, str] | None, list[str]]:
    """The target's ref tips for `init` and `adopt`, or None and a warning when git cannot list them."""
    try:
        return target_ref_tips(target), []
    except _common.UsageError as exc:
        return None, [f"no ref tips recorded, so verify-refs cannot guard the history: {exc}"]


# --- Ref tips (ADR 0007) ----------------------------------------------------------------------------------

REF_TIP = re.compile(r"^[0-9a-f]{12}\Z")
REF_NAME = re.compile(r"^refs/(heads|tags|remotes/origin)/[^\x00-\x1f\x7f]+\Z")


def ref_tips_name(label: str) -> str:
    """The file name of the ref tips recorded for one state, beside it in the workspace."""
    state_names(label)  # refuses a label that is not a file name
    return label + REF_TIPS_SUFFIX


def target_ref_tips(target: Path) -> dict[str, str]:
    """Each branch, tag and origin branch of `target`, with the first 12 digits of the object it names.

    Read-only git. A symbolic ref such as ``origin/HEAD`` is left out. A target that is not the top folder of a git
    work tree is refused (exit 1): its refs would be another repository's.
    """
    top = validate_report.git_toplevel(target)
    if top != target:
        raise _refuse(
            f"the target is not the top folder of a git work tree: {target}",
            "pass the repository's root folder to --target",
        )
    done = validate_report.git_output(
        target, ["for-each-ref", "--format=%(refname)%00%(objectname)%00%(symref)", *REF_NAMESPACES]
    )
    if done is None or done.returncode != 0:
        why = done.stderr.strip() if done is not None else "git did not run"
        raise _refuse(f"git could not list the refs of {target}: {why}")
    tips: dict[str, str] = {}
    for line in done.stdout.splitlines():
        name, _, rest = line.partition("\0")
        objectname, _, symref = rest.partition("\0")
        if name and objectname and not symref:
            tips[name] = objectname[: validate_report.SHORT_SHA_CHARS]
    return tips


def encode_ref_tips(label: str, recorded: str, tips: Mapping[str, str]) -> str:
    document = {
        "tool": "progress",
        "kind": "ref-tips",
        "label": label,
        "recorded": recorded,
        "refs": [{"ref": ref, "tip": tips[ref]} for ref in sorted(tips)],
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def read_ref_tips(directory: Path, label: str) -> dict[str, Any] | None:
    """The ref tips recorded beside the state: ``{"recorded": date, "refs": {ref: tip}}``. None when there is no file.

    A file that is not one this tool writes is refused (exit 2): it was edited by hand.
    """
    path = state_file(directory, ref_tips_name(label))
    if not path.exists():
        return None
    if path.stat().st_size > MAX_REF_TIPS_BYTES:
        raise _common.ValidationFailed(f"{path.name} is larger than {MAX_REF_TIPS_BYTES} bytes")
    try:
        document = json.loads(path.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        document = None
    entries = document.get("refs") if isinstance(document, dict) else None
    if not (
        isinstance(document, dict)
        and (document.get("tool"), document.get("kind"), document.get("label")) == ("progress", "ref-tips", label)
        and isinstance(document.get("recorded"), str)
        and isinstance(entries, list)
        and all(
            isinstance(entry, dict)
            and isinstance(entry.get("ref"), str)
            and REF_NAME.match(entry["ref"])
            and isinstance(entry.get("tip"), str)
            and REF_TIP.match(entry["tip"])
            for entry in entries
        )
    ):
        raise _common.ValidationFailed(
            f"{path.name} is not a ref record that progress.py wrote",
            hint="tell the owner it was edited; record-refs records new tips only when the file is gone",
        )
    refs = {entry["ref"]: entry["tip"] for entry in entries}
    if len(refs) != len(entries):
        raise _common.ValidationFailed(f"{path.name} lists a ref twice")
    return {"recorded": document["recorded"], "refs": refs}


def refuse_existing_ref_tips(directory: Path, label: str) -> Path:
    """The path of the ref record for `label`, refusing one that exists: it is never replaced by a new recording."""
    path = state_file(directory, ref_tips_name(label))
    if path.exists():
        raise _refuse(
            f"a ref record already exists: {path}; it is never replaced",
            "move it aside with the old state files to start a new run",
        )
    return path


def write_ref_tips(path: Path, label: str, recorded: str, tips: Mapping[str, str]) -> None:
    sweep_temporaries(path.parent, (path.name,))
    _common.atomic_write_text(path, encode_ref_tips(label, recorded, tips))


def ref_problems(target: Path, recorded: Mapping[str, str], current: Mapping[str, str]) -> list[dict[str, Any]]:
    """Each recorded ref that lost history: gone, a branch that no longer contains its recorded tip, or a moved tag."""
    problems: list[dict[str, Any]] = []
    for ref, tip in sorted(recorded.items()):
        now = current.get(ref)
        if now == tip:
            continue
        if now is None:
            what, line = "gone", f"{ref} is gone; it pointed at {tip}"
        elif ref.startswith("refs/tags/"):
            what, line = "moved", f"{ref} pointed at {tip} and now points at {now}"
        else:
            done = validate_report.git_output(target, ["merge-base", "--is-ancestor", tip, now])
            if done is not None and done.returncode == 0:
                continue  # it moved forward: the recorded tip is still in its history
            gone = done is None or done.returncode != 1
            what = "rewritten"
            line = (
                f"{ref} no longer contains its recorded tip {tip}; it is now {now}"
                + (" (the recorded tip is no longer in the repository)" if gone else "")
                + ": a rebase, an amend, a reset or a forced push"
            )
        problems.append({"ref": ref, "what": what, "recorded": tip, "now": now, "line": line})
    return problems


def recorded_ref_tips(directory: Path, label: str) -> dict[str, Any]:
    found = read_ref_tips(directory, label)
    if found is None:
        raise _refuse(
            f"no ref tips are recorded for {label} in {directory}, so the history check did not run",
            "record them now with: progress.py record-refs --target REPO --workspace DIR --phase P; "
            "refs are checked from then on",
        )
    return found


def target_outside_workspace(args: Any, workspace: Path) -> Path:
    target = _common.resolve_target(args.target)
    if _common.is_within(target, workspace):
        raise _common.PathNotAllowed(f"the workspace is inside the target: {workspace}")
    return target
