# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TST-01: Test verb exists, suite non-empty."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import resolve_verbs
from audit.rules.checks.tst._shared import _finding, _outcome, _test_files, _unknown

SPEC = declare("TST-01", "Test verb exists, suite non-empty", "A", Severity.BLOCKER)


# ===========================================================================
# TST-01 — test verb and a non-empty suite
# ===========================================================================


def check_tst01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    binding = resolve_verbs(inventory, stack).get("test")
    files = _test_files(inventory)

    if binding and files:
        return _outcome(
            spec, Verdict.PASS, f"test verb on {binding.runner} ({binding.command}); {len(files)} test file(s)"
        )

    if binding and not files:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"test verb on {binding.runner} ({binding.command}) but no test file matches the framework conventions",
            [
                _finding(
                    spec,
                    "run a real suite rather than an empty one",
                    "a test verb resolves but no test file exists yet",
                    Verdict.PARTIAL,
                    [Evidence(binding.runner, note=binding.command)],
                    "Add a test file (for example `test/` or `src/**/*.test.ts`) so the test verb runs a "
                    "real suite, not an empty one.",
                    severity=Severity.DEGRADER,
                )
            ],
        )

    if files and not binding:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"{len(files)} test file(s) but no resolvable test verb",
            [
                _finding(
                    spec,
                    "run the suite by name",
                    "test files exist but no runner exposes a test verb",
                    Verdict.PARTIAL,
                    [Evidence(rel) for rel in files[:12]],
                    "Define a test verb on the runner (for example `npm test`, a Makefile `test` target, or "
                    "`pytest`) so the suite is reachable without inventing a command.",
                    severity=Severity.DEGRADER,
                )
            ],
        )

    if stack.ecosystems:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no test verb and no test file",
            [
                _finding(
                    spec,
                    "run the test suite",
                    "no test verb resolves and no test file exists",
                    Verdict.FAIL,
                    [Evidence("<repository>")],
                    "Add a test verb and at least one test file so a change set can be verified.",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem, no test verb and no test file, so a suite cannot be ruled out")


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, Reads, SCAN_KIND, What, _at, _runners

    return Reads(
        where=(
            *_runners(),
            *_at(
                GLOB,
                "**/*test_*",
                "**/*_test.*",
                "**/*.test.*",
                "**/*.spec.*",
                "**/tests/**",
                "**/test/**",
                "**/__tests__/**",
                via=SCAN_KIND,
            ),
            *_at(ANY_DEPTH, "*_test.go"),
            *_at(GLOB, "tests/**/*.rs"),
        ),
        what=What("key"),
        binding="file",
        note=(
            "The test verb is resolved from the runner manifests. A test file is a scanned file whose "
            "lower-case path holds a test hint (test_, _test., .test., .spec., tests/, test/, __tests__/) and"
            " has a test-source suffix, plus *_test.go and tests/*.rs; the globs approximate that substring "
            "match."
        ),
    )
