# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``ruleset_renumber.py`` on small temporary git repositories."""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ruleset_renumber as rr  # noqa: E402

DAY = "2026-11-20"


def _row(revision: str, text: str) -> str:
    return f"| `{revision}` | 2026-11-20 | 61 | {text} |\n"


def _changelog(rows: list[tuple[str, str]]) -> str:
    return "# Changelog\n\n| Revision | Date | Checks | What |\n|---|---|---|---|\n" + "".join(
        _row(r, t) for r, t in rows
    )


def _write_state(root: Path, rows: list[tuple[str, str]], extra: str = "") -> None:
    newest = rows[0][0]
    files = {
        rr.CHANGELOG: _changelog(rows),
        rr.INIT: f'x = 1\n__ruleset_revision__ = "{newest}"\n',
        rr.BASELINE: f'{{\n  "ruleset_revision": "{newest}",\n  "n": 1\n}}\n',
        rr.SELF_AUDIT: f"| Field | Value |\n| Ruleset | `{newest}` (hash `abc`) |\nBetween `{rows[-1][0]}` and `{newest}`.\n",
        "audit/catalogue.json": '{"since_ruleset": "' + rows[-1][0] + '"}\n',
        "notes.txt": extra,
    }
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class Repo:
    """A temporary git repository with a ``dev`` branch and a ``feature`` branch."""

    def __init__(self, test: unittest.TestCase) -> None:
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.git("init", "-q", "-b", "dev")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args: str, check: bool = True) -> str:
        done = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, check=check)
        return done.stdout

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


def _two_branches(test: unittest.TestCase, base_rev: str, branch_rev: str, *, merge: str = "") -> Repo:
    """dev and feature both add a row on top of ``.1``; ``merge`` is "" (not merged), "start" or "clean"."""
    repo = Repo(test)
    start = [(f"{DAY}.1", "first")]
    _write_state(repo.root, start)
    repo.commit("start")
    repo.git("switch", "-q", "-c", "feature")
    _write_state(repo.root, [(branch_rev, "branch change"), *start])
    repo.commit("feature")
    repo.git("switch", "-q", "dev")
    _write_state(repo.root, [(base_rev, "base change"), *start])
    repo.commit("base")
    repo.git("switch", "-q", "feature")
    repo.git("update-ref", "refs/remotes/origin/dev", "dev")
    if merge:
        repo.git("merge", "--no-commit", "--no-ff", "dev", check=False)
        if merge == "clean":
            repo.git("add", "-A")
            repo.git("commit", "-q", "-m", "merge", "--allow-empty")
    return repo


def _run(root: Path, verb: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = rr.main([verb, "--root", str(root)])
    return code, out.getvalue(), err.getvalue()


class CheckTests(unittest.TestCase):
    def test_branch_without_a_revision_reports_nothing(self) -> None:
        repo = Repo(self)
        _write_state(repo.root, [(f"{DAY}.1", "first")])
        repo.commit("start")
        repo.git("update-ref", "refs/remotes/origin/dev", "HEAD")
        self.assertEqual(_run(repo.root, "check"), (0, "", ""))
        self.assertEqual(_run(repo.root, "apply"), (0, "nothing to renumber\n", ""))

    def test_a_new_number_is_listed_and_passes(self) -> None:
        repo = Repo(self)
        _write_state(repo.root, [(f"{DAY}.1", "first")])
        repo.commit("start")
        repo.git("update-ref", "refs/remotes/origin/dev", "HEAD")
        _write_state(repo.root, [(f"{DAY}.2", "new"), (f"{DAY}.1", "first")], extra=f"see {DAY}.2\n")
        repo.commit("add")
        code, out, _ = _run(repo.root, "check")
        self.assertEqual(code, 0)
        self.assertIn(f"branch revision: {DAY}.2", out)
        self.assertIn("notes.txt (NOT HANDLED)", out)
        self.assertIn(rr.CHANGELOG + " (handled)", out)

    def test_two_branches_with_one_number_collide(self) -> None:
        repo = _two_branches(self, f"{DAY}.2", f"{DAY}.2")
        code, out, _ = _run(repo.root, "check")
        self.assertEqual(code, 2)
        self.assertIn(f"branch revision: {DAY}.2 (also on the base)", out)

    def test_branches_with_different_numbers_do_not_collide(self) -> None:
        repo = _two_branches(self, f"{DAY}.2", f"{DAY}.3")
        self.assertEqual(_run(repo.root, "check")[0], 0)

    def test_a_clean_merge_that_duplicates_a_number_fails(self) -> None:
        repo = _two_branches(self, f"{DAY}.2", f"{DAY}.2")
        # Reproduce the silent merge: put the base row under the branch row.
        text = (repo.root / rr.CHANGELOG).read_text(encoding="utf-8")
        row = _row(f"{DAY}.2", "base change")
        (repo.root / rr.CHANGELOG).write_text(text.replace(_row(f"{DAY}.1", "first"), row + _row(f"{DAY}.1", "first")))
        repo.commit("merged by hand")
        code, out, _ = _run(repo.root, "check")
        self.assertEqual(code, 2)
        self.assertIn(f"changelog rows share the revision {DAY}.2", out)


class ApplyTests(unittest.TestCase):
    def _assert_renumbered(self, root: Path) -> None:
        self.assertIn(f'__ruleset_revision__ = "{DAY}.3"', (root / rr.INIT).read_text())
        self.assertIn(f'"ruleset_revision": "{DAY}.3"', (root / rr.BASELINE).read_text())
        self.assertIn(f"| Ruleset | `{DAY}.3`", (root / rr.SELF_AUDIT).read_text())
        rows = rr.row_lines((root / rr.CHANGELOG).read_text())
        self.assertEqual([rr.row_revision(r) for r in rows], [f"{DAY}.3", f"{DAY}.2", f"{DAY}.1"])
        self.assertIn("branch change", rows[0])
        self.assertIn("base change", rows[1])

    def test_apply_before_the_merge_moves_the_branch_row(self) -> None:
        repo = _two_branches(self, f"{DAY}.2", f"{DAY}.2")
        code, out, _ = _run(repo.root, "apply")
        self.assertEqual(code, 0, out)
        self.assertIn(f"renumber {DAY}.2 -> {DAY}.3", out)
        rows = rr.row_lines((repo.root / rr.CHANGELOG).read_text())
        self.assertEqual([rr.row_revision(r) for r in rows], [f"{DAY}.3", f"{DAY}.1"])
        repo.commit("renumbered")
        self.assertEqual(_run(repo.root, "apply"), (0, "nothing to renumber\n", ""))

    def test_apply_in_a_conflicted_merge(self) -> None:
        repo = _two_branches(self, f"{DAY}.2", f"{DAY}.2", merge="start")
        self.assertIn("UU", repo.git("status", "--porcelain"))
        code, out, err = _run(repo.root, "apply")
        self.assertEqual(code, 0, out + err)  # both sides wrote the same current-revision lines: no conflict there
        self.assertIn("resolved a conflict hunk, kept both sides", out)
        rows = rr.row_lines((repo.root / rr.CHANGELOG).read_text())
        self.assertEqual([rr.row_revision(r) for r in rows], [f"{DAY}.3", f"{DAY}.2", f"{DAY}.1"])
        self.assertIn(f'__ruleset_revision__ = "{DAY}.3"', (repo.root / rr.INIT).read_text())
        self.assertNotIn("<<<<<<<", (repo.root / rr.INIT).read_text())

    def test_apply_after_a_clean_merge_keeps_the_base_row(self) -> None:
        repo = _two_branches(self, f"{DAY}.2", f"{DAY}.2")
        text = (repo.root / rr.CHANGELOG).read_text()
        row = _row(f"{DAY}.2", "base change")
        (repo.root / rr.CHANGELOG).write_text(text.replace(_row(f"{DAY}.1", "first"), row + _row(f"{DAY}.1", "first")))
        repo.commit("merged")
        code, out, err = _run(repo.root, "apply")
        self.assertEqual(code, 0, out + err)
        self._assert_renumbered(repo.root)

    def test_a_silent_identical_current_revision_is_set_to_the_newest(self) -> None:
        # Both sides wrote the same current-revision line, so git merges it without a conflict.
        repo = _two_branches(self, f"{DAY}.2", f"{DAY}.2")
        _run(repo.root, "apply")
        self.assertIn(f'"{DAY}.3"', (repo.root / rr.INIT).read_text())

    def test_a_name_in_an_unknown_file_is_reported_not_rewritten(self) -> None:
        repo = Repo(self)
        _write_state(repo.root, [(f"{DAY}.1", "first")])
        repo.commit("start")
        repo.git("update-ref", "refs/remotes/origin/dev", "HEAD")
        _write_state(repo.root, [(f"{DAY}.2", "new"), (f"{DAY}.1", "first")], extra=f"see {DAY}.2\n")
        repo.commit("add")
        code, out, _ = _run(repo.root, "apply")
        self.assertEqual(code, 2)
        self.assertIn("cannot rewrite notes.txt", out)
        self.assertEqual((repo.root / "notes.txt").read_text(), f"see {DAY}.2\n")

    def test_a_dirty_tree_is_refused(self) -> None:
        repo = _two_branches(self, f"{DAY}.2", f"{DAY}.2")
        (repo.root / "stray.txt").write_text("x")
        code, _, err = _run(repo.root, "apply")
        self.assertEqual(code, 1)
        self.assertIn("dirty", err)

    def test_a_rebase_in_progress_is_refused(self) -> None:
        repo = _two_branches(self, f"{DAY}.2", f"{DAY}.2")
        (repo.root / ".git" / "rebase-merge").mkdir()
        self.assertEqual(_run(repo.root, "apply")[0], 1)

    def test_a_conflict_hunk_in_another_file_is_left_and_reported(self) -> None:
        notes: list[str] = []
        text = "a\n<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> dev\nb\n"
        out, unresolved = rr._resolve_conflicts(text, rr.SELF_AUDIT, notes)
        self.assertTrue(unresolved)
        self.assertIn("<<<<<<<", out)
        self.assertIn("NOT resolved", notes[0])

    def test_plan_chains_two_branch_revisions(self) -> None:
        analysis = rr.Analysis(base_newest=f"{DAY}.5", base_revisions={f"{DAY}.5"})
        analysis.branch_rows = [_row(f"{DAY}.5", "a").rstrip("\n"), _row(f"{DAY}.4", "b").rstrip("\n")]
        self.assertEqual(analysis.plan(), {f"{DAY}.4": f"{DAY}.6", f"{DAY}.5": f"{DAY}.7"})

    def test_a_missing_changelog_on_the_base_is_a_usage_error(self) -> None:
        repo = Repo(self)
        (repo.root / "a.txt").write_text("x")
        repo.commit("start")
        repo.git("update-ref", "refs/remotes/origin/dev", "HEAD")
        self.assertEqual(_run(repo.root, "check")[0], 1)


if __name__ == "__main__":
    unittest.main()
