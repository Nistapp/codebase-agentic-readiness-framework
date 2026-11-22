# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-13: Coding conventions written."""

from __future__ import annotations

import fnmatch
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.checks.agt._shared import _MD_HEADING_RE, _MD_FENCE_RE

SPEC = declare(
    "AGT-13",
    "Coding conventions written",
    "B",
    Severity.COSMETIC,
    rule="A conventions file (root, docs/ or .github/) or a conventions section of AGENTS.md or CONTRIBUTING.md "
    "covers naming, layering, error handling and logging, and testing, links the formatter or linter config, "
    "and holds no stub word; docs/STYLE_GUIDE.md never counts.",
)


# ---------------------------------------------------------------------------
# AGT-13 — coding conventions written
# ---------------------------------------------------------------------------

#: The basenames of a conventions file, matched case-insensitively (PLAN.md 5.6.1 a).
_CONVENTIONS_FILE_GLOBS = ("conventions*", "*convention*", "code_style*", "coding_standards*", "*coding-guidelines*")
#: The extensions a conventions file may carry: prose, or none at all.
_CONVENTIONS_FILE_SUFFIXES = (".md", ".markdown", ".mdx", ".txt", ".rst", ".adoc")
#: The docs style guide sets the rules for documentation, not for code, so it never counts (PLAN.md 5.6.1 c).
_DOCS_STYLE_GUIDE = "docs/style_guide.md"
#: The files read for a conventions section (PLAN.md 5.6.1 b), in this order.
_CONVENTIONS_SECTION_FILES = ("AGENTS.md", "CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md")
#: A heading of level 2 to 6 that opens a conventions section.
_CONVENTIONS_HEADING_RE = re.compile(r"(?i)\b(conventions?|code style|coding standards?|naming)\b")
#: A heading about Git or documentation is not about code, even when it says "conventions": "Git conventions".
_NOT_CODE_HEADING_RE = re.compile(
    r"(?i)\b(git|commits?|branch\w*|pull requests?|releases?|docs|documentation|writing|prose)\b"
)
#: A stub word, upper case and as a whole word, outside code spans and fenced blocks (PLAN.md 5.6.1 e).
_CONVENTIONS_STUB_RE = re.compile(r"\b(TBD|TODO)\b")
_CODE_SPAN_RE = re.compile(r"`[^`]*`")
#: The five best-practice items (P9.2.3), in order, each with the words that show it. The words cover the Java,
#: Node and Python stack profiles in `audit/stacks/`. An item is covered when any of its patterns matches; error
#: handling and logging needs a word for each.
_CONVENTIONS_ITEMS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "naming",
        (re.compile(r"(?i)\bnaming\b|camel[ -]?case|pascal[ -]?case|snake[_ -]case|kebab[- ]case|\bpep ?8\b"),),
    ),
    (
        "layering",
        (
            re.compile(
                r"(?i)\blayer(?:s|ed|ing)?\b|\barchitecture\b|\bboundar(?:y|ies)\b|\bwhat goes where\b"
                r"|\b(?:package|project|folder|directory|module|source) (?:structure|layout)\b"
                r"|\bmay (?:import|call|depend on)\b|\bcontrollers?\b|\bhexagonal\b|\bports and adapters\b"
            ),
        ),
    ),
    (
        "error handling and logging",
        (
            re.compile(r"(?i)\berrors?\b|\bexceptions?\b|\bthrows?\b|\braises?\b"),
            re.compile(r"(?i)\blog(?:s|ging|ged|gers?)?\b|\bslf4j\b|\blog4j2?\b|\blogback\b|\bwinston\b|\bpino\b"),
        ),
    ),
    (
        "testing",
        (re.compile(r"(?i)\btest(?:s|ing|ed)?\b|\bjunit\b|\bpytest\b|\bunittest\b|\bjest\b|\bvitest\b|\bmocha\b"),),
    ),
    (
        "a link to the formatter or linter config",
        (
            re.compile(
                r"(?i)\.editorconfig\b|\.prettierrc|\bprettier\.config\.|\bbiome\.jsonc?\b|\beslint\.config\."
                r"|\.eslintrc|\bpyproject\.toml\b|\bruff\.toml\b|\bsetup\.cfg\b|\.flake8\b|\.?pylintrc\b"
                r"|\bcheckstyle[\w-]*\.xml\b|\bpmd[\w-]*\.xml\b|\bspotless\b"
            ),
        ),
    ),
)


def _conventions_files(inventory: Inventory) -> list[str]:
    """The conventions files at the root or under `docs/` or `.github/`, sorted; never the docs style guide."""
    found: list[str] = []
    for rel in sorted(inventory.paths()):
        lowered = rel.lower()
        folder, _, base = lowered.rpartition("/")
        if folder and not (folder in ("docs", ".github") or folder.startswith(("docs/", ".github/"))):
            continue
        if lowered == _DOCS_STYLE_GUIDE or not any(fnmatch.fnmatchcase(base, g) for g in _CONVENTIONS_FILE_GLOBS):
            continue
        if "." in base.lstrip(".") and not base.endswith(_CONVENTIONS_FILE_SUFFIXES):
            continue
        found.append(rel)
    return found


def _conventions_sections(text: str) -> list[tuple[int, str, str]]:
    """Each conventions section of ``text``: its heading line, its heading and its text, heading and subsections in.

    A section opens at a heading of level 2 to 6, outside a fenced block, and ends at the next heading of its level
    or a higher one, or at the end of the file.
    """
    lines = text.splitlines()
    headings: list[tuple[int, int, str]] = []
    in_fence = False
    for number, line in enumerate(lines, start=1):
        if _MD_FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        match = None if in_fence else _MD_HEADING_RE.match(line)
        if match:
            headings.append((number, len(match.group(1)), match.group(2)))
    sections: list[tuple[int, str, str]] = []
    for index, (number, level, title) in enumerate(headings):
        if level < 2 or not _CONVENTIONS_HEADING_RE.search(title) or _NOT_CODE_HEADING_RE.search(title):
            continue
        end = next((n for n, lvl, _ in headings[index + 1 :] if lvl <= level), len(lines) + 1)
        sections.append((number, title, "\n".join(lines[number - 1 : end - 1])))
    return sections


def _stub_word(text: str, first_line: int) -> tuple[int, str] | None:
    """The first stub word in ``text`` and its line, counting from ``first_line``; code spans and fences skipped."""
    in_fence = False
    for offset, line in enumerate(text.splitlines()):
        if _MD_FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        match = None if in_fence else _CONVENTIONS_STUB_RE.search(_CODE_SPAN_RE.sub(" ", line))
        if match:
            return first_line + offset, match.group(1)
    return None


def check_agt13(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    # (path, first line, label, evidence note, text) for each source: files first, then sections in file order.
    sources: list[tuple[str, int, str, str, str]] = []
    for rel in _conventions_files(inventory):
        text = inventory.read(rel)
        if text:
            sources.append((rel, 1, rel, "conventions file", text))
    read_for_sections: list[str] = []
    for name in _CONVENTIONS_SECTION_FILES:
        text = inventory.read(name)
        if not text:
            continue
        read_for_sections.append(name)
        for number, title, body in _conventions_sections(text):
            sources.append((name, number, f"{name}:{number} § {title}", f"section: {title}", body))

    if not sources:
        where = " or ".join(read_for_sections)
        why = (
            f"there is no conventions file and {where} has no conventions section"
            if where
            else "there is no conventions file, and no AGENTS.md or CONTRIBUTING.md to hold a conventions section"
        )
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.FAIL,
            spec.status,
            summary=why,
            findings=[
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement("follow the code rules of this repository", why),
                    evidence=[Evidence(name, line=1, note="no conventions section") for name in read_for_sections],
                    remediation="Write CONVENTIONS.md (the greenfield template is a start): naming, layering, "
                    "error handling and logging, and testing, from the code as it is, and a link to the formatter "
                    "and linter configs. A conventions section in AGENTS.md or CONTRIBUTING.md also counts.",
                ),
            ],
        )

    combined = "\n".join(text for *_, text in sources)
    uncovered = [label for label, patterns in _CONVENTIONS_ITEMS if not all(p.search(combined) for p in patterns)]
    stubs = [(path, *found) for path, first, *_, text in sources if (found := _stub_word(text, first))]
    where = "; ".join(label for _, _, label, _, _ in sources)

    if not uncovered and not stubs:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.PASS,
            spec.status,
            summary=f"conventions ({where}) cover naming, layering, error handling and logging, and testing, "
            "and link the formatter or linter config",
        )

    gaps: list[str] = []
    if uncovered:
        gaps.append(f"do not cover {', '.join(uncovered)}")
    if stubs:
        held = ", ".join(f"{word} at {path}:{line}" for path, line, word in stubs)
        gaps.append(f"{'they ' if uncovered else ''}hold the stub word {held}")
    why = f"the conventions ({where}) " + "; ".join(gaps)
    evidence = [Evidence(path, line=first, note=note) for path, first, _, note, _ in sources]
    evidence += [Evidence(path, line=line, note=f"stub word {word}") for path, line, word in stubs]
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        Verdict.PARTIAL,
        spec.status,
        summary=why,
        findings=[
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement("follow the code rules of this repository in full", why),
                evidence=evidence,
                remediation="Complete the conventions from the code as it is: add each missing item, link the "
                "formatter and linter configs rather than copy their settings, and replace each stub word with "
                "the rule the team follows.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import FOLD, GLOB, ROOT, Reads, What, _at

    return Reads(
        where=(
            *_at(
                GLOB,
                "*convention*",
                "code_style*",
                "coding_standards*",
                "*coding-guidelines*",
                "docs/**/*convention*",
                "docs/**/code_style*",
                "docs/**/coding_standards*",
                "docs/**/*coding-guidelines*",
                ".github/**/*convention*",
                ".github/**/code_style*",
                ".github/**/coding_standards*",
                ".github/**/*coding-guidelines*",
                case=FOLD,
            ),
            *_at(ROOT, "AGENTS.md", "CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"),
        ),
        what=What("word-list"),
        binding="file",
        threshold="all five items and no stub word",
        note=(
            "Conventions files match the globs by lower-case base name at the root or anywhere under docs/ or"
            " .github/, with a prose extension or none, never docs/STYLE_GUIDE.md; the four root files give "
            "level 2-6 conventions sections that are not about git or docs. Five items over all sources "
            "together (naming, layering, error handling and logging, testing, a formatter or linter config "
            "name), plus TBD or TODO outside code."
        ),
    )
