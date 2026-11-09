# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`HYG-09` reads the dependency-update file for coverage per ecosystem and the `target-branch` trap.

The update policy itself (security pull requests only, majors advisory, cooldown) is the owner's choice and never
a verdict. Two defects hold whatever the policy: an ecosystem with no entry, and a Dependabot entry whose `ignore`
or `groups` options `target-branch` keeps from applying to security updates.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

PACKAGE_JSON = '{"name": "x", "version": "0.1.0", "private": true}\n'
WORKFLOW = (
    "name: CI\non: [pull_request]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make check\n"
)


def dependabot(*entries: str) -> str:
    return "version: 2\nupdates:\n" + "".join(entries)


def entry(ecosystem: str, *extra: str) -> str:
    lines = [f"  - package-ecosystem: {ecosystem}", "    directory: /", "    schedule:", "      interval: weekly"]
    return "\n".join(lines + [f"    {line}" for line in extra]) + "\n"


class Hyg09PolicyTests(unittest.TestCase):
    def check(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            report = support.run_audit(root)
        check = next(c for c in report["checks"] if c["id"] == "HYG-09")
        check["findings"] = [f for f in report.get("findings", []) if f["check"] == "HYG-09"]
        return check

    def test_every_ecosystem_covered_passes(self):
        check = self.check(
            {
                "package.json": PACKAGE_JSON,
                "pyproject.toml": "[project]\nname = 'x'\n",
                ".github/workflows/ci.yml": WORKFLOW,
                ".github/dependabot.yml": dependabot(entry("npm"), entry("uv"), entry("github-actions")),
            }
        )
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("covers github-actions, node, python", check["summary"])

    def test_github_ci_needs_a_github_actions_entry(self):
        check = self.check(
            {
                "package.json": PACKAGE_JSON,
                ".github/workflows/ci.yml": WORKFLOW,
                ".github/dependabot.yml": dependabot(entry("npm")),
            }
        )
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("no entry for github-actions", check["findings"][0]["statement"])

    def test_items_at_the_updates_indent_are_read(self):
        text = "version: 2\nupdates:\n- package-ecosystem: 'npm'  # quoted, with a comment\n  directory: /\n"
        check = self.check({"package.json": PACKAGE_JSON, "dependabot.yml": text})
        self.assertEqual(check["verdict"], "PASS")

    def test_target_branch_alone_is_not_the_trap(self):
        check = self.check(
            {"package.json": PACKAGE_JSON, ".github/dependabot.yml": dependabot(entry("npm", "target-branch: develop"))}
        )
        self.assertEqual(check["verdict"], "PASS")

    def test_target_branch_with_groups_is_the_trap_and_cites_its_line(self):
        text = dependabot(entry("npm", "target-branch: develop", "groups:", "  all:", "    patterns: ['*']"))
        check = self.check({"package.json": PACKAGE_JSON, ".github/dependabot.yml": text})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertEqual(check["findings"][0]["evidence"][0]["line"], 7)
        self.assertIn("`groups`", check["findings"][0]["statement"])

    def test_a_source_only_python_project_needs_no_entry(self):
        check = self.check({"src/app.py": "print('x')\n", ".github/dependabot.yml": dependabot(entry("docker"))})
        self.assertEqual(check["verdict"], "PASS")

    def test_a_dependabot_file_without_an_updates_list_is_unknown(self):
        check = self.check({"package.json": PACKAGE_JSON, ".github/dependabot.yml": "version: 2\n"})
        self.assertEqual(check["verdict"], "UNKNOWN")

    def test_renovate_without_enabled_managers_covers_everything(self):
        check = self.check(
            {"package.json": PACKAGE_JSON, ".github/workflows/ci.yml": WORKFLOW, "renovate.json": '{"extends": []}'}
        )
        self.assertEqual(check["verdict"], "PASS")

    def test_renovate_enabled_managers_that_leave_out_an_ecosystem_is_partial(self):
        check = self.check({"package.json": PACKAGE_JSON, "renovate.json": '{"enabledManagers": ["pep621"]}'})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("no entry for node", check["findings"][0]["statement"])

    def test_renovate_json5_counts_on_presence(self):
        check = self.check({"package.json": PACKAGE_JSON, "renovate.json5": "{ extends: [] }"})
        self.assertEqual(check["verdict"], "PASS")

    def test_invalid_renovate_json_is_unknown(self):
        check = self.check({"package.json": PACKAGE_JSON, "renovate.json": "{ not json"})
        self.assertEqual(check["verdict"], "UNKNOWN")

    def test_a_second_tool_can_cover_what_the_first_leaves_out(self):
        check = self.check(
            {
                "package.json": PACKAGE_JSON,
                ".github/workflows/ci.yml": WORKFLOW,
                ".github/dependabot.yml": dependabot(entry("github-actions")),
                "renovate.json": '{"enabledManagers": ["npm"]}',
            }
        )
        self.assertEqual(check["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
