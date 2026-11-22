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
from audit.stack import extract_npm_scripts, parse_makefile_targets
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


def _resolves(
    inv: Inventory, tokens: list[str], verbs: dict, scripts: dict, make_targets: dict, bins: set[str]
) -> bool:
    while tokens and tokens[0] in _STRIPPABLE_PREFIXES:
        tokens = tokens[1:]
    if not tokens:
        return True
    head = tokens[0]
    rest = tokens[1:]

    if head in _SHELL_KEYWORDS or head in _KNOWN_TOOLS:
        if head in {"npm", "pnpm", "bun"}:
            if rest[:1] == ["run"]:
                return len(rest) >= 2 and rest[1] in scripts
            return True
        if head == "yarn":
            if rest[:1] == ["run"]:
                return len(rest) >= 2 and rest[1] in scripts
            return True
        if head == "make":
            targets = [t for t in rest if not t.startswith("-") and "=" not in t]
            return all(t in make_targets for t in targets) if targets and make_targets else True
        return True

    if head in verbs:
        return True

    if head in bins:
        return True

    candidate = head[2:] if head.startswith("./") else head
    if "/" in candidate or head.startswith("./"):
        if inv.has(candidate) or any(f.rel == candidate or f.rel.startswith(candidate + "/") for f in inv.files):
            return True

    return False


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

    unresolved: list[tuple[str, int, str]] = []
    for path, line, command in unique:
        if re.search(r"[<]|\.\.\.|\b(your[_-]|tbd|xxx|placeholder)\b", command, re.IGNORECASE):
            continue
        tokens = _command_parts(command)
        if not tokens:
            continue
        if not _resolves(inventory, tokens, verbs, scripts, make_targets, bins):
            unresolved.append((path, line, command))

    if not unresolved:
        return _outcome(spec, Verdict.PASS, f"{len(unique)} documented command(s) resolve")

    because = f"{len(unresolved)} documented command(s) name no script, verb, or file: " + "; ".join(
        f"{cmd!r} ({path}:{line})" for path, line, cmd in unresolved[:8]
    )
    return _outcome(
        spec,
        Verdict.FAIL,
        because,
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
