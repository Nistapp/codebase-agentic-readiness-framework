# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Tests for the git-aware ignore engine (``audit.ignore``).

The temp git repository is created inside the test's own temporary directory — never the audit repo.
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
from audit.ignore import tracked_files  # noqa: E402


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class TrackedFilesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_tracked_set_on_a_real_repository(self):
        self.assertEqual(_git(self.root, "init").returncode, 0)
        support.write(self.root, "a.txt", "a\n")
        support.write(self.root, "src/b.py", "print(1)\n")
        self.assertEqual(_git(self.root, "add", "-A").returncode, 0)

        self.assertEqual(tracked_files(self.root), {"a.txt", "src/b.py"})

    def test_none_for_a_non_repository(self):
        support.write(self.root, "a.txt", "a\n")
        self.assertIsNone(tracked_files(self.root))

    def test_none_for_a_path_git_cannot_answer_for(self):
        self.assertIsNone(tracked_files(self.root / "does-not-exist"))


if __name__ == "__main__":
    unittest.main()
