# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TST test-surface checks against their one-defect fixtures.

Each fixture is a small node project that isolates one TST defect; the inline cases cover the
verdict floors and the probe contract. `tst-03-skip-markers` is a census, so it passes with a
non-zero count rather than failing — the test asserts the count, not a threshold.

The probe (`TST-02`) is exercised twice: refused by default (the audit must run no probe unless
`--run-gates` + `--allow-probe` are passed), and permitted against a trivially safe temp repo. The
target's real test runner is never invoked outside a temp fixture.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.probes import ProbePlan, ProbeSession, run_plan  # noqa: E402
from audit.rules.checks import tst  # noqa: E402
from audit.rules.registry import REGISTRY  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

TST_CHECKS = ("TST-01", "TST-02", "TST-03", "TST-04", "TST-05")

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "tst-01-no-suite": ("TST-01", "PARTIAL"),
    "tst-04-no-fastpath": ("TST-04", "FAIL"),
    "tst-05-no-coverage": ("TST-05", "FAIL"),
}


class TstFixtureTests(unittest.TestCase):
    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in TST_CHECKS if verdicts[cid] == "FAIL")
                expected_failing = [check] if expected == "FAIL" else []
                self.assertEqual(failing, expected_failing, f"{name}: unexpected TST FAILs {failing}")

    def test_skip_marker_fixture_is_a_nonzero_census(self):
        report = support.run_audit(support.fixture("tst-03-skip-markers"))
        verdicts = support.verdicts(report)
        self.assertEqual(verdicts["TST-03"], "PASS")

        check = next(c for c in report["checks"] if c["id"] == "TST-03")
        self.assertEqual(check["data"]["kind"], "counter")
        self.assertEqual(check["data"]["value"], 3, f"census did not count the markers: {check['data']}")


class TstInlineTests(unittest.TestCase):
    def _scan(self, files: dict[str, str], *, extra_args: tuple[str, ...] = ()) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.run_audit(root, extra_args=extra_args)

    def test_suite_without_a_verb_is_partial(self):
        report = self._scan({"test/app.test.ts": "import { it } from 'vitest';\n"})
        self.assertEqual(support.verdicts(report)["TST-01"], "PARTIAL")

    def test_no_verb_and_no_suite_in_a_known_ecosystem_is_fail(self):
        report = self._scan({"package.json": json.dumps({"scripts": {"lint": "eslint ."}})})
        self.assertEqual(support.verdicts(report)["TST-01"], "FAIL")

    def test_unrecognised_repository_is_unknown_not_fail(self):
        report = self._scan({"notes.txt": "nothing executable here\n"})
        self.assertEqual(support.verdicts(report)["TST-01"], "UNKNOWN")

    def test_fully_tooled_repository_passes_the_artifact_checks(self):
        report = self._scan(
            {
                "package.json": json.dumps({"scripts": {"test": "vitest run --coverage"}}),
                "test/app.test.ts": "import { expect, it } from 'vitest';\nit('adds', () => expect(1 + 1).toBe(2));\n",
                "README.md": "# x\n\n```bash\nnpx vitest run test/app.test.ts\n```\n",
            }
        )
        verdicts = support.verdicts(report)
        for check in ("TST-01", "TST-03", "TST-04", "TST-05"):
            self.assertEqual(verdicts[check], "PASS", check)

    def test_coverage_config_file_is_pass(self):
        report = self._scan({".coveragerc": "[run]\nbranch = true\n"})
        self.assertEqual(support.verdicts(report)["TST-05"], "PASS")

    def test_fastpath_is_unknown_without_a_suite(self):
        report = self._scan({"README.md": "# x\n\n```bash\nnpm test -- foo\n```\n"})
        self.assertEqual(support.verdicts(report)["TST-04"], "UNKNOWN")

    def test_unittest_single_test_form_is_a_fast_path(self):
        for command in (
            "python3 -m unittest tests.test_cmd_pack -k verbs",
            "python -m unittest tests.test_cmd_pack -k verbs",
        ):
            with self.subTest(command=command):
                report = self._scan(
                    {
                        "tests/test_cmd_pack.py": "import unittest\n",
                        "AGENTS.md": f"# x\n\n```bash\n{command}   # one test\n```\n",
                    }
                )
                self.assertEqual(support.verdicts(report)["TST-04"], "PASS")

    def test_vitest_name_filter_is_a_fast_path(self):
        for command in ("npx vitest run -t '<test name>'", "vitest --testNamePattern adds"):
            with self.subTest(command=command):
                report = self._scan(
                    {
                        "test/app.test.ts": "import { it } from 'vitest';\n",
                        "AGENTS.md": f"# x\n\n```bash\n{command}\n```\n",
                    }
                )
                self.assertEqual(support.verdicts(report)["TST-04"], "PASS")

    def test_a_jest_run_narrowed_by_a_test_file_path_is_a_fast_path(self):
        # Issue #50: a path-only run is the documented form when the test verb carries a coverage floor.
        for command in (
            "npx jest src/path/to/file.spec.ts",
            "jest src/app.test.tsx --coverage=false",
            "npx react-scripts test --watchAll=false src/path/to/file.test.tsx",
        ):
            with self.subTest(command=command):
                report = self._scan(
                    {
                        "src/app.test.tsx": "it('adds', () => {});\n",
                        "AGENTS.md": f"# x\n\n```bash\n{command}\n```\n",
                    }
                )
                self.assertEqual(support.verdicts(report)["TST-04"], "PASS")

    def test_a_jest_or_react_scripts_run_without_a_test_file_path_is_not_a_fast_path(self):
        for command in ("npx jest --coverage", "npx react-scripts test --watchAll=false", "jest src/"):
            with self.subTest(command=command):
                report = self._scan(
                    {
                        "src/app.test.tsx": "it('adds', () => {});\n",
                        "AGENTS.md": f"# x\n\n```bash\n{command}\n```\n",
                    }
                )
                self.assertEqual(support.verdicts(report)["TST-04"], "FAIL")

    def test_a_subset_run_in_an_inline_code_span_is_a_fast_path(self):
        # Issue #123: the instruction file names the targeted run in prose, not in a fenced block.
        report = self._scan(
            {
                "src/app.test.ts": "it('adds', () => {});\n",
                "AGENTS.md": "# x\n\n4. Add tests; run `npm test` (targeted: `npm test -- path/to/__tests__`).\n",
            }
        )
        check = [c for c in report["checks"] if c["id"] == "TST-04"][0]
        self.assertEqual(
            (check["verdict"], check["summary"]),
            (
                "PASS",
                "fast path documented in an inline code span: AGENTS.md:3 `npm test -- path/to/__tests__` "
                "(scope: AGENTS.md)",
            ),
        )

    def test_a_fenced_fast_path_is_cited_before_an_inline_one(self):
        report = self._scan(
            {
                "src/app.test.ts": "it('adds', () => {});\n",
                "README.md": "# x\n\nRun `npm test -- one`.\n",
                "AGENTS.md": "# x\n\n```bash\nnpm test -- two\n```\n",
            }
        )
        summary = [c for c in report["checks"] if c["id"] == "TST-04"][0]["summary"]
        self.assertTrue(summary.startswith("fast path documented: AGENTS.md:4 `npm test -- two`"), summary)

    def test_an_inline_full_suite_run_or_a_span_inside_a_fence_is_not_a_fast_path(self):
        report = self._scan(
            {
                "src/app.test.ts": "it('adds', () => {});\n",
                "AGENTS.md": "# x\n\nRun `npm test`.\n\n```text\nsee `npm test -- foo`\n```\n",
            }
        )
        check = [c for c in report["checks"] if c["id"] == "TST-04"][0]
        self.assertEqual(
            (check["verdict"], check["summary"]),
            (
                "FAIL",
                "no single-test/subset invocation in fenced shell blocks or inline code spans (scope: AGENTS.md)",
            ),
        )

    def test_vitest_full_run_is_not_a_fast_path(self):
        report = self._scan(
            {
                "test/app.test.ts": "import { it } from 'vitest';\n",
                "AGENTS.md": "# x\n\n```bash\nnpx vitest run\n```\n",
            }
        )
        self.assertEqual(support.verdicts(report)["TST-04"], "FAIL")

    def test_unittest_discover_alone_is_not_a_fast_path(self):
        report = self._scan(
            {
                "tests/test_cmd_pack.py": "import unittest\n",
                "AGENTS.md": "# x\n\n```bash\npython3 -m unittest discover -s tests\n```\n",
            }
        )
        self.assertEqual(support.verdicts(report)["TST-04"], "FAIL")

    def test_probe_is_refused_and_recorded_by_default(self):
        report = self._scan({"package.json": json.dumps({"scripts": {"test": "vitest run"}})})
        self.assertEqual(support.verdicts(report)["TST-02"], "UNKNOWN")

        probes = [p for p in report["probes"] if p["verb"] == "test"]
        self.assertTrue(probes, "the refused test probe is not recorded")
        self.assertIsNotNone(probes[0]["refused_reason"])
        self.assertIsNone(probes[0]["exit_code"])

    def test_permitted_probe_runs_a_safe_command_and_passes(self):
        report = self._scan(
            {"package.json": json.dumps({"scripts": {"test": 'python3 -c "pass"'}})},
            extra_args=("--run-gates", "--allow-probe", "test"),
        )
        self.assertEqual(support.verdicts(report)["TST-02"], "PASS")

        probes = [p for p in report["probes"] if p["verb"] == "test"]
        self.assertTrue(probes)
        self.assertEqual(probes[0]["exit_code"], 0)
        self.assertIsNone(probes[0]["refused_reason"])


#: A command name no machine has on its PATH; only the target's own node_modules/.bin provides it.
_LOCAL_BIN = "agentic-audit-fake-suite"


def _write_local_bin(root: Path, rel_dir: str, exit_code: int) -> None:
    script = support.write(root, f"{rel_dir}/{_LOCAL_BIN}", f"#!/bin/sh\nexit {exit_code}\n")
    script.chmod(0o755)


class Tst02RunnerPathTests(unittest.TestCase):
    """Issue #121: a package.json script body runs with node_modules/.bin on PATH, as `npm run` sets it."""

    def test_runner_path_lists_each_node_modules_bin_nearest_first(self):
        self.assertEqual(tst._runner_path("package.json"), ("node_modules/.bin",))
        self.assertEqual(
            tst._runner_path("packages/app/package.json"),
            ("packages/app/node_modules/.bin", "packages/node_modules/.bin", "node_modules/.bin"),
        )
        self.assertEqual(tst._runner_path("Makefile"), ())

    def test_run_plan_puts_the_prepended_directory_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_local_bin(root, "node_modules/.bin", 0)
            bare = run_plan(ProbePlan("test", [_LOCAL_BIN]), allow=("test",), cwd=root)
            self.assertIsNotNone(bare.refused_reason, "the bare command must not resolve without the prepend")
            found = run_plan(
                ProbePlan("test", [_LOCAL_BIN], path_prepend=("node_modules/.bin",)), allow=("test",), cwd=root
            )
            self.assertIsNone(found.refused_reason)
            self.assertEqual(found.exit_code, 0)

    def test_permitted_probe_resolves_a_package_bin_in_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "package.json", json.dumps({"scripts": {"test": f"{_LOCAL_BIN} --ci"}}))
            _write_local_bin(root, "node_modules/.bin", 3)
            inventory = build_inventory(root)
            spec = next(s for s in REGISTRY if s.id == "TST-02")
            session = ProbeSession(cwd=root, allow=("test",), enabled=True)
            outcome = tst.check_tst02(
                spec=spec,
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=session,
            )
            self.assertEqual(outcome.verdict.value, "FAIL", outcome.summary)
            self.assertEqual(session.results[0].exit_code, 3)
            self.assertNotIn(str(root), os.environ.get("PATH", ""), "the probe must not change the caller's PATH")


if __name__ == "__main__":
    unittest.main()
