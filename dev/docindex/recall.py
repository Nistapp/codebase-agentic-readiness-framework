# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The sweep's recall measure: how many lines that commits removed lie in no normative item at their parent.

The input is a list of commits (:func:`load_commits`), each a JSON object with ``hash``, ``parent`` and ``files``
(other keys are ignored). For each commit and each listed file, :func:`measure`:

1. takes the lines removed by ``git diff --unified=0 <parent> <hash> -- <file>`` (no rename detection, literal
   pathspec), with their line numbers at the parent;
2. keeps a line when it lies outside a code fence of the file at the parent (the fence lines included) and has
   :data:`MIN_CHARS` or more characters once each run of whitespace is one space and the ends are trimmed;
3. sweeps the file at the parent (:func:`docindex.sweep.items_of`, with the selected triggers) and marks the line
   *found* when it is one of the lines of a normative item, else *missed*.

The listed files are the in-scope files of that commit, whatever the sweep scope says, so an old layout works.

:func:`to_json` and :func:`to_text` report, per commit in input order and in total, the removed lines kept, the
missed lines and the share missed (``missed / removed``; ``null`` when no line was kept). The JSON also lists each
kept line: its path, its normalised text, and the address and kind of the item that holds it (``null`` when
missed), sorted by path and line order. The output is deterministic: no timestamp, no absolute path and no line
number. This module imports nothing outside the standard library and this package.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .gitread import GitError, RefTree
from .markdown import parse
from .sweep import Item, items_of

__all__ = [
    "MIN_CHARS",
    "RECALL_FORMAT",
    "Commit",
    "CommitRecall",
    "Removed",
    "load_commits",
    "measure",
    "parse_hunks",
    "removed_lines",
    "to_json",
    "to_text",
]

MIN_CHARS = 25
RECALL_FORMAT = 1

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,(\d+))? @@")
_WHITESPACE = re.compile(r"\s+")


# --- The data -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Commit:
    """One commit of the measure: its hash, its parent and the files it changed that are in scope."""

    hash: str
    parent: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class Removed:
    """One removed line that the measure keeps. ``number`` is its line at the parent, for in-memory use only."""

    path: str
    text: str
    item: Item | None
    number: int = field(default=0, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": None if self.item is None else self.item.address,
            "kind": None if self.item is None else self.item.kind,
            "path": self.path,
            "text": self.text,
        }


@dataclass(frozen=True)
class CommitRecall:
    """The kept removed lines of one commit."""

    commit: Commit
    lines: tuple[Removed, ...]

    @property
    def removed(self) -> int:
        return len(self.lines)

    @property
    def missed(self) -> int:
        return sum(1 for line in self.lines if line.item is None)


def _share(missed: int, removed: int) -> float | None:
    return round(missed / removed, 4) if removed else None


# --- Input ----------------------------------------------------------------------------------------------------------


def load_commits(data: Any) -> list[Commit]:
    """The commits of a parsed COMMITS_JSON: a list of objects with string ``hash`` and ``parent``, and ``files``."""
    if not isinstance(data, list):
        raise ValueError("the commits file must hold a JSON list")
    commits: list[Commit] = []
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"commit {index} is not a JSON object")
        hash_, parent, files = entry.get("hash"), entry.get("parent"), entry.get("files")
        if not isinstance(hash_, str) or not hash_ or not isinstance(parent, str) or not parent:
            raise ValueError(f"commit {index} needs a string hash and parent")
        if not isinstance(files, list) or not all(isinstance(file, str) and file for file in files):
            raise ValueError(f"commit {index} needs a list of file paths at files")
        commits.append(Commit(hash=hash_, parent=parent, files=tuple(files)))
    return commits


# --- Removed lines --------------------------------------------------------------------------------------------------


def parse_hunks(output: str) -> list[tuple[int, str]]:
    """The removed lines of one file's ``git diff --unified=0`` output: (line number at the old side, text)."""
    lines = output.split("\n")
    removed: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        hunk = _HUNK.match(lines[index])
        index += 1
        if hunk is None:
            continue
        start = int(hunk.group(1))
        old_count = 1 if hunk.group(2) is None else int(hunk.group(2))
        new_count = 1 if hunk.group(3) is None else int(hunk.group(3))
        seen_old = seen_new = 0
        while index < len(lines) and (seen_old < old_count or seen_new < new_count):
            line = lines[index]
            if line.startswith("-") and seen_old < old_count:
                removed.append((start + seen_old, line[1:]))
                seen_old += 1
            elif line.startswith("+") and seen_new < new_count:
                seen_new += 1
            elif not line.startswith("\\"):
                break
            index += 1
    return removed


def _git_diff(root: Path, parent: str, commit: str, path: str) -> str:
    command = [
        *("git", "--literal-pathspecs", "-C", str(root), "-c", "core.quotePath=false", "diff", "--no-color"),
        *("--no-ext-diff", "--no-textconv", "--no-renames", "--unified=0", parent, commit, "--", path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, check=False)
    except OSError as exc:
        raise GitError(f"git could not run: {exc}") from None
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip() or f"exit {result.returncode}"
        raise GitError(f"git diff failed: {message}")
    return result.stdout.decode("utf-8", errors="replace")


def removed_lines(root: Path, commit: Commit, triggers: Sequence[str]) -> CommitRecall:
    """The kept removed lines of ``commit`` in its listed files, each marked found or missed."""
    parent_tree = RefTree(root, commit.parent)
    RefTree(root, commit.hash)  # checks that the hash names a commit
    kept: list[Removed] = []
    for path in sorted(set(commit.files)):
        removed = parse_hunks(_git_diff(root, commit.parent, commit.hash, path))
        if not removed:
            continue
        document = parse(path, parent_tree.read(path) or "")
        holder: dict[int, Item] = {}
        for item in items_of(document, triggers):
            for number in item.lines:
                holder.setdefault(number, item)
        for number, raw in removed:
            text = _WHITESPACE.sub(" ", raw).strip()
            if len(text) < MIN_CHARS:
                continue
            if number <= len(document.lines) and document.line(number).fence:
                continue
            kept.append(Removed(path=path, text=text, item=holder.get(number), number=number))
    kept.sort(key=lambda line: (line.path, line.number))
    return CommitRecall(commit=commit, lines=tuple(kept))


def measure(root: Path, commits: Sequence[Commit], triggers: Sequence[str]) -> list[CommitRecall]:
    """The recall of each commit, in input order. A ref that names no commit raises :class:`GitError`."""
    return [removed_lines(root, commit, triggers) for commit in commits]


# --- Output ---------------------------------------------------------------------------------------------------------


def _totals(results: Sequence[CommitRecall]) -> tuple[int, int]:
    return sum(result.removed for result in results), sum(result.missed for result in results)


def to_json(results: Sequence[CommitRecall], *, selection: str) -> str:
    """The measure as deterministic JSON: sorted keys, two-space indent, a final newline."""
    removed, missed = _totals(results)
    data = {
        "commits": [
            {
                "hash": result.commit.hash,
                "lines": [line.to_dict() for line in result.lines],
                "missed": result.missed,
                "parent": result.commit.parent,
                "removed": result.removed,
                "share": _share(result.missed, result.removed),
            }
            for result in results
        ],
        "format": RECALL_FORMAT,
        "min_chars": MIN_CHARS,
        "total": {"commits": len(results), "missed": missed, "removed": removed, "share": _share(missed, removed)},
        "triggers": selection,
    }
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _percent(missed: int, removed: int) -> str:
    return f"{100 * missed / removed:.1f}%" if removed else "-"


def to_text(results: Sequence[CommitRecall], *, selection: str) -> str:
    """The measure as a text table: one row per commit, then the total."""
    lines = [
        f"Removed lines of {MIN_CHARS} or more characters outside code fences, in no normative item "
        f"(triggers: {selection})",
        "",
        f"{'commit':<12}  {'parent':<12}  {'removed':>7}  {'in no item':>10}  {'share':>6}",
    ]
    for result in results:
        commit = result.commit
        lines.append(
            f"{commit.hash[:12]:<12}  {commit.parent[:12]:<12}  {result.removed:>7}  {result.missed:>10}  "
            f"{_percent(result.missed, result.removed):>6}"
        )
    removed, missed = _totals(results)
    lines.append(f"{'total':<12}  {'':<12}  {removed:>7}  {missed:>10}  {_percent(missed, removed):>6}")
    return "\n".join(lines) + "\n"
