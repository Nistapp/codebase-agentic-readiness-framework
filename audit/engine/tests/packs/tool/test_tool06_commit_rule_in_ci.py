# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`TOOL-06`: the commit-message rule runs in a local `commit-msg` stage and in CI.

Both ⇒ `PASS`; only one of the two ⇒ `PARTIAL`; neither ⇒ `FAIL`. CI is seen through a known tool on a workflow
line, a pull-request title check, a script the local stage also runs, or a runner target whose command does one
of those. The check runs in-process here, so coverage traces it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks.tool import check_tool06 as CHECK  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "TOOL-06"

PACKAGE = '{"name": "x", "version": "0.1.0", "private": true}\n'
SCRIPT = "import sys\nsys.exit(0)\n"

LEFTHOOK_WITH_SCRIPT = """pre-commit:
  commands:
    format:
      run: scripts/format_check.py {staged_files}
commit-msg:
  commands:
    subject:
      run: python3 scripts/commit_lint.py --message-file {1}
"""


def workflow(*runs: str) -> str:
    steps = "".join(f"      - run: {run}\n" for run in runs)
    return (
        "name: ci\non:\n  pull_request:\njobs:\n  commits:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n" + steps
    )


class Tool06CommitRuleInCiTests(unittest.TestCase):
    def check(self, files: dict[str, str]) -> dict:
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

    # -- PASS: the rule runs in both places -----------------------------------------------------------

    def test_the_hook_script_run_again_in_ci_passes(self):
        result = self.check(
            {
                "package.json": PACKAGE,
                "lefthook.yml": LEFTHOOK_WITH_SCRIPT,
                "scripts/commit_lint.py": SCRIPT,
                "scripts/format_check.py": SCRIPT,
                ".github/workflows/ci.yml": workflow('python3 scripts/commit_lint.py --range "$BASE..$HEAD"'),
            }
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertIn("CI: scripts/commit_lint.py (.github/workflows/ci.yml)", result["summary"])

    def test_a_make_target_that_runs_the_hook_script_passes(self):
        result = self.check(
            {
                "Makefile": "commit-lint:\n\tpython3 scripts/commit_lint.py --range $(RANGE)\n",
                "lefthook.yml": LEFTHOOK_WITH_SCRIPT,
                "scripts/commit_lint.py": SCRIPT,
                "scripts/format_check.py": SCRIPT,
                ".github/workflows/ci.yml": workflow("make commit-lint RANGE=origin/main..HEAD"),
            }
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertIn("commit-lint (scripts/commit_lint.py)", result["summary"])

    def test_an_npm_script_that_runs_commitlint_passes(self):
        result = self.check(
            {
                "package.json": '{"name": "x", "scripts": {"lint:commits": "commitlint --from origin/main"}}\n',
                ".husky/commit-msg": 'npx --no -- commitlint --edit "$1"\n',
                "commitlint.config.js": "export default { extends: ['@commitlint/config-conventional'] };\n",
                ".github/workflows/ci.yml": workflow("npm run lint:commits"),
            }
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertIn("lint:commits (commitlint)", result["summary"])

    def test_gitlint_in_gitlab_ci_with_a_pre_commit_hook_passes(self):
        result = self.check(
            {
                "pyproject.toml": '[project]\nname = "x"\nversion = "0.1.0"\n',
                ".pre-commit-config.yaml": (
                    "repos:\n  - repo: https://github.com/jorisroovers/gitlint\n    rev: v0.19.1\n    hooks:\n"
                    "      - id: gitlint\n        stages: [commit-msg]\n"
                ),
                ".gitlab-ci.yml": (
                    "commits:\n  rules:\n    - if: $CI_PIPELINE_SOURCE == 'merge_request_event'\n  script:\n"
                    '    - gitlint --commits "$CI_MERGE_REQUEST_DIFF_BASE_SHA..$CI_COMMIT_SHA"\n'
                ),
            }
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertIn("gitlint (.gitlab-ci.yml)", result["summary"])

    def test_commitizen_check_in_ci_passes(self):
        result = self.check(
            {
                "pyproject.toml": '[project]\nname = "x"\nversion = "0.1.0"\n',
                ".pre-commit-config.yaml": (
                    "repos:\n  - repo: https://github.com/commitizen-tools/commitizen\n    rev: v4.0.0\n"
                    "    hooks:\n      - id: commitizen\n        stages: [commit-msg]\n"
                ),
                ".github/workflows/ci.yml": workflow('cz check --rev-range "$BASE..$HEAD"'),
            }
        )
        self.assertEqual(result["verdict"], "PASS")

    # -- PARTIAL: only one of the two ------------------------------------------------------------------

    def test_a_local_hook_with_no_ci_step_is_partial(self):
        result = self.check({"package.json": PACKAGE, ".husky/commit-msg": 'npx --no -- commitlint --edit "$1"\n'})
        self.assertEqual(result["verdict"], "PARTIAL")
        self.assertIn("runs only in a local hook", result["findings"][0]["statement"])
        self.assertEqual([e["path"] for e in result["findings"][0]["evidence"]], [".husky/commit-msg"])

    def test_installing_commitlint_in_ci_is_not_running_it(self):
        result = self.check(
            {
                "package.json": PACKAGE,
                ".husky/commit-msg": 'npx --no -- commitlint --edit "$1"\n',
                ".github/workflows/ci.yml": workflow("npm install --no-save @commitlint/cli"),
            }
        )
        self.assertEqual(result["verdict"], "PARTIAL")

    def test_a_commented_out_ci_step_does_not_count(self):
        result = self.check(
            {
                "package.json": PACKAGE,
                ".husky/commit-msg": 'npx --no -- commitlint --edit "$1"\n',
                ".github/workflows/ci.yml": workflow("npm test") + "      # - run: npx commitlint --from main\n",
            }
        )
        self.assertEqual(result["verdict"], "PARTIAL")

    def test_a_script_from_another_hook_stage_does_not_count(self):
        result = self.check(
            {
                "package.json": PACKAGE,
                "lefthook.yml": LEFTHOOK_WITH_SCRIPT,
                "scripts/commit_lint.py": SCRIPT,
                "scripts/format_check.py": SCRIPT,
                ".github/workflows/ci.yml": workflow("python3 scripts/format_check.py"),
            }
        )
        self.assertEqual(result["verdict"], "PARTIAL")

    def test_a_pre_commit_item_outside_the_commit_msg_stage_does_not_count(self):
        result = self.check(
            {
                "package.json": PACKAGE,
                ".pre-commit-config.yaml": (
                    "repos:\n  - repo: local\n    hooks:\n      - id: fmt\n        entry: python3 scripts/fmt.py\n"
                    "        language: system\n      - id: subject\n        entry: python3 scripts/subject.py\n"
                    "        language: system\n        stages: [commit-msg]\n"
                ),
                "scripts/fmt.py": SCRIPT,
                "scripts/subject.py": SCRIPT,
                ".github/workflows/ci.yml": workflow("python3 scripts/fmt.py"),
            }
        )
        self.assertEqual(result["verdict"], "PARTIAL")
        self.assertIn("CI: none", result["summary"])

    def test_a_ci_step_with_no_local_rule_is_partial(self):
        result = self.check(
            {
                "package.json": PACKAGE,
                ".github/workflows/title.yml": (
                    "name: title\non:\n  pull_request:\njobs:\n  title:\n    runs-on: ubuntu-latest\n"
                    "    steps:\n      - uses: amannn/action-semantic-pull-request@v5\n"
                ),
            }
        )
        self.assertEqual(result["verdict"], "PARTIAL")
        finding = result["findings"][0]
        self.assertIn("runs only in CI", finding["statement"])
        self.assertEqual(
            [(e["path"], e["line"], e["note"]) for e in finding["evidence"]],
            [(".github/workflows/title.yml", 8, "pull-request title check")],
        )

    # -- FAIL and UNKNOWN: unchanged ------------------------------------------------------------------

    def test_no_rule_anywhere_fails(self):
        result = self.check({"package.json": PACKAGE, ".github/workflows/ci.yml": workflow("npm test")})
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("CI step", result["findings"][0]["statement"])

    def test_nothing_to_judge_is_unknown(self):
        result = self.check({"notes.txt": "hello\n"})
        self.assertEqual(result["verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
