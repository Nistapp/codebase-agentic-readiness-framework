# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""``fixtures/README.md`` lists every fixture folder and names no folder that is not there.

Two fixtures were once missing from the list and nothing noticed. This test keeps the list complete in both
directions. It reads the folder and the README in this process and runs no audit.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
README = FIXTURES / "README.md"
_NAME = r"[A-Za-z0-9][A-Za-z0-9._-]*"
# A row of the convention listing: two spaces, the folder name, a slash, then the description.
_ROW = re.compile(rf"^  ({_NAME})/(?:\s|$)", re.MULTILINE)


def _folders() -> set[str]:
    return {entry.name for entry in FIXTURES.iterdir() if entry.is_dir()}


def _mentions(text: str, name: str) -> bool:
    """True when ``name`` appears as a whole name, so ``stack-dotnet`` is not found inside ``stack-dotnet-locked``."""
    return re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w-])", text) is not None


class FixtureReadmeTests(unittest.TestCase):
    def test_every_fixture_folder_is_mentioned_in_the_readme(self):
        text = README.read_text(encoding="utf-8")
        missing = sorted(name for name in _folders() if not _mentions(text, name))
        self.assertEqual(missing, [], f"fixture folders with no mention in fixtures/README.md: {missing}")

    def test_every_folder_the_readme_lists_exists(self):
        text = README.read_text(encoding="utf-8")
        listed = set(_ROW.findall(text))
        self.assertTrue(listed, "the README convention listing was not found")
        unknown = sorted(listed - _folders())
        self.assertEqual(unknown, [], f"fixtures/README.md lists folders that do not exist: {unknown}")

    def test_the_mention_check_matches_whole_names_only(self):
        self.assertTrue(_mentions("  stack-dotnet-locked/ x", "stack-dotnet-locked"))
        self.assertFalse(_mentions("  stack-dotnet-locked/ x", "stack-dotnet"))


if __name__ == "__main__":
    unittest.main()
