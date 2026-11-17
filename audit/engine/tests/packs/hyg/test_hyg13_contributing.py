# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`HYG-13` reads what a CONTRIBUTING document says, where `HYG-05` only reports that it exists.

Three items count (P9.3.3 a to c): (a) a pointer to the setup command, a link to `README.md` or `AGENTS.md` or a named
setup command; (b) the gate command, and a paragraph that says CI runs the same; (c) the rules for branches, commits
and pull requests. All three is `PASS`, one or two `PARTIAL`, none `FAIL`. With no CONTRIBUTING document the check is
`UNKNOWN`, because `HYG-05` owns that finding. The check is informational and never scored.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks.hyg import check_hyg05, check_hyg13  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "HYG-13"

#: (a) a link to the setup command in README.md.
SETUP = "## Setup\n\nSet up your machine with the commands in [`README.md`](README.md#development).\n"
#: (b) the gate command, and CI runs the same.
GATE = "## The gate\n\nRun `make check` before each pull request.\nCI runs the same command.\n"
#: (c) branches, commits and pull requests.
WORKFLOW = (
    "## Branches\n\nBranch from `main` as `<type>/<topic>`.\n\n"
    "## Commits\n\nEach commit subject follows Conventional Commits.\n\n"
    "## Pull requests\n\nA maintainer reviews and squash-merges each pull request.\n"
)
THIN = "# Contributing\n\nThank you for your interest. Please be kind, and open an issue to discuss an idea.\n"


class Hyg13ContributingTests(unittest.TestCase):
    def run_check(self, files: dict[str, str], check=check_hyg13, check_id: str = CHECK_ID):
        """Run a check in-process (so coverage traces it) on a repository built from ``files``."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "src/app.py", "print('hi')\n")
            for rel, text in files.items():
                support.write(root, rel, text)
            inventory = build_inventory(root)
            return check(
                spec=REGISTRY_BY_ID[check_id],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )

    def evidence(self, outcome) -> list[tuple[str, int | None, str | None]]:
        return [(e.path, e.line, e.note) for finding in outcome.findings for e in finding.evidence]

    def test_all_three_items_pass_with_each_line_in_the_summary(self):
        outcome = self.run_check({"CONTRIBUTING.md": "# Contributing\n\n" + SETUP + "\n" + GATE + "\n" + WORKFLOW})
        self.assertEqual(outcome.verdict.value, "PASS")
        self.assertEqual(outcome.findings, [])
        self.assertIn("setup pointer at CONTRIBUTING.md:5", outcome.summary)
        self.assertIn("gate command at CONTRIBUTING.md:9", outcome.summary)
        self.assertIn("CI runs it at CONTRIBUTING.md:10", outcome.summary)
        self.assertIn("pull requests at CONTRIBUTING.md:", outcome.summary)

    def test_a_named_setup_command_counts_as_the_pointer(self):
        text = "# Contributing\n\nRun `npm ci` once after you clone.\n\n" + GATE + "\n" + WORKFLOW
        self.assertEqual(self.run_check({"CONTRIBUTING.md": text}).verdict.value, "PASS")

    def test_the_greenfield_templates_pass(self):
        """A copy of the whole `greenfield/templates/` tree, read as the engine reads a target (R11)."""
        templates = Path(__file__).resolve().parents[5] / "greenfield" / "templates"
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "templates"
            shutil.copytree(templates, copy)
            inventory = build_inventory(copy)
            outcome = check_hyg13(
                spec=REGISTRY_BY_ID[CHECK_ID],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        self.assertEqual(outcome.verdict.value, "PASS", outcome.summary)
        self.assertIn("CONTRIBUTING.md:", outcome.summary)

    def test_one_item_is_partial_and_names_the_two_missing(self):
        outcome = self.run_check({"CONTRIBUTING.md": "# Contributing\n\n" + WORKFLOW})
        self.assertEqual(outcome.verdict.value, "PARTIAL")
        self.assertIn("1 of 3", outcome.summary)
        self.assertIn("a pointer to the setup command", outcome.summary)
        self.assertIn("the gate command, and that CI runs the same", outcome.summary)
        self.assertEqual(len(outcome.findings), 1)
        notes = {note for _, _, note in self.evidence(outcome)}
        self.assertTrue({"branches", "commits", "pull requests"} <= notes)
        self.assertTrue(all(line for _, line, _ in self.evidence(outcome)), "every evidence item has a line")

    def test_two_items_are_partial(self):
        outcome = self.run_check({"CONTRIBUTING.md": "# Contributing\n\n" + SETUP + "\n" + GATE})
        self.assertEqual(outcome.verdict.value, "PARTIAL")
        self.assertIn("2 of 3", outcome.summary)
        self.assertIn("the rules for branches, commits and pull requests", outcome.summary)
        self.assertIn(("CONTRIBUTING.md", 5, "setup pointer"), self.evidence(outcome))

    def test_a_gate_command_without_ci_does_not_count(self):
        text = "# Contributing\n\n" + SETUP + "\nRun `make check` before each pull request.\n\n" + WORKFLOW
        outcome = self.run_check({"CONTRIBUTING.md": text})
        self.assertEqual(outcome.verdict.value, "PARTIAL")
        self.assertIn("missing: the gate command, and that CI runs the same", outcome.summary)

    def test_ci_without_a_gate_command_does_not_count(self):
        text = "# Contributing\n\n" + SETUP + "\nCI runs the same tests as you do.\n\n" + WORKFLOW
        self.assertEqual(self.run_check({"CONTRIBUTING.md": text}).verdict.value, "PARTIAL")

    def test_two_of_the_three_workflow_subjects_do_not_count(self):
        gate = "Run `make check` before you push.\nCI runs the same command.\n"
        text = "# Contributing\n\n" + SETUP + "\n" + gate + "\nBranch from `main`. Write one commit per change.\n"
        outcome = self.run_check({"CONTRIBUTING.md": text})
        self.assertEqual(outcome.verdict.value, "PARTIAL")
        self.assertIn("missing: the rules for branches, commits and pull requests", outcome.summary)

    def test_none_of_the_items_is_fail_with_the_file_and_line(self):
        outcome = self.run_check({"CONTRIBUTING.md": THIN})
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertIn("0 of 3", outcome.summary)
        self.assertEqual(self.evidence(outcome), [("CONTRIBUTING.md", 1, "contributing file")])
        self.assertEqual(outcome.findings[0].path, "CONTRIBUTING.md")

    def test_no_contributing_document_is_unknown_and_hyg_05_owns_it(self):
        outcome = self.run_check({"README.md": "# App\n"})
        self.assertEqual(outcome.verdict.value, "UNKNOWN")
        self.assertIn("HYG-05", outcome.summary)
        self.assertEqual(outcome.findings, [])
        self.assertEqual(self.run_check({}, check=check_hyg05, check_id="HYG-05").verdict.value, "FAIL")

    def test_a_component_contributing_file_is_not_the_repositorys(self):
        outcome = self.run_check({"packages/web/CONTRIBUTING.md": SETUP + GATE + WORKFLOW})
        self.assertEqual(outcome.verdict.value, "UNKNOWN")

    def test_a_file_under_docs_is_read(self):
        outcome = self.run_check({"docs/CONTRIBUTING.md": "# Contributing\n\n" + SETUP + "\n" + GATE + "\n" + WORKFLOW})
        self.assertEqual(outcome.verdict.value, "PASS")
        self.assertIn("docs/CONTRIBUTING.md:5", outcome.summary)

    def test_a_file_under_github_is_read(self):
        outcome = self.run_check({".github/CONTRIBUTING.md": THIN})
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual(outcome.findings[0].path, ".github/CONTRIBUTING.md")

    def test_a_relative_link_from_github_counts(self):
        text = "# Contributing\n\nSetup: [the README](../README.md).\n\n" + GATE + "\n" + WORKFLOW
        self.assertEqual(self.run_check({".github/CONTRIBUTING.md": text}).verdict.value, "PASS")

    def test_items_combine_across_two_contributing_files(self):
        outcome = self.run_check({"CONTRIBUTING.md": SETUP + "\n" + GATE, "docs/CONTRIBUTING.md": WORKFLOW})
        self.assertEqual(outcome.verdict.value, "PASS")

    def test_hyg_05_still_reads_presence_only(self):
        outcome = self.run_check({"CONTRIBUTING.md": THIN}, check=check_hyg05, check_id="HYG-05")
        self.assertEqual(outcome.verdict.value, "PASS")

    def test_the_check_is_informational_cosmetic_and_implemented(self):
        spec = REGISTRY_BY_ID[CHECK_ID]
        self.assertEqual(
            (spec.scored, spec.severity.value, spec.status, spec.tier), (False, "COSMETIC", "implemented", "B")
        )
        self.assertNotIn("HYG-12", REGISTRY_BY_ID, "HYG-12 is reserved for the planned release-provenance check")

    def test_the_result_is_the_same_on_two_runs(self):
        files = {"CONTRIBUTING.md": "# Contributing\n\n" + SETUP + "\n" + WORKFLOW}
        first, second = self.run_check(files), self.run_check(files)
        self.assertEqual((first.summary, self.evidence(first)), (second.summary, self.evidence(second)))


if __name__ == "__main__":
    unittest.main()
