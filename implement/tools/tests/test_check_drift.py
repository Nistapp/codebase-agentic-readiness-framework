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

import _implement_paths  # noqa: F401  (puts the tools folders on sys.path)
import _git
import _common
import check_drift
import progress

REPORT = _implement_paths.AUDIT / "schema" / "examples" / "example-service.audit-report.20261010T094207Z.json"
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

    def write_report(self, sha: str | None, release: str | None = None) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        report["provenance"]["target"]["git_sha"] = sha
        if release is not None:
            report["provenance"]["framework"]["release"] = release
        self.report_path.write_text(json.dumps(report), encoding="utf-8")

    def test_the_versions_of_the_report_and_the_tools_are_in_the_data(self) -> None:
        self.write_report(self.audited)
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 0)
        versions = envelope["data"]["versions"]
        self.assertEqual(versions["report"]["release"], "0.3.2")
        self.assertEqual(versions["tools"]["release"], progress.FRAMEWORK_RELEASE)
        self.assertIn(versions["relation"], ("same", "older", "newer"))

    def test_a_report_from_an_older_release_warns_and_goes_on(self) -> None:
        self.write_report(self.audited, release="0.0.1")
        code, envelope, stderr = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["versions"]["relation"], "older")
        self.assertTrue(any("made by framework v0.0.1" in warning for warning in envelope["warnings"]))
        self.assertIn("the report is from an older framework release", stderr)

    def test_a_report_from_a_newer_release_stops(self) -> None:
        self.write_report(self.audited, release="99.0.0")
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 2)
        self.assertIn("Update the framework to v99.0.0 or later", envelope["data"]["error"])

    def test_a_report_with_another_schema_stops_with_the_plain_message(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        report["schema_version"] = "0.1"
        self.report_path.write_text(json.dumps(report), encoding="utf-8")
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 2)
        self.assertTrue(envelope["data"]["error"].startswith("the report has schema '0.1'"))

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

    def test_a_short_id_at_head_is_current(self) -> None:
        self.write_report(self.audited[:12])
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["status"], "current")
        self.assertFalse(envelope["data"]["drifted"])

    def test_a_short_id_behind_head_drifts(self) -> None:
        self.write_report(self.audited[:12])
        self.commit("notes.txt", "new\n")
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["status"], "drifted")
        self.assertEqual(envelope["data"]["changed_paths"], ["notes.txt"])

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

    def test_dirty_is_false_on_a_clean_tree_and_true_after_an_edit(self) -> None:
        self.write_report(self.audited)
        _, clean, err = self.run_tool()
        self.assertIs(clean["data"]["dirty"], False)
        self.assertNotIn("dirty", err)
        (self.repo / "package.json").write_text("edited, not committed\n", encoding="utf-8")
        _, dirty, err = self.run_tool()
        self.assertIs(dirty["data"]["dirty"], True)
        self.assertIn("working tree is dirty", err)
        self.assertTrue(any("uncommitted" in warning for warning in dirty["warnings"]))

    def test_dirty_counts_an_untracked_file(self) -> None:
        self.write_report(self.audited)
        (self.repo / "stray.txt").write_text("new\n", encoding="utf-8")
        self.assertIs(self.run_tool()[1]["data"]["dirty"], True)


class ReportDigestTests(unittest.TestCase):
    """`report_changed`: the report file against the SHA-256 `progress.py init` recorded in the workspace's state."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        _git.make_repo(self.repo, FILES)
        self.workspace = Path(self._tmp.name) / "workspace"
        self.report = self.workspace / REPORT.name
        self.workspace.mkdir()
        document = json.loads(REPORT.read_text(encoding="utf-8"))
        document["provenance"]["target"]["git_sha"] = _git.run_git(self.repo, "rev-parse", "HEAD")
        self.report.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def init_state(self) -> None:
        out = io.StringIO()
        code = _common.run_tool(
            progress.INFO,
            progress.handler,
            ["init", "--report", str(self.report), "--target", str(self.repo), "--date", "2026-11-05"],
            stdout=out,
            stderr=io.StringIO(),
        )
        self.assertEqual(code, 0, out.getvalue())

    def drift(self) -> dict[str, Any]:
        code, envelope, _ = call([str(self.report), str(self.repo)])
        self.assertEqual(code, 0, envelope)
        data: dict[str, Any] = envelope["data"]
        return data

    def test_unchanged_report_is_not_changed(self) -> None:
        self.init_state()
        data = self.drift()
        self.assertIs(data["report_changed"], False)
        self.assertIs(data["dirty"], False)

    def test_edited_report_is_changed_and_says_so(self) -> None:
        self.init_state()
        self.report.write_text(self.report.read_text(encoding="utf-8").replace("package.json", "package.JSON", 1))
        out, err = io.StringIO(), io.StringIO()
        code = _common.run_tool(
            check_drift.INFO, check_drift.handler, [str(self.report), str(self.repo)], stdout=out, stderr=err
        )
        envelope = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertIs(envelope["data"]["report_changed"], True)
        self.assertTrue(any("edited" in warning for warning in envelope["warnings"]))
        self.assertIn("report file was edited", err.getvalue())

    def test_no_state_means_unknown(self) -> None:
        self.assertIsNone(self.drift()["report_changed"])

    def test_a_state_from_before_the_digest_means_unknown(self) -> None:
        self.init_state()
        state_path = next(self.workspace.glob("*-state.json"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["schema_version"] = "0.1"
        del state["source_reports"][0]["sha256"]
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        self.assertIsNone(self.drift()["report_changed"])

    def test_a_report_the_state_does_not_list_means_unknown(self) -> None:
        self.init_state()
        other = self.report.with_name("other.audit-report.20261010T094207Z.json")
        other.write_text(self.report.read_text(encoding="utf-8"), encoding="utf-8")
        code, envelope, _ = call([str(other), str(self.repo)])
        self.assertEqual(code, 0)
        self.assertIsNone(envelope["data"]["report_changed"])


if __name__ == "__main__":
    unittest.main()
