# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`TOOL-04` reads CI as well as the local verbs (v0.3.3 C6).

A dependency audit that only a person runs is skipped on the change that matters. CI must run it too: a scanner
command, a runner target whose command runs one, a scanner action, or GitLab's Dependency-Scanning template.
Local and CI ⇒ `PASS`; one of the two ⇒ `PARTIAL`; neither ⇒ `FAIL`. Dependabot and Renovate do not count.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

from audit.rules.checks.tool import check_tool04 as CHECK  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "TOOL-04"
NODE_AUDIT = json.dumps({"name": "x", "scripts": {"security": "npm audit --audit-level=high", "lint": "eslint ."}})
NODE_PLAIN = json.dumps({"name": "x", "scripts": {"lint": "eslint ."}})


def workflow(*steps: str) -> str:
    body = "".join(f"      - {step}\n" for step in steps)
    return f"on: [pull_request]\njobs:\n  ci:\n    runs-on: ubuntu-latest\n    steps:\n{body}"


class Tool04CiAuditTests(unittest.TestCase):
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

    def test_ci_runs_the_local_verb_passes(self):
        check = self.check({"package.json": NODE_AUDIT, ".github/workflows/ci.yml": workflow("run: npm run security")})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("CI: .github/workflows/ci.yml:6 security", check["summary"])

    def test_local_only_is_partial(self):
        check = self.check({"package.json": NODE_AUDIT, ".github/workflows/ci.yml": workflow("run: npm run lint")})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("CI runs no dependency audit", check["summary"])
        self.assertIn("Run the same verb in CI", check["findings"][0]["remediation"])

    def test_local_only_without_any_ci_is_partial(self):
        self.assertEqual(self.check({"package.json": NODE_AUDIT})["verdict"], "PARTIAL")

    def test_ci_only_is_partial(self):
        check = self.check({"package.json": NODE_PLAIN, ".github/workflows/ci.yml": workflow("run: npm audit")})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("no local verb does", check["summary"])

    def test_a_scanner_action_counts_as_ci(self):
        check = self.check(
            {
                "package.json": NODE_AUDIT,
                ".github/workflows/ci.yml": workflow("uses: google/osv-scanner-action/osv-scanner-action@v2"),
            }
        )
        self.assertEqual(check["verdict"], "PASS")

    def test_a_makefile_part_counts_as_ci(self):
        makefile = "security: secrets deps\n\nsecrets:\n\tdetect-secrets scan\n\ndeps:\n\tpip-audit\n"
        check = self.check(
            {
                "pyproject.toml": '[project]\nname = "x"\n',
                "Makefile": makefile,
                ".github/workflows/ci.yml": workflow("run: make deps"),
            }
        )
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("deps (pip-audit)", check["summary"])

    def test_gitlab_dependency_scanning_template_counts(self):
        gitlab = "include:\n  - template: Jobs/Dependency-Scanning.gitlab-ci.yml\n"
        check = self.check({"package.json": NODE_AUDIT, ".gitlab-ci.yml": gitlab})
        self.assertEqual(check["verdict"], "PASS")

    def test_dependabot_and_comments_do_not_count(self):
        dependabot = "version: 2\nupdates:\n  - package-ecosystem: npm\n    directory: /\n"
        check = self.check(
            {
                "package.json": NODE_AUDIT,
                ".github/dependabot.yml": dependabot,
                ".github/workflows/ci.yml": workflow("run: npm run lint") + "      # - run: npm audit\n",
            }
        )
        self.assertEqual(check["verdict"], "PARTIAL")

    def test_neither_stays_fail(self):
        check = self.check({"package.json": NODE_PLAIN, ".github/workflows/ci.yml": workflow("run: npm run lint")})
        self.assertEqual(check["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
