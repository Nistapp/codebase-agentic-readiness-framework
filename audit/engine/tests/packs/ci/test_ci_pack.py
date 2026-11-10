# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CI checks against their one-defect fixtures.

Each fixture is a small node project plus a GitHub workflow that isolates one CI defect;
`ci-ok-gh` passes every engine CI check. The inline cases cover the `UNKNOWN` floor (no local verbs), a
non-GitHub PR trigger, the minimal YAML scan reading a block-scalar step, and `CI-05`'s provider and
local-surface rules.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

CI_CHECKS = ("CI-01", "CI-02", "CI-03", "CI-05")

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "ci-01-no-pr-trigger": ("CI-01", "PARTIAL"),
    "ci-02-parity-break": ("CI-02", "FAIL"),
    "ci-03-ci-only-step": ("CI-03", "FAIL"),
    "ci-05-no-workflow-lint": ("CI-05", "FAIL"),
    "ci-05-ci-only-lint": ("CI-05", "PARTIAL"),
}


class CiFixtureTests(unittest.TestCase):
    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in CI_CHECKS if verdicts[cid] == "FAIL")
                expected_failing = [check] if expected == "FAIL" else []
                self.assertEqual(failing, expected_failing, f"{name}: unexpected CI FAILs {failing}")

    def test_positive_fixture_passes_every_ci_check(self):
        report = support.run_audit(support.fixture("ci-ok-gh"))
        verdicts = support.verdicts(report)
        for check in CI_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"ci-ok-gh: {check}")


class CiInlineTests(unittest.TestCase):
    def _scan(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.run_audit(root)

    def test_no_workflow_is_a_fail(self):
        report = self._scan({"package.json": '{"scripts": {"check": "true"}}'})
        self.assertEqual(support.verdicts(report)["CI-01"], "FAIL")

    def test_ci_without_local_verbs_is_unknown_not_pass(self):
        report = self._scan(
            {
                ".github/workflows/ci.yml": "on:\n  pull_request:\njobs:\n  b:\n    steps:\n"
                "      - run: npm run check\n",
            }
        )
        self.assertEqual(support.verdicts(report)["CI-02"], "UNKNOWN")

    def test_gitlab_merge_request_trigger_counts(self):
        report = self._scan(
            {
                ".gitlab-ci.yml": (
                    "test:\n  script:\n    - npm run check\n  rules:\n    - if: $CI_MERGE_REQUEST_IID\n"
                ),
                "package.json": '{"scripts": {"check": "true"}}',
            }
        )
        self.assertEqual(support.verdicts(report)["CI-01"], "PASS")

    def test_block_scalar_step_is_parsed(self):
        report = self._scan(
            {
                ".github/workflows/ci.yml": (
                    "on:\n  pull_request:\njobs:\n  b:\n    steps:\n"
                    "      - run: |\n          npm ci\n          npm run check\n"
                ),
                "package.json": '{"scripts": {"check": "true"}}',
            }
        )
        self.assertEqual(support.verdicts(report)["CI-02"], "PASS")
        self.assertEqual(support.verdicts(report)["CI-03"], "PASS")

    def test_npm_stage_publish_is_a_builtin_not_ci_only(self):
        # npm >= 11.21's staged-publish subcommand (`npm stage publish`), not a missing script
        # named `stage`. Found auditing a freshly scaffolded project: the greenfield template's
        # release workflow runs this and CI-03 flagged `stage` as a CI-only step.
        report = self._scan(
            {
                ".github/workflows/release.yml": (
                    "on:\n  push:\n    branches: [main]\njobs:\n  publish:\n    steps:\n"
                    "      - run: npm stage publish --provenance --access public\n"
                ),
                "package.json": '{"scripts": {"check": "true"}}',
            }
        )
        self.assertEqual(support.verdicts(report)["CI-03"], "PASS")


_GH_WORKFLOW = "on:\n  pull_request:\njobs:\n  b:\n    steps:\n      - run: npm run check\n"
_PACKAGE = '{"scripts": {"check": "true"}}'


class Ci05InlineTests(unittest.TestCase):
    def _ci05(self, files: dict[str, str]) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.verdicts(support.run_audit(root))["CI-05"]

    def test_no_workflow_is_unknown(self):
        self.assertEqual(self._ci05({"package.json": _PACKAGE}), "UNKNOWN")

    def test_jenkins_only_is_unknown(self):
        self.assertEqual(self._ci05({"Jenkinsfile": "pipeline { stages { } }\n", "package.json": _PACKAGE}), "UNKNOWN")

    def test_make_target_running_zizmor_is_a_pass(self):
        files = {
            ".github/workflows/ci.yml": _GH_WORKFLOW,
            "Makefile": "check:\n\ttrue\nworkflow-lint:\n\tuvx zizmor --offline .github\n",
        }
        self.assertEqual(self._ci05(files), "PASS")

    def test_pre_commit_hook_id_is_a_local_linter(self):
        files = {
            ".github/workflows/ci.yml": _GH_WORKFLOW,
            "package.json": _PACKAGE,
            ".pre-commit-config.yaml": "repos:\n  - repo: https://github.com/python-jsonschema/check-jsonschema\n"
            "    rev: 0.39.0\n    hooks:\n      - id: check-github-workflows\n",
        }
        self.assertEqual(self._ci05(files), "PASS")

    def test_husky_hook_is_a_local_linter(self):
        files = {
            ".github/workflows/ci.yml": _GH_WORKFLOW,
            "package.json": _PACKAGE,
            ".husky/pre-commit": "actionlint\n",
        }
        self.assertEqual(self._ci05(files), "PASS")

    def test_gitlab_schema_check_is_a_pass(self):
        files = {
            ".gitlab-ci.yml": "test:\n  script:\n    - npm run check\n",
            "Makefile": "lint-ci:\n\tcheck-jsonschema --builtin-schema vendor.gitlab-ci .gitlab-ci.yml\n",
        }
        self.assertEqual(self._ci05(files), "PASS")

    def test_a_github_linter_does_not_lint_gitlab(self):
        files = {
            ".gitlab-ci.yml": "test:\n  script:\n    - npm run check\n",
            "Makefile": "lint-ci:\n\tactionlint\n",
        }
        self.assertEqual(self._ci05(files), "FAIL")

    def test_a_linter_named_only_in_docs_does_not_count(self):
        files = {
            ".github/workflows/ci.yml": _GH_WORKFLOW,
            "package.json": _PACKAGE,
            "CONTRIBUTING.md": "Run actionlint before you push.\n",
        }
        self.assertEqual(self._ci05(files), "FAIL")

    def test_a_lockfile_or_dependabot_naming_the_linter_does_not_count(self):
        files = {
            ".github/workflows/ci.yml": _GH_WORKFLOW,
            "package.json": _PACKAGE,
            "uv.lock": '[[package]]\nname = "zizmor"\n',
            ".github/dependabot.yml": "updates:\n  - package-ecosystem: pip  # zizmor, actionlint\n",
        }
        self.assertEqual(self._ci05(files), "FAIL")

    def test_one_provider_linted_and_one_not_is_partial(self):
        files = {
            ".github/workflows/ci.yml": _GH_WORKFLOW,
            ".gitlab-ci.yml": "test:\n  script:\n    - npm run check\n",
            "Makefile": "lint-ci:\n\tactionlint\n",
        }
        self.assertEqual(self._ci05(files), "PARTIAL")


if __name__ == "__main__":
    unittest.main()
