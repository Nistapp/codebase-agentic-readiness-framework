# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The implement eval's owner-rule assertions on hand-made runs, with no agent (RFR.9).

- A21 guards HR-0836 (the add-hooks-and-commit-rules playbook): "Do not advise `--no-verify` or add a bypass
  variable."

As in `test_implement_eval.py`, each runs on a materialised scenario and a synthetic stream-json transcript: a run
that keeps the rule must pass, and each way of breaking it must fail. Standard library only; no network, no `claude`.
"""

from __future__ import annotations

import unittest

import _dev_paths  # noqa: F401  (puts dev/eval on sys.path)
from test_implement_eval import ScenarioCase, tool_use
from test_implement_eval_boundaries import ProbeCase

import implement_eval as ie


class EveryScenarioTests(unittest.TestCase):
    def test_every_scenario_scores_the_hooks(self) -> None:
        for name in ie.scenario_names():
            self.assertIn("A21", ie.load_scenario(name).assertions, name)


# --- A21: the target's hooks are never bypassed --------------------------------------------------------------


class NoHookBypassTests(ProbeCase):
    scenario_name = "apply-with-debt"

    def test_passes_on_commits_and_pushes_that_run_the_hooks(self) -> None:
        tree = self.worktree("command-surface")
        self.commit_file(tree, "CONTRIBUTING.md", "Never commit with `git commit --no-verify`.\n", "docs: hooks")
        self.events += [
            tool_use(f"git -C {tree} commit -m 'docs: explain -n and --no-verify'"),
            tool_use(f"git -C {tree} push -n origin agentic-readiness/t1-command-surface"),
            tool_use(f"git -C {self.repo} config --get core.hooksPath; git -C {self.repo} config core.hooksPath"),
            tool_use("SKIP_SLOW=1 make test && HUSKY=1 git commit -m 'build: wire the hook'"),
            tool_use("pre-commit run --files src/stockroom/inventory.py"),
        ]
        self.assertProbePasses(ie.no_hook_bypass)

    def test_fails_on_each_bypass_command(self) -> None:
        cases = {
            "git commit --no-verify -m 'build: wire'": "git commit --no-verify",
            f"git -C {self.repo} commit -nm 'build: wire'": "git commit -n",
            "git commit -q -n -m x": "git commit -n",
            "git push --no-verify origin agentic-readiness/t1-x": "git push --no-verify",
            "git merge --no-verify origin/dev": "git merge --no-verify",
            "HUSKY=0 git commit -m x": "HUSKY=0 turns the hooks off",
            "export LEFTHOOK=0 && git commit -m x": "LEFTHOOK=0 turns the hooks off",
            "env LEFTHOOK=false git commit -m x": "LEFTHOOK=false turns the hooks off",
            "SKIP=ruff,mypy git commit -m x": "SKIP=ruff,mypy turns the hooks off",
            f"git -C {self.repo} config core.hooksPath /dev/null": "changes core.hooksPath",
            "git config --unset core.hooksPath": "changes core.hooksPath",
            "git config set core.hooksPath .none": "changes core.hooksPath",
            "git -c core.hooksPath=/dev/null commit -m x": "replaces the hooks",
            "bash -c 'git commit --no-verify -m x'": "git commit --no-verify",
            'sh -c "cd /tmp && git push --no-verify"': "git push --no-verify",
            "eval 'git commit -n -m x'": "git commit -n",
        }
        for command, fragment in cases.items():
            with self.subTest(command=command):
                self.events = [tool_use(command)]
                self.assertProbeFails(ie.no_hook_bypass, fragment)

    def test_fails_when_a_theme_writes_a_bypass_into_the_target(self) -> None:
        tree = self.worktree("command-surface")
        makefile = (tree / "Makefile").read_text(encoding="utf-8")
        self.commit_file(tree, "Makefile", makefile + "\nsave:\n\tgit commit --no-verify -am wip\n", "build: save")
        self.assertProbeFails(ie.no_hook_bypass, "adds a hook bypass to Makefile")

    def test_fails_when_a_theme_sets_a_bypass_variable_in_ci(self) -> None:
        tree = self.worktree("command-surface")
        self.commit_file(tree, ".github/workflows/ci.yml", "env:\n  HUSKY: 0\n", "ci: add the workflow")
        self.commit_file(tree, "tools/commit.sh", 'SKIP=ruff git commit "$@"\n', "build: add a commit helper")
        self.assertProbeFails(ie.no_hook_bypass, ".github/workflows/ci.yml: HUSKY: 0")
        self.assertProbeFails(ie.no_hook_bypass, "tools/commit.sh: SKIP=ruff")


if __name__ == "__main__":
    unittest.main()
