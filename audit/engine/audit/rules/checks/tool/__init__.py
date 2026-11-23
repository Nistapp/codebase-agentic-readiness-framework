# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`TOOL` pack — tooling.

Anchor: `docs/framework/phased-approach.md` § Key Deliverables.

Implemented here: `TOOL-01` … `TOOL-07`.

The pack verifies that the tools an agent leans on are configured **and reachable through the command
surface**, not merely installed. Verb evidence comes from `audit.rules.checks._common.resolve_verbs`;
config evidence is a small, documented set of filenames per concern. A config file with no way to
invoke the tool is `PARTIAL`, never `PASS` — a formatter an agent cannot run is not a formatter.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **TOOL-01** — a formatter config file (prettier/black/ruff/dprint/config-in-package.json or
  pyproject) **and** a resolvable `format` write verb. Only one of the two ⇒ `PARTIAL`.
* **TOOL-02** — a linter config file (eslint/ruff/flake8/pylint/golangci/rubocop/biome) **and** a
  resolvable `lint` read-only verb. Only one of the two ⇒ `PARTIAL`.
* **TOOL-03** — language-appropriate strict configuration: `tsconfig.json`/`jsconfig.json`,
  `mypy`/`pyright` strict, or `.NET` `<Nullable>enable</Nullable>`. Configured but non-strict ⇒
  `PARTIAL`. An ecosystem with no strict-config concept in this table (go, rust, jvm, ruby, php) ⇒
  `UNKNOWN`. It never invents a type checker for an ecosystem that has none.
* **TOOL-04** — a resolved verb whose command runs a known dependency-audit tool (`npm audit`,
  `pip-audit`, `osv-scanner`, `cargo audit`, `govulncheck`, `snyk`, …). The verb is the evidence;
  it is **not** run (that would be Tier C). A `security` verb that runs something else ⇒ `PARTIAL`. On the root
  `Makefile` the verb is followed the way Make runs it: simple variables are expanded (`$(OSV)`, `${OSV}`), and each
  prerequisite target and each `make <target>` or `$(MAKE) <target>` line is read in turn (cycles and
  `make -C`/`-f` calls into another Makefile are not followed). CI is read too, as `TOOL-06` reads it: a workflow
  line that runs a scanner, a runner target whose command runs one (``make security-deps``, ``npm run security``),
  a scanner action (``google/osv-scanner-action``, ``actions/dependency-review-action``, ...), or GitLab's
  Dependency-Scanning template. Dependabot and Renovate do not count (``HYG-09``). Local and CI ⇒ `PASS`; one of
  the two ⇒ `PARTIAL`; neither ⇒ `FAIL`. Whether the CI job runs on pull requests is not read.
* **TOOL-05** — a wired hook chain: `.pre-commit-config.yaml`, `lefthook.yml`, a declared
  `core.hooksPath`, or `.husky/` referenced by a `prepare`/install script. Present but unwired ⇒
  `PARTIAL`.
* **TOOL-06** — a commit-message rule in two places. Locally: a commitlint config, a `commit-msg` hook, or an
  equivalent pre-commit/lefthook stage. In CI: a workflow line that runs a commit-message linter (commitlint,
  commitizen's `cz check`, gitlint, the pre-commit or lefthook `commit-msg` stage), a pull-request title check, a
  script the local `commit-msg` stage also runs, or a runner target whose command does one of those. Both ⇒
  `PASS`; one of the two ⇒ `PARTIAL`; neither ⇒ `FAIL` (`COSMETIC`). Whether the CI job runs on pull requests is
  not read.
* **TOOL-07** — a local guard that refuses a commit on a protected branch: pre-commit's `no-commit-to-branch` hook
  (its `--branch`/`--pattern` arguments; `main` and `master` without `--branch`), or a lefthook command, a Husky hook or a
  `pre-commit`/`commit-msg` hook script that reads the current branch (`git symbolic-ref ... HEAD`,
  `git branch --show-current`, `git rev-parse --abbrev-ref HEAD`). The branches it must name are the literal ones
  the declared rules protect (:func:`audit.rules.checks._common.declared_branch_rules`); with none declared, any
  guard counts. A guard that reads the branch must also exit non-zero (``exit 1``, ``process.exit(1)``, a bare
  ``false``) in its command block or hook script; ``no-commit-to-branch`` always does. A stopping guard in a wired
  chain that names them all ⇒ `PASS`; a guard in a chain that is not wired, a guard with no non-zero exit, or one
  that misses a protected branch ⇒ `PARTIAL`; hooks but no guard ⇒ `FAIL`; no hook at all ⇒ `UNKNOWN`, which is
  `TOOL-05`'s finding. The exit is read anywhere in a hook script, not tied to the branch test; a guard in a script
  the hook calls is not read.

Deliberate limits, recorded rather than hidden. **Config detection is filename-based** against the
documented set below; a config that lives somewhere unexpected is not seen. **Verb resolution is
v1's**: only the runner manifests `_common` understands contribute verbs. When there is no
recognised ecosystem, no runner manifest, and no relevant config, the verdict is `UNKNOWN` — an
unrecognised repository is not proof of absence.
"""

from __future__ import annotations

from audit.rules.checks.tool import tool_01, tool_02, tool_03, tool_04, tool_05, tool_06, tool_07
from audit.rules.checks.tool._shared import (
    _WIRED_HOOK_FILES as _WIRED_HOOK_FILES,
    _outcome as _outcome,
    _unknown as _unknown,
    _recognised as _recognised,
    _present as _present,
    _read_matches as _read_matches,
    _finding as _finding,
    _manifest_evidence as _manifest_evidence,
    _hook_wiring as _hook_wiring,
    _husky_referenced as _husky_referenced,
)
from audit.rules.checks.tool.tool_01 import (
    _FORMATTER_CONFIG_NAMES as _FORMATTER_CONFIG_NAMES,
    _formatter_config as _formatter_config,
    check_tool01 as check_tool01,
)
from audit.rules.checks.tool.tool_02 import (
    _LINTER_CONFIG_NAMES as _LINTER_CONFIG_NAMES,
    _linter_config as _linter_config,
    check_tool02 as check_tool02,
)
from audit.rules.checks.tool.tool_03 import (
    _TYPECHECK_ECOSYSTEMS as _TYPECHECK_ECOSYSTEMS,
    _strip_jsonc_comments as _strip_jsonc_comments,
    _strip_trailing_commas as _strip_trailing_commas,
    _json_true as _json_true,
    _typecheck_signals as _typecheck_signals,
    check_tool03 as check_tool03,
)
from audit.rules.checks.tool.tool_04 import (
    _AUDIT_PATTERNS as _AUDIT_PATTERNS,
    _is_audit_command as _is_audit_command,
    _makefile_audit as _makefile_audit,
    _CI_AUDIT_ACTIONS as _CI_AUDIT_ACTIONS,
    _audit_in as _audit_in,
    _ci_audit_steps as _ci_audit_steps,
    _local_audit as _local_audit,
    check_tool04 as check_tool04,
)
from audit.rules.checks.tool.tool_05 import check_tool05 as check_tool05
from audit.rules.checks.tool.tool_06 import (
    _COMMITLINT_CONFIG_NAMES as _COMMITLINT_CONFIG_NAMES,
    _CI_COMMIT_TOOLS as _CI_COMMIT_TOOLS,
    _PATH_TOKEN_RE as _PATH_TOKEN_RE,
    _SCRIPT_SUFFIXES as _SCRIPT_SUFFIXES,
    _commit_rule as _commit_rule,
    _commit_msg_text as _commit_msg_text,
    _commit_msg_scripts as _commit_msg_scripts,
    _commit_rule_in as _commit_rule_in,
    _ci_commit_steps as _ci_commit_steps,
    check_tool06 as check_tool06,
)
from audit.rules.checks.tool.tool_07 import (
    _BRANCH_READ_RE as _BRANCH_READ_RE,
    _GUARD_HOOK_NAMES as _GUARD_HOOK_NAMES,
    _NO_COMMIT_DEFAULTS as _NO_COMMIT_DEFAULTS,
    _NONZERO_EXIT_RE as _NONZERO_EXIT_RE,
    _ARG_SEP as _ARG_SEP,
    _BRANCH_ARG_RE as _BRANCH_ARG_RE,
    _PATTERN_ARG_RE as _PATTERN_ARG_RE,
    _Guard as _Guard,
    _block as _block,
    _pre_commit_guards as _pre_commit_guards,
    _stage as _stage,
    _branch_read_guards as _branch_read_guards,
    _local_guards as _local_guards,
    check_tool07 as check_tool07,
)
from audit.rules.checks._common import _expand_make as _expand_make
from audit.rules.checks._common import _makefile_variables as _makefile_variables
from audit.rules.spec import CheckSpec

#: The TOOL checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    tool_01.SPEC,
    tool_02.SPEC,
    tool_03.SPEC,
    tool_04.SPEC,
    tool_05.SPEC,
    tool_06.SPEC,
    tool_07.SPEC,
)

IMPLEMENTATIONS = {
    "TOOL-01": check_tool01,
    "TOOL-02": check_tool02,
    "TOOL-03": check_tool03,
    "TOOL-04": check_tool04,
    "TOOL-05": check_tool05,
    "TOOL-06": check_tool06,
    "TOOL-07": check_tool07,
}
