# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the quote verifier, ``doc_index.py verify-quotes``, on temporary folders and git repositories."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from docindex import cli, quotes

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Quote Test",
    "GIT_AUTHOR_EMAIL": "quotes@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Quote Test",
    "GIT_COMMITTER_EMAIL": "quotes@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

GUIDE = """# Guide

Every public method requires positive
and negative tests, written before
the code.

Never push to the main branch.
"""


class _Folder(unittest.TestCase):
    """A temporary repository root with ``docs/guide.md`` and an empty report folder, ``report/``."""

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.report = self.root / "report"
        self.report.mkdir()
        self._write("docs/guide.md", GUIDE)

    def _write(self, path: str, text: str) -> None:
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    def _quotes(self, entries: list[Any], folder: str = "report") -> None:
        self._write(f"{folder}/quotes.json", json.dumps(entries))

    def _run(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = cli.main(["verify-quotes", *args], {}, root=self.root)
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, out.getvalue(), err.getvalue()

    def _verify(self, *args: str) -> tuple[int, str, str]:
        return self._run(str(self.report), *args)


class NormaliseTest(unittest.TestCase):
    def test_whitespace_runs_collapse_and_nothing_else_changes(self) -> None:
        self.assertEqual(quotes.normalise("  A\n  b,\t\tC.  "), "A b, C.")


class PathProblemTest(unittest.TestCase):
    def test_a_plain_repository_path_is_accepted(self) -> None:
        self.assertIsNone(quotes.path_problem("docs/guide.md"))
        self.assertIsNone(quotes.path_problem("docs/environment.md"))

    def test_refused_paths(self) -> None:
        for path in (
            "",
            "/etc/passwd",
            "../outside.md",
            "docs/../guide.md",
            "./docs/guide.md",
            "docs//guide.md",
            "docs/",
            "docs\\guide.md",
            "C:/guide.md",
            "artefacts/notes.md",
            ".env",
            "app/.env",
            "app/.env.local",
            "app/prod.env",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(quotes.path_problem(path))


class VerifyQuotesTest(_Folder):
    def test_a_quote_across_a_line_wrap_passes(self) -> None:
        self._quotes(
            [
                {"id": "Q1", "path": "docs/guide.md", "quote": "requires positive and negative tests, written before"},
                {"id": "Q2", "path": "docs/guide.md", "quote": "Never push to the main branch."},
            ]
        )
        self._write("report/report.md", "A rule [Q1] and another [Q2], again [Q1].\n")
        code, out, err = self._verify()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, "verify-quotes: 2 quotes and 2 citations checked, 0 failed\n")

    def test_a_changed_word_fails(self) -> None:
        self._quotes([{"id": "Q1", "path": "docs/guide.md", "quote": "requires positive and negative checks"}])
        code, out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn("Q1: docs/guide.md: the quote does not occur in the file", err)
        self.assertIn("1 failed", out)

    def test_case_and_punctuation_must_match(self) -> None:
        for quote in ("never push to the main branch.", "Never push to the main branch!"):
            with self.subTest(quote=quote):
                self._quotes([{"id": "Q1", "path": "docs/guide.md", "quote": quote}])
                self.assertEqual(self._verify()[0], 2)

    def test_a_missing_path_fails(self) -> None:
        self._quotes([{"id": "Q1", "path": "docs/gone.md", "quote": "Never push"}])
        code, _out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn("Q1: docs/gone.md: no such file in the working tree", err)

    def test_a_duplicate_id_fails(self) -> None:
        self._quotes(
            [
                {"id": "Q1", "path": "docs/guide.md", "quote": "Never push"},
                {"id": "Q1", "path": "docs/guide.md", "quote": "the code."},
            ]
        )
        code, _out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn("Q1: docs/guide.md: the id is not unique", err)
        self.assertEqual(err.count("\n"), 1)

    def test_a_cited_id_with_no_entry_fails(self) -> None:
        self._quotes([{"id": "Q1", "path": "docs/guide.md", "quote": "Never push"}])
        self._write("report/report.md", "Cites [Q1] and [Q7].\n")
        code, _out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn(f"Q7: {self.report.as_posix()}/report.md: the cited id has no entry in", err)
        self.assertNotIn("Q1", err)

    def test_an_env_path_is_refused_and_never_read(self) -> None:
        self._write("app/.env", "SECRET=value\n")
        self._quotes([{"id": "Q1", "path": "app/.env", "quote": "SECRET=value"}])
        code, _out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn("Q1: app/.env: a quote may not cite a .env file", err)
        self.assertNotIn("SECRET=value", err)

    def test_a_link_to_an_env_file_is_refused(self) -> None:
        self._write("app/.env", "SECRET=value\n")
        (self.root / "docs/settings.md").symlink_to(self.root / "app/.env")
        self._quotes([{"id": "Q1", "path": "docs/settings.md", "quote": "SECRET=value"}])
        code, _out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn("the path leads to app/.env", err)

    def test_an_artefacts_path_is_refused(self) -> None:
        self._write("artefacts/plan.md", "Never push to the main branch.\n")
        self._quotes([{"id": "Q1", "path": "artefacts/plan.md", "quote": "Never push"}])
        code, _out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn("may not cite a file under artefacts/", err)

    def test_a_path_outside_the_repository_is_refused(self) -> None:
        self._quotes([{"id": "Q1", "path": "../guide.md", "quote": "Never push"}])
        self.assertEqual(self._verify()[0], 2)

    def test_malformed_entries_fail(self) -> None:
        self._quotes(
            [
                "Q1",
                {"id": "q2", "path": "docs/guide.md", "quote": "Never push"},
                {"id": "Q3", "quote": "Never push"},
                {"id": "Q4", "path": "docs/guide.md"},
                {"id": "Q5", "path": "docs/guide.md", "quote": " \n "},
            ]
        )
        code, out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertEqual(err.count("\n"), 5, err)
        self.assertIn("5 quotes", out)

    def test_a_quotes_file_that_is_not_a_list_fails(self) -> None:
        self._write("report/quotes.json", '{"id": "Q1"}')
        code, _out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn("quotes.json is not a JSON list", err)

    def test_a_citation_resolves_to_the_nearest_quotes_file(self) -> None:
        self._quotes([{"id": "Q1", "path": "docs/guide.md", "quote": "Never push"}])
        self._quotes([{"id": "Q2", "path": "docs/guide.md", "quote": "the code."}], folder="report/pass-a")
        self._write("report/pass-a/report.md", "Cites [Q2].\n")
        self._write("report/pass-a/deep/notes.md", "Cites [Q2] from below.\n")
        self._write("report/pass-b/report.md", "Cites [Q1] from the parent.\n")
        self.assertEqual(self._verify()[0], 0)
        self._write("report/pass-a/other.md", "Cites [Q1], which only the parent holds.\n")
        code, _out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn("pass-a/other.md: the cited id has no entry in", err)
        self.assertIn("pass-a/quotes.json", err)

    def test_every_quotes_file_under_the_folder_is_verified(self) -> None:
        self._quotes([{"id": "Q1", "path": "docs/guide.md", "quote": "Never push"}])
        self._quotes([{"id": "Q1", "path": "docs/guide.md", "quote": "Always push"}], folder="report/sub")
        code, _out, err = self._verify()
        self.assertEqual(code, 2)
        self.assertIn("report/sub/quotes.json", err)

    def test_a_folder_with_no_quotes_file_is_a_usage_error(self) -> None:
        self._write("report/report.md", "Cites [Q1].\n")
        code, out, err = self._verify()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("holds no quotes.json", err)

    def test_a_missing_folder_is_a_usage_error(self) -> None:
        code, _out, err = self._run(str(self.root / "nowhere"))
        self.assertEqual(code, 1)
        self.assertIn("is not a folder", err)

    def test_an_argument_error_exits_1(self) -> None:
        self.assertEqual(self._run()[0], 1)
        self.assertEqual(self._run(str(self.report), "--bogus")[0], 1)

    def test_the_command_is_listed_in_the_help(self) -> None:
        self.assertIn("verify-quotes", cli.build_parser().format_help())


class VerifyQuotesAtRefTest(_Folder):
    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def setUp(self) -> None:
        super().setUp()
        self._git("init", "-q")
        self._git("add", "docs/guide.md")
        self._git("commit", "-q", "-m", "first")
        self.first = self._git("rev-parse", "HEAD")
        self._write("docs/guide.md", GUIDE.replace("Never push", "Do not push"))
        self._write("docs/new.md", "A new page.\n")
        self._git("add", "docs")
        self._git("commit", "-q", "-m", "second")

    def test_at_reads_the_files_at_the_ref(self) -> None:
        self._quotes([{"id": "Q1", "path": "docs/guide.md", "quote": "Never push to the main branch."}])
        self._write("report/report.md", "Cites [Q1].\n")
        self.assertEqual(self._verify("--at", self.first)[0], 0)
        code, _out, err = self._verify("--at", "HEAD")
        self.assertEqual(code, 2)
        self.assertIn("the quote does not occur in the file", err)
        self.assertEqual(self._verify()[0], 2)

    def test_at_a_file_absent_at_the_ref_fails(self) -> None:
        self._quotes([{"id": "Q1", "path": "docs/new.md", "quote": "A new page."}])
        self.assertEqual(self._verify("--at", "HEAD")[0], 0)
        code, _out, err = self._verify("--at", self.first)
        self.assertEqual(code, 2)
        self.assertIn(f"Q1: docs/new.md: no such file at {self.first}", err)

    def test_at_a_folder_path_fails(self) -> None:
        self._quotes([{"id": "Q1", "path": "docs", "quote": "guide.md"}])
        self.assertEqual(self._verify("--at", "HEAD")[0], 2)

    def test_at_a_ref_that_names_no_commit_is_a_usage_error(self) -> None:
        self._quotes([{"id": "Q1", "path": "docs/guide.md", "quote": "Never push"}])
        code, out, err = self._verify("--at", "no-such-ref")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("does not name a commit", err)


if __name__ == "__main__":
    unittest.main()
