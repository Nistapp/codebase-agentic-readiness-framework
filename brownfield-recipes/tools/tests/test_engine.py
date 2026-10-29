# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The engine launcher runs the engine from any directory, names its report, and never replaces a file.

Most tests call the launcher in process with string streams. The first class starts it as a script from the
filesystem root, which is how a recipe calls it. Scans run on the engine's own one-defect fixtures, which are
small. Standard library only.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any, Sequence
from unittest import mock

import _paths
import _common
import engine

TOOLS = _paths.TOOLS
ENGINE_DIR = engine.ENGINE_DIR
FIXTURE = ENGINE_DIR / "tests" / "fixtures" / "cmd-ok-npm"
REPORT_NAME = re.compile(r"^(?P<label>[a-z0-9._-]+)\.engine-report\.(?P<stamp>[0-9]{8}T[0-9]{6}Z)(-[0-9]+)?\.json$")
FIXED_STAMP = "20261010T094207Z"


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    """Run the launcher in process. Returns the exit code, the parsed envelope and stderr."""
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(engine.INFO, engine.handler, list(argv), stdout=out, stderr=err)
    envelope: dict[str, Any] = json.loads(out.getvalue())
    return code, envelope, err.getvalue()


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Every file and directory under `root`, with size and modification time, to prove nothing changed."""
    state: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        info = path.stat()
        state[str(path.relative_to(root))] = (info.st_size, info.st_mtime_ns)
    return state


class working_directory:
    """Change directory for a block and change back, even when the block fails."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.previous = ""

    def __enter__(self) -> None:
        self.previous = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, *exc: object) -> None:
        os.chdir(self.previous)


class ScriptTests(unittest.TestCase):
    """The launcher started as a script from `/`, as a recipe starts it."""

    def start(self, *args: str) -> tuple[int, dict[str, Any]]:
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "engine.py"), *args], cwd="/", text=True, capture_output=True, check=False
        )
        return proc.returncode, json.loads(proc.stdout)

    def test_list_checks_works_from_the_filesystem_root(self) -> None:
        code, envelope = self.start("--list-checks")
        self.assertEqual(code, 0)
        self.assertIs(envelope["ok"], True)
        self.assertEqual(envelope["tool"], "engine")
        self.assertGreaterEqual(len(envelope["data"]["checks"]), 69)
        self.assertEqual(envelope["data"]["engine"]["name"], "python-agentic-audit")

    def test_the_checks_are_the_engines_own(self) -> None:
        _, envelope = self.start("--list-checks")
        proc = subprocess.run(
            [sys.executable, "-m", "audit", "--list-checks", "--format", "json"],
            cwd=str(ENGINE_DIR),
            text=True,
            capture_output=True,
            check=True,
        )
        own = json.loads(proc.stdout)
        self.assertEqual(envelope["data"]["checks"], own["checks"])
        self.assertEqual(envelope["data"]["engine"], own["engine"])

    def test_describe_works_from_the_filesystem_root(self) -> None:
        code, envelope = self.start("--describe")
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["name"], "engine")
        self.assertIs(envelope["data"]["writes_inside_target"], False)

    def test_a_scan_works_from_the_filesystem_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, envelope = self.start(str(FIXTURE), "--out-dir", tmp)
            self.assertEqual(code, 0, envelope)
            reports = list(Path(tmp).iterdir())
            self.assertEqual([p.name for p in reports], [Path(envelope["data"]["report"]).name])
            self.assertRegex(reports[0].name, REPORT_NAME)


class ListChecksTests(unittest.TestCase):
    def test_the_envelope_carries_the_engine_and_its_checks(self) -> None:
        code, envelope, err = call(["--list-checks"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["omitted"], 0)
        self.assertIs(envelope["truncated"], False)
        self.assertIn("checks catalogued", err)
        ids = [check["id"] for check in envelope["data"]["checks"]]
        self.assertEqual(ids, sorted(set(ids), key=ids.index), "no check is listed twice")

    def test_another_argument_is_refused(self) -> None:
        for extra in (["--phase", "1"], [str(FIXTURE)], ["--out-dir", "x"], ["--run-gates"]):
            with self.subTest(extra=extra):
                code, envelope, _ = call(["--list-checks", *extra])
                self.assertEqual(code, 1)
                self.assertIn("--list-checks takes no other argument", envelope["data"]["error"])

    def test_the_engines_own_format_flag_is_not_offered(self) -> None:
        code, envelope, _ = call(["--list-checks", "--format", "json"])
        self.assertEqual(code, 1)
        self.assertIn("unrecognized arguments", envelope["data"]["error"])


class ScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name).resolve() / "out"
        self.fixture_before = snapshot(FIXTURE)

    def tearDown(self) -> None:
        self.assertEqual(snapshot(FIXTURE), self.fixture_before, "a scan must not change the target")

    def reports(self) -> list[Path]:
        return sorted(self.out.iterdir()) if self.out.exists() else []

    def copy_fixture_as(self, name: str) -> Path:
        copy = Path(self._tmp.name).resolve() / name
        shutil.copytree(FIXTURE, copy)
        return copy

    def test_the_report_is_named_for_the_repository_and_the_scan_time(self) -> None:
        code, envelope, err = call([str(FIXTURE), "--out-dir", str(self.out)])
        self.assertEqual(code, 0, envelope)
        data = envelope["data"]
        report = Path(data["report"])
        match = REPORT_NAME.match(report.name)
        assert match is not None
        self.assertEqual(match["label"], "cmd-ok-npm")
        self.assertEqual(match["stamp"], data["stamp"])
        self.assertEqual(data["label"], "cmd-ok-npm")
        self.assertEqual(report.parent, self.out)
        self.assertEqual(self.reports(), [report])
        self.assertIn(f"engine: report written to {report}", err)
        self.assertEqual(data["target"], str(FIXTURE.resolve()))
        self.assertEqual(sorted(data["engine"]), ["ruleset_revision", "version"])

    def test_the_report_is_the_engines_json_and_only_json(self) -> None:
        code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out)])
        self.assertEqual(code, 0)
        report = json.loads(Path(envelope["data"]["report"]).read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], "2")
        self.assertEqual(len(self.reports()), 1, "no Markdown file and no draft beside the report")

    def test_the_engine_is_asked_for_json_with_a_full_file_name_and_never_for_force(self) -> None:
        with mock.patch.object(engine, "run_engine", wraps=engine.run_engine) as spy:
            code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out), "--phase", "1"])
        self.assertEqual(code, 0)
        argv = spy.call_args.args[0]
        self.assertEqual(argv[0], str(FIXTURE.resolve()))
        self.assertEqual(argv[argv.index("--format") + 1], "json")
        self.assertEqual(argv[argv.index("--out") + 1], envelope["data"]["report"])
        self.assertEqual(argv[argv.index("--phase") + 1], "1")
        for never in ("--force", "--baseline", "--fail-on"):
            self.assertNotIn(never, argv)

    def test_options_are_passed_to_the_engine(self) -> None:
        with mock.patch.object(engine, "run_engine", wraps=engine.run_engine) as spy:
            code, _, _ = call(
                [
                    str(FIXTURE),
                    "--out-dir",
                    str(self.out),
                    "--exclude",
                    "docs/**",
                    "--exclude",
                    "*.md",
                    "--max-files",
                    "500",
                ]
            )
        self.assertEqual(code, 0)
        argv = spy.call_args.args[0]
        self.assertEqual([argv[i + 1] for i, a in enumerate(argv) if a == "--exclude"], ["docs/**", "*.md"])
        self.assertEqual(argv[argv.index("--max-files") + 1], "500")

    def test_without_emit_baseline_no_draft_is_written_and_the_field_is_null(self) -> None:
        code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out)])
        self.assertEqual(code, 0)
        self.assertIsNone(envelope["data"]["baseline_draft"])
        self.assertFalse((self.out / "do-not-do.draft.md").exists())

    def test_emit_baseline_is_forwarded_and_the_draft_path_is_reported(self) -> None:
        with mock.patch.object(engine, "run_engine", wraps=engine.run_engine) as spy:
            code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out), "--emit-baseline"])
        self.assertEqual(code, 0)
        self.assertIn("--emit-baseline", spy.call_args.args[0])
        draft = self.out / "do-not-do.draft.md"
        self.assertEqual(envelope["data"]["baseline_draft"], str(draft))
        self.assertTrue(draft.is_file())

    def test_the_engine_claims_success_but_wrote_no_draft_is_an_internal_error(self) -> None:
        def fake(argv: list[str]) -> tuple[int, str, str]:
            Path(argv[argv.index("--out") + 1]).write_text("{}", encoding="utf-8")
            return 0, "", ""

        with mock.patch.object(engine, "run_engine", side_effect=fake):
            code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out), "--emit-baseline"])
        self.assertEqual(code, 3)
        self.assertIn("wrote no draft", envelope["data"]["error"])

    def test_a_second_scan_in_the_same_second_gets_a_new_name_and_leaves_the_first_alone(self) -> None:
        with mock.patch.object(_common, "utc_stamp", return_value=FIXED_STAMP):
            first_code, first, _ = call([str(FIXTURE), "--out-dir", str(self.out)])
            first_bytes = Path(first["data"]["report"]).read_bytes()
            second_code, second, _ = call([str(FIXTURE), "--out-dir", str(self.out)])
        self.assertEqual((first_code, second_code), (0, 0))
        self.assertEqual(Path(first["data"]["report"]).name, f"cmd-ok-npm.engine-report.{FIXED_STAMP}.json")
        self.assertEqual(Path(second["data"]["report"]).name, f"cmd-ok-npm.engine-report.{FIXED_STAMP}-2.json")
        self.assertEqual(Path(first["data"]["report"]).read_bytes(), first_bytes)
        self.assertEqual(len(self.reports()), 2)

    def test_a_name_taken_after_it_was_chosen_is_not_overwritten(self) -> None:
        self.out.mkdir(parents=True)
        taken = self.out / f"cmd-ok-npm.engine-report.{FIXED_STAMP}.json"
        taken.write_text("another run's report", encoding="utf-8")
        with mock.patch.object(_common, "free_name", return_value=taken):
            code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out)])
        self.assertEqual(code, 1)
        self.assertIn("the engine refused the run", envelope["data"]["error"])
        self.assertIn("nothing was replaced", envelope["data"]["error"])
        self.assertNotIn("--force", envelope["data"]["error"])
        self.assertEqual(taken.read_text(encoding="utf-8"), "another run's report")

    def test_an_explicit_label_names_the_file(self) -> None:
        code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out), "--repo-label", "my-repo"])
        self.assertEqual(code, 0)
        self.assertTrue(Path(envelope["data"]["report"]).name.startswith("my-repo.engine-report."))

    def test_a_bad_label_is_a_usage_error_and_nothing_is_written(self) -> None:
        code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out), "--repo-label", "Bad Label"])
        self.assertEqual(code, 1)
        self.assertIn("repo_label", envelope["data"]["error"])
        self.assertEqual(self.reports(), [])

    def test_the_label_is_derived_from_the_directory_name(self) -> None:
        target = self.copy_fixture_as("Digital_Assistant_microServices")
        code, envelope, _ = call([str(target), "--out-dir", str(self.out)])
        self.assertEqual(code, 0)
        self.assertTrue(Path(envelope["data"]["report"]).name.startswith("digital-assistant-micros.engine-report."))

    def test_an_output_directory_inside_the_target_is_refused(self) -> None:
        target = self.copy_fixture_as("inside")
        before = snapshot(target)
        code, envelope, _ = call([str(target), "--out-dir", str(target / "reports")])
        self.assertEqual(code, 1)
        self.assertIn("inside the target", envelope["data"]["error"])
        self.assertEqual(snapshot(target), before)

    def test_the_default_output_directory_is_the_current_directory(self) -> None:
        self.out.mkdir(parents=True)
        with working_directory(self.out):
            code, envelope, _ = call([str(FIXTURE)])
        self.assertEqual(code, 0)
        self.assertEqual(Path(envelope["data"]["report"]).parent, self.out)

    def test_the_current_directory_inside_the_target_is_refused_with_a_hint(self) -> None:
        target = self.copy_fixture_as("inside")
        before = snapshot(target)
        with working_directory(target):
            code, envelope, err = call([str(target)])
        self.assertEqual(code, 1)
        self.assertIn("inside the target", envelope["data"]["error"])
        self.assertIn("--out-dir", err)
        self.assertEqual(snapshot(target), before)

    def test_a_missing_target_is_a_usage_error(self) -> None:
        code, envelope, _ = call([str(self.out / "nowhere"), "--out-dir", str(self.out)])
        self.assertEqual(code, 1)
        self.assertIn("target not found", envelope["data"]["error"])

    def test_options_that_could_overwrite_or_gate_are_not_offered(self) -> None:
        for flags in (
            ["--force"],
            ["--out", "x"],
            ["--format", "md"],
            ["--fail-on", "BLOCKER"],
            ["--baseline", "x"],
        ):
            with self.subTest(flags=flags):
                code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out), *flags])
                self.assertEqual(code, 1)
                self.assertIn("unrecognized arguments", envelope["data"]["error"])
        self.assertEqual(self.reports(), [])

    def test_run_gates_without_allow_probe_is_refused_with_the_engines_reason(self) -> None:
        code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out), "--run-gates"])
        self.assertEqual(code, 1)
        self.assertIn("--run-gates requires at least one --allow-probe VERB", envelope["data"]["error"])
        self.assertEqual(self.reports(), [])

    def test_an_engine_exit_code_other_than_0_or_1_is_an_internal_error(self) -> None:
        with mock.patch.object(engine, "run_engine", return_value=(2, "", "audit: gate failed\n")):
            code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out)])
        self.assertEqual(code, 3)
        self.assertIn("exited with code 2", envelope["data"]["error"])

    def test_success_without_a_report_is_an_internal_error(self) -> None:
        with mock.patch.object(engine, "run_engine", return_value=(0, "", "")):
            code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out)])
        self.assertEqual(code, 3)
        self.assertIn("wrote no report", envelope["data"]["error"])

    def test_text_the_engine_prints_to_stdout_becomes_a_warning(self) -> None:
        def fake(argv: list[str]) -> tuple[int, str, str]:
            Path(argv[argv.index("--out") + 1]).write_text("{}", encoding="utf-8")
            return 0, "stray text\n", ""

        with mock.patch.object(engine, "run_engine", side_effect=fake):
            code, envelope, _ = call([str(FIXTURE), "--out-dir", str(self.out)])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["warnings"], ["the engine printed to stdout: stray text"])

    def test_what_the_engine_says_on_stderr_is_kept_in_the_summary(self) -> None:
        def fake(argv: list[str]) -> tuple[int, str, str]:
            Path(argv[argv.index("--out") + 1]).write_text("{}", encoding="utf-8")
            return 0, "", "audit: note about the scan\n\nreport written: somewhere\n"

        with mock.patch.object(engine, "run_engine", side_effect=fake):
            code, _, err = call([str(FIXTURE), "--out-dir", str(self.out)])
        self.assertEqual(code, 0)
        self.assertIn("audit: note about the scan", err)
        self.assertNotIn("report written: somewhere", err)


class LoadEngineTests(unittest.TestCase):
    def test_the_engine_comes_from_the_deterministic_audit_folder(self) -> None:
        module = engine.load_engine()
        self.assertEqual(module.__name__, "audit.__main__")
        self.assertIn(ENGINE_DIR, Path(sys.modules["audit"].__file__ or "").resolve().parents)

    def test_a_different_audit_package_is_refused(self) -> None:
        engine.load_engine()  # so that audit.__main__ is already imported and only the package is swapped
        impostor = types.ModuleType("audit")
        impostor.__file__ = "/somewhere/else/audit/__init__.py"
        impostor.__path__ = [str(ENGINE_DIR / "audit")]
        with mock.patch.dict(sys.modules, {"audit": impostor}):
            with self.assertRaises(_common.ToolError) as caught:
                engine.load_engine()
        self.assertIn("not from", str(caught.exception))

    def test_loading_twice_adds_the_folder_to_the_path_once(self) -> None:
        engine.load_engine()
        engine.load_engine()
        self.assertEqual(sys.path.count(str(ENGINE_DIR)), 1)


if __name__ == "__main__":
    unittest.main()
