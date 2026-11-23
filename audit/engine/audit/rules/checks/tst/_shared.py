# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one TST check uses."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.payloads import Payload
from audit.scan import Kind

#: Suffixes a *test source* file can carry. A file classified ``Kind.TEST`` by a directory hint
#: (``test/``, ``tests/``) but carrying another suffix (``.json``) is configuration, not a test.
_TEST_SOURCE_SUFFIXES: tuple[str, ...] = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".rb",
    ".cs",
    ".php",
)

#: Framework-specific test-file globs, in addition to the scan's classification.
_FRAMEWORK_TEST_GLOBS: tuple[str, ...] = ("*_test.go", "tests/**/*.rs")


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
    severity: Severity | None = None,
) -> Finding:
    return Finding(
        check=spec.id,
        severity=severity or spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence,
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# shared readers
# ---------------------------------------------------------------------------


def _test_files(inventory) -> list[str]:
    """Test source files, per the scan's conventions plus the framework test globs."""
    files = {f.rel for f in inventory.files if f.kind is Kind.TEST and f.rel.lower().endswith(_TEST_SOURCE_SUFFIXES)}
    files.update(inventory.match(*_FRAMEWORK_TEST_GLOBS))
    return sorted(files)
