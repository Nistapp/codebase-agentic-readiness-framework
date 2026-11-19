# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the index diff (``doc_index.py diff``).

The fixture repository is built at run time in a temporary folder, one commit per case; no nested repository is
committed, and no fixture file is named like the repository's own instruction files.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, ClassVar, Mapping

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from docindex import cli, extract
from docindex import diff as index_diff
from docindex.model import Edge

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Diff Test",
    "GIT_AUTHOR_EMAIL": "diff@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Diff Test",
    "GIT_COMMITTER_EMAIL": "diff@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

#: The fixture's config: Markdown and JSON files, and one ID kind defined by a JSON list.
CONFIG: dict[str, Any] = {
    "exclude": {"list_only": [], "skip": []},
    "file_kinds": {".json": "json", ".md": "markdown"},
    "ids": {
        "check": {
            "define": {"json": {"id": "id", "list": "checks", "title": "title"}},
            "defined_in": ["checks.json"],
            "pattern": r"\b([A-Z]{2,4}-\d{2})\b",
        }
    },
}

CHECKS = {"checks": [{"id": "ABC-01", "title": "First"}, {"id": "ABC-02", "title": "Second"}]}

GUIDE = """Intro text, see [the notes](notes.md).

# Guide

The guide's opening words.

## Keep

Keep this part as it is.

## Drop

This part goes away later.

## Travel

This part travels to the other file.

## Old name

This body stays while the title changes.

## Change

The first wording of this part.
"""

NOTES = """# Notes

Notes about the guide.

## Destination

Where things arrive.
"""

MENTIONS = """# Checks

## First check

The check ABC-01 runs first.

## Second check

The check ABC-02 runs second.
"""

LINKS = """Read [the guide](guide.md) first.
"""

FRESH = "\n## Fresh\n\nA new part with its own words.\n"
TRAVEL = "## Travel\n\nThis part travels to the other file.\n\n"

#: Every group of the report, as its count key; a case's expected counts name the groups that are not zero.
GROUPS = (
    "edges_gained",
    "edges_lost",
    "ids_lost_definition",
    "ids_lost_mentions",
    "sections_added",
    "sections_edited",
    "sections_moved",
    "sections_removed",
    "sections_renamed",
)


def _counts(**nonzero: int) -> dict[str, int]:
    return {group: nonzero.get(group, 0) for group in GROUPS}


def _edge(kind: str, source: str, target: str, anchor: str | None = None) -> dict[str, Any]:
    return {"anchor": anchor, "confidence": "exact", "kind": kind, "source": source, "target": target}


class _MemoryTree:
    """A tree held in memory: a path to its text."""

    def __init__(self, files: Mapping[str, str]) -> None:
        self._files = dict(files)

    def files(self) -> list[str]:
        return sorted(self._files)

    def read(self, path: str) -> str | None:
        return self._files.get(path)


def _compare(old: Mapping[str, str], new: Mapping[str, str]) -> index_diff.IndexDiff:
    old_tree, new_tree = _MemoryTree(old), _MemoryTree(new)
    return index_diff.compare(
        extract.extract(old_tree, CONFIG).index,
        extract.extract(new_tree, CONFIG).index,
        old_body=index_diff.body_hashes(old_tree),
        new_body=index_diff.body_hashes(new_tree),
    )


class FixtureRepositoryTest(unittest.TestCase):
    """One commit per case on a temporary repository; each case is diffed against its parent."""

    root: ClassVar[Path]
    commits: ClassVar[dict[str, str]]

    @classmethod
    def setUpClass(cls) -> None:
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)
        cls.root = Path(folder.name)
        cls._git("init", "-q")
        cls.commits = {}
        guide, notes, links = GUIDE, NOTES, LINKS
        cls.commits["base"] = cls._commit(
            {"checks.json": json.dumps(CHECKS, indent=2) + "\n", "guide.md": guide, "notes.md": notes},
            {"mentions.md": MENTIONS, "links.md": links},
        )
        notes += FRESH
        cls.commits["added"] = cls._commit({"notes.md": notes})
        guide = guide.replace("## Drop\n\nThis part goes away later.\n\n", "")
        cls.commits["removed"] = cls._commit({"guide.md": guide})
        guide = guide.replace(TRAVEL, "")
        notes += "\n" + TRAVEL
        cls.commits["moved"] = cls._commit({"guide.md": guide, "notes.md": notes})
        guide = guide.replace("## Old name\n", "## New name\n")
        cls.commits["renamed"] = cls._commit({"guide.md": guide})
        guide = guide.replace("The first wording", "The second wording")
        cls.commits["edited"] = cls._commit({"guide.md": guide})
        links = "Read the guide first.\n"
        cls.commits["link-lost"] = cls._commit({"links.md": links})
        links += "\nThen read [the notes](notes.md#notes).\n"
        cls.commits["link-gained"] = cls._commit({"links.md": links})
        checks = {"checks": [CHECKS["checks"][0]]}
        cls.commits["id-undefined"] = cls._commit({"checks.json": json.dumps(checks, indent=2) + "\n"})

    @classmethod
    def _git(cls, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=cls.root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    @classmethod
    def _commit(cls, *groups: Mapping[str, str]) -> str:
        for files in groups:
            for path, text in files.items():
                (cls.root / path).write_text(text, encoding="utf-8")
        cls._git("add", "-A")
        cls._git("commit", "-q", "-m", "change")
        return cls._git("rev-parse", "HEAD")

    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv, CONFIG, root=self.root)
        return code, out.getvalue(), err.getvalue()

    def _case(self, name: str) -> dict[str, Any]:
        """The JSON report of the commit ``name`` against its parent."""
        commit = self.commits[name]
        code, out, err = self._run(["diff", f"{commit}~1", "--at", commit, "--format", "json"])
        self.assertEqual((code, err), (0, ""))
        report: dict[str, Any] = json.loads(out)
        self.assertEqual(report["old"], f"{commit}~1")
        self.assertEqual(report["new"], commit)
        return report

    def test_a_section_added(self) -> None:
        report = self._case("added")
        self.assertEqual(report["counts"], _counts(sections_added=1))
        self.assertEqual(
            report["sections"]["added"], [{"address": "notes.md#notes/fresh", "level": 2, "title": "Fresh"}]
        )

    def test_a_section_removed(self) -> None:
        report = self._case("removed")
        self.assertEqual(report["counts"], _counts(sections_removed=1))
        self.assertEqual(
            report["sections"]["removed"], [{"address": "guide.md#guide/drop", "level": 2, "title": "Drop"}]
        )

    def test_a_section_moved(self) -> None:
        report = self._case("moved")
        self.assertEqual(report["counts"], _counts(sections_moved=1))
        self.assertEqual(
            report["sections"]["moved"],
            [{"new": "notes.md#notes/travel", "old": "guide.md#guide/travel", "title": "Travel"}],
        )

    def test_a_section_renamed(self) -> None:
        report = self._case("renamed")
        self.assertEqual(report["counts"], _counts(sections_renamed=1))
        self.assertEqual(
            report["sections"]["renamed"],
            [
                {
                    "new": "guide.md#guide/new-name",
                    "new_title": "New name",
                    "old": "guide.md#guide/old-name",
                    "old_title": "Old name",
                }
            ],
        )

    def test_a_section_edited(self) -> None:
        report = self._case("edited")
        self.assertEqual(report["counts"], _counts(sections_edited=1))
        self.assertEqual(
            report["sections"]["edited"], [{"address": "guide.md#guide/change", "old_address": "guide.md#guide/change"}]
        )

    def test_a_link_lost(self) -> None:
        report = self._case("link-lost")
        self.assertEqual(report["counts"], _counts(edges_lost=1))
        self.assertEqual(report["edges"]["lost"], [_edge("links", "links.md", "guide.md")])

    def test_a_link_gained_keeps_its_anchor(self) -> None:
        report = self._case("link-gained")
        self.assertEqual(report["counts"], _counts(edges_gained=1))
        self.assertEqual(report["edges"]["gained"], [_edge("links", "links.md", "notes.md#notes", "notes")])

    def test_an_id_losing_its_definition_carries_its_mentions(self) -> None:
        report = self._case("id-undefined")
        self.assertEqual(report["counts"], _counts(ids_lost_definition=1))
        self.assertEqual(
            report["ids"]["lost_definition"],
            [
                {
                    "defined_by": "checks.json",
                    "edges": [_edge("mentions", "mentions.md#checks/second-check", "ABC-02")],
                    "id": "ABC-02",
                    "kind": "check",
                }
            ],
        )

    def test_the_whole_range_reports_each_case_once(self) -> None:
        argv = ["diff", self.commits["base"], "--at", self.commits["id-undefined"], "--format", "json"]
        code, out, err = self._run(argv)
        self.assertEqual((code, err), (0, ""))
        counts = _counts(
            edges_gained=1,
            edges_lost=1,
            ids_lost_definition=1,
            sections_added=1,
            sections_edited=1,
            sections_moved=1,
            sections_removed=1,
            sections_renamed=1,
        )
        self.assertEqual(json.loads(out)["counts"], counts)

    def test_the_text_form_groups_and_sorts(self) -> None:
        base, last = self.commits["base"], self.commits["id-undefined"]
        code, out, err = self._run(["diff", base, "--at", last])
        self.assertEqual((code, err), (0, ""))
        expected = f"""# Index diff from {base} to {last}: 8 changes

# Sections added: 1
  notes.md#notes/fresh "Fresh"

# Sections removed: 1
  guide.md#guide/drop "Drop"

# Sections moved: 1
  guide.md#guide/travel -> notes.md#notes/travel

# Sections renamed: 1
  guide.md#guide/old-name -> guide.md#guide/new-name ("Old name" -> "New name")

# Sections edited: 1
  guide.md#guide/change

# Edges lost: 1
  links: links.md -> guide.md

# Edges gained: 1
  links: links.md -> notes.md#notes (anchor #notes)

# IDs that lost their definition: 1
  ABC-02 (check), defined by checks.json
    lost with it: mentions: mentions.md#checks/second-check -> ABC-02

# IDs that lost every mention: 0
"""
        self.assertEqual(out, expected)

    def test_the_json_form_is_deterministic(self) -> None:
        argv = ["diff", self.commits["base"], "--at", self.commits["id-undefined"], "--format", "json"]
        first, second = self._run(argv), self._run(argv)
        self.assertEqual(first, second)
        report = json.loads(first[1])
        self.assertEqual(report["format"], index_diff.DIFF_FORMAT)
        self.assertEqual(first[1], json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def test_the_new_side_defaults_to_the_working_tree(self) -> None:
        code, out, err = self._run(["diff", "HEAD", "--format", "json"])
        self.assertEqual((code, err), (0, ""))
        report = json.loads(out)
        self.assertIsNone(report["new"])
        self.assertEqual(report["counts"], _counts())
        code, out, _err = self._run(["diff", "HEAD"])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("# Index diff from HEAD to the working tree: 0 changes\n"), out)

    def test_a_ref_that_names_no_commit_exits_1(self) -> None:
        for argv in (["diff", "no-such-ref"], ["diff", "HEAD", "--at", "no-such-ref"], ["diff", "--", "-x"]):
            with self.subTest(argv=argv):
                code, out, err = self._run(argv)
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertIn("doc_index.py diff: ", err)

    def test_an_argument_error_exits_1(self) -> None:
        for argv in (["diff"], ["diff", "HEAD", "--format", "xml"], ["diff", "HEAD", "extra"]):
            with self.subTest(argv=argv):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    self._run(argv)
                self.assertEqual(caught.exception.code, 1)


class CompareTest(unittest.TestCase):
    """The pairing rules, on trees held in memory."""

    def test_no_change_is_an_empty_report(self) -> None:
        report = _compare({"a.md": GUIDE}, {"a.md": GUIDE})
        self.assertEqual(report, index_diff.IndexDiff())
        self.assertEqual(report.changes, 0)

    def test_the_children_of_a_renamed_section_follow_it(self) -> None:
        old = "# Top\n\n## Parent\n\nParent body.\n\n### Child\n\nChild body.\n\n### Other\n\nOther body.\n"
        new = old.replace("## Parent", "## Elder").replace("Other body.", "Other body, edited.")
        report = _compare({"a.md": old}, {"a.md": new})
        self.assertEqual(report.renamed, (index_diff.Renamed("a.md#top/parent", "a.md#top/elder", "Parent", "Elder"),))
        self.assertEqual(report.edited, (index_diff.Edited("a.md#top/elder/other", "a.md#top/parent/other"),))
        self.assertEqual((report.added, report.removed, report.moved), ((), (), ()))

    def test_the_children_of_a_moved_section_follow_it_with_their_edges(self) -> None:
        old = {
            "a.md": "# A\n\n## Box\n\nBox body.\n\n### Inner\n\nSee [b](b.md).\n",
            "b.md": "# B\n\nB body.\n",
        }
        new = {"a.md": "# A\n", "b.md": "# B\n\nB body.\n\n## Box\n\nBox body.\n\n### Inner\n\nSee [b](b.md).\n"}
        report = _compare(old, new)
        self.assertEqual(report.moved, (index_diff.Moved("a.md#a/box", "b.md#b/box", "Box"),))
        self.assertEqual(report.counts(), {**_counts(sections_moved=1)})

    def test_a_section_with_a_new_body_and_title_is_removed_and_added(self) -> None:
        old = "# Top\n\n## One\n\nFirst body.\n"
        new = "# Top\n\n## Two\n\nSecond body.\n"
        report = _compare({"a.md": old}, {"a.md": new})
        self.assertEqual([node.address for node in report.removed], ["a.md#top/one"])
        self.assertEqual([node.address for node in report.added], ["a.md#top/two"])
        self.assertEqual(report.renamed, ())

    def test_a_rename_needs_the_same_parent(self) -> None:
        old = "# Top\n\n## One\n\nSame body.\n\n# Other\n"
        new = "# Top\n\n# Other\n\n## Two\n\nSame body.\n"
        report = _compare({"a.md": old}, {"a.md": new})
        self.assertEqual(report.renamed, ())
        self.assertEqual([node.address for node in report.removed], ["a.md#top/one"])
        self.assertEqual([node.address for node in report.added], ["a.md#other/two"])

    def test_a_move_prefers_the_same_file(self) -> None:
        old = {"a.md": "# A\n\n## Twin\n\nTwin body.\n\n# Here\n", "b.md": "# B\n"}
        new = {
            "a.md": "# A\n\n# Here\n\n## Twin\n\nTwin body.\n",
            "b.md": "# B\n\n## Twin\n\nTwin body.\n",
        }
        report = _compare(old, new)
        self.assertEqual(report.moved, (index_diff.Moved("a.md#a/twin", "a.md#here/twin", "Twin"),))
        self.assertEqual([node.address for node in report.added], ["b.md#b/twin"])

    def test_an_id_that_loses_every_mention(self) -> None:
        checks = json.dumps(CHECKS)
        old = {"checks.json": checks, "m.md": MENTIONS}
        new = {"checks.json": checks, "m.md": MENTIONS.replace("The check ABC-02 runs second.", "It runs second.")}
        report = _compare(old, new)
        mention = Edge(kind="mentions", source="m.md#checks/second-check", target="ABC-02")
        self.assertEqual(report.ids_unmentioned, (index_diff.IdLost("ABC-02", "check", "checks.json", (mention,)),))
        self.assertEqual(report.edges_lost, (mention,))
        self.assertEqual([entry.address for entry in report.edited], ["m.md#checks/second-check"])
        self.assertEqual(report.ids_undefined, ())

    def test_body_hashes_skip_the_heading_line(self) -> None:
        read = index_diff.body_hashes(_MemoryTree({"a.md": "# One\n\nBody.\n", "b.md": "# Two\n\nBody.\n"}))
        self.assertEqual(read("a.md")["a.md#one"], read("b.md")["b.md#two"])
        self.assertEqual(read("missing.md"), {})


if __name__ == "__main__":
    unittest.main()
