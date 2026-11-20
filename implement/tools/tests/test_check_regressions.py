# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`check_regressions.py` on a hand-made engine report and close reports made from it: a lost pass (to each other
verdict and to a missing check), a PARTIAL to FAIL regression, an improvement, other moves, an evidence-only change,
each refusal, a report of the wrong shape, the output budget and the envelope. Standard library only, in process.
"""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence
from unittest import mock

import _implement_paths  # noqa: F401  (puts the tools folders on sys.path)
import _common
import check_regressions

BASE = Path(__file__).resolve().parent / "fixtures" / "check-regressions-base.engine-report.json"
LATER = "2026-11-19T11:00:00+00:00"


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(check_regressions.INFO, check_regressions.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


def check_of(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(check for check in report["checks"] if check["id"] == check_id)
    return found


class CheckRegressionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name)
        self.base: dict[str, Any] = json.loads(BASE.read_text(encoding="utf-8"))

    def close_report(self) -> dict[str, Any]:
        """The base report taken an hour later at another commit: no check moved yet."""
        close: dict[str, Any] = copy.deepcopy(self.base)
        close["provenance"]["scanned_at"] = LATER
        close["provenance"]["git_sha"] = "2" * 40
        return close

    def write(self, name: str, document: Any) -> str:
        path = self.folder / name
        path.write_text(json.dumps(document), encoding="utf-8")
        return str(path)

    def run_pair(self, close: Any, base: Any = None) -> tuple[int, dict[str, Any], str]:
        return call([self.write("base.json", self.base if base is None else base), self.write("close.json", close)])

    def rows(self, envelope: dict[str, Any]) -> dict[str, dict[str, Any]]:
        data = envelope["data"]
        return {row["check"]: row for row in [*data["stops"], *data["moves"], *data["evidence_changes"]]}

    # --- clean --------------------------------------------------------------------------------------------

    def test_an_unchanged_pair_is_clean_and_lists_nothing(self) -> None:
        code, envelope, err = self.run_pair(self.close_report())
        self.assertEqual(code, 0)
        data = envelope["data"]
        self.assertEqual(data["status"], "clean")
        self.assertEqual((data["stops"], data["moves"], data["evidence_changes"]), ([], [], []))
        self.assertEqual(data["counts"]["unchanged"], 7)  # six checks and one not-applicable check
        self.assertEqual(sum(data["counts"].values()), 7)
        self.assertEqual(list(data["counts"]), list(check_regressions.CLASSES))
        self.assertEqual(data["base"]["report"], "base.json")
        self.assertEqual(data["close"]["git_sha"], "2" * 40)
        self.assertEqual(envelope["warnings"], [])
        self.assertFalse(envelope["truncated"])
        self.assertIn("check_regressions: clean", err)
        self.assertNotIn("stop the theme", err)

    def test_the_same_input_gives_the_same_bytes(self) -> None:
        close = self.close_report()
        check_of(close, "DOC-01")["summary"] = "docs/ holds 4 pages"
        first, second = io.StringIO(), io.StringIO()
        argv = [self.write("base.json", self.base), self.write("close.json", close)]
        for out in (first, second):
            check_regressions_code = _common.run_tool(
                check_regressions.INFO, check_regressions.handler, argv, stdout=out, stderr=io.StringIO()
            )
            self.assertEqual(check_regressions_code, 0)
        self.assertEqual(first.getvalue(), second.getvalue())

    # --- stops --------------------------------------------------------------------------------------------

    def test_a_pass_that_fails_at_close_is_a_lost_pass_and_stops(self) -> None:
        close = self.close_report()
        check = check_of(close, "IDX-01")
        check.update(verdict="FAIL", summary="no project-level MCP configuration found")
        close["findings"].append({"id": "IDX-01", "check": "IDX-01", "verdict": "FAIL", "severity": "BLOCKER"})
        code, envelope, err = self.run_pair(close)
        self.assertEqual(code, 0)
        data = envelope["data"]
        self.assertEqual(data["status"], "lost")
        self.assertEqual(
            data["stops"],
            [
                {
                    "check": "IDX-01",
                    "class": "lost_pass",
                    "base": "PASS",
                    "close": "FAIL",
                    "evidence": ["finding IDX-01 added", "summary"],
                }
            ],
        )
        self.assertEqual(data["counts"]["lost_pass"], 1)
        self.assertIn("stop the theme and ask the owner", err)

    def test_a_pass_that_becomes_anything_else_or_vanishes_is_a_lost_pass(self) -> None:
        for verdict in ("PARTIAL", "UNKNOWN", "ATTEST"):
            with self.subTest(verdict=verdict):
                close = self.close_report()
                check_of(close, "CMD-01")["verdict"] = verdict
                _, envelope, _ = self.run_pair(close)
                self.assertEqual(self.rows(envelope)["CMD-01"]["class"], "lost_pass")
                self.assertEqual(envelope["data"]["status"], "lost")
        with self.subTest(verdict="NOT_APPLICABLE"):
            close = self.close_report()
            close["checks"] = [check for check in close["checks"] if check["id"] != "CMD-01"]
            close["not_applicable"].append("CMD-01")
            _, envelope, _ = self.run_pair(close)
            row = self.rows(envelope)["CMD-01"]
            self.assertEqual((row["class"], row["close"]), ("lost_pass", "NOT_APPLICABLE"))
        with self.subTest(verdict="missing"):
            close = self.close_report()
            close["checks"] = [check for check in close["checks"] if check["id"] != "CMD-01"]
            _, envelope, _ = self.run_pair(close)
            row = self.rows(envelope)["CMD-01"]
            self.assertEqual((row["class"], row["close"], row["evidence"]), ("lost_pass", None, []))

    def test_partial_to_fail_is_a_regression_and_stops(self) -> None:
        close = self.close_report()
        check_of(close, "DOC-05")["verdict"] = "FAIL"
        code, envelope, _ = self.run_pair(close)
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["status"], "lost")
        row = self.rows(envelope)["DOC-05"]
        self.assertEqual((row["class"], row["base"], row["close"]), ("regressed", "PARTIAL", "FAIL"))
        self.assertEqual(envelope["data"]["counts"]["regressed"], 1)

    # --- reported, never a stop ---------------------------------------------------------------------------

    def test_an_improvement_is_reported_and_does_not_stop(self) -> None:
        close = self.close_report()
        check_of(close, "SEC-01")["verdict"] = "PASS"
        close["findings"] = [finding for finding in close["findings"] if finding["check"] != "SEC-01"]
        check_of(close, "DOC-05")["verdict"] = "PASS"
        _, envelope, _ = self.run_pair(close)
        self.assertEqual(envelope["data"]["status"], "clean")
        rows = self.rows(envelope)
        self.assertEqual(rows["SEC-01"]["class"], "improved")
        self.assertIn("finding SEC-01 removed", rows["SEC-01"]["evidence"])
        self.assertEqual(rows["DOC-05"]["class"], "improved")
        self.assertEqual([row["check"] for row in envelope["data"]["moves"]], ["DOC-05", "SEC-01"])

    def test_other_verdict_moves_are_changed_added_or_removed_and_do_not_stop(self) -> None:
        close = self.close_report()
        check_of(close, "TST-02")["verdict"] = "FAIL"  # UNKNOWN -> FAIL: no order
        check_of(close, "SEC-01")["verdict"] = "UNKNOWN"  # FAIL -> UNKNOWN
        close["checks"] = [check for check in close["checks"] if check["id"] != "DOC-05"]  # PARTIAL -> missing
        close["checks"].append({"id": "CI-01", "verdict": "FAIL", "summary": "no CI", "data": {}})  # new
        close["not_applicable"] = []  # HYG-13 goes missing
        _, envelope, err = self.run_pair(close)
        self.assertEqual(envelope["data"]["status"], "clean")
        classes = {check: row["class"] for check, row in self.rows(envelope).items()}
        self.assertEqual(
            classes,
            {"TST-02": "changed", "SEC-01": "changed", "DOC-05": "removed", "CI-01": "added", "HYG-13": "removed"},
        )
        self.assertIn("5 other verdict moves", err)

    def test_an_evidence_change_with_the_same_verdict_is_reported_not_a_stop(self) -> None:
        close = self.close_report()
        check_of(close, "DOC-01").update(summary="docs/ holds 4 pages", data={"pages": 4})
        check_of(close, "CMD-01")["data"] = {"verbs": ["build", "test"], "aliases": ["check"]}
        check_of(close, "DOC-05")["data"] = ["not", "an", "object"]
        for finding in close["findings"]:
            if finding["check"] == "SEC-01":
                finding["statement"] = "Still no secret scanner."
        _, envelope, _ = self.run_pair(close)
        data = envelope["data"]
        self.assertEqual(data["status"], "clean")
        self.assertEqual((data["stops"], data["moves"]), ([], []))
        evidence = {row["check"]: row["evidence"] for row in data["evidence_changes"]}
        self.assertEqual(
            evidence,
            {
                "CMD-01": ["data.aliases"],
                "DOC-01": ["data.pages", "summary"],
                "DOC-05": ["data"],
                "SEC-01": ["finding SEC-01 changed"],
            },
        )
        self.assertTrue(all(row["class"] == "evidence" for row in data["evidence_changes"]))
        self.assertEqual(data["counts"]["evidence"], 4)

    def test_a_finding_listed_without_an_id_is_keyed_by_its_check(self) -> None:
        base = copy.deepcopy(self.base)
        close = self.close_report()
        for report in (base, close):
            for finding in report["findings"]:
                del finding["id"]
        close["findings"] = [finding for finding in close["findings"] if finding["check"] != "DOC-05"]
        _, envelope, _ = self.run_pair(close, base)
        self.assertEqual(self.rows(envelope)["DOC-05"]["evidence"], ["finding DOC-05 removed"])

    # --- warnings -----------------------------------------------------------------------------------------

    def test_another_engine_version_and_a_dirty_close_tree_are_warnings(self) -> None:
        close = self.close_report()
        close["provenance"].update(version="0.4.2", git_dirty=True)
        code, envelope, _ = self.run_pair(close)
        self.assertEqual(code, 0)
        self.assertEqual(len(envelope["warnings"]), 2)
        self.assertIn("engine versions differ (base 0.4.1, close 0.4.2)", envelope["warnings"][0])
        self.assertIn("uncommitted changes", envelope["warnings"][1])

    # --- refusals -----------------------------------------------------------------------------------------

    def assert_refused(self, close: Any, *expected: str, base: Any = None) -> list[str]:
        code, envelope, err = self.run_pair(close, base)
        self.assertEqual(code, _common.EXIT_INVALID)
        self.assertFalse(envelope["ok"])
        self.assertTrue(envelope["data"]["error"].startswith("refused:"))
        errors: list[str] = envelope["data"]["errors"]
        self.assertEqual(len(errors), len(expected), errors)
        for line, text in zip(errors, expected):
            self.assertIn(text, line)
        self.assertIn("check_regressions: refused", err)
        return errors

    def test_each_differing_setting_is_one_refusal(self) -> None:
        cases = {
            "ruleset_hash": ("ruleset_hash", "ffffffffffffffff", 'base "aaaabbbbccccdddd", close "ffffffffffffffff"'),
            "target": ("target", "/work/other", 'base "/work/example-service-theme-t1", close "/work/other"'),
            "phase": ("phase", 2, "base 1, close 2"),
            "probes_enabled": ("probes_enabled", True, "base false, close true"),
        }
        for name, (key, value, detail) in cases.items():
            with self.subTest(setting=name):
                close = self.close_report()
                close["provenance"][key] = value
                expected = [f"{name} differs: {detail}"]
                if name == "probes_enabled":
                    expected.append('allowed probe verbs differs: base null, close ["test"]')
                self.assert_refused(close, *expected)
        with self.subTest(setting="user_config.read_allowed"):
            close = self.close_report()
            close["provenance"]["user_config"]["read_allowed"] = True
            self.assert_refused(close, "user_config.read_allowed differs: base false, close true")

    def test_another_allow_probe_list_is_refused(self) -> None:
        base = copy.deepcopy(self.base)
        base["provenance"]["probes_enabled"] = True
        base["probes"][0].update(exit_code=0, refused_reason=None)
        close = copy.deepcopy(base)
        close["provenance"]["scanned_at"] = LATER
        close["probes"][0].update(exit_code=None, refused_reason="verb 'test' not in --allow-probe list")
        self.assert_refused(close, 'allowed probe verbs differs: base ["test"], close []', base=base)

    def test_the_same_allow_probe_list_compares_even_when_a_probe_result_differs(self) -> None:
        base = copy.deepcopy(self.base)
        base["provenance"]["probes_enabled"] = True
        base["probes"][0].update(exit_code=0, refused_reason=None)
        close = copy.deepcopy(base)
        close["provenance"]["scanned_at"] = LATER
        close["probes"][0]["exit_code"] = 1
        code, envelope, _ = self.run_pair(close, base)
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["status"], "clean")

    def test_a_close_report_that_is_not_newer_is_refused(self) -> None:
        for scanned_at in ("2026-11-19T10:00:00+00:00", "2026-11-19T09:00:00+00:00", "2026-11-19T11:30:00+02:00"):
            with self.subTest(scanned_at=scanned_at):
                close = self.close_report()
                close["provenance"]["scanned_at"] = scanned_at
                self.assert_refused(close, "the close report is not newer than the base report")

    def test_every_refusal_is_listed_at_once(self) -> None:
        close = self.close_report()
        close["provenance"].update(ruleset_hash="0" * 16, target="/elsewhere", scanned_at="2026-11-18T10:00:00+00:00")
        errors = self.assert_refused(close, "ruleset_hash", "target", "not newer")
        self.assertEqual(len(errors), 3)

    # --- input errors -------------------------------------------------------------------------------------

    def test_a_missing_file_is_a_usage_error(self) -> None:
        code, envelope, _ = call([self.write("base.json", self.base), str(self.folder / "absent.json")])
        self.assertEqual(code, _common.EXIT_USAGE)
        self.assertIn("close engine report not found", envelope["data"]["error"])

    def test_a_missing_argument_is_a_usage_error(self) -> None:
        code, _, _ = call([self.write("base.json", self.base)])
        self.assertEqual(code, _common.EXIT_USAGE)

    def test_an_audit_report_or_a_broken_engine_report_fails_validation(self) -> None:
        code, envelope, _ = self.run_pair(["not", "an", "object"])
        self.assertEqual(code, _common.EXIT_INVALID)
        self.assertEqual(envelope["data"]["errors"], ["close: the top level must be an object"])
        broken = self.close_report()
        broken["schema_version"] = "1"
        broken["provenance"].update(ruleset_hash=None, scanned_at="yesterday", phase="1", probes_enabled="no")
        broken["provenance"]["user_config"] = {}
        broken["checks"] = [
            "CMD-01",
            {"id": "DOC-01"},
            {"id": "DOC-05", "verdict": "PASS"},
            {"id": "DOC-05", "verdict": "PASS"},
        ]
        broken["findings"] = [{"id": "x"}]
        broken["not_applicable"] = [1]
        broken["probes"] = [{}]
        code, envelope, _ = self.run_pair(broken)
        self.assertEqual(code, _common.EXIT_INVALID)
        self.assertEqual(envelope["data"]["error"], "the close file is not an engine report: 12 errors")
        self.assertEqual(
            envelope["data"]["errors"],
            [
                "close: /schema_version: expected '2', found '1'",
                "close: /provenance/ruleset_hash: must be a string",
                "close: /provenance/scanned_at: must be an ISO 8601 time with a UTC offset",
                "close: /provenance/phase: must be an integer",
                "close: /provenance/probes_enabled: must be a boolean",
                "close: /provenance/user_config/read_allowed: must be a boolean",
                "close: /checks/0: must be an object with a string id",
                "close: /checks/1/verdict: must be a string",
                "close: /checks/3: check DOC-05 is listed twice",
                "close: /findings/0: must be an object with a string check",
                "close: /not_applicable: must be a list of check ids",
                "close: /probes: must be a list of objects with a string verb",
            ],
        )

    def test_missing_sections_fail_validation(self) -> None:
        bare = {"schema_version": "2", "provenance": [], "checks": {}, "findings": {}}
        code, envelope, _ = self.run_pair(self.close_report(), base=bare)
        self.assertEqual(code, _common.EXIT_INVALID)
        self.assertEqual(
            envelope["data"]["errors"],
            [
                "base: /provenance: must be an object",
                "base: /checks: must be a list",
                "base: /findings: must be a list",
                "base: /not_applicable: must be a list of check ids",
                "base: /probes: must be a list of objects with a string verb",
            ],
        )

    def test_a_time_without_a_utc_offset_fails_validation(self) -> None:
        close = self.close_report()
        close["provenance"]["scanned_at"] = "2026-11-19T11:00:00"
        code, envelope, _ = self.run_pair(close)
        self.assertEqual(code, _common.EXIT_INVALID)
        self.assertEqual(
            envelope["data"]["errors"], ["close: /provenance/scanned_at: must be an ISO 8601 time with a UTC offset"]
        )

    # --- the contract -------------------------------------------------------------------------------------

    def test_describe_states_the_contract(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        manifest = envelope["data"]
        self.assertEqual(manifest["name"], "check_regressions")
        self.assertTrue(manifest["writes"].startswith("With --workspace only:"))
        self.assertFalse(manifest["network"])
        self.assertFalse(manifest["writes_inside_target"])
        self.assertEqual(
            manifest["synopsis"],
            [
                "check_regressions.py BASE CLOSE [--changed-from WORKTREE [--base SHA] [--base-target DIR]]"
                " [--workspace DIR --theme THEME [--label LABEL]]"
            ],
        )

    def test_long_lists_are_bounded_and_counted(self) -> None:
        close = self.close_report()
        for index in range(400):
            self.base["checks"].append({"id": f"X-{index:03d}", "verdict": "PASS", "summary": "a" * 40, "data": {}})
            close["checks"].append({"id": f"X-{index:03d}", "verdict": "FAIL", "summary": "b" * 40, "data": {}})
        code, envelope, _ = self.run_pair(close)
        self.assertEqual(code, 0)
        self.assertTrue(envelope["truncated"])
        data = envelope["data"]
        self.assertEqual(data["counts"]["lost_pass"], 400)
        self.assertEqual(len(data["stops"]) + data["omitted"]["stops"], 400)
        self.assertNotIn("moves", data["omitted"])

    def test_classify_covers_every_verdict_pair(self) -> None:
        verdicts = (None, "PASS", "PARTIAL", "FAIL", "UNKNOWN", "ATTEST", "NOT_APPLICABLE")
        for base in verdicts:
            for close in verdicts:
                kind = check_regressions.classify(base, close, ())
                self.assertIn(kind, check_regressions.CLASSES)
                stops = kind in check_regressions.STOPS
                self.assertEqual(stops, (base == "PASS" and close != "PASS") or (base, close) == ("PARTIAL", "FAIL"))

    def test_the_handler_reads_each_report_once(self) -> None:
        argv = [self.write("base.json", self.base), self.write("close.json", self.close_report())]
        with mock.patch.object(
            check_regressions, "read_engine_report", wraps=check_regressions.read_engine_report
        ) as read:
            check_regressions.handler(argv)
        self.assertEqual([entry.args[1] for entry in read.call_args_list], ["base", "close"])


if __name__ == "__main__":
    unittest.main()
