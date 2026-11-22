# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one TOOL check uses."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.checks._common import runner_commands
from audit.scan import Kind
from audit.stack import extract_npm_scripts
from audit.rules.payloads import Payload

#: Hook managers whose mere presence is a wired chain.
_WIRED_HOOK_FILES: tuple[str, ...] = (".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml")


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


def _recognised(stack, inventory) -> bool:
    """Whether there is any basis to judge: a detected ecosystem or a recognised verb runner."""
    return bool(stack.ecosystems) or bool(runner_commands(inventory))


def _present(inventory, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if inventory.has(name)]


def _read_matches(inventory, rel: str, pattern: str) -> bool:
    text = inventory.read(rel)
    return bool(text and re.search(pattern, text))


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


def _manifest_evidence(inventory) -> list[Evidence]:
    """Real runner manifests as evidence, so an absence finding still cites concrete paths."""
    evidence = [Evidence(runner) for runner, _cmds in runner_commands(inventory)]
    return evidence or [Evidence("<repository>", note="detected ecosystem")]


def _hook_wiring(inventory) -> tuple[list[str], list[str]]:
    """Return ``(wired, configured)`` hook-chain evidence."""
    wired = _present(inventory, _WIRED_HOOK_FILES)
    configured: list[str] = []

    hooks_path = inventory.grep(
        r"core\.hooksPath",
        kinds=(Kind.MANIFEST, Kind.CONFIG, Kind.SCRIPT, Kind.CI, Kind.BUILD),
    )
    if hooks_path:
        wired.append(f"{hooks_path[0][0]} core.hooksPath")

    githooks = inventory.match(".githooks/*")
    if githooks and not hooks_path:
        configured.append(".githooks/")

    husky = inventory.match(".husky/*")
    if husky:
        if _husky_referenced(inventory):
            wired.append(".husky/ (referenced)")
        else:
            configured.append(".husky/ (not referenced)")

    return wired, configured


def _husky_referenced(inventory) -> bool:
    scripts = extract_npm_scripts(inventory)
    return any("husky" in command for command in scripts.values())
