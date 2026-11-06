# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""git-aware tracked-file access and a documented-subset ignore matcher.

Scope contract
--------------
This is a read-only helper layer for checks that need to know *which files matter*: which paths git
tracks (SEC-01/03, EXEC-05) and whether an ignore rule covers a path (DOC-03, CON-03). It never
writes to the target, never mutates a git repository, never installs anything, and makes no network
request.

Documented subset
-----------------
Ignore matching implements the same **documented subset** of gitignore semantics that
``audit.scan`` has always used, and deliberately does not overclaim:

* a rule is matched with :func:`fnmatch.fnmatch` against both the repository-relative path and the
  basename;
* **anchored** patterns (``/dist``) are not interpreted as anchored and may therefore fail to match
  the path they were written for;
* **negation** lines (``!keep``) are dropped entirely, so a later ``!`` cannot re-include a path;
* ``**`` is treated as a plain glob, not the gitignore "any depth" operator.

That is the **walk** matcher (:func:`load_ignore_rules`, :func:`is_ignored`), kept exactly as it was so the
traversal does not shift (ADR-0006). The checks that ask "is this path ignored?" (DOC-03, CON-03, SEC-01,
SEC-03) use the **scoped** matcher instead (ADR-0009): :func:`load_scoped_rules` reads every ``.gitignore``
the scan saw, scopes each file's rules to its directory, and :func:`decide` applies them in git's order
(the deepest file and the last line win; an ignored parent directory cannot be re-included) with anchoring,
directory-only rules, ``*``, ``?``, ``[...]`` and ``**`` interpreted. Both matchers are parsers: neither runs
``git check-ignore``, so a negative answer is still a parser answer.

Callers that need certainty must treat a negative or ambiguous answer as ``UNKNOWN`` — never as
``PASS``. When git is unavailable, the target is not a repository, or the command fails,
:func:`tracked_files` returns ``None`` so callers degrade to ``UNKNOWN`` rather than infer.
"""

from __future__ import annotations

import fnmatch
import functools
import os
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

    The walk loader only yields non-negated root rules, so ``base`` is ``""`` and ``negated`` is false there.
    The scoped loader also yields ``!`` lines (``negated``), trailing-slash rules (``dir_only``) and the
    directory the ignore file sits in (``base``, repository-relative, no trailing slash).
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


def load_ignore_rules(root: Path) -> list[IgnoreRule]:
    """Load the documented-subset rules from every ignore file present in ``root``.

    Behaviour is preserved from ``audit.scan``: blank lines and comments are skipped, and a leading
    ``!`` drops the line rather than being interpreted as negation.
    """
    rules: list[IgnoreRule] = []
    for name in IGNORE_FILE_NAMES:
        path = root / name
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if line and not line.startswith("#") and not line.startswith("!"):
                rules.append(IgnoreRule(pattern=line.rstrip("/"), source=name))
    return rules


def ignore_patterns(root: Path) -> list[str]:
    """The bare patterns, for callers that only need the historical list shape."""
    return [rule.pattern for rule in load_ignore_rules(root)]


def matching_rules(rel: str, rules: list[IgnoreRule]) -> list[IgnoreRule]:
    """Every rule that covers ``rel``, carrying the ignore file each one came from.

    This is the "does any ignore file cover this path?" answer DOC-03 and CON-03 need.
    """
    base = os.path.basename(rel)
    return [rule for rule in rules if fnmatch.fnmatch(rel, rule.pattern) or fnmatch.fnmatch(base, rule.pattern)]


def is_ignored(rel: str, patterns: list[str]) -> bool:
    """Historical pattern matcher, unchanged, so ``audit.scan`` keeps walking exactly what it did."""
    base = os.path.basename(rel)
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(base, p) for p in patterns)


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
        path = root / rel
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for raw in lines:
            rule = _parse_line(raw, base, rel)
            if rule is not None:
                rules.append(rule)
    return rules


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
