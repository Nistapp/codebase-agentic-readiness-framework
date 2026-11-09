# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`AGT-09` compares the instruction file with the branches the declared branch rules protect.

A branch a rule protects by its literal name, and that the instruction file does not name, reads `PARTIAL`: an
agent that reads the file does not learn that the branch is protected. `~DEFAULT_BRANCH`, `~ALL` and globs name no
branch, so they are skipped. The rules come from `declared_branch_rules`, the list `HYG-11` and `TOOL-07` read.
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

from audit.rules.checks.agt import _names_branch  # noqa: E402
from audit.rules.checks.agt import check_agt09 as CHECK  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "AGT-09"

BOTH_HALVES = (
    "# AGENTS.md\n\n## Branches\n\n- `main` is the release branch and `dev` is the integration branch.\n"
    "- Never push a tag or publish a release.\n"
)


def ruleset(*refs: str) -> str:
    return json.dumps(
        {
            "name": "protection",
            "target": "branch",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": list(refs), "exclude": []}},
            "rules": [{"type": "deletion"}],
        }
    )


class Agt09RulesetBranchesTests(unittest.TestCase):
    def check(self, files: dict[str, str]) -> dict:
        """Run the check in-process (so coverage traces it) on a repository built from ``files``."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            inventory = build_inventory(root)
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

    def test_no_declared_rules_keeps_the_text_rule(self):
        self.assertEqual(self.check({"AGENTS.md": BOTH_HALVES})["verdict"], "PASS")

    def test_every_protected_branch_named_passes(self):
        check = self.check(
            {
                "AGENTS.md": BOTH_HALVES,
                ".github/rulesets/main.json": ruleset("refs/heads/main"),
                ".github/rulesets/dev.json": ruleset("refs/heads/dev"),
            }
        )
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["findings"], [])

    def test_an_unnamed_protected_branch_is_partial(self):
        check = self.check(
            {
                "AGENTS.md": BOTH_HALVES,
                ".github/rulesets/branches.json": ruleset("refs/heads/main", "refs/heads/staging"),
            }
        )
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("staging is protected by the declared rules", check["summary"])
        self.assertIn(".github/rulesets/branches.json", check["summary"])
        finding = check["findings"][0]
        self.assertIn("Name staging", finding["remediation"])
        self.assertIn(".github/rulesets/branches.json", [item["path"] for item in finding["evidence"]])

    def test_two_unnamed_branches_are_listed(self):
        check = self.check(
            {
                "AGENTS.md": BOTH_HALVES,
                ".github/rulesets/branches.json": ruleset("refs/heads/qa", "refs/heads/staging"),
            }
        )
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("qa, staging are protected", check["summary"])

    def test_keywords_and_globs_are_skipped(self):
        check = self.check(
            {
                "AGENTS.md": BOTH_HALVES,
                ".github/rulesets/branches.json": ruleset("~DEFAULT_BRANCH", "~ALL", "refs/heads/release/*"),
            }
        )
        self.assertEqual(check["verdict"], "PASS")

    def test_a_disabled_ruleset_protects_nothing(self):
        disabled = json.loads(ruleset("refs/heads/staging"))
        disabled["enforcement"] = "disabled"
        check = self.check({"AGENTS.md": BOTH_HALVES, ".github/rulesets/staging.json": json.dumps(disabled)})
        self.assertEqual(check["verdict"], "PASS")

    def test_settings_app_and_terraform_rules_count(self):
        settings = "branches:\n  - name: main\n  - name: staging\n"
        self.assertEqual(self.check({"AGENTS.md": BOTH_HALVES, ".github/settings.yml": settings})["verdict"], "PARTIAL")
        terraform = 'resource "gitlab_branch_protection" "qa" {\n  project = "1"\n  branch  = "qa"\n}\n'
        check = self.check({"AGENTS.md": BOTH_HALVES, "infra/protection.tf": terraform})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("qa is protected", check["summary"])

    def test_one_half_missing_also_reports_the_unnamed_branch(self):
        text = "# AGENTS.md\n\n- `main` is the only branch.\n"
        check = self.check({"AGENTS.md": text, ".github/rulesets/b.json": ruleset("refs/heads/main", "refs/heads/qa")})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("nothing says whether an agent may tag or release", check["summary"])
        self.assertIn("; qa is protected", check["summary"])

    def test_neither_half_stays_fail(self):
        text = "# AGENTS.md\n\nThis file governs agents.\n"
        check = self.check({"AGENTS.md": text, ".github/rulesets/b.json": ruleset("refs/heads/qa")})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("qa is protected", check["summary"])

    def test_no_instruction_file_stays_unknown(self):
        check = self.check({".github/rulesets/b.json": ruleset("refs/heads/qa")})
        self.assertEqual(check["verdict"], "UNKNOWN")

    def test_a_branch_is_named_only_as_a_whole_name(self):
        self.assertTrue(_names_branch("work on `dev`.", "dev"))
        self.assertTrue(_names_branch("dev is protected", "dev"))
        self.assertFalse(_names_branch("ask devops first", "dev"))
        self.assertFalse(_names_branch("branch feat/dev-x", "dev"))
        self.assertFalse(_names_branch("see release/dev", "dev"))
        self.assertTrue(_names_branch("the release/1.x branch", "release/1.x"))


if __name__ == "__main__":
    unittest.main()
