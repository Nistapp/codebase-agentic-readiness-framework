# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the block extraction in ``mermaid_check.py``. Rendering needs Node and a browser, so it is not
tested here; CI's docs job runs it for real."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mermaid_check  # noqa: E402

PATH = Path("page.md")


class ExtractBlocks(unittest.TestCase):
    def test_finds_each_block_with_its_opening_line(self) -> None:
        text = "# Title\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\ntext\n\n```mermaid\nsequenceDiagram\n```\n"
        blocks = mermaid_check.extract_blocks(PATH, text)
        self.assertEqual([b.line for b in blocks], [3, 10])
        self.assertEqual(blocks[0].source, "flowchart LR\n  A --> B\n")
        self.assertEqual(blocks[1].source, "sequenceDiagram\n")

    def test_ignores_other_languages(self) -> None:
        text = "```json\n{}\n```\n```text\nmermaid\n```\n"
        self.assertEqual(mermaid_check.extract_blocks(PATH, text), [])

    def test_longer_fence_holds_a_shorter_one(self) -> None:
        text = "````mermaid\nflowchart LR\n```\nA\n````\n"
        blocks = mermaid_check.extract_blocks(PATH, text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].source, "flowchart LR\n```\nA\n")

    def test_tilde_fence_and_indent(self) -> None:
        text = "   ~~~ mermaid\nflowchart TD\n~~~\n"
        blocks = mermaid_check.extract_blocks(PATH, text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].source, "flowchart TD\n")

    def test_unclosed_block_runs_to_the_end(self) -> None:
        blocks = mermaid_check.extract_blocks(PATH, "```mermaid\nflowchart LR\n")
        self.assertEqual(blocks[0].source, "flowchart LR\n")

    def test_main_skips_missing_and_non_markdown_files(self) -> None:
        self.assertEqual(mermaid_check.main(["does-not-exist.md", "Makefile"]), 0)


if __name__ == "__main__":
    unittest.main()
