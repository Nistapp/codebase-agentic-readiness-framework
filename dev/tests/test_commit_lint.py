# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``commit_lint.py``: the subject rule, message files and git ranges."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import commit_lint


class Subject(unittest.TestCase):
    def test_accepts_conventional_subjects(self) -> None:
        for subject in (
            "feat: add a check",
            "fix(engine): handle an empty file",
            "docs(release): describe the promotion",
            "ci(deps): Bump actions/checkout from 7.0.1 to 7.0.2",
            "build(dev): update ruff to 0.17.0",
            "feat!: drop the v1 schema",
            "refactor(audit.tools)!: rename a field",
        ):
            with self.subTest(subject=subject):
                self.assertTrue(commit_lint.valid(subject))

    def test_rejects_other_subjects(self) -> None:
        for subject in (
            "Add a check",
            "feature: add a check",
            "fix:missing space",
            "fix: ",
            "fix(Engine): upper-case scope",
            "Merge branch 'dev'",
            "",
        ):
            with self.subTest(subject=subject):
                self.assertFalse(commit_lint.valid(subject))


class MessageFile(unittest.TestCase):
    def test_skips_git_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            message = Path(tmp) / "COMMIT_EDITMSG"
            message.write_text("# Please enter the commit message\nfix: a bug\n\nbody\n", encoding="utf-8")
            self.assertEqual(commit_lint.first_line(message), "fix: a bug")
            self.assertEqual(commit_lint.main(["--message-file", str(message)]), 0)

    def test_fails_on_a_bad_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            message = Path(tmp) / "COMMIT_EDITMSG"
            message.write_text("Fixed a bug\n", encoding="utf-8")
            self.assertEqual(commit_lint.main(["--message-file", str(message)]), 1)


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class Range(unittest.TestCase):
    def git(self, repo: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    def make_repo(self, tmp: str, subjects: list[str]) -> Path:
        repo = Path(tmp)
        self.git(repo, "init", "-q", "-b", "dev")
        self.git(repo, "config", "user.email", "test@example.invalid")
        self.git(repo, "config", "user.name", "Test")
        self.git(repo, "commit", "-q", "--allow-empty", "-m", "chore: start")
        self.git(repo, "switch", "-q", "-c", "work")
        for subject in subjects:
            self.git(repo, "commit", "-q", "--allow-empty", "-m", subject)
        return repo

    def run_in(self, repo: Path, revision_range: str) -> int:
        cwd = Path.cwd()
        try:
            os.chdir(repo)
            return commit_lint.main(["--range", revision_range])
        finally:
            os.chdir(cwd)

    def test_passes_a_clean_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp, ["feat: one", "docs: two"])
            self.assertEqual(self.run_in(repo, "dev..work"), 0)

    def test_fails_a_range_with_one_bad_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp, ["feat: one", "wip"])
            self.assertEqual(self.run_in(repo, "dev..work"), 1)

    def test_skips_merge_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp, ["feat: one"])
            self.git(repo, "switch", "-q", "dev")
            self.git(repo, "merge", "-q", "--no-ff", "-m", "Merge branch 'work' into dev", "work")
            self.assertEqual(self.run_in(repo, "HEAD~1..HEAD"), 0)

    def test_unknown_range_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp, [])
            self.assertEqual(self.run_in(repo, "nope..work"), 2)


if __name__ == "__main__":
    unittest.main()
