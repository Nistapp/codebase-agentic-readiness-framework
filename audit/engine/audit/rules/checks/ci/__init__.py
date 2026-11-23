# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`CI` pack — continuous integration.

Anchor: `docs/framework/phased-approach.md` § Key Deliverables. The normative sentence is the
one-command-surface note in the Phase 1 activities block.

Implemented here: `CI-01` … `CI-03` and `CI-05` (`CI-04` is an agent-run check with no engine id).

The pack verifies that a repository's CI is *the same command surface* an agent runs locally, not a
second, secret one. Workflow files are read through `audit.scan`; the local verbs they are compared
against come from `audit.rules.checks._common`.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **CI-01** — a workflow file exists (`audit.stack.CI_PROVIDERS` globs) **and** at least one of them
  declares a pull-request trigger (GitHub `pull_request`/`pull_request_target`, GitLab
  `merge_request`, Azure `pr:`, Jenkins `changeRequest`). Workflows present but no such trigger ⇒
  `PARTIAL`. No workflow file at all ⇒ `FAIL` — a PR-triggered pipeline is a Phase-1 deliverable.
* **CI-02** — the set of framework verbs (`audit.stack.VERBS`) the workflows invoke, against the
  verbs `CMD-01` resolves locally. A CI command whose verb has no local definition is a parity
  break ⇒ `FAIL`. The read-only local verbs the CI never exercises are reported in `detail` but do
  not fail the check, because CI may legitimately delegate to the composed `check` gate. A step that
  runs a repository shell script (`run: scripts/ci/test.sh`, `bash ./build.sh`) is read one script
  deep, so a wrapper's verbs count. With **no resolvable local verb**, no workflow file, or **no CI
  command that maps to a verb** there is nothing to compare ⇒ `UNKNOWN`, never a vacuous `PASS`.
* **CI-03** — every CI command that invokes a runner target (`npm run <x>`, `make <x>`, …) with no
  local runner entry is listed as a finding, so an agent can see which CI steps it cannot reproduce.
  Framework-verb invocations are `CI-02`'s subject and are not repeated here; package-manager
  plumbing (`npm ci`, `npm publish`) and shell automation (`gh`, `echo`) are not project tools and
  are ignored. No findings ⇒ `PASS`.
* **CI-05** — the workflow files are linted, per CI provider, by a tool that knows that provider:
  actionlint, zizmor or `check-jsonschema --builtin-schema vendor.github-workflows` for GitHub;
  `check-jsonschema` with the provider's built-in schema (or the matching pre-commit hook id) for
  GitLab, Azure, CircleCI and Buildkite; `glab ci lint` and `circleci config validate` count too.
  A linter named in a local surface (a runner manifest, a build file, a hook config, a script) ⇒
  local; named only in a workflow file (a `run:` step or a `uses:` action) ⇒ CI only. Every
  lintable provider linted locally ⇒ `PASS`; at least one linted only in CI, or one linted and
  another not ⇒ `PARTIAL`; workflows exist and nothing lints them ⇒ `FAIL`. No workflow file
  (`CI-01`'s subject), or only providers with no known offline linter (Jenkins) ⇒ `UNKNOWN`.

Both CI-02 and CI-03 split a step at shell operators outside quotes, and treat the arguments of
`echo`/`printf` and the body of a heredoc (a job summary written with `cat <<EOF`) as text, not commands.

Deliberate limits, recorded rather than hidden. **YAML is not parsed.** This module is a minimal,
documented text scan: it recognises `run:` / `script:` / `command:` scalar and block-scalar steps,
splits them on shell operators, and matches triggers by pattern. Anchors, expressions, `uses:`
steps, matrix expansion and full YAML semantics are out of scope, so a command hidden inside an
expression is not seen. **Verb mapping is textual**, reusing the runner-indirection idea from
`CMD-01`; an ecosystem outside that set is not mapped. Neither limit produces a `PASS` by guessing:
an unmapped command is simply not counted as evidence. **CI-05 matches tool names in text**: a
local file that names `actionlint` in a comment counts, and a linter started through an indirection
the scan cannot see (a script it does not read) is missed. Documentation files, lockfiles and
dependency-update configs (Dependabot, Renovate) never count: they name a tool without running it.
"""

from __future__ import annotations

from audit.rules.checks.ci import ci_01, ci_02, ci_03, ci_05
from audit.rules.checks.ci._shared import (
    _STEP_KEY_RE as _STEP_KEY_RE,
    _BLOCK_SCALAR_VALUES as _BLOCK_SCALAR_VALUES,
    _ASSIGNMENT_RE as _ASSIGNMENT_RE,
    _TEXT_COMMANDS as _TEXT_COMMANDS,
    _HEREDOC_RE as _HEREDOC_RE,
    _DIRECT_VERB_PATTERNS as _DIRECT_VERB_PATTERNS,
    _outcome as _outcome,
    _unknown as _unknown,
    _finding as _finding,
    _workflows as _workflows,
    _split_unquoted as _split_unquoted,
    _first_word as _first_word,
    _split_commands as _split_commands,
    _body_commands as _body_commands,
    _iter_run_commands as _iter_run_commands,
    _command_verb as _command_verb,
    _all_run_commands as _all_run_commands,
)
from audit.rules.checks.ci.ci_01 import (
    _PR_TRIGGER_PATTERNS as _PR_TRIGGER_PATTERNS,
    _has_pr_trigger as _has_pr_trigger,
    check_ci01 as check_ci01,
)
from audit.rules.checks.ci.ci_02 import (
    READ_ONLY_VERBS as READ_ONLY_VERBS,
    _SHELLS as _SHELLS,
    _script_path as _script_path,
    _script_commands as _script_commands,
    check_ci02 as check_ci02,
)
from audit.rules.checks.ci.ci_03 import _PM_BUILTINS as _PM_BUILTINS, check_ci03 as check_ci03
from audit.rules.checks.ci.ci_05 import (
    _WORKFLOW_LINTERS as _WORKFLOW_LINTERS,
    _LOCAL_SURFACE_KINDS as _LOCAL_SURFACE_KINDS,
    _NOT_A_SURFACE as _NOT_A_SURFACE,
    _local_linter_hits as _local_linter_hits,
    _ci_linter_hits as _ci_linter_hits,
    check_ci05 as check_ci05,
)
from audit.rules.spec import CheckSpec

#: The CI checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    ci_01.SPEC,
    ci_02.SPEC,
    ci_03.SPEC,
    ci_05.SPEC,
)

IMPLEMENTATIONS = {
    "CI-01": check_ci01,
    "CI-02": check_ci02,
    "CI-03": check_ci03,
    "CI-05": check_ci05,
}
