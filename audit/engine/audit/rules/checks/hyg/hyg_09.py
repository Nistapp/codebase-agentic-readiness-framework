# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-09: Dependency update automation configured."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import _indent
from audit.stack import Stack
from audit.rules.checks.hyg._shared import _basename, _finding, _outcome, _present

SPEC = declare("HYG-09", "Dependency update automation configured", "A", Severity.COSMETIC, scored=False)


_DEPENDENCY_AUTOMATION = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    "dependabot.yml",
    "dependabot.yaml",
    "renovate.json",
    "renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".github/renovate.json",
    "renovate.config.js",
)
_RENOVATE_UNPARSED = frozenset({"renovate.json5", "renovate.config.js"})

#: Stack ecosystem (or ``github`` for the CI provider) -> the Dependabot ``package-ecosystem`` values that cover it.
_DEPENDABOT_ECOSYSTEMS: dict[str, tuple[str, ...]] = {
    "node": ("npm", "bun"),
    "python": ("pip", "uv"),
    "jvm": ("maven", "gradle"),
    "go": ("gomod",),
    "rust": ("cargo",),
    "dotnet": ("nuget",),
    "ruby": ("bundler",),
    "php": ("composer",),
    "github": ("github-actions",),
}

#: The same, as Renovate manager names for ``enabledManagers``.
_RENOVATE_MANAGERS: dict[str, tuple[str, ...]] = {
    "node": ("npm", "bun"),
    "python": ("pep621", "pip_requirements", "pip_setup", "pip-compile", "pipenv", "poetry", "setuptools"),
    "jvm": ("maven", "gradle"),
    "go": ("gomod",),
    "rust": ("cargo",),
    "dotnet": ("nuget",),
    "ruby": ("bundler",),
    "php": ("composer",),
    "github": ("github-actions",),
}

#: The Dependabot entry options that the owner expects to bind security updates, and that ``target-branch`` drops.
_TRAPPED_OPTIONS = frozenset({"ignore", "groups"})


# ===========================================================================
# HYG-09 — dependency update automation
# ===========================================================================


@dataclass
class _UpdateEntry:
    """One item of a Dependabot ``updates:`` list: its ecosystem, its option keys and their line numbers."""

    line: int
    ecosystem: str | None = None
    keys: dict[str, int] = field(default_factory=dict)


@dataclass
class _AutomationConfig:
    """What one dependency-update file tells the check. ``covers`` is ``None`` when it covers every ecosystem."""

    path: str
    readable: bool = True
    covers: set[str] | None = None
    traps: list[_UpdateEntry] = field(default_factory=list)


def _scalar(value: str) -> str:
    value = re.sub(r"\s+#.*$", "", value).strip()
    return value.strip("\"'")


def _dependabot_entries(text: str) -> list[_UpdateEntry] | None:
    """Minimal reader for the ``updates:`` list of a Dependabot file; ``None`` when there is no such list.

    No YAML library is available (stdlib only), so this understands block style: ``- key: value`` items and
    their sibling keys. Anchors, flow-style items and multi-document files are not interpreted.
    """
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if re.match(r"^updates:\s*(#.*)?$", line))
    except StopIteration:
        return None
    entries: list[_UpdateEntry] = []
    item_indent: int | None = None
    key_indent = 0
    for number, line in enumerate(lines[start + 1 :], start=start + 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = _indent(line)
        stripped = line.strip()
        if stripped.startswith("- ") and (item_indent is None or indent == item_indent):
            item_indent = indent
            key_indent = indent + 2
            entries.append(_UpdateEntry(line=number))
            stripped = stripped[2:].strip()
            indent = key_indent
        elif item_indent is None or indent <= item_indent:
            break
        key = re.match(r"^([A-Za-z0-9_-]+):(.*)$", stripped)
        if entries and key and indent == key_indent:
            name, value = key.group(1), key.group(2)
            entries[-1].keys.setdefault(name, number)
            if name == "package-ecosystem":
                entries[-1].ecosystem = _scalar(value)
    return entries


def _read_dependabot(rel: str, text: str | None) -> _AutomationConfig:
    entries = _dependabot_entries(text or "")
    if entries is None:
        return _AutomationConfig(rel, readable=False, covers=set())
    named = {entry.ecosystem for entry in entries if entry.ecosystem}
    covers = {eco for eco, accepted in _DEPENDABOT_ECOSYSTEMS.items() if named & set(accepted)}
    traps = [entry for entry in entries if "target-branch" in entry.keys and _TRAPPED_OPTIONS & set(entry.keys)]
    return _AutomationConfig(rel, covers=covers, traps=traps)


def _read_renovate(rel: str, text: str | None) -> _AutomationConfig:
    if _basename(rel) in _RENOVATE_UNPARSED:
        return _AutomationConfig(rel)
    try:
        config = json.loads(text or "")
    except ValueError:
        return _AutomationConfig(rel, readable=False, covers=set())
    if not isinstance(config, dict):
        return _AutomationConfig(rel, readable=False, covers=set())
    enabled = config.get("enabledManagers")
    if not isinstance(enabled, list):
        return _AutomationConfig(rel)
    names = {str(name) for name in enabled}
    return _AutomationConfig(rel, covers={eco for eco, accepted in _RENOVATE_MANAGERS.items() if names & set(accepted)})


def _required_coverage(stack: Stack) -> set[str]:
    """The ecosystems a dependency-update policy must reach: those a manifest names, plus GitHub Actions."""
    required = {eco for eco in stack.ecosystems - stack.source_only if eco in _DEPENDABOT_ECOSYSTEMS}
    if "github" in stack.ci_providers:
        required.add("github")
    return required


def _coverage_label(eco: str) -> str:
    return "github-actions" if eco == "github" else eco


def check_hyg09(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _present(inventory, *_DEPENDENCY_AUTOMATION)
    if not found:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no dependency update automation",
            [
                _finding(
                    spec,
                    Verdict.FAIL,
                    "keep dependencies patched without manual sweeps",
                    "no Dependabot or Renovate configuration exists",
                    remediation="Add .github/dependabot.yml (or renovate.json) with an update schedule.",
                ),
            ],
        )

    configs = [
        _read_renovate(rel, inventory.read(rel)) if "renovate" in rel else _read_dependabot(rel, inventory.read(rel))
        for rel in found
    ]
    required = _required_coverage(stack)
    covered: set[str] = set()
    for config in configs:
        covered |= required if config.covers is None else config.covers
    missing = sorted(required - covered)
    unreadable = [config.path for config in configs if not config.readable]

    findings = [
        _finding(
            spec,
            Verdict.PARTIAL,
            "rely on the update policy reaching security updates",
            f"the `{entry.ecosystem or 'unnamed'}` entry sets `target-branch` together with "
            f"`{'`, `'.join(sorted(_TRAPPED_OPTIONS & set(entry.keys)))}`, and Dependabot drops those options for "
            "security updates, which always go to the default branch",
            evidence=[Evidence(config.path, line=entry.keys["target-branch"], note="target-branch")],
            path=f"{config.path}:{entry.keys['target-branch']}",
            remediation="Remove `target-branch` when it names the default branch; otherwise make that branch the "
            "default, so the entry's options apply to security updates too.",
        )
        for config in configs
        for entry in config.traps
    ]
    if missing and not unreadable:
        labels = ", ".join(_coverage_label(eco) for eco in missing)
        accepted = "; ".join(f"{_coverage_label(eco)}: {' or '.join(_DEPENDABOT_ECOSYSTEMS[eco])}" for eco in missing)
        findings.append(
            _finding(
                spec,
                Verdict.PARTIAL,
                "keep every ecosystem's dependencies under the update policy",
                f"the dependency-update configuration has no entry for {labels}",
                evidence=[Evidence(config.path) for config in configs],
                path=configs[0].path,
                remediation=f"Add an update entry for each detected ecosystem (Dependabot `package-ecosystem` "
                f"{accepted}), or the matching Renovate manager to `enabledManagers`.",
            )
        )
    if findings:
        return _outcome(
            spec, Verdict.PARTIAL, f"dependency automation at {found[0]} has {len(findings)} defect(s)", findings
        )
    if missing or len(unreadable) == len(configs):
        return _outcome(
            spec,
            Verdict.UNKNOWN,
            f"dependency automation at {', '.join(unreadable)} could not be read; coverage is not settled",
        )
    reach = ", ".join(_coverage_label(eco) for eco in sorted(required)) or "no ecosystem with a manifest"
    return _outcome(spec, Verdict.PASS, f"dependency automation configured at {found[0]}; covers {reach}")


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.checks import hyg
    from audit.rules.reads import REPOSITORY_LEVEL, Reads, What, _held

    return Reads(
        where=(*_held(hyg, "_DEPENDENCY_AUTOMATION", REPOSITORY_LEVEL),),
        what=What("key"),
        binding="file",
        note=(
            "Dependabot: the package-ecosystem of each updates item, and target-branch with ignore or groups "
            "is a defect; Renovate JSON: enabledManagers. Each detected ecosystem, plus github-actions with "
            "GitHub CI, must be covered."
        ),
    )
