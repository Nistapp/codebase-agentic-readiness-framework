# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""A lost pass stops the theme (ADR 0005), as a refusal: ``check_regressions.py --workspace`` writes the theme's
verdict beside the state, and ``progress.py`` refuses ``set-status <item> done`` and ``theme --status merged`` while it
reads ``lost`` and the owner has not accepted it with ``accept-lost``. A clean verdict and no verdict pass. Standard
library only, in process.
"""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path
from typing import Any, Sequence

import _implement_paths  # noqa: F401  (puts the tools folders on sys.path)
import _common
import check_regressions
import progress
from test_progress_transitions import SHA, TransitionCase

BASE = Path(__file__).resolve().parent / "fixtures" / "check-regressions-base.engine-report.json"
LATER = "2026-11-19T11:00:00+00:00"
LATER_STILL = "2026-11-19T12:00:00+00:00"


def compare(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(check_regressions.INFO, check_regressions.handler, list(argv), stdout=out, stderr=err)
    envelope: dict[str, Any] = json.loads(out.getvalue())
    return code, envelope, err.getvalue()


class LostPassRefusalTests(TransitionCase):
    def setUp(self) -> None:
        super().setUp()
        self.finding = self.to_in_progress()
        self.theme: str = self.item(self.finding)["theme"]
        self.label: str = self.state()["repo"]["label"]
        self.verdict_path = self.state_dir / progress.verdict_name(self.label, self.theme)

    def reports(self, *, lose: bool, scanned_at: str = LATER, target: str | None = None) -> tuple[str, str]:
        """A base engine report and a close report taken later: IDX-01 goes from PASS to FAIL when `lose`."""
        base: dict[str, Any] = json.loads(BASE.read_text(encoding="utf-8"))
        if target is not None:
            base["provenance"]["target"] = target
        close = copy.deepcopy(base)
        close["provenance"].update(scanned_at=scanned_at, git_sha="2" * 40)
        if lose:
            next(check for check in close["checks"] if check["id"] == "IDX-01")["verdict"] = "FAIL"
        paths = []
        for name, document in (("base", base), ("close-" + scanned_at[11:19].replace(":", ""), close)):
            path = self.tmp / f"{name}.engine.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            paths.append(str(path))
        return paths[0], paths[1]

    def record_verdict(self, *, lose: bool, scanned_at: str = LATER, theme: str | None = None) -> None:
        base, close = self.reports(lose=lose, scanned_at=scanned_at)
        argv = [base, close, "--workspace", str(self.state_dir), "--theme", theme or self.theme]
        code, envelope, err = compare(argv)
        self.assertEqual(code, 0, (envelope, err))
        self.assertTrue(envelope["data"]["verdict"].endswith(progress.verdict_name(self.label, theme or self.theme)))

    def done(self) -> tuple[str, ...]:
        return ("set-status", self.finding, "done", "--verification-command", "make check",
                "--verification-result", "exit 0")  # fmt: skip

    def merged(self) -> tuple[str, ...]:
        return ("theme", self.theme, "--status", "merged", "--branch", "b", "--pr", "1", "--merged-sha", SHA)

    # --- the verdict file ---------------------------------------------------------------------------------

    def test_the_verdict_is_written_beside_the_state_with_every_stop(self) -> None:
        self.record_verdict(lose=True)
        verdict = json.loads(self.verdict_path.read_text(encoding="utf-8"))
        self.assertEqual(
            (verdict["tool"], verdict["theme"], verdict["status"]), ("check_regressions", self.theme, "lost")
        )
        self.assertEqual([row["check"] for row in verdict["stops"]], ["IDX-01"])
        self.assertEqual(verdict["close"]["scanned_at"], LATER)
        self.assertEqual(self.temporaries(), [])

    def test_the_verdict_options_are_checked(self) -> None:
        base, close = self.reports(lose=True)
        for argv, text in (
            ([base, close, "--theme", self.theme], "--workspace and --theme go together"),
            ([base, close, "--workspace", str(self.state_dir)], "--workspace and --theme go together"),
            ([base, close, "--label", "x"], "--label needs --workspace"),
            ([base, close, "--workspace", str(self.tmp / "nowhere"), "--theme", "T1"], "workspace not found"),
            ([base, close, "--workspace", str(self.target), "--theme", "T1"], "no state in"),
        ):
            code, envelope, _ = compare(argv)
            self.assertEqual(code, 1, envelope)
            self.assertIn(text, envelope["data"]["error"])
        self.assertFalse(self.verdict_path.exists())

    def test_a_verdict_is_never_written_inside_the_target(self) -> None:
        base, close = self.reports(lose=True, target=str(self.tmp))
        code, envelope, _ = compare([base, close, "--workspace", str(self.state_dir), "--theme", self.theme])
        self.assertNotEqual(code, 0, envelope)
        self.assertIn("inside the target", envelope["data"]["error"])
        self.assertFalse(self.verdict_path.exists())

    # --- the refusal ----------------------------------------------------------------------------------------

    def test_a_lost_verdict_refuses_done_and_merged(self) -> None:
        self.record_verdict(lose=True)
        self.refused(*self.done(), text=rf"to done is refused: theme {self.theme} lost a pass \(IDX-01\)")
        self.refused(*self.merged(), text=rf"theme {self.theme} to merged is refused")
        code, envelope, err = self.run_cmd(*self.done())
        self.assertEqual(code, 1)
        self.assertIn("lost a pass", err)
        self.assertIn(f"accept-lost {self.theme} --reason TEXT --by owner", err)

    def test_an_accepted_lost_verdict_passes_and_a_new_one_needs_a_new_acceptance(self) -> None:
        self.record_verdict(lose=True)
        self.refused("accept-lost", self.theme, "--reason", "the owner moves the MCP config", text="owner decision")
        self.ok("accept-lost", self.theme, "--reason", "the owner moves the MCP config", by="owner")
        event = self.state()["log"][-1]["event"]
        self.assertRegex(event, rf"^theme {self.theme} lost verdict [0-9a-f]{{12}} accepted by owner \(IDX-01\): ")
        self.refused("accept-lost", self.theme, "--reason", "again", by="owner", text="already accepted")
        self.ok("theme", self.theme, "--status", "pr_open", "--branch", "b", "--pr", "1")
        self.record_verdict(lose=True, scanned_at=LATER_STILL)
        self.refused(*self.done(), text="to done is refused")
        self.ok("accept-lost", self.theme, "--reason", "still accepted", by="owner")
        self.ok(*self.done())
        self.ok("theme", self.theme, "--status", "merged", "--merged-sha", SHA)

    def test_a_clean_verdict_passes(self) -> None:
        self.record_verdict(lose=True)
        self.record_verdict(lose=False, scanned_at=LATER_STILL)
        self.assertEqual(json.loads(self.verdict_path.read_text(encoding="utf-8"))["status"], "clean")
        self.refused("accept-lost", self.theme, "--reason", "x", by="owner", text="no lost pass to accept")
        self.ok(*self.done())
        self.ok(*self.merged())

    def test_no_verdict_passes(self) -> None:
        self.refused("accept-lost", self.theme, "--reason", "x", by="owner", text="has no verdict to accept")
        self.ok(*self.done())
        self.ok(*self.merged())

    def test_a_lost_verdict_of_another_theme_does_not_refuse(self) -> None:
        self.record_verdict(lose=True, theme=next(theme for theme in progress.THEME_IDS if theme != self.theme))
        self.ok(*self.done())

    def test_other_moves_are_not_refused_by_a_lost_verdict(self) -> None:
        self.record_verdict(lose=True)
        self.ok("set-status", self.finding, "blocked", "--reason", "waits for the owner")
        self.ok("theme", self.theme, "--status", "branch_open", "--branch", "b")

    def test_a_verdict_edited_by_hand_is_refused(self) -> None:
        self.record_verdict(lose=True)
        for text in ("not json", json.dumps({"theme": self.theme, "status": "fine", "stops": []})):
            self.verdict_path.write_text(text, encoding="utf-8")
            self.refused(*self.done(), text="is not a check_regressions.py verdict", code=2)

    def test_a_bad_theme_name_is_refused(self) -> None:
        with self.assertRaises(_common.UsageError):
            progress.verdict_name(self.label, "T9")
