# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The themes of the implement recipe and the checks each owns: one place for the table and the diagram's edges."""

from __future__ import annotations

from typing import Sequence


def _span(prefix: str, first: int, last: int, *, skip: Sequence[int] = ()) -> tuple[str, ...]:
    return tuple(f"{prefix}-{number:02d}" for number in range(first, last + 1) if number not in skip)


# The themes, in dependency order, and the checks each one owns. Every check in catalogue.json has exactly one theme;
# a test holds the two together. CON-04 (unscored, no playbook) sits with CON-01..03: add-deny-rules reads its draft.
THEMES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("T1", "Command surface and quality tools", _span("CMD", 1, 4) + _span("TOOL", 1, 4)),
    ("T2", "Execution determinism", _span("EXEC", 1, 8, skip=(4,))),
    ("T3", "Secrets and environment variables", _span("SEC", 1, 3) + ("EXEC-04",)),
    ("T4", "CI parity, Git hooks and commit messages", _span("CI", 1, 5) + ("TOOL-05", "TOOL-06", "TOOL-07")),
    ("T5", "Tests and baselines", _span("TST", 1, 5) + _span("BASE", 1, 4)),
    ("T6", "Docs and navigation", _span("DOC", 1, 5) + _span("NAV", 1, 5)),
    ("T7", "AGENTS.md and governance", _span("AGT", 1, 13) + _span("CON", 1, 4)),
    ("T8", "Hygiene and index", _span("HYG", 1, 13, skip=(12,)) + _span("IDX", 1, 3)),
)
CHECK_THEME: dict[str, str] = {check: theme for theme, _, checks in THEMES for check in checks}
THEME_IDS = tuple(theme for theme, _, _ in THEMES)
# The edges of the theme diagram in implement/SKILL.md ("Themes"): each theme and the themes it waits for. THEMES is
# in an order the diagram allows. A test holds this map, that order and the diagram together.
THEME_PREDECESSORS: dict[str, tuple[str, ...]] = {
    "T1": (),
    "T2": (),
    "T3": (),
    "T4": ("T1", "T2"),
    "T5": ("T1", "T4"),
    "T6": (),
    "T7": ("T3", "T5", "T6"),
    "T8": ("T7",),
}
