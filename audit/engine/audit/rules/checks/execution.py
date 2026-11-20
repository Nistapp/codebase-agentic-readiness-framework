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

import fnmatch
import json
import re
import shlex
from collections.abc import Collection
from dataclasses import dataclass

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.checks._common import (
    extract_documented_commands,
    extract_fenced_commands,
    follow_makefile,
    resolve_all_verbs,
    resolve_verbs,
    runner_kind,
    README,
    entry_documents,
    tracked_and_ignored,
    tracked_in_scope,
)
from audit.scan import Inventory, Kind, in_signed_generated_dir
from audit.stack import PACKAGE_MANAGERS, extract_npm_scripts, parse_makefile_targets
from audit.rules.payloads import EnvKeys, Payload


def _outcome(
    spec, verdict: Verdict, summary: str = "", findings: list[Finding] | None = None, data: Payload | None = None
) -> CheckOutcome:
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=summary,
        data=data,
        findings=findings or [],
    )


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


# ===========================================================================
# EXEC-01 — toolchain pinned / wrapper committed
# ===========================================================================

_PIN_FILES: dict[str, tuple[str, ...]] = {
    "node": (".nvmrc", ".node-version"),
    "python": (".python-version",),
    "jvm": ("gradlew", "mvnw"),
    "dotnet": ("global.json",),
    "rust": ("rust-toolchain.toml", "rust-toolchain"),
    "ruby": (".ruby-version",),
    "php": (".php-version",),
}
_PINNABLE = frozenset(_PIN_FILES) | {"go"}

#: A shared ``.tool-versions`` line counts for the ecosystem whose asdf or mise plugin name starts it. The JDK pins
#: jvm (``java``); .NET's asdf plugin is ``dotnet-core`` and mise's is ``dotnet``; Go's asdf plugin is ``golang`` and
#: mise's core plugin is ``go``.
_TOOL_VERSIONS = {
    "node": re.compile(r"(?mi)^\s*(?:nodejs|node)\s+\S+"),
    "python": re.compile(r"(?mi)^\s*python\s+\S+"),
    "rust": re.compile(r"(?mi)^\s*rust\s+\S+"),
    "go": re.compile(r"(?mi)^\s*(?:golang|go)\s+\S+"),
    "php": re.compile(r"(?mi)^\s*php\s+\S+"),
    "ruby": re.compile(r"(?mi)^\s*ruby\s+\S+"),
    "dotnet": re.compile(r"(?mi)^\s*(?:dotnet-core|dotnet)\s+\S+"),
    "jvm": re.compile(r"(?mi)^\s*java\s+\S+"),
}


def _composer_php_pin(text: str) -> str | None:
    """The ``composer.json`` key that pins PHP: ``config.platform.php`` (Composer resolves as if that PHP ran), then
    ``require.php`` (Composer refuses to install outside the range, as ``requires-python`` does)."""
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    config = data.get("config")
    platform = config.get("platform") if isinstance(config, dict) else None
    if isinstance(platform, dict) and isinstance(platform.get("php"), str) and platform["php"].strip():
        return "config.platform.php"
    require = data.get("require")
    if isinstance(require, dict) and isinstance(require.get("php"), str) and require["php"].strip():
        return "require.php"
    return None


def _manifests(inv: Inventory, name: str) -> list[str]:
    """Every file called ``name``, shallowest first: a nested module (``tools/osv/go.mod``) pins its toolchain the
    same way a root one does, as the pin files above count at any depth. The first that pins is the evidence."""
    return sorted(
        (f.rel for f in inv.files if f.rel == name or f.rel.endswith("/" + name)), key=lambda r: (r.count("/"), r)
    )


def _pin_evidence(inv: Inventory, ecosystem: str) -> list[str]:
    evidence = [name for name in _PIN_FILES.get(ecosystem, ()) if inv.has(name)]

    if inv.has(".tool-versions"):
        pattern = _TOOL_VERSIONS.get(ecosystem)
        if pattern and pattern.search(inv.read(".tool-versions") or ""):
            evidence.append(".tool-versions")

    if ecosystem == "node":
        for rel in _manifests(inv, "package.json"):
            try:
                engines = json.loads(inv.read(rel) or "{}").get("engines")
            except (json.JSONDecodeError, AttributeError):
                engines = None
            if isinstance(engines, dict) and engines.get("node"):
                evidence.append(f"{rel} (engines.node)")
                break

    if ecosystem == "python":
        for rel in _manifests(inv, "pyproject.toml"):
            if re.search(r"(?m)^\s*requires-python\s*=", inv.read(rel) or ""):
                evidence.append(f"{rel} (requires-python)")
                break

    if ecosystem == "go":
        for rel in _manifests(inv, "go.mod"):
            if re.search(r"(?m)^\s*go\s+\d", inv.read(rel) or ""):
                evidence.append(f"{rel} (go directive)")
                break

    if ecosystem == "php":
        for rel in _manifests(inv, "composer.json"):
            key = _composer_php_pin(inv.read(rel) or "")
            if key:
                evidence.append(f"{rel} ({key})")
                break

    return sorted(dict.fromkeys(evidence))


#: The manifest that makes a module of the ecosystem, and what in it pins the toolchain.
_MODULE_MANIFESTS = {"node": "package.json", "python": "pyproject.toml", "go": "go.mod", "php": "composer.json"}

#: Ecosystems whose every manifest is its own toolchain unit: a parent manifest does not reach a nested one.
_SELF_CONTAINED_MODULES = frozenset({"go", "php"})

#: At most this many unpinned modules are named in a summary; the finding's evidence lists them all.
_MODULES_NAMED = 5


def _dir_of(rel: str) -> str:
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def _manifest_pins(inv: Inventory, ecosystem: str, rel: str) -> bool:
    text = inv.read(rel) or ""
    if ecosystem == "node":
        try:
            engines = json.loads(text or "{}").get("engines")
        except (json.JSONDecodeError, AttributeError):
            return False
        return isinstance(engines, dict) and bool(engines.get("node"))
    if ecosystem == "python":
        return re.search(r"(?m)^\s*requires-python\s*=", text) is not None
    if ecosystem == "php":
        return _composer_php_pin(text) is not None
    return re.search(r"(?m)^\s*go\s+\d", text) is not None


def _unpinned_modules(inv: Inventory, ecosystem: str) -> list[str]:
    """The module manifests of ``ecosystem`` that no pin reaches. A pin reaches a module when the module's own
    manifest pins, or when its folder or a parent folder holds a pin file (``.nvmrc``, ``.python-version``, a
    ``.tool-versions`` line) or, for node and python, a pinning manifest (a workspace root's ``engines.node`` or
    ``requires-python``). A Go module is its own toolchain unit, so a parent ``go.mod`` does not reach it; nor does a
    parent ``composer.json`` reach a nested Composer project, which Composer installs on its own."""
    name = _MODULE_MANIFESTS.get(ecosystem)
    if name is None:
        return []
    manifests = _manifests(inv, name)
    pin_dirs: set[str] = set()
    pin_names = set(_PIN_FILES.get(ecosystem, ()))
    pattern = _TOOL_VERSIONS.get(ecosystem)
    for entry in inv.files:
        base = entry.rel.rsplit("/", 1)[-1]
        if base in pin_names or (
            base == ".tool-versions" and pattern is not None and pattern.search(inv.read(entry.rel) or "")
        ):
            pin_dirs.add(_dir_of(entry.rel))
    pinning = {rel for rel in manifests if _manifest_pins(inv, ecosystem, rel)}
    if ecosystem not in _SELF_CONTAINED_MODULES:
        pin_dirs |= {_dir_of(rel) for rel in pinning}

    def reached(folder: str) -> bool:
        return any(pin == "" or folder == pin or folder.startswith(pin + "/") for pin in pin_dirs)

    return [rel for rel in manifests if rel not in pinning and not reached(_dir_of(rel))]


def check_exec01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    ecosystems = sorted(stack.ecosystems & _PINNABLE)
    if not ecosystems:
        return _unknown(spec, "no recognised ecosystem, so no toolchain pin can be chosen")

    findings: list[Finding] = []
    partial: list[Finding] = []
    pinned: list[str] = []
    unpinned: list[str] = []
    gaps: list[str] = []
    for ecosystem in ecosystems:
        evidence = _pin_evidence(inventory, ecosystem)
        if evidence:
            pinned.append(f"{ecosystem} ({', '.join(evidence)})")
            modules = _unpinned_modules(inventory, ecosystem)
            if modules:
                named = ", ".join(modules[:_MODULES_NAMED])
                more = f" and {len(modules) - _MODULES_NAMED} more" if len(modules) > _MODULES_NAMED else ""
                gaps.append(f"{ecosystem} ({named}{more})")
                partial.append(
                    Finding(
                        check=spec.id,
                        severity=spec.severity,
                        phase=spec.phase,
                        verdict=Verdict.PARTIAL,
                        statement=statement(
                            f"reproduce the {ecosystem} toolchain in every module",
                            f"{len(modules)} {ecosystem} module(s) carry no pin and sit under no pinned folder",
                        ),
                        remediation=f"Pin each {ecosystem} module: a pin in its own manifest, or a "
                        f"{', '.join(_PIN_FILES.get(ecosystem) or ('.tool-versions',))} in its folder or a "
                        "parent folder.",
                        path=ecosystem,
                        evidence=[Evidence(rel) for rel in modules],
                    )
                )
            continue
        unpinned.append(ecosystem)
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    f"reproduce the {ecosystem} toolchain",
                    f"the detected {ecosystem} project pins no toolchain version",
                ),
                remediation=f"Commit the pin appropriate to {ecosystem} — "
                f"{', '.join(_PIN_FILES.get(ecosystem) or ('.tool-versions',))} "
                f"— so the agent's runtime is the repository's, not the host's.",
                path=ecosystem,
            )
        )

    if findings:
        return _outcome(spec, Verdict.FAIL, f"unpinned: {', '.join(unpinned)}", findings + partial)
    if partial:
        summary = "pinned: " + "; ".join(pinned) + "; modules no pin reaches: " + "; ".join(gaps)
        return _outcome(spec, Verdict.PARTIAL, summary, partial)
    return _outcome(spec, Verdict.PASS, "pinned: " + "; ".join(pinned))


# ===========================================================================
# EXEC-02 — lockfile committed and consistent
# ===========================================================================

#: Ecosystem -> package managers whose files are lockfiles (manifest-as-lock entries are excluded).
_ECOSYSTEM_MANAGERS: dict[str, tuple[str, ...]] = {
    "node": ("npm", "pnpm", "yarn", "bun"),
    "python": ("poetry", "uv", "pipenv", "pdm"),
    "jvm": ("gradle",),
    "rust": ("cargo",),
    "go": ("gomod",),
    "ruby": ("bundler",),
    "php": ("composer",),
    "dotnet": ("nuget",),
}

#: Ecosystems whose package names are case-insensitive, so the manifest and the lockfile are compared casefolded.
_CASE_INSENSITIVE = frozenset({"dotnet"})

#: Why a missing lockfile matters, where the resolver does not simply take whatever versions are current.
_NO_LOCK_REASON: dict[str, str] = {
    "dotnet": "a fresh restore is free to resolve other versions of floating and transitive dependencies",
}

#: How to create the lockfile, where the package manager does not write one by default.
_NO_LOCK_REMEDIATION: dict[str, str] = {
    "dotnet": "Set RestorePackagesWithLockFile to true in each project (or once in Directory.Build.props), run "
    "dotnet restore, commit every packages.lock.json, and restore with dotnet restore --locked-mode in CI.",
}


def _lockfiles_for(ecosystem: str) -> list[str]:
    return [f for manager in _ECOSYSTEM_MANAGERS.get(ecosystem, ()) for f in PACKAGE_MANAGERS.get(manager, ())]


def _in_folder(folder: str, name: str) -> str:
    """``name`` in ``folder``, where the root folder is ``""``."""
    return f"{folder}/{name}" if folder else name


def _dependency_name(spec_text: str) -> str | None:
    match = re.match(r"^[A-Za-z0-9_.@/-]+", spec_text.strip())
    return match.group(0) if match else None


def _node_manifest_deps(inv: Inventory, folder: str = "") -> set[str] | None:
    text = inv.read(_in_folder(folder, "package.json"))
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        block = data.get(key)
        if isinstance(block, dict):
            deps |= set(block)
    return deps


def _toml_package_names(text: str) -> set[str]:
    names: set[str] = set()
    for block in re.finditer(r"(?ms)^\[\[package\]\]\s*\n(.*?)(?=^\[\[|\Z)", text):
        match = re.search(r"(?m)^\s*name\s*=\s*[\"']([^\"']+)[\"']", block.group(1))
        if match:
            names.add(match.group(1))
    return names


def _node_lock_deps(inv: Inventory, lockfile: str) -> set[str] | None:
    text = inv.read(lockfile)
    if text is None:
        return None
    name = lockfile.rsplit("/", 1)[-1]
    if name in ("package-lock.json", "npm-shrinkwrap.json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        deps: set[str] = set()
        packages = data.get("packages")
        if isinstance(packages, dict):
            for key in packages:
                if key:
                    deps.add(key.rsplit("node_modules/", 1)[-1])
        legacy = data.get("dependencies")
        if isinstance(legacy, dict):
            deps |= set(legacy)
        return deps
    if name == "pnpm-lock.yaml":
        deps = set(re.findall(r"(?m)^\s{2,}'?((?:@[^/'\s]+/)?[A-Za-z0-9._-]+)@[^'\s:]+'?\s*:", text))
        deps |= set(re.findall(r"(?m)^\s{4,}'?((?:@[^/'\s]+/)?[A-Za-z0-9._-]+)'?:\s*$", text))
        return deps or None
    if name == "yarn.lock":
        deps = set(re.findall(r"(?m)^\"?((?:@[^/\"]+/)?[A-Za-z0-9._-]+)@", text))
        return deps or None
    return None


def _python_manifest_deps(inv: Inventory, folder: str = "") -> set[str] | None:
    deps: set[str] = set()
    parsed = False
    text = inv.read(_in_folder(folder, "pyproject.toml"))
    if text is not None:
        parsed = True
        for block in re.finditer(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", text):
            for item in re.findall(r"[\"']([^\"']+)[\"']", block.group(1)):
                name = _dependency_name(item)
                if name:
                    deps.add(name)
        for block in re.finditer(r"(?ms)^\[tool\.poetry\.dependencies\]\s*\n(.*?)(?=^\[|\Z)", text):
            for line in block.group(1).splitlines():
                match = re.match(r"^([A-Za-z0-9_.-]+)\s*=", line.strip())
                if match and match.group(1).lower() != "python":
                    deps.add(match.group(1))
    for req in ("requirements.txt", "requirements-dev.txt"):
        req_text = inv.read(_in_folder(folder, req))
        if req_text is None:
            continue
        parsed = True
        for line in req_text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            name = _dependency_name(line)
            if name:
                deps.add(name)
    return deps if parsed else None


def _python_lock_deps(inv: Inventory, lockfile: str) -> set[str] | None:
    text = inv.read(lockfile)
    if text is None:
        return None
    name = lockfile.rsplit("/", 1)[-1]
    if name in ("poetry.lock", "uv.lock", "pdm.lock"):
        return _toml_package_names(text) or None
    if name == "Pipfile.lock":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        deps: set[str] = set()
        for key in ("default", "develop"):
            block = data.get(key)
            if isinstance(block, dict):
                deps |= set(block)
        return deps or None
    return None


def _cargo_manifest_deps(inv: Inventory, folder: str = "") -> set[str] | None:
    text = inv.read(_in_folder(folder, "Cargo.toml"))
    if text is None:
        return None
    deps: set[str] = set()
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        header = re.match(r"^\[(.+)\]$", stripped)
        if header:
            in_deps = header.group(1).endswith("dependencies")
            continue
        if in_deps:
            match = re.match(r"^([A-Za-z0-9_-]+)\s*=", stripped)
            if match:
                deps.add(match.group(1))
    return deps


def _go_manifest_deps(inv: Inventory, folder: str = "") -> set[str] | None:
    text = inv.read(_in_folder(folder, "go.mod"))
    if text is None:
        return None
    deps: set[str] = set()
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_block = True
            continue
        if in_block and stripped == ")":
            in_block = False
            continue
        if stripped.startswith("require "):
            parts = stripped.split()
            if len(parts) >= 2:
                deps.add(parts[1])
            continue
        if in_block and stripped and not stripped.startswith("//"):
            parts = stripped.split()
            if parts:
                deps.add(parts[0])
    return deps


def _go_lock_deps(inv: Inventory, lockfile: str) -> set[str] | None:
    text = inv.read(lockfile)
    if text is None:
        return None
    deps = {line.split()[0] for line in text.splitlines() if len(line.split()) >= 2}
    return deps or None


#: MSBuild files that a project imports implicitly from its own folder and every folder above it; package references
#: there are not read.
_DOTNET_IMPORTED = ("Directory.Build.props", "Directory.Build.targets", "Directory.Packages.props")
_DOTNET_PROJECT_SUFFIXES = (".csproj", ".fsproj", ".vbproj")
_PACKAGE_REFERENCE = re.compile(r"<PackageReference\b[^>]*?\bInclude\s*=\s*[\"']([^\"']+)[\"']")


def _dotnet_manifest_deps(inv: Inventory, folder: str = "") -> set[str] | None:
    """The ``PackageReference`` names of the project files in ``folder`` itself.

    ``None`` (cannot compare) when the folder holds no project file, when a project imports another MSBuild file, or
    when a ``Directory.*`` file in the folder or above it adds package references: those references are not read here.
    """
    prefix = f"{folder}/" if folder else ""
    projects = sorted(
        rel
        for rel in inv.paths()
        if rel.startswith(prefix) and "/" not in rel[len(prefix) :] and rel.endswith(_DOTNET_PROJECT_SUFFIXES)
    )
    if not projects:
        return None
    parts = folder.split("/") if folder else []
    for depth in range(len(parts), -1, -1):
        for imported in _DOTNET_IMPORTED:
            text = inv.read(_in_folder("/".join(parts[:depth]), imported))
            if text is not None and re.search(r"<(?:Global)?PackageReference\b", text):
                return None
    deps: set[str] = set()
    for project in projects:
        text = inv.read(project)
        if text is None or re.search(r"<Import\b", text):
            return None
        deps |= set(_PACKAGE_REFERENCE.findall(text))
    return deps


def _dotnet_lock_deps(inv: Inventory, lockfile: str) -> set[str] | None:
    """Every package name a ``packages.lock.json`` records, over all its target frameworks."""
    text = inv.read(lockfile)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    frameworks = data.get("dependencies") if isinstance(data, dict) else None
    if not isinstance(frameworks, dict):
        return None
    deps: set[str] = set()
    for packages in frameworks.values():
        if isinstance(packages, dict):
            deps |= set(packages)
    return deps


def _manifest_deps(inv: Inventory, ecosystem: str, folder: str = "") -> set[str] | None:
    if ecosystem == "node":
        return _node_manifest_deps(inv, folder)
    if ecosystem == "python":
        return _python_manifest_deps(inv, folder)
    if ecosystem == "rust":
        return _cargo_manifest_deps(inv, folder)
    if ecosystem == "go":
        return _go_manifest_deps(inv, folder)
    if ecosystem == "dotnet":
        return _dotnet_manifest_deps(inv, folder)
    return None


def _lock_deps(inv: Inventory, ecosystem: str, lockfile: str) -> set[str] | None:
    if ecosystem == "node":
        return _node_lock_deps(inv, lockfile)
    if ecosystem == "python":
        return _python_lock_deps(inv, lockfile)
    if ecosystem == "rust":
        text = inv.read(lockfile)
        return (_toml_package_names(text) or None) if text is not None else None
    if ecosystem == "go":
        return _go_lock_deps(inv, lockfile)
    if ecosystem == "dotnet":
        return _dotnet_lock_deps(inv, lockfile)
    return None


def _lockfile_paths(inv: Inventory, ecosystem: str, tracked: Collection[str] = ()) -> list[str]:
    """Every lockfile of the ecosystem, at any depth, as the path git would track it; the shallowest first.

    ``tracked`` adds each tracked lockfile the walk skipped as ignored (issue #21). The walk applies ``!`` lines
    (ADR-0009), so this is a lockfile an ignore rule covers but git tracks, such as one added with ``git add -f``.
    A file in a directory the walk never enters (``node_modules``) is not one of them.
    """
    names = _lockfiles_for(ecosystem)
    found = {rel for rel in inv.paths() if rel.split("/")[-1] in names}
    found |= {
        rel for rel, reason in inv.skipped if reason == "ignored" and rel in tracked and rel.split("/")[-1] in names
    }
    return sorted(found, key=lambda rel: (rel.count("/"), rel))


def _lock_consistency(inv: Inventory, ecosystem: str, lockfile: str) -> tuple[str, set[str]]:
    """Return ``(state, extras)`` where state is ok | mismatch | unverified.

    A lockfile is compared with the manifest in its own folder (``app/package-lock.json`` with
    ``app/package.json``), never with one above it; no manifest there is ``unverified``.
    """
    folder = lockfile.rsplit("/", 1)[0] if "/" in lockfile else ""
    manifest = _manifest_deps(inv, ecosystem, folder)
    lock = _lock_deps(inv, ecosystem, lockfile)
    if manifest is None or lock is None:
        return "unverified", set()
    if not manifest:
        return "ok", set()
    if not lock:
        return "unverified", set()
    if ecosystem in _CASE_INSENSITIVE:
        folded = {name.casefold() for name in lock}
        extras = {name for name in manifest if name.casefold() not in folded}
    else:
        extras = manifest - lock
    return ("mismatch", extras) if extras else ("ok", set())


#: The ecosystems whose lockfile :func:`_lock_consistency` compares with a manifest.
_COMPARED = frozenset({"node", "python", "rust", "go", "dotnet"})


def _unverified_finding(spec, inv: Inventory, ecosystem: str, lockfile: str) -> Finding:
    """The ``PARTIAL`` finding for a tracked lockfile that :func:`_lock_consistency` could not compare."""
    folder = lockfile.rsplit("/", 1)[0] if "/" in lockfile else ""
    by_hand = "Confirm by hand that the lockfile names every dependency of the manifest beside it."
    remediation = by_hand
    if ecosystem not in _COMPARED:
        reason = f"the engine does not compare {ecosystem} lockfiles"
    elif _manifest_deps(inv, ecosystem, folder) is None:
        reason = f"the engine found no {ecosystem} manifest it can read in the lockfile's own folder"
        remediation = (
            "Keep the lockfile in the same folder as the manifest it locks, so the engine can compare them; "
            "otherwise confirm by hand that the lockfile names every dependency of its manifest."
        )
    else:
        reason = "the engine cannot read the dependency names in the lockfile"
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=Verdict.PARTIAL,
        statement=statement(
            "confirm that every run installs identical dependencies",
            f"{lockfile} is tracked, but {reason}, so its consistency with the manifest is unverified",
        ),
        evidence=[Evidence(lockfile, note="consistency unverified")],
        remediation=remediation,
        path=lockfile,
    )


def check_exec02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    ecosystems = sorted((stack.ecosystems - stack.source_only) & set(_ECOSYSTEM_MANAGERS))
    if not ecosystems:
        no_convention = sorted(stack.ecosystems - stack.source_only)
        if no_convention:
            return _unknown(
                spec,
                f"{', '.join(no_convention)} has no lockfile convention the engine reads, so no lockfile is expected",
            )
        from_source = sorted(stack.source_only & set(_ECOSYSTEM_MANAGERS))
        if from_source:
            return _unknown(
                spec,
                f"{', '.join(from_source)} was recognised from its source files and no manifest declares "
                "dependencies, so no lockfile is expected",
            )
        return _unknown(spec, "no recognised ecosystem, so no lockfile is expected")

    tracked = tracked_in_scope(target, inventory)
    if tracked is None:
        return _unknown(spec, "git could not report tracked files, so the lockfile's tracked state is unknown")

    findings: list[Finding] = []
    verified: list[str] = []
    unverified: list[str] = []
    missing: list[str] = []
    untracked: list[str] = []
    stale: list[str] = []
    partial: list[Finding] = []
    for ecosystem in ecosystems:
        candidates = _lockfile_paths(inventory, ecosystem, tracked)
        tracked_candidates = [rel for rel in candidates if rel in tracked]
        if not candidates:
            missing.append(f"{ecosystem} ({', '.join(_lockfiles_for(ecosystem))})")
            findings.append(
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "install identical dependencies on every run",
                        f"the {ecosystem} project has no lockfile "
                        f"({', '.join(_lockfiles_for(ecosystem))}), so "
                        + _NO_LOCK_REASON.get(ecosystem, "a fresh install resolves whatever versions are current"),
                    ),
                    remediation=_NO_LOCK_REMEDIATION.get(
                        ecosystem, "Generate the lockfile with the project's package manager and commit it."
                    ),
                    path=ecosystem,
                )
            )
            continue
        untracked_here = [rel for rel in candidates if rel not in tracked]
        if untracked_here:
            untracked.extend(untracked_here)
            findings.append(
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "install identical dependencies on every run",
                        f"{', '.join(sorted(untracked_here))} exists but is not tracked, so a fresh "
                        f"checkout does not get it",
                    ),
                    evidence=[Evidence(p) for p in sorted(untracked_here)],
                    remediation="Commit the lockfile; add it to .gitignore only if the team has "
                    "deliberately chosen floating dependencies.",
                    path=sorted(untracked_here)[0],
                )
            )
        for lockfile in tracked_candidates:
            state, extras = _lock_consistency(inventory, ecosystem, lockfile)
            if state == "mismatch":
                stale.append(lockfile)
                findings.append(
                    Finding(
                        check=spec.id,
                        severity=spec.severity,
                        phase=spec.phase,
                        verdict=Verdict.FAIL,
                        statement=statement(
                            "install identical dependencies on every run",
                            f"{lockfile} is tracked but omits manifest dependencies: {', '.join(sorted(extras)[:12])}",
                        ),
                        evidence=[Evidence(lockfile, note="lockfile out of step with the manifest")],
                        remediation="Re-run the package manager's install/lock step and commit the updated lockfile.",
                        path=lockfile,
                    )
                )
            elif state == "unverified":
                unverified.append(lockfile)
                partial.append(_unverified_finding(spec, inventory, ecosystem, lockfile))
            else:
                verified.append(lockfile)

    if findings:
        verdict = Verdict.FAIL
    elif partial:
        verdict = Verdict.PARTIAL
    else:
        verdict = Verdict.PASS
    detail = "; ".join(
        filter(
            None,
            [
                f"no lockfile: {', '.join(missing)}" if missing else "",
                f"not tracked: {', '.join(untracked)}" if untracked else "",
                f"out of step with the manifest: {', '.join(stale)}" if stale else "",
                f"tracked: {', '.join(verified)}" if verified else "",
                f"consistency unverified: {', '.join(unverified)}" if unverified else "",
            ],
        )
    )
    return _outcome(spec, verdict, detail, findings + partial)


# ===========================================================================
# EXEC-03 — non-interactive setup path
# ===========================================================================

_SETUP_FILES = (
    ".devcontainer/devcontainer.json",
    ".devcontainer.json",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "Dockerfile",
    "setup.sh",
    "bootstrap.sh",
    "dev-setup.sh",
)
#: Dockerfiles with a variant in the name (``Dockerfile.jvm``, ``dev.Dockerfile``), found at any depth by base name:
#: frameworks keep them below the root (Quarkus writes ``src/main/docker/Dockerfile.jvm``).
_DOCKERFILE_PATTERNS = ("Dockerfile.*", "*.Dockerfile", "*.dockerfile")
#: The dev container spec reads ``.devcontainer/devcontainer.json`` and one configuration per subfolder,
#: ``.devcontainer/<name>/devcontainer.json``.
_DEVCONTAINER_PATTERNS = (".devcontainer/*.json", ".devcontainer/*/devcontainer.json")
_DOC_FILES = (README, "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md")
_SETUP_TARGETS = ("setup", "bootstrap", "install", "dev", "dev-setup")


def _setup_signals(inv: Inventory) -> list[str]:
    signals = [name for name in _SETUP_FILES if inv.has(name)]
    signals += inv.match(*_DEVCONTAINER_PATTERNS)
    signals += inv.match(*_DOCKERFILE_PATTERNS)

    make_targets = parse_makefile_targets(inv)
    signals += [f"Makefile:{t}" for t in _SETUP_TARGETS if t in make_targets]

    scripts = extract_npm_scripts(inv)
    signals += [f"package.json:{t}" for t in _SETUP_TARGETS if t in scripts]
    return sorted(dict.fromkeys(signals))


_INSTALL_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "npm": frozenset({"install", "ci", "i"}),
    "pnpm": frozenset({"install", "i"}),
    "yarn": frozenset({"install"}),
    "bun": frozenset({"install"}),
    "pip": frozenset({"install"}),
    "pip3": frozenset({"install"}),
    "poetry": frozenset({"install"}),
    "pipenv": frozenset({"install", "sync"}),
    "uv": frozenset({"sync", "pip"}),
    "bundle": frozenset({"install"}),
    "gem": frozenset({"install"}),
    "composer": frozenset({"install"}),
    "make": frozenset(_SETUP_TARGETS),
    "task": frozenset(_SETUP_TARGETS),
    "cargo": frozenset({"fetch", "build"}),
    "go": frozenset({"mod", "build", "install"}),
    "dotnet": frozenset({"restore"}),
    "gradle": frozenset({"build", "assemble"}),
    "gradlew": frozenset({"build", "assemble"}),
    "mvn": frozenset({"install", "package"}),
    "mvnw": frozenset({"install", "package"}),
    "docker": frozenset({"compose", "build"}),
    "docker-compose": frozenset({"up", "build"}),
    "nvm": frozenset({"use"}),
}


def _tokenise(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
        tokens = tokens[1:]
    return tokens


def _documented_setup(inv: Inventory) -> list[str]:
    found: set[str] = set()
    for name in entry_documents(inv, _DOC_FILES):
        text = inv.read(name)
        if not text:
            continue
        for _lang, _line, command in extract_documented_commands(text):
            tokens = _tokenise(command)
            if not tokens:
                continue
            head = tokens[0].lstrip("./")
            subcommands = _INSTALL_SUBCOMMANDS.get(head)
            if subcommands and len(tokens) > 1 and tokens[1] in subcommands:
                found.add(f"{name}: {command}")
    return sorted(found)


def _is_documented(signal: str, text: str) -> bool:
    name = signal.split(":", 1)[1] if ":" in signal else signal
    name = name.rsplit("/", 1)[-1]
    if name.endswith((".json", ".yml", ".yaml", ".sh")):
        return name in text or signal in text
    return name in text


def check_exec03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if not stack.ecosystems:
        return _unknown(spec, "no recognised ecosystem, so no setup path can be characterised")

    doc_text = "\n".join(filter(None, (inventory.read(n) for n in entry_documents(inventory, _DOC_FILES))))
    documented_commands = _documented_setup(inventory)
    if documented_commands:
        return _outcome(spec, Verdict.PASS, f"documented setup command: {documented_commands[0]}")

    signals = _setup_signals(inventory)
    documented = [s for s in signals if _is_documented(s, doc_text)]
    if documented:
        return _outcome(spec, Verdict.PASS, f"documented setup artifact: {', '.join(documented)}")
    if signals:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"present but undocumented: {', '.join(signals)}",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "provision the environment from the repository alone",
                        f"{', '.join(signals)} exists but no doc names it",
                    ),
                    evidence=[Evidence(s) for s in signals],
                    remediation="Reference the setup path in README.md or AGENTS.md so an "
                    "agent finds it without guessing.",
                )
            ],
        )

    return _outcome(
        spec,
        Verdict.FAIL,
        "no setup path found",
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "prepare the environment non-interactively",
                    "no devcontainer, compose file, Dockerfile, setup target/script, or documented "
                    "install command exists",
                ),
                remediation="Add a committed setup path (a devcontainer, compose file, or a documented "
                "install command in README.md) that runs with no prompts.",
            )
        ],
    )


# ===========================================================================
# EXEC-04 — env-var inventory complete
# ===========================================================================

#: The leading character anchors these on the env-var convention (upper-case first); the rest of
#: the capture class permits lower-case and digits too, so an identifier such as
#: ``UDA_LOG_LEVELNumber`` is captured whole rather than truncated at its first lower-case run.
_SHELL_ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Za-z0-9_]*)(?:(:?[-=+?])[^}]*)?\}")

#: The parameter-expansion operators that give a reference a fallback, so the script runs without the variable:
#: ``${VAR:-default}``, ``${VAR-default}``, ``${VAR:=default}``, ``${VAR=default}``, ``${VAR:+alt}`` and
#: ``${VAR+alt}`` (issue #13). ``${VAR:?message}`` and ``${VAR?message}`` stop the script without it, so they are
#: required references, as a bare ``${VAR}`` is.
_SHELL_OPTIONAL_OPERATORS = frozenset({":-", "-", ":=", "=", ":+", "+"})

#: A shell assignment to the same identifier class the reference pattern above captures —
#: ``GREEN='\033[0;32m'``, optionally ``export``-ed. A file that assigns ``VAR`` itself is
#: declaring a local shell variable, not requiring it from the process environment, so a
#: ``${VAR}`` use of it is excluded from that file's contribution to the referenced-keys set.
#: Scoped per key, per file (the capture group names exactly which identifier was assigned) —
#: never a single blanket pattern that can't tell one variable name from another.
_SHELL_ASSIGN_PATTERN = re.compile(r"(?m)^[ \t]*(?:export[ \t]+)?([A-Z][A-Za-z0-9_]*)[ \t]*=")
_CODE_ENV_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"os\.environ\.get\(\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']"),
    re.compile(r"os\.environ\[\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']\s*\]"),
    re.compile(r"os\.getenv\(\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']"),
    re.compile(r"(?<!os\.)\bgetenv\(\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']"),
    re.compile(r"process\.env\.([A-Z][A-Za-z0-9_]*)"),
    re.compile(r"process\.env\[\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']\s*\]"),
    re.compile(r"ENV\[\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']\s*\]"),
)

#: Files where ``${VAR}`` is an environment reference rather than a language-level string
#: interpolation. Restricting the shell pattern to these is what keeps a TypeScript template
#: literal such as ``${PIPELINE_VERSION}`` from being misread as an undeclared secret. Deployment
#: YAML (compose, Terraform) is deliberately out of scope: its ``${VAR}`` references usually name
#: host/CI values, not repository environment requirements.
_SHELL_ENV_SUFFIXES = (".sh", ".bash", ".zsh", ".fish", ".ksh", ".ps1")
_SHELL_ENV_BASENAMES = ("Dockerfile",)

#: Conventional host/CI/test variables an agent never needs a template for. Kept in code so the
#: allow-list is deterministic and reviewable rather than a per-target heuristic.
_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "CI",
        "HOME",
        "PATH",
        "PWD",
        "SHELL",
        "USER",
        "LANG",
        "LC_ALL",
        "TZ",
        "TERM",
        "TMPDIR",
        "NODE_ENV",
        "DEBUG",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "VERBOSE",
        "PORT",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "VIRTUAL_ENV",
        "PYTHONHASHSEED",
        "FORCE_COLOR",
        "NO_COLOR",
        "COLUMNS",
        "LINES",
        # Variables the shell itself sets (bash, and zsh where it shares the name), never read from a template.
        "BASHPID",
        "EPOCHREALTIME",
        "EPOCHSECONDS",
        "EUID",
        "FUNCNAME",
        "GROUPS",
        "HOSTNAME",
        "HOSTTYPE",
        "IFS",
        "LINENO",
        "MACHTYPE",
        "OLDPWD",
        "OPTARG",
        "OPTIND",
        "OSTYPE",
        "PIPESTATUS",
        "PPID",
        "RANDOM",
        "REPLY",
        "SECONDS",
        "SHELLOPTS",
        "SHLVL",
        "SRANDOM",
        "UID",
    }
)
_ENV_ALLOW_PREFIXES: tuple[str, ...] = (
    "GITHUB_",
    "CI_",
    "RUNNER_",
    "ACTIONS_",
    "npm_config_",
    "NPM_CONFIG_",
    "VITEST_",
    "PYTEST_",
    "COVERAGE_",
    "BASH_",
)
_ENV_EXAMPLE_FILES = (".env.example", ".env.sample", ".env.template", "env.example")


def _is_shell_env_file(rel: str) -> bool:
    return rel.endswith(_SHELL_ENV_SUFFIXES) or rel.rsplit("/", 1)[-1] in _SHELL_ENV_BASENAMES


def _referenced_env_keys(inv: Inventory) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """The keys the repository requires and the keys it reads only with a fallback, each with the files that read it.

    A key is optional only when every shell reference to it has a fallback operator
    (:data:`_SHELL_OPTIONAL_OPERATORS`) and no source file reads it; one required reference anywhere makes it
    required.
    """
    required: dict[str, set[str]] = {}
    optional: dict[str, set[str]] = {}
    for path in inv.paths():
        if not _is_shell_env_file(path):
            continue
        text = inv.read(path)
        if text:
            assigned_here = {m.group(1) for m in _SHELL_ASSIGN_PATTERN.finditer(text)}
            for match in _SHELL_ENV_PATTERN.finditer(text):
                key = match.group(1)
                if key in assigned_here:
                    continue
                target = optional if match.group(2) in _SHELL_OPTIONAL_OPERATORS else required
                target.setdefault(key, set()).add(path)
    for pattern in _CODE_ENV_PATTERNS:
        for rel, _line, text in inv.grep(pattern, kinds=(Kind.SOURCE, Kind.SCRIPT), limit=2000):
            for match in pattern.finditer(text):
                if match.group(1):
                    required.setdefault(match.group(1), set()).add(rel)
    return required, {key: readers for key, readers in optional.items() if key not in required}


def _declared_env_keys(inv: Inventory) -> dict[str, set[str]]:
    """Each committed example file, at any depth, shallowest first, with the keys it declares."""
    templates = sorted(
        (rel for rel in inv.paths() if rel.rsplit("/", 1)[-1] in _ENV_EXAMPLE_FILES),
        key=lambda rel: (rel.count("/"), rel),
    )
    declared: dict[str, set[str]] = {}
    for rel in templates:
        text = inv.read(rel)
        if text is None:
            continue
        keys = declared.setdefault(rel, set())
        for line in text.splitlines():
            match = re.match(r"^\s*(?:export\s+)?#?\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
            if match:
                keys.add(match.group(1))
    return declared


def _reaches(template: str, rel: str) -> bool:
    """Whether an example file documents ``rel``: it sits in ``rel``'s folder or a folder above it."""
    folder = template.rsplit("/", 1)[0] + "/" if "/" in template else ""
    return rel.startswith(folder)


def _declared_for(key: str, readers: set[str], declared: dict[str, set[str]]) -> bool:
    """Whether every file that reads ``key`` is reached by an example file that declares it."""
    holders = [template for template, keys in declared.items() if key in keys]
    return all(any(_reaches(template, rel) for template in holders) for rel in readers)


def _env_allowed(key: str) -> bool:
    return key in _ENV_ALLOWLIST or key.startswith(_ENV_ALLOW_PREFIXES)


def check_exec04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    referenced, optional = _referenced_env_keys(inventory)
    declared = _declared_env_keys(inventory)
    files = list(declared)
    missing = sorted(
        key
        for key, readers in referenced.items()
        if not _env_allowed(key) and not _declared_for(key, readers, declared)
    )
    optional_undeclared = sorted(
        key for key, readers in optional.items() if not _env_allowed(key) and not _declared_for(key, readers, declared)
    )
    keys = EnvKeys(
        referenced=tuple(sorted(referenced)),
        missing=tuple(missing),
        templates=tuple(files),
        optional=tuple(optional_undeclared),
    )
    optional_note = (
        f"; {len(optional_undeclared)} optional key(s) with a fallback, not in an example file: "
        f"{', '.join(optional_undeclared[:12])}"
        if optional_undeclared
        else ""
    )

    if not missing:
        if referenced:
            detail = f"{len(referenced)} referenced key(s) declared"
        else:
            detail = "no required environment key referenced" if optional else "no environment keys referenced"
        return _outcome(spec, Verdict.PASS, detail + optional_note, data=keys)

    because = (
        f"{len(missing)} referenced key(s) are absent from "
        + (
            f"every example file that covers the files reading them ({', '.join(files)})"
            if files
            else "any committed example file"
        )
        + f": {', '.join(missing[:12])}"
    )
    return _outcome(
        spec,
        Verdict.FAIL,
        because + optional_note,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement("know every variable the code needs before running it", because),
                evidence=[Evidence(f) for f in files] or [Evidence("(no example file)")],
                remediation="Add the missing keys to .env.example (values redacted) so the environment "
                "can be provisioned without reading the source.",
            )
        ],
        data=keys,
    )


# ===========================================================================
# EXEC-05 — no generated artifacts committed in-tree
# ===========================================================================

_GENERATED_HEADER_MARKERS = (
    "@generated",
    "do not edit",
    "generated by",
    "code generated",
    "auto-generated",
    "autogenerated",
    "this file is generated",
)


def _has_generated_header(text: str | None) -> bool:
    if text is None:
        return False
    head = "\n".join(text.splitlines()[:20]).lower()
    return any(marker in head for marker in _GENERATED_HEADER_MARKERS)


def _ignored_build_files(target, inventory: Inventory) -> set[str]:
    """The tracked text files under ``build/`` the target's own ignore rules also match.

    The ignore rules are the sign that such a file is build output (issue #260): the folder name alone is not,
    because repositories keep hand-written build scripts there.
    """
    ignored = set(tracked_and_ignored(target, inventory) or ())
    return {f.rel for f in inventory.files if f.has_text and f.rel in ignored and in_signed_generated_dir(f.rel)}


def check_exec05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    tracked = tracked_in_scope(target, inventory)
    if tracked is None:
        return _unknown(spec, "git could not report tracked files, so generated-file state is unknown")

    named = {f.rel for f in inventory.files if f.kind is Kind.GENERATED and f.rel in tracked}
    generated = sorted(named | _ignored_build_files(target, inventory))
    if not generated:
        return _outcome(spec, Verdict.PASS, "no tracked generated or vendored paths")

    offenders = [rel for rel in generated if not _has_generated_header(inventory.read(rel))]
    if not offenders:
        return _outcome(spec, Verdict.PASS, f"{len(generated)} tracked generated path(s) carry a generated header")

    because = (
        f"{len(offenders)} generated/vendored path(s) are tracked without a "
        f"generated-file header: {', '.join(offenders[:12])}"
    )
    return _outcome(
        spec,
        Verdict.FAIL,
        because,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement("edit tracked source without it being overwritten", because),
                evidence=[Evidence(p) for p in offenders[:12]],
                remediation="Untrack the generated output and ignore it, or add a generated-file header "
                "(`@generated` / `DO NOT EDIT`) so agents know not to edit it.",
            )
        ],
    )


# ===========================================================================
# EXEC-06 — documented commands resolve
# ===========================================================================

_KNOWN_TOOLS = frozenset(
    {
        "python",
        "python3",
        "pip",
        "pip3",
        "poetry",
        "uv",
        "pipenv",
        "pytest",
        "tox",
        "ruff",
        "black",
        "mypy",
        "pyright",
        "flake8",
        "pylint",
        "isort",
        "node",
        "npm",
        "npx",
        "pnpm",
        "yarn",
        "bun",
        "corepack",
        "tsc",
        "vitest",
        "jest",
        "eslint",
        "biome",
        "prettier",
        "shx",
        "husky",
        "lint-staged",
        "commitlint",
        "semgrep",
        "go",
        "gofmt",
        "golangci-lint",
        "cargo",
        "rustc",
        "rustup",
        "clippy",
        "rustfmt",
        "java",
        "javac",
        "mvn",
        "gradle",
        "dotnet",
        "ruby",
        "gem",
        "bundle",
        "rake",
        "php",
        "composer",
        "git",
        "gh",
        "docker",
        "docker-compose",
        "podman",
        "kubectl",
        "helm",
        "terraform",
        "aws",
        "az",
        "gcloud",
        "make",
        "task",
        "just",
        "cmake",
        "ninja",
        "bash",
        "sh",
        "zsh",
        "fish",
        "shellcheck",
        "curl",
        "wget",
        "jq",
        "yq",
        "tar",
        "zip",
        "unzip",
        "gzip",
        "openssl",
        "ssh",
        "scp",
        "rsync",
        "mkdir",
        "cp",
        "mv",
        "rm",
        "ls",
        "cat",
        "touch",
        "chmod",
        "ln",
        "sed",
        "awk",
        "grep",
        "find",
        "xargs",
        "which",
        "command",
        "env",
        "echo",
        "printf",
        "head",
        "tail",
        "tee",
        "sort",
        "uniq",
        "wc",
        "diff",
        "sleep",
        "kill",
        "ps",
        "du",
        "df",
        "nvm",
        "fnm",
        "asdf",
        "mise",
        "volta",
        "sdk",
        "pre-commit",
        "lefthook",
        "opencode",
        "claude",
        "codex",
        "gemini",
        "aider",
        "copilot",
        "cursor",
        "windsurf",
        "amp",
        "crush",
        "pi",
        "goose",
        "audit",
    }
)

_SHELL_KEYWORDS = frozenset(
    {
        "cd",
        "export",
        "source",
        ".",
        "set",
        "unset",
        "alias",
        "if",
        "then",
        "else",
        "elif",
        "fi",
        "for",
        "while",
        "do",
        "done",
        "case",
        "esac",
        "function",
        "return",
        "local",
        "readonly",
        "declare",
        "eval",
        "trap",
        "umask",
        "ulimit",
        "wait",
        "jobs",
        "fg",
        "bg",
        "type",
        "hash",
        "pwd",
        "whoami",
        "id",
        "uname",
        "date",
        "hostname",
        "realpath",
        "dirname",
        "basename",
        "printenv",
        "true",
        "false",
        "exit",
        "yes",
        "no",
        "test",
        "[",
        "[[",
    }
)

_STRIPPABLE_PREFIXES = frozenset({"sudo", "env", "time", "nohup", "command", "stdbuf"})


def _package_bins(inv: Inventory) -> set[str]:
    text = inv.read("package.json")
    if not text:
        return set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set()
    bins = data.get("bin")
    if isinstance(bins, str):
        return {str(data.get("name") or "").strip()} - {""}
    if isinstance(bins, dict):
        return set(bins)
    return set()


def _command_parts(command: str) -> list[str]:
    command = re.split(r"\s*(?:&&|\|\||;|\|)\s*", command, maxsplit=1)[0]
    command = re.split(r"\s+2?>\s*", command, maxsplit=1)[0]
    return _tokenise(command)


def _resolves(
    inv: Inventory, tokens: list[str], verbs: dict, scripts: dict, make_targets: dict, bins: set[str]
) -> bool:
    while tokens and tokens[0] in _STRIPPABLE_PREFIXES:
        tokens = tokens[1:]
    if not tokens:
        return True
    head = tokens[0]
    rest = tokens[1:]

    if head in _SHELL_KEYWORDS or head in _KNOWN_TOOLS:
        if head in {"npm", "pnpm", "bun"}:
            if rest[:1] == ["run"]:
                return len(rest) >= 2 and rest[1] in scripts
            return True
        if head == "yarn":
            if rest[:1] == ["run"]:
                return len(rest) >= 2 and rest[1] in scripts
            return True
        if head == "make":
            targets = [t for t in rest if not t.startswith("-") and "=" not in t]
            return all(t in make_targets for t in targets) if targets and make_targets else True
        return True

    if head in verbs:
        return True

    if head in bins:
        return True

    candidate = head[2:] if head.startswith("./") else head
    if "/" in candidate or head.startswith("./"):
        if inv.has(candidate) or any(f.rel == candidate or f.rel.startswith(candidate + "/") for f in inv.files):
            return True

    return False


def _logical_commands(entries: list[tuple[str, int, str]]) -> list[tuple[str, int, str]]:
    """Join trailing-backslash line continuations into one command.

    ``extract_fenced_commands`` reports each physical line; a multi-line invocation would otherwise
    present its continuation lines (``--out ...``) as commands in their own right.
    """
    merged: list[tuple[str, int, str]] = []
    for path, line, command in entries:
        if merged and merged[-1][0] == path and merged[-1][1] + 1 == line and merged[-1][2].rstrip().endswith("\\"):
            prev_path, prev_line, prev = merged[-1]
            merged[-1] = (prev_path, prev_line, prev.rstrip().rstrip("\\").rstrip() + " " + command)
        else:
            merged.append((path, line, command))
    return merged


def check_exec06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    # The catalogue's evidence rule names README and AGENTS.md; docs/** fences routinely mix
    # languages (a Python snippet in a ```bash block), which is a documentation defect EXEC-06 is
    # not chartered to police.
    doc_paths = entry_documents(inventory, (README, "AGENTS.md", "CLAUDE.md"))

    raw: list[tuple[str, int, str]] = []
    for name in doc_paths:
        text = inventory.read(name)
        if not text:
            continue
        raw.extend((name, line, command) for _lang, line, command in extract_fenced_commands(text))

    commands = _logical_commands(raw)
    seen: set[str] = set()
    unique: list[tuple[str, int, str]] = []
    for path, line, command in commands:
        if command in seen:
            continue
        seen.add(command)
        unique.append((path, line, command))

    if not unique:
        return _outcome(spec, Verdict.PASS, "no fenced shell commands documented")

    verbs = resolve_verbs(inventory, stack)
    scripts = extract_npm_scripts(inventory)
    make_targets = parse_makefile_targets(inventory)
    # A verb is also invoked under its other spelling (``format:check`` for ``format-check``); the
    # resolver already knows which runner binds it, so ask it rather than re-reading the manifest.
    for verb, bindings in resolve_all_verbs(inventory, stack).items():
        for binding in bindings:
            kind = runner_kind(binding.runner)
            if kind == "Makefile" and make_targets:
                make_targets.setdefault(verb, binding.command)
            elif kind == "package.json":
                scripts.setdefault(verb, binding.command)
    bins = _package_bins(inventory)

    unresolved: list[tuple[str, int, str]] = []
    for path, line, command in unique:
        if re.search(r"[<]|\.\.\.|\b(your[_-]|tbd|xxx|placeholder)\b", command, re.IGNORECASE):
            continue
        tokens = _command_parts(command)
        if not tokens:
            continue
        if not _resolves(inventory, tokens, verbs, scripts, make_targets, bins):
            unresolved.append((path, line, command))

    if not unresolved:
        return _outcome(spec, Verdict.PASS, f"{len(unique)} documented command(s) resolve")

    because = f"{len(unresolved)} documented command(s) name no script, verb, or file: " + "; ".join(
        f"{cmd!r} ({path}:{line})" for path, line, cmd in unresolved[:8]
    )
    return _outcome(
        spec,
        Verdict.FAIL,
        because,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement("run the documented commands literally", because),
                evidence=[Evidence(path, line=line, note=cmd) for path, line, cmd in unresolved[:12]],
                remediation="Fix the documented command to name a resolvable script, verb, or file — an "
                "agent will run it exactly as written.",
            )
        ],
    )


# ===========================================================================
# EXEC-07 — no competing configs for one concern
# ===========================================================================

_CONCERN_GLOBS: dict[str, tuple[str, ...]] = {
    "lint": (
        "eslint.config.*",
        ".eslintrc",
        ".eslintrc.*",
        "biome.json",
        "biome.jsonc",
        "ruff.toml",
        ".ruff.toml",
        ".flake8",
        ".pylintrc",
        ".golangci.yml",
        ".golangci.yaml",
        "clippy.toml",
        ".stylelintrc",
        ".stylelintrc.*",
        "oxlint.json",
        ".oxlintrc.json",
    ),
    "format": (
        "prettier.config.*",
        ".prettierrc",
        ".prettierrc.*",
        "biome.json",
        "biome.jsonc",
        ".clang-format",
        "rustfmt.toml",
        ".rustfmt.toml",
        "dprint.json",
    ),
    "test": (
        "vitest.config.*",
        "jest.config.*",
        "pytest.ini",
        "tox.ini",
        ".mocharc.*",
        "karma.conf.js",
        "cypress.config.*",
    ),
    "types (TypeScript)": ("tsconfig.json", "jsconfig.json"),
    "types (Python)": ("mypy.ini", ".mypy.ini", "pyrightconfig.json"),
    "security": (".gitleaks.toml", "semgrep.yml", ".semgrep.yml", ".snyk", "osv-scanner.toml", ".bandit"),
}

#: Sections inside a root ``pyproject.toml`` that author a concern, matched per concern.
_PYPROJECT_SECTIONS: dict[str, tuple[str, ...]] = {
    "lint": (r"\[tool\.ruff\]", r"\[tool\.pylint\]", r"\[tool\.flake8\]"),
    "format": (r"\[tool\.black\]", r"\[tool\.ruff\.format\]"),
    "test": (r"\[tool\.pytest", r"\[tool\.tox\]"),
    "types (Python)": (r"\[tool\.mypy\]", r"\[tool\.pyright\]", r"\[tool\.basedpyright\]"),
    "security": (r"\[tool\.bandit\]",),
}


def _concern_configs(inv: Inventory) -> dict[str, list[str]]:
    roots = sorted(f.rel for f in inv.files if "/" not in f.rel)
    found: dict[str, list[str]] = {concern: [] for concern in _CONCERN_GLOBS}
    for concern, globs in _CONCERN_GLOBS.items():
        for rel in roots:
            if any(fnmatch.fnmatch(rel, glob) for glob in globs):
                found[concern].append(rel)
    pyproject = inv.read("pyproject.toml")
    if pyproject is not None:
        for concern, patterns in _PYPROJECT_SECTIONS.items():
            if any(re.search(pattern, pyproject) for pattern in patterns):
                found[concern].append("pyproject.toml")
    return found


_MYPY_RE = re.compile(r"\bmypy\b")
_PYRIGHT_RE = re.compile(r"\b(?:based)?pyright\b")
_PYRIGHT_FILES = frozenset({"pyrightconfig.json"})
_MYPY_FILES = frozenset({"mypy.ini", ".mypy.ini"})


def _typecheck_runs(inventory: Inventory, stack, pattern: re.Pattern[str]) -> bool:
    """True when the ``typecheck`` verb runs a tool ``pattern`` names, directly or through the root Makefile."""
    binding = resolve_verbs(inventory, stack).get("typecheck")
    if binding is None:
        return False
    if pattern.search(binding.command):
        return True
    return binding.runner == "Makefile" and follow_makefile(inventory, binding.command, pattern.search) is not None


def _language_server_mirror(inventory: Inventory, stack, paths: list[str]) -> str | None:
    """The pyright config that mirrors the one mypy config the ``typecheck`` verb runs, or ``None``.

    Only files are read: a ``pyproject.toml`` that holds both tables is one path and never competes."""
    mypy = [p for p in paths if p in _MYPY_FILES]
    pyright = [p for p in paths if p in _PYRIGHT_FILES]
    if len(mypy) != 1 or not pyright or len(mypy) + len(pyright) != len(paths):
        return None
    if not _typecheck_runs(inventory, stack, _MYPY_RE) or _typecheck_runs(inventory, stack, _PYRIGHT_RE):
        return None
    return f"{', '.join(pyright)} mirrors {mypy[0]} for a language server (typecheck runs mypy)"


def check_exec07(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _concern_configs(inventory)
    competing = {concern: sorted(set(paths)) for concern, paths in found.items() if len(set(paths)) > 1}
    notes: list[str] = []
    python = competing.get("types (Python)")
    mirror = _language_server_mirror(inventory, stack, python) if python else None
    if mirror:
        del competing["types (Python)"]
        found["types (Python)"] = [p for p in python if p in _MYPY_FILES]
        notes.append(mirror)
    if not competing:
        authored = {c: (paths[0] if paths else None) for c, paths in found.items() if paths}
        detail = "; ".join([*(f"{c}: {p}" for c, p in sorted(authored.items())), *notes])
        return _outcome(spec, Verdict.PASS, detail or "no concern configs found")

    because = "; ".join(f"{concern} ({', '.join(paths)})" for concern, paths in sorted(competing.items()))
    return _outcome(
        spec,
        Verdict.FAIL,
        f"competing configs: {because}",
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "know which config wins for each concern",
                    f"{len(competing)} concern(s) have more than one config: {because}",
                ),
                evidence=[Evidence(p) for _concern, paths in sorted(competing.items()) for p in paths],
                remediation="Keep one authoritative config per concern and document any deliberate "
                "delegation, or delete the redundant config.",
            )
        ],
    )


# ===========================================================================
# EXEC-08 — tool versions visible to dependency automation
# ===========================================================================

#: Basenames of the command-runner and hook files whose lines are read.
_INLINE_SURFACE_NAMES = frozenset(
    {
        "Makefile",
        "makefile",
        "GNUmakefile",
        "justfile",
        "Justfile",
        ".justfile",
        "Taskfile.yml",
        "Taskfile.yaml",
        "package.json",
        "lefthook.yml",
        "lefthook.yaml",
        ".lefthook.yml",
        ".lefthook.yaml",
        ".gitlab-ci.yml",
    }
)

_LITERAL_VERSION = r"v?\d[\w.+-]*"
_SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")

#: ``(ecosystem, launcher pattern)``. The tokens after a launcher are read for ``name@version`` or
#: ``name==version``; a version is a literal only when it starts with a digit (or ``v`` and a digit).
_INLINE_LAUNCHERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("node", re.compile(r"(?:^|[\s(\"'])(?:npx|bunx|pnpx|pnpm\s+dlx|yarn\s+dlx|npm\s+exec)\s")),
    ("node", re.compile(r"(?:^|[\s(\"'])npm\s+(?:install|i)\s+(?:\S+\s+)*?(?:-g|--global)\b")),
    ("python", re.compile(r"(?:^|[\s(\"'])(?:uvx|uv\s+tool\s+(?:run|install)|pipx\s+(?:run|install))\s")),
    ("python", re.compile(r"(?:^|[\s(\"'])uv\s+run\s")),
    ("python", re.compile(r"(?:^|[\s(\"'])(?:pip3?|uv\s+pip|python3?\s+-m\s+pip)\s+install\s")),
    ("go", re.compile(r"(?:^|[\s(\"'])go\s+(?:run|install)\s")),
    ("rust", re.compile(r"(?:^|[\s(\"'])cargo\s+(?:install|binstall)\s")),
)

_NODE_TOKEN = re.compile(rf"^(@?[A-Za-z0-9][\w./-]*)@({_LITERAL_VERSION})$")
_PYTHON_TOKEN = re.compile(rf"^([A-Za-z0-9][\w.-]*)(?:\[[^\]]*\])?(?:==|@)({_LITERAL_VERSION})$")
_GO_TOKEN = re.compile(r"^([\w.-]+(?:/[\w.-]+)+)@(v\d[\w.+-]*)$")
_RUST_TOKEN = re.compile(rf"^([A-Za-z0-9][\w-]*)@({_LITERAL_VERSION})$")
_TOKEN_PATTERNS = {"node": _NODE_TOKEN, "python": _PYTHON_TOKEN, "go": _GO_TOKEN, "rust": _RUST_TOKEN}

#: Tool-installer actions whose input names a tool version: ``action -> (input, ecosystem, tool name)``.
_INSTALLER_ACTIONS: dict[str, tuple[str, str, str]] = {
    "astral-sh/setup-uv": ("version", "python", "uv"),
    "pnpm/action-setup": ("version", "node", "pnpm"),
    "oven-sh/setup-bun": ("bun-version", "node", "bun"),
    "golangci/golangci-lint-action": ("version", "go", "github.com/golangci/golangci-lint"),
}
_USES_RE = re.compile(r"^(\s*)(?:-\s+)?uses:\s*['\"]?([\w.-]+/[\w.-]+)(?:/[\w./-]*)?@")

_RENOVATE_FILES = ("renovate.json", ".renovaterc", ".renovaterc.json", ".github/renovate.json")


@dataclass(frozen=True)
class _InlineVersion:
    path: str
    line: int
    ecosystem: str
    tool: str
    version: str


def _inline_surfaces(inv: Inventory) -> list[str]:
    out = []
    for rel in inv.paths():
        base = rel.rsplit("/", 1)[-1]
        if (
            base in _INLINE_SURFACE_NAMES
            or base.endswith(".mk")
            or (rel.startswith(".github/workflows/") and base.endswith((".yml", ".yaml")))
            or (rel.startswith(".husky/") and rel.count("/") == 1)
        ):
            out.append(rel)
    return sorted(out)


def _token(raw: str) -> str:
    token = raw.strip().strip("\"'`,)")
    for prefix in ("--from=", "--with=", "--spec=", "--package="):
        if token.startswith(prefix):
            return token[len(prefix) :]
    return token


def _versions_in_segment(segment: str) -> list[tuple[str, str, str]]:
    """``(ecosystem, tool, version)`` for each literal-versioned token after a launcher in one command."""
    found: list[tuple[str, str, str]] = []
    for ecosystem, launcher in _INLINE_LAUNCHERS:
        match = launcher.search(segment)
        if not match:
            continue
        tokens = [_token(raw) for raw in segment[match.end() :].split()]
        pattern = _TOKEN_PATTERNS[ecosystem]
        for index, token in enumerate(tokens):
            hit = pattern.match(token)
            if hit:
                found.append((ecosystem, hit.group(1), hit.group(2)))
            elif ecosystem == "rust" and token in ("--version", "--vers") and index + 1 < len(tokens):
                name = next((t for t in tokens[:index] if not t.startswith("-")), None)
                if name and re.match(rf"^{_LITERAL_VERSION}$", tokens[index + 1]):
                    found.append((ecosystem, name, tokens[index + 1]))
    return sorted(set(found))


def _installer_versions(lines: list[str]) -> list[tuple[int, str, str, str]]:
    """``(line, ecosystem, tool, version)`` for a literal ``version`` input of a known tool-installer action."""
    found: list[tuple[int, str, str, str]] = []
    for index, line in enumerate(lines):
        uses = _USES_RE.match(line)
        if not uses or uses.group(2) not in _INSTALLER_ACTIONS:
            continue
        key, ecosystem, tool = _INSTALLER_ACTIONS[uses.group(2)]
        step_indent = len(uses.group(1))
        for number in range(index + 1, len(lines)):
            text = lines[number]
            if text.strip() and len(text) - len(text.lstrip()) <= step_indent:
                break
            value = re.match(rf"^\s*{re.escape(key)}:\s*['\"]?({_LITERAL_VERSION})['\"]?\s*(#.*)?$", text)
            if value:
                found.append((number + 1, ecosystem, tool, value.group(1)))
    return found


def _inline_versions(inv: Inventory, rel: str) -> list[_InlineVersion]:
    text = inv.read(rel) or ""
    lines = text.splitlines()
    out: list[_InlineVersion] = []
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("#"):
            continue
        for segment in _SEGMENT_SPLIT.split(line):
            for ecosystem, tool, version in _versions_in_segment(segment):
                out.append(_InlineVersion(rel, number, ecosystem, tool, version))
    if rel.startswith(".github/workflows/"):
        out.extend(_InlineVersion(rel, n, eco, tool, ver) for n, eco, tool, ver in _installer_versions(lines))
    return sorted(set(out), key=lambda v: (v.path, v.line, v.tool, v.version))


def _renovate_patterns(inv: Inventory) -> list[re.Pattern[str]]:
    """The file patterns of every Renovate custom manager: files Renovate reads versions from by regex."""
    patterns: list[re.Pattern[str]] = []
    for rel in _RENOVATE_FILES:
        try:
            config = json.loads(inv.read(rel) or "")
        except ValueError:
            continue
        if not isinstance(config, dict):
            continue
        for key in ("customManagers", "regexManagers"):
            managers = config.get(key)
            for manager in managers if isinstance(managers, list) else []:
                if not isinstance(manager, dict):
                    continue
                for field_name in ("fileMatch", "managerFilePatterns"):
                    raw = manager.get(field_name)
                    for item in raw if isinstance(raw, list) else []:
                        text = str(item)
                        if len(text) > 1 and text.startswith("/") and text.endswith("/"):
                            text = text[1:-1]
                        try:
                            patterns.append(re.compile(text))
                        except re.error:
                            continue
    return patterns


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _bare(version: str) -> str:
    return version[1:] if version.startswith("v") else version


def _node_manifest_holds(inv: Inventory, tool: str, version: str) -> bool:
    for rel in inv.paths():
        if rel.rsplit("/", 1)[-1] != "package.json":
            continue
        try:
            manifest = json.loads(inv.read(rel) or "")
        except ValueError:
            continue
        if not isinstance(manifest, dict):
            continue
        if manifest.get("packageManager") == f"{tool}@{_bare(version)}":
            return True
        for key in ("dependencies", "devDependencies", "optionalDependencies"):
            deps = manifest.get(key)
            if isinstance(deps, dict) and str(deps.get(tool, "")).lstrip("^~=v") == _bare(version):
                return True
    return False


def _python_manifest_holds(inv: Inventory, tool: str, version: str) -> bool:
    wanted = _normalise(tool)
    pin = re.compile(r"([A-Za-z0-9][\w.-]*)(?:\[[^\]]*\])?\s*==\s*([\w.+-]+)")
    for rel in inv.paths():
        base = rel.rsplit("/", 1)[-1]
        if base != "pyproject.toml" and not (base.startswith("requirements") and base.endswith(".txt")):
            continue
        for name, pinned in pin.findall(inv.read(rel) or ""):
            if _normalise(name) == wanted and pinned == version:
                return True
    return False


def _go_manifest_holds(inv: Inventory, tool: str, version: str) -> bool:
    for rel in inv.paths():
        if rel.rsplit("/", 1)[-1] != "go.mod":
            continue
        for line in (inv.read(rel) or "").splitlines():
            parts = line.split("//", 1)[0].split()
            if parts and parts[0] == "require":
                parts = parts[1:]
            if len(parts) >= 2 and (tool == parts[0] or tool.startswith(parts[0] + "/")):
                if _bare(parts[1]) == _bare(version):
                    return True
    return False


def _rust_manifest_holds(inv: Inventory, tool: str, version: str) -> bool:
    pin = re.compile(rf"^\s*{re.escape(tool)}\s*=\s*(?:\{{[^}}]*version\s*=\s*)?\"[=^~]?{re.escape(version)}\"", re.M)
    return any(pin.search(inv.read(rel) or "") for rel in inv.paths() if rel.rsplit("/", 1)[-1] == "Cargo.toml")


def _manifest_holds(inv: Inventory, found: _InlineVersion) -> bool:
    """Whether a manifest that dependency automation reads names the same tool at the same version."""
    lookup = {
        "node": _node_manifest_holds,
        "python": _python_manifest_holds,
        "go": _go_manifest_holds,
        "rust": _rust_manifest_holds,
    }[found.ecosystem]
    return lookup(inv, found.tool, found.version)


def check_exec08(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    surfaces = _inline_surfaces(inventory)
    if not surfaces:
        return _unknown(spec, "no command runner, workflow or hook file to read for tool versions")
    patterns = _renovate_patterns(inventory)
    visible = [rel for rel in surfaces if any(pattern.search(rel) for pattern in patterns)]
    inline = [v for rel in surfaces if rel not in visible for v in _inline_versions(inventory, rel)]
    if not inline:
        note = f"; {len(visible)} file(s) read by a Renovate custom manager" if visible else ""
        return _outcome(spec, Verdict.PASS, f"no literal tool version in {len(surfaces)} command file(s){note}")

    unheld = [v for v in inline if not _manifest_holds(inventory, v)]
    held = [v for v in inline if v not in unheld]

    def evidence(items: list[_InlineVersion]) -> list[Evidence]:
        return [Evidence(v.path, line=v.line, note=f"{v.tool} {v.version}") for v in items]

    findings: list[Finding] = []
    if unheld:
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "rely on dependency automation to patch the tools the gate runs",
                    f"{len(unheld)} tool version(s) are written into commands and no manifest holds them "
                    f"({', '.join(sorted({v.tool for v in unheld}))})",
                ),
                evidence=evidence(unheld),
                path=unheld[0].path,
                remediation="Move each version into a manifest the dependency-update tool reads (a dev-tools "
                "package.json or pyproject.toml with a lockfile, a go.mod tool directive) and have the "
                "command read it from there.",
            )
        )
    if held:
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "trust that one update changes every copy of a tool version",
                    f"{len(held)} tool version(s) written into commands repeat a manifest pin "
                    f"({', '.join(sorted({v.tool for v in held}))}), so the copy drifts when the manifest is updated",
                ),
                evidence=evidence(held),
                path=f"{held[0].path}:duplicate",
                remediation="Have the command read the version from the manifest instead of repeating it.",
            )
        )
    verdict = Verdict.FAIL if unheld else Verdict.PARTIAL
    summary = (
        f"{len(unheld)} literal tool version(s) no manifest holds"
        if unheld
        else f"{len(held)} literal tool version(s) repeat a manifest pin"
    )
    return _outcome(spec, verdict, summary, findings)


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
