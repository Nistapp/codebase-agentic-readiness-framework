# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TST-05: Coverage configuration present."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import resolve_verbs
from audit.stack import extract_npm_scripts
from audit.rules.checks.tst._shared import _finding, _outcome

SPEC = declare("TST-05", "Coverage configuration present", "A", Severity.COSMETIC)

#: Coverage configuration filenames. Present at any depth is evidence.
_COVERAGE_FILES: tuple[str, ...] = (
    ".coveragerc",
    ".coveragerc.toml",
    ".nycrc",
    ".nycrc.json",
    ".nycrc.yml",
    ".nycrc.yaml",
    "nyc.config.js",
    "nyc.config.cjs",
    ".c8rc",
    ".c8rc.json",
    "codecov.yml",
    ".codecov.yml",
    ".codecov.yaml",
    "coveralls.yml",
    ".coveralls.yml",
)

#: A command that turns coverage on. Matched against package scripts and resolved verb commands.
_COVERAGE_TOOL_RE = re.compile(
    r"--(?:coverage|cov)\b|\b(?:c8|nyc|jacoco|cobertura|coveralls|codecov)\b"
    r"|\bgo\s+test\b[^\n&|;]*-cover\b"
)

#: Runner config globs that enable coverage through a config key rather than a script flag.
_COVERAGE_CONFIG_GLOBS: tuple[str, ...] = (
    "vitest.config.*",
    "jest.config.*",
    "vite.config.*",
    "karma.conf.*",
)
_COVERAGE_CONFIG_RE = re.compile(r"(?m)^\s*coverage\s*:|[\"']coverage[\"']\s*:")


# ===========================================================================
# TST-05 — coverage configuration
# ===========================================================================


def _coverage_evidence(inventory, stack) -> list[str]:
    found = [name for name in _COVERAGE_FILES if inventory.has(name)]

    if any(_COVERAGE_TOOL_RE.search(command) for command in extract_npm_scripts(inventory).values()):
        found.append("package.json script")
    if _read_matches(inventory, "pyproject.toml", r"(?ms)^\[tool\.coverage"):
        found.append("pyproject.toml [tool.coverage]")
    for rel, pattern in (
        ("setup.cfg", r"(?m)^\[coverage"),
        ("tox.ini", r"(?m)^\[coverage"),
        ("pytest.ini", r"--cov\b"),
        ("pom.xml", r"jacoco"),
        ("build.gradle", r"jacoco"),
        ("build.gradle.kts", r"jacoco"),
    ):
        if _read_matches(inventory, rel, pattern):
            found.append(rel)

    for glob in _COVERAGE_CONFIG_GLOBS:
        for rel in inventory.match(glob):
            text = inventory.read(rel)
            if text and _COVERAGE_CONFIG_RE.search(text):
                found.append(rel)

    for binding in resolve_verbs(inventory, stack).values():
        if _COVERAGE_TOOL_RE.search(binding.command):
            found.append(f"{binding.runner}:{binding.verb}")

    return sorted(set(found))


def _read_matches(inventory, rel: str, pattern: str) -> bool:
    text = inventory.read(rel)
    return bool(text and re.search(pattern, text))


def check_tst05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    evidence = _coverage_evidence(inventory, stack)
    if evidence:
        return _outcome(spec, Verdict.PASS, f"coverage configured: {', '.join(evidence)}")

    return _outcome(
        spec,
        Verdict.FAIL,
        "no coverage configuration",
        [
            _finding(
                spec,
                "see how much of the code the suite actually covers",
                "no coverage configuration or coverage-invoking command is present",
                Verdict.FAIL,
                [Evidence("<repository>")],
                "Configure coverage for the test runner (a `coverage` block, `.coveragerc`/`.nycrc`, "
                "`--coverage`/`--cov`, or `go test -cover`).",
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, ROOT, Reads, What, _at, _runners

    return Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".coveragerc",
                ".coveragerc.toml",
                ".nycrc",
                ".nycrc.json",
                ".nycrc.yml",
                ".nycrc.yaml",
                "nyc.config.js",
                "nyc.config.cjs",
                ".c8rc",
                ".c8rc.json",
                "codecov.yml",
                ".codecov.yml",
                ".codecov.yaml",
                "coveralls.yml",
                ".coveralls.yml",
            ),
            *_at(
                ROOT,
                "setup.cfg",
                "tox.ini",
                "pytest.ini",
            ),
            *_at(ANY_DEPTH, "vitest.config.*", "jest.config.*", "vite.config.*", "karma.conf.*"),
            *_runners(),
        ),
        what=What("key"),
        binding="file",
        note=(
            "Coverage config names count on presence at any depth; the root files are read for "
            "[tool.coverage, [coverage, --cov or jacoco; a runner config at any depth for a coverage key; "
            "package scripts and resolved verbs for --coverage, --cov, c8, nyc, jacoco or go test -cover."
        ),
    )
