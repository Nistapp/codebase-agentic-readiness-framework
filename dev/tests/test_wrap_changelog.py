# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``wrap_changelog.py``: which lines it wraps, how, and what it leaves alone."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import wrap_changelog as wc

# The v0.4.0 breaking-change bullet that release-please wrote, which failed MD013 on the release pull request.
BREAKING = (
    "- **implement:** progress.py init takes the report from outside the target and writes the state beside it. "
    "show, render, set-status, skip, unskip, defer, undefer, pref and theme take --workspace DIR (the report's "
    "folder) instead of --target. A state kept in a target's docs/agentic-readiness/ is no longer found."
)
# A feature bullet that ends in a long link: longer than 120, but no space after column 120, so MD013 accepts it.
LINKED = (
    "- **audit:** print family names and check titles beside their codes "
    "([70a7d5a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/"
    "70a7d5a5261281f70424f704b23887aaa4443334))"
)


def changelog(*body: str) -> str:
    return "\n".join(["# Changelog", "", "## [0.4.0](https://example.invalid) (2026-11-12)", "", *body, ""])


class Refused(unittest.TestCase):
    def test_a_long_line_with_a_space_past_the_limit_is_refused(self) -> None:
        self.assertTrue(wc.refused(BREAKING))

    def test_a_long_line_that_ends_in_one_long_link_is_accepted(self) -> None:
        self.assertGreater(len(LINKED), wc.WIDTH)
        self.assertFalse(wc.refused(LINKED))

    def test_a_line_at_the_limit_is_accepted(self) -> None:
        self.assertFalse(wc.refused("x " * 59 + "xx"))


class Wrap(unittest.TestCase):
    def test_a_refused_bullet_wraps_with_a_two_space_hanging_indent(self) -> None:
        lines = wc.wrap(changelog(BREAKING)).split("\n")[4:-1]
        self.assertGreater(len(lines), 1)
        self.assertTrue(lines[0].startswith("- **implement:** "))
        for line in lines:
            self.assertLessEqual(len(line), wc.WIDTH)
        for line in lines[1:]:
            self.assertRegex(line, r"^  \S")
        self.assertEqual(" ".join(line.strip() for line in lines), BREAKING)

    def test_a_star_bullet_keeps_its_marker(self) -> None:
        lines = wc.wrap("* " + BREAKING[2:]).split("\n")
        self.assertTrue(lines[0].startswith("* **implement:** "))
        self.assertTrue(all(line.startswith("  ") for line in lines[1:]))

    def test_a_paragraph_line_wraps_flush(self) -> None:
        lines = wc.wrap(BREAKING[2:]).split("\n")
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(not line.startswith(" ") for line in lines))

    def test_every_other_line_is_kept_byte_for_byte(self) -> None:
        text = changelog(LINKED, "", "| a | " + "b " * 70 + "|", "", "# " + "heading " * 20, "> " + "quote " * 30)
        self.assertEqual(wc.wrap(text), text)

    def test_fenced_code_is_never_wrapped(self) -> None:
        text = changelog("```text", BREAKING, "```")
        self.assertEqual(wc.wrap(text), text)

    def test_a_continuation_line_never_starts_a_new_block(self) -> None:
        for marker in ("-", "*", "+", "1.", "2)", "#", ">", "|", "==="):
            with self.subTest(marker=marker):
                line = "- " + "word " * 23 + "wor " + marker + " tail" * 10
                lines = wc.wrap(line).split("\n")
                for continuation in lines[1:]:
                    self.assertNotRegex(continuation.strip().split(" ")[0], wc.STARTS_BLOCK)
                self.assertEqual(" ".join(x.strip() for x in lines), " ".join(line.split()))

    def test_running_twice_changes_nothing(self) -> None:
        once = wc.wrap(changelog(BREAKING, LINKED))
        self.assertEqual(wc.wrap(once), once)

    def test_the_count_is_the_number_of_refused_lines(self) -> None:
        self.assertEqual(wc.wrap_counted(changelog(BREAKING, LINKED, BREAKING))[1], 2)


class Main(unittest.TestCase):
    def test_it_rewrites_the_file_in_place_and_reports_the_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text(changelog(BREAKING), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(wc.main([str(path)]), 0)
            self.assertEqual(path.read_text(encoding="utf-8"), wc.wrap(changelog(BREAKING)))
            self.assertIn("1 line(s) wrapped", out.getvalue())

    def test_a_missing_file_is_exit_2(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(wc.main(["/nonexistent/CHANGELOG.md"]), 2)
        self.assertIn("cannot read", err.getvalue())

    def test_two_arguments_are_exit_2(self) -> None:
        with redirect_stderr(io.StringIO()):
            self.assertEqual(wc.main(["a", "b"]), 2)


if __name__ == "__main__":
    unittest.main()
