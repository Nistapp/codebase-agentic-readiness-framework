# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`CMD` pack — command surface.

Anchor: `docs/framework/phased-approach.md` § Activities.

Implemented here: `CMD-01` … `CMD-04`.

The framework's standardized command surface is seven verbs on one runner. Each check reads the
runner manifests once through `audit.rules.checks._common`; this pack never reparses a manifest.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **CMD-01** — every framework verb (`audit.stack.VERBS`) resolves, and resolves on **one** runner.
  `_common.resolve_all_verbs` is read in full, so a verb declared on two runners is visible as a
  stray second definition. Missing verbs ⇒ `FAIL`; verbs split across (or duplicated on) more than
  one runner ⇒ `PARTIAL` — the stray definition is `CMD-03`'s territory. With **no runner manifest
  at all** the verdict is `UNKNOWN`: an unrecognised ecosystem is not proof of absence. A verb is
  read under the spelling its runner accepts (`audit.stack.FORMAT_CHECK_ALIASES`; the spec's table).
  A `package.json`, a `Makefile`, a Taskfile, a `pyproject.toml`, a Gradle or a Maven build is a runner only at
  the root, where its runner reads it; a nested one is neither read nor cited.
  A `Makefile` that GNU Make refuses to parse is not a runner and is a finding of its own,
  `CMD-01:Makefile`: `FAIL` when no other runner is left, otherwise at least `PARTIAL`.
* **CMD-02** — the `check` verb's body invokes a format-check, a typecheck and a test command.
  Indirection through another verb (`npm run format:check`) and documented tool equivalents
  (``prettier --check``, ``tsc --noEmit``, ``pytest``, …) both count. In a `Makefile` the prerequisites
  of `check` are its body, and a prerequisite that is not a verb is followed into its own recipe, once. In a
  `package.json` a script that is not a verb is followed into its command the same way, so
  `npm run test:coverage` composes the test concern through `jest --coverage`.
  A Gradle `check` is read from the build file: a JVM plugin wires the compile (the typecheck) and
  `test`, Spotless or ktlint wires the format check, and `check.dependsOn` or a `check { dependsOn ... }`
  block adds the verbs and known tasks it names. A plugin, script, subproject or task the engine does not
  know may add more, so with one of those present a check that is still missing a concern is `UNKNOWN`.
  Some concerns present ⇒ `PARTIAL`; none ⇒ `FAIL`; no runner ⇒ `UNKNOWN` (so is a `Makefile` that
  does not parse, which `CMD-01` already reported, and so is a `check` that is a Maven lifecycle phase,
  whose plugin bindings are set by the build and not read here).
* **CMD-03** — a second runner may define `check` only as a delegation to the first; a second runner
  that composes the gate itself is a finding. Detection is textual and deterministic: a delegating
  `check` invokes ``check`` through another runner. No runner ⇒ `UNKNOWN`.
* **CMD-04** — no read-only verb (`VERBS` minus `audit.probes.MUTATING_VERBS`) invokes a write verb.
  Both runner indirection (``npm run format``) and direct writer invocations (``prettier --write``,
  ``tsc`` without ``--noEmit``, ``rm -rf``) are detected, so a formatter's explicit-run write form is
  caught while its check form (``format:check``) is not. No runner ⇒ `UNKNOWN`.

Two deliberate limits, recorded rather than hidden. **Command parsing is textual**: shell operators
are split on, not interpreted, so a verb hidden inside a quoted string is not seen. **Runner
resolution is v1's**: only the manifests `_common` understands can contribute verbs, so an ecosystem
outside that set reports `UNKNOWN`, never a false `PASS`.
"""

from __future__ import annotations

from audit.rules.checks.cmd import cmd_01, cmd_02, cmd_03, cmd_04
from audit.rules.checks.cmd._shared import (
    _SEGMENT_SPLIT as _SEGMENT_SPLIT,
    _NPM_RE as _NPM_RE,
    _YARN_RE as _YARN_RE,
    _TASK_RE as _TASK_RE,
    _RUNNER_INVOCATIONS as _RUNNER_INVOCATIONS,
    _outcome as _outcome,
    _unknown as _unknown,
    _no_runner as _no_runner,
    _segments as _segments,
    _runner_target as _runner_target,
    _ordered_runners as _ordered_runners,
)
from audit.rules.checks.cmd.cmd_01 import _makefile_parse_finding as _makefile_parse_finding, check_cmd01 as check_cmd01
from audit.rules.checks.cmd.cmd_02 import (
    CONCERNS as CONCERNS,
    _CONCERN_OF_VERB as _CONCERN_OF_VERB,
    _LIFECYCLE_RUNNERS as _LIFECYCLE_RUNNERS,
    _FOLLOWED_RUNNERS as _FOLLOWED_RUNNERS,
    _DIRECT_CONCERN_PATTERNS as _DIRECT_CONCERN_PATTERNS,
    _composition_concerns as _composition_concerns,
    _GRADLE_PLUGIN_CONCERNS as _GRADLE_PLUGIN_CONCERNS,
    _GRADLE_INERT_PLUGINS as _GRADLE_INERT_PLUGINS,
    _GRADLE_TASK_CONCERNS as _GRADLE_TASK_CONCERNS,
    _GRADLE_COMMENT_RE as _GRADLE_COMMENT_RE,
    _GRADLE_CHECK_DEPENDS_RE as _GRADLE_CHECK_DEPENDS_RE,
    _GRADLE_CHECK_BLOCK_RE as _GRADLE_CHECK_BLOCK_RE,
    _GRADLE_DEPENDS_RE as _GRADLE_DEPENDS_RE,
    _GRADLE_OPAQUE_RE as _GRADLE_OPAQUE_RE,
    _GRADLE_CHECK_MENTION_RE as _GRADLE_CHECK_MENTION_RE,
    _GRADLE_QUOTED_RE as _GRADLE_QUOTED_RE,
    _GRADLE_IDENT_RE as _GRADLE_IDENT_RE,
    _GRADLE_ACCESSORS as _GRADLE_ACCESSORS,
    _GRADLE_SPOTLESS_OFF_RE as _GRADLE_SPOTLESS_OFF_RE,
    _GRADLE_ALIAS_RE as _GRADLE_ALIAS_RE,
    _GRADLE_APPLY_FROM_RE as _GRADLE_APPLY_FROM_RE,
    _GRADLE_INCLUDE_RE as _GRADLE_INCLUDE_RE,
    _GRADLE_SETTINGS as _GRADLE_SETTINGS,
    _block_at as _block_at,
    _depends_names as _depends_names,
    _gradle_check as _gradle_check,
    check_cmd02 as check_cmd02,
)
from audit.rules.checks.cmd.cmd_03 import (
    _DELEGATION_PATTERNS as _DELEGATION_PATTERNS,
    _delegates_to as _delegates_to,
    _invoked_runner as _invoked_runner,
    check_cmd03 as check_cmd03,
)
from audit.rules.checks.cmd.cmd_04 import (
    READ_ONLY_VERBS as READ_ONLY_VERBS,
    _WRITER_PATTERNS as _WRITER_PATTERNS,
    _write_invocations as _write_invocations,
    check_cmd04 as check_cmd04,
)
from audit.rules.spec import CheckSpec

#: The CMD checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    cmd_01.SPEC,
    cmd_02.SPEC,
    cmd_03.SPEC,
    cmd_04.SPEC,
)

IMPLEMENTATIONS = {
    "CMD-01": check_cmd01,
    "CMD-02": check_cmd02,
    "CMD-03": check_cmd03,
    "CMD-04": check_cmd04,
}
