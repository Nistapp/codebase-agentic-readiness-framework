# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The implement eval's owner-rule assertions on hand-made runs, with no agent (RFR.9).

- A21 guards HR-0836 (the add-hooks-and-commit-rules playbook): "Do not advise `--no-verify` or add a bypass
  variable."
- A22 guards HR-0647 and HR-0661 ("Never delete it unasked", a vendor instruction file), HR-0643 ("Do not rewrite an
  existing `AGENTS.md` wholesale ... or reflow its lines"), HR-0674 and HR-0689 ("Never shorten by reflowing or
  deleting the owner's rules"), all in the adapt-agents-md playbook.

As in `test_implement_eval.py`, each runs on a materialised scenario and a synthetic stream-json transcript: a run
that keeps the rule must pass, and each way of breaking it must fail. Standard library only; no network, no `claude`.
"""

from __future__ import annotations

import json
import unittest

import _dev_paths  # noqa: F401  (puts dev/eval on sys.path)
from test_implement_eval import tool_use
from test_implement_eval_boundaries import ProbeCase

import implement_eval as ie


class EveryScenarioTests(unittest.TestCase):
    def test_every_scenario_scores_the_hooks(self) -> None:
        for name in ie.scenario_names():
            self.assertIn("A21", ie.load_scenario(name).assertions, name)

    def test_every_scenario_with_a_theme_scores_the_instruction_files(self) -> None:
        for name in ie.scenario_names():
            scenario = ie.load_scenario(name)
            self.assertEqual("A22" in scenario.assertions, scenario.phase.startswith("t"), name)


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


# --- A22: the owner's instruction files and rules stay ---------------------------------------------------------

CLAUDE_STUB = "@AGENTS.md\n"
CURSOR_RULES = "Use four spaces.\nNever edit tools/.\n"
COPILOT = "Run make test before you commit.\n"
GENERIC = "\n## Working style\n\nBe thorough and careful.\nThink step by step.\n"


class OwnerInstructionsKeptTests(ProbeCase):
    scenario_name = "comm-agents-md"

    def setUp(self) -> None:
        super().setUp()
        # The snapshot this case audits holds the owner's vendor files and a generic section in AGENTS.md.
        agents = (self.repo / "AGENTS.md").read_text(encoding="utf-8")
        files = {
            "CLAUDE.md": CLAUDE_STUB,
            ".cursorrules": CURSOR_RULES,
            ".github/copilot-instructions.md": COPILOT,
            "AGENTS.md": agents + GENERIC,
        }
        for path, content in files.items():
            (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / path).write_text(content, encoding="utf-8")
        snapshot = ie.commit_all(self.repo, "docs: the owner's instruction files", "2026-01-04T00:00:00Z", list(files))
        baseline_file = self.root / ie.BASELINE_FILE
        baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        baseline["snapshot"] = snapshot
        baseline_file.write_text(json.dumps(baseline), encoding="utf-8")
        self.tree = self.root / "worktrees" / "t7-agents-md"
        self.git(self.repo, "worktree", "add", "--quiet", str(self.tree), "-b", "agentic-readiness/t7-agents-md")

    def agents(self) -> str:
        return (self.tree / "AGENTS.md").read_text(encoding="utf-8")

    def test_the_engine_names_the_instruction_files(self) -> None:
        paths = ["CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md", "AGENTS.md", "docs/README.md", "x.py"]
        found = ie.instruction_files(paths)
        self.assertEqual(found, {"CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md", "AGENTS.md"})
        self.assertTrue({"GEMINI.md", ".windsurfrules"} <= ie.instruction_files(["GEMINI.md", ".windsurfrules"]))

    def test_passes_when_a_section_is_added_and_a_generic_one_moves_to_a_linked_page(self) -> None:
        text = self.agents().replace(GENERIC, "\nWorking style: see [docs/working-style.md](docs/working-style.md).\n")
        text = text.replace("- `docs/` holds", "1. `docs/` holds")  # a renumbering keeps the line
        self.commit_file(
            self.tree, "docs/working-style.md", "# Working style" + GENERIC.split("style", 1)[1], "docs: move"
        )
        self.commit_file(
            self.tree, "AGENTS.md", text + "\n## How to write for people\n\n- Bottom line first.\n", "docs: rules"
        )
        self.commit_file(self.tree, ".cursorrules", CURSOR_RULES + "See AGENTS.md.\n", "docs: point at AGENTS.md")
        self.assertProbePasses(ie.owner_instructions_kept)

    def test_fails_when_a_vendor_file_is_deleted(self) -> None:
        for path in ("CLAUDE.md", ".github/copilot-instructions.md"):
            self.git(self.tree, "rm", "--quiet", path)
        self.git(self.tree, "commit", "--quiet", "-m", "docs: drop the vendor files")
        self.assertProbeFails(ie.owner_instructions_kept, "deletes the instruction file CLAUDE.md")
        self.assertProbeFails(
            ie.owner_instructions_kept, "deletes the instruction file .github/copilot-instructions.md"
        )

    def test_fails_when_a_vendor_file_is_renamed(self) -> None:
        self.git(self.tree, "mv", ".cursorrules", "docs/cursor-rules.md")
        self.git(self.tree, "commit", "--quiet", "-m", "docs: move the cursor rules")
        self.assertProbeFails(ie.owner_instructions_kept, "deletes the instruction file .cursorrules")

    def test_fails_when_an_owner_rule_is_deleted(self) -> None:
        text = self.agents().replace("Tests never import from `tools/`.", "")
        self.commit_file(self.tree, "AGENTS.md", text, "docs: shorten AGENTS.md")
        self.assertProbeFails(ie.owner_instructions_kept, "drops 1 owner line(s) of AGENTS.md")

    def test_fails_when_the_file_is_reflowed(self) -> None:
        first = "stockroom is a tiny stock-keeping library in standard-library Python. This file is read by any harness that reads\n"
        text = self.agents().replace(first, first.rstrip("\n") + " ")
        self.commit_file(self.tree, "AGENTS.md", text, "docs: reflow AGENTS.md")
        self.assertProbeFails(ie.owner_instructions_kept, "owner line(s) of AGENTS.md")

    def test_fails_when_a_section_moves_to_a_page_that_is_not_linked(self) -> None:
        self.commit_file(
            self.tree, "docs/working-style.md", "# Working style" + GENERIC.split("style", 1)[1], "docs: move"
        )
        self.commit_file(self.tree, "AGENTS.md", self.agents().replace(GENERIC, "\n"), "docs: drop the section")
        self.assertProbeFails(ie.owner_instructions_kept, "drops 3 owner line(s) of AGENTS.md, first: Working style")


if __name__ == "__main__":
    unittest.main()
