# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC` pack — execution determinism.

Anchor: `docs/framework/phased-approach.md` § Activities.

Implemented here: `EXEC-01` … `EXEC-08`.

What each check reads and what makes it ``UNKNOWN`` rather than ``FAIL``:

* **EXEC-01** — a toolchain pin appropriate to each **detected** ecosystem (``.nvmrc``, ``engines``,
  ``.python-version``/``requires-python``, ``gradlew``/``mvnw``, ``global.json``,
  ``rust-toolchain.toml``, the ``go`` directive, ``.php-version``/``composer.json``'s ``config.platform.php`` or
  ``require.php``). Pin files and manifests count at any depth, so a nested
  ``go.mod``'s ``go`` directive, a nested ``requires-python`` or a nested ``engines.node`` pins the ecosystem. A
  pinned ecosystem with a module manifest that no pin reaches (:func:`_unpinned_modules`: not its own manifest, nor
  a pin file or a node/python pinning manifest in its folder or a parent) ⇒ ``PARTIAL``. No recognised ecosystem ⇒
  ``UNKNOWN``.
* **EXEC-02** — the ecosystem's lockfile is **tracked** (``audit.ignore.tracked_files``) and its
  declared dependencies agree with the manifest. ``tracked_files`` returning ``None`` (not a git
  repository, git absent) makes the tracked half ``UNKNOWN`` — never a ``PASS``. Agreement is a
  best-effort stdlib parse; when a manifest or lockfile cannot be parsed reliably the tracked fact
  is reported and consistency is left ``PARTIAL``, never ``PASS`` by inference. A lockfile is found at
  any depth and is tracked or not by the path it was found at (``app/package-lock.json``, not its
  basename). Every lockfile is judged, so a second app's lockfile is read too: each one that git does not
  track is a ``FAIL``, and each tracked one is compared with the manifest in its own folder
  (``app/package.json``); one with no manifest beside it is tracked but its consistency is unverified, a
  ``PARTIAL`` finding of its own. A tracked lockfile the walk left out, because an ignore rule covers it, is
  found too. An ecosystem that was
  recognised only from its source files (``Stack.source_only``) has no manifest and declares no
  dependencies, so it is not expected to have a lockfile. A recognised ecosystem with no lockfile convention in
  :data:`_ECOSYSTEM_MANAGERS` is named in the ``UNKNOWN`` summary. A ``FAIL`` summary names each ecosystem with
  no lockfile, each untracked lockfile and each lockfile out of step with its manifest.
* **EXEC-03** — a devcontainer / compose file / Dockerfile / setup target-script, or a documented
  non-interactive install command in a fenced block or an inline code span of README/``AGENTS.md``. The setup
  files count at any depth, and so does a Dockerfile with a variant in its name
  (``src/main/docker/Dockerfile.jvm``). Present but
  undocumented ⇒ ``PARTIAL``. No recognised ecosystem ⇒ ``UNKNOWN``: with no build manifest there is
  no way to say what provisioning is expected.
* **EXEC-04** — a set difference: env keys referenced by source against keys declared in the
  committed example files (``.env.example`` and its kin, at any depth). An example file documents the files in its
  own folder and below it, so ``api/.env.example`` covers the keys ``api/`` reads and a root one covers every file;
  a key counts as declared when every file that reads it is covered by an example file that names it. A documented allow-list of conventional CI/test/host variables lives in
  :data:`_ENV_ALLOWLIST` and :data:`_ENV_ALLOW_PREFIXES`; it is deterministic and kept in code.
* **EXEC-05** — generated files are either untracked or carry a generated-file header. A file is generated when
  the scan classifies it ``GENERATED`` (a generated hint or suffix, or any tracked file under ``dist/``), or when
  it is a tracked text file under ``build/`` that the target's own ignore rules also match
  (:func:`tracked_and_ignored`, the list ``SEC-01`` and ``SEC-03`` read). Any other file under ``build/`` keeps the
  kind it would have elsewhere, so a hand-written build script there passes (issue #260). Tracked state
  unavailable ⇒ ``UNKNOWN``.
* **EXEC-06** — every shell command in a fenced README/``AGENTS.md`` block resolves to a
  known tool, a declared verb, an npm script, a Makefile target, a package binary, or a real path.
  Shell builtins and obvious placeholders are skipped, never failed. Line continuations are joined.
* **EXEC-07** — at most one authoritative config per concern (lint, format, test, types, security).
  Only repository-root configs are counted, so a monorepo's per-component configs are not mistaken
  for competition. Types are counted per language (TypeScript, Python), so ``tsconfig.json`` beside ``mypy.ini``
  is two languages, not two configs. A pyright or basedpyright config beside one mypy config, when the
  ``typecheck`` verb runs mypy and not pyright, gives a language server the gate's paths: it is a mirror, not a
  competitor, and is named in the summary.
* **EXEC-08** — a tool version written as a literal into a command (``uvx ruff@0.5.0``, ``npx x@1.2.3``,
  ``pip install x==1.2``, ``go install pkg@v1.2``, ``cargo install x --version 1.2``, or the ``version`` input of a
  tool-installer action) is invisible to Dependabot and Renovate. The surfaces read are the command runners
  (``Makefile``, ``*.mk``, ``justfile``, ``Taskfile``, ``package.json``), the CI workflows and the hook files, line by
  line; a version that is a variable (``$(call pin,ruff)``) is not a literal. Each literal is looked up in the
  manifests at any depth (:func:`_manifest_holds`). Any literal no manifest holds ⇒ ``FAIL``; every literal also
  held by a manifest ⇒ ``PARTIAL`` (the inline copy drifts when the bot updates the manifest); none ⇒ ``PASS``. A
  file that a Renovate ``customManagers``/``regexManagers`` pattern matches is visible and is not read. No surface
  file at all ⇒ ``UNKNOWN``. Runtime versions (``node-version``) are ``EXEC-01``'s; ``uses:`` pins are visible to
  Dependabot already; a versionless ``uvx ruff`` is not a visibility defect.

.NET is locked by NuGet's ``packages.lock.json``, which a project writes only when it sets
``RestorePackagesWithLockFile``; a .NET project with none ⇒ ``FAIL``, as for every other ecosystem. A root
``packages.lock.json`` is compared, casefolded, with the ``PackageReference`` names of the project files in the root
folder; a project that imports another MSBuild file, or a root ``Directory.*`` file that adds package references,
leaves the consistency unverified.

Known limitation, recorded rather than hidden: manifest↔lockfile consistency parsing for ecosystems
beyond node/python/rust/go/dotnet is not attempted, so those ecosystems report the tracked fact and
``PARTIAL`` consistency. This is deliberately conservative — a false ``PASS`` on a stale lockfile is
worse than an honest ``PARTIAL``.
"""

from __future__ import annotations

from audit.rules.checks.execution import exec_01, exec_02, exec_03, exec_04, exec_05, exec_06, exec_07, exec_08
from audit.rules.checks.execution._shared import _outcome as _outcome, _unknown as _unknown, _tokenise as _tokenise
from audit.rules.checks.execution.exec_01 import (
    _PIN_FILES as _PIN_FILES,
    _PINNABLE as _PINNABLE,
    _TOOL_VERSIONS as _TOOL_VERSIONS,
    _composer_php_pin as _composer_php_pin,
    _manifests as _manifests,
    _pin_evidence as _pin_evidence,
    _MODULE_MANIFESTS as _MODULE_MANIFESTS,
    _SELF_CONTAINED_MODULES as _SELF_CONTAINED_MODULES,
    _MODULES_NAMED as _MODULES_NAMED,
    _dir_of as _dir_of,
    _manifest_pins as _manifest_pins,
    _unpinned_modules as _unpinned_modules,
    check_exec01 as check_exec01,
)
from audit.rules.checks.execution.exec_02 import (
    _ECOSYSTEM_MANAGERS as _ECOSYSTEM_MANAGERS,
    _CASE_INSENSITIVE as _CASE_INSENSITIVE,
    _NO_LOCK_REASON as _NO_LOCK_REASON,
    _NO_LOCK_REMEDIATION as _NO_LOCK_REMEDIATION,
    _lockfiles_for as _lockfiles_for,
    _in_folder as _in_folder,
    _dependency_name as _dependency_name,
    _node_manifest_deps as _node_manifest_deps,
    _toml_package_names as _toml_package_names,
    _node_lock_deps as _node_lock_deps,
    _python_manifest_deps as _python_manifest_deps,
    _python_lock_deps as _python_lock_deps,
    _cargo_manifest_deps as _cargo_manifest_deps,
    _go_manifest_deps as _go_manifest_deps,
    _go_lock_deps as _go_lock_deps,
    _DOTNET_IMPORTED as _DOTNET_IMPORTED,
    _DOTNET_PROJECT_SUFFIXES as _DOTNET_PROJECT_SUFFIXES,
    _PACKAGE_REFERENCE as _PACKAGE_REFERENCE,
    _dotnet_manifest_deps as _dotnet_manifest_deps,
    _dotnet_lock_deps as _dotnet_lock_deps,
    _manifest_deps as _manifest_deps,
    _lock_deps as _lock_deps,
    _lockfile_paths as _lockfile_paths,
    _lock_consistency as _lock_consistency,
    _COMPARED as _COMPARED,
    _unverified_finding as _unverified_finding,
    check_exec02 as check_exec02,
)
from audit.rules.checks.execution.exec_03 import (
    _SETUP_FILES as _SETUP_FILES,
    _DOCKERFILE_PATTERNS as _DOCKERFILE_PATTERNS,
    _DEVCONTAINER_PATTERNS as _DEVCONTAINER_PATTERNS,
    _DOC_FILES as _DOC_FILES,
    _SETUP_TARGETS as _SETUP_TARGETS,
    _setup_signals as _setup_signals,
    _INSTALL_SUBCOMMANDS as _INSTALL_SUBCOMMANDS,
    _documented_setup as _documented_setup,
    _is_documented as _is_documented,
    check_exec03 as check_exec03,
)
from audit.rules.checks.execution.exec_04 import (
    _SHELL_ENV_PATTERN as _SHELL_ENV_PATTERN,
    _SHELL_OPTIONAL_OPERATORS as _SHELL_OPTIONAL_OPERATORS,
    _SHELL_ASSIGN_PATTERN as _SHELL_ASSIGN_PATTERN,
    _CODE_ENV_PATTERNS as _CODE_ENV_PATTERNS,
    _SHELL_ENV_SUFFIXES as _SHELL_ENV_SUFFIXES,
    _SHELL_ENV_BASENAMES as _SHELL_ENV_BASENAMES,
    _ENV_ALLOWLIST as _ENV_ALLOWLIST,
    _ENV_ALLOW_PREFIXES as _ENV_ALLOW_PREFIXES,
    _ENV_EXAMPLE_FILES as _ENV_EXAMPLE_FILES,
    _is_shell_env_file as _is_shell_env_file,
    _referenced_env_keys as _referenced_env_keys,
    _declared_env_keys as _declared_env_keys,
    _reaches as _reaches,
    _declared_for as _declared_for,
    _env_allowed as _env_allowed,
    check_exec04 as check_exec04,
)
from audit.rules.checks.execution.exec_05 import (
    _GENERATED_HEADER_MARKERS as _GENERATED_HEADER_MARKERS,
    _has_generated_header as _has_generated_header,
    _ignored_build_files as _ignored_build_files,
    check_exec05 as check_exec05,
)
from audit.rules.checks.execution.exec_06 import (
    _KNOWN_TOOLS as _KNOWN_TOOLS,
    _SHELL_KEYWORDS as _SHELL_KEYWORDS,
    _STRIPPABLE_PREFIXES as _STRIPPABLE_PREFIXES,
    _package_bins as _package_bins,
    _command_parts as _command_parts,
    _resolves as _resolves,
    _logical_commands as _logical_commands,
    check_exec06 as check_exec06,
)
from audit.rules.checks.execution.exec_07 import (
    _CONCERN_GLOBS as _CONCERN_GLOBS,
    _PYPROJECT_SECTIONS as _PYPROJECT_SECTIONS,
    _concern_configs as _concern_configs,
    _MYPY_RE as _MYPY_RE,
    _PYRIGHT_RE as _PYRIGHT_RE,
    _PYRIGHT_FILES as _PYRIGHT_FILES,
    _MYPY_FILES as _MYPY_FILES,
    _typecheck_runs as _typecheck_runs,
    _language_server_mirror as _language_server_mirror,
    check_exec07 as check_exec07,
)
from audit.rules.checks.execution.exec_08 import (
    _INLINE_SURFACE_NAMES as _INLINE_SURFACE_NAMES,
    _LITERAL_VERSION as _LITERAL_VERSION,
    _SEGMENT_SPLIT as _SEGMENT_SPLIT,
    _INLINE_LAUNCHERS as _INLINE_LAUNCHERS,
    _NODE_TOKEN as _NODE_TOKEN,
    _PYTHON_TOKEN as _PYTHON_TOKEN,
    _GO_TOKEN as _GO_TOKEN,
    _RUST_TOKEN as _RUST_TOKEN,
    _TOKEN_PATTERNS as _TOKEN_PATTERNS,
    _INSTALLER_ACTIONS as _INSTALLER_ACTIONS,
    _USES_RE as _USES_RE,
    _RENOVATE_FILES as _RENOVATE_FILES,
    _InlineVersion as _InlineVersion,
    _inline_surfaces as _inline_surfaces,
    _token as _token,
    _versions_in_segment as _versions_in_segment,
    _installer_versions as _installer_versions,
    _inline_versions as _inline_versions,
    _renovate_patterns as _renovate_patterns,
    _normalise as _normalise,
    _bare as _bare,
    _node_manifest_holds as _node_manifest_holds,
    _python_manifest_holds as _python_manifest_holds,
    _go_manifest_holds as _go_manifest_holds,
    _rust_manifest_holds as _rust_manifest_holds,
    _manifest_holds as _manifest_holds,
    check_exec08 as check_exec08,
)
from audit.rules.spec import CheckSpec

#: The EXEC checks, in catalogue order. The registry assembles every family's SPECS into the catalogue.
SPECS: tuple[CheckSpec, ...] = (
    exec_01.SPEC,
    exec_02.SPEC,
    exec_03.SPEC,
    exec_04.SPEC,
    exec_05.SPEC,
    exec_06.SPEC,
    exec_07.SPEC,
    exec_08.SPEC,
)

IMPLEMENTATIONS = {
    "EXEC-01": check_exec01,
    "EXEC-02": check_exec02,
    "EXEC-03": check_exec03,
    "EXEC-04": check_exec04,
    "EXEC-05": check_exec05,
    "EXEC-06": check_exec06,
    "EXEC-07": check_exec07,
    "EXEC-08": check_exec08,
}
