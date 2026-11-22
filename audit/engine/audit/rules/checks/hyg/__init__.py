# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`HYG` pack — repository hygiene (informational, never scored).

Anchor: `docs/framework/phased-approach.md` § Phase 1: Agentic Bootstrap.

Implemented here: `HYG-01` … `HYG-11` and `HYG-13` (`HYG-12` is reserved for a planned release-provenance
check). Every check reads its artifact through
:class:`audit.scan.Inventory`; none writes to the target and none runs a command in the target's
toolchain — `HYG-07` reads git metadata, read-only, through :func:`_git_output`.

Verdict contract for this pack — **absent artifacts are `FAIL`**. These checks are informational
(`scored=False` in the registry), so a `FAIL` is a reported fact and does not move the readiness
number. ``UNKNOWN`` is reserved for "the artifact is present but its quality cannot be settled":
an unreadable README, an undatable changelog, or an unrecognisable CI provider for branch
protection. It is never used merely because an artifact is absent, with one exception: `HYG-13` reads the content
of the file whose presence `HYG-05` reports, so with no such file it is ``UNKNOWN`` and `HYG-05` owns the finding.

* **HYG-01** — a root `README*` is the evidence. Present and at least
  :data:`MIN_README_CHARS` characters of body, free of a :data:`STUB_MARKERS` marker and not a bare
  title, is `PASS`. Present but below the bar is `FAIL` (with the file as evidence); present but
  unreadable (binary or oversized) is ``UNKNOWN``; absent is `FAIL`.
* **HYG-02** — `CODEOWNERS` at the root, under `.github/`, `.gitlab/` or `docs/`.
* **HYG-03** — any `pull_request_template*` (case-insensitive), normally under `.github/`.
* **HYG-04** — at least one file under `.github/ISSUE_TEMPLATE/`, or `.github/ISSUE_TEMPLATE.md`.
* **HYG-05** — a `CONTRIBUTING*` document at the root or under `.github/`, `.gitlab/` or `docs/`.
* **HYG-06** — a `SECURITY*` document at the same places.
* **HYG-07** — a `CHANGELOG*` document, **dated recently**. This is the only time-sensitive rule.
  Recency is derived from the repository's own git history, never from wall-clock time (AGENTS.md §5):
  the changelog's last commit date is compared with the `HEAD` commit date and is "recent" when it
  falls within :data:`RECENT_WINDOW`. When git cannot supply either date — no repository, git absent,
  or the changelog untracked — the verdict is ``UNKNOWN``, not ``FAIL`` and never ``date.today()``.
* **HYG-08** — a text/markdown document whose filename contains "release" (a release process or
  release-notes page), at the same places. CI workflow files named `release.yml` are not documents and do
  not count.
* **HYG-09** — Dependabot or Renovate configuration at any of its conventional locations, read for two defects
  that hold whatever update policy the owner chose. (1) **Coverage:** every ecosystem the stack names from a
  manifest, plus `github-actions` when GitHub CI is detected, has a Dependabot entry of an accepted
  `package-ecosystem` (:data:`_DEPENDABOT_ECOSYSTEMS`); Renovate covers every manager unless `enabledManagers`
  leaves one out (:data:`_RENOVATE_MANAGERS`). (2) **The `target-branch` trap:** a Dependabot entry that sets
  `target-branch` together with `ignore` or `groups`, whose options then do not apply to security updates. Either
  defect is `PARTIAL`. A configuration whose content cannot be read (no `updates:` list, invalid JSON) is
  ``UNKNOWN`` when it is the only one or when an ecosystem is uncovered; `renovate.json5` and `renovate.config.js`
  count on presence. Coverage is per ecosystem, not per directory.
* **HYG-10** — a root license file: `LICENSE*`, `LICENCE*`, `COPYING*`, `COPYRIGHT*` or `UNLICENSE*`
  (case-insensitive, bare name or document suffix).
* **HYG-11** — branch protection declared as code, where the provider allows it
  (:func:`audit.rules.checks._common.declared_branch_rules`). A GitHub ruleset file (`.github/rulesets/*.json`), the
  Settings app's `branches:` (`.github/settings.yml`), a Terraform protection resource, or a non-document file whose
  path names branch protection is `PASS`; when the rules protect an integration branch (`dev`, `develop`, ...) and
  another branch, a workflow must also read the pull request's source branch (GitHub `github.head_ref`, GitLab
  `CI_MERGE_REQUEST_SOURCE_BRANCH_NAME`), or the verdict is `PARTIAL`. A document only (`docs/branch-protection.md`)
  records the rules without declaring them: `PARTIAL`. A ruleset file that is not a ruleset is ``UNKNOWN``. None
  found is `FAIL` when the CI provider offers config-as-code (GitHub, GitLab); otherwise ``UNKNOWN``, because
  whether protection *can* be declared as code is provider-dependent. Live settings are never read (no network).
* **HYG-13** — the content of the `CONTRIBUTING*` documents `HYG-05` finds, read for three items (P9.3.3 a to c):
  (a) a pointer to the setup command, a Markdown link to `README.md` or `AGENTS.md` or a named setup command
  (:data:`_SETUP_LINK_RE`, :data:`_SETUP_COMMAND_RE`); (b) the gate command (:data:`_GATE_COMMAND_RE`) and a paragraph
  that names CI and says "same" or names the gate command; (c) the words for branches, commits and pull requests
  (:data:`_WORKFLOW_SUBJECTS`). All three is `PASS`, one or two `PARTIAL`, none `FAIL`; no document is ``UNKNOWN``.

Presence is repository-level (ADR-0008): a hygiene file counts at the root or under `.github/`, `.gitlab/` or
`docs/` (:func:`_repository_level`), never in a component's or a template's directory. Carried data
(`templates/`, `examples/`, `fixtures/`) is not in the inventory at all.

Deliberate limit, recorded rather than hidden: "recently" is always relative to the repository's
latest commit, so an abandoned repository is judged on its own clock, not the audit machine's.
"""

from __future__ import annotations

from audit.rules.checks.hyg import (
    hyg_01,
    hyg_02,
    hyg_03,
    hyg_04,
    hyg_05,
    hyg_06,
    hyg_07,
    hyg_08,
    hyg_09,
    hyg_10,
    hyg_11,
    hyg_13,
)
from audit.rules.checks.hyg._shared import (
    _DOC_SUFFIXES as _DOC_SUFFIXES,
    _RENOVATE_JSON as _RENOVATE_JSON,
    _outcome as _outcome,
    _finding as _finding,
    _basename as _basename,
    _REPOSITORY_LEVEL_DIRS as _REPOSITORY_LEVEL_DIRS,
    _repository_level as _repository_level,
    _present as _present,
    _named_documents as _named_documents,
)
from audit.rules.checks.hyg.hyg_01 import (
    MIN_README_CHARS as MIN_README_CHARS,
    STUB_MARKERS as STUB_MARKERS,
    FILLER_MARKERS as FILLER_MARKERS,
    STUB_MARKER_ANYWHERE_CHARS as STUB_MARKER_ANYWHERE_CHARS,
    _LINE_MARKUP_RE as _LINE_MARKUP_RE,
    _MARKER_END_RE as _MARKER_END_RE,
    _marker_line as _marker_line,
    _readme_reason as _readme_reason,
    check_hyg01 as check_hyg01,
)
from audit.rules.checks.hyg.hyg_02 import check_hyg02 as check_hyg02
from audit.rules.checks.hyg.hyg_03 import check_hyg03 as check_hyg03
from audit.rules.checks.hyg.hyg_04 import check_hyg04 as check_hyg04
from audit.rules.checks.hyg.hyg_05 import check_hyg05 as check_hyg05
from audit.rules.checks.hyg.hyg_06 import check_hyg06 as check_hyg06
from audit.rules.checks.hyg.hyg_07 import (
    RECENT_WINDOW as RECENT_WINDOW,
    _git_output as _git_output,
    _commit_date as _commit_date,
    check_hyg07 as check_hyg07,
)
from audit.rules.checks.hyg.hyg_08 import _documents_containing as _documents_containing, check_hyg08 as check_hyg08
from audit.rules.checks.hyg.hyg_09 import (
    _DEPENDENCY_AUTOMATION as _DEPENDENCY_AUTOMATION,
    _RENOVATE_UNPARSED as _RENOVATE_UNPARSED,
    _DEPENDABOT_ECOSYSTEMS as _DEPENDABOT_ECOSYSTEMS,
    _RENOVATE_MANAGERS as _RENOVATE_MANAGERS,
    _TRAPPED_OPTIONS as _TRAPPED_OPTIONS,
    _UpdateEntry as _UpdateEntry,
    _AutomationConfig as _AutomationConfig,
    _scalar as _scalar,
    _dependabot_entries as _dependabot_entries,
    _read_dependabot as _read_dependabot,
    _read_renovate as _read_renovate,
    _required_coverage as _required_coverage,
    _coverage_label as _coverage_label,
    check_hyg09 as check_hyg09,
)
from audit.rules.checks.hyg.hyg_10 import check_hyg10 as check_hyg10
from audit.rules.checks.hyg.hyg_11 import (
    _PROTECTION_PROVIDERS as _PROTECTION_PROVIDERS,
    _INTEGRATION_BRANCHES as _INTEGRATION_BRANCHES,
    _SOURCE_BRANCH_TOKENS as _SOURCE_BRANCH_TOKENS,
    _NOT_A_SOURCE_CHECK_RE as _NOT_A_SOURCE_CHECK_RE,
    _protection_pages as _protection_pages,
    _two_branch_model as _two_branch_model,
    _source_branch_check as _source_branch_check,
    check_hyg11 as check_hyg11,
)
from audit.rules.checks.hyg.hyg_13 import (
    _SETUP_LINK_RE as _SETUP_LINK_RE,
    _SETUP_COMMAND_RE as _SETUP_COMMAND_RE,
    _GATE_COMMAND_RE as _GATE_COMMAND_RE,
    _CI_WORD_RE as _CI_WORD_RE,
    _SAME_RE as _SAME_RE,
    _WORKFLOW_SUBJECTS as _WORKFLOW_SUBJECTS,
    _CONTRIBUTING_ITEMS as _CONTRIBUTING_ITEMS,
    _paragraphs as _paragraphs,
    _first_line as _first_line,
    _ci_runs_the_gate as _ci_runs_the_gate,
    _contributing_items as _contributing_items,
    check_hyg13 as check_hyg13,
)
from audit.rules.spec import CheckSpec

#: The HYG checks (informational, never scored), in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    hyg_01.SPEC,
    hyg_02.SPEC,
    hyg_03.SPEC,
    hyg_04.SPEC,
    hyg_05.SPEC,
    hyg_06.SPEC,
    hyg_07.SPEC,
    hyg_08.SPEC,
    hyg_09.SPEC,
    hyg_10.SPEC,
    hyg_11.SPEC,
    hyg_13.SPEC,
)

IMPLEMENTATIONS = {
    "HYG-01": check_hyg01,
    "HYG-02": check_hyg02,
    "HYG-03": check_hyg03,
    "HYG-04": check_hyg04,
    "HYG-05": check_hyg05,
    "HYG-06": check_hyg06,
    "HYG-07": check_hyg07,
    "HYG-08": check_hyg08,
    "HYG-09": check_hyg09,
    "HYG-10": check_hyg10,
    "HYG-11": check_hyg11,
    "HYG-13": check_hyg13,
}
