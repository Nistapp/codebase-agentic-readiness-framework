# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`--exclude` takes a path out of the audit for every check, including those that ask git what it tracks.

The walk always honoured it. SEC-01, DOC-03, CON-03 and EXEC-02 read ``git ls-files`` instead of the walk, so a
tracked ``.env`` in a directory the operator had excluded was still a BLOCKER (S0.5 self-audit: the engine's own
fixtures). They now ask :func:`audit.rules.checks._common.tracked_in_scope`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks._common import tracked_in_scope  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.target import resolve_target  # noqa: E402


def git(root: Path, *args: str) -> None:
    done = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)
    assert done.returncode == 0, done.stderr


def copy_into_repository(name: str, force: str, tmp: str) -> Path:
    target = Path(tmp) / name
    shutil.copytree(support.fixture(name), target)
    git(target, "init", "-q")
    git(target, "add", "-A")
    git(target, "add", "-f", force)
    return target


class InventoryExcludeTests(unittest.TestCase):
    def inventory(self, files: dict[str, str], excludes: tuple[str, ...]):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return build_inventory(root, extra_excludes=excludes)

    def test_a_glob_matches_the_whole_relative_path_and_a_star_crosses_directories(self):
        inventory = self.inventory({}, ("vendor/*", "docs/a.md"))
        self.assertTrue(inventory.is_excluded("vendor/x"))
        self.assertTrue(inventory.is_excluded("vendor/deep/er/x"))
        self.assertTrue(inventory.is_excluded("docs/a.md"))
        self.assertFalse(inventory.is_excluded("docs/b.md"))
        self.assertFalse(inventory.is_excluded("other/vendor/x"))
        self.assertFalse(inventory.is_excluded("vendor"))

    def test_nothing_is_excluded_by_default(self):
        self.assertEqual(self.inventory({}, ()).excludes, ())
        self.assertFalse(self.inventory({}, ()).is_excluded("anything"))

    def test_the_walk_skips_an_excluded_file_and_says_why(self):
        inventory = self.inventory({"samples/a.txt": "x", "src/b.txt": "y"}, ("samples/*",))
        self.assertEqual([f.rel for f in inventory.files], ["src/b.txt"])
        self.assertEqual(inventory.skipped, [("samples/a.txt", "ignored")])
        self.assertEqual(inventory.excludes, ("samples/*",))


class TrackedInScopeTests(unittest.TestCase):
    def repository(self, tmp: str, files: tuple[str, ...]) -> Path:
        root = Path(tmp)
        for rel in files:
            support.write(root, rel, "x\n")
        git(root, "init", "-q")
        git(root, "add", "-A")
        return root

    def scope(self, root: Path, excludes: tuple[str, ...]):
        inventory = build_inventory(root, extra_excludes=excludes)
        return tracked_in_scope(resolve_target(root), inventory)

    def test_the_tracked_set_less_what_was_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repository(tmp, ("a/x.txt", "b/y.txt", "b/z.txt", "top.txt"))
            self.assertEqual(self.scope(root, ()), {"a/x.txt", "b/y.txt", "b/z.txt", "top.txt"})
            self.assertEqual(self.scope(root, ("b/*",)), {"a/x.txt", "top.txt"})
            self.assertEqual(self.scope(root, ("b/y.txt", "top.txt")), {"a/x.txt", "b/z.txt"})

    def test_a_path_that_is_ignored_by_rule_but_tracked_is_still_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repository(tmp, ("a/x.txt",))
            support.write(root, ".gitignore", "kept.log\n")
            support.write(root, "kept.log", "x\n")
            git(root, "add", "-f", "kept.log")
            self.assertIn("kept.log", self.scope(root, ("a/*",)) or set())

    def test_git_that_cannot_answer_is_none_and_not_an_empty_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "a.txt", "x\n")
            self.assertIsNone(self.scope(root, ("a.txt",)))


class ExcludeVerdictTests(unittest.TestCase):
    def verdicts(self, name: str, force: str, *excludes: str) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            target = copy_into_repository(name, force, tmp)
            args = tuple(arg for pattern in excludes for arg in ("--exclude", pattern))
            return support.verdicts(support.run_audit(target, extra_args=args))

    def test_a_tracked_env_in_an_excluded_directory_is_no_longer_a_blocker(self):
        force = "vendor-samples/.env"
        self.assertEqual(self.verdicts("sec-01-excluded-env", force)["SEC-01"], "FAIL")
        self.assertEqual(self.verdicts("sec-01-excluded-env", force, "vendor-samples/*")["SEC-01"], "PASS")

    def test_an_exclusion_that_misses_the_file_changes_nothing(self):
        force = "vendor-samples/.env"
        self.assertEqual(self.verdicts("sec-01-excluded-env", force, "other/*")["SEC-01"], "FAIL")
        self.assertEqual(self.verdicts("sec-01-excluded-env", force, "vendor-samples")["SEC-01"], "FAIL")

    def test_tracked_scratch_files_are_out_of_scope_for_doc_03_and_con_03_when_excluded(self):
        force = "artefacts/notes.md"
        before = self.verdicts("doc-03-tracked-artefacts", force)
        after = self.verdicts("doc-03-tracked-artefacts", force, "artefacts/*")
        self.assertEqual((before["DOC-03"], before["CON-03"]), ("FAIL", "FAIL"))
        self.assertEqual((after["DOC-03"], after["CON-03"]), ("PASS", "PASS"))


if __name__ == "__main__":
    unittest.main()
