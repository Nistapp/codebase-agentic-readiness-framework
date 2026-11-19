# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the sweep's diff mode, its path-only filter and the recall measure, on temporary git repositories."""

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
import doc_index
from docindex import cli, recall, sweep, sweep_diff
from docindex.gitread import GitError

CONFIG = doc_index.load_config()
ALL = sweep.select_triggers(CONFIG, "all")

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Sweep Test",
    "GIT_AUTHOR_EMAIL": "sweep@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Sweep Test",
    "GIT_COMMITTER_EMAIL": "sweep@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

#: The temporary repository's config: no fixture file is named like the repository's own instruction files.
_REPO_CONFIG: dict[str, Any] = {
    "exclude": {"list_only": [], "skip": []},
    "file_kinds": {".md": "markdown"},
    "sweep": {"file_names": ["RULES.md"], "paths": ["templates/"], "triggers": CONFIG["sweep"]["triggers"]},
}

RULE = "Every public method requires positive and negative tests."

OLD_RULES = """# Rules

You must sign the form before lunch.

Never push to the main branch.

Always read `docs/old/guide.md` first.

You must run the gate on each change.
"""

NEW_RULES = """# Rules

You must sign the form before dinner.

You must sign the letter after lunch.

You must sign the form.

Never wait for a review.

Always read `docs/new/guide.md` first.

You must run the gate on each change.
"""


def _item(text: str, path: str = "a.md", address: str = "a.md#") -> sweep.Item:
    return sweep.Item(path=path, address=address, kind="required-step", triggers=("must",), text=text)


class _Repo(unittest.TestCase):
    """A temporary git repository; :meth:`_commit` writes files, removes others, and commits."""

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self._git("init", "-q")

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def _commit(self, files: dict[str, str], remove: tuple[str, ...] = ()) -> str:
        for path, text in files.items():
            file = self.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
        for path in remove:
            self._git("rm", "-q", path)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "change")
        return self._git("rev-parse", "HEAD")

    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv, _REPO_CONFIG, root=self.root, bundle_sources=lambda: ["bundle"])
        return code, out.getvalue(), err.getvalue()


# --- The comparison -------------------------------------------------------------------------------------------------


class CompareTest(unittest.TestCase):
    def test_closest_items_are_ordered_by_ratio_then_path_and_address(self) -> None:
        old = [_item("You must sign the form.")]
        new = [
            _item("You must sign the form now.", "b.md", "b.md#"),
            _item("You must sign the form now.", "a.md", "a.md#z"),
            _item("You must sign the form now.", "a.md", "a.md#y"),
            _item("Never wait.", "a.md", "a.md#"),
        ]
        report = sweep_diff.compare(old, new)
        self.assertEqual(len(report.vanished), 1)
        closest = report.vanished[0].closest
        self.assertEqual([match.item.address for match in closest], ["a.md#y", "a.md#z", "b.md#"])

    def test_path_tokens_are_masked(self) -> None:
        text = "Read `audit/SKILL.md`, ../guide.md#steps, SKILL.md and recipe_lint.py, then templates/ now."
        self.assertEqual(sweep_diff.mask_paths(text), "Read `<path>`, <path>, <path> and <path>, then <path> now.")
        self.assertEqual(sweep_diff.mask_paths("Python 3.11, e.g. a.txt."), "Python 3.11, e.g. a.txt.")

    def test_a_removed_path_is_not_a_repoint(self) -> None:
        report = sweep_diff.compare([_item("You must read `docs/guide.md` first.")], [_item("You must read first.")])
        self.assertEqual((len(report.vanished), len(report.repointed)), (1, 0))

    def test_restrict_keeps_files_at_or_under_a_path(self) -> None:
        files = ["a/b.md", "a/bc.md", "a/b/c.md", "d.md"]
        self.assertEqual(sweep_diff.restrict(files, ["a/b", "d.md/"]), ["a/b/c.md", "d.md"])


# --- --diff ---------------------------------------------------------------------------------------------------------


class DiffModeTest(_Repo):
    def setUp(self) -> None:
        super().setUp()
        guide = "# Guide\n\nNever delete the cache.\n\nYou must keep the log.\n"
        self.old = self._commit({"RULES.md": OLD_RULES, "old/guide.md": guide})
        self.new = self._commit(
            {
                "RULES.md": NEW_RULES,
                "templates/guide.md": guide,
                "templates/moved.md": "# Moved\n\nNever push to the main branch.\n",
            },
            remove=("old/guide.md",),
        )

    def _diff(self, *extra: str) -> dict[str, Any]:
        code, out, err = self._run(["sweep", "--diff", self.old, "--at", self.new, "--format", "json", *extra])
        self.assertEqual((code, err), (0, ""))
        data: dict[str, Any] = json.loads(out)
        return data

    def test_a_vanished_item_is_listed_with_its_three_closest_items(self) -> None:
        data = self._diff()
        self.assertEqual([item["text"] for item in data["vanished"]], ["You must sign the form before lunch."])
        closest = data["vanished"][0]["closest"]
        self.assertEqual(closest[0]["text"], "You must sign the form before dinner.")
        self.assertEqual(
            {match["text"] for match in closest},
            {
                "You must sign the form before dinner.",
                "You must sign the letter after lunch.",
                "You must sign the form.",
            },
        )
        ratios = [match["ratio"] for match in closest]
        self.assertEqual(ratios, sorted(ratios, reverse=True))
        self.assertEqual(sorted(closest[0]), ["address", "kind", "path", "ratio", "text"])
        self.assertEqual(closest[0]["address"], "RULES.md#rules")

    def test_an_item_moved_verbatim_is_counted_not_listed(self) -> None:
        data = self._diff()
        listed = [item["text"] for item in data["vanished"] + data["path_repoint"]]
        self.assertNotIn("Never push to the main branch.", listed)
        self.assertEqual(data["counts"]["moved"], 1)
        self.assertEqual(data["counts"]["unchanged"], 1)

    def test_a_path_repoint_is_listed_apart(self) -> None:
        data = self._diff()
        self.assertEqual(len(data["path_repoint"]), 1)
        repoint = data["path_repoint"][0]
        self.assertEqual(repoint["text"], "Always read `docs/old/guide.md` first.")
        self.assertEqual(repoint["target"]["text"], "Always read `docs/new/guide.md` first.")
        self.assertEqual(data["counts"]["path_repoint"], 1)
        self.assertEqual(data["counts"]["vanished"], 1)

    def test_the_scope_is_used_without_paths(self) -> None:
        data = self._diff()
        self.assertIsNone(data["paths"])
        self.assertEqual((data["old"], data["new"], data["triggers"]), (self.old, self.new, "all"))
        # old/guide.md is in no scope at the old commit; templates/guide.md is in scope at the new one.
        self.assertEqual(data["counts"]["old_items"], 4)
        self.assertEqual(data["counts"]["new_items"], 9)

    def test_paths_restrict_both_sides_and_a_path_at_old_only_works(self) -> None:
        data = self._diff("--paths", "old/guide.md,templates/guide.md")
        self.assertEqual(data["paths"], ["old/guide.md", "templates/guide.md"])
        self.assertEqual(data["counts"]["old_items"], 2)
        self.assertEqual(data["counts"]["new_items"], 2)
        self.assertEqual(data["counts"]["moved"], 2)
        self.assertEqual((data["vanished"], data["path_repoint"]), ([], []))

    def test_paths_at_old_only_shows_the_items_as_vanished(self) -> None:
        data = self._diff("--paths", "old")
        self.assertEqual(data["counts"]["new_items"], 0)
        self.assertEqual([item["path"] for item in data["vanished"]], ["old/guide.md", "old/guide.md"])
        self.assertEqual([item["closest"] for item in data["vanished"]], [[], []])

    def test_without_at_the_working_tree_is_new(self) -> None:
        (self.root / "RULES.md").write_text(OLD_RULES, encoding="utf-8")
        code, out, _err = self._run(["sweep", "--diff", self.old, "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIsNone(data["new"])
        self.assertEqual((data["counts"]["vanished"], data["counts"]["unchanged"]), (0, 4))

    def test_the_text_form(self) -> None:
        code, out, _err = self._run(["sweep", "--diff", self.old, "--at", self.new])
        self.assertEqual(code, 0)
        self.assertIn(f"# Vanished from {self.old} to {self.new}: 1\n", out)
        self.assertIn("RULES.md#rules\n  kind: required-step\n  triggers: before, must\n", out)
        self.assertIn("  closest:\n    0.", out)
        self.assertIn("# Path re-point: 1\n", out)
        self.assertIn("  now: RULES.md#rules: Always read `docs/new/guide.md` first.\n", out)
        self.assertIn("     1  moved verbatim\n", out)

    def test_the_output_is_deterministic(self) -> None:
        first = self._run(["sweep", "--diff", self.old, "--at", self.new, "--format", "json"])
        second = self._run(["sweep", "--diff", self.old, "--at", self.new, "--format", "json"])
        self.assertEqual(first[1].encode("utf-8"), second[1].encode("utf-8"))
        self.assertNotIn(str(self.root), first[1])

    def test_a_bad_ref_and_a_bad_option_exit_1(self) -> None:
        code, out, err = self._run(["sweep", "--diff", "no-such-ref"])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("does not name a commit", err)
        usage = (
            ["sweep", "--paths", "a.md"],
            ["sweep", "--diff", "HEAD", "--paths", " , "],
            ["sweep", "--diff", "HEAD", "--recall", "x.json"],
            ["sweep", "--recall", "x.json", "--at", "HEAD"],
        )
        for argv in usage:
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                cli.main(argv, _REPO_CONFIG, root=self.root)
            self.assertEqual(raised.exception.code, 1)


# --- The recall measure ---------------------------------------------------------------------------------------------


class RecallTest(_Repo):
    def setUp(self) -> None:
        super().setUp()
        self.parent = self._commit(
            {
                "docs/rules.md": (
                    "# Rules\n\n"
                    "Keep the public surface small and well named.\n\n"
                    f"{RULE}\n\n"
                    "Short line here.\n\n"
                    "```text\nThis fenced line is long enough to count.\n```\n"
                ),
                "docs/other.md": "# Other\n\nThis whole file is removed but it is not listed.\n",
            }
        )
        self.commit = self._commit(
            {"docs/rules.md": "# Rules\n\nKeep the public surface small and well named.\n"},
            remove=("docs/other.md",),
        )
        self.commits = [{"hash": self.commit, "parent": self.parent, "files": ["docs/rules.md"], "role": "x"}]

    def _recall(self, *extra: str) -> tuple[int, str, str]:
        path = self.root / "commits.json"
        path.write_text(json.dumps(self.commits), encoding="utf-8")
        return self._run(["sweep", "--recall", str(path), *extra])

    def _json(self, triggers: str) -> dict[str, Any]:
        code, out, err = self._recall("--format", "json", "--triggers", triggers)
        self.assertEqual((code, err), (0, ""))
        data: dict[str, Any] = json.loads(out)
        return data

    def test_group1_misses_the_rule_and_all_finds_it(self) -> None:
        group1 = self._json("group1")
        self.assertEqual(group1["triggers"], "group1")
        self.assertEqual(group1["total"], {"commits": 1, "missed": 1, "removed": 1, "share": 1.0})
        line = {"address": None, "kind": None, "path": "docs/rules.md", "text": RULE}
        self.assertEqual(group1["commits"][0]["lines"], [line])
        everything = self._json("all")
        self.assertEqual(everything["total"], {"commits": 1, "missed": 0, "removed": 1, "share": 0.0})
        found = everything["commits"][0]["lines"][0]
        self.assertEqual((found["address"], found["kind"]), ("docs/rules.md#rules", "required-step"))

    def test_a_fenced_line_and_a_short_line_are_not_counted(self) -> None:
        results = recall.measure(self.root, recall.load_commits(self.commits), ALL)
        self.assertEqual([line.text for line in results[0].lines], [RULE])

    def test_the_per_commit_fields_and_the_text_table(self) -> None:
        data = self._json("group1")
        entry = data["commits"][0]
        self.assertEqual((entry["hash"], entry["parent"]), (self.commit, self.parent))
        self.assertEqual((entry["removed"], entry["missed"], entry["share"]), (1, 1, 1.0))
        self.assertEqual((data["format"], data["min_chars"]), (1, 25))
        code, out, _err = self._recall("--triggers", "group1")
        self.assertEqual(code, 0)
        self.assertIn(f"{self.commit[:12]}  {self.parent[:12]}        1           1  100.0%\n", out)
        self.assertTrue(out.endswith(f"{'total':<28}{1:>7}{1:>12}  100.0%\n"), out)

    def test_the_output_is_deterministic(self) -> None:
        first, second = self._recall("--format", "json"), self._recall("--format", "json")
        self.assertEqual(first[1].encode("utf-8"), second[1].encode("utf-8"))
        self.assertNotIn(str(self.root), first[1])

    def test_a_commit_with_no_kept_line_has_no_share(self) -> None:
        self.commits = [{"hash": self.parent, "parent": self.parent, "files": ["docs/rules.md"]}]
        data = self._json("all")
        self.assertEqual(data["total"], {"commits": 1, "missed": 0, "removed": 0, "share": None})
        code, out, _err = self._recall()
        self.assertEqual(code, 0)
        self.assertIn("  -\n", out)

    def test_bad_input_exits_1(self) -> None:
        for commits in ({"hash": "x"}, [{"hash": "x", "parent": "y"}], [3], [{"hash": "", "parent": "y", "files": []}]):
            with self.subTest(commits=commits), self.assertRaises(ValueError):
                recall.load_commits(commits)
        code, _out, err = self._run(["sweep", "--recall", str(self.root / "missing.json")])
        self.assertEqual(code, 1)
        self.assertIn("cannot read the commits file", err)
        self.commits = [{"hash": "no-such-ref", "parent": self.parent, "files": ["docs/rules.md"]}]
        code, _out, err = self._recall()
        self.assertEqual(code, 1)
        self.assertIn("does not name a commit", err)
        with self.assertRaises(GitError):
            recall.measure(self.root, [recall.Commit(hash="-x", parent=self.parent, files=())], ALL)

    def test_hunks_count_their_lines(self) -> None:
        output = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -2 +1,0 @@\n--- a rule\n@@ -5,2 +4 @@\n-one\n-two\n+new\n"
        self.assertEqual(recall.parse_hunks(output), [(2, "-- a rule"), (5, "one"), (6, "two")])


if __name__ == "__main__":
    unittest.main()
