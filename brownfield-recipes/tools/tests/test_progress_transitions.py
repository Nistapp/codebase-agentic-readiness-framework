# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`progress.py set-status`, `skip`, `unskip`, `defer`, `undefer`, `pref` and `theme`.

Every legal move of the state diagram is run, and every illegal one is shown to be refused with a message of its own and
to leave the state file byte for byte as it was. Each test starts from the state `init` makes from the framework's
synthetic example report. Standard library only.
"""

from __future__ import annotations

import json
import re
import unittest
from typing import Any
from unittest import mock

import _common
import progress
from test_progress import MD_NAME, TargetCase, call

SHA = "aaaabbbbcccc"
SHA2 = "ddddeeeeffff"


class TransitionCase(TargetCase):
    def setUp(self) -> None:
        super().setUp()
        self.init_ok()
        self.queued = self.first("queued")
        self.deferred = self.first("deferred")

    def state(self) -> dict[str, Any]:
        data: dict[str, Any] = json.loads(self.json_path.read_text(encoding="utf-8"))
        return data

    def first(self, status: str) -> str:
        found: str = next(item["finding"] for item in self.state()["items"] if item["status"] == status)
        return found

    def item(self, finding: str) -> dict[str, Any]:
        return next(item for item in self.state()["items"] if item["finding"] == finding)

    def run_cmd(self, *argv: str, by: str | None = None) -> tuple[int, dict[str, Any], str]:
        tail = ["--target", str(self.target), "--phase", "IRtest", "--date", "2026-11-01"]
        if by:
            tail += ["--by", by]
        return call([*argv, *tail])

    def ok(self, *argv: str, by: str | None = None) -> dict[str, Any]:
        code, envelope, err = self.run_cmd(*argv, by=by)
        self.assertEqual(code, 0, (envelope, err))
        return envelope

    def refused(self, *argv: str, by: str | None = None, text: str, code: int = 1) -> None:
        before = self.json_path.read_bytes()
        got, envelope, _ = self.run_cmd(*argv, by=by)
        self.assertEqual(got, code, envelope)
        self.assertFalse(envelope["ok"])
        message = envelope["data"]["error"]
        self.assertRegex(message, text)
        self.assertEqual(self.json_path.read_bytes(), before, "a refused command changed the state")

    def to_in_progress(self, finding: str | None = None) -> str:
        finding = finding or self.queued
        self.ok("set-status", finding, "in_progress")
        return finding


class LegalMoveTests(TransitionCase):
    def test_every_legal_move_of_the_diagram_works(self) -> None:
        f = self.queued
        for new in ("in_progress", "blocked"):
            self.ok("set-status", f, new, *(["--reason", "waits for T3"] if new == "blocked" else []))
        self.ok("set-status", f, "queued")
        self.ok("set-status", f, "in_progress")
        self.ok("set-status", f, "failed", "--reason", "does not apply")
        self.ok("set-status", f, "in_progress")
        self.ok("set-status", f, "partial", "--debt", "what=lint errors,count=3,baseline=lint.baseline")
        self.ok("set-status", f, "in_progress")
        self.ok(
            "set-status",
            f,
            "done",
            "--clear-debt",
            "--verification-command",
            "make lint",
            "--verification-result",
            "ok",
        )
        self.assertEqual(self.item(f)["status"], "done")

    def test_owner_moves_work_and_log(self) -> None:
        f = self.queued
        self.ok("skip", f, "--reason", "not wanted", by="owner")
        self.assertEqual(self.item(f)["status"], "skipped")
        self.assertEqual(self.item(f)["reason"], "not wanted")
        self.ok("unskip", f, by="owner")
        self.assertEqual((self.item(f)["status"], self.item(f)["reason"]), ("queued", None))
        self.ok("defer", f, "--reason", "later", by="owner")
        self.assertEqual(self.item(f)["status"], "deferred")
        self.ok("undefer", f, by="owner")
        self.assertEqual(self.item(f)["status"], "queued")
        events = [entry["event"] for entry in self.state()["log"][-4:]]
        self.assertEqual(
            [re.sub(r":.*", "", e) for e in events],
            [f"{f} queued to skipped by owner", f"{f} skipped to queued by owner",
             f"{f} queued to deferred by owner", f"{f} deferred to queued by owner"],
        )  # fmt: skip

    def test_the_deferred_item_of_the_audit_can_be_undeferred(self) -> None:
        self.ok("undefer", self.deferred, by="owner")
        self.assertEqual(self.item(self.deferred)["status"], "queued")

    def test_a_write_records_who_when_and_a_log_entry(self) -> None:
        f = self.to_in_progress()
        item = self.item(f)
        self.assertEqual((item["by"], item["date"]), ("agent", "2026-11-01"))
        last = self.state()["log"][-1]
        self.assertEqual(
            last, {"date": "2026-11-01", "phase": "IRtest", "event": f"{f} queued to in_progress by agent"}
        )

    def test_commits_accumulate_without_repeats_and_verification_is_kept(self) -> None:
        f = self.to_in_progress()
        self.ok("set-status", f, "failed", "--reason", "x", "--commit", SHA)
        self.ok("set-status", f, "in_progress", "--commit", SHA, "--commit", SHA2, "--note", "retry")
        self.ok(
            "set-status", f, "failed", "--reason", "y", "--verification-command", "make", "--verification-result", "2"
        )
        item = self.item(f)
        self.assertEqual(item["commits"], [SHA, SHA2])
        self.assertEqual(item["verification"], {"command": "make", "result": "2"})
        self.assertEqual(item["notes"], "retry")
        self.assertEqual(item["reason"], "y")

    def test_leaving_failed_clears_the_reason(self) -> None:
        f = self.to_in_progress()
        self.ok("set-status", f, "blocked", "--reason", "waits")
        self.assertEqual(self.item(f)["reason"], "waits")
        self.ok("set-status", f, "queued")
        self.assertIsNone(self.item(f)["reason"])

    def test_a_debt_entry_with_the_same_name_is_replaced(self) -> None:
        f = self.to_in_progress()
        self.ok("set-status", f, "partial", "--debt", "what=lint,count=9", "--debt", "what=fmt,count=2")
        self.ok("set-status", f, "in_progress", "--debt", "what=lint,count=4,baseline=b.txt")
        self.assertEqual(
            self.item(f)["debt"],
            [
                {"what": "fmt", "count": 2, "baseline_file": None},
                {"what": "lint", "count": 4, "baseline_file": "b.txt"},
            ],
        )


class IllegalMoveTests(TransitionCase):
    def test_same_status(self) -> None:
        self.refused("set-status", self.queued, "queued", text="already queued")

    def test_queued_cannot_jump_to_a_result(self) -> None:
        for new in ("done", "partial", "failed", "blocked"):
            self.refused("set-status", self.queued, new, text="must be in_progress before")

    def test_in_progress_cannot_go_back_to_queued(self) -> None:
        f = self.to_in_progress()
        self.refused("set-status", f, "queued", text="end it as done, partial, failed or blocked")

    def test_in_progress_cannot_be_skipped_or_deferred(self) -> None:
        f = self.to_in_progress()
        self.refused("skip", f, "--reason", "r", by="owner", text="only a queued item can be skipped")
        self.refused("defer", f, "--reason", "r", by="owner", text="only a queued item can be deferred")

    def test_partial_and_failed_go_back_to_in_progress_only(self) -> None:
        f = self.to_in_progress()
        self.ok("set-status", f, "partial", "--debt", "what=x,count=1")
        self.refused("set-status", f, "done", text="partial and can only go back to in_progress")
        self.ok("set-status", f, "in_progress")
        self.ok("set-status", f, "failed", "--reason", "r")
        self.refused("set-status", f, "queued", text="failed and can only go back to in_progress")

    def test_blocked_goes_back_to_queued_only(self) -> None:
        f = self.to_in_progress()
        self.ok("set-status", f, "blocked", "--reason", "r")
        self.refused("set-status", f, "in_progress", text="blocked and can only go back to queued")

    def test_done_is_final(self) -> None:
        f = self.to_in_progress()
        self.ok("set-status", f, "done", "--verification-command", "c", "--verification-result", "r")
        self.refused("set-status", f, "in_progress", text="done is final")
        self.refused("set-status", f, "queued", text="done is final")

    def test_set_status_does_not_do_the_owner_moves(self) -> None:
        self.refused("set-status", self.queued, "skipped", text="has its own command")
        self.refused("set-status", self.queued, "deferred", text="has its own command")
        self.refused("set-status", self.deferred, "queued", text="has its own command")
        self.refused(
            "set-status", self.deferred, "in_progress", text="deferred and goes back to queued only with undefer"
        )

    def test_skipped_can_only_be_left_by_unskip_by_owner(self) -> None:
        f = self.queued
        self.ok("skip", f, "--reason", "no", by="owner")
        for new in ("queued", "in_progress", "done", "partial", "failed", "blocked", "deferred"):
            self.refused("set-status", f, new, text="skipped and only the owner can bring it back")
        self.refused("unskip", f, text="owner decision")
        self.refused("unskip", f, by="agent", text="owner decision")
        self.refused("undefer", f, by="owner", text="not deferred")
        self.ok("unskip", f, by="owner")
        self.assertEqual(self.item(f)["status"], "queued")

    def test_owner_moves_need_the_owner(self) -> None:
        for command in ("skip", "defer"):
            self.refused(command, self.queued, "--reason", "r", text="owner decision")
        self.refused("undefer", self.deferred, text="owner decision")

    def test_unskip_of_an_item_that_is_not_skipped(self) -> None:
        self.refused("unskip", self.queued, by="owner", text="already queued")

    def test_skip_and_defer_need_a_reason(self) -> None:
        code, envelope, _ = self.run_cmd("skip", self.queued, by="owner")
        self.assertEqual(code, 1, envelope)
        self.assertEqual(self.item(self.queued)["status"], "queued")

    def test_unknown_and_rejected_findings(self) -> None:
        self.refused("set-status", "F-999", "in_progress", text="no item for F-999")
        rejected = self.state()["not_queued"][0]["finding"]
        self.refused("set-status", rejected, "in_progress", text="rejected in the audit")
        self.refused("skip", rejected, "--reason", "r", by="owner", text="rejected in the audit")

    def test_done_needs_verification_and_no_debt(self) -> None:
        f = self.to_in_progress()
        self.refused("set-status", f, "done", text="without a verification")
        self.refused(
            "set-status", f, "done", "--verification-command", "c", "--verification-result", "r",
            "--debt", "what=x,count=1", text="debt is partial, never done",
        )  # fmt: skip
        self.ok("set-status", f, "partial", "--debt", "what=x,count=1")
        self.ok("set-status", f, "in_progress")
        self.refused("set-status", f, "done", "--verification-command", "c", "--verification-result", "r",
                     text="still has 1 debt")  # fmt: skip

    def test_partial_needs_debt_and_failed_blocked_need_a_reason(self) -> None:
        f = self.to_in_progress()
        self.refused("set-status", f, "partial", text="cannot be partial without debt")
        self.refused("set-status", f, "failed", text="cannot be failed without --reason")
        self.refused("set-status", f, "blocked", text="cannot be blocked without --reason")

    def test_bad_arguments(self) -> None:
        f = self.to_in_progress()
        self.refused("set-status", f, "partial", "--debt", "lint=3", text="--debt must look like")
        self.refused("set-status", f, "failed", "--reason", "r", "--commit", "XYZ", text="--commit must be")
        self.refused("set-status", f, "failed", "--reason", "r", "--verification-command", "c", text="go together")
        self.refused("set-status", f, "failed", "--reason", "r", "--note", "n" * 2100, text="state invalid", code=2)

    def test_an_invalid_state_is_refused_and_not_written(self) -> None:
        f = self.to_in_progress()
        with mock.patch.object(progress, "state_errors", return_value=["rule: planted"]):
            before = self.json_path.read_bytes()
            code, envelope, _ = self.run_cmd("set-status", f, "failed", "--reason", "r")
        self.assertEqual(code, 2, envelope)
        self.assertEqual(self.json_path.read_bytes(), before)


class PreferenceTests(TransitionCase):
    def test_set_replace_and_unset(self) -> None:
        self.ok("pref", "set", "java.formatter", "palantir", "--reason", "owner choice", by="owner")
        pref = self.state()["preferences"][0]
        self.assertEqual(
            pref,
            {"key": "java.formatter", "value": "palantir", "reason": "owner choice", "by": "owner",
             "date": "2026-11-01", "phase": "IRtest"},
        )  # fmt: skip
        self.ok("pref", "set", "java.formatter", "google", "--reason", "changed mind", by="owner")
        self.assertEqual([p["value"] for p in self.state()["preferences"]], ["google"])
        self.assertIn("changed from palantir to google", self.state()["log"][-1]["event"])
        self.ok("pref", "unset", "java.formatter", "--reason", "gone", by="owner")
        self.assertEqual(self.state()["preferences"], [])

    def test_refusals(self) -> None:
        self.refused("pref", "set", "k", "v", "--reason", "r", text="owner decision")
        self.refused("pref", "set", "k", "--reason", "r", by="owner", text="needs a value")
        self.refused("pref", "unset", "k", "v", "--reason", "r", by="owner", text="only the key")
        self.refused("pref", "unset", "k", "--reason", "r", by="owner", text="no preference k")
        self.ok("pref", "set", "k", "v", "--reason", "r", by="owner")
        self.refused("pref", "set", "k", "v", "--reason", "r2", by="owner", text="already has that value")
        self.refused("pref", "set", "Bad Key", "v", "--reason", "r", by="owner", text="state invalid", code=2)


class ThemeTests(TransitionCase):
    def theme(self, theme_id: str = "T1") -> dict[str, Any]:
        return next(t for t in self.state()["themes"] if t["id"] == theme_id)

    def test_a_theme_walks_forward(self) -> None:
        self.ok("theme", "T1", "--status", "branch_open", "--branch", "agentic-readiness/ir04-x")
        self.assertEqual(self.theme()["phase"], "IRtest")
        self.ok("theme", "T1", "--status", "pr_open", "--pr", "12")
        self.assertEqual((self.theme()["branch"], self.theme()["pr"]), ("agentic-readiness/ir04-x", 12))
        self.ok("theme", "T1", "--status", "merged", "--merged-sha", SHA)
        self.assertEqual(
            self.theme(),
            {"id": "T1", "title": self.theme()["title"], "status": "merged", "phase": "IRtest",
             "branch": "agentic-readiness/ir04-x", "pr": 12, "merged_sha": SHA},
        )  # fmt: skip
        self.assertIn("theme T1 pr_open to merged", self.state()["log"][-1]["event"])

    def test_a_theme_may_skip_a_step_when_it_has_the_data(self) -> None:
        self.ok("theme", "T2", "--status", "pr_open", "--branch", "b", "--pr", "3")
        self.assertEqual(self.theme("T2")["status"], "pr_open")

    def test_refusals(self) -> None:
        self.refused("theme", "T1", "--status", "branch_open", text="needs --branch")
        self.refused("theme", "T1", "--status", "pr_open", "--branch", "b", text="needs --pr")
        self.refused("theme", "T1", "--status", "merged", "--branch", "b", "--pr", "1", text="needs --merged-sha")
        self.refused("theme", "T1", "--status", "branch_open", "--branch", "b", "--merged-sha", SHA,
                     text="belongs to the merged status")  # fmt: skip
        self.ok("theme", "T1", "--status", "pr_open", "--branch", "b", "--pr", "1")
        self.refused("theme", "T1", "--status", "branch_open", text="only moves forward")
        self.refused("theme", "T1", "--status", "pr_open", text="only moves forward")
        self.refused("theme", "T1", "--status", "merged", "--merged-sha", "XYZ", text="--merged-sha must be")
        code, envelope, _ = self.run_cmd("theme", "T9", "--status", "merged")
        self.assertEqual(code, 1, envelope)


class WriteTests(TransitionCase):
    def test_render_is_only_done_on_request(self) -> None:
        self.md_path.unlink()
        code, envelope, _ = self.run_cmd("set-status", self.queued, "in_progress")
        self.assertEqual(code, 0)
        self.assertFalse(self.md_path.exists())
        self.assertTrue(any("out of date" in w for w in envelope["warnings"]))
        envelope = self.ok("set-status", self.queued, "failed", "--reason", "r", "--render")
        self.assertEqual(envelope["warnings"], [])
        self.assertEqual(self.md_path.read_text(encoding="utf-8"), progress.render(self.state()))
        self.assertIn("failed", self.md_path.read_text(encoding="utf-8"))
        self.assertEqual(self.md_path.name, MD_NAME)

    def test_the_state_stays_valid_and_log_only_grows(self) -> None:
        before = len(self.state()["log"])
        f = self.to_in_progress()
        self.ok("set-status", f, "blocked", "--reason", "r")
        state = self.state()
        self.assertEqual(progress.state_errors(state), [])
        self.assertEqual(len(state["log"]), before + 2)

    def test_a_killed_write_leaves_the_old_state_whole(self) -> None:
        before = self.json_path.read_bytes()
        with mock.patch("os.replace", side_effect=OSError("killed")):
            code, envelope, _ = self.run_cmd("set-status", self.queued, "in_progress")
        self.assertEqual(code, 3)
        self.assertIn("killed", envelope["data"]["error"])
        self.assertEqual(self.json_path.read_bytes(), before)
        self.assertEqual(self.temporaries(), [])

    def test_a_write_needs_a_state_and_a_phase(self) -> None:
        code, _, _ = call(["set-status", "F-001", "in_progress", "--target", str(self.target)])
        self.assertEqual(code, 1)
        self.json_path.unlink()
        code, envelope, _ = self.run_cmd("set-status", self.queued, "in_progress")
        self.assertEqual(code, 1, envelope)

    def test_a_bad_date_is_refused(self) -> None:
        code, envelope, _ = call(
            [
                "set-status",
                self.queued,
                "in_progress",
                "--target",
                str(self.target),
                "--phase",
                "p",
                "--date",
                "yesterday",
            ]
        )
        self.assertEqual(code, 1, envelope)

    def test_describe_lists_the_commands(self) -> None:
        synopsis = " ".join(progress.INFO.synopsis)
        for word in ("set-status", "skip", "unskip", "defer", "undefer", "pref set", "pref unset", "theme"):
            self.assertIn(word, synopsis)
        self.assertTrue(issubclass(_common.UsageError, _common.ToolError))

    def test_every_legal_move_is_in_the_diagram_table(self) -> None:
        self.assertEqual(set(progress.LEGAL), set(progress.ITEM_STATUSES))
        self.assertEqual(progress.LEGAL["done"], ())


if __name__ == "__main__":
    unittest.main()
