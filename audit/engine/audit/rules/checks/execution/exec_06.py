# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""EXEC-06: Documented commands resolve."""

from __future__ import annotations

import json
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import (
    extract_fenced_commands,
    resolve_all_verbs,
    resolve_verbs,
    runner_kind,
    README,
    entry_documents,
)
from audit.scan import Inventory
from audit.stack import ParsedMakefile, extract_npm_scripts, parse_makefile, parse_makefile_targets
from audit.rules.checks.execution._shared import _outcome, _tokenise

SPEC = declare("EXEC-06", "Documented commands resolve", "B", Severity.DEGRADER)


# ===========================================================================
# EXEC-06 — documented commands resolve
# ===========================================================================

_KNOWN_TOOLS = frozenset(
    {
        "python",
        "python3",
        "pip",
        "pip3",
        "poetry",
        "uv",
        "pipenv",
        "pytest",
        "tox",
        "ruff",
        "black",
        "mypy",
        "pyright",
        "flake8",
        "pylint",
        "isort",
        "node",
        "npm",
        "npx",
        "pnpm",
        "yarn",
        "bun",
        "corepack",
        "tsc",
        "vitest",
        "jest",
        "eslint",
        "biome",
        "prettier",
        "shx",
        "husky",
        "lint-staged",
        "commitlint",
        "semgrep",
        "go",
        "gofmt",
        "golangci-lint",
        "cargo",
        "rustc",
        "rustup",
        "clippy",
        "rustfmt",
        "java",
        "javac",
        "mvn",
        "gradle",
        "dotnet",
        "ruby",
        "gem",
        "bundle",
        "rake",
        "php",
        "composer",
        "git",
        "gh",
        "docker",
        "docker-compose",
        "podman",
        "kubectl",
        "helm",
        "terraform",
        "aws",
        "az",
        "gcloud",
        "make",
        "task",
        "just",
        "cmake",
        "ninja",
        "bash",
        "sh",
        "zsh",
        "fish",
        "shellcheck",
        "curl",
        "wget",
        "jq",
        "yq",
        "tar",
        "zip",
        "unzip",
        "gzip",
        "openssl",
        "ssh",
        "scp",
        "rsync",
        "mkdir",
        "cp",
        "mv",
        "rm",
        "ls",
        "cat",
        "touch",
        "chmod",
        "ln",
        "sed",
        "awk",
        "grep",
        "find",
        "xargs",
        "which",
        "command",
        "env",
        "echo",
        "printf",
        "head",
        "tail",
        "tee",
        "sort",
        "uniq",
        "wc",
        "diff",
        "sleep",
        "kill",
        "ps",
        "du",
        "df",
        "nvm",
        "fnm",
        "asdf",
        "mise",
        "volta",
        "sdk",
        "pre-commit",
        "lefthook",
        "opencode",
        "claude",
        "codex",
        "gemini",
        "aider",
        "copilot",
        "cursor",
        "windsurf",
        "amp",
        "crush",
        "pi",
        "goose",
        "audit",
    }
)

_SHELL_KEYWORDS = frozenset(
    {
        "cd",
        "export",
        "source",
        ".",
        "set",
        "unset",
        "alias",
        "if",
        "then",
        "else",
        "elif",
        "fi",
        "for",
        "while",
        "do",
        "done",
        "case",
        "esac",
        "function",
        "return",
        "local",
        "readonly",
        "declare",
        "eval",
        "trap",
        "umask",
        "ulimit",
        "wait",
        "jobs",
        "fg",
        "bg",
        "type",
        "hash",
        "pwd",
        "whoami",
        "id",
        "uname",
        "date",
        "hostname",
        "realpath",
        "dirname",
        "basename",
        "printenv",
        "true",
        "false",
        "exit",
        "yes",
        "no",
        "test",
        "[",
        "[[",
    }
)

_STRIPPABLE_PREFIXES = frozenset({"sudo", "env", "time", "nohup", "command", "stdbuf"})


def _package_bins(inv: Inventory) -> set[str]:
    text = inv.read("package.json")
    if not text:
        return set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set()
    bins = data.get("bin")
    if isinstance(bins, str):
        return {str(data.get("name") or "").strip()} - {""}
    if isinstance(bins, dict):
        return set(bins)
    return set()


def _command_parts(command: str) -> list[str]:
    command = re.split(r"\s*(?:&&|\|\||;|\|)\s*", command, maxsplit=1)[0]
    command = re.split(r"\s+2?>\s*", command, maxsplit=1)[0]
    return _tokenise(command)


#: What :func:`_resolves` says of one command.
RESOLVED, UNVERIFIED, UNRESOLVED = "resolved", "unverified", "unresolved"


def _matches_pattern(target: str, pattern: str) -> bool:
    """Whether a Make target pattern (``test-%``) matches ``target``; the ``%`` stands for at least one character."""
    prefix, _, suffix = pattern.partition("%")
    return len(target) > len(prefix) + len(suffix) and target.startswith(prefix) and target.endswith(suffix)


def _computed_lines(target: str, makefile: ParsedMakefile) -> list[int]:
    """The lines of the target lists the reader cannot expand that may name ``target``.

    Make requires every name a static pattern rule lists to match its target pattern, so a list bounded by
    ``test-%`` cannot name ``deploy``; a list with no such pattern may name anything.
    """
    return [line for line, pattern in makefile.computed if pattern is None or _matches_pattern(target, pattern)]


def _make_target(target: str, make_targets: dict, makefile: ParsedMakefile) -> str:
    """Whether a rule, a pattern rule or the list of a static pattern rule builds ``target``.

    Failing that, a target list the reader cannot expand (``$(TARGETS):``) may name it, so the target is not
    verified rather than unresolved. With no such list, it is unresolved.
    """
    if target in make_targets or target in makefile.static_targets:
        return RESOLVED
    if any(_matches_pattern(target, pattern) for pattern in makefile.patterns):
        return RESOLVED
    return UNVERIFIED if _computed_lines(target, makefile) else UNRESOLVED


def _resolves(
    inv: Inventory,
    tokens: list[str],
    verbs: dict,
    scripts: dict,
    make_targets: dict,
    bins: set[str],
    makefile: ParsedMakefile | None = None,
) -> str:
    while tokens and tokens[0] in _STRIPPABLE_PREFIXES:
        tokens = tokens[1:]
    if not tokens:
        return RESOLVED
    head = tokens[0]
    rest = tokens[1:]

    if head in _SHELL_KEYWORDS or head in _KNOWN_TOOLS:
        if head in {"npm", "pnpm", "bun", "yarn"} and rest[:1] == ["run"]:
            return RESOLVED if len(rest) >= 2 and rest[1] in scripts else UNRESOLVED
        if head == "make":
            targets = [t for t in rest if not t.startswith("-") and "=" not in t]
            if not targets or not make_targets:
                return RESOLVED
            parsed = makefile or ParsedMakefile(rules={}, errors=())
            states = {_make_target(t, make_targets, parsed) for t in targets}
            return next(state for state in (UNRESOLVED, UNVERIFIED, RESOLVED) if state in states)
        return RESOLVED

    if head in verbs or head in bins:
        return RESOLVED

    candidate = head[2:] if head.startswith("./") else head
    if "/" in candidate or head.startswith("./"):
        if inv.has(candidate) or any(f.rel == candidate or f.rel.startswith(candidate + "/") for f in inv.files):
            return RESOLVED

    return UNRESOLVED


def _logical_commands(entries: list[tuple[str, int, str]]) -> list[tuple[str, int, str]]:
    """Join trailing-backslash line continuations into one command.

    ``extract_fenced_commands`` reports each physical line; a multi-line invocation would otherwise
    present its continuation lines (``--out ...``) as commands in their own right.
    """
    merged: list[tuple[str, int, str]] = []
    for path, line, command in entries:
        if merged and merged[-1][0] == path and merged[-1][1] + 1 == line and merged[-1][2].rstrip().endswith("\\"):
            prev_path, prev_line, prev = merged[-1]
            merged[-1] = (prev_path, prev_line, prev.rstrip().rstrip("\\").rstrip() + " " + command)
        else:
            merged.append((path, line, command))
    return merged


def check_exec06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    # The catalogue's evidence rule names README and AGENTS.md; docs/** fences routinely mix
    # languages (a Python snippet in a ```bash block), which is a documentation defect EXEC-06 is
    # not chartered to police.
    doc_paths = entry_documents(inventory, (README, "AGENTS.md", "CLAUDE.md"))

    raw: list[tuple[str, int, str]] = []
    for name in doc_paths:
        text = inventory.read(name)
        if not text:
            continue
        raw.extend((name, line, command) for _lang, line, command in extract_fenced_commands(text))

    commands = _logical_commands(raw)
    seen: set[str] = set()
    unique: list[tuple[str, int, str]] = []
    for path, line, command in commands:
        if command in seen:
            continue
        seen.add(command)
        unique.append((path, line, command))

    if not unique:
        return _outcome(spec, Verdict.PASS, "no fenced shell commands documented")

    verbs = resolve_verbs(inventory, stack)
    scripts = extract_npm_scripts(inventory)
    make_targets = parse_makefile_targets(inventory)
    # A verb is also invoked under its other spelling (``format:check`` for ``format-check``); the
    # resolver already knows which runner binds it, so ask it rather than re-reading the manifest.
    for verb, bindings in resolve_all_verbs(inventory, stack).items():
        for binding in bindings:
            kind = runner_kind(binding.runner)
            if kind == "Makefile" and make_targets:
                make_targets.setdefault(verb, binding.command)
            elif kind == "package.json":
                scripts.setdefault(verb, binding.command)
    bins = _package_bins(inventory)

    makefile = parse_makefile(inventory)
    unresolved: list[tuple[str, int, str]] = []
    unverified: list[tuple[str, int, str]] = []
    for path, line, command in unique:
        if re.search(r"[<]|\.\.\.|\b(your[_-]|tbd|xxx|placeholder)\b", command, re.IGNORECASE):
            continue
        tokens = _command_parts(command)
        if not tokens:
            continue
        state = _resolves(inventory, tokens, verbs, scripts, make_targets, bins, makefile)
        if state == UNRESOLVED:
            unresolved.append((path, line, command))
        elif state == UNVERIFIED:
            unverified.append((path, line, command))

    # The engine never runs Make, so a target list it cannot expand is no evidence against a target. Such a
    # command does not fail the check, as a make command does not when no Makefile can be read; the summary
    # names it, so a reader can check it by hand.
    lines = sorted(
        {n for _path, _line, cmd in unverified for word in _command_parts(cmd) for n in _computed_lines(word, makefile)}
    )
    note = (
        f"; {len(unverified)} make command(s) not verified, because the Makefile builds target names from a "
        f"variable or a function (line {', '.join(str(n) for n in lines[:4])}) the engine does not "
        "expand: " + "; ".join(f"{cmd!r} ({path}:{line})" for path, line, cmd in unverified[:8])
        if unverified
        else ""
    )

    if not unresolved:
        return _outcome(spec, Verdict.PASS, f"{len(unique) - len(unverified)} documented command(s) resolve{note}")

    because = f"{len(unresolved)} documented command(s) name no script, verb, or file: " + "; ".join(
        f"{cmd!r} ({path}:{line})" for path, line, cmd in unresolved[:8]
    )
    return _outcome(
        spec,
        Verdict.FAIL,
        because + note,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement("run the documented commands literally", because),
                evidence=[Evidence(path, line=line, note=cmd) for path, line, cmd in unresolved[:12]],
                remediation="Fix the documented command to name a resolvable script, verb, or file — an "
                "agent will run it exactly as written.",
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, ROOT, Reads, What, _at, _runners

    return Reads(
        where=(
            *_at(ROOT, "README.md", "AGENTS.md", "CLAUDE.md"),
            *_at(GLOB, "README*"),
            *_runners(),
            *_at(ANY_DEPTH, "gradlew", "mvnw"),
        ),
        what=What("fenced-command"),
        binding="line",
        threshold="every documented command resolves",
        note=(
            "Fenced bash, sh, shell, console and zsh blocks in the three root docs only, continuations "
            "joined, repeats and placeholders skipped. The first word must be a known tool, a shell keyword, "
            "a resolved verb, an npm script or bin of the root package.json, a root Makefile target or a real"
            " path. A make target also resolves through a pattern rule or a static pattern rule's list; one that"
            " only a computed target list may name (one with no static pattern, or whose static pattern matches"
            " it) is not verified and does not fail."
        ),
    )
