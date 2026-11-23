# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one BASE check uses."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.checks._common import resolve_verbs
from audit.scan import Inventory
from audit.rules.payloads import Payload

#: Baseline / suppression artifacts, matched by name at any depth. A `*baseline*` name is treated as
#: a baseline wherever it sits; this is a documented name set, not a content assertion.
_BASELINE_GLOBS: tuple[str, ...] = (
    ".eslint-baseline*",
    ".ruff-baseline*",
    ".mypy-baseline*",
    "baseline.json",
    "*baseline*.json",
    "*baseline*.xml",
    "coverage-baseline.*",
    "*.baseline",
    ".secrets.baseline",
    ".snyk",
    ".gitleaksignore",
)

#: Entry documents whose contents can satisfy the "documented equivalent mechanism" clause.
_DOCS: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md")

#: Files whose mere presence implies a violation-counting tool is configured.
_COUNTING_CONFIG_GLOBS: tuple[str, ...] = (
    ".eslintrc*",
    "eslint.config.*",
    "biome.json",
    "biome.jsonc",
    ".ruff.toml",
    "ruff.toml",
    ".flake8",
    "pylintrc",
    ".pylintrc",
    "mypy.ini",
    ".mypy.ini",
    ".golangci.yml",
    ".golangci.yaml",
    "clippy.toml",
    ".gitleaks.toml",
    ".snyk",
    "sonar-project.properties",
    ".semgrep.yml",
    ".semgrep.yaml",
)
_PYPROJECT_TOOL_RE = re.compile(r"(?m)^\[tool\.(?:ruff|mypy|pylint|bandit|pyright)\b")
_SETUP_CFG_TOOL_RE = re.compile(r"(?m)^\[(?:mypy|flake8|pylint|isort|bandit)\b")

#: An explicit numeric violation budget — the only count a static scan can point at exactly.
_BUDGET_RE = re.compile(
    r"--max-warnings(?:=|\s+)\d+"
    r"|\bmax[-_]?(?:warnings|issues|problems)\b\s*[:=]?\s*\d+"
    r"|\bviolation[-_]?budget\b\s*[:=]?\s*\d+"
)

#: Runner manifests read for a numeric budget in addition to the counting configs.
_RUNNER_MANIFESTS: tuple[str, ...] = (
    "package.json",
    "pyproject.toml",
    "Makefile",
    "Taskfile.yml",
    "Taskfile.yaml",
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


def _finding(spec, cannot: str, because: str, verdict: Verdict, evidence: list[Evidence], remediation: str) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence,
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# readers
# ---------------------------------------------------------------------------


def _baseline_artifacts(inventory: Inventory) -> list[str]:
    found: set[str] = set()
    for pattern in _BASELINE_GLOBS:
        found.update(inventory.match(pattern))
    return sorted(found)


def _text_matches(inventory: Inventory, rel: str, pattern: re.Pattern[str]) -> bool:
    text = inventory.read(rel)
    return bool(text and pattern.search(text))


def _counting_tools(inventory: Inventory, stack) -> list[str]:
    """Configured lint / type-check / security tooling that could count violations."""
    found: set[str] = set()
    for pattern in _COUNTING_CONFIG_GLOBS:
        found.update(inventory.match(pattern))
    if _text_matches(inventory, "pyproject.toml", _PYPROJECT_TOOL_RE):
        found.add("pyproject.toml")
    for rel in ("setup.cfg", "tox.ini"):
        if _text_matches(inventory, rel, _SETUP_CFG_TOOL_RE):
            found.add(rel)
    verbs = resolve_verbs(inventory, stack)
    for verb in ("lint", "typecheck", "security"):
        binding = verbs.get(verb)
        if binding is not None:
            found.add(f"{binding.runner}:{binding.verb}")
    return sorted(found)


def _budget_evidence(inventory: Inventory, stack) -> list[str]:
    found: set[str] = set()
    for rel in _RUNNER_MANIFESTS:
        text = inventory.read(rel)
        if text and _BUDGET_RE.search(text):
            found.add(rel)
    for pattern in _COUNTING_CONFIG_GLOBS:
        for rel in inventory.match(pattern):
            text = inventory.read(rel)
            if text and _BUDGET_RE.search(text):
                found.add(rel)
    for binding in resolve_verbs(inventory, stack).values():
        if _BUDGET_RE.search(binding.command):
            found.add(f"{binding.runner}:{binding.verb}")
    return sorted(found)


def _recognised(inventory: Inventory, stack) -> bool:
    """Whether a recognised ecosystem or a project configuration exists at all."""
    if stack.ecosystems:
        return True
    for pattern in (
        "package.json",
        "pyproject.toml",
        "setup.py",
        "requirements*.txt",
        "Pipfile",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "go.mod",
        "Cargo.toml",
        "Gemfile",
        "composer.json",
    ):
        if inventory.match(pattern):
            return True
    return False
