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
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

import _paths

TOOLS = _paths.TOOLS
sys.path.insert(0, str(TOOLS / "eval"))

import score  # noqa: E402

EXAMPLES = TOOLS.parent / "schema" / "examples"
WORKED = next(EXAMPLES.glob("example-service.audit-report.*.json"))
REPO_SHA = "deadbeef" * 5
REPO_LABEL = "example-service"


def git_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    return environment


def run_git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, env=git_environment())
    return done.stdout.strip()


def write_sized_files(root: Path, sizes: Mapping[str, int]) -> None:
    for path, lines in sizes.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text("".join(f"line{i}\n" for i in range(lines)) or "\n", encoding="utf-8")


def base_report() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(WORKED.read_text(encoding="utf-8"))
    assert document["provenance"]["target"]["git_sha"] == REPO_SHA
    assert document["provenance"]["target"]["label"] == REPO_LABEL
    return document


def check_of(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(c for c in report["checks"] if c["id"] == check_id)
    return found


def check_ids_of_pointers(report: dict[str, Any], pointers: list[str]) -> list[str]:
    """The check id each `/checks/<index>/evidence/<n>` pointer belongs to."""
    ids = []
    for pointer in pointers:
        index = int(pointer.split("/")[2])
        ids.append(report["checks"][index]["id"])
    return ids


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


class LinesFitTests(unittest.TestCase):
    def test_a_single_line_within_range_fits(self) -> None:
        self.assertTrue(score.lines_fit(10, "4"))

    def test_a_range_within_the_file_fits(self) -> None:
        self.assertTrue(score.lines_fit(10, "4-6"))

    def test_a_range_past_the_end_does_not_fit(self) -> None:
        self.assertFalse(score.lines_fit(10, "9-11"))

    def test_an_unknown_line_count_never_fits(self) -> None:
        self.assertFalse(score.lines_fit(None, "1"))

    def test_a_malformed_spec_does_not_fit(self) -> None:
        self.assertFalse(score.lines_fit(10, "not-a-range"))


class EvidenceValidityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name).resolve() / "target"
        self.target.mkdir()

    def commit(self, sizes: Mapping[str, int]) -> str:
        write_sized_files(self.target, sizes)
        run_git(self.target, "init", "-q")
        run_git(self.target, "add", "-A")
        run_git(self.target, "commit", "-q", "-m", "x")
        return run_git(self.target, "rev-parse", "HEAD")

    def report_at(self, sha: str) -> dict[str, Any]:
        report = base_report()
        report["provenance"]["target"]["git_sha"] = sha
        return report

    def test_no_file_evidence_gives_a_null_ratio_not_zero(self) -> None:
        result = score.evidence_validity({"checks": [], "findings": []}, self.target)
        self.assertIsNone(result["ratio"])
        self.assertEqual(result["total"], 0)

    def test_every_cited_path_and_line_present_gives_ratio_one(self) -> None:
        sha = self.commit(
            {
                "AGENTS.md": 40,
                "package.json": 1,
                "tsconfig.base.json": 4,
                "tsconfig.json": 4,
                "src/config/constants.ts": 12,
                "src/services/__tests__/auth.test.ts": 60,
            }
        )
        result = score.evidence_validity(self.report_at(sha), self.target)
        self.assertEqual(result["ratio"], 1.0)
        self.assertEqual(result["invalid"], [])

    def test_a_missing_path_is_invalid(self) -> None:
        sha = self.commit(
            {
                "AGENTS.md": 40,
                "package.json": 1,
                "tsconfig.base.json": 4,
                "tsconfig.json": 4,
                "src/services/__tests__/auth.test.ts": 60,
                # src/config/constants.ts deliberately missing.
            }
        )
        report = self.report_at(sha)
        result = score.evidence_validity(report, self.target)
        self.assertLess(result["ratio"], 1.0)
        self.assertIn("SEC-02", check_ids_of_pointers(report, result["invalid"]))

    def test_a_line_past_the_end_of_the_file_is_invalid(self) -> None:
        sha = self.commit(
            {
                "AGENTS.md": 10,  # AGT-11 cites lines 14-16 and 31-33; the file has only 10.
                "package.json": 1,
                "tsconfig.base.json": 4,
                "tsconfig.json": 4,
                "src/config/constants.ts": 12,
                "src/services/__tests__/auth.test.ts": 60,
            }
        )
        report = self.report_at(sha)
        result = score.evidence_validity(report, self.target)
        self.assertLess(result["ratio"], 1.0)
        self.assertIn("AGT-11", check_ids_of_pointers(report, result["invalid"]))

    def test_a_commit_the_target_does_not_hold_gives_a_null_ratio_with_a_warning(self) -> None:
        self.commit({"AGENTS.md": 40})
        result = score.evidence_validity(self.report_at("ab" * 20), self.target)
        self.assertIsNone(result["ratio"])
        self.assertIn("warning", result)

    def test_a_directory_cited_with_no_lines_is_a_valid_absence_proof(self) -> None:
        # CI-04's own spec asks the agent, on finding nothing, to cite the location it searched; the
        # repository root is a legitimate such citation (git's <tree>:"." lookup is the one that was
        # broken, not the citation itself — "." resolves fine via "./" or "").
        sha = self.commit(
            {
                "AGENTS.md": 40,
                "package.json": 1,
                "tsconfig.base.json": 4,
                "tsconfig.json": 4,
                "src/config/constants.ts": 12,
                "src/services/__tests__/auth.test.ts": 60,
            }
        )
        report = self.report_at(sha)
        check_of(report, "CI-04")["evidence"] = [{"kind": "file", "captured_by": "agent", "path": "."}]
        result = score.evidence_validity(report, self.target)
        self.assertEqual(result["ratio"], 1.0)
        self.assertNotIn("CI-04", check_ids_of_pointers(report, result["invalid"]))

    def test_a_directory_cited_with_lines_is_still_invalid(self) -> None:
        # A directory has no lines, so a citation that claims some is a genuinely bad one and must still
        # score as invalid - the fix for "." must not make the metric blind to this.
        sha = self.commit(
            {
                "AGENTS.md": 40,
                "package.json": 1,
                "tsconfig.base.json": 4,
                "tsconfig.json": 4,
                "src/config/constants.ts": 12,
                "src/services/__tests__/auth.test.ts": 60,
            }
        )
        report = self.report_at(sha)
        check_of(report, "CI-04")["evidence"] = [{"kind": "file", "captured_by": "agent", "path": ".", "lines": "1-3"}]
        result = score.evidence_validity(report, self.target)
        self.assertLess(result["ratio"], 1.0)
        self.assertIn("CI-04", check_ids_of_pointers(report, result["invalid"]))


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

    def test_without_a_target_evidence_validity_is_null_not_zero(self) -> None:
        report = base_report()
        data = score.score(report, expected(entry("CMD-02", "FAIL")))
        self.assertIsNone(data["metrics"]["evidence_validity"]["ratio"])

    def test_with_a_target_evidence_validity_is_computed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "target"
            target.mkdir()
            write_sized_files(
                target,
                {
                    "AGENTS.md": 40,
                    "package.json": 1,
                    "tsconfig.base.json": 4,
                    "tsconfig.json": 4,
                    "src/config/constants.ts": 12,
                    "src/services/__tests__/auth.test.ts": 60,
                },
            )
            run_git(target, "init", "-q")
            run_git(target, "add", "-A")
            run_git(target, "commit", "-q", "-m", "x")
            sha = run_git(target, "rev-parse", "HEAD")
            report = base_report()
            report["provenance"]["target"]["git_sha"] = sha
            data = score.score(report, expected(entry("CMD-02", "FAIL"), repo_sha=sha), target=target)
            self.assertEqual(data["metrics"]["evidence_validity"]["ratio"], 1.0)


# --- Mutation tests: a clean baseline, mutated one field at a time, every mutant moves at least one metric ------


def baseline_metrics() -> dict[str, Any]:
    report = base_report()
    exp = expected(
        entry("CMD-01", "FAIL"),
        entry("CMD-02", "FAIL"),
        entry("SEC-02", "FAIL"),
        entry("IDX-01", "PASS"),
        entry("TOOL-03", "PASS"),
    )
    metrics: dict[str, Any] = score.score(report, exp)["metrics"]
    return metrics


def mutated_metrics(mutate: Any) -> dict[str, Any] | None:
    report = base_report()
    exp = expected(
        entry("CMD-01", "FAIL"),
        entry("CMD-02", "FAIL"),
        entry("SEC-02", "FAIL"),
        entry("IDX-01", "PASS"),
        entry("TOOL-03", "PASS"),
    )
    report, exp = mutate(report, exp)
    data = score.score(report, exp)
    if not data["schema_valid"] or not data["comparable"]:
        return None  # The mutant moved schema_valid/comparable itself, which is its own detectable change.
    metrics: dict[str, Any] = data["metrics"]
    return metrics


class MutationTests(unittest.TestCase):
    """One mutation per test; each must move at least one metric away from the clean baseline."""

    def assert_survives_nothing(self, mutate: Any) -> None:
        before = baseline_metrics()
        after = mutated_metrics(mutate)
        self.assertNotEqual(after, before, "a mutant that leaves every metric unchanged is a survivor")

    def test_flipping_an_expected_blocker_to_pass(self) -> None:
        def mutate(report: dict[str, Any], exp: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            check_of(report, "CMD-02")["verdict"] = "PASS"
            return report, exp

        self.assert_survives_nothing(mutate)

    def test_dropping_a_false_positive_candidate_check(self) -> None:
        def mutate(report: dict[str, Any], exp: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            check_of(report, "IDX-01")["verdict"] = "FAIL"
            return report, exp

        self.assert_survives_nothing(mutate)

    def test_dropping_the_override_reason(self) -> None:
        def mutate(report: dict[str, Any], exp: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            check_of(report, "TOOL-03").pop("override_reason")
            return report, exp

        self.assert_survives_nothing(mutate)

    def test_changing_the_catalogue_severity_of_an_expected_blocker(self) -> None:
        def mutate(report: dict[str, Any], exp: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            check_of(report, "SEC-02")["severity"] = "DEGRADER"
            return report, exp

        self.assert_survives_nothing(mutate)

    def test_changing_the_report_sha(self) -> None:
        def mutate(report: dict[str, Any], exp: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            report["provenance"]["target"]["git_sha"] = "ab" * 20
            return report, exp

        self.assert_survives_nothing(mutate)

    def test_changing_the_report_label(self) -> None:
        def mutate(report: dict[str, Any], exp: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            report["provenance"]["target"]["label"] = "other-service"
            return report, exp

        self.assert_survives_nothing(mutate)


if __name__ == "__main__":
    unittest.main()
