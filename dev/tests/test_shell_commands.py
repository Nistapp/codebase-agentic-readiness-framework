# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for `dev/eval/shell_commands.py`, the shell parsing the implement and audit evals share.

Run from the repository root: ``python3 -m unittest discover -s dev/tests -k shell_commands``.
"""

from __future__ import annotations

import sys
import unittest

import _dev_paths

sys.path.insert(0, str(_dev_paths.DEV / "eval"))

import shell_commands as sc  # noqa: E402


class ShellSegmentsTests(unittest.TestCase):
    def test_splits_on_every_separator(self) -> None:
        self.assertEqual(
            sc.shell_segments("a 1 && b || c ; d | e & f"),
            [["a", "1"], ["b"], ["c"], ["d"], ["e"], ["f"]],
        )

    def test_a_new_line_separates_commands(self) -> None:
        self.assertEqual(
            sc.shell_segments("git fetch origin\ngit status"), [["git", "fetch", "origin"], ["git", "status"]]
        )

    def test_keeps_quoted_text_together(self) -> None:
        self.assertEqual(
            sc.shell_segments("git commit -m 'a && b; c' && echo \"x | y\""),
            [["git", "commit", "-m", "a && b; c"], ["echo", "x | y"]],
        )

    def test_parentheses_and_command_substitution_split(self) -> None:
        self.assertEqual(
            sc.shell_segments("x=$(wget -qO- u) ; (cd d && ls)"), [["x=$"], ["wget", "-qO-", "u"], ["cd", "d"], ["ls"]]
        )

    def test_an_open_quote_falls_back_to_a_plain_split(self) -> None:
        self.assertEqual(sc.shell_segments("echo 'open && git push"), [["echo", "'open"], ["git", "push"]])

    def test_an_empty_command_has_no_segment(self) -> None:
        self.assertEqual(sc.shell_segments(""), [])
        self.assertEqual(sc.shell_segments(" ; && "), [])


class AllSegmentsTests(unittest.TestCase):
    def test_includes_the_script_of_sh_and_bash_c(self) -> None:
        found = sc.all_segments("bash -c 'git add . && git commit -m x'")
        self.assertIn(["git", "add", "."], found)
        self.assertIn(["git", "commit", "-m", "x"], found)
        self.assertIn(["git", "status"], sc.all_segments("/bin/sh -c 'git status'"))

    def test_includes_the_words_after_eval(self) -> None:
        self.assertIn(["git", "pull"], sc.all_segments("eval git pull"))
        self.assertIn(["gh", "api", "x"], sc.all_segments('eval "gh api x"'))

    def test_nested_scripts_are_split_too(self) -> None:
        self.assertIn(["git", "rebase", "main"], sc.all_segments("sh -c \"bash -c 'git rebase main'\""))

    def test_a_shell_without_a_script_adds_nothing(self) -> None:
        self.assertEqual(sc.all_segments("bash -c"), [["bash", "-c"]])
        self.assertEqual(sc.all_segments("bash script.sh"), [["bash", "script.sh"]])


class SubcommandTests(unittest.TestCase):
    def test_names_the_subcommand_and_its_arguments(self) -> None:
        self.assertEqual(sc.subcommand(["git", "push", "origin", "x"], "git"), ("push", ["origin", "x"]))

    def test_skips_global_flags_and_their_values(self) -> None:
        self.assertEqual(sc.subcommand(["git", "-C", "repo", "-c", "a=b", "merge", "x"], "git"), ("merge", ["x"]))
        self.assertEqual(sc.subcommand(["gh", "-R", "o/r", "api", "x"], "gh"), ("api", ["x"]))
        self.assertEqual(sc.subcommand(["git", "--no-pager", "log"], "git"), ("log", []))

    def test_finds_the_program_after_a_wrapper_or_by_its_path(self) -> None:
        self.assertEqual(sc.subcommand(["env", "X=1", "/usr/bin/git", "status"], "git"), ("status", []))

    def test_none_when_the_program_does_not_run_or_has_no_subcommand(self) -> None:
        self.assertIsNone(sc.subcommand(["echo", "git", "-C"], "gh"))
        self.assertIsNone(sc.subcommand(["git", "-C", "repo"], "git"))
        self.assertIsNone(sc.subcommand(["gitk", "status"], "git"))


if __name__ == "__main__":
    unittest.main()
