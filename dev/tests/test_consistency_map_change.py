# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The consistency map's change mode (``dev/consistency_map_change.py``, ADR 0012).

The unit tests build index diffs and file changes by hand. :class:`ReplayTest` replays the two incidents of the
consistency-map design (TODO 2.4 and 2.5) on a small fixture repository with git history, and runs the real engine
on both sides:

- 2.4: renumbering a boundary rule moved "must never" to the next line, so ``AGT-06`` counted one boundary rule
  fewer and fell from ``PASS`` to ``PARTIAL``;
- 2.5: one more "do not" line turned the Documentation section into a prohibitions section, so ``CON-01`` kept
  ``PASS`` on other evidence.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

import _dev_paths
import consistency_map
import consistency_map_change as cmc
from docindex.diff import Edited, IndexDiff, Moved, Renamed
from docindex.gitread import GitError

REAL_MAP: dict[str, Any] = json.loads((_dev_paths.DEV / "consistency-map.json").read_text(encoding="utf-8"))
REAL_READS = {read["check"]: read for read in REAL_MAP["reads"]}
CONFIG: dict[str, Any] = {"default_zone": "docs"}
GIT_ENV = {**os.environ, **cmc._GIT_ENV, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

AGENTS_BASE = """# AGENTS.md

## 1. Boundaries

1. Code in `src/core/` must never import `src/cli/`.
2. Keep each module small.

## 2. Documentation

- Never restate a rule; link to `docs/README.md`.
- Do not edit generated files.

## 3. Never

- Never commit secrets.
- Never push to `main`.
- Do not touch `src/core/`.
"""

# TODO 2.4: the renumbering moved "must never" off the line that names the path.
AGENTS_RENUMBERED = AGENTS_BASE.replace(
    "1. Code in `src/core/` must never import `src/cli/`.", "1. Code in `src/core/`\n   must never import the CLI."
)

# TODO 2.5: a third prohibition line makes the Documentation section a prohibitions section.
AGENTS_DO_NOT_COPY = AGENTS_BASE.replace(
    "- Do not edit generated files.\n", "- Do not edit generated files.\n- Do not copy text from `docs/README.md`.\n"
)

KEEPS_BASE = """# Keeps

## Boundaries

`AGT-06` reads one line: keep each boundary rule and its path on one physical line.
"""

KEEPS_UNMENTIONED = KEEPS_BASE.replace("`AGT-06` reads one line: k", "K")

FIXTURE_MAP: dict[str, Any] = {
    "reads": [REAL_READS["AGT-06"], REAL_READS["CON-01"]],
    "keeps": [
        {
            "move": "renumber",
            "check": "AGT-06",
            "status": "kept",
            "home": {
                "path": "docs/keeps.md",
                "section": "docs/keeps.md#keeps/boundaries",
                "quote": "keep each boundary rule and its path on one physical line",
            },
        }
    ],
}


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True, env=GIT_ENV)
    return result.stdout.strip()


def _commit(root: Path, files: dict[str, str], message: str) -> str:
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "--no-gpg-sign", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _fixture_repository(root: Path) -> str:
    """A fixture repository with the base commit; returns its sha."""
    root.mkdir()
    _git(root, "init", "--quiet")
    return _commit(
        root,
        {
            "src/core/a.py": "X = 1\n",
            "src/cli/b.py": "Y = 1\n",
            "docs/README.md": "# Docs\n",
            "AGENTS.md": AGENTS_BASE,
            "docs/keeps.md": KEEPS_BASE,
        },
        "base",
    )


def _verdicts(report: cmc.ChangeReport) -> dict[str, tuple[str, str | None, str | None]]:
    assert report.evidence is not None
    return {
        change.check: (change.kind, change.old_verdict, change.new_verdict) for change in report.evidence.overlapping
    }


class ReplayTest(unittest.TestCase):
    """TODO incidents 2.4 and 2.5, replayed on a fixture repository with the real engine (the RF4.7 done-when)."""

    scratch: Path
    root: Path
    base: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.scratch = Path(tempfile.mkdtemp(prefix="cmap-change-test-"))
        cls.root = cls.scratch / "repo"
        cls.base = _fixture_repository(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.scratch)

    def setUp(self) -> None:
        _git(self.root, "checkout", "--quiet", "--detach", self.base)

    def _report(self, at: str | None) -> cmc.ChangeReport:
        return cmc.change_report(FIXTURE_MAP, self.root, self.base, at, CONFIG, targets=lambda path: [path])

    def test_incident_2_4_the_renumbered_boundary_rule_is_reported(self) -> None:
        at = _commit(self.root, {"AGENTS.md": AGENTS_RENUMBERED}, "renumber")
        report = self._report(at)
        self.assertIn(
            "edited AGENTS.md#agentsmd/1-boundaries: read by AGT-06, CON-01", [r.line for r in report.reviews]
        )
        self.assertEqual(_verdicts(report)["AGT-06"], ("verdict", "PASS", "PARTIAL"))
        self.assertEqual(report.problems, {"lost-mention": [], "left-scope": []})

    def test_incident_2_5_the_same_verdict_on_new_evidence_is_reported(self) -> None:
        at = _commit(self.root, {"AGENTS.md": AGENTS_DO_NOT_COPY}, "do not copy")
        report = self._report(at)
        self.assertIn(
            "edited AGENTS.md#agentsmd/2-documentation: read by AGT-06, CON-01", [r.line for r in report.reviews]
        )
        self.assertEqual(_verdicts(report)["CON-01"], ("evidence", "PASS", "PASS"))
        text = cmc.format_text(report)
        self.assertIn("CON-01: same verdict PASS, evidence changed: data.paths, summary", text)
        self.assertIn("consistency map, change mode: 0 problem(s)", text)

    def test_the_working_tree_is_the_new_side_by_default(self) -> None:
        (self.root / "AGENTS.md").write_text(AGENTS_DO_NOT_COPY, encoding="utf-8")
        try:
            report = self._report(None)
        finally:
            _git(self.root, "checkout", "--quiet", "--", "AGENTS.md")
        self.assertEqual(_verdicts(report)["CON-01"], ("evidence", "PASS", "PASS"))
        self.assertIsNone(report.at)

    def test_a_kept_section_that_lost_its_mention_fails(self) -> None:
        at = _commit(self.root, {"docs/keeps.md": KEEPS_UNMENTIONED}, "unmention")
        report = cmc.change_report(FIXTURE_MAP, self.root, self.base, at, CONFIG, engine_dir=None)
        self.assertEqual(
            report.problems["lost-mention"],
            ["renumber -> AGT-06: docs/keeps.md#keeps/boundaries no longer mentions it"],
        )
        self.assertIsNone(report.evidence)
        self.assertIn("evidence: not compared (--no-evidence)", cmc.format_text(report))

    def test_a_reads_file_renamed_out_of_its_scope_fails(self) -> None:
        _git(self.root, "mv", "AGENTS.md", "docs/AGENTS.md")
        _git(self.root, "commit", "--quiet", "--no-gpg-sign", "-m", "move")
        at = _git(self.root, "rev-parse", "HEAD")
        report = cmc.change_report(FIXTURE_MAP, self.root, self.base, at, CONFIG, engine_dir=None)
        self.assertEqual(
            report.problems["left-scope"],
            [
                "AGENTS.md -> docs/AGENTS.md leaves the scope of AGT-06 (AGENTS.md, root)",
                "AGENTS.md -> docs/AGENTS.md leaves the scope of CON-01 (AGENTS.md, root)",
            ],
        )
        self.assertEqual(report.checks(), {"AGT-06", "CON-01"})
        self.assertEqual(cmc.to_dict(report)["left-scope"], report.problems["left-scope"])

    def test_a_ref_that_names_no_commit_raises(self) -> None:
        with self.assertRaises(GitError):
            cmc.change_report(FIXTURE_MAP, self.root, "no-such-ref", None, CONFIG, engine_dir=None)


# --- Unit tests ---------------------------------------------------------------------------------------------------


def _read(texts: dict[str, str]) -> consistency_map.Reader:
    def read(path: str) -> str:
        if path not in texts:
            raise FileNotFoundError(path)
        return texts[path]

    return read


KEEP = FIXTURE_MAP["keeps"][0]


class LostMentionTest(unittest.TestCase):
    def test_an_unchanged_mention_is_not_lost(self) -> None:
        read = _read({"docs/keeps.md": KEEPS_BASE})
        self.assertEqual(cmc.lost_mentions([KEEP], IndexDiff(), read, read), [])

    def test_a_section_that_never_mentioned_the_check_is_left_to_the_static_gate(self) -> None:
        read = _read({"docs/keeps.md": KEEPS_UNMENTIONED})
        self.assertEqual(cmc.lost_mentions([KEEP], IndexDiff(), read, read), [])

    def test_a_removed_section_lost_its_mention(self) -> None:
        old, new = _read({"docs/keeps.md": KEEPS_BASE}), _read({"docs/keeps.md": "# Keeps\n"})
        self.assertEqual(
            cmc.lost_mentions([KEEP], IndexDiff(), old, new),
            ["renumber -> AGT-06: docs/keeps.md#keeps/boundaries is gone"],
        )

    def test_a_moved_section_is_followed_forward_when_the_map_names_the_old_address(self) -> None:
        moved = IndexDiff(moved=(Moved("docs/keeps.md#keeps/boundaries", "docs/keeps.md#keeps/rules/boundaries", ""),))
        new_text = "# Keeps\n\n## Rules\n\n### Boundaries\n\nnothing here\n"
        lost = cmc.lost_mentions(
            [KEEP], moved, _read({"docs/keeps.md": KEEPS_BASE}), _read({"docs/keeps.md": new_text})
        )
        self.assertEqual(
            lost,
            [
                "renumber -> AGT-06: docs/keeps.md#keeps/rules/boundaries (was docs/keeps.md#keeps/boundaries) "
                "no longer mentions it"
            ],
        )

    def test_a_moved_section_is_followed_back_when_the_map_names_the_new_address(self) -> None:
        keep = {**KEEP, "home": {**KEEP["home"], "section": "docs/other.md#other/boundaries"}}
        renamed = IndexDiff(
            renamed=(Renamed("docs/keeps.md#keeps/boundaries", "docs/other.md#other/boundaries", "", ""),)
        )
        old = _read({"docs/keeps.md": KEEPS_BASE})
        kept = _read({"docs/other.md": "# Other\n\n## Boundaries\n\nAGT-06 still here\n"})
        lost = _read({"docs/other.md": "# Other\n\n## Boundaries\n\ngone\n"})
        self.assertEqual(cmc.lost_mentions([keep], renamed, old, kept), [])
        self.assertEqual(len(cmc.lost_mentions([keep], renamed, old, lost)), 1)

    def test_an_ancestor_move_carries_its_children(self) -> None:
        forward = {"a.md#x": "b.md#y"}
        self.assertEqual(cmc._follow("a.md#x/z/w", forward), "b.md#y/z/w")
        self.assertEqual(cmc._follow("a.md#x", forward), "b.md#y")
        self.assertEqual(cmc._follow("a.md#q", forward), "a.md#q")
        self.assertEqual(cmc._follow("a.md", forward), "a.md")

    def test_an_accepted_keep_is_skipped(self) -> None:
        accepted = {**KEEP, "status": "accepted"}
        old, new = _read({"docs/keeps.md": KEEPS_BASE}), _read({"docs/keeps.md": KEEPS_UNMENTIONED})
        self.assertEqual(cmc.lost_mentions([accepted], IndexDiff(), old, new), [])

    def test_an_edited_section_under_a_moved_parent_maps_both_ways(self) -> None:
        found = IndexDiff(edited=(Edited(address="b.md#y", old_address="a.md#x"),))
        forward, backward = cmc._address_maps(found)
        self.assertEqual((forward, backward), ({"a.md#x": "b.md#y"}, {"b.md#y": "a.md#x"}))


READS = FIXTURE_MAP["reads"]


class ReviewTest(unittest.TestCase):
    def test_a_template_is_read_at_its_scaffolded_path(self) -> None:
        self.assertEqual(
            cmc.scaffold_targets("greenfield/templates/AGENTS.md"), ["greenfield/templates/AGENTS.md", "AGENTS.md"]
        )
        self.assertEqual(
            cmc.scaffold_targets("greenfield/templates/github/workflows/ci.yml"),
            ["greenfield/templates/github/workflows/ci.yml", ".github/workflows/ci.yml"],
        )
        self.assertEqual(cmc.scaffold_targets("docs/x.md"), ["docs/x.md"])
        self.assertIn("AGT-06", cmc.readers("greenfield/templates/AGENTS.md", REAL_MAP["reads"]))

    def test_section_changes_in_read_files_are_listed_with_their_checks(self) -> None:
        found = IndexDiff(
            moved=(Moved("AGENTS.md#a/testing", "docs/testing.md#testing", "Testing"),),
            edited=(Edited("AGENTS.md#a/never", "AGENTS.md#a/never"),),
            renamed=(Renamed("docs/x.md#x", "docs/x.md#y", "X", "Y"),),
        )
        lines = [review.line for review in cmc.reviews(found, [], READS, lambda path: [path])]
        self.assertEqual(
            lines,
            [
                "moved AGENTS.md#a/testing -> docs/testing.md#testing (leaves the scope of AGT-06, CON-01): "
                "read by AGT-06, CON-01",
                "edited AGENTS.md#a/never: read by AGT-06, CON-01",
            ],
        )

    def test_files_with_no_section_in_the_index_diff_are_listed_by_status(self) -> None:
        files = [
            cmc.FileChange("A", "CLAUDE.md", "CLAUDE.md"),
            cmc.FileChange("M", "AGENTS.md", "AGENTS.md"),
            cmc.FileChange("D", "CLAUDE.md", "CLAUDE.md"),
            cmc.FileChange("R", "CLAUDE.md", "docs/CLAUDE.md"),
            cmc.FileChange("M", "src/a.py", "src/a.py"),
        ]
        lines = [review.line for review in cmc.reviews(IndexDiff(), files, READS, lambda path: [path])]
        self.assertEqual(
            lines,
            [
                "added file CLAUDE.md: read by AGT-06, CON-01",
                "changed file AGENTS.md: read by AGT-06, CON-01",
                "deleted file CLAUDE.md: read by AGT-06, CON-01",
                "renamed file CLAUDE.md -> docs/CLAUDE.md (leaves the scope of AGT-06, CON-01): read by AGT-06, CON-01",
            ],
        )
        renamed = [cmc.FileChange("R", "CLAUDE.json", "x.json")]
        reads = [{"check": "X-01", "where": [{"path": "CLAUDE.json", "scope": "root"}]}]
        self.assertEqual(
            [r.line for r in cmc.reviews(IndexDiff(), renamed, reads, lambda path: [path])],
            ["renamed file CLAUDE.json -> x.json (leaves the scope of X-01): read by X-01"],
        )

    def test_a_rename_inside_the_scope_is_not_a_problem(self) -> None:
        reads = [{"check": "X-01", "where": [{"path": "AGENTS.md", "scope": "any-depth"}]}]
        moved = [cmc.FileChange("R", "AGENTS.md", "docs/AGENTS.md")]
        self.assertEqual(cmc.left_scope(moved, reads, lambda path: [path]), [])
        self.assertEqual(cmc.left_scope([cmc.FileChange("M", "AGENTS.md", "AGENTS.md")], reads), [])


class GitTest(unittest.TestCase):
    def test_file_changes_and_materialise(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch) / "repo"
            base = _fixture_repository(root)
            _git(root, "mv", "docs/keeps.md", "docs/kept.md")
            (root / "new.txt").write_text("n\n", encoding="utf-8")
            (root / "src/core/a.py").write_text("X = 2\n", encoding="utf-8")
            changes = cmc.file_changes(root, base, None)
            self.assertEqual(
                [(c.status, c.old, c.new) for c in changes],
                [
                    ("R", "docs/keeps.md", "docs/kept.md"),
                    ("A", "new.txt", "new.txt"),
                    ("M", "src/core/a.py", "src/core/a.py"),
                ],
            )
            work = cmc.materialise(root, None, Path(scratch) / "work")
            self.assertEqual((work / "src/core/a.py").read_text(encoding="utf-8"), "X = 2\n")
            self.assertTrue((work / "new.txt").is_file())
            self.assertFalse((work / "docs/keeps.md").exists())
            old = cmc.materialise(root, base, Path(scratch) / "old")
            self.assertEqual((old / "src/core/a.py").read_text(encoding="utf-8"), "X = 1\n")
            self.assertEqual(_git(old, "log", "--format=%an %at"), "consistency-map 1767225600")


class ReviewFixesTest(unittest.TestCase):
    """The findings of the RF4.7 review: hook environments, hooks, unparsed Markdown, an unstaged move, type changes."""

    def test_a_hook_environment_does_not_reach_the_copy_or_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch) / "repo"
            base = _fixture_repository(root)
            hooks = Path(scratch) / "hooks"
            hooks.mkdir()
            (hooks / "pre-commit").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            (hooks / "pre-commit").chmod(0o755)
            env = {"GIT_DIR": str(root / ".git"), "GIT_INDEX_FILE": str(root / ".git" / "index")}
            with mock.patch.dict(os.environ, env):
                _git(root, "config", "core.hooksPath", str(hooks))
                copy = cmc.materialise(root, None, Path(scratch) / "copy")
            self.assertTrue((copy / ".git").is_dir())
            self.assertEqual(_git(root, "rev-parse", "HEAD"), base)
            self.assertEqual(_git(copy, "log", "--format=%s"), "consistency map side")

    def test_a_failed_copy_is_an_evidence_error(self) -> None:
        from docindex.evidence import EvidenceError

        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch) / "repo"
            base = _fixture_repository(root)
            with mock.patch.object(cmc, "materialise", side_effect=GitError("boom")):
                with self.assertRaises(EvidenceError):
                    cmc.compare_evidence(root, base, None, consistency_map.ENGINE)

    def test_an_unparsed_markdown_file_is_listed_by_file(self) -> None:
        reads = [{"check": "X-01", "where": [{"path": "AGENTS.md", "scope": "any-depth"}]}]
        files = [
            cmc.FileChange("M", "fixtures/x/AGENTS.md", "fixtures/x/AGENTS.md"),
            cmc.FileChange("M", "AGENTS.md", "AGENTS.md"),
            cmc.FileChange("T", "y/AGENTS.md", "y/AGENTS.md"),
            cmc.FileChange("C", "AGENTS.md", "z/AGENTS.md"),
        ]
        found = IndexDiff(edited=(Edited("AGENTS.md#a", "AGENTS.md#a"),))
        self.assertEqual(
            [r.line for r in cmc.reviews(found, files, reads, lambda path: [path])],
            [
                "edited AGENTS.md#a: read by X-01",
                "changed file fixtures/x/AGENTS.md: read by X-01",
                "changed file y/AGENTS.md: read by X-01",
                "copied file AGENTS.md -> z/AGENTS.md: read by X-01",
            ],
        )

    def test_an_unstaged_move_counts_as_a_rename(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch) / "repo"
            base = _fixture_repository(root)
            (root / "AGENTS.md").rename(root / "docs" / "AGENTS.md")
            (root / "src/core/a.py").unlink()
            (root / "other.txt").write_text("other\n", encoding="utf-8")
            changes = [(c.status, c.old, c.new) for c in cmc.file_changes(root, base, None)]
            self.assertEqual(
                changes,
                [
                    ("R", "AGENTS.md", "docs/AGENTS.md"),
                    ("A", "other.txt", "other.txt"),
                    ("D", "src/core/a.py", "src/core/a.py"),
                ],
            )
            files = cmc.file_changes(root, base, None)
            self.assertEqual(len(cmc.left_scope(files, FIXTURE_MAP["reads"], lambda path: [path])), 2)

    def test_untracked_files_with_nothing_deleted_are_added(self) -> None:
        self.assertEqual(cmc._pair_untracked(Path("."), "HEAD", [], ["a"]), [cmc.FileChange("A", "a", "a")])

    def test_the_manual_tar_check_refuses_an_escaping_member(self) -> None:
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w") as archive:
            info = tarfile.TarInfo("../escape.txt")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
        with tempfile.TemporaryDirectory() as scratch, mock.patch.object(tarfile, "data_filter", create=True):
            delattr(tarfile, "data_filter")
            with self.assertRaises(GitError):
                cmc._safe_extract(data.getvalue(), Path(scratch))


def _change(check: str) -> Any:
    from docindex.evidence import CheckChange

    return CheckChange("repo", check, "PASS", "PASS", ("summary",))


class OutputTest(unittest.TestCase):
    def test_split_and_format(self) -> None:
        from docindex.evidence import CheckChange, Comparison

        comparison = Comparison(
            (), (), (_change("AGT-06"), _change("NAV-05"), CheckChange("repo", "X-01", None, "PASS", ()))
        )
        split = cmc.split_evidence(comparison, {"AGT-06"})
        report = cmc.ChangeReport(base="b", at="a", evidence=split)
        text = cmc.format_text(report)
        self.assertIn("change mode: b -> a", text)
        self.assertIn("  AGT-06: same verdict PASS, evidence changed: summary", text)
        self.assertIn("  and 2 changed check(s) whose reads the change does not touch", text)
        self.assertEqual(cmc._change_line(comparison.changes[2]), "X-01: check added")
        data = cmc.to_dict(report)
        self.assertEqual([c["check"] for c in data["evidence"]["others"]], ["NAV-05", "X-01"])
        self.assertEqual(data["lost-mention"], [])


#: A tree of 60 distinct names (a broad place needs 3): 20 Python files, 10 docs pages, 11 copies of package.json.
BROAD_TREE = (
    [f"src/m{n}.py" for n in range(20)]
    + [f"docs/how-to/p{n}.md" for n in range(10)]
    + [f"tests/fixtures/f{n}/package.json" for n in range(10)]
    + ["package.json", "AGENTS.md", "Makefile"]
    + [f".github/workflows/w{n}.yml" for n in range(2)]
    + [f"x{n}.txt" for n in range(25)]
)
BROAD_READS: list[dict[str, Any]] = [
    {"check": "ALL-01", "where": [{"path": "**", "scope": "glob"}]},
    {"check": "PY-01", "where": [{"path": "*.py", "scope": "any-depth"}]},
    {"check": "DOC-09", "where": [{"path": "docs/**/*.md", "scope": "glob"}]},
    {"check": "PKG-01", "where": [{"path": "package.json", "scope": "any-depth"}]},
    {"check": "CI-09", "where": [{"path": ".github/workflows/*.yml", "scope": "glob"}]},
    {"check": "ROOT-01", "where": [{"path": "*.md", "scope": "root"}]},
    {
        "check": "MIX-01",
        "where": [{"path": "**", "scope": "glob"}, {"path": "AGENTS.md", "scope": "root"}],
    },
]


def _broad_review(paths: list[str]) -> cmc.Review:
    files = [cmc.FileChange("M", path, path) for path in paths]
    broad = cmc.broad_places(BROAD_READS, BROAD_TREE)
    (review,) = cmc.reviews(IndexDiff(), files, BROAD_READS, lambda path: [path], broad)
    return review


class BroadReadTest(unittest.TestCase):
    """Broad reads: a place that covers every file of a kind is named once, not on each review line."""

    def test_a_wildcard_place_over_a_large_share_of_the_names_is_broad(self) -> None:
        self.assertEqual(
            cmc.broad_places(BROAD_READS, BROAD_TREE),
            {("**", "glob"), ("*.py", "any-depth"), ("docs/**/*.md", "glob")},
        )

    def test_one_name_in_many_folders_a_small_glob_and_a_root_place_are_specific(self) -> None:
        broad = cmc.broad_places(BROAD_READS, BROAD_TREE)
        self.assertNotIn(("package.json", "any-depth"), broad)  # 11 files, one name
        self.assertNotIn((".github/workflows/*.yml", "glob"), broad)  # 2 of 60 names
        self.assertNotIn(("*.md", "root"), broad)  # a root place is never broad
        self.assertEqual(cmc.broad_places(BROAD_READS, BROAD_TREE, share=0.6), {("**", "glob")})

    def test_a_check_with_a_specific_place_over_the_path_is_specific(self) -> None:
        broad = cmc.broad_places(BROAD_READS, BROAD_TREE)
        self.assertEqual(cmc.broad_readers(["AGENTS.md"], BROAD_READS, broad, lambda path: [path]), {"ALL-01"})
        self.assertEqual(
            cmc.broad_readers(["src/m1.py"], BROAD_READS, broad, lambda path: [path]), {"ALL-01", "MIX-01", "PY-01"}
        )

    def test_a_review_keeps_every_check_and_marks_the_broad_ones(self) -> None:
        review = _broad_review(["AGENTS.md"])
        self.assertEqual(review.checks, ("ALL-01", "MIX-01", "ROOT-01"))
        self.assertEqual(review.broad, ("ALL-01",))
        self.assertEqual(review.specific, ("MIX-01", "ROOT-01"))
        self.assertEqual(review.line, "changed file AGENTS.md: read by ALL-01, MIX-01, ROOT-01")
        self.assertEqual(review.place, "changed file AGENTS.md")

    def test_the_text_names_specific_checks_per_line_and_broad_checks_once(self) -> None:
        report = cmc.ChangeReport(base="b", at="a")
        report.reviews = [
            _broad_review(["AGENTS.md"]),
            _broad_review(["src/m1.py"]),
            _broad_review(["src/m2.py"]),
            _broad_review(["package.json"]),
        ]
        text = cmc.format_text(report)
        self.assertIn("review (sections and files a read covers; not a problem): 4\n", text)
        self.assertIn("  changed file AGENTS.md: read by MIX-01, ROOT-01\n", text)
        self.assertIn("  changed file package.json: read by PKG-01\n", text)
        self.assertIn("  and 2 more read only by broad checks (--verbose lists them)\n", text)
        self.assertIn("  broad checks, which read every file of a kind: ALL-01, MIX-01, PY-01\n", text)
        self.assertNotIn("src/m1.py", text)
        verbose = cmc.format_text(report, verbose=True)
        self.assertIn("  changed file AGENTS.md: read by MIX-01, ROOT-01; and by broad checks ALL-01\n", verbose)
        self.assertIn("  changed file src/m1.py: read only by broad checks ALL-01, MIX-01, PY-01\n", verbose)
        self.assertNotIn("more read only by broad checks", verbose)

    def test_a_review_with_no_broad_reader_prints_its_full_line(self) -> None:
        report = cmc.ChangeReport(base="b", at="a")
        report.reviews = [cmc.Review("edited a.md#a: read by X-01", ("X-01",))]
        text = cmc.format_text(report)
        self.assertIn("  edited a.md#a: read by X-01\n", text)
        self.assertNotIn("broad checks", text)

    def test_the_json_and_the_evidence_overlap_keep_every_check(self) -> None:
        report = cmc.ChangeReport(base="b", at="a")
        report.reviews = [_broad_review(["src/m1.py"])]
        entry = cmc.to_dict(report)["review"][0]
        self.assertEqual(entry["checks"], ["ALL-01", "MIX-01", "PY-01"])
        self.assertEqual(entry["broad"], ["ALL-01", "MIX-01", "PY-01"])
        self.assertEqual(entry["line"], "changed file src/m1.py: read by ALL-01, MIX-01, PY-01")
        self.assertEqual(report.checks(), {"ALL-01", "MIX-01", "PY-01"})

    def test_this_repository_classifies_the_whole_tree_glob_as_broad_and_named_files_as_specific(self) -> None:
        from docindex.gitread import WorkTree

        broad = cmc.broad_places(REAL_MAP["reads"], WorkTree(_dev_paths.REPO).files())
        self.assertIn(("**", "glob"), broad)
        self.assertNotIn(("package.json", "any-depth"), broad)
        self.assertNotIn(("AGENTS.md", "root"), broad)


class MainTest(unittest.TestCase):
    def _main(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            try:
                code = consistency_map.main(argv)
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, out.getvalue()

    def test_at_without_base_is_a_usage_error(self) -> None:
        self.assertEqual(self._main(["--at", "HEAD"])[0], 2)
        self.assertEqual(self._main(["--no-evidence"])[0], 2)

    def test_a_bad_base_is_a_usage_error(self) -> None:
        with mock.patch.object(cmc, "change_report", side_effect=GitError("bad ref")):
            self.assertEqual(self._main(["--base", "nope", "--no-evidence"])[0], 2)

    def test_a_failed_engine_run_exits_1(self) -> None:
        from docindex.evidence import EvidenceError

        with mock.patch.object(cmc, "change_report", side_effect=EvidenceError("engine")):
            self.assertEqual(self._main(["--base"])[0], 1)

    def test_change_mode_is_appended_to_the_report_and_counts_in_strict_mode(self) -> None:
        report = cmc.ChangeReport(base=cmc.DEFAULT_BASE, at=None)
        report.problems["left-scope"] = ["a -> b leaves the scope of X-01 (a, root)"]
        with (
            mock.patch.object(cmc, "change_report", return_value=report) as called,
            mock.patch.object(consistency_map, "report", return_value={kind: [] for kind in consistency_map.KINDS}),
        ):
            code, text = self._main(["--base"])
            self.assertEqual(code, 0)
            self.assertIn("change mode: origin/dev -> the working tree", text)
            self.assertEqual(called.call_args.args[2:4], ("origin/dev", None))
            self.assertEqual(self._main(["--base", "--strict"])[0], 1)
            code, text = self._main(["--base", "HEAD", "--at", "HEAD", "--no-evidence", "--format", "json"])
            self.assertEqual(json.loads(text)["change"]["left-scope"], report.problems["left-scope"])
            self.assertIsNone(called.call_args.kwargs["engine_dir"])

    def test_verbose_reaches_the_change_report_text(self) -> None:
        report = cmc.ChangeReport(base=cmc.DEFAULT_BASE, at=None)
        report.reviews = [_broad_review(["src/m1.py"])]
        with (
            mock.patch.object(cmc, "change_report", return_value=report),
            mock.patch.object(consistency_map, "report", return_value={kind: [] for kind in consistency_map.KINDS}),
        ):
            self.assertIn("and 1 more read only by broad checks", self._main(["--base"])[1])
            self.assertIn("src/m1.py: read only by broad checks", self._main(["--base", "--verbose"])[1])

    def test_change_mode_on_this_repository_against_head(self) -> None:
        report = cmc.change_report(REAL_MAP, _dev_paths.REPO, "HEAD", "HEAD", cmc.project_config(), engine_dir=None)
        self.assertEqual((report.reviews, report.problems), ([], {"lost-mention": [], "left-scope": []}))


if __name__ == "__main__":
    unittest.main()
