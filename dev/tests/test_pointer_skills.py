# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The pointer skills in `.claude/skills/` name a recipe that exists, under their own folder name.

A clone gives Claude Code these two skills, so "audit <repo>" and "start implementing the fixes" start the recipes
with no install step (v0.3, owner decision U1). Each pointer holds no copy of a recipe; this test keeps the pointer
and the recipe it names in step.
"""

from __future__ import annotations

import re
import unittest

import _dev_paths

SKILLS = _dev_paths.REPO / ".claude" / "skills"
EXPECTED = {"agentic-readiness-audit": "audit/SKILL.md", "agentic-readiness-implement": "implement/SKILL.md"}
FRONTMATTER = re.compile(r"\A---\nname: (?P<name>[^\n]+)\ndescription: (?P<description>[^\n]+)\n---\n")


class PointerSkillTests(unittest.TestCase):
    def test_each_pointer_names_its_folder_and_an_existing_recipe(self) -> None:
        for folder, recipe in EXPECTED.items():
            with self.subTest(folder=folder):
                text = (SKILLS / folder / "SKILL.md").read_text(encoding="utf-8")
                match = FRONTMATTER.match(text)
                self.assertIsNotNone(match, "frontmatter must hold name and description")
                assert match is not None
                self.assertEqual(match["name"], folder)
                self.assertLessEqual(len(match["description"]), 1024)
                self.assertIn(f"`{recipe}`", text)
                self.assertTrue((_dev_paths.REPO / recipe).is_file(), recipe)

    def test_no_other_skill_is_tracked_there(self) -> None:
        found = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
        self.assertEqual(found, set(EXPECTED))


if __name__ == "__main__":
    unittest.main()
