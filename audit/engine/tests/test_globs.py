# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Tests for the engine's one path-glob matcher (``audit.globs``) and its use by ``Inventory.match``."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit.globs import glob_match, path_match  # noqa: E402
from audit.rules import variants  # noqa: E402
from audit.rules.checks import agt  # noqa: E402
from audit.scan import FileEntry, Inventory, Kind  # noqa: E402


class GlobMatchTest(unittest.TestCase):
    def test_a_star_stays_inside_one_name(self) -> None:
        self.assertTrue(glob_match(".github/workflows/*.yml", ".github/workflows/ci.yml"))
        self.assertFalse(glob_match(".github/workflows/*.yml", ".github/workflows/reusable/ci.yml"))
        self.assertFalse(glob_match(".husky/*", ".husky/_/husky.sh"))

    def test_a_double_star_matches_any_number_of_folders_none_included(self) -> None:
        for path in ("docs/a.md", "docs/a/b.md", "docs/a/b/c.md"):
            with self.subTest(path=path):
                self.assertTrue(glob_match("docs/**/*.md", path))
        self.assertTrue(glob_match("a/**/b/**/*.md", "a/b/c.md"))
        self.assertTrue(glob_match(".opencode/**", ".opencode/node_modules/x/y.js"))
        self.assertTrue(glob_match("**/AGENTS.md", "AGENTS.md"))
        self.assertFalse(glob_match("docs/**/*.md", "src/docs/a.md"))

    def test_a_pattern_is_anchored_at_the_root(self) -> None:
        self.assertFalse(glob_match("CLAUDE.md", "pkg/CLAUDE.md"))
        self.assertFalse(glob_match(".roorules-*", "sub/.roorules-code"))

    def test_case_is_exact_unless_folded_as_the_platform_folds_it(self) -> None:
        self.assertFalse(glob_match("README*", "readme.md"))
        folded = glob_match("README*", "readme.md", fold_case=True)
        self.assertEqual(folded, sys.platform == "win32")

    def test_a_question_mark_and_a_class_match_one_character_of_a_name(self) -> None:
        self.assertTrue(glob_match("v?/[ab].txt", "v1/a.txt"))
        self.assertFalse(glob_match("v?/[ab].txt", "v1/c.txt"))
        self.assertFalse(glob_match("v?", "v/1"))


class PathMatchTest(unittest.TestCase):
    def test_a_pattern_with_no_slash_is_a_base_name_at_any_depth(self) -> None:
        self.assertTrue(path_match("*.csproj", "src/App/App.csproj"))
        self.assertTrue(path_match("package.json", "package.json"))
        self.assertFalse(path_match("Dockerfile*", "Dockerfile.d/run.sh"))

    def test_a_pattern_with_a_slash_is_a_glob_from_the_root(self) -> None:
        self.assertTrue(path_match(".devcontainer/*/devcontainer.json", ".devcontainer/node/devcontainer.json"))
        self.assertFalse(path_match(".devcontainer/*.json", ".devcontainer/node/devcontainer.json"))


def _inventory(*paths: str) -> Inventory:
    return Inventory(root=Path("."), files=[FileEntry(rel=p, size=1, kind=Kind.OTHER, has_text=True) for p in paths])


class InventoryMatchTest(unittest.TestCase):
    def test_match_finds_what_the_shared_matcher_finds(self) -> None:
        inventory = _inventory(
            ".github/workflows/ci.yml", ".github/workflows/reusable/ci.yml", ".husky/pre-commit", ".husky/_/husky.sh"
        )
        self.assertEqual(inventory.match(".github/workflows/*.yml"), [".github/workflows/ci.yml"])
        self.assertEqual(inventory.match(".husky/*"), [".husky/pre-commit"])
        self.assertEqual(inventory.match("ci.yml"), [".github/workflows/ci.yml", ".github/workflows/reusable/ci.yml"])


class InstructionGlobTest(unittest.TestCase):
    def test_a_file_straight_in_a_rules_folder_and_below_it_is_an_instruction_file(self) -> None:
        inventory = _inventory(".cursor/rules/a.mdc", ".cursor/rules/sub/b.mdc", ".junie/rules/sub/c.md")
        self.assertEqual(
            agt.instruction_paths(inventory),
            {".cursor/rules/a.mdc", ".cursor/rules/sub/b.mdc", ".junie/rules/sub/c.md"},
        )

    def test_a_generated_memory_bank_file_at_any_depth_is_no_instruction_file(self) -> None:
        self.assertTrue(agt.is_non_instruction(".amazonq/rules/memory-bank/a/b.md"))
        self.assertTrue(agt.is_non_instruction(".github/agents/team/AGENTS.md"))

    def test_a_harness_folder_pattern_also_names_the_file_of_that_name(self) -> None:
        self.assertTrue(variants._matches(".clinerules", (".clinerules/**",)))
        self.assertTrue(variants._matches(".roo/rules/a.md", (".roo/rules/**",)))
        self.assertFalse(variants._matches("pkg/CLAUDE.md", ("CLAUDE.md",)))


if __name__ == "__main__":
    unittest.main()
