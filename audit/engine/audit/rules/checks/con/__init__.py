# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`CON` pack — constraints.

Anchor: `docs/framework/phased-approach.md` § Key Deliverables ("Allow/deny lists").

Implemented here: `CON-01`, `CON-02`, `CON-03`, and the `CON-04` emitter.

The framework requires initial allow/deny lists as a Phase-1 deliverable, and the spec names the artifact: the
prohibitions section of the instruction file (decision 0001, ``spec/decisions/0001-constraint-artifact.md``).
`CON-01` and `CON-02` read it through ``_common.prohibitions_section``; a path or a pattern is *named* when it
stands in a code span of the section. In a section opened only by its body (no prohibition word in its heading, three
prohibition lines under it), only a list item or paragraph that holds a prohibition line names anything: a conventions
section that says "never" three times also names paths that are not a deny list (issue #9). A finding cites the
heading of every part of the section.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **CON-01** — *the deny list names paths*. The section names at least one path or pattern that matches a file
  or directory of the repository ⇒ `PASS`. It names paths and none of them matches anything ⇒ `PARTIAL`. It
  names no path or pattern ⇒ `FAIL`. No instruction file or no prohibitions section ⇒ `UNKNOWN` (`AGT-01` and
  `AGT-07` report that once). A code span is a path or pattern when it has no command syntax and holds a slash,
  a glob or a dot, or is a bare word that exists; ``git push --force`` and ``main`` are not paths. A literal
  path is also looked for on disk, because the scan leaves out ``node_modules/`` and the like, which a deny
  list often names.
* **CON-02** — *test directories protected*. Reads the prohibitions section of the entry instruction file
  (``_common.prohibitions_section``; decision 0001, ``spec/decisions/0001-constraint-artifact.md``): a test
  directory is protected when the section names it, or a pattern that covers it, in a code span. Test
  directories are located from the scan (a directory segment named ``test``/``tests``/``__tests__``; ``spec``
  and ``specs`` hold feature specifications, not tests) plus the filesystem. The section names every one ⇒
  `PASS`; some ⇒ `PARTIAL`; none ⇒ `FAIL`. No instruction file or no prohibitions section ⇒ `UNKNOWN`, since
  `AGT-01` and `AGT-07` report that once and the check does not pile on, and so is a repository with no test
  directory. Constraint files, ignore rules and CI text are not read: they are not the artifact.
* **CON-03** — *`artefacts/` excluded from the index and agent reads*. Candidate roots are the
  scratch spellings (``artefacts``, ``artifacts``) and the agent/tool state directories
  (``.codebase-memory``, ``.opencode``, ``.agentic-tdd``). A root that exists is covered when an
  ignore rule matches it; a **tracked** member of any root is a `FAIL`. When the roots are covered
  but git cannot report the tracked set, the untracked half is `UNKNOWN` — never inferred — while
  the rule-coverage half still evaluates (the same degradation `SEC-01`/`DOC-03` use).
* **CON-04** — the emitter, not a scored check. It returns a `CheckOutcome` like every other check,
  but it becomes `PASS` only when the operator asked for the draft with ``--emit-baseline``; without
  the flag it is `UNKNOWN`, and it is refused outright if the resolved output would land inside the
  target (ADR-0002). The draft is deterministic: fixed sections, sorted entries.

CON-04's draft is a Markdown list to paste under the prohibitions heading of the instruction file, one entry
for each of six categories (secrets, migrations, generated code, tests, infrastructure as code, production
configuration), with the paths in code spans. It is written to the same ``--out`` directory as the report, gated
by ``--emit-baseline``, as ``do-not-do.draft.md`` (``docs/how-to/hand-findings-to-remediation.md``). It replaces
the YAML ``constraints.draft.yaml``, which nothing reads any more.
The emitter writes to a module-level target set by the CLI before the scan; nothing else reads it.

Deliberate limits, recorded rather than hidden. Ignore matching (``CON-03``) is the documented subset in
``audit.ignore`` (anchoring and ``**`` approximated). The prohibitions section is prose, so ``CON-02`` is a
heuristic: a path written without backticks is not seen, and a pattern is read like an ignore entry (a
leading ``/`` anchors it, a leading ``**/`` is any depth, one with no inner slash names a directory of that
name at any depth, ``fnmatch`` globs). Test-directory discovery is directory-based; a suite laid out as
loose ``*_test.py`` files with no test-named directory is not seen and degrades to `UNKNOWN`, and so is a
Ruby ``spec/`` directory. The emitter writes exactly one artifact (``do-not-do.draft.md``); the other S12
remediation inputs are out of scope for this pack.
"""

from __future__ import annotations

from audit.rules.checks.con import con_01, con_02, con_03, con_04
from audit.rules.checks.con._shared import (
    _TEST_DIR_NAMES as _TEST_DIR_NAMES,
    _outcome as _outcome,
    _unknown as _unknown,
    _finding as _finding,
    _split_pattern as _split_pattern,
    _names_directory as _names_directory,
)
from audit.rules.checks.con.con_01 import (
    _GLOB_CHARS as _GLOB_CHARS,
    _NOT_A_PATH_CHARS as _NOT_A_PATH_CHARS,
    _path_like as _path_like,
    _repository_paths as _repository_paths,
    _exists_in_repository as _exists_in_repository,
    _listed as _listed,
    check_con01 as check_con01,
)
from audit.rules.checks.con.con_02 import _describe as _describe, _test_roots as _test_roots, check_con02 as check_con02
from audit.rules.checks.con.con_03 import (
    _SCRATCH_ROOTS as _SCRATCH_ROOTS,
    _STATE_ROOTS as _STATE_ROOTS,
    _CON_ROOTS as _CON_ROOTS,
    _present_roots as _present_roots,
    check_con03 as check_con03,
)
from audit.rules.checks.con.con_04 import (
    DRAFT_FILENAME as DRAFT_FILENAME,
    _EMIT_TARGET as _EMIT_TARGET,
    _EMIT_FORCE as _EMIT_FORCE,
    draft_path as draft_path,
    set_emit_target as set_emit_target,
    _DRAFT_PATTERNS as _DRAFT_PATTERNS,
    _GENERATED_DIRS as _GENERATED_DIRS,
    _IAC_DIRS as _IAC_DIRS,
    _MIGRATION_DIRS as _MIGRATION_DIRS,
    _is_secret_path as _is_secret_path,
    _is_generated_path as _is_generated_path,
    _is_migration_path as _is_migration_path,
    _is_iac_path as _is_iac_path,
    _is_production_path as _is_production_path,
    _is_test_path as _is_test_path,
    _DRAFT_MATCHERS as _DRAFT_MATCHERS,
    _DRAFT_OPENINGS as _DRAFT_OPENINGS,
    _CATEGORY_DIRS as _CATEGORY_DIRS,
    _observed_entry as _observed_entry,
    _covered_by_another as _covered_by_another,
    build_do_not_do_draft as build_do_not_do_draft,
    _write_draft as _write_draft,
    check_con04 as check_con04,
)
from audit.rules.spec import CheckSpec

#: The CON checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    con_01.SPEC,
    con_02.SPEC,
    con_03.SPEC,
    con_04.SPEC,
)

IMPLEMENTATIONS = {
    "CON-01": check_con01,
    "CON-02": check_con02,
    "CON-03": check_con03,
    "CON-04": check_con04,
}
