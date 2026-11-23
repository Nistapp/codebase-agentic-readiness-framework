# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`TST` pack — tests.

Anchor: `docs/framework/phased-approach.md` § Activities.

Implemented here: `TST-01` … `TST-05`.

The pack verifies that the test surface is *runnable and situated*: a test verb and a suite (TST-01),
a known suite status (TST-02, the only Tier-C probe in the pack), a skip/xfail census (TST-03), a
documented fast path (TST-04), and coverage reporting (TST-05). The test verb is read the same way
CMD/CI/TOOL read it — through `audit.rules.checks._common.resolve_verbs` — so the packs cannot drift.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **TST-01** — a resolvable `test` verb **and** at least one test file. A test file is a source file
  classified `audit.scan.Kind.TEST` by the scan hints (``test_``, ``_test.``, ``.test.``, ``.spec.``,
  ``tests/``, ``test/``, ``__tests__/``), restricted to test-source suffixes so a config file such as
  `tsconfig.test.json` or `vitest.config.ts` is never mistaken for a test. Verb without files, or files
  without a verb, is `PARTIAL` (the finding is `DEGRADER`: half the surface exists). Neither, with a
  recognised ecosystem, is `FAIL`; neither with **no** recognised ecosystem is `UNKNOWN` — an
  unrecognised repository is not proof of absence.
* **TST-02 (Tier C)** — the resolved `test` verb is run as a `ProbePlan(verb="test", read_only=True)`.
  The probe is refused unless `--run-gates` **and** `--allow-probe test`; a refusal is recorded in the
  report's `probes` array and the verdict is `UNKNOWN`, never an error (AGENTS.md §2.2, ADR-0002).
  Exit 0 is `PASS`, a non-zero exit is `FAIL`, and a timed-out or unpermitted probe is `UNKNOWN`.
  No mutating verb is ever constructed here. A verb read from a `package.json` runs with each
  `node_modules/.bin` from that manifest's directory up to the root first on `PATH`, as `npm run` sets it,
  so a script body such as `jest` resolves; nothing is installed and nothing else changes.
* **TST-03** — a **census**, not a threshold: the count of skip, ignore and expected-failure markers in
  each readable test file, grouped by the language family that file belongs to (javascript/vitest/jest/
  mocha, python, go, rust, jvm). Zero markers is a `PASS`; no test file, or no readable test file,
  is `UNKNOWN`. This check never invents a maximum.
* **TST-04** — a single-test/subset invocation in a fenced shell block, read from the repository's
  root entry documents (the root README by any name, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`), or else in
  an inline code span outside a fence (`npm test -- <path>` in a sentence), both via
  `_common.extract_documented_commands`. A fenced one is cited first. `PASS` when one is documented; `FAIL` when the documents are
  readable but none shows one. With **no test file** there is no suite for a fast path to act on, so
  the verdict is `UNKNOWN` — a missing suite is TST-01's finding, not doubled here. The search scope is
  stated in `detail`.
* **TST-05** — coverage reporting configured for the test runner: a coverage config file, a
  `coverage` block in a runner config (`vitest`/`jest`/`vite`), a package script or resolved verb
  invoking a coverage tool (`--coverage`, `--cov`, `c8`, `nyc`, `jacoco`, `go test -cover`), or a
  `[tool.coverage]` section. Present is `PASS`; absent is `FAIL` (`COSMETIC`). Coverage is **not**
  run — that would be Tier C.

Deliberate limits, recorded rather than hidden. **Test-file discovery is the scan's classification**,
filtered to source suffixes; a suite laid out under none of the conventions above is not seen and
degrades to `UNKNOWN`, never a false `PASS`. **Marker patterns are language-family heuristics**, not a
parse — a marker inside a string literal is counted too, which is acceptable for a census. **Fast-path
and coverage detection are textual**, against a documented pattern set; a command hidden inside a
quoted string or an exotic runner is not seen.
"""

from __future__ import annotations

from audit.rules.checks.tst import tst_01, tst_02, tst_03, tst_04, tst_05
from audit.rules.checks.tst._shared import (
    _TEST_SOURCE_SUFFIXES as _TEST_SOURCE_SUFFIXES,
    _FRAMEWORK_TEST_GLOBS as _FRAMEWORK_TEST_GLOBS,
    _outcome as _outcome,
    _unknown as _unknown,
    _finding as _finding,
    _test_files as _test_files,
)
from audit.rules.checks.tst.tst_01 import (
    check_tst01 as check_tst01,
)
from audit.rules.checks.tst.tst_02 import (
    _runner_path as _runner_path,
    check_tst02 as check_tst02,
)
from audit.rules.checks.tst.tst_03 import (
    _FAMILY_BY_SUFFIX as _FAMILY_BY_SUFFIX,
    _JS_MARKERS as _JS_MARKERS,
    _MARKER_PATTERNS as _MARKER_PATTERNS,
    _family_for as _family_for,
    check_tst03 as check_tst03,
)
from audit.rules.checks.tst.tst_04 import (
    _FASTPATH_DOCS as _FASTPATH_DOCS,
    _FASTPATH_PATTERNS as _FASTPATH_PATTERNS,
    _FASTPATH_RE as _FASTPATH_RE,
    check_tst04 as check_tst04,
)
from audit.rules.checks.tst.tst_05 import (
    _COVERAGE_FILES as _COVERAGE_FILES,
    _COVERAGE_TOOL_RE as _COVERAGE_TOOL_RE,
    _COVERAGE_CONFIG_GLOBS as _COVERAGE_CONFIG_GLOBS,
    _COVERAGE_CONFIG_RE as _COVERAGE_CONFIG_RE,
    _coverage_evidence as _coverage_evidence,
    _read_matches as _read_matches,
    check_tst05 as check_tst05,
)
from audit.rules.spec import CheckSpec

#: The TST checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    tst_01.SPEC,
    tst_02.SPEC,
    tst_03.SPEC,
    tst_04.SPEC,
    tst_05.SPEC,
)

IMPLEMENTATIONS = {
    "TST-01": check_tst01,
    "TST-02": check_tst02,
    "TST-03": check_tst03,
    "TST-04": check_tst04,
    "TST-05": check_tst05,
}
