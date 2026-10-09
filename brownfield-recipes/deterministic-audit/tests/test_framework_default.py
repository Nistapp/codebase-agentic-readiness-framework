# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The framework checkout defaults to the repository this tool lives in.

``--framework`` used to be mandatory for ``--verify-rules`` and the report's ``framework_revision`` was
``null`` without it. Now the tool sits inside the framework repository, so both resolve from the package
location. Moving the tool out of the repository must degrade to an explicit request for the flag, never to a
wrong answer.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ENGINE_DIR = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(TESTS_DIR))

import support                                                           # noqa: E402
from audit import cli                                                     # noqa: E402
from audit.rules.registry import find_framework_root                      # noqa: E402

FRAMEWORK_ROOT = ENGINE_DIR.parents[1]
MARKER = ("brownfield-legacy", "Phased-Approach.md")


def _git_head(path: Path) -> str | None:
    proc = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _make_framework_tree(root: Path) -> None:
    support.write(root, "/".join(MARKER), "# Phase 1: Agentic Bootstrap\n")


class FindFrameworkRootTests(unittest.TestCase):
    def test_default_is_the_repository_this_tool_lives_in(self):
        root = find_framework_root()
        self.assertEqual(root, FRAMEWORK_ROOT.resolve())
        self.assertTrue(root.joinpath(*MARKER).is_file())

    def test_walks_up_from_a_nested_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _make_framework_tree(root)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            self.assertEqual(find_framework_root(nested), root)

    def test_returns_none_outside_any_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(find_framework_root(Path(tmp)))


class VerifyRulesTests(unittest.TestCase):
    def test_verify_rules_needs_no_flag_inside_the_repository(self):
        proc = subprocess.run([sys.executable, "-m", "audit", "--verify-rules"],
                              cwd=str(ENGINE_DIR), text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("framework anchors resolve", proc.stdout)

    def test_verify_rules_outside_a_checkout_asks_for_the_flag(self):
        stderr = io.StringIO()
        with mock.patch("audit.rules.registry.find_framework_root", return_value=None), \
                contextlib.redirect_stderr(stderr):
            code = cli.run(["--verify-rules"])
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("--framework", stderr.getvalue())

    def test_missing_framework_path_is_a_usage_error_not_a_traceback(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = cli.run(["--verify-rules", "--framework", "/nonexistent/framework-checkout"])
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("framework checkout not found", stderr.getvalue())


class FrameworkRevisionTests(unittest.TestCase):
    def test_report_records_this_repositorys_head_by_default(self):
        head = _git_head(FRAMEWORK_ROOT)
        if head is None:
            self.skipTest("not a git checkout")
        report = support.run_audit(support.fixture("exec-ok"))
        self.assertEqual(report["provenance"]["framework_revision"], head)

    def test_explicit_framework_overrides_the_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for args in (("init", "-q"),
                         ("-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                          "commit", "--allow-empty", "-q", "-m", "x")):
                subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
            report = support.run_audit(support.fixture("exec-ok"), extra_args=("--framework", str(repo)))
            self.assertEqual(report["provenance"]["framework_revision"], _git_head(repo))

    def test_revision_is_null_when_the_framework_is_not_a_git_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = support.run_audit(support.fixture("exec-ok"), extra_args=("--framework", tmp))
        self.assertIsNone(report["provenance"]["framework_revision"])


class ZipappTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build = subprocess.run([sys.executable, str(ENGINE_DIR / "tools" / "build.py")],
                               cwd=str(ENGINE_DIR), text=True, capture_output=True)
        assert build.returncode == 0, build.stderr
        cls.archive = ENGINE_DIR / "dist" / "audit.pyz"

    def test_archive_inside_the_repository_finds_the_framework(self):
        proc = subprocess.run([str(self.archive), "--verify-rules"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_archive_copied_elsewhere_asks_for_the_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "audit.pyz"
            shutil.copy(self.archive, copy)
            proc = subprocess.run([str(copy), "--verify-rules"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, cli.EXIT_USAGE)
        self.assertIn("--framework", proc.stderr)


if __name__ == "__main__":
    unittest.main()
