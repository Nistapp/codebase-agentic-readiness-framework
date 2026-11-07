# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The bounded walk (``audit.scan.build_inventory``): its caps, what it never follows, and what it skips and why.

Every skipped path is recorded with a reason, so a report can say what it did not look at.
"""

from __future__ import annotations

import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.scan import FileEntry, Kind, build_inventory  # noqa: E402


class WalkTests(unittest.TestCase):
    def walk(self, files: dict[str, str | bytes], **options):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, content in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    path.write_bytes(content)
                else:
                    path.write_text(content, encoding="utf-8")
            return build_inventory(root, **options)

    def test_the_caps_default_to_a_quarter_of_a_million_files_and_twenty_four_levels(self):
        parameters = inspect.signature(build_inventory).parameters
        self.assertEqual(parameters["max_files"].default, 250_000)
        self.assertEqual(parameters["max_depth"].default, 24)
        self.assertEqual(parameters["extra_excludes"].default, ())

    def test_a_directory_at_the_depth_cap_is_not_entered_and_is_named(self):
        inventory = self.walk({"a/one.txt": "x", "a/b/two.txt": "x", "a/b/c/three.txt": "x"}, max_depth=2)
        self.assertEqual([f.rel for f in inventory.files], ["a/one.txt"])
        self.assertEqual(inventory.skipped, [("a/b", "max-depth")])

    def test_a_directory_just_inside_the_depth_cap_is_walked(self):
        inventory = self.walk({"a/one.txt": "x", "a/b/two.txt": "x"}, max_depth=3)
        self.assertEqual([f.rel for f in inventory.files], ["a/one.txt", "a/b/two.txt"])
        self.assertEqual(inventory.skipped, [])

    def test_the_file_cap_truncates_the_walk_and_says_so(self):
        inventory = self.walk({"a.txt": "x", "b.txt": "x", "c.txt": "x"}, max_files=2)
        self.assertEqual([f.rel for f in inventory.files], ["a.txt", "b.txt"])
        self.assertTrue(inventory.truncated)

    def test_a_walk_that_just_fits_is_not_truncated(self):
        inventory = self.walk({"a.txt": "x", "b.txt": "x", "c.txt": "x"}, max_files=3)
        self.assertEqual(len(inventory.files), 3)
        self.assertFalse(inventory.truncated)

    def test_the_file_cap_stops_the_walk_of_the_directories_after_it(self):
        inventory = self.walk({"a.txt": "x", "z/deep.txt": "x"}, max_files=1)
        self.assertEqual([f.rel for f in inventory.files], ["a.txt"])
        self.assertTrue(inventory.truncated)

    def test_a_symlinked_file_is_skipped_and_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "real.txt", "x")
            os.symlink(root / "real.txt", root / "link.txt")
            inventory = build_inventory(root)
        self.assertEqual([f.rel for f in inventory.files], ["real.txt"])
        self.assertEqual(inventory.skipped, [("link.txt", "symlink")])

    def test_a_symlinked_directory_is_not_entered(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
            support.write(Path(elsewhere), "outside.txt", "x")
            root = Path(tmp)
            support.write(root, "inside.txt", "x")
            os.symlink(elsewhere, root / "link")
            inventory = build_inventory(root)
        self.assertEqual([f.rel for f in inventory.files], ["inside.txt"])

    def test_a_hard_excluded_directory_and_a_directory_an_ignore_rule_names_are_not_entered(self):
        inventory = self.walk(
            {
                "node_modules/x.js": "x",
                ".gitignore": "skipme\n",
                "skipme/a.txt": "x",
                "kept/b.txt": "x",
            }
        )
        self.assertEqual([f.rel for f in inventory.files], [".gitignore", "kept/b.txt"])

    def test_a_file_an_ignore_rule_names_is_skipped_and_named(self):
        inventory = self.walk({".gitignore": "*.log\n", "run.log": "x", "run.txt": "x"})
        self.assertEqual([f.rel for f in inventory.files], [".gitignore", "run.txt"])
        self.assertEqual(inventory.skipped, [("run.log", "ignored")])

    def test_a_file_that_cannot_be_statted_is_skipped_and_named(self):
        real_stat = Path.stat

        def stat(self, *args, follow_symlinks=True, **kwargs):
            # `is_symlink` asks for `stat(follow_symlinks=False)` on Python 3.11; only the walk's own call may fail.
            if self.name == "bad.txt" and follow_symlinks:
                raise PermissionError("denied")
            return real_stat(self, *args, follow_symlinks=follow_symlinks, **kwargs)

        with mock.patch.object(Path, "stat", stat):
            inventory = self.walk({"bad.txt": "x", "good.txt": "x"})
        self.assertEqual([f.rel for f in inventory.files], ["good.txt"])
        self.assertEqual(inventory.skipped, [("bad.txt", "unreadable")])

    def test_an_empty_file_is_text_of_size_zero_and_a_one_byte_file_has_its_size(self):
        inventory = self.walk({"empty.py": "", "one.py": "x"})
        self.assertEqual(
            inventory.files,
            [FileEntry("empty.py", 0, Kind.SOURCE, True), FileEntry("one.py", 1, Kind.SOURCE, True)],
        )

    def test_a_file_with_a_nul_byte_is_binary_and_has_no_text(self):
        inventory = self.walk({"data.py": b"abc\x00def"})
        self.assertEqual(inventory.files, [FileEntry("data.py", 7, Kind.BINARY, False)])

    def test_a_text_file_is_classified_by_its_path(self):
        inventory = self.walk({"README.md": "hello"})
        self.assertEqual(inventory.files, [FileEntry("README.md", 5, Kind.DOC, True)])

    def test_files_and_directories_are_visited_in_sorted_order(self):
        inventory = self.walk({"b/z.txt": "x", "a/y.txt": "x", "c.txt": "x", "a.txt": "x"})
        self.assertEqual([f.rel for f in inventory.files], ["a.txt", "c.txt", "a/y.txt", "b/z.txt"])


if __name__ == "__main__":
    unittest.main()
