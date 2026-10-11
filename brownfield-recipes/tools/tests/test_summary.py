# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The readiness summary: the definition in spec/readiness-summary.md, one case at a time, and the examples, where
the score must equal the engine's own. Standard library only.
"""

from __future__ import annotations

import copy
import json
import unittest
from typing import Any

import _paths
import _summary

EXAMPLES = _paths.TOOLS.parent / "schema" / "examples"


def check(
    check_id: str = "AGT-01",
    severity: str = "BLOCKER",
    verdict: str = "PASS",
    *,
    scored: bool = True,
    phase: int = 1,
    method: str = "automated",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "severity": severity,
        "verdict": verdict,
        "scored": scored,
        "phase": phase,
        "method": method,
    }


def finding(check_id: str, disposition: str = "pending") -> dict[str, Any]:
    return {"check": check_id, "disposition": disposition}


def summary_of(checks: list[dict[str, Any]], findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return _summary.compute_summary({"checks": checks, "findings": findings or []})


class ScoreTests(unittest.TestCase):
    def test_the_example_in_the_spec_gives_0_6667(self) -> None:
        result = summary_of(
            [
                check("A-01", "BLOCKER", "PASS"),
                check("A-02", "DEGRADER", "PARTIAL"),
                check("A-03", "COSMETIC", "UNKNOWN"),
            ]
        )
        self.assertEqual(result["phase1_score"], 0.6667)
        self.assertEqual(result["scored_checks"], 3)

    def test_each_verdict_earns_its_credit_at_each_weight(self) -> None:
        credit = {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0, "UNKNOWN": 0.0}
        for severity in ("BLOCKER", "DEGRADER", "COSMETIC"):
            for verdict, expected in credit.items():
                with self.subTest(severity=severity, verdict=verdict):
                    self.assertEqual(summary_of([check("A-01", severity, verdict)])["phase1_score"], expected)

    def test_the_weights_are_3_2_and_1(self) -> None:
        passes_blocker = summary_of([check("A-01", "BLOCKER", "PASS"), check("A-02", "COSMETIC", "FAIL")])
        self.assertEqual(passes_blocker["phase1_score"], 0.75)
        passes_cosmetic = summary_of([check("A-01", "BLOCKER", "FAIL"), check("A-02", "COSMETIC", "PASS")])
        self.assertEqual(passes_cosmetic["phase1_score"], 0.25)
        degrader = summary_of([check("A-01", "DEGRADER", "PASS"), check("A-02", "COSMETIC", "FAIL")])
        self.assertEqual(round(degrader["phase1_score"], 4), 0.6667)

    def test_unknown_stays_in_the_denominator_at_zero_credit(self) -> None:
        self.assertEqual(
            summary_of([check("A-01", "BLOCKER", "PASS"), check("A-02", "BLOCKER", "UNKNOWN")])["phase1_score"], 0.5
        )

    def test_a_check_that_does_not_apply_is_left_out_of_both_sides(self) -> None:
        result = summary_of([check("A-01", "BLOCKER", "PASS"), check("A-02", "BLOCKER", "NOT_APPLICABLE")])
        self.assertEqual((result["phase1_score"], result["scored_checks"]), (1.0, 1))

    def test_an_unscored_check_and_a_check_of_another_phase_are_left_out(self) -> None:
        result = summary_of(
            [
                check("A-01", "BLOCKER", "PASS"),
                check("A-02", "BLOCKER", "FAIL", scored=False),
                check("A-03", "BLOCKER", "FAIL", phase=2),
            ]
        )
        self.assertEqual((result["phase1_score"], result["scored_checks"]), (1.0, 1))
        self.assertEqual(result["blockers_remaining"], {"total": 0, "fail": 0, "partial": 0, "unknown": 0})

    def test_with_nothing_to_score_the_score_is_zero(self) -> None:
        for checks in ([], [check("A-01", scored=False)], [check("A-01", verdict="NOT_APPLICABLE")]):
            with self.subTest(checks=len(checks)):
                result = summary_of(checks)
                self.assertEqual((result["phase1_score"], result["scored_checks"]), (0.0, 0))

    def test_the_score_is_rounded_to_four_places(self) -> None:
        two_thirds = summary_of(
            [check("A-01", "DEGRADER", "PASS"), check("A-02", "DEGRADER", "PASS"), check("A-03", "DEGRADER", "FAIL")]
        )
        self.assertEqual(two_thirds["phase1_score"], 0.6667)
        one_third = summary_of(
            [check("A-01", "DEGRADER", "PASS"), check("A-02", "DEGRADER", "FAIL"), check("A-03", "DEGRADER", "FAIL")]
        )
        self.assertEqual(one_third["phase1_score"], 0.3333)


class BlockerAndQualifierTests(unittest.TestCase):
    def test_blockers_remaining_counts_checks_by_state(self) -> None:
        result = summary_of(
            [
                check("A-01", "BLOCKER", "PASS"),
                check("A-02", "BLOCKER", "FAIL"),
                check("A-03", "BLOCKER", "FAIL"),
                check("A-04", "BLOCKER", "PARTIAL"),
                check("A-05", "BLOCKER", "UNKNOWN"),
                check("A-06", "DEGRADER", "FAIL"),
                check("A-07", "BLOCKER", "NOT_APPLICABLE"),
                check("A-08", "BLOCKER", "FAIL", scored=False),
            ]
        )
        self.assertEqual(result["blockers_remaining"], {"total": 4, "fail": 2, "partial": 1, "unknown": 1})

    def test_open_blockers_are_the_scored_blocker_checks_that_are_not_met_in_report_order(self) -> None:
        checks = [
            check("A-01", "BLOCKER", "UNKNOWN"),
            check("A-02", "BLOCKER", "PASS"),
            check("A-03", "DEGRADER", "FAIL"),
            check("A-04", "BLOCKER", "FAIL", scored=False),
            check("A-05", "BLOCKER", "FAIL", phase=2),
            check("A-06", "BLOCKER", "NOT_APPLICABLE"),
            check("A-07", "BLOCKER", "PARTIAL"),
            check("A-08", "BLOCKER", "FAIL"),
        ]
        self.assertEqual([c["id"] for c in _summary.open_blockers(checks)], ["A-01", "A-07", "A-08"])
        self.assertEqual(_summary.open_blockers([]), [])

    def test_unknown_scored_checks_counts_every_severity(self) -> None:
        result = summary_of(
            [
                check("A-01", "BLOCKER", "UNKNOWN"),
                check("A-02", "COSMETIC", "UNKNOWN"),
                check("A-03", "COSMETIC", "UNKNOWN", scored=False),
            ]
        )
        self.assertEqual(result["unknown_scored_checks"], 2)

    def test_unconfirmed_agent_findings_are_pending_findings_of_agent_checks(self) -> None:
        checks = [check("A-01", method="agent"), check("A-02", method="agent"), check("A-03", method="automated")]
        findings = [
            finding("A-01", "pending"),
            finding("A-01", "pending"),
            finding("A-02", "confirmed"),
            finding("A-02", "deferred"),
            finding("A-03", "pending"),
        ]
        self.assertEqual(summary_of(checks, findings)["unconfirmed_agent_findings"], 2)

    def test_a_finding_on_a_check_the_report_lacks_does_not_stop_the_summary(self) -> None:
        self.assertEqual(summary_of([check("A-01")], [finding("Z-99")])["unconfirmed_agent_findings"], 0)

    def test_the_keys_come_in_the_order_of_the_schema_and_the_input_is_not_changed(self) -> None:
        report = {"checks": [check("A-01", method="agent")], "findings": [finding("A-01")]}
        before = copy.deepcopy(report)
        result = _summary.compute_summary(report)
        self.assertEqual(
            list(result),
            [
                "phase1_score",
                "scored_checks",
                "blockers_remaining",
                "unknown_scored_checks",
                "unconfirmed_agent_findings",
            ],
        )
        self.assertEqual(list(result["blockers_remaining"]), ["total", "fail", "partial", "unknown"])
        self.assertEqual(report, before)


class ExamplesTests(unittest.TestCase):
    def test_every_example_carries_the_summary_its_checks_give(self) -> None:
        examples = [
            EXAMPLES / "minimal.json",
            *sorted(EXAMPLES.glob("example-service.audit-report.*.json")),
            *sorted(EXAMPLES.rglob("*.audit-draft.*.json")),
        ]
        self.assertGreaterEqual(len(examples), 5)
        for path in examples:
            with self.subTest(example=path.name):
                report = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(_summary.compute_summary(report), report["summary"])

    def test_the_score_and_the_scored_count_equal_the_engines_own(self) -> None:
        pairs = 0
        for raw_path in sorted(EXAMPLES.rglob("*.engine-report.*.json")):
            stamp = raw_path.name.split(".engine-report.")[1]
            label = raw_path.name.split(".engine-report.")[0]
            drafts = list(raw_path.parent.glob(f"{label}.audit-draft.*.json"))
            self.assertEqual(len(drafts), 1, raw_path.name)
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            draft = json.loads(drafts[0].read_text(encoding="utf-8"))
            # A check the engine's ruleset blocked did not run: the draft scores it as the catalogue does, the engine's
            # own number does not, so the engine's number is what the draft's is with that check left unscored.
            blocked = {check["id"] for check in raw["checks"] if check["status"] == "blocked"}
            for check in draft["checks"]:
                if check["id"] in blocked:
                    check["scored"] = False
            ours = _summary.compute_summary(draft)
            with self.subTest(report=raw_path.name, stamp=stamp):
                self.assertEqual(ours["phase1_score"], raw["summary"]["phase1_score"])
                self.assertEqual(ours["scored_checks"], raw["summary"]["checks_scoreable"])
            pairs += 1
        self.assertGreaterEqual(pairs, 3)


if __name__ == "__main__":
    unittest.main()
