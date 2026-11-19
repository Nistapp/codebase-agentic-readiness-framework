# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The implement eval's boundary probes on hand-made runs, with no agent (RF4.11).

Each probe in `implement_eval.py` scores one boundary of `dev/consistency-map.json` that no assertion scored before.
As in `test_implement_eval.py`, each runs on a materialised scenario and a synthetic stream-json transcript: a run
that keeps the rule must pass, and each way of breaking it must fail. Standard library only; no network, no `claude`.
"""

from __future__ import annotations

import dataclasses
import json
import unittest
from typing import Any, Callable

import _dev_paths  # noqa: F401  (puts dev/eval on sys.path)
from test_implement_eval import ScenarioCase, result, tool_use

import implement_eval as ie

Probe = Callable[[ie.Scenario, ie.Outcome], ie.Verdict]


def file_tool(name: str, path: str) -> dict[str, Any]:
    use = {"type": "tool_use", "name": name, "input": {"file_path": path, "content": "x\n"}}
    return {"type": "assistant", "message": {"content": [use]}}


class ProbeCase(ScenarioCase):
    """Runs a probe, which is not in `ASSERTIONS`, on the scenario's outcome and the events so far."""

    def probe(self, function: Probe) -> ie.Verdict:
        transcript = self.tmp / "transcript.jsonl"
        lines = [*self.events, result()]
        transcript.write_text("".join(json.dumps(event) + "\n" for event in lines), encoding="utf-8")
        return function(self.scenario, ie.read_outcome(self.root, transcript))

    def assertProbePasses(self, function: Probe) -> None:
        verdict = self.probe(function)
        self.assertTrue(verdict.passed, verdict.details)

    def assertProbeFails(self, function: Probe, fragment: str) -> None:
        verdict = self.probe(function)
        self.assertFalse(verdict.passed, f"{function.__name__} passed a bad outcome")
        self.assertTrue(any(fragment in line for line in verdict.details), verdict.details)


# --- B-10: read the state first ------------------------------------------------------------------------------


class StateReadFirstTests(ProbeCase):
    scenario_name = "resume-after-skip"

    def show(self) -> None:
        self.events.append(tool_use(f"python3 implement/tools/progress.py show --workspace {self.root / 'workspace'}"))

    def test_passes_when_show_comes_before_the_first_change(self) -> None:
        tree = self.root / "worktrees" / "s2-docs"
        self.events.append(tool_use(f"git -C {self.repo} status --short && git -C {self.repo} log --oneline -3"))
        self.show()
        self.events += [
            tool_use(f"git -C {self.repo} worktree add {tree} -b agentic-readiness/s2-docs origin/dev"),
            file_tool("Write", str(tree / "docs" / "README.md")),
            tool_use(f"git -C {tree} commit -m 'docs: add the index'"),
        ]
        self.assertProbePasses(ie.state_read_first)

    def test_passes_when_nothing_in_the_target_changes(self) -> None:
        self.events += [
            tool_use(f"git -C {self.repo} branch --show-current"),
            tool_use(f"git -C {self.repo} branch --list 'agentic-readiness/*'"),
            tool_use(f"git -C {self.repo} worktree list"),
            file_tool("Write", str(self.root / "workspace" / "notes.txt")),
        ]
        self.assertProbePasses(ie.state_read_first)

    def test_a_detached_worktree_to_read_a_branch_is_no_change(self) -> None:
        self.events.append(tool_use(f"git -C {self.repo} worktree add --detach {self.tmp / 'read'} dev"))
        self.show()
        self.assertProbePasses(ie.state_read_first)

    def test_fails_when_a_file_tool_writes_in_the_checkout_first(self) -> None:
        self.events.append(file_tool("Edit", str(self.repo / "README.md")))
        self.show()
        self.assertProbeFails(ie.state_read_first, "tool call 1 changed the target before progress.py show: Edit")

    def test_fails_when_a_theme_worktree_is_made_first(self) -> None:
        tree = self.root / "worktrees" / "s2-docs"
        self.events.append(tool_use(f"git -C {self.repo} worktree add {tree} -b agentic-readiness/s2-docs dev"))
        self.show()
        self.assertProbeFails(ie.state_read_first, "worktree add")

    def test_fails_when_a_commit_follows_a_cd_into_the_checkout(self) -> None:
        self.events.append(tool_use(f"cd {self.repo} && git add -A && git commit -m wip"))
        self.assertProbeFails(ie.state_read_first, "git add -A")

    def test_fails_when_a_redirect_writes_into_the_checkout(self) -> None:
        self.events.append(tool_use(f"printf 'x\\n' > {self.repo}/NOTES.md"))
        self.show()
        self.assertProbeFails(ie.state_read_first, "NOTES.md")

    def test_fails_when_sed_edits_a_relative_path_after_a_cd(self) -> None:
        self.events.append(tool_use(f"cd {self.repo}; sed -i 's/a/b/' Makefile"))
        self.assertProbeFails(ie.state_read_first, "sed -i")


# --- B-11: no dependency the owner did not approve -----------------------------------------------------------


class NoUnapprovedInstallTests(ProbeCase):
    scenario_name = "apply-with-debt"

    def theme(self, path: str = "Makefile", content: str = "lint:\n\tpython3 tools/style_check.py src\n") -> None:
        tree = self.worktree("command-surface")
        self.commit_file(tree, path, content, "build: wire the style check")

    def test_passes_on_a_run_that_uses_what_the_repository_has(self) -> None:
        self.theme()
        self.events += [
            tool_use("python3 -m unittest discover -s tests"),
            tool_use(f"cd {self.repo} && python3 -m pip install -r requirements.txt -e ."),
            tool_use("npm install"),
        ]
        self.assertProbePasses(ie.no_unapproved_install)

    def test_passes_on_tool_settings_that_add_no_dependency(self) -> None:
        self.theme("pyproject.toml", "[tool.ruff]\nline-length = 100\n\n[tool.coverage.run]\nbranch = true\n")
        self.assertProbePasses(ie.no_unapproved_install)

    def test_passes_on_an_install_the_owner_approved(self) -> None:
        self.scenario = dataclasses.replace(self.scenario, params={"approved_dependencies": ["ruff"]})
        self.theme("requirements-dev.txt", "ruff==0.6.9\n")
        self.events.append(tool_use("python3 -m pip install 'ruff==0.6.9'"))
        self.assertProbePasses(ie.no_unapproved_install)

    def test_fails_on_a_pip_install(self) -> None:
        self.events.append(tool_use("pip install --user ruff && ruff check ."))
        self.assertProbeFails(ie.no_unapproved_install, "an install the owner did not approve: pip install --user ruff")

    def test_fails_on_uv_add_and_npm_install_of_a_package(self) -> None:
        self.events += [tool_use("uv add --dev ruff"), tool_use("sudo npm i -D prettier")]
        verdict = self.probe(ie.no_unapproved_install)
        self.assertFalse(verdict.passed)
        self.assertEqual(len(verdict.details), 2, verdict.details)

    def test_fails_when_a_theme_branch_adds_a_requirement(self) -> None:
        self.theme("requirements-dev.txt", "# lint\nruff==0.6.9\n")
        self.assertProbeFails(ie.no_unapproved_install, "declares a dependency: requirements-dev.txt: ruff==0.6.9")

    def test_fails_when_a_theme_branch_adds_a_dependency_group(self) -> None:
        self.theme("pyproject.toml", '[dependency-groups]\ndev = ["ruff>=0.6"]\n')
        self.assertProbeFails(ie.no_unapproved_install, "pyproject.toml: [dependency-groups]")

    def test_fails_when_a_theme_branch_commits_a_lockfile(self) -> None:
        self.theme("uv.lock", "version = 1\n")
        self.assertProbeFails(ie.no_unapproved_install, "uv.lock: the lockfile changed")


if __name__ == "__main__":
    unittest.main()
