# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Build the two reader-facing master lists from the recipe sources, or check that they are current.

    build_masters.py --check   exit 1 when a page differs from what the sources give (``make masters-check``)
    build_masters.py --write   rewrite both pages in place (``make update-masters``)

The pages are ``docs/reference/audit-master.md`` (every audit check, grouped by area and family) and
``docs/reference/implement-master.md`` (every playbook, grouped by theme). Their sources:

- ``audit/catalogue.json``: each check's id, title, severity, scoring, method and playbooks.
- ``audit/checks/NN-*.md``: each family's name (the H1) and each check's ``Why it matters`` and rubric ``PASS``.
- ``implement/playbooks/README.md``: each playbook's theme (the "Playbook list" table).
- ``implement/playbooks/<name>.md``: each playbook's ``Goal``, ``Checks resolved`` and ``Do-not-do`` sections.

A page is never edited by hand. ``make check`` runs ``--check``, so a change to a source that leaves a page stale
fails the gate, in CI too. Links copied from a source are rewritten relative to ``docs/reference/``;
``recipe_lint.py`` then checks that every link and anchor resolves. Exit 2 when a source is malformed (a family
with no area, a check with no section, a playbook with no theme). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path("docs/reference")
AUDIT_PAGE = OUT_DIR / "audit-master.md"
IMPLEMENT_PAGE = OUT_DIR / "implement-master.md"
CATALOGUE = Path("audit/catalogue.json")
CHECKS_DIR = Path("audit/checks")
PLAYBOOKS_DIR = Path("implement/playbooks")

# The reader's grouping of the check families. Every family in the catalogue must appear here exactly once; a new
# family fails the build until it is placed.
AREAS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "Agent context",
        "Can an agent find the code, the rules and the documents it needs before it edits anything?",
        ("IDX", "AGT", "DOC", "NAV"),
    ),
    (
        "Command surface and quality gates",
        "Can an agent run one command that formats, lints, type-checks and tests, and trust its answer?",
        ("CMD", "TOOL", "TST", "BASE"),
    ),
    (
        "Enforcement in CI",
        "Does the pipeline run the same gate the agent runs locally, and does it block the merge?",
        ("CI",),
    ),
    (
        "Reproducible execution",
        "Does the same command give the same result on a fresh machine, without a human in the loop?",
        ("EXEC",),
    ),
    (
        "Safety boundaries and secrets",
        "Is it written down, and enforced, what an agent must never touch or reveal?",
        ("CON", "SEC"),
    ),
    (
        "Team hygiene (informational)",
        "Is the repository run like a team project? Reported for the whole picture; never scored.",
        ("HYG",),
    ),
)

SEVERITY_ORDER = ("BLOCKER", "DEGRADER", "COSMETIC")
WIDTH = 120  # markdownlint's MD013 line length for prose (.markdownlint-cli2.jsonc)
METHOD_LABEL = {"automated": "engine check", "agent": "agent judgement"}

_LINK = re.compile(r"(?<!!)(\[[^\]\n]*\])\(([^)\s]+)\)")
_EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://|^mailto:")
_FAMILY_H1 = re.compile(r"^# (.+?) \(`([A-Z]+)`\)", re.MULTILINE)
_CHECK_SECTION = re.compile(r"^## ([A-Z]+-[0-9]+) — .*?$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
_THEME_ROW = re.compile(r"^\| \[`([a-z0-9-]+)`\]\([a-z0-9-]+\.md\) \| (T[0-9]+) ([^|]+?) \|", re.MULTILINE)
_RESOLVED_ROW = re.compile(r"^\| ([A-Z]+-[0-9]+) \| [^|]+ \| (.+?) \|\s*$", re.MULTILINE)


class SourceError(Exception):
    """A source file lacks something a page needs."""


@dataclass(frozen=True)
class Check:
    id: str
    title: str
    family: str
    severity: str
    scored: bool
    method: str
    playbooks: tuple[str, ...]
    why: str
    passes: str


@dataclass(frozen=True)
class Playbook:
    name: str
    theme: str
    theme_name: str
    goal: str
    resolves: tuple[tuple[str, str], ...]
    never: str


# --- Reading the sources ------------------------------------------------------------------------------------


def rebase_links(text: str, source: Path) -> str:
    """Rewrite each relative link in ``text`` (written in ``source``) so it resolves from :data:`OUT_DIR`."""

    def fix(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2)
        if _EXTERNAL.match(target):
            return match.group(0)
        path_part, hash_mark, anchor = target.partition("#")
        # A same-page anchor in the source points at the source page, not at this one.
        resolved = source if path_part == "" else source.parent / path_part
        moved = os.path.relpath(os.path.normpath(resolved), OUT_DIR)
        return f"{label}({Path(moved).as_posix()}{hash_mark}{anchor})"

    return _LINK.sub(fix, text)


def section(text: str, heading: str) -> str:
    """The body of the ``## heading`` section of ``text``, stripped; empty when there is none."""
    found = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return found.group(1).strip() if found else ""


def field_text(body: str, name: str) -> str:
    """One fixed-anatomy field of a check section, its continuation lines joined into one line."""
    found = re.search(rf"^{re.escape(name)}\s+(.*?)(?=^\S|\Z)", body, re.MULTILINE | re.DOTALL)
    return " ".join(found.group(1).split()) if found else ""


def read_families(root: Path) -> tuple[dict[str, str], dict[str, tuple[Path, str]]]:
    """Each family's name, and each check's ``(file, section body)``, from the check files."""
    names: dict[str, str] = {}
    sections: dict[str, tuple[Path, str]] = {}
    for path in sorted((root / CHECKS_DIR).glob("[0-9][0-9]-*.md")):
        text = path.read_text(encoding="utf-8")
        h1 = _FAMILY_H1.search(text)
        if h1 is None:
            raise SourceError(f"{path.relative_to(root)}: no '# <name> (`<FAMILY>`)' heading")
        names[h1.group(2)] = h1.group(1)
        for found in _CHECK_SECTION.finditer(text):
            sections[found.group(1)] = (path.relative_to(root), found.group(2))
    return names, sections


def read_checks(root: Path) -> tuple[str, list[Check], dict[str, str]]:
    """The catalogue version, every check in catalogue order, and each family's name."""
    catalogue: dict[str, Any] = json.loads((root / CATALOGUE).read_text(encoding="utf-8"))
    names, sections = read_families(root)
    checks: list[Check] = []
    for entry in catalogue["checks"]:
        if entry["id"] not in sections:
            raise SourceError(f"{entry['id']} has no section in {CHECKS_DIR}/")
        path, body = sections[entry["id"]]
        rubric = field_text(body, "Rubric")
        passes = re.search(r"PASS:(.*?)(?=PARTIAL:|FAIL:|NOT_APPLICABLE:|UNKNOWN when:|\Z)", rubric)
        checks.append(
            Check(
                id=entry["id"],
                title=entry["title"],
                family=entry["family"],
                severity=entry["severity"],
                scored=bool(entry["scored"]),
                method=entry["method"],
                playbooks=tuple(entry["playbooks"]),
                why=rebase_links(field_text(body, "Why it matters"), path),
                passes=rebase_links(passes.group(1).strip() if passes else "", path),
            )
        )
    placed = [family for _, _, families in AREAS for family in families]
    unplaced = sorted({check.family for check in checks} - set(placed))
    if unplaced:
        raise SourceError(f"family {', '.join(unplaced)} has no area in build_masters.AREAS")
    missing = sorted({check.family for check in checks} - set(names))
    if missing:
        raise SourceError(f"family {', '.join(missing)} has no check file in {CHECKS_DIR}/")
    return str(catalogue["catalogue_version"]), checks, names


def read_playbooks(root: Path) -> list[Playbook]:
    """Every playbook, in the order of the playbook list in ``implement/playbooks/README.md``."""
    index = (root / PLAYBOOKS_DIR / "README.md").read_text(encoding="utf-8")
    rows = _THEME_ROW.findall(index)
    if not rows:
        raise SourceError(f"{PLAYBOOKS_DIR}/README.md: no playbook list rows")
    listed = {name for name, _, _ in rows}
    on_disk = {path.stem for path in (root / PLAYBOOKS_DIR).glob("*.md")} - {"README"}
    if listed != on_disk:
        raise SourceError(f"{PLAYBOOKS_DIR}/README.md lists {sorted(listed)}; the folder holds {sorted(on_disk)}")
    playbooks: list[Playbook] = []
    for name, theme, theme_name in rows:
        path = PLAYBOOKS_DIR / f"{name}.md"
        text = (root / path).read_text(encoding="utf-8")
        resolves = tuple(
            (check_id, rebase_links(what.strip(), path))
            for check_id, what in _RESOLVED_ROW.findall(section(text, "Checks resolved"))
        )
        goal = section(text, "Goal")
        if not goal or not resolves:
            raise SourceError(f"{path}: needs a Goal section and a Checks resolved table")
        playbooks.append(
            Playbook(
                name=name,
                theme=theme,
                theme_name=theme_name.strip(),
                goal=rebase_links(goal, path),
                resolves=resolves,
                never=rebase_links(section(text, "Do-not-do"), path),
            )
        )
    return playbooks


# --- Rendering ----------------------------------------------------------------------------------------------


def slug(heading: str) -> str:
    """GitHub's anchor for a heading (the same rule as ``recipe_lint.slugify``)."""
    return re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")


def wrap(text: str, first: str = "", rest: str = "") -> list[str]:
    """``text`` as prose lines of at most :data:`WIDTH` columns, never broken inside a word."""
    return textwrap.wrap(
        text, WIDTH, initial_indent=first, subsequent_indent=rest, break_long_words=False, break_on_hyphens=False
    )


def check_heading(check: Check) -> str:
    return f"`{check.id}` {check.title}"


def generated_note(sources: str) -> list[str]:
    return wrap(
        f"**Generated** by [`dev/build_masters.py`](../../dev/build_masters.py) from {sources}. Do not edit it by "
        "hand: change a source, then run `make update-masters`. `make check` fails when this page is stale.",
        "> ",
        "> ",
    )


def count_line(checks: Sequence[Check]) -> str:
    parts = [
        f"{sum(c.severity == s for c in checks)} {s}" for s in SEVERITY_ORDER if any(c.severity == s for c in checks)
    ]
    return ", ".join(parts)


def render_audit(version: str, checks: Sequence[Check], names: dict[str, str]) -> str:
    by_family: dict[str, list[Check]] = {}
    for check in checks:
        by_family.setdefault(check.family, []).append(check)
    scored = sum(c.scored for c in checks)
    agent = sum(c.method == "agent" for c in checks)
    out: list[str] = [
        "# Audit master list",
        "",
        "> **Audience:** CTOs, senior engineers and anyone who wants to know what an audit looks at.",
        "> **Source of truth:** [`catalogue.json`](../../audit/catalogue.json) and the check files in",
        "> [`audit/checks/`](../../audit/checks/README.md).",
        ">",
        *generated_note("the catalogue and the check files"),
        "",
        "---",
        "",
        *wrap(
            f"The audit runs **{len(checks)} checks** in {len(by_family)} families (catalogue {version}). "
            f"{scored} are scored; the rest are reported for the whole picture and earn no credit. "
            f"The engine decides {len(checks) - agent} checks from the files alone; the agent judges {agent}. "
            "Each check below says what passes and why it matters. To fix a finding, follow the playbook it names "
            "in the [implement master list](implement-master.md)."
        ),
        "",
        "| Severity | Meaning |",
        "|---|---|",
        "| `BLOCKER` | An agent cannot work safely until this is fixed |",
        "| `DEGRADER` | An agent can work, but slower, with more mistakes or with less trust in its result |",
        "| `COSMETIC` | Worth fixing; it does not change what an agent can do |",
        "",
        "## At a glance",
        "",
        "| Area | The question it answers | Families | Checks |",
        "|---|---|---|---|",
    ]
    for area, question, families in AREAS:
        in_area = [c for f in families for c in by_family.get(f, [])]
        links = ", ".join(f"[`{f}`](#{slug(f'{names[f]} ({f})')})" for f in families if f in by_family)
        out.append(f"| [{area}](#{slug(area)}) | {question} | {links} | {len(in_area)} ({count_line(in_area)}) |")
    for area, question, families in AREAS:
        out += ["", f"## {area}", "", question]
        for family in families:
            members = by_family.get(family, [])
            if not members:
                continue
            out += ["", f"### {names[family]} ({family})", "", f"{len(members)} checks: {count_line(members)}."]
            for check in members:
                facts = [f"`{check.severity}`", "scored" if check.scored else "not scored", METHOD_LABEL[check.method]]
                if check.playbooks:
                    fixes = ", ".join(f"[`{p}`](implement-master.md#{p})" for p in check.playbooks)
                    facts.append(f"fixed by {fixes}")
                else:
                    facts.append("no playbook (the audit emits it as an input)")
                out += [
                    "",
                    f"#### {check_heading(check)}",
                    "",
                    *wrap(" · ".join(facts)),
                    "",
                    *wrap(f"**Passes when:** {check.passes}", "- ", "  "),
                    *wrap(f"**Why it matters:** {check.why}", "- ", "  "),
                ]
    out += [
        "",
        "## Read more",
        "",
        "- The full rubric of each check (PARTIAL, FAIL, evidence, pitfalls):",
        "  [`audit/checks/`](../../audit/checks/README.md).",
        "- Each check's requirement and framework section:",
        "  [Checks to framework map](how-the-checks-map-to-the-framework.md).",
        "- How an audit runs: [Run an audit](../how-to/run-an-audit.md).",
    ]
    return "\n".join(out) + "\n"


IMPLEMENT_FLOW = """```mermaid
flowchart LR
    R["Final audit report<br/>(owner-confirmed)"] --> T["Triage: keep, skip<br/>or defer each finding"]
    T --> P["Plan the next theme"]
    P --> A["Apply its playbooks<br/>on a branch, one commit per item"]
    A --> C["Re-check with the engine<br/>and run the gate"]
    C --> PR["Pull request<br/>for the owner"]
    PR -->|owner merges| P
    PR -->|last theme| F["Full re-audit<br/>and comparison"]
```"""


def render_implement(checks: Sequence[Check], playbooks: Sequence[Playbook]) -> str:
    titles = {c.id: check_heading(c) for c in checks}
    by_theme: dict[str, list[Playbook]] = {}
    theme_names: dict[str, str] = {}
    for playbook in playbooks:
        by_theme.setdefault(playbook.theme, []).append(playbook)
        theme_names.setdefault(playbook.theme, playbook.theme_name)
    themes = sorted(by_theme, key=lambda t: int(t[1:]))
    orphans = [c for c in checks if not c.playbooks]
    out: list[str] = [
        "# Implement master list",
        "",
        "> **Audience:** CTOs, senior engineers and anyone who wants to know what an implement run changes.",
        "> **Source of truth:** the playbooks in [`implement/playbooks/`](../../implement/playbooks/README.md) and",
        "> [`catalogue.json`](../../audit/catalogue.json).",
        ">",
        *generated_note("the playbooks and the catalogue"),
        "",
        "---",
        "",
        *wrap(
            f"An implement run closes the confirmed findings of an audit with **{len(playbooks)} playbooks** in "
            f"{len(themes)} themes. Each theme is one branch and one pull request in the audited repository. The "
            "agent never merges: the owner reviews and merges each pull request, and can skip or defer any finding. "
            "Each playbook below says what it achieves, what it changes per check, and what it never does. The "
            "checks themselves are in the [audit master list](audit-master.md)."
        ),
        "",
        IMPLEMENT_FLOW,
        "",
        "## At a glance",
        "",
        "Themes run in dependency order: the order and the dependencies are in",
        "[`implement/SKILL.md`](../../implement/SKILL.md#themes).",
        "",
        "| Theme | Playbooks | Checks closed |",
        "|---|---|---|",
    ]
    for theme in themes:
        names = ", ".join(f"[`{p.name}`](#{p.name})" for p in by_theme[theme])
        closed = sum(len(p.resolves) for p in by_theme[theme])
        out.append(f"| [{theme} {theme_names[theme]}](#{slug(f'{theme} {theme_names[theme]}')}) | {names} | {closed} |")
    for theme in themes:
        out += ["", f"## {theme} {theme_names[theme]}"]
        for playbook in by_theme[theme]:
            out += [
                "",
                f"### `{playbook.name}`",
                "",
                playbook.goal,
                "",
                "| Check | What the playbook does |",
                "|---|---|",
            ]
            for check_id, what in playbook.resolves:
                title = titles.get(check_id, f"`{check_id}`")
                out.append(f"| [{title}](audit-master.md#{slug(title)}) | {what} |")
            if playbook.never:
                out += ["", "**What it never does:**", "", playbook.never]
            out += ["", f"Full playbook: [`{playbook.name}.md`](../../implement/playbooks/{playbook.name}.md)."]
    if orphans:
        out += ["", "## Checks with no playbook", ""]
        for check in orphans:
            out += wrap(
                f"[{check_heading(check)}](audit-master.md#{slug(check_heading(check))}): the audit emits it, and "
                "a playbook reads it as an input.",
                "- ",
                "  ",
            )
    out += [
        "",
        "## Read more",
        "",
        "- The stages, the hard rules and the state file: [`implement/SKILL.md`](../../implement/SKILL.md).",
        "- How to run it: [Implement an audit report](../how-to/implement-an-audit-report.md).",
    ]
    return "\n".join(out) + "\n"


def render(root: Path) -> dict[Path, str]:
    """Both pages, keyed by their path relative to ``root``."""
    version, checks, names = read_checks(root)
    playbooks = read_playbooks(root)
    known = {c.id for c in checks}
    for playbook in playbooks:
        for check_id, _ in playbook.resolves:
            if check_id not in known:
                raise SourceError(f"{PLAYBOOKS_DIR}/{playbook.name}.md resolves {check_id}, which the catalogue lacks")
    return {AUDIT_PAGE: render_audit(version, checks, names), IMPLEMENT_PAGE: render_implement(checks, playbooks)}


# --- Entry point --------------------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="exit 1 when a page is stale")
    mode.add_argument("--write", action="store_true", help="rewrite both pages in place")
    args = parser.parse_args(argv)
    try:
        pages = render(root)
    except (SourceError, OSError, KeyError, ValueError) as exc:
        print(f"build_masters: {exc}", file=sys.stderr)
        return 2
    stale = [
        path
        for path, text in pages.items()
        if not (root / path).is_file() or (root / path).read_text(encoding="utf-8") != text
    ]
    if args.write:
        for path in stale:
            (root / path).write_text(pages[path], encoding="utf-8")
            print(f"build_masters: wrote {path}")
        return 0
    for path in stale:
        print(f"build_masters: {path} is stale; run `make update-masters` and commit the result", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
