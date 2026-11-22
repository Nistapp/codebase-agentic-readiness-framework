# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`BASE` pack — quality baselines and the no-new-violations ratchet.

Anchor: `docs/framework/phased-approach.md` § Activities ("Establish quality baselines for
existing technical debt", "Enforce a **no new violations** policy") and § Key Deliverables
("Quality baselines | Config files | CI").

Implemented here: `BASE-01` … `BASE-04`.

The pack verifies that a repository has a **quality baseline** it can be measured against, that it
*measures* violations, that it refuses to let the count grow, and that it holds a coverage floor.
The audit never runs the target's tools (that would be Tier C); it reads the committed configuration
and artifacts, and records the method it used.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **BASE-01** — a committed baseline or suppression artifact (`.eslint-baseline*`,
  `.ruff-baseline*`, `.mypy-baseline*`, `baseline.json`, `coverage-baseline.*`, `.snyk`,
  `.gitleaksignore`, …), or an equivalent mechanism documented in `AGENTS.md`/`CLAUDE.md`. Tooling
  that could *produce* a baseline without one being committed is `PARTIAL`, not `PASS`.
* **BASE-02** — whether a violation **count** is committed. The only count this static scan can
  point at exactly is an explicit numeric budget (`--max-warnings N`, `max-issues`, a
  `violation budget`); a committed baseline artifact or a configured lint/type/security tool is a
  mechanism but not a count, so it is `PARTIAL`. The check **never** returns `FAIL`: the audit
  cannot run the target's tools, so it cannot prove no count exists. The `detail` always states the
  method used.
* **BASE-03** — a committed ratchet: a numeric violation budget, a baseline artifact that a CI
  workflow references (a comparison step), or a comparison step documented in the entry docs.
  A repository that has committed a baseline but does nothing that compares against it is `FAIL` —
  the debt is measured but not guarded. A repository with no measurement surface at all is
  `PARTIAL`: there is nothing yet for a ratchet to compare, so absence is not proof of the policy.
* **BASE-04** — a coverage threshold in test-runner configuration (`coverage.fail_under`,
  `--cov-fail-under`, `coverageThreshold`, vitest/jest `thresholds`), or a JaCoCo floor in a build file: a Gradle
  `jacocoTestCoverageVerification` task with a `minimum`, or a Maven `jacoco-maven-plugin` `check` goal with a
  `<minimum>`. Runner configs, every `package.json` and the Gradle and Maven build files count at any depth, so
  an app's own build counts in a repository with an app per folder. A threshold stated only in
  prose is `PARTIAL`. No threshold and no prose, in a recognised repository, is `FAIL`.

No recognised ecosystem and no configuration at all ⇒ every check returns `UNKNOWN`, never `PASS`.

Deliberate limits, recorded rather than hidden. **Artifacts are matched by name, not parsed** — a
`baseline.json` is evidence it exists, not proof it is current or adequate (`baseline-adequacy` is
on the unattested list). **A baseline does not count for BASE-02**, which asks specifically for a
number the audit can see without running a tool. The audit never executes a formatter, linter or
scanner; every verdict above is derived from committed text.

The ``AuditResult.regressions()`` ratchet this pack reports on lives in ``audit/evaluate.py``; it
compares stable finding ids (`check id + path`) against a previously emitted JSON report.
"""

from __future__ import annotations

from audit.rules.checks.base import base_01, base_02, base_03, base_04
from audit.rules.checks.base._shared import (
    _BASELINE_GLOBS as _BASELINE_GLOBS,
    _DOCS as _DOCS,
    _COUNTING_CONFIG_GLOBS as _COUNTING_CONFIG_GLOBS,
    _PYPROJECT_TOOL_RE as _PYPROJECT_TOOL_RE,
    _SETUP_CFG_TOOL_RE as _SETUP_CFG_TOOL_RE,
    _BUDGET_RE as _BUDGET_RE,
    _RUNNER_MANIFESTS as _RUNNER_MANIFESTS,
    _outcome as _outcome,
    _unknown as _unknown,
    _finding as _finding,
    _baseline_artifacts as _baseline_artifacts,
    _text_matches as _text_matches,
    _counting_tools as _counting_tools,
    _budget_evidence as _budget_evidence,
    _recognised as _recognised,
)
from audit.rules.checks.base.base_01 import (
    _DOC_BASELINE_RE as _DOC_BASELINE_RE,
    _documented_baseline as _documented_baseline,
    check_base01 as check_base01,
)
from audit.rules.checks.base.base_02 import _METHOD as _METHOD, check_base02 as check_base02
from audit.rules.checks.base.base_03 import (
    _DOC_RATCHET_RE as _DOC_RATCHET_RE,
    _ci_references_baseline as _ci_references_baseline,
    _ratchet as _ratchet,
    check_base03 as check_base03,
)
from audit.rules.checks.base.base_04 import (
    _FLOOR_FILES as _FLOOR_FILES,
    _FLOOR_FILE_RE as _FLOOR_FILE_RE,
    _COVERAGE_CONFIG_GLOBS as _COVERAGE_CONFIG_GLOBS,
    _COVERAGE_CONFIG_RE as _COVERAGE_CONFIG_RE,
    _PACKAGE_FLOOR_RE as _PACKAGE_FLOOR_RE,
    _GRADLE_BUILDS as _GRADLE_BUILDS,
    _GRADLE_JACOCO_RE as _GRADLE_JACOCO_RE,
    _GRADLE_MINIMUM_RE as _GRADLE_MINIMUM_RE,
    _MAVEN_JACOCO_RE as _MAVEN_JACOCO_RE,
    _MAVEN_CHECK_RE as _MAVEN_CHECK_RE,
    _MAVEN_MINIMUM_RE as _MAVEN_MINIMUM_RE,
    _XML_COMMENT_RE as _XML_COMMENT_RE,
    _COVERAGE_PROSE_RE as _COVERAGE_PROSE_RE,
    _coverage_floor_config as _coverage_floor_config,
    _strip_js_comments as _strip_js_comments,
    _coverage_prose as _coverage_prose,
    check_base04 as check_base04,
)
from audit.rules.spec import CheckSpec

#: The BASE checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    base_01.SPEC,
    base_02.SPEC,
    base_03.SPEC,
    base_04.SPEC,
)

IMPLEMENTATIONS = {
    "BASE-01": check_base01,
    "BASE-02": check_base02,
    "BASE-03": check_base03,
    "BASE-04": check_base04,
}
