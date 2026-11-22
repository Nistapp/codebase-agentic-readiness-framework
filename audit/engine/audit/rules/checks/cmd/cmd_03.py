# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CMD-03: No divergent second definition."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import runner_commands, runner_kind
from audit.rules.checks.cmd._shared import (
    _NPM_RE,
    _TASK_RE,
    _YARN_RE,
    _no_runner,
    _ordered_runners,
    _outcome,
    _runner_target,
    _segments,
)

SPEC = declare("CMD-03", "No divergent second definition", "B", Severity.DEGRADER)


# ===========================================================================
# CMD-03 — no divergent second definition
# ===========================================================================

#: How a delegating `check` invokes the primary runner, per known primary.
_DELEGATION_PATTERNS: dict[str, re.Pattern] = {
    "package.json": re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?check\b"),
    "Makefile": re.compile(r"(?:\bmake\b|\$\(MAKE\))\s+check\b"),
    "Taskfile.yml": re.compile(r"\btask\s+check\b"),
    "Taskfile.yaml": re.compile(r"\btask\s+check\b"),
    "pyproject.toml": re.compile(r"\b(?:poe|task|taskipy|invoke)\s+check\b"),
    "build.gradle": re.compile(r"\b(?:\./gradlew|gradle)\s+check\b"),
    "build.gradle.kts": re.compile(r"\b(?:\./gradlew|gradle)\s+check\b"),
    "pom.xml": re.compile(r"\b(?:\./mvnw|mvn)\b[^&|;]*\bcheck\b"),
}


def _delegates_to(command: str, primary: str, secondary: str) -> bool:
    pattern = _DELEGATION_PATTERNS.get(runner_kind(primary))
    if pattern and pattern.search(command):
        return True
    for segment in _segments(command):
        target = _runner_target(segment)
        if target == "check":
            invoked = _invoked_runner(segment)
            if invoked != runner_kind(secondary):
                return True
    return False


def _invoked_runner(segment: str) -> str | None:
    if _NPM_RE.search(segment):
        return "package.json"
    if _YARN_RE.search(segment):
        return "package.json"
    if _TASK_RE.search(segment):
        return "Makefile"
    return None


def check_cmd03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    declared = runner_commands(inventory)
    if not declared:
        return _no_runner(spec, inventory, "no second definition can be read")

    check_defs = [(runner, commands["check"]) for runner, commands in declared if "check" in commands]
    if len(check_defs) <= 1:
        detail = (
            "one runner defines the gate" if check_defs else "no runner defines check, so there is nothing to diverge"
        )
        return _outcome(spec, Verdict.PASS, detail)

    primary = _ordered_runners({runner for runner, _cmd in check_defs})[0]
    divergent = [
        (runner, command)
        for runner, command in check_defs
        if runner != primary and not _delegates_to(command, primary, runner)
    ]

    if not divergent:
        return _outcome(spec, Verdict.PASS, f"{len(check_defs)} runners define check; all but {primary} delegate to it")

    detail = "; ".join(f"{runner} defines its own check" for runner, _cmd in divergent)
    return _outcome(
        spec,
        Verdict.FAIL,
        detail,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "know which check definition is authoritative",
                    f"{', '.join(runner for runner, _cmd in divergent)} compose the gate independently of "
                    f"the primary runner {primary}",
                ),
                evidence=[Evidence(runner, note=command) for runner, command in divergent],
                remediation=f"Make the second runner delegate to the {primary} check (for example "
                f"`npm run check`), or delete its duplicate gate.",
            )
        ],
    )
