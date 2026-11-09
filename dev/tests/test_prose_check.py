# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``prose_check.py``: the three rules, what is skipped, and the summary and exit code."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import _dev_paths  # noqa: F401
import prose_check as pc


def _codes(text: str, path: str = "docs/how-to/x.md") -> list[str]:
    return [issue.code for issue in pc.check_text(path, text)]


def _words(n: int) -> str:
    return " ".join(["word"] * n) + "."


class LongSentences(unittest.TestCase):
    def test_a_sentence_of_25_words_passes(self) -> None:
        self.assertEqual(_codes(_words(25) + "\n"), [])

    def test_a_sentence_of_26_words_fails(self) -> None:
        issues = pc.check_text("a.md", _words(26) + "\n")
        self.assertEqual([i.code for i in issues], ["PL001"])
        self.assertIn("26 words (limit 25)", issues[0].message)

    def test_a_numbered_step_has_a_limit_of_20(self) -> None:
        self.assertEqual(_codes("1. " + _words(20) + "\n"), [])
        self.assertEqual(_codes("1. " + _words(21) + "\n"), ["PL001"])

    def test_a_bullet_item_has_the_normal_limit(self) -> None:
        self.assertEqual(_codes("- " + _words(25) + "\n"), [])

    def test_a_paragraph_wrapped_over_lines_is_one_text(self) -> None:
        text = " ".join(["word"] * 15) + "\n" + " ".join(["word"] * 15) + ".\n"
        issues = pc.check_text("a.md", text)
        self.assertEqual([(i.code, i.line) for i in issues], [("PL001", 1)])

    def test_sentences_split_at_a_full_stop_and_a_capital(self) -> None:
        self.assertEqual(_codes(_words(20) + " " + _words(20).capitalize() + "\n"), [])

    def test_a_code_span_counts_as_one_word(self) -> None:
        span = "`" + " ".join(["x"] * 30) + "`"
        self.assertEqual(_codes(f"Run {span} now.\n"), [])

    def test_a_link_counts_as_its_text(self) -> None:
        self.assertEqual(_codes("Read [the guide](" + "a/" * 40 + "b.md) first.\n"), [])

    def test_the_line_number_is_the_block_start(self) -> None:
        issues = pc.check_text("a.md", "# Title\n\nShort.\n\n" + _words(30) + "\n")
        self.assertEqual(issues[0].line, 5)


class Skipped(unittest.TestCase):
    def test_code_blocks_tables_and_headings_are_skipped(self) -> None:
        long = " ".join(["word"] * 40)
        text = f"# {long}\n\n```text\n{long}.\n```\n\n| {long} |\n|---|\n| {long} |\n"
        self.assertEqual(_codes(text), [])

    def test_html_comments_are_skipped(self) -> None:
        self.assertEqual(_codes("<!--\n" + _words(40) + "\n-->\n"), [])

    def test_an_off_region_is_skipped(self) -> None:
        text = f"<!-- prose-check off -->\n\n{_words(40)} Simply.\n\n<!-- prose-check on -->\n\n{_words(30)}\n"
        self.assertEqual(_codes(text), ["PL001"])

    def test_a_blockquote_is_checked(self) -> None:
        self.assertEqual(_codes("> [!NOTE]\n> " + _words(30) + "\n"), ["PL001"])


class VagueWords(unittest.TestCase):
    def test_each_vague_word_is_reported(self) -> None:
        issues = pc.check_text("a.md", "Simply run it in order to win, etc.\n")
        self.assertEqual([i.code for i in issues], ["PL002"] * 3)
        self.assertIn("'Simply'", issues[0].message)

    def test_a_word_inside_another_is_not_reported(self) -> None:
        self.assertEqual(_codes("Adjust the justification.\n"), [])

    def test_a_vague_word_in_a_code_span_is_not_reported(self) -> None:
        self.assertEqual(_codes("Do not write `simply`.\n"), [])


class Diagrams(unittest.TestCase):
    def test_an_explanation_page_without_mermaid_fails(self) -> None:
        self.assertEqual(_codes("Text.\n", "docs/explanation/user-overview/01-x.md"), ["PL003"])

    def test_an_explanation_page_with_mermaid_passes(self) -> None:
        text = "Text.\n\n```mermaid\nflowchart LR\n  A --> B\n```\n"
        self.assertEqual(_codes(text, "docs/explanation/user-overview/01-x.md"), [])

    def test_which_pages_need_a_diagram(self) -> None:
        self.assertTrue(pc.needs_diagram("docs/tutorials/first.md"))
        self.assertTrue(pc.needs_diagram("audit/engine/docs/architecture/user-overview/01-a.md"))
        self.assertFalse(pc.needs_diagram("docs/explanation/README.md"))
        self.assertFalse(pc.needs_diagram("docs/how-to/run-an-audit.md"))


class Main(unittest.TestCase):
    def _run(self, *texts: str, quiet: bool = False) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            files = []
            for n, text in enumerate(texts):
                path = Path(tmp) / f"{n}.md"
                path.write_text(text, encoding="utf-8")
                files.append(str(path))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = pc.main([*files, *(["--quiet"] if quiet else [])])
            return code, out.getvalue()

    def test_clean_files_exit_0_with_a_summary(self) -> None:
        code, out = self._run("Short.\n", "Also short.\n")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "Summary: 0 issues in 2 files")

    def test_issues_exit_1_and_are_listed(self) -> None:
        code, out = self._run(_words(30) + "\n")
        self.assertEqual(code, 1)
        self.assertIn("PL001", out)
        self.assertTrue(out.rstrip().endswith("Summary: 1 issue in 1 file"))

    def test_quiet_prints_only_the_summary(self) -> None:
        code, out = self._run(_words(30) + "\n", quiet=True)
        self.assertEqual((code, out.strip()), (1, "Summary: 1 issue in 1 file"))

    def test_a_missing_file_exits_2(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(pc.main(["/nonexistent/x.md"]), 2)


if __name__ == "__main__":
    unittest.main()
