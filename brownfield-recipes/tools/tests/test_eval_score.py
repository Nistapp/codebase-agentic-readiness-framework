# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The eval scorer: schema validity and blocker recall (S4.1.2.1).

Reports are built by changing the worked example (as `test_validate_report.py` does), so a test that mutates
one check's verdict starts from a report that is otherwise known-good. Expected-results files are built by
hand in this file, not read from `schema/examples/eval-expected.example-service.json`: that shipped example's
`repo_sha` does not match the worked report's own `git_sha` (found, not fixed — S4.1.1 wrote it before a
scorer existed to catch the mismatch), so a test here pins its own matching `repo_sha` instead of inheriting
that drift. Standard library only.
"""

from __future__ import annotations

import json
import sys
import unittest
from typing import Any

import _paths

TOOLS = _paths.TOOLS
sys.path.insert(0, str(TOOLS / "eval"))

import score  # noqa: E402

EXAMPLES = TOOLS.parent / "schema" / "examples"
WORKED = next(EXAMPLES.glob("example-service.audit-report.*.json"))
REPO_SHA = "deadbeef" * 5
REPO_LABEL = "example-service"


def base_report() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(WORKED.read_text(encoding="utf-8"))
    assert document["provenance"]["target"]["git_sha"] == REPO_SHA
    assert document["provenance"]["target"]["label"] == REPO_LABEL
    return document


def check_of(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(c for c in report["checks"] if c["id"] == check_id)
    return found


def expected(*checks: dict[str, Any], repo_sha: str = REPO_SHA, repo_label: str = REPO_LABEL) -> dict[str, Any]:
    return {
        "expected_version": "0.1",
        "repo_label": repo_label,
        "repo_sha": repo_sha,
        "checks": list(checks),
    }


def entry(check_id: str, *acceptable: str) -> dict[str, Any]:
    return {"id": check_id, "acceptable_verdicts": list(acceptable)}


class MatchTargetTests(unittest.TestCase):
    def test_matching_sha_and_label_is_comparable(self) -> None:
        match = score.match_target(base_report(), expected(entry("CMD-02", "FAIL")))
        self.assertTrue(match.comparable)

    def test_sha_mismatch_is_not_comparable(self) -> None:
        match = score.match_target(base_report(), expected(entry("CMD-02", "FAIL"), repo_sha="ab" * 20))
        self.assertFalse(match.comparable)
        self.assertIn("commit", match.reason)

    def test_label_mismatch_is_not_comparable(self) -> None:
        match = score.match_target(base_report(), expected(entry("CMD-02", "FAIL"), repo_label="other-service"))
        self.assertFalse(match.comparable)
        self.assertIn("repo_label", match.reason)


class ExpectedBlockersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.severities = score.catalogue_severities()

    def test_a_blocker_check_with_no_acceptable_pass_is_a_ground_truth_blocker(self) -> None:
        wanted = score.expected_blockers(expected(entry("CMD-02", "FAIL")), self.severities)
        self.assertEqual(wanted, ["CMD-02"])

    def test_a_blocker_check_with_pass_acceptable_is_not_a_ground_truth_blocker(self) -> None:
        wanted = score.expected_blockers(expected(entry("IDX-01", "PASS", "PARTIAL")), self.severities)
        self.assertEqual(wanted, [])

    def test_a_degrader_check_is_never_a_ground_truth_blocker(self) -> None:
        wanted = score.expected_blockers(expected(entry("AGT-07", "FAIL")), self.severities)
        self.assertEqual(wanted, [])


class BlockerRecallTests(unittest.TestCase):
    def test_every_expected_blocker_recalled_gives_ratio_one(self) -> None:
        report = base_report()
        exp = expected(entry("CMD-01", "FAIL"), entry("CMD-02", "FAIL"), entry("SEC-02", "FAIL"))
        result = score.blocker_recall(report, exp, score.catalogue_severities())
        self.assertEqual(result["ratio"], 1.0)
        self.assertEqual(result["expected_total"], 3)
        self.assertEqual(sorted(result["matched"]), ["CMD-01", "CMD-02", "SEC-02"])
        self.assertEqual(result["missed"], [])

    def test_a_blocker_the_report_turned_to_pass_is_missed(self) -> None:
        report = base_report()
        check_of(report, "CMD-02")["verdict"] = "PASS"
        exp = expected(entry("CMD-01", "FAIL"), entry("CMD-02", "FAIL"))
        result = score.blocker_recall(report, exp, score.catalogue_severities())
        self.assertEqual(result["ratio"], 0.5)
        self.assertEqual(result["matched"], ["CMD-01"])
        self.assertEqual(result["missed"], ["CMD-02"])

    def test_a_partial_verdict_still_counts_as_an_open_blocker(self) -> None:
        report = base_report()
        check_of(report, "CMD-02")["verdict"] = "PARTIAL"
        exp = expected(entry("CMD-02", "FAIL"))
        result = score.blocker_recall(report, exp, score.catalogue_severities())
        self.assertEqual(result["ratio"], 1.0)

    def test_no_expected_blockers_gives_a_null_ratio_not_zero(self) -> None:
        report = base_report()
        exp = expected(entry("IDX-01", "PASS"))
        result = score.blocker_recall(report, exp, score.catalogue_severities())
        self.assertIsNone(result["ratio"])
        self.assertEqual(result["expected_total"], 0)


class FalsePositiveCandidatesTests(unittest.TestCase):
    def test_an_expected_pass_check_the_report_fails_is_a_candidate(self) -> None:
        report = base_report()
        exp = expected(entry("IDX-01", "PASS"))
        result = score.false_positive_candidates(report, exp)
        self.assertEqual(result["ids"], [])
        self.assertEqual(result["rate"], 0.0)

    def test_an_expected_pass_check_the_report_also_passes_is_not_a_candidate(self) -> None:
        report = base_report()
        check_of(report, "IDX-01")["verdict"] = "FAIL"
        exp = expected(entry("IDX-01", "PASS"))
        result = score.false_positive_candidates(report, exp)
        self.assertEqual(result["ids"], ["IDX-01"])
        self.assertEqual(result["rate"], 1.0)

    def test_a_check_with_more_than_one_acceptable_verdict_is_never_a_candidate(self) -> None:
        report = base_report()
        exp = expected(entry("AGT-08", "PASS", "PARTIAL"))
        result = score.false_positive_candidates(report, exp)
        self.assertEqual(result["expected_total"], 0)
        self.assertIsNone(result["rate"])

    def test_no_expected_pass_only_checks_gives_a_null_rate(self) -> None:
        report = base_report()
        exp = expected(entry("CMD-02", "FAIL"))
        result = score.false_positive_candidates(report, exp)
        self.assertIsNone(result["rate"])
        self.assertEqual(result["expected_total"], 0)


class OverridePrecisionTests(unittest.TestCase):
    def test_an_override_landing_on_an_acceptable_verdict_is_correct(self) -> None:
        report = base_report()  # TOOL-03 already carries an override_reason in the worked example.
        exp = expected(entry("TOOL-03", "PASS"))
        result = score.override_precision(report, exp)
        self.assertEqual(result["ratio"], 1.0)
        self.assertEqual(result["correct"], ["TOOL-03"])
        self.assertEqual(result["incorrect"], [])

    def test_an_override_landing_on_an_unacceptable_verdict_is_incorrect(self) -> None:
        report = base_report()
        exp = expected(entry("TOOL-03", "FAIL"))
        result = score.override_precision(report, exp)
        self.assertEqual(result["ratio"], 0.0)
        self.assertEqual(result["incorrect"], ["TOOL-03"])

    def test_an_override_the_expected_file_is_silent_on_is_not_judged(self) -> None:
        report = base_report()
        exp = expected(entry("CMD-02", "FAIL"))
        result = score.override_precision(report, exp)
        self.assertIsNone(result["ratio"])
        self.assertEqual(result["overridden_total"], 0)

    def test_no_overrides_at_all_gives_a_null_ratio(self) -> None:
        report = base_report()
        check_of(report, "TOOL-03").pop("override_reason")
        exp = expected(entry("TOOL-03", "PASS"))
        result = score.override_precision(report, exp)
        self.assertIsNone(result["ratio"])


class ScoreTests(unittest.TestCase):
    def test_a_schema_invalid_report_is_not_comparable(self) -> None:
        report = base_report()
        del report["schema_version"]
        data = score.score(report, expected(entry("CMD-02", "FAIL")))
        self.assertFalse(data["schema_valid"])
        self.assertFalse(data["comparable"])
        self.assertIn("schema_errors", data)
        self.assertNotIn("metrics", data)

    def test_a_sha_mismatch_is_not_comparable_and_has_no_metrics(self) -> None:
        report = base_report()
        data = score.score(report, expected(entry("CMD-02", "FAIL"), repo_sha="ab" * 20))
        self.assertTrue(data["schema_valid"])
        self.assertFalse(data["comparable"])
        self.assertNotIn("metrics", data)

    def test_a_comparable_report_scores_blocker_recall(self) -> None:
        report = base_report()
        data = score.score(report, expected(entry("CMD-02", "FAIL")))
        self.assertTrue(data["comparable"])
        self.assertEqual(data["metrics"]["blocker_recall"]["ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
