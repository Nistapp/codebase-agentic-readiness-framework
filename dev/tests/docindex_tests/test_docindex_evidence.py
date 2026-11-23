# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the evidence comparison (``doc_index.py evidence run`` and ``evidence compare``).

Every test is in-process on small hand-written engine reports in temporary folders; the engine never runs. A fake
runner stands in for the engine, ``git`` and ``--version``.
"""

from __future__ import annotations

import copy
import dataclasses
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Mapping, Sequence

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import doc_index
from docindex import cli, evidence

SHA = "0123456789abcdef0123456789abcdef01234567"
VERSION = "audit 9.9.9 (ruleset test)"
OLD_TIME_NS = 1_000_000_000 * 1_000_000_000


def _report(target: str = "/somewhere/target") -> dict[str, Any]:
    """A small engine report: two checks, one finding with evidence."""
    return {
        "schema_version": "2",
        "provenance": {"generated_at": "2026-11-18T00:00:00Z", "target": target},
        "checks": [
            {
                "id": "AGT-01",
                "verdict": "PASS",
                "summary": "3 nested instruction file(s)",
                "data": {"kind": "files", "count": 3, "files": ["AGENTS.md", "a/AGENTS.md", "b/AGENTS.md"]},
            },
            {
                "id": "CMD-01",
                "verdict": "FAIL",
                "summary": f"no test verb in {target}/Makefile",
                "data": {},
            },
        ],
        "findings": [
            {
                "id": "CMD-01:Makefile",
                "check": "CMD-01",
                "phase": 1,
                "severity": "BLOCKER",
                "verdict": "FAIL",
                "statement": "An agent cannot run the tests because no test verb exists.",
                "evidence": [{"path": "Makefile", "line": 12, "note": "test: (missing)"}],
                "remediation": None,
            }
        ],
    }


def _check(report: dict[str, Any], cid: str) -> dict[str, Any]:
    return next(check for check in report["checks"] if check["id"] == cid)


class FakeRunner:
    """Stands in for every command: ``--version``, ``git``, and the engine, which writes ``reports[name]``.

    ``reports[name]`` is a report dict to write, ``None`` to write nothing, or ``("stale", report)`` to write the
    report with a modification time long before the run.
    """

    def __init__(self, reports: Mapping[str, Any], engine_code: int = 0) -> None:
        self.reports = reports
        self.engine_code = engine_code
        self.calls: list[tuple[list[str], Path, dict[str, str]]] = []

    def __call__(self, argv: Sequence[str], cwd: Path, env: Mapping[str, str]) -> tuple[int, str, str]:
        args = list(argv)
        self.calls.append((args, cwd, dict(env)))
        if args[:1] == ["git"]:
            return (0, SHA + "\n", "") if "rev-parse" in args else (0, "", "")
        if args[-1] == "--version":
            return 0, VERSION + "\n", ""
        report = Path(args[args.index("--out") + 1])
        name = report.stem
        value = self.reports[name]
        if value is None:
            return self.engine_code, "", ""
        stale = isinstance(value, tuple)
        data = value[1] if stale else value
        report.write_text(json.dumps(data), encoding="utf-8")
        if stale:
            os.utime(report, ns=(OLD_TIME_NS, OLD_TIME_NS))
        return self.engine_code, "", ""


class _Temp(unittest.TestCase):
    def _folder(self) -> Path:
        handle = tempfile.TemporaryDirectory()
        self.addCleanup(handle.cleanup)
        return Path(handle.name)

    def _project(self, runner: FakeRunner, targets: Sequence[evidence.Target] | None = None) -> evidence.Project:
        repo = self._folder()
        chosen = list(targets) if targets is not None else [evidence.Target(name="repo", path=repo)]
        return evidence.Project(
            engine_dir=self._folder(), repo=repo, targets=lambda _kind, _work: chosen, python="python3", runner=runner
        )

    def _run(self, reports: Mapping[str, Any], targets: Sequence[evidence.Target] | None = None) -> Path:
        """A finished run of the given reports in a new folder; returns the folder."""
        out = self._folder() / "run"
        evidence.run(out, "repo", self._project(FakeRunner(reports), targets), self._folder())
        return out


class RunTest(_Temp):
    def test_a_run_writes_the_reports_and_a_run_record(self) -> None:
        out = self._folder() / "run"
        runner = FakeRunner({"repo": _report()})
        project = self._project(runner)
        record = evidence.run(out, "repo", project, self._folder())
        self.assertEqual(record, json.loads((out / evidence.RUN_RECORD).read_text(encoding="utf-8")))
        self.assertEqual(record["format"], evidence.RUN_FORMAT)
        self.assertEqual(record["engine_version"], VERSION)
        self.assertEqual(record["target"], "repo")
        self.assertEqual(record["commit"], SHA)
        self.assertFalse(record["dirty"])
        self.assertEqual([entry["report"] for entry in record["reports"]], ["reports/repo.json"])
        self.assertEqual(sorted(path.name for path in out.iterdir()), [evidence.REPORTS, evidence.RUN_RECORD])

    def test_the_engine_runs_as_self_audit_runs_it_from_the_engine_folder(self) -> None:
        out = self._folder() / "run"
        runner = FakeRunner({"repo": _report()})
        repo = self._folder()
        project = evidence.Project(
            engine_dir=self._folder(),
            repo=repo,
            targets=lambda _kind, _work: [evidence.Target("repo", repo, ("artefacts/*", "dist/*"))],
            python="python3",
            runner=runner,
        )
        evidence.run(out, "repo", project, self._folder())
        engine = [call for call in runner.calls if "--out" in call[0]]
        self.assertEqual(len(engine), 1)
        argv, cwd, _env = engine[0]
        report = str((out / "reports" / "repo.json").resolve())
        expected = ["python3", "-m", "audit", str(repo), "--out", report, "--format", "json", "--no-user-config"]
        self.assertEqual(argv, expected + ["--exclude", "artefacts/*", "--exclude", "dist/*"])
        self.assertNotIn("--baseline", argv)
        self.assertNotIn("--force", argv)
        self.assertEqual(cwd, project.engine_dir)

    def test_an_empty_out_folder_is_accepted(self) -> None:
        out = self._folder()
        evidence.run(out, "repo", self._project(FakeRunner({"repo": _report()})), self._folder())
        self.assertTrue((out / evidence.RUN_RECORD).is_file())

    def test_a_non_empty_out_folder_is_refused_before_the_engine_runs(self) -> None:
        out = self._folder()
        (out / "left-over.json").write_text("{}", encoding="utf-8")
        runner = FakeRunner({"repo": _report()})
        with self.assertRaises(evidence.RefusedError):
            evidence.run(out, "repo", self._project(runner), self._folder())
        self.assertEqual(runner.calls, [])
        self.assertEqual(sorted(path.name for path in out.iterdir()), ["left-over.json"])

    def test_an_out_folder_inside_the_repository_is_refused(self) -> None:
        runner = FakeRunner({"repo": _report()})
        project = self._project(runner)
        with self.assertRaises(evidence.RefusedError):
            evidence.run(project.repo / "dist" / "evidence", "repo", project, self._folder())
        self.assertFalse((project.repo / "dist").exists())

    def test_a_missing_report_is_refused(self) -> None:
        out = self._folder() / "run"
        with self.assertRaises(evidence.StaleReportError):
            evidence.run(out, "repo", self._project(FakeRunner({"repo": None})), self._folder())
        self.assertFalse((out / evidence.RUN_RECORD).exists())

    def test_a_report_older_than_the_run_is_refused(self) -> None:
        out = self._folder() / "run"
        with self.assertRaises(evidence.StaleReportError):
            evidence.run(out, "repo", self._project(FakeRunner({"repo": ("stale", _report())})), self._folder())
        self.assertFalse((out / evidence.RUN_RECORD).exists())

    def test_a_failed_engine_run_is_an_error(self) -> None:
        out = self._folder() / "run"
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.run(out, "repo", self._project(FakeRunner({"repo": _report()}, engine_code=1)), self._folder())
        self.assertNotIsInstance(caught.exception, evidence.RefusedError)

    def test_check_fresh_accepts_a_report_written_after_the_start(self) -> None:
        out = self._folder()
        started = evidence.start_stamp(out)
        report = out / "r.json"
        report.write_text("{}", encoding="utf-8")
        evidence.check_fresh(report, started)
        self.assertEqual(list(out.iterdir()), [report])


class CompareTest(_Temp):
    def _compare(self, old: dict[str, Any], new: dict[str, Any]) -> evidence.Comparison:
        return evidence.compare(self._run({"repo": old}), self._run({"repo": new}))[2]

    def test_identical_runs_report_nothing(self) -> None:
        old_dir, new_dir = self._run({"repo": _report()}), self._run({"repo": _report()})
        old, new, comparison = evidence.compare(old_dir, new_dir)
        self.assertTrue(comparison.empty)
        self.assertEqual(comparison.changes, ())
        self.assertIn("no verdict or evidence changed", evidence.to_text(old, new, comparison))
        self.assertEqual(json.loads(evidence.diff_to_json(old, new, comparison))["changes"], [])

    def test_provenance_is_not_compared(self) -> None:
        new = _report()
        new["provenance"]["generated_at"] = "2026-12-01T00:00:00Z"
        self.assertTrue(self._compare(_report(), new).empty)

    def test_a_changed_verdict_is_reported(self) -> None:
        new = _report()
        _check(new, "AGT-01")["verdict"] = "FAIL"
        comparison = self._compare(_report(), new)
        self.assertEqual(len(comparison.changes), 1)
        change = comparison.changes[0]
        self.assertEqual(
            (change.check, change.kind, change.old_verdict, change.new_verdict), ("AGT-01", "verdict", "PASS", "FAIL")
        )

    def test_the_same_verdict_with_different_data_is_reported(self) -> None:
        new = _report()
        _check(new, "AGT-01")["data"]["files"] = ["AGENTS.md", "a/AGENTS.md", "c/AGENTS.md"]
        comparison = self._compare(_report(), new)
        self.assertEqual(len(comparison.changes), 1)
        change = comparison.changes[0]
        self.assertEqual((change.check, change.kind), ("AGT-01", "evidence"))
        self.assertEqual(change.evidence, ("data.files",))

    def test_the_same_verdict_with_a_different_count_and_summary_is_reported(self) -> None:
        new = _report()
        _check(new, "AGT-01")["data"]["count"] = 2
        _check(new, "AGT-01")["summary"] = "2 nested instruction file(s)"
        change = self._compare(_report(), new).changes[0]
        self.assertEqual(change.kind, "evidence")
        self.assertEqual(change.evidence, ("data.count", "summary"))

    def test_the_same_verdict_with_a_different_quoted_line_is_reported(self) -> None:
        new = _report()
        new["findings"][0]["evidence"][0]["line"] = 14
        change = self._compare(_report(), new).changes[0]
        self.assertEqual(
            (change.check, change.kind, change.old_verdict, change.new_verdict), ("CMD-01", "evidence", "FAIL", "FAIL")
        )
        self.assertEqual(change.evidence, ("finding CMD-01:Makefile changed",))

    def test_a_finding_added_under_the_same_verdict_is_reported(self) -> None:
        new = _report()
        extra = copy.deepcopy(new["findings"][0])
        extra["id"] = "CMD-01:justfile"
        extra["evidence"] = [{"path": "justfile", "line": None, "note": None}]
        new["findings"].append(extra)
        change = self._compare(_report(), new).changes[0]
        self.assertEqual(change.evidence, ("finding CMD-01:justfile added",))

    def test_a_check_on_one_side_only_is_reported(self) -> None:
        new = _report()
        new["checks"].append({"id": "NAV-01", "verdict": "PASS", "summary": "", "data": {}})
        change = self._compare(_report(), new).changes[0]
        self.assertEqual(
            (change.check, change.kind, change.old_verdict, change.new_verdict), ("NAV-01", "added", None, "PASS")
        )

    def test_the_target_path_does_not_count_as_evidence(self) -> None:
        old_target, new_target = self._folder(), self._folder()
        old_dir = self._run({"t": _report(str(old_target))}, [evidence.Target("t", old_target)])
        new_dir = self._run({"t": _report(str(new_target))}, [evidence.Target("t", new_target)])
        self.assertTrue(evidence.compare(old_dir, new_dir)[2].empty)

    def test_a_report_on_one_side_only_is_reported(self) -> None:
        one = [evidence.Target("a", self._folder())]
        two = [evidence.Target("a", one[0].path), evidence.Target("b", self._folder())]
        old_dir = self._run({"a": _report()}, one)
        new_dir = self._run({"a": _report(), "b": _report()}, two)
        comparison = evidence.compare(old_dir, new_dir)[2]
        self.assertEqual((comparison.reports_added, comparison.reports_removed, comparison.changes), (("b",), (), ()))

    def test_the_text_and_json_are_deterministic_and_name_each_kind(self) -> None:
        new = _report()
        _check(new, "AGT-01")["verdict"] = "FAIL"
        new["findings"][0]["statement"] = "An agent cannot run the tests because the verb is broken."
        old_dir, new_dir = self._run({"repo": _report()}, None), self._run({"repo": new}, None)
        first = evidence.compare(old_dir, new_dir)
        second = evidence.compare(old_dir, new_dir)
        self.assertEqual(evidence.to_text(*first), evidence.to_text(*second))
        self.assertEqual(evidence.diff_to_json(*first), evidence.diff_to_json(*second))
        text = evidence.to_text(*first)
        self.assertIn("AGT-01: verdict PASS -> FAIL", text)
        self.assertIn("CMD-01: same verdict FAIL, evidence changed: finding CMD-01:Makefile changed", text)
        self.assertIn("1 verdict changed, 1 same verdict with different evidence", text)
        kinds = [change["kind"] for change in json.loads(evidence.diff_to_json(*first))["changes"]]
        self.assertEqual(kinds, ["verdict", "evidence"])

    def test_a_folder_without_a_run_record_is_an_error(self) -> None:
        with self.assertRaises(evidence.EvidenceError):
            evidence.compare(self._folder(), self._run({"repo": _report()}))


class CliTest(_Temp):
    def _main(self, argv: list[str], project: evidence.Project | None = None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv, {}, root=self._folder(), evidence_project=project)
        return code, out.getvalue(), err.getvalue()

    def test_run_exits_0_and_compare_reports_a_change(self) -> None:
        old_dir, new_dir = self._folder() / "old", self._folder() / "new"
        code, _out, _err = self._main(
            ["evidence", "run", "--out", str(old_dir)], self._project(FakeRunner({"repo": _report()}))
        )
        self.assertEqual(code, 0)
        new = _report()
        _check(new, "AGT-01")["data"]["count"] = 4
        code, _out, _err = self._main(
            ["evidence", "run", "--out", str(new_dir)], self._project(FakeRunner({"repo": new}))
        )
        self.assertEqual(code, 0)
        code, out, _err = self._main(["evidence", "compare", str(old_dir), str(new_dir)])
        self.assertEqual(code, 0)
        self.assertIn("AGT-01: same verdict PASS, evidence changed: data.count", out)
        code, out, _err = self._main(["evidence", "compare", str(old_dir), str(new_dir), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["format"], evidence.COMPARE_FORMAT)

    def test_a_stale_report_exits_2(self) -> None:
        out_dir = self._folder() / "run"
        project = self._project(FakeRunner({"repo": ("stale", _report())}))
        code, _out, err = self._main(["evidence", "run", "--out", str(out_dir)], project)
        self.assertEqual(code, 2)
        self.assertIn("older than the run's start", err)

    def test_a_missing_report_exits_2(self) -> None:
        code, _out, err = self._main(
            ["evidence", "run", "--out", str(self._folder() / "run")], self._project(FakeRunner({"repo": None}))
        )
        self.assertEqual(code, 2)
        self.assertIn("no report", err)

    def test_a_non_empty_out_folder_exits_2(self) -> None:
        out_dir = self._folder()
        (out_dir / "x").write_text("", encoding="utf-8")
        code, _out, err = self._main(
            ["evidence", "run", "--out", str(out_dir)], self._project(FakeRunner({"repo": _report()}))
        )
        self.assertEqual(code, 2)
        self.assertIn("not empty", err)

    def test_run_without_a_project_exits_1(self) -> None:
        code, _out, _err = self._main(["evidence", "run", "--out", str(self._folder() / "run")])
        self.assertEqual(code, 1)

    def test_compare_of_an_unreadable_folder_exits_1(self) -> None:
        code, _out, _err = self._main(["evidence", "compare", str(self._folder()), str(self._folder())])
        self.assertEqual(code, 1)


class EntryPointTest(unittest.TestCase):
    def test_the_repo_target_has_the_excludes_of_make_self_audit(self) -> None:
        makefile = (doc_index.REPO / "Makefile").read_text(encoding="utf-8")
        flags = next(line for line in makefile.splitlines() if line.startswith("SELF_AUDIT_FLAGS"))
        self.assertEqual(tuple(re.findall(r"--exclude '([^']+)'", flags)), doc_index.SELF_AUDIT_EXCLUDES)
        targets = doc_index.evidence_targets("repo", Path(tempfile.gettempdir()))
        self.assertEqual(targets, [evidence.Target("repo", doc_index.REPO, doc_index.SELF_AUDIT_EXCLUDES)])

    def test_the_project_names_the_engine_folder(self) -> None:
        project = doc_index.evidence_project()
        self.assertEqual(project.engine_dir, doc_index.REPO / "audit" / "engine")
        self.assertTrue((project.engine_dir / "audit" / "__main__.py").is_file())
        self.assertEqual(project.repo, doc_index.REPO)


def _git_out(target: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(target), *args], capture_output=True, text=True, check=True).stdout.strip()


class ScaffoldTargetTest(_Temp):
    """The ``scaffold`` target: the greenfield scaffolder runs in process into the work folder, deterministically."""

    def _templates(self) -> Path:
        """A scratch copy of the greenfield templates, which a test may change; the real files never change."""
        copy_dir = self._folder() / "templates"
        shutil.copytree(doc_index.TEMPLATES, copy_dir)
        return copy_dir

    def _run_scaffold(self, templates: Path = doc_index.TEMPLATES) -> Path:
        """A real ``evidence run`` of the scaffold of ``templates``: the engine runs on it; returns the run folder."""
        project = dataclasses.replace(
            doc_index.evidence_project(), targets=lambda _kind, work: doc_index.scaffold_targets(work, templates)
        )
        out = self._folder() / "run"
        evidence.run(out, doc_index.SCAFFOLD, project, self._folder())
        return out

    def test_scaffold_is_a_target_kind(self) -> None:
        self.assertIn("scaffold", evidence.TARGET_KINDS)

    def test_the_scaffold_is_one_committed_target_with_an_isolated_home(self) -> None:
        work = self._folder()
        targets = doc_index.evidence_targets("scaffold", work)
        self.assertEqual([target.name for target in targets], ["scaffold"])
        target = targets[0]
        self.assertEqual(target.path, work / "targets" / "scaffold")
        self.assertTrue((target.path / "AGENTS.md").is_file())
        self.assertTrue((target.path / ".github").is_dir(), "the scaffolder's renames are applied")
        self.assertEqual(target.env["HOME"], str(work / "homes" / "scaffold"))
        self.assertTrue(Path(target.env["HOME"]).is_dir())
        self.assertFalse(Path(target.env["AUDIT_INDEX_STORE"]).exists())
        self.assertEqual(_git_out(target.path, "rev-parse", "--abbrev-ref", "HEAD"), "dev")
        self.assertEqual(_git_out(target.path, "status", "--porcelain"), "")
        self.assertEqual(
            _git_out(target.path, "log", "--format=%an %at %ct"),
            "agentic-readiness-eval 1767225600 1767225600",
        )

    def test_two_scaffolds_of_the_same_tree_are_the_same_commit(self) -> None:
        first = doc_index.scaffold_targets(self._folder())[0].path
        second = doc_index.scaffold_targets(self._folder())[0].path
        self.assertEqual(_git_out(first, "rev-parse", "HEAD"), _git_out(second, "rev-parse", "HEAD"))

    def test_the_scaffold_date_is_fixed_and_the_scaffolder_keeps_its_clock(self) -> None:
        templates = self._templates()
        (templates / "docs" / "architecture" / "dated.md").write_text("# Dated\n\nDate: YYYY-MM-DD\n", encoding="utf-8")
        target = doc_index.scaffold_targets(self._folder(), templates)[0].path
        dated = (target / "docs" / "architecture" / "dated.md").read_text(encoding="utf-8")
        self.assertEqual(dated, f"# Dated\n\nDate: {doc_index.SCAFFOLD_DATE.isoformat()}\n")
        self.assertIs(sys.modules["_doc_index_bootstrap"].dt, datetime)

    def test_a_failed_scaffolder_is_an_evidence_error(self) -> None:
        with self.assertRaisesRegex(evidence.EvidenceError, "the scaffolder failed .exit 1.: .*template directory"):
            doc_index.scaffold_targets(self._folder(), self._folder() / "no-templates")

    def test_a_failed_git_command_is_an_evidence_error(self) -> None:
        with self.assertRaisesRegex(evidence.EvidenceError, "git init failed in the scaffold"):
            doc_index._commit(self._folder() / "missing", {})

    def test_two_runs_of_the_same_tree_compare_equal(self) -> None:
        old, new, comparison = evidence.compare(self._run_scaffold(), self._run_scaffold())
        self.assertTrue(comparison.empty, evidence.to_text(old, new, comparison))
        self.assertEqual([entry["name"] for entry in new["reports"]], ["scaffold"])

    def test_moving_never_restate_to_the_next_line_reports_the_agt_06_change(self) -> None:
        templates = self._templates()
        agents = templates / "AGENTS.md"
        text = agents.read_text(encoding="utf-8")
        line = "`docs/STYLE_GUIDE.md`; never restate its rules.\nThat covers"
        self.assertEqual(text.count(line), 1, "the template line this replay moves has changed")
        agents.write_text(text.replace(line, "`docs/STYLE_GUIDE.md`;\nnever restate its rules. That covers"), "utf-8")
        old, new, comparison = evidence.compare(self._run_scaffold(), self._run_scaffold(templates))
        changed = {change.check: change for change in comparison.changes}
        self.assertIn("AGT-06", changed, evidence.to_text(old, new, comparison))
        self.assertEqual(changed["AGT-06"].report, "scaffold")
        self.assertIn("summary", changed["AGT-06"].evidence)


if __name__ == "__main__":
    unittest.main()
