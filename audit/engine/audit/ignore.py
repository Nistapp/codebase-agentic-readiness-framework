# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""git-aware tracked-file access and a documented-subset ignore matcher.

Scope contract
--------------
This is a read-only helper layer for the walk and the checks that need to know *which files matter*: which
paths git tracks (SEC-01/03, EXEC-05, the walk) and whether an ignore rule covers a path (the walk, DOC-03,
CON-03, SEC-01, SEC-03). It never writes to the target, never mutates a git repository, never installs anything,
and makes no network request.

Documented subset
-----------------
The **scoped** matcher (ADR-0009) is the one answer to "is this path ignored?": :func:`load_scoped_rules` reads the
root ignore files and the nested ``.gitignore`` files it is given, :func:`load_ignore_file` reads one more as the
walk enters its directory, and :func:`decide` applies them in git's order (the deepest file and the last line win;
an ignored parent directory cannot be re-included) with anchoring, directory-only rules, ``*``, ``?``, ``[...]``
and ``**`` interpreted. :func:`decide_path` answers for one path whose parents are already decided. The matcher is
a parser: it never runs ``git check-ignore`` and reads neither ``.git/info/exclude`` nor a global excludes file, so a
negative answer is still a parser answer.

Callers that need certainty must treat a negative or ambiguous answer as ``UNKNOWN`` — never as
``PASS``. When git is unavailable, the target is not a repository, or the command fails,
:func:`tracked_files` returns ``None`` so callers degrade to ``UNKNOWN`` rather than infer.
"""

from __future__ import annotations

import functools
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

#: Ignore files lifted from the target, in load order. Mirrors the historical set in ``audit.scan``.
IGNORE_FILE_NAMES: tuple[str, ...] = (
    ".gitignore",
    ".cbmignore",
    ".cursorignore",
    ".aiderignore",
    ".rooignore",
)


@dataclass(frozen=True)
class IgnoreRule:
    """One ignore line and the file it came from.

    ``negated`` marks a ``!`` line, ``dir_only`` a trailing-slash rule, and ``base`` is the directory the ignore
    file sits in (repository-relative, no trailing slash; ``""`` for a root file).
    """

    pattern: str
    source: str
    base: str = ""
    negated: bool = False
    dir_only: bool = False


@dataclass(frozen=True)
class IgnoreDecision:
    """The answer of :func:`decide`: whether a path is ignored, by which rule, and whether a ``!`` rescued it."""

    ignored: bool
    rule: IgnoreRule | None = None
    reincluded: bool = False


def tracked_files(target: Path) -> set[str] | None:
    """Repository-relative paths git tracks under ``target``, or ``None`` when git cannot answer.

    ``None`` is a first-class answer: the target may not be a repository, git may be absent, or the
    command may fail. Callers must then degrade to ``UNKNOWN`` and never infer a tracked set.
    The command is invoked with an argument vector — no user input is ever passed through a shell.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(target), "ls-files", "-z"],
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return {entry for entry in proc.stdout.split("\0") if entry}


# ---------------------------------------------------------------------------
# Scoped matcher (ADR-0009)
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1024)
def _glob_regex(body: str) -> re.Pattern[str]:
    """Translate a gitignore glob body into a regex: ``*``/``?`` stop at ``/``, ``**`` crosses it."""
    out: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        char = body[i]
        if char == "*":
            if body.startswith("**", i):
                j = i + 2
                if body.startswith("/", j) and (i == 0 or body[i - 1] == "/"):
                    out.append("(?:.*/)?")
                    i = j + 1
                    continue
                out.append(".*")
                i = j
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "[":
            end = body.find("]", i + 2)
            if end == -1:
                out.append(re.escape(char))
            else:
                klass = body[i + 1 : end]
                if klass.startswith("!"):
                    klass = "^" + klass[1:]
                out.append("[" + klass.replace("\\", "\\\\") + "]")
                i = end
        elif char == "\\" and i + 1 < n:
            i += 1
            out.append(re.escape(body[i]))
        else:
            out.append(re.escape(char))
        i += 1
    return re.compile("".join(out), re.DOTALL)


def _parse_line(raw: str, base: str, source: str) -> IgnoreRule | None:
    line = raw.rstrip("\r\n").strip()
    if not line or line.startswith("#"):
        return None
    negated = line.startswith("!")
    if negated:
        line = line[1:]
    elif line.startswith("\\#") or line.startswith("\\!"):
        line = line[1:]
    dir_only = line.endswith("/")
    line = line.rstrip("/")
    if not line:
        return None
    return IgnoreRule(pattern=line, source=source, base=base, negated=negated, dir_only=dir_only)


def load_scoped_rules(root: Path, nested: Iterable[str] = ()) -> list[IgnoreRule]:
    """Every rule of every ignore file, scoped to the directory of its file, in application order.

    The root files are the ones in :data:`IGNORE_FILE_NAMES`; ``nested`` lists repository-relative paths of
    further ``.gitignore`` files the scan saw (only ``.gitignore`` is nested: the other names are tool files
    read at the root). Files are ordered shallowest first and lines in file order, so the last matching
    rule is the deepest and latest one, which is git's precedence.
    """
    files: list[tuple[str, str]] = [(name, "") for name in IGNORE_FILE_NAMES]
    for rel in sorted(set(nested)):
        if rel.rsplit("/", 1)[-1] == ".gitignore" and "/" in rel:
            files.append((rel, rel.rsplit("/", 1)[0]))
    files.sort(key=lambda item: (item[1].count("/") + 1 if item[1] else 0, item[0]))
    rules: list[IgnoreRule] = []
    for rel, base in files:
        rules.extend(_read_rules(root, rel, base))
    return rules


def load_ignore_file(root: Path, rel: str) -> list[IgnoreRule]:
    """The rules of the one nested ``.gitignore`` at ``rel``, scoped to its directory, in file order.

    The walk calls it as it enters a directory, after the root files of :func:`load_scoped_rules`; a parent
    directory is always entered before its children, so the rules stay in git's order.
    """
    return _read_rules(root, rel, rel.rsplit("/", 1)[0] if "/" in rel else "")


def _read_rules(root: Path, rel: str, base: str) -> list[IgnoreRule]:
    path = root / rel
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [rule for rule in (_parse_line(raw, base, rel) for raw in lines) if rule is not None]


def _rule_matches(rule: IgnoreRule, rel: str, is_dir: bool) -> bool:
    if rule.dir_only and not is_dir:
        return False
    if rule.base:
        if not rel.startswith(rule.base + "/"):
            return False
        rel = rel[len(rule.base) + 1 :]
    body = rule.pattern
    anchored = body.startswith("/") or "/" in body
    body = body.lstrip("/")
    regex = _glob_regex(body)
    if anchored:
        return regex.fullmatch(rel) is not None
    return regex.fullmatch(rel.rsplit("/", 1)[-1]) is not None


def decide_path(rel: str, rules: list[IgnoreRule], *, is_dir: bool = False) -> IgnoreDecision:
    """Whether the rules ignore ``rel`` itself, without looking at its parent directories.

    The walk asks this: it never enters an ignored directory unless git tracks a file in it, so the parents of a
    path it meets are already decided.
    """
    return _decide_one(rel, is_dir, rules)


def _decide_one(rel: str, is_dir: bool, rules: list[IgnoreRule]) -> IgnoreDecision:
    winner: IgnoreRule | None = None
    positive: IgnoreRule | None = None
    for rule in rules:
        if _rule_matches(rule, rel, is_dir):
            winner = rule
            if not rule.negated:
                positive = rule
    if winner is None:
        return IgnoreDecision(False)
    if winner.negated:
        return IgnoreDecision(False, winner, reincluded=positive is not None)
    return IgnoreDecision(True, winner)


def decide(rel: str, rules: list[IgnoreRule], *, is_dir: bool = False) -> IgnoreDecision:
    """Whether ``rel`` is ignored under ``rules``, applying git's order.

    A parent directory that is ignored hides everything under it; a ``!`` rule cannot bring a file back out of an
    ignored directory. ``reincluded`` is true when a ``!`` rule overrode an earlier ignore rule for the path
    itself, which is how a tracked ``README.md`` beside a ``*`` rule is told apart from a stray tracked file.
    """
    parts = rel.strip("/").split("/")
    for index in range(1, len(parts)):
        parent = _decide_one("/".join(parts[:index]), True, rules)
        if parent.ignored:
            return parent
    return _decide_one("/".join(parts), is_dir, rules)
