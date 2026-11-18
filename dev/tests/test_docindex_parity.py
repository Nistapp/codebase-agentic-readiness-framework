# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Parity of the index extractor with ``dev/recipe_lint.py``: two independent parsers must agree (plan 7.5).

For every Markdown file that ``recipe_lint`` lints (``find_markdown`` and ``find_root_pages``), the test compares the
set of relative link targets, as (repository path, anchor), that each one finds. ``recipe_lint``'s side is what its
own link loop (``check_links``) hands to ``check_link``, less the targets that ``check_link`` treats as external. The
extractor's side is :func:`docindex.links.find_links` on :func:`docindex.markdown.parse`, resolved with
:func:`docindex.links.resolve`; a second test checks that the index holds exactly those links for each file it
parses.

A difference is a bug in one of the two parsers, unless :data:`ACCEPTED` lists it with a reason. Any other
difference fails, and so does an accepted one that no longer occurs, so the list stays exact.

The ID part (leaf RF1.6) compares, for every file whose IDs ``recipe_lint`` reads (``find_markdown``, outside the
engine's tree), the check IDs and the requirement IDs it finds (``load_catalogue``'s pattern and
``REQUIREMENT_ID``, on every line) with the targets of the index's ``mentions`` edges from that file. Its accepted
differences are in :data:`ACCEPTED_IDS`, under the same rules.

This test, not the extractor, imports ``dev/recipe_lint.py``: the core package never does.
"""

from __future__ import annotations

import posixpath
import unittest
from pathlib import Path
from typing import Sequence
from unittest import mock

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import doc_index
import recipe_lint
from docindex import extract, links, markdown, model
from docindex.gitread import WorkTree

REPO = doc_index.REPO

#: A link target as the test compares it: the repository path and the anchor ('' for none).
Target = tuple[str, str]

#: The accepted differences: (file, side, path, anchor) to the reason. ``side`` names the parser that finds the
#: target and the other does not: ``recipe_lint`` or ``docindex``.
ACCEPTED: dict[tuple[str, str, str, str], str] = {
    ("docs/STYLE_GUIDE.md", "recipe_lint", "audit/tools/report.py", "L1-L40"): (
        "The link syntax is an example inside an inline code span. GitHub renders it as code, not as a link, so "
        "docindex leaves it out; recipe_lint drops the backticks first and reads a link."
    ),
    (
        "greenfield/templates/docs/STYLE_GUIDE.md",
        "recipe_lint",
        "greenfield/templates/src/core/orchestrator.ts",
        "L37-L61",
    ): (
        "The link syntax is an example inside an inline code span. GitHub renders it as code, not as a link, so "
        "docindex leaves it out; recipe_lint drops the backticks first and reads a link (it does not check this "
        "template's links, which are relative to the new project)."
    ),
}


def _linted() -> list[Path]:
    """The files ``recipe_lint`` lints, tracked files only (an untracked page on disk is no part of the index)."""
    tracked = set(WorkTree(REPO).files())
    files = recipe_lint.find_markdown(REPO) + recipe_lint.find_root_pages(REPO)
    return sorted({file for file in files if file.relative_to(REPO).as_posix() in tracked})


def _recipe_lint_targets(file: Path, lines: Sequence[str]) -> set[Target]:
    """The relative targets that ``recipe_lint``'s link loop finds in ``file``."""
    found: list[str] = []

    def collect(root: Path, source: Path, line: int, target: str, cache: object, out: object) -> None:
        if not recipe_lint._EXTERNAL.match(target):
            found.append(target)

    with mock.patch.object(recipe_lint, "check_link", collect):
        recipe_lint.check_links(REPO, file, lines, {}, recipe_lint.Outcome())
    relative = file.relative_to(REPO).as_posix()
    targets: set[Target] = set()
    for target in found:
        path_part, _sep, anchor = target.partition("#")
        if path_part:
            targets.add((posixpath.normpath(posixpath.join(posixpath.dirname(relative), path_part)), anchor))
        else:
            targets.add((relative, anchor))
    return targets


def _docindex_targets(relative: str, text: str) -> set[Target]:
    """The relative targets that the extractor's link finder finds in the file at ``relative``."""
    targets: set[Target] = set()
    for found in links.find_links(markdown.parse(relative, text)):
        path, anchor = links.resolve(relative, found.text)
        targets.add((path, anchor or ""))
    return targets


class LinkParityTest(unittest.TestCase):
    maxDiff = None

    def test_both_parsers_find_the_same_link_targets(self) -> None:
        unexplained: list[str] = []
        seen: set[tuple[str, str, str, str]] = set()
        files = _linted()
        self.assertGreater(len(files), 100)
        for file in files:
            relative = file.relative_to(REPO).as_posix()
            text = file.read_text(encoding="utf-8")
            theirs = _recipe_lint_targets(file, text.splitlines())
            ours = _docindex_targets(relative, text)
            differences = [(relative, "recipe_lint", *target) for target in sorted(theirs - ours)]
            differences += [(relative, "docindex", *target) for target in sorted(ours - theirs)]
            for difference in differences:
                if difference in ACCEPTED:
                    seen.add(difference)
                else:
                    unexplained.append(" | ".join(difference))
        self.assertEqual(unexplained, [], "differences between recipe_lint and docindex not in ACCEPTED")
        self.assertEqual(sorted(set(ACCEPTED) - seen), [], "accepted differences that no longer occur")

    def test_every_accepted_difference_has_a_reason(self) -> None:
        for key, reason in ACCEPTED.items():
            with self.subTest(key=key):
                self.assertIn(key[1], ("recipe_lint", "docindex"))
                self.assertGreater(len(reason.split()), 5)


class IndexHoldsTheLinksTest(unittest.TestCase):
    def test_each_parsed_file_has_an_exact_links_edge_per_target_found(self) -> None:
        tree = WorkTree(REPO)
        config = doc_index.load_config()
        result = extract.extract(tree, config)
        by_file: dict[str, set[Target]] = {}
        for edge in result.index.edges:
            if edge.kind == "links" and edge.confidence == "exact":
                source = edge.source.partition("#")[0]
                by_file.setdefault(source, set()).add((edge.target.partition("#")[0], edge.anchor or ""))
        list_only = tuple(prefix.rstrip("/") + "/" for prefix in config.get("exclude", {}).get("list_only", []))
        checked = 0
        for file in _linted():
            relative = file.relative_to(REPO).as_posix()
            if relative.startswith(list_only):
                continue  # listed and not parsed: a fixture tree's file
            checked += 1
            text = tree.read(relative) or ""
            with self.subTest(file=relative):
                self.assertEqual(by_file.get(relative, set()), _docindex_targets(relative, text))
        self.assertGreater(checked, 100)


#: An ID as the ID parity compares it: the ID kind (``check`` or ``requirement``) and the ID.
IdMention = tuple[str, str]

#: The accepted differences of the ID parity: (file, side, kind, ID) to the reason. ``side`` names the parser that
#: finds the ID and the other does not. None today: both read every line of a file, code fences included, and
#: recipe_lint's patterns find no ID that the catalogue or the spec does not define (recipe-lint would fail).
ACCEPTED_IDS: dict[tuple[str, str, str, str], str] = {}


def _id_linted() -> list[Path]:
    """The files whose check and requirement IDs ``recipe_lint`` reads: ``find_markdown``, tracked, outside
    ``EXCLUDED_FROM_CATALOGUE`` (the engine's tree)."""
    tracked = set(WorkTree(REPO).files())
    return sorted(
        file
        for file in recipe_lint.find_markdown(REPO)
        if file.relative_to(REPO).as_posix() in tracked and not recipe_lint.excluded_from_catalogue_checks(file, REPO)
    )


def _recipe_lint_ids(lines: Sequence[str], catalogue: recipe_lint.Catalogue) -> set[IdMention]:
    """The check and requirement IDs that ``check_catalogue_references`` and ``check_requirement_references`` find."""
    found: set[IdMention] = set()
    for line in lines:
        if catalogue.check_id_pattern is not None:
            found.update(("check", match.group(0)) for match in catalogue.check_id_pattern.finditer(line))
        found.update(("requirement", match.group(0)) for match in recipe_lint.REQUIREMENT_ID.finditer(line))
    return found


class MentionParityTest(unittest.TestCase):
    """The check and requirement IDs each file mentions: the index's ``mentions`` edges against ``recipe_lint``."""

    maxDiff = None

    def test_both_find_the_same_id_mentions(self) -> None:
        catalogue = recipe_lint.load_catalogue(REPO)
        assert catalogue is not None
        index = extract.extract(WorkTree(REPO), doc_index.load_config()).index
        kinds = {node.address: node.kind for node in index.nodes if isinstance(node, model.IdNode)}
        ours_by_file: dict[str, set[IdMention]] = {}
        for edge in index.edges:
            kind = kinds.get(edge.target)
            if edge.kind == "mentions" and kind is not None and kind in ("check", "requirement"):
                ours_by_file.setdefault(edge.source.partition("#")[0], set()).add((kind, edge.target))
        unexplained: list[str] = []
        seen: set[tuple[str, str, str, str]] = set()
        files = _id_linted()
        self.assertGreater(len(files), 100)
        compared = 0
        for file in files:
            relative = file.relative_to(REPO).as_posix()
            theirs = _recipe_lint_ids(file.read_text(encoding="utf-8").splitlines(), catalogue)
            ours = ours_by_file.get(relative, set())
            compared += len(theirs)
            differences = [(relative, "recipe_lint", *mention) for mention in sorted(theirs - ours)]
            differences += [(relative, "docindex", *mention) for mention in sorted(ours - theirs)]
            for difference in differences:
                if difference in ACCEPTED_IDS:
                    seen.add(difference)
                else:
                    unexplained.append(" | ".join(difference))
        self.assertGreater(compared, 500)
        self.assertEqual(unexplained, [], "ID differences between recipe_lint and docindex not in ACCEPTED_IDS")
        self.assertEqual(sorted(set(ACCEPTED_IDS) - seen), [], "accepted ID differences that no longer occur")

    def test_every_accepted_id_difference_has_a_reason(self) -> None:
        for key, reason in ACCEPTED_IDS.items():
            with self.subTest(key=key):
                self.assertIn(key[1], ("recipe_lint", "docindex"))
                self.assertIn(key[2], ("check", "requirement"))
                self.assertGreater(len(reason.split()), 5)

    def test_the_index_defines_what_recipe_lint_loads(self) -> None:
        catalogue = recipe_lint.load_catalogue(REPO)
        requirements = recipe_lint.load_requirement_ids(REPO)
        assert catalogue is not None and requirements is not None
        index = extract.extract(WorkTree(REPO), doc_index.load_config()).index
        defined = {(node.kind, node.address) for node in index.nodes if isinstance(node, model.IdNode)}
        self.assertLessEqual({("check", check) for check in catalogue.check_ids}, defined)
        self.assertLessEqual({("requirement", requirement) for requirement in requirements}, defined)


if __name__ == "__main__":
    unittest.main()
