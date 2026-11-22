# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""EXEC-07: No competing configs for one concern."""

from __future__ import annotations

import fnmatch
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import follow_makefile, resolve_verbs
from audit.scan import Inventory
from audit.rules.checks.execution._shared import _outcome

SPEC = declare("EXEC-07", "No competing configs for one concern", "B", Severity.DEGRADER)


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
