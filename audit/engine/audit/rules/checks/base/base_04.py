# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""BASE-04: Coverage floor configured."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import README, entry_documents
from audit.scan import Inventory
from audit.rules.checks.base._shared import _DOCS, _finding, _outcome, _recognised, _unknown

SPEC = declare("BASE-04", "Coverage floor configured", "A", Severity.DEGRADER)


#: Configs that carry a coverage floor, and a runner config that enables it through a key.
_FLOOR_FILES: tuple[str, ...] = (
    ".coveragerc",
    ".coveragerc.toml",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
    "pyproject.toml",
)
_FLOOR_FILE_RE = re.compile(r"(?i)fail_under\s*[:=]\s*\d+|--cov-fail-under(?:=|\s+)\d+")

_COVERAGE_CONFIG_GLOBS: tuple[str, ...] = (
    "vitest.config.*",
    "jest.config.*",
    "vite.config.*",
    "karma.conf.*",
)
_COVERAGE_CONFIG_RE = re.compile(
    r"(?i)coverageThreshold|\bthresholds\b\s*[:=]|fail_under\s*[:=]\s*\d+"
    r"|--cov-fail-under(?:=|\s+)\d+"
)

#: A ``coverageThreshold`` (Jest) or ``--cov-fail-under`` in a ``package.json`` at any depth, so an app's own manifest
#: counts in a repository with an app per folder.
_PACKAGE_FLOOR_RE = re.compile(r"coverageThreshold|--cov-fail-under")

#: A JaCoCo floor in a Gradle build: the ``jacocoTestCoverageVerification`` task with a ``minimum`` in a limit
#: (``minimum = 0.80``, ``minimum = "0.80".toBigDecimal()``, ``minimum.set(...)``).
_GRADLE_BUILDS: tuple[str, ...] = ("build.gradle", "build.gradle.kts")
_GRADLE_JACOCO_RE = re.compile(r"\bjacocoTestCoverageVerification\b")
_GRADLE_MINIMUM_RE = re.compile(r"\bminimum\s*(?:=|\.set\s*\()")

#: A JaCoCo floor in a Maven build: ``jacoco-maven-plugin`` running its ``check`` goal with a ``<minimum>``.
_MAVEN_JACOCO_RE = re.compile(r"<artifactId>\s*jacoco-maven-plugin\s*</artifactId>")
_MAVEN_CHECK_RE = re.compile(r"<goal>\s*check\s*</goal>")
_MAVEN_MINIMUM_RE = re.compile(r"<minimum>\s*[\d.]+\s*</minimum>")
_XML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

_COVERAGE_PROSE_RE = re.compile(
    r"(?i)(?:coverage|covered)[^\n]{0,40}(?:threshold|minimum|fail|floor|at least|>=?)"
    r"|(?:threshold|minimum|at least)[^\n]{0,40}coverage"
    r"|\b\d{1,3}\s?%[^\n]{0,20}coverage|coverage[^\n]{0,20}\b\d{1,3}\s?%"
)


def _coverage_floor_config(inventory: Inventory, stack) -> list[str]:
    found: set[str] = set()
    for rel in _FLOOR_FILES:
        text = inventory.read(rel)
        if text and _FLOOR_FILE_RE.search(text):
            found.add(rel)
    for rel in inventory.match("package.json"):
        text = inventory.read(rel)
        if text and _PACKAGE_FLOOR_RE.search(text):
            found.add(rel)
    for pattern in _COVERAGE_CONFIG_GLOBS:
        for rel in inventory.match(pattern):
            text = inventory.read(rel)
            if text and _COVERAGE_CONFIG_RE.search(_strip_js_comments(text)):
                found.add(rel)
    for rel in inventory.match(*_GRADLE_BUILDS):
        text = inventory.read(rel)
        if text:
            code = _strip_js_comments(text)
            if _GRADLE_JACOCO_RE.search(code) and _GRADLE_MINIMUM_RE.search(code):
                found.add(rel)
    for rel in inventory.match("pom.xml"):
        text = inventory.read(rel)
        if text:
            xml = _XML_COMMENT_RE.sub("", text)
            if all(rx.search(xml) for rx in (_MAVEN_JACOCO_RE, _MAVEN_CHECK_RE, _MAVEN_MINIMUM_RE)):
                found.add(rel)
    return sorted(found)


def _strip_js_comments(text: str) -> str:
    """Drop whole-line ``//`` comments so a commented-out threshold is not read as configuration."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def _coverage_prose(inventory: Inventory) -> list[str]:
    found: list[str] = []
    for rel in entry_documents(inventory, _DOCS + (README, "CONTRIBUTING.md")):
        text = inventory.read(rel)
        if not text:
            continue
        for line in text.splitlines():
            if _COVERAGE_PROSE_RE.search(line):
                found.append(f"{rel}:{line.strip()[:80]}")
    return sorted(found)


# ===========================================================================
# BASE-04 — coverage floor configured
# ===========================================================================


def check_base04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    configured = _coverage_floor_config(inventory, stack)
    if configured:
        return _outcome(spec, Verdict.PASS, f"coverage threshold configured: {', '.join(configured)}")

    prose = _coverage_prose(inventory)
    if prose:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"coverage threshold stated in prose only: {'; '.join(prose[:4])}",
            [
                _finding(
                    spec,
                    "know when coverage drops below an agreed floor",
                    "a coverage threshold is described in prose but not configured in the test runner",
                    Verdict.PARTIAL,
                    [Evidence(entry.split(":", 1)[0]) for entry in prose[:4]],
                    "Move the threshold into test-runner configuration (`coverage.fail_under`, "
                    "`--cov-fail-under`, `coverageThreshold`, or a vitest/jest `thresholds` block).",
                )
            ],
        )

    if _recognised(inventory, stack):
        return _outcome(
            spec,
            Verdict.FAIL,
            "no coverage threshold configured",
            [
                _finding(
                    spec,
                    "know when coverage drops below an agreed floor",
                    "no coverage threshold is configured in the test runner",
                    Verdict.FAIL,
                    [Evidence("<repository>")],
                    "Configure a coverage floor for the test runner so a drop fails the gate.",
                )
            ],
        )

    return _unknown(
        spec, "no recognised ecosystem or test-runner configuration, so a coverage floor cannot be ruled out"
    )
