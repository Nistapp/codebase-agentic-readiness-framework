# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TST-04: Fast path documented."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import at_root, entry_documents, extract_documented_commands
from audit.rules.checks.tst._shared import _finding, _outcome, _test_files, _unknown

SPEC = declare("TST-04", "Fast path documented", "B", Severity.DEGRADER)

#: Entry documents read for a documented fast path, in fixed order.
_FASTPATH_DOCS: tuple[str, ...] = ("README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md")

#: A single-test or subset invocation, per runner. Deliberately excludes a plain full-suite run
#: (``npm test``, ``pytest``), which is the gate TST-01 already covers.
_FASTPATH_PATTERNS: tuple[str, ...] = (
    r"\bpytest\b[^\n&|;]*\s-k\b",
    r"\bpytest\b[^\n&|;]*::[A-Za-z_]\w*",
    r"\bpython3?\s+-m\s+pytest\b[^\n&|;]*\s-k\b",
    r"\bpython3?\s+-m\s+unittest\b[^\n&|;]*\s-k\b",
    r"\bnpm\s+(?:run\s+)?(?:test|t)\s+--\s+\S+",
    r"\b(?:pnpm|yarn|bun)\s+(?:run\s+)?(?:test|t)\s+(?:--\s+)?\S+",
    r"\b(?:npx\s+)?vitest\s+run\s+\S*(?:test|spec)\S*",
    r"\b(?:npx\s+)?vitest\b[^\n&|;]*\s(?:-t|--testNamePattern)\b",
    r"\b(?:npx\s+)?jest\b[^\n&|;]*\s(?:-t|--testNamePattern)\b",
    r"\b(?:npx\s+)?jest\b[^\n&|;]*\s\S*\.(?:test|spec)\.\S*",
    r"\breact-scripts\s+test\b[^\n&|;]*\s\S*\.(?:test|spec)\.\S*",
    r"\bgo\s+test\b[^\n&|;]*\s-run\b",
    r"\bcargo\s+test\b\s+[A-Za-z_]\w*",
    r"\b(?:\./)?(?:gradlew|gradle)\b[^\n&|;]*--tests\b",
    r"\bmvn\b[^\n&|;]*-Dtest=",
    r"\bdotnet\s+test\b[^\n&|;]*--filter\b",
    r"\bmocha\b[^\n&|;]*\s-g\b",
    r"\brspec\b[^\n&|;]*\S+\.rb(?::\d+)?",
    r"\btox\b[^\n&|;]*-e\b",
)
_FASTPATH_RE = re.compile("|".join(_FASTPATH_PATTERNS))


# ===========================================================================
# TST-04 — fast path documented
# ===========================================================================


def check_tst04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    files = _test_files(inventory)
    if not files:
        return _unknown(spec, "no test file is present, so there is no suite for a fast path to act on (see TST-01)")

    docs = [rel for rel in entry_documents(inventory, _FASTPATH_DOCS) if inventory.has(rel) and at_root(inventory, rel)]
    scope = ", ".join(docs) if docs else f"{', '.join(_FASTPATH_DOCS)} (none present)"

    commands = [(rel, extract_documented_commands(text)) for rel in docs if (text := inventory.read(rel))]
    for rel, found in commands:
        for language, line, command in found:
            if language != "inline" and _FASTPATH_RE.search(command):
                return _outcome(spec, Verdict.PASS, f"fast path documented: {rel}:{line} `{command}` (scope: {scope})")
    for rel, found in commands:
        for language, line, command in found:
            if language == "inline" and _FASTPATH_RE.search(command):
                return _outcome(
                    spec,
                    Verdict.PASS,
                    f"fast path documented in an inline code span: {rel}:{line} `{command}` (scope: {scope})",
                )

    return _outcome(
        spec,
        Verdict.FAIL,
        f"no single-test/subset invocation in fenced shell blocks or inline code spans (scope: {scope})",
        [
            _finding(
                spec,
                "run one test or a subset without the whole suite",
                f"none of the entry documents shows a single-test or subset invocation (scope: {scope})",
                Verdict.FAIL,
                [Evidence(rel) for rel in docs] or [Evidence("<repository>")],
                "Document a fast path (for example `pytest -k <name>`, "
                "`npm test -- <name>`, or `go test -run <name>`) in a fenced shell block or as inline code.",
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.checks import tst
    from audit.rules.reads import ANY_DEPTH, GLOB, Reads, SCAN_KIND, What, _at, _held

    return Reads(
        where=(
            *_held(tst, "_FASTPATH_DOCS", ANY_DEPTH),
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
            *_held(tst, "_FRAMEWORK_TEST_GLOBS", ANY_DEPTH, {"tests/*.rs": GLOB}),
        ),
        what=What("fenced-command"),
        binding="line",
        note=(
            "Only bash, sh, shell, console or zsh fences count, each physical line is one command, and a "
            "plain full-suite run does not count. With no fenced match, an inline code span outside any fence "
            "is read with the same patterns. A file is kept only at the root, so a nested-only copy is "
            "skipped. README.md stands for the root README: the root file whose name starts with readme, any "
            "case, README.md first, as for HYG-01. The test files "
            "give the runner family: the scanned files with a test hint, as in TST-01, and the two framework globs."
        ),
    )
