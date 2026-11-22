# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""EXEC-02: Lockfile committed and consistent."""

from __future__ import annotations

import json
import re
from collections.abc import Collection

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import tracked_in_scope
from audit.scan import Inventory
from audit.stack import PACKAGE_MANAGERS
from audit.rules.checks.execution._shared import _outcome, _unknown

SPEC = declare("EXEC-02", "Lockfile committed and consistent", "B", Severity.BLOCKER)


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
