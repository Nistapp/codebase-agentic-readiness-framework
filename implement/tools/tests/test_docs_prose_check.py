# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the playbook template ``docs_prose_check.py``: the three rules, the ratchet limit and the folders.

The rules themselves are held equal to ``dev/prose_check.py`` and the engine's ``DOC-05`` by
``dev/tests/test_prose_template_parity.py``; these tests cover what only the template has.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import _implement_paths  # noqa: F401
import docs_prose_check as dpc


def _words(n: int) -> str:
    return " ".join(["word"] * n) + "."


def _run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = dpc.main(list(argv))
        except SystemExit as exc:
            code = int(exc.code or 0)
    return code, out.getvalue(), err.getvalue()


class Rules(unittest.TestCase):
    def test_a_long_sentence_a_vague_word_and_a_long_step(self) -> None:
        text = f"{_words(30)}\n\nRun it, simply.\n\n1. {_words(22)}\n"
        codes = [(i.code, i.severity) for i in dpc.check_text("docs/how-to/x.md", text)]
        self.assertEqual(codes, [("PL001", "notice"), ("PL002", "warning"), ("PL001", "warning")])

    def test_a_skipped_region_is_not_read(self) -> None:
        text = f"<!-- prose-check off -->\n\n{_words(50)} Just so.\n\n<!-- prose-check on -->\n\nShort text.\n"
        self.assertEqual(dpc.check_text("docs/x.md", text), [])


class DiagramFolders(unittest.TestCase):
    def test_the_default_folders_are_explanation_and_tutorials(self) -> None:
        self.assertTrue(dpc.needs_diagram("docs/explanation/flow.md"))
        self.assertTrue(dpc.needs_diagram("docs/tutorials/start.md"))
        self.assertFalse(dpc.needs_diagram("docs/explanation/README.md"))
        self.assertFalse(dpc.needs_diagram("docs/how-to/x.md"))

    def test_a_named_folder_replaces_the_defaults(self) -> None:
        dirs = ("docs/architecture",)
        self.assertTrue(dpc.needs_diagram("docs/architecture/overview.md", dirs))
        self.assertFalse(dpc.needs_diagram("docs/explanation/flow.md", dirs))
        self.assertFalse(dpc.needs_diagram("docs/architecture-notes.md", dirs))
        issues = dpc.check_text("docs/architecture/overview.md", "Short text here.\n", dirs)
        self.assertEqual([i.code for i in issues], ["PL003"])

    def test_the_option_reaches_the_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "docs" / "architecture" / "overview.md"
            page.parent.mkdir(parents=True)
            page.write_text("Short text here.\n", encoding="utf-8")
            code, out, _ = _run("--diagram-dir", "architecture/", str(page))
        self.assertEqual(code, 0)
        self.assertIn("PL003", out)


class Ratchet(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.page = Path(self._tmp.name) / "page.md"
        self.page.write_text(f"{_words(30)}\n\nIt is easily done.\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_without_a_limit_the_check_is_advisory(self) -> None:
        code, out, _ = _run(str(self.page))
        self.assertEqual(code, 0)
        self.assertIn("Summary: 2 issues in 1 file (1 warning, 1 notice)", out)

    def test_above_the_limit_it_fails(self) -> None:
        code, _, err = _run("--max-issues", "1", str(self.page))
        self.assertEqual(code, 1)
        self.assertIn("2 issues, more than the limit of 1", err)

    def test_at_the_limit_it_passes(self) -> None:
        self.assertEqual(_run("--max-issues", "2", str(self.page))[0], 0)

    def test_the_limit_counts_only_the_shown_issues(self) -> None:
        self.assertEqual(_run("--max-issues", "1", "--min-severity", "warning", str(self.page))[0], 0)

    def test_a_negative_limit_is_refused(self) -> None:
        self.assertEqual(_run("--max-issues", "-1", str(self.page))[0], 2)

    def test_a_file_that_cannot_be_read_is_exit_2(self) -> None:
        code, _, err = _run("--max-issues", "0", str(Path(self._tmp.name) / "missing.md"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_github_format_prints_annotations(self) -> None:
        code, out, _ = _run("--format", "github", "--quiet", str(self.page))
        self.assertEqual(code, 0)
        self.assertNotIn("::", out)
        code, out, _ = _run("--format", "github", str(self.page))
        self.assertIn("::warning file=", out)


if __name__ == "__main__":
    unittest.main()
