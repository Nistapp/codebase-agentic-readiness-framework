# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Renumber the ruleset revisions a branch adds, so two engine branches merge without hand work.

    ruleset_renumber.py check [--base REF] [--root DIR]
    ruleset_renumber.py apply [--base REF] [--root DIR]

Each engine change that moves a verdict adds a revision (``2026-11-20.25``) to ``__ruleset_revision__`` and one row to
the top of ``audit/engine/docs/reference/changelog.md``. Two branches that each add one take the same next number.
This tool finds the revisions the branch adds and moves them after the newest revision of the base.

A branch row is a changelog row of ``HEAD`` that is neither in the merge base nor in the base ref. A base row is any
row the base ref added since the merge base. The tool reads ``HEAD`` and the base ref from git, so it works before the
merge, in the middle of a conflicted merge and after a clean merge.

``check`` is read-only. It lists the branch's revisions and each tracked file that names one, and exits 2 when a
branch revision also exists on the base (a collision), when two changelog rows share a revision, or when the rows are
not newest first.

``apply`` gives each branch revision that is not above the base's newest one the next free number after it. Then it
rewrites, in the working tree and without staging:

* the changelog: branch rows only, by whole line (a row the base has is never touched). A conflict hunk keeps both
  sides, branch rows first;
* the three places that hold the current revision (``__ruleset_revision__``, ``ruleset_revision`` in
  ``.audit-baseline.json`` and the ``Ruleset`` row of ``docs/reference/self-audit.md``): set to the newest revision;
* the other lines of these files that name a renumbered revision, unless the base has the same line.

It prints each change. A file that names a branch revision and that it does not know how to rewrite is reported and
the exit code is 2; it never guesses. So is a conflict hunk in a file other than the changelog and the engine's
``__init__.py`` (regenerate those with ``make self-audit`` and ``make update-audit-baseline``).
``apply`` refuses a dirty tree, unless the only changes are the unmerged files it handles and the files a merge in
progress has staged. A rebase in progress is refused. Dev-only; standard library only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

CHANGELOG = "audit/engine/docs/reference/changelog.md"
INIT = "audit/engine/audit/__init__.py"
BASELINE = ".audit-baseline.json"
SELF_AUDIT = "docs/reference/self-audit.md"
#: Files whose lines ``apply`` knows how to rewrite.
HANDLED = (CHANGELOG, INIT, BASELINE, SELF_AUDIT, "audit/catalogue.json")
_REV = r"\d{4}-\d{2}-\d{2}\.[1-9]\d*"
_ROW = re.compile(rf"^\| `({_REV})` \|")
_INIT_LINE = re.compile(rf'^(__ruleset_revision__ = ")({_REV})(")')
_BASELINE_LINE = re.compile(rf'^(\s*"ruleset_revision": ")({_REV})(")')
_SELF_AUDIT_LINE = re.compile(rf"^(\| Ruleset \| `)({_REV})(`)")
_CURRENT = ((INIT, _INIT_LINE), (BASELINE, _BASELINE_LINE), (SELF_AUDIT, _SELF_AUDIT_LINE))
_MARK_OURS, _MARK_MID, _MARK_THEIRS = "<<<<<<<", "=======", ">>>>>>>"


class UsageError(Exception):
    """Bad input or a refusal (exit 1)."""


def key(revision: str) -> tuple[str, int]:
    """Sort key: the date, then the number within the day."""
    day, number = revision.split(".")
    return day, int(number)


def _git(root: Path, *args: str, check: bool = True) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    if check and done.returncode != 0:
        raise UsageError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def _show(root: Path, ref: str, path: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "show", f"{ref}:{path}"], capture_output=True, text=True, check=False
    )
    return done.stdout if done.returncode == 0 else ""


def row_lines(text: str) -> list[str]:
    """The changelog table rows of ``text``, in page order."""
    return [line for line in text.splitlines() if _ROW.match(line)]


def row_revision(line: str) -> str:
    match = _ROW.match(line)
    assert match is not None
    return match.group(1)


@dataclass
class Analysis:
    """What ``HEAD`` adds over the base."""

    base_newest: str
    branch_rows: list[str] = field(default_factory=list)
    base_revisions: set[str] = field(default_factory=set)
    collisions: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    misordered: bool = False
    hits: dict[str, list[tuple[int, str]]] = field(default_factory=dict)

    @property
    def branch_revisions(self) -> list[str]:
        return sorted({row_revision(r) for r in self.branch_rows}, key=key)

    def plan(self) -> dict[str, str]:
        """Old revision to new revision, for each branch revision that has to move."""
        previous = self.base_newest
        mapping: dict[str, str] = {}
        for old in self.branch_revisions:
            if key(old) > key(previous) and old not in self.base_revisions:
                previous = old
                continue
            day, number = previous.split(".")
            new = f"{day}.{int(number) + 1}"
            mapping[old] = new
            previous = new
        return mapping


def analyse(root: Path, base: str) -> Analysis:
    """Compare ``HEAD`` with ``base`` and search the tracked files for the branch's revisions."""
    merge_base = _git(root, "merge-base", "HEAD", base).strip()
    head_rows = row_lines(_show(root, "HEAD", CHANGELOG))
    old_rows = set(row_lines(_show(root, merge_base, CHANGELOG)))
    base_rows = row_lines(_show(root, base, CHANGELOG))
    if not base_rows:
        raise UsageError(f"no changelog rows at {base}:{CHANGELOG}")
    result = Analysis(base_newest=max((row_revision(r) for r in base_rows), key=key))
    result.branch_rows = [r for r in head_rows if r not in old_rows and r not in set(base_rows)]
    result.base_revisions = {row_revision(r) for r in base_rows}
    result.collisions = [r for r in result.branch_revisions if r in result.base_revisions]
    work = row_lines((root / CHANGELOG).read_text(encoding="utf-8")) if (root / CHANGELOG).exists() else []
    seen: set[str] = set()
    for line in work:
        revision = row_revision(line)
        if revision in seen and revision not in result.duplicates:
            result.duplicates.append(revision)
        seen.add(revision)
    keys = [key(row_revision(line)) for line in work]
    result.misordered = keys != sorted(keys, reverse=True)
    result.hits = _find_hits(root, base, result.branch_revisions)
    return result


def _find_hits(root: Path, base: str, revisions: list[str]) -> dict[str, list[tuple[int, str]]]:
    """Tracked files with a line that names a branch revision and that the base does not have."""
    hits: dict[str, list[tuple[int, str]]] = {}
    for revision in revisions:
        out = _git(root, "grep", "-nIF", "--no-color", revision, check=False)
        for raw in out.splitlines():
            path, _, rest = raw.partition(":")
            number, _, text = rest.partition(":")
            if not number.isdigit() or path.startswith("artefacts/") or path.startswith(".claude/"):
                continue
            if text in _show(root, base, path).splitlines():
                continue
            entry = (int(number), revision)
            if entry not in hits.setdefault(path, []):
                hits[path].append(entry)
    return hits


def unknown_hits(analysis: Analysis) -> dict[str, list[tuple[int, str]]]:
    return {p: h for p, h in analysis.hits.items() if p not in HANDLED}


def report(analysis: Analysis, out: list[str]) -> None:
    out.append(f"base newest revision: {analysis.base_newest}")
    for revision in analysis.branch_revisions:
        tag = " (also on the base)" if revision in analysis.collisions else ""
        out.append(f"branch revision: {revision}{tag}")
    for path, found in sorted(analysis.hits.items()):
        known = "handled" if path in HANDLED else "NOT HANDLED"
        out.append(f"  {path} ({known}): " + ", ".join(f"line {n} {r}" for n, r in found))
    for revision in analysis.duplicates:
        out.append(f"changelog rows share the revision {revision}")
    if analysis.misordered:
        out.append("changelog rows are not newest first")


def cmd_check(root: Path, base: str) -> int:
    analysis = analyse(root, base)
    lines: list[str] = []
    if analysis.branch_rows or analysis.duplicates or analysis.misordered:
        report(analysis, lines)
    for line in lines:
        print(line)
    return 2 if analysis.collisions or analysis.duplicates or analysis.misordered else 0


def _dirty(root: Path) -> list[str]:
    """Status lines that block ``apply``."""
    merging = (root / _git(root, "rev-parse", "--git-path", "MERGE_HEAD").strip()).exists()
    blocking: list[str] = []
    for line in _git(root, "status", "--porcelain").splitlines():
        code, path = line[:2], line[3:]
        unmerged = code in {"UU", "AA", "DU", "UD", "AU", "UA", "DD"}
        if unmerged and path in HANDLED:
            continue
        if merging and not unmerged and code[1] == " ":
            continue  # staged by the merge in progress
        blocking.append(line)
    return blocking


def _resolve_conflicts(text: str, path: str, notes: list[str]) -> tuple[str, bool]:
    """Resolve conflict hunks of the changelog (keep both sides, ours first) and ``__init__.py`` (keep ours)."""
    if _MARK_OURS not in text:
        return text, False
    out: list[str] = []
    side = ""
    ours: list[str] = []
    theirs: list[str] = []
    unresolved = False
    for line in text.splitlines(keepends=True):
        if line.startswith(_MARK_OURS):
            side, ours, theirs = "ours", [], []
        elif line.startswith(_MARK_MID) and side == "ours":
            side = "theirs"
        elif line.startswith(_MARK_THEIRS) and side == "theirs":
            if path == CHANGELOG:
                out += ours + theirs
                notes.append(f"{path}: resolved a conflict hunk, kept both sides")
            elif path == INIT:
                out += ours
                notes.append(f"{path}: resolved a conflict hunk, kept the branch side")
            else:
                out += [_MARK_OURS + "\n", *ours, _MARK_MID + "\n", *theirs, _MARK_THEIRS + "\n"]
                unresolved = True
                notes.append(f"{path}: conflict hunk NOT resolved; regenerate this file")
            side = ""
        elif side == "ours":
            ours.append(line)
        elif side == "theirs":
            theirs.append(line)
        else:
            out.append(line)
    return "".join(out), unresolved


def _rewrite(root: Path, base: str, analysis: Analysis, mapping: dict[str, str], newest: str) -> tuple[list[str], bool]:
    notes: list[str] = []
    failed = False
    branch_rows = set(analysis.branch_rows)
    pattern = re.compile("|".join(re.escape(r) for r in sorted(mapping, key=key, reverse=True))) if mapping else None
    for path in HANDLED:
        target = root / path
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        text, unresolved = _resolve_conflicts(text, path, notes)
        failed = failed or unresolved
        base_lines = set(_show(root, base, path).splitlines())
        current = dict(_CURRENT).get(path)
        changed: list[str] = []
        for number, line in enumerate(text.splitlines(keepends=True), start=1):
            body = line.rstrip("\n")
            new = body
            if path == CHANGELOG:
                if body in branch_rows and pattern is not None:
                    new = pattern.sub(lambda m: mapping[m.group(0)], body, count=1)
            elif current is not None and (m := current.match(body)):
                new = m.group(1) + newest + m.group(3) + body[m.end() :]
            if new == body and path != CHANGELOG and pattern is not None and body not in base_lines:
                new = pattern.sub(lambda m: mapping[m.group(0)], body)
            if new != body:
                notes.append(f"{path}:{number}: {_brief(body)} -> {_brief(new)}")
            changed.append(new + line[len(body) :])
        result = "".join(changed)
        if result != target.read_text(encoding="utf-8"):
            target.write_text(result, encoding="utf-8")
    return notes, failed


def _brief(line: str) -> str:
    return line if len(line) <= 70 else line[:67] + "..."


def cmd_apply(root: Path, base: str) -> int:
    if any(
        (root / _git(root, "rev-parse", "--git-path", d).strip()).exists() for d in ("rebase-merge", "rebase-apply")
    ):
        raise UsageError("a rebase is in progress; the tool reads HEAD as the branch, which a rebase reverses")
    dirt = _dirty(root)
    if dirt:
        raise UsageError("the working tree is dirty; commit or stash first:\n" + "\n".join(dirt))
    analysis = analyse(root, base)
    mapping = analysis.plan()
    newest = analysis.base_newest
    needs_current = False
    if analysis.branch_revisions:
        newest = mapping.get(analysis.branch_revisions[-1], analysis.branch_revisions[-1])
        needs_current = _current_values(root) - {newest} != set()
    unknown = unknown_hits(analysis)
    unmerged = _unmerged_handled(root)
    if not (mapping or analysis.duplicates or needs_current or unmerged or unknown or analysis.misordered):
        print("nothing to renumber")
        return 0
    notes: list[str] = []
    failed = False
    if mapping or analysis.duplicates or needs_current or unmerged:
        notes, failed = _rewrite(root, base, analysis, mapping, newest)
    for old, new in mapping.items():
        print(f"renumber {old} -> {new}")
    for note in notes:
        print(note)
    for path, found in sorted(unknown.items()):
        print(f"cannot rewrite {path}: " + ", ".join(f"line {n} {r}" for n, r in found))
    after = row_lines((root / CHANGELOG).read_text(encoding="utf-8"))
    keys = [key(row_revision(r)) for r in after]
    if keys != sorted(keys, reverse=True) or len(set(keys)) != len(keys):
        print("the changelog rows are still not unique and newest first; fix the order by hand")
        failed = True
    return 2 if failed or unknown else 0


def _current_values(root: Path) -> set[str]:
    """The revisions the three current-revision places hold now."""
    values: set[str] = set()
    for path, pattern in _CURRENT:
        for line in (root / path).read_text(encoding="utf-8").splitlines():
            if (match := pattern.match(line)) is not None:
                values.add(match.group(2))
    return values


def _unmerged_handled(root: Path) -> bool:
    return any(
        line[:2] in {"UU", "AA"} and line[3:] in HANDLED for line in _git(root, "status", "--porcelain").splitlines()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("verb", choices=("check", "apply"))
    parser.add_argument("--base", default="origin/dev", help="the ref the branch merges into (default origin/dev)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        return cmd_check(root, args.base) if args.verb == "check" else cmd_apply(root, args.base)
    except UsageError as err:
        print(f"ruleset_renumber: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
