# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`compare_reports.py` on the example report and the example in-progress state: identical reports, closed, new and
moved findings, check moves, state labels, a state that belongs to another report, and an invalid report.
Standard library only.
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

import _paths  # noqa: F401  (puts the tools folder on sys.path)
import _common
import compare_reports
import validate_report

EXAMPLES = _paths.TOOLS.parent / "schema" / "examples"
REPORT = EXAMPLES / "example-service.audit-report.20261010T094207Z.json"
STATE = EXAMPLES / "readiness-state.example-service.in-progress.json"


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(compare_reports.INFO, compare_reports.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


class CompareReportsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.before = json.loads(REPORT.read_text(encoding="utf-8"))

    def write(self, name: str, document: Any) -> str:
        path = self.base / name
        path.write_text(json.dumps(document), encoding="utf-8")
        return str(path)

    def after_report(self) -> dict[str, Any]:
        """A later audit: CMD-01 and CMD-02 pass (findings gone), EXEC-01's finding is gone too, AGT-07 is now a BLOCKER."""
        after: dict[str, Any] = copy.deepcopy(self.before)
        after["checks"] = [{**c, "verdict": "PASS"} if c["id"] in ("CMD-01", "CMD-02") else c for c in after["checks"]]
        after["findings"] = [f for f in after["findings"] if f["key"] not in ("CMD-01", "CMD-02", "EXEC-01")]
        for finding in after["findings"]:
            if finding["key"] == "AGT-07":
                finding["severity"] = "BLOCKER"
        return after

    def compare(self, after: Any, *extra: str, validate: bool = False) -> tuple[int, dict[str, Any], str]:
        """Run the tool. A hand-edited report cannot pass the report validator (its summary and overrides would have
        to be rebuilt), so unless `validate` is set the validator is bypassed; the comparison logic is what is tested."""
        argv = [self.write("before.json", self.before), self.write("after.json", after), *extra]
        if validate:
            return call(argv)
        raw = lambda path, which: validate_report.read_report(Path(path).expanduser(), which)  # noqa: E731
        with mock.patch.object(compare_reports, "read_valid", raw):
            return call(argv)

    def rows(self, envelope: dict[str, Any], section: str, key: str, name: str) -> dict[str, Any]:
        found: dict[str, Any] = next(row for row in envelope["data"][section] if row[key] == name)
        return found

    def test_identical_reports_have_no_moves(self) -> None:
        code, envelope, _ = self.compare(copy.deepcopy(self.before), "--json", validate=True)
        self.assertEqual(code, 0)
        data = envelope["data"]
        self.assertEqual(data["summary"]["checks"], {"unchanged": 12})
        self.assertEqual(data["summary"]["findings"], {"unchanged": 8})
        self.assertEqual(data["summary"]["rejected_ignored"], 4)
        self.assertEqual(data["summary"]["unexplained"], 0)

    def test_moves_without_state_have_no_label(self) -> None:
        _, envelope, _ = self.compare(self.after_report(), "--json")
        data = envelope["data"]
        self.assertFalse(data["summary"]["state_used"])
        self.assertEqual(self.rows(envelope, "checks", "check", "CMD-01")["move"], "improved")
        self.assertEqual(self.rows(envelope, "checks", "check", "CMD-01")["label"], "-")
        self.assertEqual(self.rows(envelope, "findings", "key", "CMD-01")["move"], "closed")
        self.assertEqual(self.rows(envelope, "findings", "key", "AGT-07")["severity"], "DEGRADER -> BLOCKER")

    def test_state_labels_each_move(self) -> None:
        _, envelope, _ = self.compare(self.after_report(), "--json", "--state", str(STATE))
        data = envelope["data"]
        self.assertTrue(data["summary"]["state_used"])
        self.assertEqual(self.rows(envelope, "findings", "key", "CMD-01")["label"], "explained:partial")
        self.assertEqual(self.rows(envelope, "findings", "key", "CMD-02")["label"], "explained:done")
        self.assertEqual(self.rows(envelope, "findings", "key", "EXEC-01")["label"], "unexplained:in_progress")
        self.assertEqual(self.rows(envelope, "findings", "key", "AGT-07")["label"], "unexplained")
        self.assertEqual(self.rows(envelope, "checks", "check", "CMD-02")["label"], "explained:done")
        self.assertEqual(self.rows(envelope, "checks", "check", "CMD-01")["label"], "explained:partial")
        self.assertEqual(data["summary"]["unexplained"], 2)

    def test_regression_and_new_finding_are_never_explained(self) -> None:
        after = copy.deepcopy(self.before)
        after["checks"] = [{**c, "verdict": "FAIL"} if c["id"] == "CI-01" else c for c in after["checks"]]
        new = copy.deepcopy(after["findings"][0])
        new.update(id="F-099", key="CI-01", check="CI-01")
        after["findings"].append(new)
        _, envelope, _ = self.compare(after, "--json", "--state", str(STATE))
        self.assertEqual(self.rows(envelope, "checks", "check", "CI-01")["move"], "regressed")
        self.assertEqual(self.rows(envelope, "checks", "check", "CI-01")["label"], "unexplained")
        self.assertEqual(self.rows(envelope, "findings", "key", "CI-01")["move"], "new")
        self.assertEqual(self.rows(envelope, "findings", "key", "CI-01")["label"], "unexplained")

    def test_move_to_unknown_is_changed(self) -> None:
        self.assertEqual(compare_reports.check_move("FAIL", "UNKNOWN"), "changed")
        self.assertEqual(compare_reports.check_move("NOT_APPLICABLE", "PASS"), "changed")
        self.assertEqual(compare_reports.check_move(None, "PASS"), "added")
        self.assertEqual(compare_reports.check_move("PASS", None), "removed")
        self.assertEqual(compare_reports.check_move("PARTIAL", "FAIL"), "regressed")

    def test_markdown_is_the_default_and_deterministic(self) -> None:
        after = self.after_report()
        _, first, _ = self.compare(after, "--state", str(STATE))
        _, second, _ = self.compare(after, "--state", str(STATE))
        markdown = first["data"]["markdown"]
        self.assertEqual(markdown, second["data"]["markdown"])
        self.assertNotIn("checks", first["data"])
        self.assertIn("## Checks that moved", markdown)
        self.assertIn("| CMD-01 | CMD-01 | closed | F-001 | - | BLOCKER | explained:partial |", markdown)
        self.assertTrue(markdown.endswith("\n"))

    def test_state_item_for_another_report_explains_nothing(self) -> None:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        for item in state["items"]:
            if item["finding"] == "F-002":
                item["check"] = "CMD-01"  # F-002 is a CMD-02 finding in the before report
        _, envelope, _ = self.compare(self.after_report(), "--json", "--state", self.write("state.json", state))
        self.assertTrue(any("F-002" in w for w in envelope["warnings"]))
        self.assertEqual(self.rows(envelope, "findings", "key", "CMD-02")["label"], "unexplained")

    def test_different_repositories_warn(self) -> None:
        after = copy.deepcopy(self.before)
        after["provenance"]["target"]["label"] = "other-service"
        _, envelope, _ = self.compare(after, "--json")
        self.assertTrue(any("different repositories" in w for w in envelope["warnings"]))

    def test_invalid_report_exits_2(self) -> None:
        broken = copy.deepcopy(self.before)
        del broken["checks"]
        code, envelope, _ = self.compare(broken, validate=True)
        self.assertEqual(code, 2)
        self.assertFalse(envelope["ok"])
        self.assertIn("after report is not valid", envelope["data"]["error"])

    def test_missing_file_exits_1(self) -> None:
        code, envelope, _ = call([str(self.base / "nope.json"), str(REPORT)])
        self.assertEqual(code, 1)
        self.assertFalse(envelope["ok"])

    def test_writes_nothing(self) -> None:
        self.compare(self.after_report(), "--state", str(STATE))
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), ["after.json", "before.json"])

    def test_describe(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["name"], "compare_reports")


if __name__ == "__main__":
    unittest.main()
