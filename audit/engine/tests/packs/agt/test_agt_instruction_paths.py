# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Which files `AGT-01` and `AGT-08` see as instruction files, and the verdicts that follow, run in-process.

The variant table's paths are relative to the repository root. A plain name (`CLAUDE.md`) counts in any folder; a
path with a folder (`.github/copilot-instructions.md`) counts only as the whole path from the root.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.rules.checks.agt import MIN_INSTRUCTION_CHARS, check_agt01, check_agt08, instruction_paths  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

#: Long enough to be no stub, and free of every stub marker.
RULES = "Never weaken a failing test to get green. Never commit secrets or credentials.\n" * (
    MIN_INSTRUCTION_CHARS // 40
)

#: The harness paths with a folder and no wildcard that the variant table names.
FOLDER_PATHS = (
    ".github/copilot-instructions.md",
    ".devin/global_rules.md",
    ".junie/guidelines.md",
    ".junie/playbook.md",
    ".idx/airules.md",
    ".gemini/styleguide.md",
)


def run(files: dict[str, str]) -> tuple[set[str], dict[str, tuple[str, list[str]]]]:
    """The instruction paths of a repository built from `files`, and `AGT-01`'s and `AGT-08`'s verdicts and
    finding paths."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        inventory = build_inventory(root)
        outcomes = {}
        for check_id, check in (("AGT-01", check_agt01), ("AGT-08", check_agt08)):
            outcome = check(
                spec=REGISTRY_BY_ID[check_id],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
            outcomes[check_id] = (outcome.verdict.value, sorted(f.path for f in outcome.findings))
        return instruction_paths(inventory), outcomes


class FolderPathTests(unittest.TestCase):
    def test_each_folder_path_at_the_root_is_an_instruction_file(self):
        for rel in FOLDER_PATHS:
            with self.subTest(path=rel):
                paths, _ = run({rel: RULES})
                self.assertEqual(paths, {rel})

    def test_a_folder_path_below_the_root_is_not_one(self):
        paths, _ = run({"sub/.github/copilot-instructions.md": RULES})
        self.assertEqual(paths, set())

    def test_a_folder_path_whose_base_name_is_an_instruction_name_is_still_found(self):
        paths, _ = run({".claude/CLAUDE.md": RULES, ".junie/AGENTS.md": RULES})
        self.assertEqual(paths, {".claude/CLAUDE.md", ".junie/AGENTS.md"})

    def test_a_folder_path_alone_is_vendor_only_content_and_competes(self):
        for rel in FOLDER_PATHS:
            with self.subTest(path=rel):
                _, outcomes = run({rel: RULES})
                self.assertEqual(outcomes["AGT-01"], ("PARTIAL", ["vendor-only"]))
                self.assertEqual(outcomes["AGT-08"][0], "FAIL")
                self.assertIn("vendor-files", outcomes["AGT-08"][1])

    def test_a_folder_path_beside_agents_md_competes_with_it(self):
        _, outcomes = run({"AGENTS.md": RULES, ".github/copilot-instructions.md": RULES})
        self.assertEqual(outcomes["AGT-01"], ("PASS", []))
        self.assertEqual(outcomes["AGT-08"][0], "FAIL")
        self.assertIn("vendor-files", outcomes["AGT-08"][1])


#: A file straight in each `**/` rules folder of the variant table.
FLAT_RULE_FILES = (
    ".claude/rules/a.md",
    ".github/instructions/a.instructions.md",
    ".cursor/rules/a.mdc",
    ".devin/rules/a.md",
    ".windsurf/rules/a.md",
    ".continue/rules/a.md",
    ".amazonq/rules/a.md",
    ".kiro/steering/a.md",
    ".trae/rules/a.md",
    ".augment/rules/a.md",
)


class RuleFolderTests(unittest.TestCase):
    def test_a_rule_file_straight_in_its_rules_folder_is_an_instruction_file(self):
        for rel in FLAT_RULE_FILES:
            with self.subTest(path=rel):
                paths, _ = run({rel: RULES})
                self.assertEqual(paths, {rel})

    def test_a_rule_file_in_a_subfolder_is_still_one(self):
        paths, _ = run({".cursor/rules/team/a.mdc": RULES})
        self.assertEqual(paths, {".cursor/rules/team/a.mdc"})

    def test_a_file_of_another_type_in_the_rules_folder_is_not_one(self):
        paths, _ = run({".cursor/rules/a.md": RULES, ".github/instructions/a.md": RULES})
        self.assertEqual(paths, set())

    def test_a_flat_rule_file_alone_is_vendor_only_content_and_competes(self):
        _, outcomes = run({".cursor/rules/a.mdc": RULES})
        self.assertEqual(outcomes["AGT-01"], ("PARTIAL", ["vendor-only"]))
        self.assertEqual(outcomes["AGT-08"][0], "FAIL")
        self.assertIn("vendor-files", outcomes["AGT-08"][1])


class NestedOnlyTests(unittest.TestCase):
    """`AGT-01` passes only with `AGENTS.md` at the root; a nested one alone is content below the root."""

    def test_a_nested_agents_md_alone_is_partial(self):
        for rel in (".junie/AGENTS.md", "packages/api/AGENTS.md"):
            with self.subTest(path=rel):
                _, outcomes = run({rel: RULES})
                self.assertEqual(outcomes["AGT-01"], ("PARTIAL", ["nested-only"]))
                self.assertEqual(outcomes["AGT-08"], ("PASS", []))

    def test_a_nested_agents_md_beside_a_root_one_raises_no_finding(self):
        _, outcomes = run({"AGENTS.md": RULES, ".junie/AGENTS.md": RULES})
        self.assertEqual(outcomes["AGT-01"], ("PASS", []))

    def test_a_nested_agents_md_beside_a_vendor_file_has_both_findings(self):
        _, outcomes = run({"CLAUDE.md": RULES, "packages/api/AGENTS.md": RULES})
        self.assertEqual(outcomes["AGT-01"], ("PARTIAL", ["nested-only", "vendor-only"]))

    def test_the_finding_names_the_nested_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n in range(8):
                support.write(root, f"p{n}/AGENTS.md", RULES)
            inventory = build_inventory(root)
            outcome = check_agt01(
                spec=REGISTRY_BY_ID["AGT-01"],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        (finding,) = outcome.findings
        self.assertIn("AGENTS.md exists only below the root (p0/AGENTS.md, ", finding.statement)
        self.assertIn("p5/AGENTS.md…)", finding.statement)
        self.assertEqual(len(finding.evidence), 8)


class CompetitorWordingTests(unittest.TestCase):
    """`AGT-08`'s competitor finding says "alongside the canonical one" only when a root `AGENTS.md` exists."""

    def statement(self, files: dict[str, str]) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            inventory = build_inventory(root)
            outcome = check_agt08(
                spec=REGISTRY_BY_ID["AGT-08"],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        return next(f.statement for f in outcome.findings if f.path == "vendor-files")

    def test_beside_a_root_agents_md_the_files_are_alongside_the_canonical_one(self):
        self.assertIn(
            "1 vendor-specific instruction files exist alongside the canonical one (CLAUDE.md)",
            self.statement({"AGENTS.md": RULES, "CLAUDE.md": RULES}),
        )

    def test_without_a_root_agents_md_the_statement_says_there_is_none(self):
        for files in ({".claude/CLAUDE.md": RULES}, {"CLAUDE.md": RULES, ".junie/AGENTS.md": RULES}):
            with self.subTest(files=sorted(files)):
                statement = self.statement(files)
                self.assertIn("exist with no canonical AGENTS.md at the root (", statement)
                self.assertNotIn("alongside", statement)


if __name__ == "__main__":
    unittest.main()
