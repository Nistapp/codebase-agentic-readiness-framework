# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The implement tool ``check_regressions.py`` compares two engine reports as ``dev/docindex/evidence.py`` does.

The shipped tool may not import ``dev/``, so it holds its own copy of the evidence comparison (RF5.1 proposal,
option A). This test holds the two in step: on each pair of engine reports, both must name the same changed checks,
the same verdict on each side and the same changed evidence parts, and the tool's class must fit the kind
``evidence.py`` gives. The pairs are hand-made, plus one pair of real engine runs, in process, on a small git
repository in a temporary folder before and after a change. One known difference is pinned too: the tool reads the
report's ``not_applicable`` list as the verdict ``NOT_APPLICABLE``, which ``evidence.py`` does not read.
"""

from __future__ import annotations

import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import _dev_paths
import _common
import _git
import engine
from docindex import evidence

IMPLEMENT_TOOLS = _dev_paths.REPO / "implement" / "tools"
if str(IMPLEMENT_TOOLS) not in sys.path:
    sys.path.insert(0, str(IMPLEMENT_TOOLS))

import check_regressions  # noqa: E402  (needs implement/tools on sys.path)

TARGET = "/work/theme"

#: The tool's classes each kind of ``evidence.CheckChange`` may take.
KINDS = {
    "added": {"added"},
    "removed": {"removed", "lost_pass"},
    "verdict": {"lost_pass", "regressed", "improved", "changed"},
    "evidence": {"evidence"},
}


def _report() -> dict[str, Any]:
    return {
        "schema_version": "2",
        "provenance": {"target": TARGET},
        "checks": [
            {"id": "AGT-01", "verdict": "PASS", "summary": "2 instruction files", "data": {"count": 2, "files": ["a"]}},
            {"id": "CMD-01", "verdict": "PARTIAL", "summary": "no lint verb", "data": {}},
            {"id": "DOC-01", "verdict": "PASS", "summary": "docs/ holds 3 pages", "data": ["x"]},
            {"id": "SEC-01", "verdict": "FAIL", "summary": "no scanner", "data": {}},
            {"id": "TST-02", "verdict": "UNKNOWN", "summary": "probes disabled", "data": {}},
        ],
        "findings": [
            {"id": "CMD-01", "check": "CMD-01", "severity": "DEGRADER", "evidence": [{"path": "Makefile"}]},
            {"check": "SEC-01", "severity": "BLOCKER", "evidence": [{"path": "<repository>"}]},
        ],
        "not_applicable": [],
    }


def _check(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(item for item in report["checks"] if item["id"] == check_id)
    return found


def _pairs() -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """Named pairs of a base and a close report, each built from the one base."""
    pairs: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    def pair(name: str) -> dict[str, Any]:
        base, close = _report(), _report()
        pairs[name] = (base, close)
        return close

    pair("identical")
    close = pair("lost pass with a new finding")
    _check(close, "AGT-01").update(verdict="FAIL", summary="no instruction file")
    close["findings"].append({"id": "AGT-01", "check": "AGT-01", "severity": "BLOCKER", "evidence": []})
    pair("partial to fail")["checks"][1]["verdict"] = "FAIL"
    close = pair("improvement with a finding removed")
    _check(close, "SEC-01")["verdict"] = "PASS"
    close["findings"] = close["findings"][:1]
    pair("unordered move")["checks"][4]["verdict"] = "FAIL"
    close = pair("check removed and added")
    close["checks"] = [item for item in close["checks"] if item["id"] not in ("AGT-01", "CMD-01")]
    close["checks"].append({"id": "CI-01", "verdict": "FAIL", "summary": "no CI", "data": {}})
    close = pair("evidence only")
    _check(close, "AGT-01")["data"] = {"count": 3, "files": ["a"], "nested": True}
    _check(close, "DOC-01").update(summary="docs/ holds 4 pages", data={"pages": 4})
    close["findings"][0]["evidence"] = [{"path": "Makefile", "line": 3}]
    close = pair("a finding listed twice under one id")
    close["findings"].append(copy.deepcopy(close["findings"][0]))
    return pairs


def _tool_rows(base: dict[str, Any], close: dict[str, Any]) -> dict[str, check_regressions.Row]:
    return {row.check: row for row in check_regressions.compare(base, close) if row.kind != "unchanged"}


def _evidence_changes(base: dict[str, Any], close: dict[str, Any]) -> dict[str, evidence.CheckChange]:
    replacements = [(base["provenance"]["target"], evidence.TARGET_PLACEHOLDER)]
    old = evidence.checks_of(base, replacements)
    new = evidence.checks_of(close, [(close["provenance"]["target"], evidence.TARGET_PLACEHOLDER)])
    return {change.check: change for change in evidence.compare_reports("pair", old, new)}


def assert_same(
    case: unittest.TestCase, base: dict[str, Any], close: dict[str, Any]
) -> dict[str, check_regressions.Row]:
    """Both comparisons name the same changed checks, verdicts and evidence parts; the tool's class fits the kind."""
    rows, changes = _tool_rows(base, close), _evidence_changes(base, close)
    case.assertEqual(sorted(rows), sorted(changes))
    for check_id, change in changes.items():
        row = rows[check_id]
        with case.subTest(check=check_id):
            case.assertEqual((row.base, row.close), (change.old_verdict, change.new_verdict))
            case.assertEqual(row.evidence, change.evidence)
            case.assertIn(row.kind, KINDS[change.kind])
    return rows


class ParityTests(unittest.TestCase):
    def test_every_hand_made_pair_is_compared_the_same_way(self) -> None:
        for name, (base, close) in _pairs().items():
            with self.subTest(pair=name):
                assert_same(self, base, close)

    def test_the_pairs_reach_every_class_but_unchanged_of_the_tool(self) -> None:
        reached = {row.kind for base, close in _pairs().values() for row in _tool_rows(base, close).values()}
        self.assertEqual(reached, set(check_regressions.CLASSES) - {"unchanged"})

    def test_a_not_applicable_check_is_the_one_known_difference(self) -> None:
        base, close = _report(), _report()
        close["checks"] = [item for item in close["checks"] if item["id"] != "AGT-01"]
        close["not_applicable"] = ["AGT-01"]
        rows, changes = _tool_rows(base, close), _evidence_changes(base, close)
        self.assertEqual((rows["AGT-01"].kind, rows["AGT-01"].close), ("lost_pass", "NOT_APPLICABLE"))
        self.assertEqual((changes["AGT-01"].kind, changes["AGT-01"].new_verdict), ("removed", None))


class RealRunParityTests(unittest.TestCase):
    """One pair of real engine runs, in process: a small repository before and after a theme's change."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name).resolve()
        self.repo = self.folder / "theme"
        _git.make_repo(self.repo, ("README.md", "AGENTS.md", ".mcp.json", "docs/guide.md", "Makefile"))
        (self.repo / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"codebase-memory-mcp": {"command": "codebase-memory-mcp"}}}), encoding="utf-8"
        )
        (self.repo / "Makefile").write_text("test:\n\tpython3 -m unittest\n", encoding="utf-8")
        self.commit("start")

    def commit(self, message: str) -> None:
        _git.run_git(self.repo, "add", "-A")
        _git.run_git(self.repo, "commit", "-q", "-m", message)

    def scan(self, name: str) -> dict[str, Any]:
        out_dir = self.folder / name
        out_dir.mkdir()
        out = io.StringIO()
        argv = [str(self.repo), "--out-dir", str(out_dir), "--no-user-config"]
        code = _common.run_tool(engine.INFO, engine.handler, argv, stdout=out, stderr=io.StringIO())
        self.assertEqual(code, 0, out.getvalue())
        report: dict[str, Any] = json.loads(Path(json.loads(out.getvalue())["data"]["report"]).read_text("utf-8"))
        return report

    def test_a_real_base_and_close_run_are_compared_the_same_way(self) -> None:
        base = self.scan("base")
        (self.repo / ".mcp.json").unlink()
        (self.repo / "docs" / "second.md").write_text("# Second\n\nA short page.\n", encoding="utf-8")
        self.commit("change")
        close = self.scan("close")
        rows = assert_same(self, base, close)
        self.assertEqual(rows["IDX-01"].kind, "lost_pass")
        self.assertTrue(any(row.kind == "evidence" for row in rows.values()), rows)
        status = subprocess.run(
            ["git", "-C", str(self.repo), "status", "--porcelain"], capture_output=True, text=True, check=True
        )
        self.assertEqual(status.stdout, "")


if __name__ == "__main__":
    unittest.main()
