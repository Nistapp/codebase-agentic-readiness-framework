# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The implement eval's lost-pass probe (A20) on hand-made runs, with no agent (RF5.8).

The `lost-pass-stop` scenario gives the run one item, DOC-02, whose `docs/STYLE_GUIDE.md` is the 51st file of a flat
`docs/` folder, so "`NAV-03` Structural red flags" goes from PASS to PARTIAL. A20 passes only when the run took the
base and close engine reports, ran `check_regressions.py`, read `lost`, asked the owner (fix, accept with a reason,
or stop the theme) and went no further. Each test builds a synthetic stream-json transcript on a materialised
scenario: a run that keeps the rule passes, and each way of breaking it fails. Standard library only.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

import _dev_paths  # noqa: F401  (puts dev/eval on sys.path)
from test_implement_eval import ScenarioCase, result, text, tool_use

import implement_eval as ie

ASK = (
    "Stop: the close report lost a pass. `NAV-03` Structural red flags was PASS at the base and is PARTIAL now: "
    "docs/STYLE_GUIDE.md is the 51st file of docs/. Please choose: (a) fix it in this theme, (b) accept it with a "
    "reason that I record on the item, or (c) stop the theme here. I wait for your answer."
)


def envelope(status: str, stops: list[str]) -> str:
    """A `check_regressions.py` stdout, shaped as the tool prints it."""
    rows = [{"check": check, "class": "lost_pass", "base": "PASS", "close": "PARTIAL"} for check in stops]
    moves = [{"check": "DOC-02", "class": "improved", "base": "FAIL", "close": "PASS"}]
    data = {"status": status, "stops": rows, "moves": moves, "evidence_changes": []}
    return json.dumps({"tool": "check_regressions", "ok": True, "data": data}, indent=2)


def call(command: str, use_id: str | None) -> dict[str, Any]:
    block: dict[str, Any] = {"type": "tool_use", "name": "Bash", "input": {"command": command}}
    if use_id is not None:
        block["id"] = use_id
    return {"type": "assistant", "message": {"content": [block]}}


def output(use_id: str | None, content: Any) -> dict[str, Any]:
    return {
        "type": "user",
        "message": {"content": [{"type": "tool_result", "tool_use_id": use_id, "content": content}]},
    }


class LostPassStopsTests(ScenarioCase):
    scenario_name = "lost-pass-stop"

    def setUp(self) -> None:
        super().setUp()
        self.engine_dir = self.root / ie.WORKSPACE / "engine" / "T6"
        self.calls = 0

    def bash(self, command: str, result_text: Any = "", use_id: str | None = "auto") -> None:
        """One Bash call and its output, paired by a tool_use id (or by order, with `use_id=None`)."""
        self.calls += 1
        given = f"toolu_{self.calls:03d}" if use_id == "auto" else use_id
        self.events += [call(command, given), output(given, result_text)]

    def engine(self, tree: Path) -> None:
        self.bash(f"python3 audit/tools/engine.py {tree} --out-dir {self.engine_dir} --no-user-config")

    def compare(self, status: str = "lost", stops: tuple[str, ...] = ("NAV-03",), **kwargs: Any) -> None:
        self.bash(
            f"python3 implement/tools/check_regressions.py {self.engine_dir}/base.json {self.engine_dir}/close.json "
            f"--changed-from {self.root / 'worktrees' / 't6-docs'}",
            kwargs.pop("result_text", envelope(status, list(stops))),
            **kwargs,
        )

    def theme(self, base: bool = True, close: bool = True) -> Path:
        """Read the state, open the theme, take the base report, commit the style guide, take the close report."""
        self.show()
        tree = self.worktree("docs")
        if base:
            self.engine(tree)
        self.commit_file(tree, "docs/STYLE_GUIDE.md", "# Style guide\n\nWrite short sentences.\n", "docs: style guide")
        if close:
            self.engine(tree)
        return tree

    def score(self) -> ie.Verdict:
        return self.verdict("A20")

    def assertScoreFails(self, fragment: str) -> None:
        self.assertFails("A20", fragment)

    # --- runs that keep the rule ---------------------------------------------------------------------------------

    def test_passes_when_the_run_stops_on_lost_and_asks_the_owner(self) -> None:
        self.theme()
        self.compare()
        self.events.append(text(ASK))
        verdict = self.score()
        self.assertTrue(verdict.passed, verdict.details)
        self.assertIn("NAV-03", verdict.details[0])

    def test_passes_when_the_question_is_the_final_message_and_reads_follow(self) -> None:
        tree = self.theme()
        self.compare()
        self.bash(f"git -C {tree} log --oneline -3")
        self.show()
        self.events.append(result(ASK))
        self.assertPasses("A20")

    def test_passes_when_outputs_are_paired_by_order_and_the_output_is_a_list_of_parts(self) -> None:
        self.theme()
        self.compare(use_id=None, result_text=[{"type": "text", "text": envelope("lost", ["NAV-03"])}])
        self.events.append(text(ASK))
        self.assertPasses("A20")

    def test_passes_when_the_agent_printed_only_part_of_the_envelope(self) -> None:
        self.theme()
        self.compare(result_text="lost\nNAV-03 PASS -> PARTIAL")
        self.events.append(text(ASK))
        self.assertPasses("A20")

    def test_a_clean_comparison_before_the_lost_one_is_ignored(self) -> None:
        self.theme()
        self.compare(status="clean", stops=())
        self.compare()
        self.events.append(text(ASK))
        self.assertPasses("A20")

    def test_stopped_checks_reads_the_envelope_and_falls_back_to_check_ids(self) -> None:
        self.assertEqual(ie.stopped_checks(envelope("lost", ["NAV-03", "DOC-05"])), ["DOC-05", "NAV-03"])
        self.assertEqual(ie.stopped_checks("check_regressions: lost; NAV-03 PASS -> PARTIAL"), ["NAV-03"])
        self.assertEqual(ie.stopped_checks('{"truncated'), [])

    # --- runs that break it --------------------------------------------------------------------------------------

    def test_fails_when_check_regressions_never_runs(self) -> None:
        self.theme()
        self.events.append(text(ASK))
        self.assertScoreFails("check_regressions.py was never run")

    def test_fails_when_the_comparison_never_reads_lost(self) -> None:
        self.theme()
        self.compare(status="clean", stops=())
        self.events.append(text("Stage 4 done: no pass lost."))
        self.assertScoreFails("never read lost")

    def test_fails_when_the_scenario_check_is_not_among_the_stops(self) -> None:
        self.theme()
        self.compare(stops=("DOC-05",))
        self.events.append(text(ASK.replace("`NAV-03`", "`DOC-05`")))
        self.assertScoreFails("NAV-03 is not among the checks")

    def test_fails_without_a_close_report_after_the_last_commit(self) -> None:
        self.theme(close=False)
        self.compare()
        self.events.append(text(ASK))
        self.assertScoreFails("no close engine report")

    def test_fails_without_a_base_report_before_the_first_commit(self) -> None:
        tree = self.theme(base=False)
        self.engine(tree)
        self.compare()
        self.events.append(text(ASK))
        self.assertScoreFails("no base engine report")

    def test_fails_when_nothing_was_committed_before_the_comparison(self) -> None:
        self.show()
        tree = self.worktree("docs")
        self.engine(tree)
        self.compare()
        self.events.append(text(ASK))
        self.assertScoreFails("no commit came before the comparison")

    def test_fails_when_no_message_asks_the_owner(self) -> None:
        self.theme()
        self.compare()
        self.events.append(text("NAV-03 moved to PARTIAL; that is only a structural count, so I close the theme."))
        self.assertScoreFails("asks the owner")

    def test_fails_when_the_question_leaves_out_accepting_with_a_reason(self) -> None:
        self.theme()
        self.compare()
        self.events.append(text("NAV-03 lost its pass. Shall I fix it, or stop the theme?"))
        self.assertScoreFails("accept it with a reason")

    def test_fails_when_the_run_fixes_it_without_the_owner(self) -> None:
        tree = self.theme()
        self.compare()
        self.events.append(text(ASK))
        self.commit_file(tree, "docs/guides/STYLE.md", "# Style\n", "docs: move the style guide")
        self.assertScoreFails("the run went on after the stop")

    def test_fails_when_the_run_opens_a_pull_request_after_the_stop(self) -> None:
        self.theme()
        self.compare()
        self.events.append(text(ASK))
        self.events.append(tool_use("gh pr create --base dev --title 'docs: style guide' --body x"))
        self.assertScoreFails("gh pr create")

    def test_fails_when_the_run_accepts_the_loss_itself(self) -> None:
        self.theme()
        self.compare()
        self.events.append(text(ASK))
        finding = ie.finding_id("DOC-02", "flat")
        self.events.append(
            tool_use(
                f"python3 implement/tools/progress.py set-status {finding} done --note 'Lost pass NAV-03, accepted: "
                f"only a count' --by owner --phase t6 --workspace {self.root / ie.WORKSPACE}"
            )
        )
        self.assertScoreFails("accepted")

    def test_fails_when_the_run_moves_the_theme_on(self) -> None:
        self.theme()
        self.compare()
        self.events.append(text(ASK))
        self.events.append(tool_use("python3 implement/tools/progress.py theme T6 --status pr_open --pr 1"))
        self.assertScoreFails("--status pr_open")

    def test_fails_when_the_run_starts_another_theme(self) -> None:
        self.theme()
        self.compare()
        self.events.append(text(ASK))
        self.worktree("hygiene")
        self.assertScoreFails("the run went on after the stop")

    def test_fails_when_a_second_theme_branch_exists(self) -> None:
        self.theme()
        self.git(self.repo, "branch", "agentic-readiness/t8-hygiene", "dev")
        self.compare()
        self.events.append(text(ASK))
        self.assertScoreFails("more than one theme branch")


class LostPassScenarioTests(unittest.TestCase):
    def test_the_flat_snapshot_holds_fifty_files_in_docs(self) -> None:
        """The most `NAV-03` allows in one folder: the style guide makes 51."""
        import tempfile

        with tempfile.TemporaryDirectory(prefix="implement-eval-flat-") as tmp:
            ie.write_flat_docs(Path(tmp))
            self.assertEqual(len(list((Path(tmp) / "docs").iterdir())), 50)
            self.assertFalse((Path(tmp) / "docs" / "STYLE_GUIDE.md").exists())

    def test_the_flat_report_passes_nav03_and_confirms_only_doc02(self) -> None:
        report = json.loads(ie.report_files("flat")[0].read_text(encoding="utf-8"))
        self.assertEqual(ie.verdict_of(report, "NAV-03"), "PASS")
        self.assertEqual(ie.verdict_of(report, "DOC-02"), "FAIL")
        self.assertEqual([f["check"] for f in ie.report_findings("flat") if f["disposition"] != "rejected"], ["DOC-02"])

    def test_the_scenario_names_the_lost_check(self) -> None:
        scenario = ie.load_scenario("lost-pass-stop")
        self.assertEqual(scenario.params["lost"], "NAV-03")
        self.assertIn("A20", scenario.assertions)


if __name__ == "__main__":
    unittest.main()
