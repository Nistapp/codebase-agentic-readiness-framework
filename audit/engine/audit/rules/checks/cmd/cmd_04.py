# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CMD-04: Write verbs separated from read-only verbs."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.probes import MUTATING_VERBS
from audit.rules.checks._common import VerbBinding, resolve_verbs, runner_commands
from audit.stack import VERBS
from audit.rules.checks.cmd._shared import _no_runner, _outcome, _runner_target, _segments

SPEC = declare("CMD-04", "Write verbs separated from read-only verbs", "B", Severity.DEGRADER)


#: The read-only verbs `check` and CI may compose: every framework verb except a write verb.
READ_ONLY_VERBS: tuple[str, ...] = tuple(v for v in VERBS if v not in MUTATING_VERBS)

#: Direct writer invocations, keyed by the write verb they represent. Only the check form is read, so
#: `format:check` is never mistaken for `format`.
_WRITER_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "format",
        (
            r"\bprettier\b[^&|;]*\s(?:--write|-w)\b",
            r"\bbiome\s+format\b",
            r"\bbiome\s+(?:check|format)\b[^&|;]*--write\b",
            r"\bruff\s+format\b(?![^&|;]*--(?:check|diff))",
            r"\bblack\b(?![^&|;]*--check)",
            r"\bgofmt\b[^&|;]*\s-w\b",
            r"\beslint\b[^&|;]*--fix\b",
            r"\bclippy\b[^&|;]*--fix\b",
            r"\bcargo\s+fmt\b(?![^&|;]*--check)",
        ),
    ),
    (
        "install",
        (
            r"\b(?:npm|pnpm|yarn|bun)\s+(?:ci|install)\b",
            r"\bpip3?\s+install\b",
            r"\buv\s+(?:sync|pip)\b",
            r"\bcargo\s+(?:fetch|install)\b",
        ),
    ),
    (
        "build",
        (
            r"\bcargo\s+build\b",
            r"\btsc\b(?!\s+--noEmit)",
            r"\bdotnet\s+build\b",
        ),
    ),
    (
        "clean",
        (
            r"\brm\s+-rf?\b",
            r"\bshx\s+rm\b",
        ),
    ),
)


# ===========================================================================
# CMD-04 — write verbs separated from read-only verbs
# ===========================================================================


def _write_invocations(command: str) -> list[str]:
    found: set[str] = set()
    for segment in _segments(command):
        target = _runner_target(segment)
        if target in MUTATING_VERBS:
            found.add(target)
        for write_verb, patterns in _WRITER_PATTERNS:
            if any(re.search(p, segment, re.IGNORECASE) for p in patterns):
                found.add(write_verb)
    return sorted(found)


def check_cmd04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    declared = runner_commands(inventory)
    if not declared:
        return _no_runner(spec, inventory, "read-only verbs cannot be read")

    resolved = resolve_verbs(inventory, stack)
    offenders: list[tuple[str, VerbBinding, list[str]]] = []
    for verb in READ_ONLY_VERBS:
        binding = resolved.get(verb)
        if binding is None:
            continue
        writes = _write_invocations(binding.command)
        if writes:
            offenders.append((verb, binding, writes))

    if not offenders:
        return _outcome(spec, Verdict.PASS, "no read-only verb invokes a write verb")

    detail = "; ".join(f"{verb} -> {', '.join(writes)}" for verb, _binding, writes in offenders)
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
                    "verify a change set without mutating the working tree",
                    f"{len(offenders)} read-only verb(s) invoke a write verb: {detail}",
                ),
                evidence=[
                    Evidence(binding.runner, note=command)
                    for _verb, binding, _writes in offenders
                    for command in (binding.command,)
                ],
                remediation="Keep write verbs (format, install, clean, build) out of verification verbs; "
                "a gate composes the read-only form (format:check), never the writing one.",
            )
        ],
    )
