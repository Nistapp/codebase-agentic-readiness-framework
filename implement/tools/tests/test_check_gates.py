# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`check_gates.py` on scratch git repositories: one test per pattern of a weakened gate (B-03) and of an unapproved
dependency (B-11), the owner's preferences that approve or accept one, a clean diff that passes, and the usage
errors. Standard library only, in process.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping, Sequence

import _implement_paths  # noqa: F401  (puts the tools folders on sys.path)
import _common
import _git
import check_gates
import progress

REPORT = _implement_paths.AUDIT / "schema" / "examples" / "example-service.audit-report.20261010T094207Z.json"

BASE_FILES: Mapping[str, str] = {
    "Makefile": "check: lint test\n\nlint:\n\truff check .\n\tmypy src\n\ntest:\n\tpytest\n",
    "tests/test_app.py": "def test_one():\n    assert 1\n",
    "tests/test_other.py": "def test_two():\n    assert 2\n",
    "src/app.py": "def run():\n    return 1\n",
    "pyproject.toml": '[project]\nname = "app"\ndependencies = ["requests>=2"]\n\n'
    "[tool.coverage.report]\nfail_under = 90\n",
    "package.json": json.dumps(
        {"scripts": {"test": "jest", "lint": "eslint ."}, "devDependencies": {"jest": "^29"}}, indent=2
    )
    + "\n",
    ".github/workflows/ci.yml": "jobs:\n  check:\n    steps:\n      - run: make check\n      - run: npx eslint .\n",
    "quality-baseline.json": json.dumps({"ruff": 3, "mypy": 5}) + "\n",
}


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(check_gates.INFO, check_gates.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


class GateCase(unittest.TestCase):
    """A repository with one base commit; each test commits a theme on top and runs the tool."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        _git.make_repo(self.repo, (), commit=False)
        self.write(BASE_FILES)
        _git.run_git(self.repo, "add", "-A")
        _git.run_git(self.repo, "commit", "-q", "-m", "base")
        self.base = _git.run_git(self.repo, "rev-parse", "HEAD")

    def write(self, files: Mapping[str, str | None]) -> None:
        for name, text in files.items():
            path = self.repo / name
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def theme(self, files: Mapping[str, str | None]) -> None:
        self.write(files)
        _git.run_git(self.repo, "add", "-A")
        _git.run_git(self.repo, "commit", "-q", "-m", "theme")

    def run_tool(self, *extra: str) -> tuple[int, dict[str, Any], str]:
        return call([str(self.repo), "--base", self.base, *extra])

    def findings(self, *extra: str) -> list[str]:
        code, envelope, _ = self.run_tool(*extra)
        self.assertEqual(code, 2, envelope)
        self.assertFalse(envelope["ok"])
        errors: list[str] = envelope["data"]["errors"]
        return errors

    def assert_one(self, kind: str, path: str, *extra: str) -> str:
        errors = self.findings(*extra)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith(f"{kind}: {path}: "), errors)
        return errors[0]

    def clean(self, *extra: str) -> dict[str, Any]:
        code, envelope, err = self.run_tool(*extra)
        self.assertEqual(code, 0, (envelope, err))
        data: dict[str, Any] = envelope["data"]
        self.assertEqual(data["status"], "clean")
        return data

    def state_with(self, preferences: Mapping[str, str]) -> Path:
        """An implement state, made by `progress.py init`, with each preference set by the owner."""
        workspace = self.root / "workspace"
        workspace.mkdir(exist_ok=True)
        report = workspace / REPORT.name
        document = json.loads(REPORT.read_text(encoding="utf-8"))
        document["provenance"]["target"]["git_sha"] = self.base
        report.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        tail = ["--workspace", str(workspace), "--phase", "IRtest", "--date", "2026-11-20"]
        for argv in [
            ["init", "--report", str(report), "--target", str(self.repo), "--date", "2026-11-20"],
            *(["pref", "set", key, value, "--reason", "owner choice", "--by", "owner", *tail] for key, value in
              preferences.items()),
        ]:  # fmt: skip
            out = io.StringIO()
            code = _common.run_tool(progress.INFO, progress.handler, argv, stdout=out, stderr=io.StringIO())
            self.assertEqual(code, 0, out.getvalue())
        _, path = progress.find_state(workspace, None)
        return path


class CleanTests(GateCase):
    def test_a_theme_that_adds_a_test_and_raises_a_floor_is_clean(self) -> None:
        self.theme(
            {
                "tests/test_new.py": "def test_three():\n    assert 3\n",
                "src/app.py": "def run():\n    return 2\n",
                "pyproject.toml": BASE_FILES["pyproject.toml"].replace("90", "95"),
                "quality-baseline.json": json.dumps({"ruff": 1, "mypy": 5}) + "\n",
            }
        )
        data = self.clean()
        self.assertEqual(data["changed_count"], 4)
        self.assertEqual(data["accepted"], [])
        self.assertEqual(data["base"], self.base)

    def test_an_empty_theme_is_clean_and_warns_without_a_state(self) -> None:
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["changed_count"], 0)
        self.assertTrue(any("no --state" in warning for warning in envelope["warnings"]))

    def test_a_renamed_test_file_is_not_a_deleted_one(self) -> None:
        self.theme({"tests/test_other.py": None, "tests/test_moved.py": BASE_FILES["tests/test_other.py"]})
        self.clean()

    def test_a_gate_command_moved_to_a_script_is_kept(self) -> None:
        self.theme(
            {
                "Makefile": "check: lint test\n\nlint:\n\t./scripts/lint.sh\n\ntest:\n\tpytest\n",
                "scripts/lint.sh": "#!/bin/sh\nruff check .\nmypy src\n",
            }
        )
        self.clean()

    def test_the_tool_reads_and_never_writes(self) -> None:
        self.theme({"tests/test_other.py": None})
        status = _git.run_git(self.repo, "status", "--porcelain")
        head = _git.run_git(self.repo, "rev-parse", "HEAD")
        self.findings()
        self.assertEqual(_git.run_git(self.repo, "status", "--porcelain"), status)
        self.assertEqual(_git.run_git(self.repo, "rev-parse", "HEAD"), head)


class TestFileTests(GateCase):
    def test_a_deleted_test_file_is_a_finding(self) -> None:
        self.theme({"tests/test_other.py": None})
        line = self.assert_one("B-03 test-deleted", "tests/test_other.py")
        self.assertIn("deleted", line)

    def test_a_test_renamed_to_a_non_test_path_is_a_finding(self) -> None:
        self.theme({"tests/test_other.py": None, "src/other.py": BASE_FILES["tests/test_other.py"]})
        line = self.assert_one("B-03 test-deleted", "tests/test_other.py")
        self.assertIn("renamed to src/other.py", line)

    def test_an_added_skip_marker_is_a_finding_from_the_engine_table(self) -> None:
        self.theme({"tests/test_app.py": "import unittest\n\n@unittest.skip('later')\ndef test_one():\n    assert 1\n"})
        line = self.assert_one("B-03 skip-added", "tests/test_app.py")
        self.assertIn("0 -> 1", line)

    def test_a_javascript_skip_in_a_new_test_file_is_a_finding(self) -> None:
        self.theme({"web/app.test.js": "it.skip('works', () => {});\nxit('later', () => {});\n"})
        line = self.assert_one("B-03 skip-added", "web/app.test.js")
        self.assertIn("0 -> 2", line)

    def test_an_added_inline_suppression_is_a_finding(self) -> None:
        self.theme({"src/app.py": "def run():  # type: ignore\n    return 1\n"})
        line = self.assert_one("B-03 suppression-added", "src/app.py")
        self.assertIn("type: ignore", line)

    def test_a_suppression_in_markdown_is_not_counted(self) -> None:
        self.theme({"docs/review.md": "- [ ] No `@ts-ignore` introduced\n"})
        self.clean()


class NumberTests(GateCase):
    def test_a_lowered_coverage_floor_is_a_finding(self) -> None:
        self.theme({"pyproject.toml": BASE_FILES["pyproject.toml"].replace("90", "80")})
        line = self.assert_one("B-03 floor-lowered", "pyproject.toml")
        self.assertIn("fail-under 90 -> 80", line)

    def test_a_floor_moved_to_another_file_is_compared(self) -> None:
        self.theme(
            {
                "pyproject.toml": '[project]\nname = "app"\ndependencies = ["requests>=2"]\n',
                ".coveragerc": "[report]\nfail_under = 85\n",
            }
        )
        self.assert_one("B-03 floor-lowered", ".coveragerc")

    def test_a_removed_floor_is_a_finding(self) -> None:
        self.theme({"pyproject.toml": '[project]\nname = "app"\ndependencies = ["requests>=2"]\n'})
        self.assert_one("B-03 floor-removed", "pyproject.toml")

    def test_a_lowered_jest_threshold_is_a_finding(self) -> None:
        self.theme({"jest.config.js": "module.exports = { coverageThreshold: { global: { lines: 80 } } };\n"})
        self.base = _git.run_git(self.repo, "rev-parse", "HEAD")
        self.theme({"jest.config.js": "module.exports = { coverageThreshold: { global: { lines: 70 } } };\n"})
        line = self.assert_one("B-03 floor-lowered", "jest.config.js")
        self.assertIn("coverage threshold lines 80 -> 70", line)

    def test_a_raised_warning_limit_is_a_finding(self) -> None:
        self.theme({"package.json": BASE_FILES["package.json"].replace("eslint .", "eslint . --max-warnings 0")})
        self.base = _git.run_git(self.repo, "rev-parse", "HEAD")
        self.theme({"package.json": BASE_FILES["package.json"].replace("eslint .", "eslint . --max-warnings 10")})
        line = self.assert_one("B-03 limit-raised", "package.json")
        self.assertIn("--max-warnings 0 -> 10", line)

    def test_a_raised_count_in_a_baseline_file_is_a_finding(self) -> None:
        self.theme({"quality-baseline.json": json.dumps({"ruff": 4, "mypy": 5}) + "\n"})
        line = self.assert_one("B-03 limit-raised", "quality-baseline.json")
        self.assertIn("/ruff 3 -> 4", line)


class GateCommandTests(GateCase):
    def test_a_gate_command_gone_from_every_gate_file_is_a_finding(self) -> None:
        self.theme({"Makefile": "check: lint test\n\nlint:\n\truff check .\n\ntest:\n\tpytest\n"})
        line = self.assert_one("B-03 gate-removed", "Makefile")
        self.assertIn("`mypy`", line)

    def test_a_removed_make_target_is_a_finding(self) -> None:
        self.theme({"Makefile": "check: lint\n\nlint:\n\truff check .\n\tmypy src\n\tpytest\n"})
        line = self.assert_one("B-03 gate-removed", "Makefile")
        self.assertIn("`test`", line)

    def test_a_removed_package_script_is_a_finding(self) -> None:
        document = json.loads(BASE_FILES["package.json"])
        document["scripts"] = {"test": "jest", "prelint": "eslint ."}
        self.theme({"package.json": json.dumps(document, indent=2) + "\n"})
        line = self.assert_one("B-03 gate-removed", "package.json")
        self.assertIn("`lint`", line)

    def test_a_swallowed_gate_failure_is_a_finding(self) -> None:
        self.theme({"Makefile": BASE_FILES["Makefile"].replace("\tpytest\n", "\tpytest || true\n")})
        line = self.assert_one("B-03 gate-loosened", "Makefile")
        self.assertIn("0 -> 1", line)


class DependencyTests(GateCase):
    def test_an_added_python_dependency_is_a_finding(self) -> None:
        self.theme(
            {"pyproject.toml": BASE_FILES["pyproject.toml"].replace('"requests>=2"', '"requests>=2", "Left_Pad"')}
        )
        line = self.assert_one("B-11 dependency-added", "pyproject.toml")
        self.assertIn("left-pad (python)", line)

    def test_an_added_npm_dependency_is_a_finding(self) -> None:
        self.theme(
            {"package.json": BASE_FILES["package.json"].replace('"jest": "^29"', '"jest": "^29", "husky": "^9"')}
        )
        self.assert_one("B-11 dependency-added", "package.json")

    def test_other_manifests_are_read(self) -> None:
        manifests = {
            "requirements-dev.txt": "black==24.1\n# a comment\n-r base.txt\n",
            "go.mod": "module x\n\nrequire (\n\tgithub.com/a/b v1.0.0\n)\nrequire github.com/c/d v2.0.0\n",
            "Cargo.toml": "[package]\nname = 'x'\n[dependencies]\nserde = '1'\n[dev-dependencies]\ninsta = '1'\n",
            "Gemfile": "source 'https://rubygems.org'\ngem 'rails'\n",
            "composer.json": json.dumps({"require": {"php": ">=8", "ext-json": "*", "monolog/monolog": "^3"}}),
            "Pipfile": "[packages]\nflask = '*'\n[dev-packages]\npytest = '*'\n",
        }
        self.theme(manifests)
        names = {line.split(": ", 2)[2].split(" ")[0] for line in self.findings()}
        expected = {"black", "github-com/a/b", "github-com/c/d", "serde", "insta", "rails", "monolog/monolog"}
        self.assertEqual(names, expected | {"flask", "pytest"})

    def test_a_lockfile_change_with_no_approved_addition_is_a_finding(self) -> None:
        self.theme({"uv.lock": "version = 1\n"})
        self.assert_one("B-11 lockfile-changed", "uv.lock")

    def test_an_approved_dependency_and_its_lockfile_pass(self) -> None:
        state = self.state_with({check_gates.APPROVED_KEY: "left-pad, husky"})
        self.theme(
            {
                "pyproject.toml": BASE_FILES["pyproject.toml"].replace('"requests>=2"', '"requests>=2", "left_pad"'),
                "uv.lock": "version = 1\n",
            }
        )
        data = self.clean("--state", str(state))
        self.assertEqual(data["approved_added"], ["left-pad"])

    def test_an_unparsable_manifest_is_a_warning(self) -> None:
        self.theme({"package.json": "{ not json"})
        code, envelope, _ = self.run_tool()
        self.assertEqual(code, 2, envelope)
        self.assertNotIn("dependency-added", json.dumps(envelope))


class PreferenceTests(GateCase):
    def test_a_gate_change_the_owner_accepted_is_listed_and_does_not_stop(self) -> None:
        state = self.state_with({check_gates.ACCEPTED_KEY: "tests/test_other.py"})
        self.theme({"tests/test_other.py": None})
        data = self.clean("--state", str(state))
        self.assertEqual([item["kind"] for item in data["accepted"]], ["test-deleted"])

    def test_an_accepted_glob_never_approves_a_dependency(self) -> None:
        state = self.state_with({check_gates.ACCEPTED_KEY: "*"})
        self.theme(
            {"package.json": BASE_FILES["package.json"].replace('"jest": "^29"', '"jest": "^29", "husky": "^9"')}
        )
        self.assert_one("B-11 dependency-added", "package.json", "--state", str(state))


class UsageTests(GateCase):
    def test_a_base_that_is_not_a_commit_is_a_usage_error(self) -> None:
        code, envelope, _ = call([str(self.repo), "--base", "f" * 40])
        self.assertEqual(code, 1, envelope)
        self.assertIn("--base", envelope["data"]["error"])

    def test_a_missing_state_is_a_usage_error(self) -> None:
        code, envelope, _ = self.run_tool("--state", str(self.root / "missing.json"))
        self.assertEqual(code, 1, envelope)

    def test_describe_says_it_writes_nothing(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["writes"], "nothing")
        self.assertIs(envelope["data"]["writes_inside_target"], False)


if __name__ == "__main__":
    unittest.main()
