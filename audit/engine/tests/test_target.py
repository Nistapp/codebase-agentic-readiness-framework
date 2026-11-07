# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Tests for the target guard (``audit.target``): what it refuses, what it records, and that it never writes in the target.

The repositories are made inside the test's own temporary directory — never the audit repo. The last class holds the
engine to its read-only rule on a repository whose index is stale: a tracked file has a time that the index does not
hold, so that a plain ``git status`` would refresh ``.git/index``.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.cli import AuditUsageError  # noqa: E402
from audit.target import _git, resolve_target  # noqa: E402

STALE = 946684800  # 2000-01-01


def git(root: Path, *args: str) -> str:
    """Run git in ``root`` as a person would, except that reads take no optional lock: they must not touch the index."""
    done = subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return done.stdout.strip()


def read(root: Path, *args: str) -> str:
    return git(root, "--no-optional-locks", *args)


def make_repo(root: Path, *, commit: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    support.write(root, "a.txt", "a\n")
    support.write(root, "src/b.txt", "b\n")
    if commit:
        git(root, "add", "-A")
        git(root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "x")
    return root


def make_stale(root: Path) -> None:
    os.utime(root / "a.txt", (STALE, STALE))


def index_hash(root: Path) -> str:
    return hashlib.sha256((root / ".git" / "index").read_bytes()).hexdigest()


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    state = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        state[str(path.relative_to(root))] = (info.st_size, info.st_mtime_ns)
    return state


class TempCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()


class RefusalTests(TempCase):
    def test_a_missing_target(self):
        with self.assertRaises(AuditUsageError) as caught:
            resolve_target(self.root / "missing")
        self.assertEqual(str(caught.exception), f"target does not exist: {self.root / 'missing'}")

    def test_a_file_is_not_a_target(self):
        path = support.write(self.root, "a.txt", "a\n")
        with self.assertRaises(AuditUsageError) as caught:
            resolve_target(path)
        self.assertEqual(str(caught.exception), f"target is not a directory: {path}")

    def test_a_filesystem_root_is_refused_before_git_is_asked(self):
        with mock.patch("audit.target.subprocess.run", side_effect=AssertionError("git was run")):
            with self.assertRaises(AuditUsageError) as caught:
                resolve_target(Path("/"))
        self.assertEqual(str(caught.exception), "refusing to scan a filesystem root")


class RecordTests(TempCase):
    def test_a_clean_repository(self):
        repo = make_repo(self.root / "repo")
        found = resolve_target(repo)
        self.assertEqual(found.path, repo)
        self.assertIs(found.is_git, True)
        self.assertEqual(found.git_sha, read(repo, "rev-parse", "HEAD"))
        self.assertEqual(found.git_branch, read(repo, "rev-parse", "--abbrev-ref", "HEAD"))
        self.assertIs(found.git_dirty, False)

    def test_an_untracked_file_or_a_change_makes_it_dirty(self):
        repo = make_repo(self.root / "repo")
        support.write(repo, "new.txt", "n\n")
        self.assertIs(resolve_target(repo).git_dirty, True)
        (repo / "new.txt").unlink()
        support.write(repo, "a.txt", "changed\n")
        self.assertIs(resolve_target(repo).git_dirty, True)

    def test_a_directory_that_is_not_a_repository(self):
        plain = self.root / "plain"
        support.write(plain, "a.txt", "a\n")
        found = resolve_target(plain)
        self.assertEqual((found.is_git, found.git_sha, found.git_branch, found.git_dirty), (False, None, None, False))

    def test_a_repository_with_no_commit_has_no_sha(self):
        repo = make_repo(self.root / "repo", commit=False)
        found = resolve_target(repo)
        self.assertEqual((found.is_git, found.git_sha, found.git_dirty), (True, None, True))

    def test_a_folder_inside_a_repository_is_a_repository_target(self):
        repo = make_repo(self.root / "repo")
        found = resolve_target(repo / "src")
        self.assertIs(found.is_git, True)
        self.assertEqual(found.git_sha, read(repo, "rev-parse", "HEAD"))


class GitQueryTests(TempCase):
    def test_a_successful_query_gives_its_output_without_the_line_break(self):
        repo = make_repo(self.root / "repo")
        self.assertEqual(_git(repo, "rev-parse", "HEAD"), read(repo, "rev-parse", "HEAD"))

    def test_a_query_that_fails_gives_none(self):
        repo = make_repo(self.root / "repo")
        self.assertIsNone(_git(repo, "rev-parse", "no-such-revision"))

    def test_git_that_cannot_run_or_takes_too_long_gives_none(self):
        for error in (FileNotFoundError("git"), subprocess.TimeoutExpired("git", 10)):
            with self.subTest(error=type(error).__name__):
                with mock.patch("audit.target.subprocess.run", side_effect=error):
                    self.assertIsNone(_git(self.root, "status"))

    def test_every_query_takes_no_optional_lock(self):
        with mock.patch("audit.target.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="x\n", stderr="")
            self.assertEqual(_git(Path("/some/repo"), "status", "--porcelain"), "x")
        run.assert_called_once_with(
            ["git", "-C", "/some/repo", "--no-optional-locks", "status", "--porcelain"],
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_the_guard_asks_git_only_with_that_flag(self):
        repo = make_repo(self.root / "repo")
        asked = []
        real = subprocess.run

        def spy(argv, **kwargs):
            asked.append(argv)
            return real(argv, **kwargs)

        for target in (repo, repo / "src"):
            asked.clear()
            with mock.patch("audit.target.subprocess.run", spy):
                resolve_target(target)
            self.assertGreaterEqual(len(asked), 3)
            for argv in asked:
                self.assertEqual(argv[:4], ["git", "-C", str(target), "--no-optional-locks"], argv)
            self.assertEqual(asked[-1][4:], ["status", "--porcelain"])


class ReadOnlyTests(TempCase):
    """The target is left as it was, down to the index, even when file times make `git status` want to refresh it."""

    def state(self, repo):
        return index_hash(repo), read(repo, "status", "--porcelain"), read(repo, "rev-parse", "HEAD"), snapshot(repo)

    def test_the_setup_is_one_where_a_plain_status_rewrites_the_index(self):
        repo = make_repo(self.root / "repo")
        make_stale(repo)
        before = index_hash(repo)
        git(repo, "status", "--porcelain")
        self.assertNotEqual(index_hash(repo), before, "git no longer refreshes a stale index: this test is moot")

    def test_the_guard_leaves_a_stale_index_alone(self):
        repo = make_repo(self.root / "repo")
        make_stale(repo)
        before = self.state(repo)
        resolve_target(repo)
        self.assertEqual(self.state(repo), before)

    def test_the_guard_leaves_a_stale_index_alone_in_a_dirty_repository(self):
        repo = make_repo(self.root / "repo")
        support.write(repo, "new.txt", "n\n")
        make_stale(repo)
        before = self.state(repo)
        self.assertIs(resolve_target(repo).git_dirty, True)
        self.assertEqual(self.state(repo), before)

    def test_a_whole_scan_leaves_a_stale_index_alone(self):
        repo = make_repo(self.root / "repo")
        make_stale(repo)
        before = self.state(repo)
        report = support.run_audit(repo)
        self.assertEqual(report["provenance"]["git_sha"], read(repo, "rev-parse", "HEAD"))
        self.assertEqual(self.state(repo), before)


if __name__ == "__main__":
    unittest.main()
