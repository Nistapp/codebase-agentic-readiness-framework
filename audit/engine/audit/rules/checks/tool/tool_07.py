# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TOOL-07: Local guard against commits to a protected branch."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import declared_branch_rules
from audit.scan import Kind
from audit.rules.checks.tool._shared import (
    _WIRED_HOOK_FILES,
    _finding,
    _hook_wiring,
    _husky_referenced,
    _outcome,
    _present,
    _unknown,
)

SPEC = declare("TOOL-07", "Local guard against commits to a protected branch", "B", Severity.COSMETIC)


# ===========================================================================
# TOOL-07 — local guard against commits to a protected branch
# ===========================================================================

#: A hook command that reads the branch being committed to.
_BRANCH_READ_RE = re.compile(
    r"git\s+(?:symbolic-ref\b[^\n]*\bHEAD\b|branch\s+--show-current\b|rev-parse\s+--abbrev-ref\s+HEAD\b)"
)

#: Hook scripts by name: ``.husky/``, ``.githooks/`` or any ``core.hooksPath`` directory. A commit-msg hook also
#: stops the commit, so either stage counts; ``pre-push`` does not.
_GUARD_HOOK_NAMES = frozenset({"pre-commit", "commit-msg"})

#: pre-commit-hooks' ``no-commit-to-branch`` protects these when it is given no ``--branch`` argument, with or
#: without ``--pattern`` (``args.branch or ('master', 'main')`` in its source, checked at v6.0.0).
_NO_COMMIT_DEFAULTS = ("main", "master")

#: A command that ends the hook with a non-zero status, so the commit stops: ``exit 1`` (any 1 to 255),
#: ``process.exit(1)`` or ``sys.exit(1)`` in a script hook, or a bare ``false`` as a command.
_NONZERO_EXIT_RE = re.compile(
    r"\bexit\s+[1-9]|\bexit\s*\(\s*[1-9]|(?:^|[;&|{(]|\bthen|\belse|\bdo)\s*false\s*(?:$|[;&|})])", re.MULTILINE
)

_ARG_SEP = r"[\s,='\"\-]+"
_BRANCH_ARG_RE = re.compile(r"(?:--branch|\B-b)" + _ARG_SEP + r"([A-Za-z0-9_][\w./-]*)")
_PATTERN_ARG_RE = re.compile(r"(?:--pattern|\B-p)" + _ARG_SEP + r"([^\s,'\"\]]+)")


class _Guard:
    """One guard: where it is, whether its hook chain is wired, and which branches it names."""

    def __init__(
        self, rel: str, line: int, wired: bool, text: str, patterns: tuple[str, ...] = (), *, exits: bool = True
    ) -> None:
        self.rel = rel
        self.line = line
        self.wired = wired
        self.text = text
        self.patterns = patterns
        self.exits = exits

    def covers(self, branch: str) -> bool:
        for pattern in self.patterns:
            try:
                if re.match(pattern, branch):
                    return True
            except re.error:
                continue
        return re.search(rf"(?<![\w/.-]){re.escape(branch)}(?![\w/.-])", self.text) is not None


def _block(lines: list[str], start: int) -> str:
    """Line ``start`` and the lines after it indented at least as deep: the command a branch read belongs to."""
    depth = len(lines[start]) - len(lines[start].lstrip())
    out = [lines[start]]
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) < depth:
            break
        out.append(line)
    return "\n".join(out)


def _pre_commit_guards(text: str, rel: str) -> list[_Guard]:
    guards: list[_Guard] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^\s*-?\s*id:\s*['\"]?no-commit-to-branch\b", line):
            block = _block(lines, index)
            branches = _BRANCH_ARG_RE.findall(block)
            patterns = tuple(_PATTERN_ARG_RE.findall(block))
            if not branches:
                branches = list(_NO_COMMIT_DEFAULTS)
            guards.append(_Guard(rel, index + 1, True, " ".join(branches), patterns))
    return guards


def _stage(lines: list[str], index: int) -> str:
    """The top-level key above line ``index``: a lefthook stage name."""
    for line in reversed(lines[: index + 1]):
        if line.strip() and not line[0].isspace() and not line.startswith("#"):
            return line.split(":", 1)[0].strip()
    return ""


def _branch_read_guards(text: str, rel: str, wired: bool, *, whole_file: bool, staged: bool = False) -> list[_Guard]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith("#") or not _BRANCH_READ_RE.search(line):
            continue
        if staged and _stage(lines, index) not in _GUARD_HOOK_NAMES:
            continue
        guard_text = text if whole_file else _block(lines, index)
        uncommented = "\n".join(line for line in guard_text.splitlines() if not line.lstrip().startswith("#"))
        return [_Guard(rel, index + 1, wired, guard_text, exits=bool(_NONZERO_EXIT_RE.search(uncommented)))]
    return []


def _local_guards(inventory) -> list[_Guard]:
    hooks_path = bool(
        inventory.grep(r"core\.hooksPath", kinds=(Kind.MANIFEST, Kind.CONFIG, Kind.SCRIPT, Kind.CI, Kind.BUILD))
    )
    guards: list[_Guard] = []
    for rel in _present(inventory, _WIRED_HOOK_FILES):
        text = inventory.read(rel) or ""
        if rel == ".pre-commit-config.yaml":
            guards.extend(_pre_commit_guards(text, rel))
        guards.extend(_branch_read_guards(text, rel, True, whole_file=False, staged=rel.startswith("lefthook")))
    for entry in inventory.files:
        name = entry.rel.rsplit("/", 1)[-1]
        if name not in _GUARD_HOOK_NAMES or entry.rel.startswith(".git/"):
            continue
        wired = _husky_referenced(inventory) if entry.rel.startswith(".husky/") else hooks_path
        guards.extend(_branch_read_guards(inventory.read(entry.rel) or "", entry.rel, wired, whole_file=True))
    return sorted(guards, key=lambda guard: (guard.rel, guard.line))


def check_tool07(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    guards = _local_guards(inventory)
    protected = declared_branch_rules(inventory).literal_branches
    if not guards:
        wired, configured = _hook_wiring(inventory)
        if not wired and not configured:
            return _unknown(spec, "no hook chain to hold a branch guard; TOOL-05 owns that finding")
        hooks = ", ".join(sorted(set(wired + configured)))
        return _outcome(
            spec,
            Verdict.FAIL,
            f"hooks present ({hooks}) but none refuses a commit on a protected branch",
            [
                _finding(
                    spec,
                    "learn it is on a protected branch before it commits",
                    "no local hook reads the current branch or runs no-commit-to-branch",
                    Verdict.FAIL,
                    [Evidence(rel.split(" ")[0]) for rel in sorted(set(wired + configured))],
                    "Add a pre-commit guard that refuses a commit on the protected branches: pre-commit's "
                    "no-commit-to-branch, or a hook command that reads `git branch --show-current` and exits 1.",
                )
            ],
        )

    wired_guards = [guard for guard in guards if guard.wired]
    where = ", ".join(f"{guard.rel}:{guard.line}" for guard in (wired_guards or guards))
    if not wired_guards:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"branch guard at {where}, but its hook chain is not wired",
            [
                _finding(
                    spec,
                    "rely on the branch guard to run before a commit",
                    f"the guard at {where} is in a hook directory nothing installs",
                    Verdict.PARTIAL,
                    [Evidence(guard.rel, line=guard.line) for guard in guards],
                    "Wire the hook chain (TOOL-05) so the guard runs.",
                )
            ],
        )

    stopping = [guard for guard in wired_guards if guard.exits]
    if not stopping:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"branch guard at {where} reads the branch but never exits non-zero",
            [
                _finding(
                    spec,
                    "rely on the branch guard to stop a commit on a protected branch",
                    f"the guard at {where} reads the branch but has no non-zero exit, so the commit goes ahead",
                    Verdict.PARTIAL,
                    [Evidence(guard.rel, line=guard.line) for guard in wired_guards],
                    "End the guard with `exit 1` when the branch is protected, so the hook stops the commit.",
                )
            ],
        )
    where = ", ".join(f"{guard.rel}:{guard.line}" for guard in stopping)
    missing = [branch for branch in protected if not any(guard.covers(branch) for guard in stopping)]
    if missing:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"branch guard at {where} does not name {', '.join(missing)}, which the declared rules protect",
            [
                _finding(
                    spec,
                    f"learn before a commit that {', '.join(missing)} is protected",
                    f"the guard at {where} does not name {', '.join(missing)}",
                    Verdict.PARTIAL,
                    [Evidence(guard.rel, line=guard.line) for guard in stopping],
                    f"Add {', '.join(missing)} to the guard's branch list.",
                )
            ],
        )
    named = f"; names {', '.join(protected)}" if protected else ""
    return _outcome(spec, Verdict.PASS, f"branch guard at {where}{named}")
