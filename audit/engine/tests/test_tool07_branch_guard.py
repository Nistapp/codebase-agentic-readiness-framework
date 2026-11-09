# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`TOOL-07` reads the local guard that refuses a commit on a protected branch.

The guard is pre-commit's `no-commit-to-branch`, or a hook that reads the current branch, in the hook manager the
stack uses. It must name every branch the declared rules protect, and its hook chain must be wired.
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

from audit.rules.checks.tool import check_tool07 as CHECK  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "TOOL-07"

LEFTHOOK_GUARD = """pre-commit:
  commands:
    protected-branch:
      run: >-
        branch="$(git symbolic-ref --quiet --short HEAD || true)";
        case "$branch" in main|dev) exit 1;; esac
    format-check:
      run: make format-check
"""

SHELL_GUARD = """#!/bin/sh
branch="$(git branch --show-current)"
if [ "$branch" = "main" ]; then
  echo "Do not commit on main." >&2
  exit 1
fi
"""

PACKAGE_WITH_HUSKY = json.dumps({"name": "x", "private": True, "scripts": {"prepare": "husky"}})


def pre_commit(*hook_lines: str) -> str:
    lines = [
        "repos:",
        "  - repo: https://github.com/pre-commit/pre-commit-hooks",
        "    rev: v5.0.0",
        "    hooks:",
        "      - id: trailing-whitespace",
    ]
    return "\n".join(lines + list(hook_lines)) + "\n"


def ruleset(branch: str) -> str:
    return json.dumps(
        {
            "name": f"{branch} protection",
            "target": "branch",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": [f"refs/heads/{branch}"], "exclude": []}},
            "rules": [{"type": "deletion"}],
        }
    )


RULESETS = {".github/rulesets/dev.json": ruleset("dev"), ".github/rulesets/main.json": ruleset("main")}


class Tool07BranchGuardTests(unittest.TestCase):
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

    # -- pre-commit (Python) ------------------------------------------------------------------------------------

    def test_no_commit_to_branch_with_its_defaults_passes_without_declared_rules(self):
        check = self.check({".pre-commit-config.yaml": pre_commit("      - id: no-commit-to-branch")})
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["summary"], "branch guard at .pre-commit-config.yaml:6")

    def test_no_commit_to_branch_naming_every_protected_branch_passes(self):
        hook = ("      - id: no-commit-to-branch", "        args: [--branch, main, --branch, dev]")
        check = self.check({".pre-commit-config.yaml": pre_commit(*hook), **RULESETS})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("names dev, main", check["summary"])

    def test_multi_line_args_are_read(self):
        hook = (
            "      - id: no-commit-to-branch",
            "        args:",
            "          - --branch",
            "          - dev",
            "          - '--branch=main'",
        )
        check = self.check({".pre-commit-config.yaml": pre_commit(*hook), **RULESETS})
        self.assertEqual(check["verdict"], "PASS")

    def test_default_branches_miss_a_protected_integration_branch(self):
        check = self.check({".pre-commit-config.yaml": pre_commit("      - id: no-commit-to-branch"), **RULESETS})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("does not name dev", check["summary"])

    def test_a_pattern_argument_covers_the_branches_it_matches(self):
        hook = ("      - id: no-commit-to-branch", "        args: ['--pattern', '(main|dev)$', '-p', '[']")
        check = self.check({".pre-commit-config.yaml": pre_commit(*hook), **RULESETS})
        self.assertEqual(check["verdict"], "PASS")

    def test_a_pattern_keeps_the_default_branches(self):
        hook = ("      - id: no-commit-to-branch", "        args: ['--pattern', 'release/.*']")
        rules = {".github/rulesets/main.json": ruleset("main")}
        check = self.check({".pre-commit-config.yaml": pre_commit(*hook), **rules})
        self.assertEqual(check["verdict"], "PASS")

    # -- lefthook (mixed) ---------------------------------------------------------------------------------------

    def test_lefthook_guard_names_both_branches(self):
        check = self.check({"lefthook.yml": LEFTHOOK_GUARD, **RULESETS})
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["summary"], "branch guard at lefthook.yml:5; names dev, main")

    def test_a_branch_named_only_in_another_command_is_not_covered(self):
        lefthook = LEFTHOOK_GUARD.replace("main|dev)", "main)").replace("make format-check", "dev/tools/lint dev")
        check = self.check({"lefthook.yml": lefthook, **RULESETS})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("does not name dev", check["summary"])

    def test_a_pre_push_guard_does_not_stop_a_commit(self):
        lefthook = LEFTHOOK_GUARD.replace("pre-commit:", "pre-push:")
        check = self.check({"lefthook.yml": lefthook})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("hooks present (lefthook.yml)", check["summary"])

    def test_a_commented_out_branch_read_is_not_a_guard(self):
        lefthook = "pre-commit:\n  commands:\n    lint:\n      # git branch --show-current\n      run: make lint\n"
        check = self.check({"lefthook.yml": lefthook})
        self.assertEqual(check["verdict"], "FAIL")

    # -- Husky (Node) and plain hook scripts --------------------------------------------------------------------

    def test_husky_guard_wired_by_the_prepare_script_passes(self):
        check = self.check({"package.json": PACKAGE_WITH_HUSKY, ".husky/pre-commit": SHELL_GUARD})
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["summary"], "branch guard at .husky/pre-commit:2")

    def test_husky_guard_without_an_install_script_is_partial(self):
        package = json.dumps({"name": "x", "private": True})
        check = self.check({"package.json": package, ".husky/pre-commit": SHELL_GUARD})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("its hook chain is not wired", check["summary"])

    def test_githooks_guard_wired_through_core_hooks_path_passes(self):
        makefile = "setup:\n\tgit config core.hooksPath .githooks\n"
        check = self.check({"Makefile": makefile, ".githooks/pre-commit": SHELL_GUARD})
        self.assertEqual(check["verdict"], "PASS")

    def test_githooks_guard_misses_a_protected_branch(self):
        makefile = "setup:\n\tgit config core.hooksPath .githooks\n"
        check = self.check({"Makefile": makefile, ".githooks/commit-msg": SHELL_GUARD, **RULESETS})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("does not name dev", check["summary"])

    # -- no guard -----------------------------------------------------------------------------------------------

    def test_hooks_without_a_guard_fail(self):
        check = self.check({".pre-commit-config.yaml": pre_commit()})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(len(check["findings"]), 1)

    def test_no_hook_chain_is_unknown_and_left_to_tool05(self):
        check = self.check({"package.json": json.dumps({"name": "x"})})
        self.assertEqual(check["verdict"], "UNKNOWN")
        self.assertIn("TOOL-05 owns that finding", check["summary"])


if __name__ == "__main__":
    unittest.main()
