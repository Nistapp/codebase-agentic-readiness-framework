# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""EXEC-01: Toolchain pinned / wrapper committed."""

from __future__ import annotations

import json
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.checks.execution._shared import _outcome, _unknown

SPEC = declare("EXEC-01", "Toolchain pinned / wrapper committed", "A", Severity.BLOCKER)


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


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, Reads, What, _at

    return Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".nvmrc",
                ".node-version",
                ".python-version",
                "gradlew",
                "mvnw",
                "global.json",
                "rust-toolchain.toml",
                "rust-toolchain",
                ".ruby-version",
                ".php-version",
                ".tool-versions",
                "package.json",
                "pyproject.toml",
                "go.mod",
                "composer.json",
            ),
        ),
        what=What("exists"),
        binding="file",
        threshold="every ecosystem pinned and every module reached",
        note=(
            "Pin files count by existence; .tool-versions needs a line for the ecosystem (java for jvm), package.json "
            "engines.node, pyproject.toml requires-python, go.mod a go directive and composer.json "
            "config.platform.php or require.php. A module manifest no pin"
            " reaches (its folder or a parent) is PARTIAL; a parent go.mod or composer.json does not reach a"
            " nested one."
        ),
    )
