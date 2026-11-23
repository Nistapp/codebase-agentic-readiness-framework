# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The target's history is guarded (ADR 0007): ``progress.py init`` and ``adopt`` record the tips of the target's
branches, tags and ``origin/*`` branches beside the state, and ``verify-refs`` exits 2 when a recorded ref is gone, a
branch no longer contains its recorded tip, or a tag moved. ``accept-ref --by owner`` takes a rewrite the owner made on
purpose. Every case runs against a scratch git repository. Standard library only, in process.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import _implement_paths  # noqa: F401  (puts the tools folders on sys.path)
import _git
import progress
from test_progress import REPORT, call, tree_bytes
from test_progress_transitions import TransitionCase

LABEL = "example-service"
RECORDED = {
    "refs/heads/feature",
    "refs/heads/main",
    "refs/remotes/origin/main",
    "refs/tags/v1",
    "refs/tags/v1-annotated",
}


def git(root: Path, *args: str) -> str:
    return _git.run_git(root, *args)


def commit(root: Path, name: str) -> str:
    (root / name).write_text(name + "\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", name)
    return git(root, "rev-parse", "HEAD")


def make_target(root: Path) -> None:
    """A repository with two commits on main, a feature branch, two tags and an origin branch with origin/HEAD."""
    _git.make_repo(root)
    commit(root, "second.txt")
    git(root, "branch", "feature")
    git(root, "tag", "v1")
    git(root, "tag", "-a", "v1-annotated", "-m", "v1")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")


class RefTipsCase(TransitionCase):
    def setUp(self) -> None:
        super().setUp()
        self.ref_path = self.state_dir / progress.ref_tips_name(LABEL)

    def init_ok(self) -> dict[str, Any]:
        """`init` on a target that is a git repository: TransitionCase.setUp runs it once."""
        if not (self.target / ".git").exists():
            make_target(self.target)
        return super().init_ok()

    def recorded(self) -> dict[str, str]:
        document: dict[str, Any] = json.loads(self.ref_path.read_text(encoding="utf-8"))
        return {entry["ref"]: entry["tip"] for entry in document["refs"]}

    def verify(self) -> tuple[int, dict[str, Any], str]:
        return call(["verify-refs", "--target", str(self.target), "--workspace", str(self.state_dir)])

    def assert_clean(self) -> dict[str, Any]:
        code, envelope, err = self.verify()
        self.assertEqual(code, 0, (envelope, err))
        self.assertEqual(envelope["data"]["status"], "clean")
        return envelope

    def assert_lost(self, *lines: str) -> tuple[dict[str, Any], str]:
        code, envelope, err = self.verify()
        self.assertEqual(code, 2, (envelope, err))
        self.assertIn("lost history", envelope["data"]["error"])
        self.assertEqual(len(envelope["data"]["errors"]), len(lines), envelope["data"]["errors"])
        for line, wanted in zip(envelope["data"]["errors"], lines):
            self.assertIn(wanted, line)
            self.assertIn(wanted, err)
        self.assertIn("accept-ref REF --reason TEXT --by owner", err)
        return envelope, err

    def accept(self, ref: str, by: str | None = "owner") -> tuple[int, dict[str, Any], str]:
        return self.run_cmd("accept-ref", ref, "--target", str(self.target), "--reason", "the owner did it", by=by)


class RecordTests(RefTipsCase):
    def test_init_records_each_branch_tag_and_origin_branch_but_no_symbolic_ref(self) -> None:
        self.assertEqual(set(self.recorded()), RECORDED)
        main = git(self.target, "rev-parse", "main")
        self.assertEqual(self.recorded()["refs/heads/main"], main[:12])
        document = json.loads(self.ref_path.read_text(encoding="utf-8"))
        self.assertEqual((document["tool"], document["kind"], document["label"]), ("progress", "ref-tips", LABEL))
        self.assertEqual(document["recorded"], "2026-10-29")
        self.assertEqual(self.temporaries(), [])

    def test_init_reads_the_target_and_writes_nothing_there(self) -> None:
        shutil.rmtree(self.state_dir)
        self.state_dir.mkdir()
        shutil.copyfile(REPORT, self.report)
        before = tree_bytes(self.target)
        envelope = self.init_ok()
        self.assertEqual(tree_bytes(self.target), before)
        self.assertEqual(Path(envelope["data"]["ref_tips"]), self.ref_path)

    def test_init_refuses_a_ref_record_left_from_an_earlier_run(self) -> None:
        self.json_path.unlink()
        self.md_path.unlink()
        before = self.ref_path.read_bytes()
        code, envelope, _ = self.init()
        self.assertEqual(code, 1, envelope)
        self.assertIn("a ref record already exists", envelope["data"]["error"])
        self.assertTrue(self.no_state())
        self.assertEqual(self.ref_path.read_bytes(), before)


class VerifyTests(RefTipsCase):
    def test_an_untouched_target_is_clean(self) -> None:
        envelope = self.assert_clean()
        self.assertEqual((envelope["data"]["checked"], envelope["data"]["new"]), (len(RECORDED), 0))

    def test_verify_refs_writes_nothing(self) -> None:
        before_target, before_workspace = tree_bytes(self.target), tree_bytes(self.state_dir)
        self.assert_clean()
        self.assertEqual(tree_bytes(self.target), before_target)
        self.assertEqual(tree_bytes(self.state_dir), before_workspace)

    def test_a_branch_that_moved_forward_is_clean(self) -> None:
        commit(self.target, "third.txt")
        git(self.target, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.assert_clean()

    def test_a_new_branch_and_tag_are_not_reported(self) -> None:
        git(self.target, "switch", "-q", "-c", "agentic-readiness/t1")
        commit(self.target, "theme.txt")
        git(self.target, "tag", "theme-tag")
        envelope = self.assert_clean()
        self.assertEqual(envelope["data"]["new"], 2)

    def test_a_deleted_branch_is_reported(self) -> None:
        git(self.target, "branch", "-q", "-D", "feature")
        self.assert_lost("refs/heads/feature is gone")

    def test_a_deleted_tag_is_reported(self) -> None:
        git(self.target, "tag", "-d", "v1")
        self.assert_lost("refs/tags/v1 is gone")

    def test_a_moved_tag_is_reported_even_when_it_moved_forward(self) -> None:
        commit(self.target, "third.txt")
        git(self.target, "tag", "-f", "v1")
        self.assert_lost("refs/tags/v1 pointed at")

    def test_an_amended_branch_is_reported(self) -> None:
        git(self.target, "commit", "-q", "--amend", "-m", "amended")
        self.assert_lost("refs/heads/main no longer contains its recorded tip")

    def test_a_force_reset_branch_is_reported(self) -> None:
        git(self.target, "reset", "-q", "--hard", "HEAD~1")
        self.assert_lost("refs/heads/main no longer contains its recorded tip")

    def test_a_rebased_branch_is_reported(self) -> None:
        git(self.target, "switch", "-q", "feature")
        commit(self.target, "feature.txt")
        git(self.target, "switch", "-q", "main")
        commit(self.target, "main.txt")
        # Record again: feature now has a commit of its own.
        self.ref_path.unlink()
        self.ok("record-refs", "--target", str(self.target))
        git(self.target, "rebase", "-q", "main", "feature")
        self.assert_lost("refs/heads/feature no longer contains its recorded tip")

    def test_a_rewritten_or_pruned_origin_branch_is_reported(self) -> None:
        orphan = git(self.target, "commit-tree", "HEAD^{tree}", "-m", "unrelated")
        git(self.target, "update-ref", "refs/remotes/origin/main", orphan)
        self.assert_lost("refs/remotes/origin/main no longer contains its recorded tip")
        git(self.target, "update-ref", "-d", "refs/remotes/origin/main")
        self.assert_lost("refs/remotes/origin/main is gone")

    def test_every_lost_ref_is_listed(self) -> None:
        git(self.target, "branch", "-q", "-D", "feature")
        git(self.target, "tag", "-d", "v1-annotated")
        envelope, _ = self.assert_lost("refs/heads/feature is gone", "refs/tags/v1-annotated is gone")
        self.assertIn("2 recorded refs", envelope["data"]["error"])

    def test_a_target_that_is_not_the_top_of_a_work_tree_is_refused(self) -> None:
        inner = self.target / "sub"
        inner.mkdir()
        code, envelope, _ = call(["verify-refs", "--target", str(inner), "--workspace", str(self.state_dir)])
        self.assertEqual(code, 1, envelope)
        self.assertIn("not the top folder of a git work tree", envelope["data"]["error"])

    def test_a_hand_edited_record_is_refused(self) -> None:
        for text in ("not json", json.dumps({"tool": "progress", "kind": "ref-tips", "label": LABEL, "refs": []}),
                     json.dumps({"tool": "progress", "kind": "ref-tips", "label": LABEL, "recorded": "d",
                                 "refs": [{"ref": "refs/heads/main", "tip": "short"}]})):  # fmt: skip
            with self.subTest(text=text):
                self.ref_path.write_text(text, encoding="utf-8")
                code, envelope, _ = self.verify()
                self.assertEqual(code, 2, envelope)
                self.assertIn("is not a ref record that progress.py wrote", envelope["data"]["error"])

    def test_a_record_that_lists_a_ref_twice_is_refused(self) -> None:
        entry = {"ref": "refs/heads/main", "tip": "a" * 12}
        document = {"tool": "progress", "kind": "ref-tips", "label": LABEL, "recorded": "d", "refs": [entry, entry]}
        self.ref_path.write_text(json.dumps(document), encoding="utf-8")
        code, envelope, _ = self.verify()
        self.assertEqual(code, 2, envelope)
        self.assertIn("lists a ref twice", envelope["data"]["error"])


class MissingRecordTests(RefTipsCase):
    def test_a_state_without_a_record_says_the_check_did_not_run_and_record_refs_starts_it(self) -> None:
        self.ref_path.unlink()
        code, envelope, err = self.verify()
        self.assertEqual(code, 1, envelope)
        self.assertIn("the history check did not run", envelope["data"]["error"])
        self.assertIn("record-refs", err)
        git(self.target, "branch", "-q", "-D", "feature")
        self.ok("record-refs", "--target", str(self.target))
        self.assertEqual(set(self.recorded()), RECORDED - {"refs/heads/feature"})
        self.assertIn("ref tips recorded for 4 refs", self.state()["log"][-1]["event"])
        self.assert_clean()
        self.refused("record-refs", "--target", str(self.target), text="a ref record already exists")

    def test_a_target_that_is_not_a_git_repository_records_nothing_and_warns(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        workspace = self.tmp / "plain-run"
        workspace.mkdir()
        shutil.copyfile(REPORT, workspace / REPORT.name)
        code, envelope, _ = call(["init", "--report", str(workspace / REPORT.name), "--target", str(plain)])
        self.assertEqual(code, 0, envelope)
        self.assertIsNone(envelope["data"]["ref_tips"])
        self.assertTrue(any("verify-refs cannot guard the history" in w for w in envelope["warnings"]))
        self.assertFalse((workspace / progress.ref_tips_name(LABEL)).exists())

    def test_record_refs_refuses_a_workspace_inside_the_target(self) -> None:
        self.ref_path.unlink()
        code, envelope, _ = self.run_cmd("record-refs", "--target", str(self.tmp))
        self.assertEqual(code, 1, envelope)
        self.assertIn("the workspace is inside the target", envelope["data"]["error"])
        self.assertFalse(self.ref_path.exists())


class AcceptTests(RefTipsCase):
    def test_only_the_owner_accepts_a_ref(self) -> None:
        git(self.target, "branch", "-q", "-D", "feature")
        self.refused("accept-ref", "refs/heads/feature", "--target", str(self.target), "--reason", "r",
                     text="accept-ref is an owner decision")  # fmt: skip
        self.assert_lost("refs/heads/feature is gone")

    def test_an_accepted_deleted_branch_is_dropped_from_the_record(self) -> None:
        git(self.target, "branch", "-q", "-D", "feature")
        code, envelope, err = self.accept("refs/heads/feature")
        self.assertEqual(code, 0, (envelope, err))
        self.assertNotIn("refs/heads/feature", self.recorded())
        event = self.state()["log"][-1]["event"]
        self.assertIn("ref refs/heads/feature gone accepted by owner", event)
        self.assertIn("the owner did it", event)
        self.assert_clean()

    def test_an_accepted_rewrite_becomes_the_recorded_tip_and_a_later_rewrite_is_reported_again(self) -> None:
        git(self.target, "commit", "-q", "--amend", "-m", "amended")
        code, envelope, err = self.accept("refs/heads/main")
        self.assertEqual(code, 0, (envelope, err))
        self.assertEqual(self.recorded()["refs/heads/main"], git(self.target, "rev-parse", "HEAD")[:12])
        self.assert_clean()
        git(self.target, "commit", "-q", "--amend", "-m", "amended again")
        self.assert_lost("refs/heads/main no longer contains its recorded tip")

    def test_accept_refuses_an_unrecorded_ref_and_an_intact_one(self) -> None:
        git(self.target, "branch", "agentic-readiness/t1")
        before = self.ref_path.read_bytes()
        self.refused("accept-ref", "refs/heads/agentic-readiness/t1", "--target", str(self.target), "--reason", "r",
                     by="owner", text="is not a recorded ref")  # fmt: skip
        self.refused("accept-ref", "refs/heads/main", "--target", str(self.target), "--reason", "r", by="owner",
                     text="still holds its recorded tip")  # fmt: skip
        self.assertEqual(self.ref_path.read_bytes(), before)

    def test_accept_needs_a_record(self) -> None:
        self.ref_path.unlink()
        self.refused("accept-ref", "refs/heads/main", "--target", str(self.target), "--reason", "r", by="owner",
                     text="the history check did not run")  # fmt: skip
