# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one AGT check uses."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Verdict
from audit import globs
from audit.scan import Inventory
from audit.rules import variants as V


#: All basenames that could be an instruction file in any folder, derived from the variant table: the canonical file,
#: the aliases, the overrides and each harness path with no folder and no wildcard.
def _instruction_basenames() -> set[str]:
    names: set[str] = set(V.CANONICAL_PATHS) | set(V.NON_CANONICAL_ALIASES) | set(V.OVERRIDE_PATHS)
    for harness in V.HARNESSES:
        for pattern in harness.paths:
            if "*" not in pattern and "/" not in pattern:
                names.add(pattern)
    return names


INSTRUCTION_BASENAMES = _instruction_basenames()


#: Harness paths with a folder and no wildcard (`.github/copilot-instructions.md`). The table's paths are relative to
#: the repository root, so each one is matched as the whole path from the root; a base name holds no folder.
def _instruction_fixed_paths() -> set[str]:
    return {pattern for harness in V.HARNESSES for pattern in harness.paths if "*" not in pattern and "/" in pattern}


INSTRUCTION_FIXED_PATHS = _instruction_fixed_paths()


#: Basenames and fixed paths that only config-gated harnesses claim, with the config files that would load them.
#: Without one of those configs the file is an ordinary document: a `CONVENTIONS.md` with no `.aider.conf.yml` is a
#: style guide.
def _config_gated_names() -> dict[str, tuple[str, ...]]:
    gated: dict[str, tuple[str, ...]] = {}
    for name in INSTRUCTION_BASENAMES | INSTRUCTION_FIXED_PATHS:
        owners = [h for h in V.HARNESSES if name in h.paths]
        claimed_elsewhere = name in V.CANONICAL_PATHS or name in V.NON_CANONICAL_ALIASES or name in V.OVERRIDE_PATHS
        if owners and not claimed_elsewhere and all(h.paths_need_config for h in owners):
            gated[name] = tuple(sorted({c for h in owners for c in h.config}))
    return gated


CONFIG_GATED_NAMES = _config_gated_names()


def is_non_instruction(rel: str) -> bool:
    return any(globs.glob_match(glob, rel, fold_case=True) for glob, _why in V.NON_INSTRUCTION_GLOBS)


def instruction_paths(inv: Inventory) -> set[str]:
    """Every path in the target that is plausibly an agent-instruction file.

    Excludes skill definitions, run state and harness config, which is what keeps this check from
    failing on every repository that happens to contain a `.opencode/` directory.
    """
    found: set[str] = set()
    for rel in inv.paths():
        if is_non_instruction(rel):
            continue
        base = rel.rsplit("/", 1)[-1]
        name = rel if rel in INSTRUCTION_FIXED_PATHS else base if base in INSTRUCTION_BASENAMES else None
        if name is not None:
            configs = CONFIG_GATED_NAMES.get(name)
            if configs is None or any(inv.has(config) for config in configs):
                found.add(rel)
            continue
        # A glob from the root, folder by folder: `**/` also matches no folder, so a file straight in a rules
        # folder (`.cursor/rules/a.mdc`) counts, as in `variants._matches`.
        for harness in V.HARNESSES:
            for pattern in harness.paths:
                if "*" in pattern and globs.glob_match(pattern, rel, fold_case=True):
                    found.add(rel)
    return found


def _rule_line_count(text: str) -> int:
    """Count lines that look like rules rather than headings, blanks or prose-only links."""
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(">"):
            continue
        if stripped.startswith("|") and set(stripped) <= set("|-: "):
            continue
        count += 1
    return count


# ---------------------------------------------------------------------------
# Shared readers for the content-contract checks (AGT-03, 04, 06, 07, 09)
# ---------------------------------------------------------------------------


def _unknown(spec, reason: str) -> CheckOutcome:
    return CheckOutcome(
        spec.id, spec.title, spec.tier, spec.severity, spec.phase, Verdict.UNKNOWN, spec.status, summary=reason
    )


def _first_line(text: str, pattern: re.Pattern) -> int | None:
    for no, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            return no
    return None


_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_MD_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
