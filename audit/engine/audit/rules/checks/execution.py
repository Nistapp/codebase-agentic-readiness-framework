# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC` pack — execution determinism.

Anchor: `docs/framework/phased-approach.md` § Activities.

Implemented here: `EXEC-01` … `EXEC-08`.

What each check reads and what makes it ``UNKNOWN`` rather than ``FAIL``:

* **EXEC-01** — a toolchain pin appropriate to each **detected** ecosystem (``.nvmrc``, ``engines``,
  ``.python-version``/``requires-python``, ``gradlew``/``mvnw``, ``global.json``,
  ``rust-toolchain.toml``, the ``go`` directive). Pin files and manifests count at any depth, so a nested
  ``go.mod``'s ``go`` directive, a nested ``requires-python`` or a nested ``engines.node`` pins the ecosystem. A
  pinned ecosystem with a module manifest that no pin reaches (:func:`_unpinned_modules`: not its own manifest, nor
  a pin file or a node/python pinning manifest in its folder or a parent) ⇒ ``PARTIAL``. No recognised ecosystem ⇒ ``UNKNOWN``; an ecosystem with no pin in the table (php) is not
  asserted against.
* **EXEC-02** — the ecosystem's lockfile is **tracked** (``audit.ignore.tracked_files``) and its
  declared dependencies agree with the manifest. ``tracked_files`` returning ``None`` (not a git
  repository, git absent) makes the tracked half ``UNKNOWN`` — never a ``PASS``. Agreement is a
  best-effort stdlib parse; when a manifest or lockfile cannot be parsed reliably the tracked fact
  is reported and consistency is left ``PARTIAL``, never ``PASS`` by inference. A lockfile is found at
  any depth and is tracked or not by the path it was found at (``app/package-lock.json``, not its
  basename); the shallowest is the one read. Only a lockfile at the root is compared with the root
  manifest, so one in a subdirectory is tracked but its consistency is unverified. An ecosystem that was
  recognised only from its source files (``Stack.source_only``) has no manifest and declares no
  dependencies, so it is not expected to have a lockfile.
* **EXEC-03** — a devcontainer / compose file / Dockerfile / setup target-script, or a documented
  non-interactive install command in the fenced blocks of README/``AGENTS.md``. Present but
  undocumented ⇒ ``PARTIAL``. No recognised ecosystem ⇒ ``UNKNOWN``: with no build manifest there is
  no way to say what provisioning is expected.
* **EXEC-04** — a set difference: env keys referenced by source against keys declared in the
  committed example file. A documented allow-list of conventional CI/test/host variables lives in
  :data:`_ENV_ALLOWLIST` and :data:`_ENV_ALLOW_PREFIXES`; it is deterministic and kept in code.
* **EXEC-05** — files the scan classifies ``GENERATED`` (including vendored paths) are either
  untracked or carry a generated-file header. Tracked state unavailable ⇒ ``UNKNOWN``.
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

Known limitation, recorded rather than hidden: manifest↔lockfile consistency parsing for ecosystems
beyond node/python/rust/go is not attempted, so those ecosystems report the tracked fact and
``PARTIAL`` consistency. This is deliberately conservative — a false ``PASS`` on a stale lockfile is
worse than an honest ``PARTIAL``.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shlex
from dataclasses import dataclass

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.checks._common import (
    extract_fenced_commands,
    follow_makefile,
    resolve_all_verbs,
    resolve_verbs,
    runner_kind,
    tracked_in_scope,
)
from audit.scan import Inventory, Kind
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
}
_PINNABLE = frozenset(_PIN_FILES) | {"go"}

#: A shared ``.tool-versions`` line counts for the ecosystem whose name follows it.
_TOOL_VERSIONS = {
    "node": re.compile(r"(?mi)^\s*(?:nodejs|node)\s+\S+"),
    "python": re.compile(r"(?mi)^\s*python\s+\S+"),
    "rust": re.compile(r"(?mi)^\s*rust\s+\S+"),
    "go": re.compile(r"(?mi)^\s*golang\s+\S+"),
}


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

    return sorted(dict.fromkeys(evidence))


#: The manifest that makes a module of the ecosystem, and what in it pins the toolchain.
_MODULE_MANIFESTS = {"node": "package.json", "python": "pyproject.toml", "go": "go.mod"}

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
    return re.search(r"(?m)^\s*go\s+\d", text) is not None


def _unpinned_modules(inv: Inventory, ecosystem: str) -> list[str]:
    """The module manifests of ``ecosystem`` that no pin reaches. A pin reaches a module when the module's own
    manifest pins, or when its folder or a parent folder holds a pin file (``.nvmrc``, ``.python-version``, a
    ``.tool-versions`` line) or, for node and python, a pinning manifest (a workspace root's ``engines.node`` or
    ``requires-python``). A Go module is its own toolchain unit, so a parent ``go.mod`` does not reach it."""
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
    if ecosystem != "go":
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
    "python": ("poetry", "uv", "pipenv"),
    "jvm": ("gradle",),
    "rust": ("cargo",),
    "go": ("gomod",),
    "ruby": ("bundler",),
    "php": ("composer",),
}


def _lockfiles_for(ecosystem: str) -> list[str]:
    return [f for manager in _ECOSYSTEM_MANAGERS.get(ecosystem, ()) for f in PACKAGE_MANAGERS.get(manager, ())]


def _dependency_name(spec_text: str) -> str | None:
    match = re.match(r"^[A-Za-z0-9_.@/-]+", spec_text.strip())
    return match.group(0) if match else None


def _node_manifest_deps(inv: Inventory) -> set[str] | None:
    text = inv.read("package.json")
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
    if lockfile == "package-lock.json":
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
    if lockfile == "pnpm-lock.yaml":
        deps = set(re.findall(r"(?m)^\s{2,}'?((?:@[^/'\s]+/)?[A-Za-z0-9._-]+)@[^'\s:]+'?\s*:", text))
        deps |= set(re.findall(r"(?m)^\s{4,}'?((?:@[^/'\s]+/)?[A-Za-z0-9._-]+)'?:\s*$", text))
        return deps or None
    if lockfile == "yarn.lock":
        deps = set(re.findall(r"(?m)^\"?((?:@[^/\"]+/)?[A-Za-z0-9._-]+)@", text))
        return deps or None
    return None


def _python_manifest_deps(inv: Inventory) -> set[str] | None:
    deps: set[str] = set()
    parsed = False
    text = inv.read("pyproject.toml")
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
        req_text = inv.read(req)
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
    if lockfile in ("poetry.lock", "uv.lock"):
        return _toml_package_names(text) or None
    if lockfile == "Pipfile.lock":
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


def _cargo_manifest_deps(inv: Inventory) -> set[str] | None:
    text = inv.read("Cargo.toml")
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


def _go_manifest_deps(inv: Inventory) -> set[str] | None:
    text = inv.read("go.mod")
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


def _manifest_deps(inv: Inventory, ecosystem: str) -> set[str] | None:
    if ecosystem == "node":
        return _node_manifest_deps(inv)
    if ecosystem == "python":
        return _python_manifest_deps(inv)
    if ecosystem == "rust":
        return _cargo_manifest_deps(inv)
    if ecosystem == "go":
        return _go_manifest_deps(inv)
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
    return None


def _lockfile_paths(inv: Inventory, ecosystem: str) -> list[str]:
    """Every lockfile of the ecosystem, at any depth, as the path git would track it; the shallowest first."""
    names = _lockfiles_for(ecosystem)
    found = (rel for rel in inv.paths() if rel.split("/")[-1] in names)
    return sorted(found, key=lambda rel: (rel.count("/"), rel))


def _lock_consistency(inv: Inventory, ecosystem: str, lockfile: str) -> tuple[str, set[str]]:
    """Return ``(state, extras)`` where state is ok | mismatch | unverified.

    The manifest read is the root one, so only a lockfile at the root is compared with it; one in a
    subdirectory is ``unverified``.
    """
    if "/" in lockfile:
        return "unverified", set()
    manifest = _manifest_deps(inv, ecosystem)
    lock = _lock_deps(inv, ecosystem, lockfile)
    if manifest is None or lock is None:
        return "unverified", set()
    if not manifest:
        return "ok", set()
    if not lock:
        return "unverified", set()
    extras = manifest - lock
    return ("mismatch", extras) if extras else ("ok", set())


def check_exec02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    ecosystems = sorted((stack.ecosystems - stack.source_only) & set(_ECOSYSTEM_MANAGERS))
    if not ecosystems:
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
    for ecosystem in ecosystems:
        candidates = _lockfile_paths(inventory, ecosystem)
        tracked_candidates = [rel for rel in candidates if rel in tracked]
        if not candidates:
            findings.append(
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "install identical dependencies on every run",
                        f"the {ecosystem} project has no lockfile "
                        f"({', '.join(_lockfiles_for(ecosystem))}), so a fresh install resolves "
                        f"whatever versions are current",
                    ),
                    remediation="Generate the lockfile with the project's package manager and commit it.",
                    path=ecosystem,
                )
            )
            continue
        if not tracked_candidates:
            findings.append(
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "install identical dependencies on every run",
                        f"{', '.join(sorted(candidates))} exists but is not tracked, so a fresh "
                        f"checkout does not get it",
                    ),
                    evidence=[Evidence(p) for p in sorted(candidates)],
                    remediation="Commit the lockfile; add it to .gitignore only if the team has "
                    "deliberately chosen floating dependencies.",
                    path=sorted(candidates)[0],
                )
            )
            continue
        lockfile = tracked_candidates[0]
        state, extras = _lock_consistency(inventory, ecosystem, lockfile)
        if state == "mismatch":
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
        else:
            verified.append(lockfile)

    if findings:
        verdict = Verdict.FAIL
    elif unverified:
        verdict = Verdict.PARTIAL
    else:
        verdict = Verdict.PASS
    detail = "; ".join(
        filter(
            None,
            [
                f"tracked: {', '.join(verified)}" if verified else "",
                f"consistency unverified: {', '.join(unverified)}" if unverified else "",
            ],
        )
    )
    return _outcome(spec, verdict, detail, findings)


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
_DOC_FILES = ("README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md")
_SETUP_TARGETS = ("setup", "bootstrap", "install", "dev", "dev-setup")


def _setup_signals(inv: Inventory) -> list[str]:
    signals = [name for name in _SETUP_FILES if inv.has(name)]
    signals += inv.match(".devcontainer/*.json")

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
    for name in _DOC_FILES:
        text = inv.read(name)
        if not text:
            continue
        for _lang, _line, command in extract_fenced_commands(text):
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

    doc_text = "\n".join(filter(None, (inventory.read(n) for n in _DOC_FILES)))
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
_SHELL_ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Za-z0-9_]*)\}")

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
)
_ENV_EXAMPLE_FILES = (".env.example", ".env.sample", ".env.template", "env.example")


def _is_shell_env_file(rel: str) -> bool:
    return rel.endswith(_SHELL_ENV_SUFFIXES) or rel.rsplit("/", 1)[-1] in _SHELL_ENV_BASENAMES


def _referenced_env_keys(inv: Inventory) -> set[str]:
    keys: set[str] = set()
    for path in inv.paths():
        if not _is_shell_env_file(path):
            continue
        text = inv.read(path)
        if text:
            referenced_here = {m.group(1) for m in _SHELL_ENV_PATTERN.finditer(text)}
            assigned_here = {m.group(1) for m in _SHELL_ASSIGN_PATTERN.finditer(text)}
            keys |= referenced_here - assigned_here
    for pattern in _CODE_ENV_PATTERNS:
        for _rel, _line, text in inv.grep(pattern, kinds=(Kind.SOURCE, Kind.SCRIPT), limit=2000):
            keys |= {m.group(1) for m in pattern.finditer(text) if m.group(1)}
    return keys


def _declared_env_keys(inv: Inventory) -> tuple[set[str], list[str]]:
    keys: set[str] = set()
    files: list[str] = []
    for name in _ENV_EXAMPLE_FILES:
        text = inv.read(name)
        if text is None:
            continue
        files.append(name)
        for line in text.splitlines():
            match = re.match(r"^\s*(?:export\s+)?#?\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
            if match:
                keys.add(match.group(1))
    return keys, files


def _env_allowed(key: str) -> bool:
    return key in _ENV_ALLOWLIST or key.startswith(_ENV_ALLOW_PREFIXES)


def check_exec04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    referenced = _referenced_env_keys(inventory)
    declared, files = _declared_env_keys(inventory)
    missing = sorted(k for k in referenced - declared if not _env_allowed(k))
    keys = EnvKeys(referenced=tuple(sorted(referenced)), missing=tuple(missing), templates=tuple(files))

    if not missing:
        detail = f"{len(referenced)} referenced key(s) declared" if referenced else "no environment keys referenced"
        return _outcome(spec, Verdict.PASS, detail, data=keys)

    because = (
        f"{len(missing)} referenced key(s) are absent from "
        f"{', '.join(files) if files else 'any committed example file'}: "
        f"{', '.join(missing[:12])}"
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


def check_exec05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    tracked = tracked_in_scope(target, inventory)
    if tracked is None:
        return _unknown(spec, "git could not report tracked files, so generated-file state is unknown")

    generated = sorted(f.rel for f in inventory.files if f.kind is Kind.GENERATED and f.rel in tracked)
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
    doc_paths = ["README.md", "AGENTS.md", "CLAUDE.md"]

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
