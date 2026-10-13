# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The facts file stays under 30 KB on a realistic, large tree, not only on the schema's synthetic worst case.

`test_facts_schema.py`'s `WorstCaseTests` already proves the mathematical worst case, every list at its cap and
every string at its length, fits in 30 KB. This module instead builds a tree of 10,000 files that the tool actually
walks: 100 directories, each with its own manifest (registered as a workspace member, so `components.declared`
genuinely exceeds its cap) and its own `AGENTS.md` (so `instruction_files` genuinely exceeds its cap too), plus a
spread of source, doc, script and binary files for several kinds. If either test fails, the fix is a lower cap or a
shorter string, not a higher bound. Standard library only.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from test_facts import call

DIRECTORIES = 100
FILES_PER_DIRECTORY = 100
BOUND_BYTES = 30_000
EXTENSIONS = (".py", ".md", ".sh", ".png")


def build_large_tree(root: Path) -> Path:
    """A plain (non-git) tree of at least 10,000 files: a workspace root plus `DIRECTORIES` member packages."""
    target = root / "repo"
    target.mkdir()
    (target / "package.json").write_text(json.dumps({"name": "root", "workspaces": ["packages/*"]}), encoding="utf-8")
    for number in range(DIRECTORIES):
        directory = target / "packages" / f"pkg{number}"
        directory.mkdir(parents=True)
        (directory / "package.json").write_text(json.dumps({"name": f"pkg{number}"}), encoding="utf-8")
        (directory / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
        for index in range(FILES_PER_DIRECTORY - 2):
            extension = EXTENSIONS[index % len(EXTENSIONS)]
            path = directory / f"file{index}{extension}"
            if extension == ".png":
                path.write_bytes(b"\x00\x01")
            else:
                path.write_text("x\n", encoding="utf-8")
    return target


class BoundTests(unittest.TestCase):
    def test_a_ten_thousand_file_tree_gives_a_file_at_or_below_30_kb(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = build_large_tree(root)
            total = sum(1 for path in repo.rglob("*") if path.is_file())
            self.assertGreaterEqual(total, 10_000)
            out = root / "facts.json"
            code, envelope, err = call([str(repo), "--out", str(out)])
            self.assertEqual(code, 0, (envelope, err))
            size = out.stat().st_size
            self.assertLessEqual(
                size, BOUND_BYTES, f"a {total}-file tree gives {size} bytes; lower a cap, not the bound"
            )
            document = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(document["inventory"]["files"], total)
            self.assertFalse(document["inventory"]["truncated"])
            # The caps actually bite on a tree this size, so the bound holds under real omission, not luck.
            self.assertGreater(document["caps"]["instruction_files"]["omitted"], 0)
            self.assertGreater(document["caps"]["declared_components"]["omitted"], 0)


if __name__ == "__main__":
    unittest.main()
