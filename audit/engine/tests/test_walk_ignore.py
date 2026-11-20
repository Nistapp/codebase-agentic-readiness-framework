# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""What the walk skips: the scoped ignore matcher (ADR-0009) and git's tracked set (issues #179, #146, #22).

The walk reads the root ignore files and each nested ``.gitignore`` with anchoring, ``**`` and ``!``. A file git
tracks stays in the inventory whatever the rules say; an untracked file an ignore rule covers never enters it.
These tests run the walk in-process, so coverage traces it.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.report.md_render import render_markdown  # noqa: E402
from audit.scan import Kind, _classify, build_inventory  # noqa: E402


def _git(root: Path, *args: str) -> None:
    done = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)
    assert done.returncode == 0, done.stderr


class ParserWalkTests(unittest.TestCase):
    """A directory that is not a git repository: the ignore files alone decide."""

    def walk(self, files: dict[str, str]):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            inventory = build_inventory(root)
        return inventory, [entry.rel for entry in inventory.files]

    def test_an_anchored_rule_prunes_the_root_directory_it_names(self):
        inventory, files = self.walk(
            {
                ".gitignore": "/out/\n/.claude/worktrees/\n",
                "out/a.py": "x",
                ".claude/worktrees/copy/AGENTS.md": "x",
                ".claude/settings.json": "{}",
                "pkg/out/b.py": "x",
            }
        )
        self.assertEqual(files, [".gitignore", ".claude/settings.json", "pkg/out/b.py"])
        self.assertEqual(inventory.ignored_dirs, [".claude/worktrees", "out"])

    def test_a_negation_re_includes_a_template_beside_an_ignored_shape(self):
        inventory, files = self.walk(
            {".gitignore": ".env\n.env.*\n!.env.example\n", ".env.example": "FOO=\n", ".env.local": "FOO=\n"}
        )
        self.assertEqual(files, [".env.example", ".gitignore"])
        self.assertEqual(inventory.skipped, [(".env.local", "ignored")])

    def test_a_negation_cannot_bring_a_file_out_of_an_ignored_directory(self):
        inventory, files = self.walk({".gitignore": "cache/\n!cache/keep.txt\n", "cache/keep.txt": "x"})
        self.assertEqual(files, [".gitignore"])
        self.assertEqual(inventory.ignored_dirs, ["cache"])

    def test_a_nested_ignore_file_prunes_only_inside_its_own_directory(self):
        _inventory, files = self.walk(
            {"tools/.gitignore": "cache/\n", "tools/cache/a.py": "x", "cache/b.py": "x", "tools/c.py": "x"}
        )
        self.assertEqual(files, ["cache/b.py", "tools/.gitignore", "tools/c.py"])

    def test_a_double_star_rule_matches_at_any_depth(self):
        _inventory, files = self.walk(
            {".gitignore": "docs/**/draft.md\n", "docs/a/b/draft.md": "x", "docs/draft.md": "x", "docs/a/final.md": "x"}
        )
        self.assertEqual(files, [".gitignore", "docs/a/final.md"])

    def test_a_tool_ignore_file_at_the_root_still_prunes(self):
        inventory, files = self.walk({".cbmignore": "/artefacts/\n", "artefacts/plan.md": "x", "src/a.py": "x"})
        self.assertEqual(files, [".cbmignore", "src/a.py"])
        self.assertEqual(inventory.ignored_dirs, ["artefacts"])


class TrackedWalkTests(unittest.TestCase):
    """A git repository: a tracked file is never skipped by an ignore rule."""

    def test_a_tracked_file_under_an_ignored_directory_stays_and_its_untracked_sibling_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "data/keep.txt", "x")
            support.write(root, "data/deep/kept.txt", "x")
            _git(root, "init", "-q")
            _git(root, "add", "-A")
            support.write(root, ".gitignore", "/data/\n*.log\n")
            support.write(root, "data/runtime.db", "x")
            support.write(root, "data/deep/runtime.db", "x")
            support.write(root, "data/other/runtime.db", "x")
            support.write(root, "forced.log", "x")
            support.write(root, "run.log", "x")
            _git(root, "add", "-f", "forced.log")
            inventory = build_inventory(root)
        self.assertEqual(
            [entry.rel for entry in inventory.files],
            [".gitignore", "forced.log", "data/keep.txt", "data/deep/kept.txt"],
        )
        self.assertEqual(
            sorted(inventory.skipped),
            [("data/deep/runtime.db", "ignored"), ("data/runtime.db", "ignored"), ("run.log", "ignored")],
        )
        self.assertEqual(inventory.ignored_dirs, ["data/other"])

    def test_an_exclude_still_removes_a_tracked_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "kept.log", "x")
            _git(root, "init", "-q")
            _git(root, "add", "-A")
            support.write(root, ".gitignore", "*.log\n")
            inventory = build_inventory(root, extra_excludes=("kept.log",))
        self.assertEqual([entry.rel for entry in inventory.files], [".gitignore"])


class TrackedBuildOutputTests(unittest.TestCase):
    """``dist/`` and ``build/`` are entered only for the files git tracks under them (issue #12, option C)."""

    def test_tracked_build_output_enters_and_untracked_output_beside_it_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "dist/app.min.js", "x")
            support.write(root, "pkg/build/deep/x.class", "x")
            support.write(root, "vendor/lib.go", "x")
            support.write(root, "dist/node_modules/m.js", "x")
            _git(root, "init", "-q")
            _git(root, "add", "-A")
            support.write(root, "dist/fresh.js", "x")
            support.write(root, "dist/chunks/c.js", "x")
            support.write(root, "build/out.js", "x")
            inventory = build_inventory(root)
        self.assertEqual([entry.rel for entry in inventory.files], ["dist/app.min.js", "pkg/build/deep/x.class"])
        self.assertEqual(inventory.skipped, [])
        self.assertEqual(inventory.ignored_dirs, [])

    def test_an_ignore_rule_does_not_hide_a_tracked_build_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "dist/app.js", "x")
            _git(root, "init", "-q")
            _git(root, "add", "-A")
            support.write(root, ".gitignore", "dist/\n")
            support.write(root, "dist/fresh.js", "x")
            inventory = build_inventory(root, extra_excludes=())
            excluded = build_inventory(root, extra_excludes=("dist/*",))
        self.assertEqual([entry.rel for entry in inventory.files], [".gitignore", "dist/app.js"])
        self.assertEqual([entry.rel for entry in excluded.files], [".gitignore"])

    def test_without_git_the_build_folders_stay_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "dist/app.js", "x")
            support.write(root, "build/x.class", "x")
            support.write(root, "src/a.py", "x")
            inventory = build_inventory(root)
        self.assertEqual([entry.rel for entry in inventory.files], ["src/a.py"])

    def test_the_generated_hint_matches_a_whole_folder_name(self):
        for rel in ("dist/app.js", "pkg/build/x.class", "Build/out.txt", "lib/dist/deep/a.py"):
            with self.subTest(rel=rel):
                self.assertIs(_classify(rel), Kind.GENERATED)
        for rel in ("redist/a.py", "prebuild/a.py", "build.py", "src/dist.py", "myvendor/a.py"):
            with self.subTest(rel=rel):
                self.assertIsNot(_classify(rel), Kind.GENERATED)


class IgnoredDirsReportTests(unittest.TestCase):
    def test_the_report_names_the_directories_the_walk_did_not_enter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            support.write(root, ".gitignore", "/scratch/\n")
            support.write(root, "scratch/a.txt", "x")
            support.write(root, "README.md", "# x\n")
            report = support.run_audit(root)
        self.assertEqual(report["inventory"]["ignored_dirs"], ["scratch"])
        markdown = render_markdown(report)
        self.assertIn(
            "Not walked, because an ignore file covers them and git tracks nothing in them: `scratch`", markdown
        )

    def test_a_long_list_is_cut_after_twenty_names(self):
        files = {".gitignore": "/d*/\n", **{f"d{index:02d}/a.txt": "x" for index in range(23)}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            for rel, text in files.items():
                support.write(root, rel, text)
            report = support.run_audit(root)
        self.assertEqual(len(report["inventory"]["ignored_dirs"]), 23)
        markdown = render_markdown(report)
        self.assertIn("`d19`, and 3 more", markdown)
        self.assertNotIn("`d20`", markdown)


if __name__ == "__main__":
    unittest.main()
