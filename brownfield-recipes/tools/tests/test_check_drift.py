# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`check_drift.py` on scripted git repositories: no drift, drift on a cited file, drift on an unrelated file, a report
SHA that is not in the history, a report with no SHA, and a report that is not valid. Standard library only.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence

import _git
import _paths  # noqa: F401  (puts the tools folder on sys.path)
import _common
import check_drift

REPORT = _paths.TOOLS.parent / "schema" / "examples" / "example-service.audit-report.20261010T094207Z.json"
FILES = ("package.json", ".nvmrc", "AGENTS.md", "src/config/constants.ts", "src/other/unrelated.txt")


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(check_drift.INFO, check_drift.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


class CheckDriftTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.repo = base / "repo"
        _git.make_repo(self.repo, FILES)
        self.audited = _git.run_git(self.repo, "rev-parse", "HEAD")
        self.report_path = base / "report.json"

    def write_report(self, sha: str | None) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        report["provenance"]["target"]["git_sha"] = sha
        self.report_path.write_text(json.dumps(report), encoding="utf-8")

    def commit(self, name: str, text: str) -> None:
        (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / name).write_text(text, encoding="utf-8")
        _git.run_git(self.repo, "add", "-A")
        _git.run_git(self.repo, "commit", "-q", "-m", "change")

    def run_tool(self) -> tuple[int, dict[str, Any], str]:
        return call([str(self.report_path), str(self.repo)])

    def test_no_drift(self) -> None:
        self.write_report(self.audited)
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 0)
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["data"]["status"], "current")
        self.assertFalse(envelope["data"]["drifted"])
        self.assertEqual(envelope["data"]["findings"], [])

    def test_drift_on_a_cited_file(self) -> None:
        self.write_report(self.audited)
        self.commit("package.json", "changed\n")
        code, envelope, err = self.run_tool()
        data = envelope["data"]
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "drifted")
        self.assertTrue(data["drifted"])
        self.assertEqual(data["changed_paths"], ["package.json"])
        ids = {item["id"] for item in data["findings"]}
        self.assertTrue({"F-001", "F-002"} <= ids)
        self.assertNotIn("F-004", ids)
        self.assertIn("drifted", err)

    def test_drift_on_a_touches_path_only(self) -> None:
        self.write_report(self.audited)
        self.commit(".nvmrc", "20\n")  # F-003 cites package.json but lists .nvmrc in remediation.touches
        _, envelope, _ = self.run_tool()
        self.assertEqual([item["id"] for item in envelope["data"]["findings"]], ["F-003"])

    def test_drift_on_an_unrelated_file(self) -> None:
        self.write_report(self.audited)
        self.commit("src/other/unrelated.txt", "changed\n")
        code, envelope, _ = self.run_tool()
        data = envelope["data"]
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "drifted")
        self.assertEqual(data["changed_paths"], ["src/other/unrelated.txt"])
        self.assertEqual(data["findings"], [])

    def test_a_deleted_file_counts(self) -> None:
        self.write_report(self.audited)
        (self.repo / "AGENTS.md").unlink()
        _git.run_git(self.repo, "add", "-A")
        _git.run_git(self.repo, "commit", "-q", "-m", "delete")
        _, envelope, _ = self.run_tool()
        self.assertIn("F-006", [item["id"] for item in envelope["data"]["findings"]])

    def test_report_sha_missing_from_history(self) -> None:
        self.write_report("1" * 40)
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["status"], "sha_missing")
        self.assertEqual(envelope["data"]["findings"], [])
        self.assertTrue(envelope["warnings"])

    def test_report_without_a_sha(self) -> None:
        self.write_report(None)
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["status"], "no_sha")
        self.assertTrue(envelope["warnings"])

    def test_rewritten_history_warns(self) -> None:
        self.write_report(self.audited)
        _git.run_git(self.repo, "checkout", "-q", "--orphan", "other")
        self.commit("package.json", "rewritten\n")
        _, envelope, _ = self.run_tool()
        self.assertEqual(envelope["data"]["status"], "drifted")
        self.assertTrue(any("ancestor" in warning for warning in envelope["warnings"]))

    def test_writes_nothing_in_the_target(self) -> None:
        self.write_report(self.audited)
        self.commit("package.json", "changed\n")
        before = _git.run_git(self.repo, "status", "--porcelain", "--ignored")
        self.run_tool()
        self.assertEqual(_git.run_git(self.repo, "status", "--porcelain", "--ignored"), before)

    def test_invalid_report_is_exit_2(self) -> None:
        self.report_path.write_text(json.dumps({"schema_version": "x"}), encoding="utf-8")
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 2)
        self.assertFalse(envelope["ok"])

    def test_missing_report_and_non_repo_are_exit_1(self) -> None:
        self.assertEqual(call([str(self.report_path), str(self.repo)])[0], 1)
        self.write_report(self.audited)
        plain = Path(self._tmp.name) / "plain"
        plain.mkdir()
        self.assertEqual(call([str(self.report_path), str(plain)])[0], 1)

    def test_describe(self) -> None:
        out = io.StringIO()
        code = _common.run_tool(check_drift.INFO, check_drift.handler, ["--describe"], stdout=out, stderr=io.StringIO())
        manifest = json.loads(out.getvalue())["data"]
        self.assertEqual(code, 0)
        self.assertEqual(manifest["name"], "check_drift")
        self.assertFalse(manifest["writes_inside_target"])


if __name__ == "__main__":
    unittest.main()
