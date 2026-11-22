# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The next step of the implement recipe, worked out from the state alone."""

from __future__ import annotations

from typing import Any, Mapping

import validate_report
from _progress_state import _finding_order
from _progress_themes import CHECK_THEME, THEME_IDS, THEME_PREDECESSORS


#: The preference Stage 1 (triage) of implement/SKILL.md always records, so a state that holds it has been triaged.
TRIAGE_KEY = "ci.pr_by_agent"
OPEN_THEME = ("branch_open", "pr_open")
LEFT = ("queued", "in_progress")


def theme_ancestors(theme: str) -> list[str]:
    """Every theme `theme` waits for in the diagram, directly or through another theme, in the order of THEMES."""
    found: set[str] = set()
    todo = list(THEME_PREDECESSORS[theme])
    while todo:
        earlier = todo.pop()
        if earlier not in found:
            found.add(earlier)
            todo.extend(THEME_PREDECESSORS[earlier])
    return [candidate for candidate in THEME_IDS if candidate in found]


def playbook_themes() -> dict[str, str]:
    """Each playbook's theme: the theme of THEMES that owns most of the checks the catalogue lists the playbook for."""
    tally: dict[str, dict[str, int]] = {}
    for check in validate_report.load_catalogue()["checks"]:
        for playbook in check.get("playbooks", []):
            counts = tally.setdefault(playbook, {})
            theme = CHECK_THEME[check["id"]]
            counts[theme] = counts.get(theme, 0) + 1
    return {
        playbook: max(THEME_IDS, key=lambda theme: (counts.get(theme, 0), -THEME_IDS.index(theme)))
        for playbook, counts in tally.items()
    }


def cross_theme_checks() -> dict[str, str]:
    """The checks a playbook of another theme closes (implement/SKILL.md, "Themes"), each with the theme that works it.

    A check is one when none of the playbooks the catalogue lists for it belongs to the check's own theme. Its item is
    worked in the theme of its first playbook, and is left out of both tests of :func:`next_theme`.
    """
    owners = playbook_themes()
    crossing: dict[str, str] = {}
    for check in validate_report.load_catalogue()["checks"]:
        homes = [owners[playbook] for playbook in check.get("playbooks", [])]
        if homes and CHECK_THEME[check["id"]] not in homes:
            crossing[check["id"]] = homes[0]
    return crossing


def next_theme(state: dict[str, Any], crossing: Mapping[str, str]) -> str | None:
    """The theme Stage 2, step 2 of implement/SKILL.md picks, or None when no theme can start.

    It is the first `not_started` theme, in the order of THEMES, that has `queued` items its own playbooks work, and
    whose every earlier theme in the diagram is `merged`, or is `not_started` with nothing left for its own playbooks
    (no item `queued` or `in_progress`). A theme shown as `branch_open` or `pr_open` holds back the themes after it.
    Items worked by another theme's playbook (`crossing`) count for neither test.
    """
    status = {theme["id"]: theme["status"] for theme in state["themes"]}
    own: dict[str, list[str]] = {theme: [] for theme in THEME_IDS}
    for item in state["items"]:
        if item["check"] not in crossing:
            own[item["theme"]].append(item["status"])

    def satisfied(theme: str) -> bool:
        return status[theme] == "merged" or (
            status[theme] == "not_started" and not any(left in LEFT for left in own[theme])
        )

    for theme in THEME_IDS:
        if status[theme] != "not_started" or "queued" not in own[theme]:
            continue
        if all(satisfied(earlier) for earlier in theme_ancestors(theme)):
            return theme
    return None


def next_step(state: dict[str, Any]) -> dict[str, Any]:
    """The stage and step of implement/SKILL.md a session goes on with, from the state alone.

    The first rule that holds decides: an item left `in_progress` is resumed (Stage 3, step 4, and "Resuming"); a state
    with no theme started and no `ci.pr_by_agent` preference has not been triaged (Stage 1); a `branch_open` theme with
    `queued` items of its own goes on (Stage 3, step 4); a theme shown as `branch_open` or `pr_open` is checked for its
    merge first (Stage 2, step 1); a theme :func:`next_theme` picks is planned (Stage 2, step 2); otherwise the run closes
    out (Stage 5). `theme` is the theme the step works on, and `check_first` lists the themes Stage 2, step 1 checks.
    """
    crossing = cross_theme_checks()
    items = state["items"]
    themes = sorted(state["themes"], key=lambda entry: entry["id"])
    check_first = [theme["id"] for theme in themes if theme["status"] in OPEN_THEME]
    picked = next_theme(state, crossing)

    def step(stage: int, number: int, text: str, theme: str | None) -> dict[str, Any]:
        return {"stage": stage, "step": number, "text": text, "theme": theme, "check_first": check_first}

    working = sorted(
        (item for item in items if item["status"] == "in_progress"), key=lambda i: _finding_order(i["finding"])
    )
    if working:
        item = working[0]
        home = crossing.get(item["check"], item["theme"])
        return step(
            3,
            4,
            f"Stage 3, step 4: resume {item['finding']} ({home}) on its theme's branch; read the branch's git log "
            "first, so nothing is committed twice.",
            home,
        )
    triaged = any(pref["key"] == TRIAGE_KEY for pref in state["preferences"])
    if not triaged and all(theme["status"] == "not_started" for theme in themes):
        return step(
            1,
            1,
            f"Stage 1, step 1: triage; no theme has started and the {TRIAGE_KEY} preference is not recorded.",
            None,
        )
    for theme in themes:
        mine = [item for item in items if item["theme"] == theme["id"] and item["check"] not in crossing] + [
            item for item in items if crossing.get(item["check"]) == theme["id"]
        ]
        if theme["status"] == "branch_open" and any(item["status"] == "queued" for item in mine):
            return step(
                3, 4, f"Stage 3, step 4: go on with the next queued item of {theme['id']} on its branch.", theme["id"]
            )
    if check_first:
        shown = ", ".join(f"{theme['id']} ({theme['status']})" for theme in themes if theme["id"] in check_first)
        then = f"then {picked} is next" if picked else "no other theme can start until they merge"
        return step(2, 1, f"Stage 2, step 1: check whether {shown} merged, and record each merge; {then}.", picked)
    if picked:
        return step(2, 2, f"Stage 2, step 2: plan {picked}, the next theme.", picked)
    left = sorted((item["finding"] for item in items if item["status"] == "queued"), key=_finding_order)
    if left:
        return step(
            5,
            1,
            f"Stage 5, step 1: close out; no theme is left to start, and no theme works the queued {' '.join(left)}.",
            None,
        )
    return step(5, 1, "Stage 5, step 1: close out; no item is queued and no theme is open.", None)
