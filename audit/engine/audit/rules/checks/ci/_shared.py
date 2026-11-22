# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one CI check uses."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.checks._common import runner_target, strip_shell_comment
from audit.stack import CI_PROVIDERS, VERBS
from audit.rules.payloads import Payload

#: Step keys that carry commands, across the workflow dialects this scan understands.
_STEP_KEY_RE = re.compile(r"^(\s*)(?:-\s+)?(run|script|command|commands|bash)\s*:\s*(.*)$")
_BLOCK_SCALAR_VALUES = frozenset({"|", "|-", "|+", ">", ">-", ">+", ""})
_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
#: Commands whose arguments are text written out (a job summary, a log line), never commands to run.
_TEXT_COMMANDS: frozenset[str] = frozenset({"echo", "printf"})
#: A heredoc opener (``<<EOF``, ``<<-'EOF'``), not a here-string (``<<<``); group 2 is the terminator word.
_HEREDOC_RE = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

#: Direct tool invocations, mapped to the framework verb they satisfy. `format:check` precedes
#: `format` and `security` precedes the rest so the more specific form wins.
_DIRECT_VERB_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (verb, tuple(re.compile(p) for p in patterns))
    for verb, patterns in (
        (
            "format:check",
            (
                r"\bprettier\b[^&|;]*--check\b",
                r"\bruff\s+format\b[^&|;]*--(?:check|diff)\b",
                r"\bbiome\s+ci\b",
                r"\bblack\b[^&|;]*--check\b",
                r"\bcargo\s+fmt\b[^&|;]*--check\b",
                r"\bdotnet\s+format\b[^&|;]*--verify-no-changes\b",
            ),
        ),
        (
            "format",
            (
                r"\bprettier\b[^&|;]*(?:--write|-w)\b",
                r"\bruff\s+format\b",
                r"\bbiome\s+format\b",
                r"\bblack\b",
                r"\bgofmt\b[^&|;]*\s-w\b",
                r"\bcargo\s+fmt\b",
            ),
        ),
        (
            "typecheck",
            (
                r"\btsc\b",
                r"\bmypy\b",
                r"\bpyright\b",
                r"\bbasedpyright\b",
                r"\bcargo\s+check\b",
                r"\bgo\s+vet\b",
            ),
        ),
        (
            "lint",
            (
                r"\beslint\b",
                r"\bruff\s+check\b",
                r"\bflake8\b",
                r"\bpylint\b",
                r"\bgolangci-lint\b",
                r"\bclippy\b",
                r"\brubocop\b",
                r"\bbiome\s+(?:check|lint)\b",
                r"\bstylelint\b",
            ),
        ),
        (
            "test",
            (
                r"\bvitest\b",
                r"\bjest\b",
                r"\bmocha\b",
                r"\bpytest\b",
                r"python3?\s+-m\s+(?:unittest|pytest)",
                r"\bgo\s+test\b",
                r"\bcargo\s+test\b",
                r"\bdotnet\s+test\b",
                r"\brspec\b",
                r"\bphpunit\b",
            ),
        ),
        (
            "security",
            (
                r"\bnpm\s+audit\b",
                r"\b(?:pnpm|yarn|bun)\s+audit\b",
                r"\bpip-audit\b",
                r"\bsafety\s+check\b",
                r"\bosv-scanner\b",
                r"\bcargo\s+audit\b",
                r"\bgovulncheck\b",
                r"\bsnyk\b",
                r"\btrivy\b",
                r"\bgrype\b",
                r"\bbundler-audit\b",
                r"\bcomposer\s+audit\b",
                r"\baudit-ci\b",
            ),
        ),
    )
)


def _outcome(
    spec, verdict: Verdict, summary: str = "", findings: list[Finding] | None = None, data: Payload | None = None
) -> CheckOutcome:
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=summary,
        data=data,
        findings=findings or [],
    )


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _finding(
    spec,
    cannot: str,
    because: str,
    verdict: Verdict,
    evidence: list[Evidence],
    remediation: str,
    path: str | None = None,
) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence,
        remediation=remediation,
        path=path,
    )


# ---------------------------------------------------------------------------
# workflow discovery and a minimal, documented YAML scan
# ---------------------------------------------------------------------------


def _workflows(inventory) -> list[tuple[str, str]]:
    """Every present workflow file as ``(provider, rel)``, in provider order then path order."""
    found: list[tuple[str, str]] = []
    for provider, globs in CI_PROVIDERS.items():
        for rel in sorted(inventory.match(*globs)):
            found.append((provider, rel))
    return found


def _split_unquoted(command: str) -> list[str]:
    """``command`` split at ``&&``, ``||``, ``;`` and ``|`` outside single and double quotes."""
    parts: list[str] = []
    start = 0
    quote = ""
    escaped = False
    index = 0
    while index < len(command):
        ch = command[index]
        if escaped:
            escaped = False
        elif ch == "\\" and quote != "'":
            escaped = True
        elif quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch in ";|" or command.startswith("&&", index):
            parts.append(command[start:index])
            width = 2 if command.startswith(("&&", "||"), index) else 1
            index += width
            start = index
            continue
        index += 1
    parts.append(command[start:])
    return [part.strip() for part in parts if part.strip()]


def _first_word(command: str) -> str:
    """The program a simple command runs: its first word after any ``NAME=value`` assignments."""
    for word in command.split():
        if not _ASSIGNMENT_RE.match(word):
            return word
    return ""


def _split_commands(raw: str) -> list[str]:
    command = raw.strip()
    if command.startswith("- "):
        command = command[2:].strip()
    command = strip_shell_comment(command)
    if not command or command.startswith("#"):
        return []
    return [part for part in _split_unquoted(command) if _first_word(part) not in _TEXT_COMMANDS]


def _body_commands(numbered: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """``(line_no, command)`` for each command in a block of shell lines; a heredoc's body is text, not commands."""
    commands: list[tuple[int, str]] = []
    terminator: str | None = None
    for line_no, raw in numbered:
        if terminator is not None:
            if raw.strip() == terminator:
                terminator = None
            continue
        split = _split_commands(raw)
        commands.extend((line_no, cmd) for cmd in split)
        heredoc = _HEREDOC_RE.search(strip_shell_comment(raw))
        if heredoc:
            terminator = heredoc.group(2)
    return commands


def _iter_run_commands(text: str) -> list[tuple[int, str]]:
    """Extract ``(line_no, command)`` from run-style steps. A minimal, documented text scan."""
    lines = text.splitlines()
    commands: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = _STEP_KEY_RE.match(lines[index])
        if not match:
            index += 1
            continue
        indent = len(match.group(1))
        value = match.group(3).strip()
        if value and value not in _BLOCK_SCALAR_VALUES:
            commands.extend((index + 1, cmd) for cmd in _split_commands(value))
            index += 1
            continue
        # Block scalar (or a list under `script:`/`commands:`): collect the indented body.
        body: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            if candidate.strip() == "":
                body.append("")
                cursor += 1
                continue
            if len(candidate) - len(candidate.lstrip()) <= indent:
                break
            body.append(candidate)
            cursor += 1
        commands.extend(_body_commands(list(enumerate(body, start=index + 2))))
        index = cursor
    return commands


def _command_verb(command: str) -> str | None:
    """The framework verb a command invokes, by runner indirection or direct tool, else ``None``."""
    target = runner_target(command)
    if target in VERBS:
        return target
    for verb, patterns in _DIRECT_VERB_PATTERNS:
        if any(pattern.search(command) for pattern in patterns):
            return verb
    return None


def _all_run_commands(inventory, workflows) -> list[tuple[str, int, str]]:
    """Every ``(rel, line_no, command)`` across the workflows, deterministically ordered."""
    out: list[tuple[str, int, str]] = []
    for _provider, rel in workflows:
        text = inventory.read(rel)
        if text:
            out.extend((rel, line, command) for line, command in _iter_run_commands(text))
    return out
