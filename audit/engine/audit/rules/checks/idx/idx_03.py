# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""IDX-03: Index freshness."""

from __future__ import annotations

import datetime as dt
import re
import subprocess
from pathlib import Path

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.idx._shared import (
    _candidate_dbs,
    _finding,
    _locate_store,
    _outcome,
    _read_projects,
    _resolve,
    _shown,
    _unknown,
)

SPEC = declare("IDX-03", "Index freshness", "C", Severity.DEGRADER)

#: Column names that would carry an indexed git revision, if a store records one.
_GIT_COLUMN_RE = re.compile(r"(?i)(?:git[_ -]?sha|sha[_ -]?git|revision|commit)")


#: The column of a store's ``projects`` row that records when the project was indexed.
_INDEXED_AT_COLUMN = "indexed_at"


def _match_project(rows: list[dict], target) -> dict | None:
    """The store row whose recorded root resolves to the target root, if any."""
    wanted = target.path.resolve()
    for row in rows:
        root = row.get("root_path")
        if root and _resolve(str(root)) == wanted:
            return row
    return None


# ===========================================================================
# IDX-03 — index freshness (Tier C)
# ===========================================================================


def _indexed_git_sha(store: Path, target) -> tuple[str | None, str, dict | None]:
    """The store's recorded git revision for the target, or ``(None, reason, row)``.

    The comparison is only possible when a store exposes a revision column; today's schema records a
    project's root and index time only, and that absence is reported rather than guessed. ``row`` is the
    matching project row, for the time-based comparison, or ``None`` when no row matches.
    """
    dbs = _candidate_dbs(store)
    if not dbs:
        return (
            None,
            f"no readable index database at {_shown(store, target)} (a .zst artifact needs zstd, which the standard library lacks)",
            None,
        )

    columns: list[str] = []
    found: dict | None = None
    for db in dbs:
        rows = _read_projects(db)
        if rows is None:
            continue
        if rows and not columns:
            columns = sorted(rows[0].keys())
        match = _match_project(rows, target)
        if match is None:
            continue
        found = match
        for key, value in match.items():
            if _GIT_COLUMN_RE.search(key) and value:
                return str(value), f"column {key!r}", match
        break

    if found is None:
        return None, "no project matching this checkout was found in the index store", None
    return (
        None,
        f"the store records project root and index time but no git revision (columns: {', '.join(columns) or 'unknown'})",
        found,
    )


def _git_query(path: Path, *args: str) -> str | None:
    """A read-only git query in ``path``; ``None`` when git is absent or fails."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "--no-optional-locks", *args],
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _head_moved_at(path: Path) -> int | None:
    """When HEAD last moved, in Unix seconds: the later of HEAD's committer time and its newest reflog entry.

    A checkout of an older commit after the index ran keeps an old committer time, so the reflog entry is what
    shows that HEAD moved. A clone with no reflog falls back to the committer time.
    """
    times: list[int] = []
    committed = _git_query(path, "log", "-1", "--format=%ct", "HEAD")
    if committed and committed.isdigit():
        times.append(int(committed))
    moved = re.fullmatch(
        r"HEAD@\{(\d+)\}", _git_query(path, "log", "-g", "-1", "--date=unix", "--format=%gd", "HEAD") or ""
    )
    if moved:
        times.append(int(moved.group(1)))
    return max(times) if times else None


def _parse_time(value: object) -> dt.datetime | None:
    """An ISO 8601 index time as an aware UTC datetime; ``None`` when it is missing or cannot be read."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def _stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _time_based(spec, store: Path, target, row: dict, reason: str) -> CheckOutcome:
    """IDX-03 by time, when the store records no revision: the index time against the time HEAD last moved."""
    indexed = _parse_time(row.get(_INDEXED_AT_COLUMN))
    if indexed is None:
        return _unknown(spec, f"indexed revision cannot be compared to HEAD: {reason}, and no readable index time")
    moved_at = _head_moved_at(target.path)
    if moved_at is None:
        return _unknown(spec, "indexed revision cannot be compared to HEAD: git gives no time for HEAD")
    head = dt.datetime.fromtimestamp(moved_at, dt.timezone.utc)
    if indexed >= head:
        return _outcome(
            spec,
            Verdict.PASS,
            f"index built at {_stamp(indexed)}, at or after HEAD last moved ({_stamp(head)}); the store records no "
            "revision, so this is a time comparison and does not cover uncommitted edits made since",
        )
    return _outcome(
        spec,
        Verdict.PARTIAL,
        f"index built at {_stamp(indexed)}, before HEAD last moved ({_stamp(head)}); the store records no revision, "
        "so the graph may not match HEAD",
        [
            _finding(
                spec,
                "trust the graph to reflect the current revision",
                f"the index was built at {_stamp(indexed)}, before HEAD last moved at {_stamp(head)}",
                Verdict.PARTIAL,
                [Evidence(_shown(store, target), note=f"indexed_at {_stamp(indexed)}; HEAD moved {_stamp(head)}")],
                "Re-index this checkout so the graph matches HEAD.",
            )
        ],
    )


def check_idx03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if target.git_sha is None:
        return _unknown(spec, "target is not a git repository, so there is no HEAD for the index to match")

    if not session.enabled:
        return _unknown(
            spec,
            "index freshness is a Tier-C probe; re-run with --run-gates to compare the indexed revision against HEAD",
        )

    store, searched = _locate_store(target, session)
    if store is None:
        return _unknown(spec, f"index store could not be located; searched: {', '.join(searched)}")

    sha, reason, row = _indexed_git_sha(store, target)
    if sha is None and row is not None:
        return _time_based(spec, store, target, row, reason)
    if sha is None:
        return _unknown(spec, f"indexed revision cannot be compared to HEAD: {reason}")
    if sha == target.git_sha:
        return _outcome(spec, Verdict.PASS, f"indexed revision {sha} equals HEAD")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"indexed revision {sha} does not match HEAD {target.git_sha}",
        [
            _finding(
                spec,
                "trust the graph to reflect the current revision",
                f"the index was built at {sha} but HEAD is {target.git_sha}",
                Verdict.FAIL,
                [Evidence(str(store), note=f"indexed {sha}; HEAD {target.git_sha}")],
                "Re-index this checkout so the graph matches HEAD.",
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at

    return Reads(
        where=(
            *_at(
                ROOT,
                ".codebase-memory/graph.db.zst",
                unexercised="IDX-03 looks for the store only as a Tier-C probe (--run-gates) on a git target, and "
                "the recording runs no probe",
            ),
        ),
        what=What("exists"),
        binding="file",
        note=(
            "The store of IDX-02 (no repository text); a git-revision column of the matching project row is "
            "compared with HEAD as a probe. With no such column, its indexed_at is compared with the time HEAD "
            "last moved (git's committer time and reflog)."
        ),
    )
