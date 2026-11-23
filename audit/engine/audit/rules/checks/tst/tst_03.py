# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TST-03: Skip / xfail census."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.rules.payloads import Counter
from audit.rules.checks.tst._shared import _outcome, _test_files, _unknown

SPEC = declare("TST-03", "Skip / xfail census", "B", Severity.DEGRADER)

#: Language family by source suffix, for the TST-03 census.
_FAMILY_BY_SUFFIX: dict[str, str] = {
    ".py": "python",
    ".go": "go",
    ".rs": "rust",
    ".java": "jvm",
    ".kt": "jvm",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}

_JS_MARKERS: tuple[str, ...] = (
    r"\b(?:it|test|describe)\.(?:skip|todo|failing|fails)\b",
    r"\b(?:xit|xtest|xdescribe)\b",
)

#: Skip / ignore / expected-failure markers by language family. Keys are families and, for
#: javascript, the test frameworks `stack.test_frameworks` can refine them to.
_MARKER_PATTERNS: dict[str, tuple[str, ...]] = {
    "javascript": _JS_MARKERS,
    "vitest": _JS_MARKERS,
    "jest": _JS_MARKERS,
    "mocha": (r"\b(?:it|describe)\.(?:skip|pending)\b", r"\b(?:xit|xdescribe)\b"),
    "python": (
        r"@pytest\.mark\.(?:skip|xfail)\b",
        r"@unittest\.(?:skip|skipIf|expectedFailure)\b",
        r"\bpytest\.skip\(",
        r"\bunittest\.SkipTest\b",
    ),
    "go": (r"\bt\.Skip(?:Now)?f?\(", r"\btesting\.Short\("),
    "rust": (r"#\[ignore\]",),
    "jvm": (r"@(?:Ignore|Disabled|DisabledOnOs)\b", r"\bassumeTrue\("),
}


def _family_for(rel: str, stack) -> str:
    base = rel.rsplit("/", 1)[-1]
    suffix = "." + base.rsplit(".", 1)[1] if "." in base else ""
    family = _FAMILY_BY_SUFFIX.get(suffix, "")
    if family == "javascript":
        for candidate in ("vitest", "jest", "mocha"):
            if candidate in stack.test_frameworks:
                return candidate
    return family


# ===========================================================================
# TST-03 — skip / xfail census
# ===========================================================================


def check_tst03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    files = _test_files(inventory)
    if not files:
        return _unknown(spec, "no test file is present, so there is no skip/xfail census to take")

    counts: dict[str, int] = {}
    readable = 0
    for rel in files:
        text = inventory.read(rel)
        if text is None:
            continue
        readable += 1
        family = _family_for(rel, stack)
        patterns = _MARKER_PATTERNS.get(family)
        if not patterns:
            continue
        found = sum(1 for pattern in patterns for _ in re.finditer(pattern, text))
        if found:
            counts[family] = counts.get(family, 0) + found

    if readable == 0:
        return _unknown(spec, "no test file could be read for a skip/xfail census")

    total = sum(counts.values())
    breakdown = ", ".join(f"{family} {count}" for family, count in sorted(counts.items()))
    detail = f"skip/xfail census across {readable} test file(s): {breakdown or 'no markers'}; total {total}"
    return _outcome(
        spec,
        Verdict.PASS,
        detail,
        data=Counter(value=total, unit="skip/xfail markers", breakdown=dict(sorted(counts.items()))),
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, Reads, SCAN_KIND, What, _at

    return Reads(
        where=(
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
        what=What("phrase"),
        binding="file",
        note=(
            "Each readable test file of TST-01 is searched for skip, ignore and expected-failure markers of "
            "its language family (by suffix), for example @pytest.mark.skip, it.skip, t.Skip(, #[ignore], "
            "@Disabled. A census: any count passes."
        ),
    )
