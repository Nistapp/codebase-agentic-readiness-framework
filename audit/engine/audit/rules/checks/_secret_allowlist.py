# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The allowlists a repository's own secret scanners keep, read for ``SEC-02``.

Three files are read, from the repository root only:

* ``.secrets.baseline`` (detect-secrets): ``results[<path>] -> [{line_number, ...}]``. A hit is allowlisted
  when its path **and** line number are listed, so a stale entry for a file never hides a new hit on
  another line of it. The ``hashed_secret`` is not recomputed: the engine never holds the secret value.
* ``.gitleaksignore``: one ``<file>:<rule>:<line>`` (or ``<commit>:<file>:<rule>:<line>``) fingerprint per
  line, ``#`` comments skipped. Matched on path and line.
* ``.gitleaks.toml``: ``[allowlist]`` and ``[[allowlists]]`` ``paths`` (regular expressions searched in the
  path) and ``regexes`` (searched in the line, which is wider than the secret gitleaks matches).

Standard library only. A file that does not parse allowlists nothing: absence of evidence is not credit.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field

from audit.scan import Inventory


@dataclass
class SecretAllowlist:
    """Which credential-shaped lines the repository has already accepted, and where it said so."""

    baseline_lines: dict[str, set[int]] = field(default_factory=dict)
    ignore_lines: dict[str, set[int]] = field(default_factory=dict)
    toml_paths: list[re.Pattern[str]] = field(default_factory=list)
    toml_regexes: list[re.Pattern[str]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def covering_source(self, rel: str, line_no: int, line: str) -> str | None:
        """The allowlist file that accepts this hit, or ``None``."""
        if line_no in self.baseline_lines.get(rel, ()):
            return ".secrets.baseline"
        if line_no in self.ignore_lines.get(rel, ()):
            return ".gitleaksignore"
        if any(p.search(rel) for p in self.toml_paths) or any(r.search(line) for r in self.toml_regexes):
            return ".gitleaks.toml"
        return None


def _norm(path: str) -> str:
    path = path.replace("\\", "/")
    return path[2:] if path.startswith("./") else path


def _baseline(text: str) -> dict[str, set[int]]:
    try:
        results = json.loads(text).get("results")
    except (json.JSONDecodeError, AttributeError):
        return {}
    out: dict[str, set[int]] = {}
    if not isinstance(results, dict):
        return out
    for path, entries in results.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            number = entry.get("line_number") if isinstance(entry, dict) else None
            if isinstance(number, int):
                out.setdefault(_norm(path), set()).add(number)
    return out


def _gitleaksignore(text: str) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) not in (3, 4) or not parts[-1].isdigit():
            continue
        out.setdefault(_norm(parts[-3]), set()).add(int(parts[-1]))
    return out


def _compile(patterns: object) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns if isinstance(patterns, list) else []:
        if isinstance(pattern, str):
            try:
                compiled.append(re.compile(pattern))
            except re.error:
                continue
    return compiled


def _toml(text: str) -> tuple[list[re.Pattern[str]], list[re.Pattern[str]]]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return [], []
    tables = []
    if isinstance(data.get("allowlist"), dict):
        tables.append(data["allowlist"])
    if isinstance(data.get("allowlists"), list):
        tables.extend(t for t in data["allowlists"] if isinstance(t, dict))
    paths: list[re.Pattern[str]] = []
    regexes: list[re.Pattern[str]] = []
    for table in tables:
        paths += _compile(table.get("paths"))
        regexes += _compile(table.get("regexes"))
    return paths, regexes


def load_secret_allowlist(inventory: Inventory) -> SecretAllowlist:
    """Read every allowlist file that exists at the repository root; empty when there is none."""
    allow = SecretAllowlist()
    if text := inventory.read(".secrets.baseline"):
        allow.baseline_lines = _baseline(text)
        if allow.baseline_lines:
            allow.sources.append(".secrets.baseline")
    if text := inventory.read(".gitleaksignore"):
        allow.ignore_lines = _gitleaksignore(text)
        if allow.ignore_lines:
            allow.sources.append(".gitleaksignore")
    if text := inventory.read(".gitleaks.toml"):
        allow.toml_paths, allow.toml_regexes = _toml(text)
        if allow.toml_paths or allow.toml_regexes:
            allow.sources.append(".gitleaks.toml")
    return allow
