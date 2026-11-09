# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`HYG-11` reads the branch rules a repository declares as code, and the source-branch check a two-branch model needs.

A ruleset file, the Settings app's `branches:` or a Terraform protection resource declares the rules. A page that
describes them only records them. When the rules protect an integration branch and another branch, a workflow must
read the pull request's source branch, because a ruleset cannot restrict it.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks._common import declared_branch_rules  # noqa: E402
from audit.rules.checks.hyg import check_hyg11 as CHECK  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "HYG-11"

WORKFLOW = (
    "name: CI\non: [pull_request]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make check\n"
)

SOURCE_CHECK = (
    "name: PR source branch\non:\n  pull_request:\n    branches: [main]\njobs:\n  check:\n    runs-on: ubuntu-latest\n"
    "    steps:\n      - env:\n          HEAD_REF: ${{ github.head_ref }}\n"
    '        run: test "$HEAD_REF" = dev\n'
)


def ruleset(*refs: str, target: str = "branch", enforcement: str = "active") -> str:
    return json.dumps(
        {
            "name": "protection",
            "target": target,
            "enforcement": enforcement,
            "conditions": {"ref_name": {"include": list(refs), "exclude": []}},
            "rules": [{"type": "deletion"}, {"type": "pull_request"}],
        }
    )


class Hyg11BranchRulesTests(unittest.TestCase):
    def build(self, files: dict[str, str], tmp: str):
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        return build_inventory(root)

    def check(self, files: dict[str, str]) -> dict:
        """Run the check in-process (so coverage traces it) on a repository built from ``files``."""
        with tempfile.TemporaryDirectory() as tmp:
            inventory = self.build(files, tmp)
            outcome = CHECK(
                spec=REGISTRY_BY_ID[CHECK_ID],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        return {
            "verdict": outcome.verdict.value,
            "summary": outcome.summary,
            "findings": [finding.to_dict() for finding in outcome.findings],
        }

    def rules(self, files: dict[str, str]):
        with tempfile.TemporaryDirectory() as tmp:
            return declared_branch_rules(self.build(files, tmp))

    # -- declared as code ---------------------------------------------------------------------------------------

    def test_one_ruleset_for_the_default_branch_passes(self):
        check = self.check(
            {".github/workflows/ci.yml": WORKFLOW, ".github/rulesets/main.json": ruleset("refs/heads/main")}
        )
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn(".github/rulesets/main.json", check["summary"])

    def test_two_branch_model_with_a_source_branch_check_passes(self):
        check = self.check(
            {
                ".github/workflows/ci.yml": WORKFLOW,
                ".github/workflows/pr-source-branch.yml": SOURCE_CHECK,
                ".github/rulesets/dev.json": ruleset("refs/heads/dev"),
                ".github/rulesets/main.json": ruleset("refs/heads/main"),
            }
        )
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("source-branch check at .github/workflows/pr-source-branch.yml:", check["summary"])

    def test_two_branch_model_without_a_source_branch_check_is_partial(self):
        check = self.check(
            {
                ".github/workflows/ci.yml": WORKFLOW,
                ".github/rulesets/dev.json": ruleset("refs/heads/dev"),
                ".github/rulesets/main.json": ruleset("~DEFAULT_BRANCH"),
            }
        )
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("no CI job checks a pull request's source branch", check["summary"])
        self.assertEqual(len(check["findings"]), 1)

    def test_a_concurrency_group_or_checkout_ref_is_not_a_source_branch_check(self):
        workflow = (
            "on: [pull_request]\nconcurrency:\n  group: ci-${{ github.head_ref || github.run_id }}\njobs:\n  b:\n"
            "    steps:\n      - uses: actions/checkout@v4\n        with:\n          ref: ${{ github.head_ref }}\n"
            "      # echo ${{ github.head_ref }}\n"
        )
        check = self.check(
            {
                ".github/workflows/ci.yml": workflow,
                ".github/rulesets/both.json": ruleset("refs/heads/develop", "refs/heads/main"),
            }
        )
        self.assertEqual(check["verdict"], "PARTIAL")

    def test_gitlab_source_branch_variable_counts(self):
        gitlab = (
            'check-source-branch:\n  rules:\n    - if: $CI_MERGE_REQUEST_TARGET_BRANCH_NAME == "main"\n'
            '  script:\n    - test "$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME" = dev\n'
        )
        terraform = (
            'resource "gitlab_branch_protection" "dev" {\n  project = "1"\n  branch  = "dev"\n}\n'
            'resource "gitlab_branch_protection" "main" {\n  project = "1"\n  branch  = "main"\n}\n'
        )
        check = self.check({".gitlab-ci.yml": gitlab, "infra/protection.tf": terraform})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("source-branch check at .gitlab-ci.yml:5", check["summary"])

    def test_protected_release_branches_without_an_integration_branch_need_no_source_check(self):
        check = self.check(
            {
                ".github/workflows/ci.yml": WORKFLOW,
                ".github/rulesets/main.json": ruleset("refs/heads/main", "refs/heads/release/*"),
            }
        )
        self.assertEqual(check["verdict"], "PASS")

    def test_settings_app_branches_declare_rules(self):
        settings = (
            "repository:\n  name: x\n# protected branches\nbranches:\n  - name: main\n    protection:\n"
            "      enforce_admins: true\n  - name: dev\nlabels:\n  - name: bug\n"
        )
        rules = self.rules({".github/settings.yml": settings})
        self.assertEqual(rules.sources, (".github/settings.yml",))
        self.assertEqual(rules.branches, ("dev", "main"))

    def test_settings_file_without_branches_declares_nothing(self):
        rules = self.rules({".github/settings.yml": "repository:\n  name: x\nlabels:\n  - name: bug\n"})
        self.assertEqual(rules.sources, ())

    def test_terraform_github_ruleset_resource_names_its_branches(self):
        terraform = (
            'resource "github_repository_ruleset" "main" {\n  target = "branch"\n  conditions {\n    ref_name {\n'
            '      include = ["~DEFAULT_BRANCH", "refs/heads/dev"]\n      exclude = []\n    }\n  }\n}\n'
        )
        rules = self.rules({"main.tf": terraform})
        self.assertEqual(rules.sources, ("main.tf",))
        self.assertEqual(rules.branches, ("dev", "~DEFAULT_BRANCH"))
        self.assertEqual(rules.literal_branches, ("dev",))

    def test_disabled_tag_and_conditionless_rulesets_protect_no_branch(self):
        rules = self.rules(
            {
                ".github/rulesets/off.json": ruleset("refs/heads/main", enforcement="disabled"),
                ".github/rulesets/tags.json": ruleset("refs/tags/v*", target="tag"),
                ".github/rulesets/bare.json": json.dumps({"name": "x", "rules": []}),
            }
        )
        self.assertEqual(rules, type(rules)())

    def test_other_protection_file_still_counts_as_configuration(self):
        check = self.check({".github/workflows/ci.yml": WORKFLOW, ".github/branch-protection.yml": "main: {}\n"})
        self.assertEqual(check["verdict"], "PASS")

    # -- recorded, unreadable, absent ---------------------------------------------------------------------------

    def test_a_page_only_records_the_rules(self):
        check = self.check({".github/workflows/ci.yml": WORKFLOW, "docs/branch-protection.md": "# Rules\n"})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("recorded at docs/branch-protection.md, not declared as code", check["summary"])

    def test_an_unreadable_ruleset_is_unknown(self):
        check = self.check(
            {
                ".github/workflows/ci.yml": WORKFLOW,
                ".github/rulesets/main.json": "{not json",
                "docs/branch-protection.md": "# Rules\n",
            }
        )
        self.assertEqual(check["verdict"], "UNKNOWN")
        self.assertIn(".github/rulesets/main.json cannot be read", check["summary"])

    def test_nothing_declared_with_github_fails(self):
        check = self.check({".github/workflows/ci.yml": WORKFLOW})
        self.assertEqual(check["verdict"], "FAIL")

    def test_nothing_declared_without_a_known_provider_is_unknown(self):
        check = self.check({"Jenkinsfile": "pipeline {}\n"})
        self.assertEqual(check["verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
