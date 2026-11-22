# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TOOL-06: Commit convention enforced."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import runner_commands, runner_target
from audit.stack import CI_PROVIDERS
from audit.rules.checks.tool._shared import (
    _finding,
    _hook_wiring,
    _manifest_evidence,
    _outcome,
    _present,
    _read_matches,
    _unknown,
)

SPEC = declare("TOOL-06", "Commit convention enforced", "A", Severity.COSMETIC)


#: Commit-message convention configuration filenames.
_COMMITLINT_CONFIG_NAMES: tuple[str, ...] = (
    "commitlint.config.js",
    "commitlint.config.cjs",
    "commitlint.config.mjs",
    "commitlint.config.ts",
    ".commitlintrc",
    ".commitlintrc.json",
    ".commitlintrc.js",
    ".commitlintrc.cjs",
    ".commitlintrc.yml",
    ".commitlintrc.yaml",
    ".commitlintrc.toml",
)

#: TOOL-06: a CI line that checks commit messages or the pull-request title, by tool. ``@commitlint/cli`` (an
#: install) is not a run; ``wagoid/commitlint-github-action`` is.
_CI_COMMIT_TOOLS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern))
    for name, pattern in (
        ("commitlint", r"(?<!@)\bcommitlint\b(?!/)"),
        ("commitizen", r"\b(?:cz|commitizen)\s+check\b"),
        ("gitlint", r"\bgitlint\b"),
        ("pre-commit commit-msg stage", r"\bpre-commit\s+run\b.*--hook-stage[=\s]+commit-msg\b"),
        ("lefthook commit-msg", r"\blefthook\s+run\s+commit-msg\b"),
        ("pull-request title check", r"\baction-semantic-pull-request\b"),
    )
)

#: TOOL-06: a token in a `commit-msg` stage that may name a repository script.
_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*")
_SCRIPT_SUFFIXES: tuple[str, ...] = (".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".ps1")


def _commit_rule(inventory) -> list[str]:
    found = _present(inventory, _COMMITLINT_CONFIG_NAMES)
    if _read_matches(inventory, "package.json", r'"commitlint"\s*:'):
        found.append("package.json commitlint")
    for rel in (".husky/commit-msg", ".githooks/commit-msg"):
        if inventory.has(rel):
            found.append(rel)
    for rel in (".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml"):
        if _read_matches(inventory, rel, r"(?i)commit-msg|commitlint|conventional"):
            found.append(f"{rel}:commit-msg")
    return found


# ===========================================================================
# TOOL-06 — commit convention enforced
# ===========================================================================


def _commit_msg_text(inventory) -> list[str]:
    """The lines of every local `commit-msg` stage: the hook files, lefthook's `commit-msg:` block, and each
    pre-commit hook item whose text names the `commit-msg` stage."""
    lines: list[str] = []
    for rel in (".husky/commit-msg", ".githooks/commit-msg"):
        lines.extend((inventory.read(rel) or "").splitlines())
    for rel in ("lefthook.yml", "lefthook.yaml"):
        inside = False
        for line in (inventory.read(rel) or "").splitlines():
            if line and not line[0].isspace() and not line.startswith("#"):
                inside = line.split(":", 1)[0].strip().strip("'\"") == "commit-msg"
                continue
            if inside:
                lines.append(line)
    item: list[str] = []
    for line in [*(inventory.read(".pre-commit-config.yaml") or "").splitlines(), "- id: <end>"]:
        if re.match(r"^\s*-\s+(?:id|repo)\s*:", line):
            if any("commit-msg" in text for text in item):
                lines.extend(item)
            item = []
        item.append(line)
    return lines


def _commit_msg_scripts(inventory) -> list[str]:
    """Repository scripts a local `commit-msg` stage runs, by path, so CI can be seen to run the same rule."""
    paths = set(inventory.paths())
    scripts: set[str] = set()
    for line in _commit_msg_text(inventory):
        for token in _PATH_TOKEN_RE.findall(line):
            rel = token.removeprefix("./")
            if rel in paths and rel.endswith(_SCRIPT_SUFFIXES):
                scripts.add(rel)
    return sorted(scripts)


def _commit_rule_in(text: str, scripts: list[str]) -> str | None:
    """What in ``text`` checks commit messages: a known tool, or a script the local stage runs."""
    for name, pattern in _CI_COMMIT_TOOLS:
        if pattern.search(text):
            return name
    for rel in scripts:
        if re.search(r"(?<![\w/.-])(?:\./)?" + re.escape(rel) + r"(?![\w/-])", text):
            return rel
    return None


def _ci_commit_steps(inventory, scripts: list[str]) -> list[tuple[str, int, str]]:
    """``(workflow, line, what)`` for each workflow line that checks commit messages or the pull-request title,
    directly or through a runner target (``make commit-lint``, ``npm run commitlint``)."""
    targets: dict[str, str] = {}
    for _runner, commands in reversed(runner_commands(inventory)):
        targets.update(commands)
    hits: list[tuple[str, int, str]] = []
    for globs in CI_PROVIDERS.values():
        for rel in sorted(inventory.match(*globs)):
            for number, line in enumerate((inventory.read(rel) or "").splitlines(), start=1):
                if line.lstrip().startswith("#"):
                    continue
                what = _commit_rule_in(line, scripts)
                target = runner_target(line)
                if what is None and target in targets:
                    via = _commit_rule_in(targets[target], scripts)
                    what = f"{target} ({via})" if via else None
                if what:
                    hits.append((rel, number, what))
    return hits


def check_tool06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    rules = sorted(set(_commit_rule(inventory)))
    ci_steps = _ci_commit_steps(inventory, _commit_msg_scripts(inventory))
    ci_seen = ", ".join(sorted({f"{what} ({rel})" for rel, _line, what in ci_steps}))
    detail = f"local: {', '.join(rules) or 'none'}; CI: {ci_seen or 'none'}"

    if rules and ci_steps:
        return _outcome(spec, Verdict.PASS, detail)
    if rules:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            detail,
            [
                _finding(
                    spec,
                    "rely on every commit following the convention",
                    "the commit-message rule runs only in a local hook, which `--no-verify` or a missing install "
                    "skips, and no CI step checks it",
                    Verdict.PARTIAL,
                    [Evidence(rel.split(" ")[0].split(":")[0]) for rel in rules],
                    "Run the same commit-message rule in CI over the commits a pull request adds (or check the "
                    "pull-request title when the repository squash-merges).",
                )
            ],
        )
    if ci_steps:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            detail,
            [
                _finding(
                    spec,
                    "learn that a commit message breaks the convention before it pushes",
                    "the commit-message rule runs only in CI; no local `commit-msg` stage runs it",
                    Verdict.PARTIAL,
                    [Evidence(rel, line=line, note=what) for rel, line, what in ci_steps],
                    "Run the same rule in a local `commit-msg` hook, with the type list CI uses.",
                )
            ],
        )

    wired, configured = _hook_wiring(inventory)
    if stack.ecosystems or wired or configured:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no commit-message rule",
            [
                _finding(
                    spec,
                    "rely on a consistent commit-message convention",
                    "no commitlint config, commit-msg hook, equivalent stage or CI step exists",
                    Verdict.FAIL,
                    _manifest_evidence(inventory),
                    "Add a commit-message rule to a commit-msg hook and run the same rule in CI.",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem and no hook configuration, so a commit convention cannot be judged")
