# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The implement eval's boundary probes on hand-made runs, with no agent (RF4.11).

Each probe in `implement_eval.py` scores one boundary of `dev/consistency-map.json` that no assertion scored before.
As in `test_implement_eval.py`, each runs on a materialised scenario and a synthetic stream-json transcript: a run
that keeps the rule must pass, and each way of breaking it must fail. Standard library only; no network, no `claude`.
"""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
