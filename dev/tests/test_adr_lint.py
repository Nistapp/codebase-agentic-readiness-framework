# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``adr_lint.py``: each policy rule, the index match, and this repository's own ADRs."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import adr_lint

REPO = Path(__file__).resolve().parents[2]

GOOD = """# 0001. Use One Thing

## Context

Why.

## Decision

What.

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| Another thing | A superseded design would be loaded as current. |

## Consequences

- A result.
"""


class LintAdr(unittest.TestCase):
    def problems(self, text: str, name: str = "0001-use-one-thing.md") -> list[str]:
        return adr_lint.lint_adr(Path(name), text)

    def test_a_lean_adr_passes(self) -> None:
        self.assertEqual(self.problems(GOOD), [])

    def test_the_title_must_carry_the_file_number(self) -> None:
        self.assertEqual(self.problems(GOOD, "0002-use-one-thing.md"), ["1: the title must open with '# 0002. '"])

    def test_each_lifecycle_field_fails_with_its_line(self) -> None:
        for field in ("* **Status:** Accepted", "* **Date:** 2026-11-10", "Last reviewed: 2026-11-10", "- Deciders: x"):
            with self.subTest(field=field):
                text = GOOD.replace("## Context", f"{field}\n\n## Context", 1)
                problems = self.problems(text)
                self.assertEqual(len(problems), 1, problems)
                self.assertTrue(problems[0].startswith("3: lifecycle field"), problems)

    def test_a_lifecycle_footer_fails(self) -> None:
        problems = self.problems(GOOD + "\n## Lifecycle — Living, Current-State ADRs\n\n- Rules.\n")
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("lifecycle section", problems[0])

    def test_a_tombstone_fails(self) -> None:
        problems = self.problems(GOOD.replace("## Context", "> Superseded by 0002.\n\n## Context", 1))
        self.assertEqual(problems, ["3: retired-ADR marker; delete the ADR or overwrite it in place"])

    def test_a_missing_section_fails(self) -> None:
        text = GOOD.replace("## Alternatives Considered", "## Options", 1)
        self.assertEqual(
            self.problems(text),
            ["1: sections must be " + ", ".join(adr_lint.SECTIONS) + " (missing Alternatives Considered)"],
        )

    def test_sections_out_of_order_fail(self) -> None:
        text = (
            GOOD.replace("## Context", "## Swap", 1)
            .replace("## Decision", "## Context", 1)
            .replace("## Swap", "## Decision", 1)
        )
        self.assertEqual(
            self.problems(text), ["1: sections must be " + ", ".join(adr_lint.SECTIONS) + " (out of order)"]
        )


class LintTree(unittest.TestCase):
    def tree(self, files: dict[str, str]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def test_an_indexed_set_in_two_folders_passes(self) -> None:
        root = self.tree(
            {
                "docs/architecture/adrs/0001-use-one-thing.md": GOOD,
                "spec/decisions/0001-use-one-thing.md": GOOD,
                adr_lint.INDEX: "[0001](0001-use-one-thing.md)\n[0001](../../../spec/decisions/0001-use-one-thing.md#context)\n",
            }
        )
        self.assertEqual(adr_lint.lint(root), [])

    def test_an_unindexed_adr_fails(self) -> None:
        root = self.tree({"spec/decisions/0001-use-one-thing.md": GOOD, adr_lint.INDEX: "No rows.\n"})
        self.assertEqual(adr_lint.lint(root), [f"spec/decisions/0001-use-one-thing.md:1: no row in {adr_lint.INDEX}"])

    def test_an_index_row_to_a_deleted_adr_fails(self) -> None:
        root = self.tree({adr_lint.INDEX: "[0003](0003-gone.md) and [web](https://example.org/0004-x.md)\n"})
        self.assertEqual(
            adr_lint.lint(root), [f"{adr_lint.INDEX}: links docs/architecture/adrs/0003-gone.md, which does not exist"]
        )

    def test_a_missing_index_fails(self) -> None:
        root = self.tree({"spec/decisions/0001-use-one-thing.md": GOOD})
        self.assertEqual(adr_lint.lint(root), [f"{adr_lint.INDEX}: the ADR index is missing"])

    def test_main_returns_one_and_prints_each_failure(self) -> None:
        root = self.tree({adr_lint.INDEX: "", "spec/decisions/0001-use-one-thing.md": "# 0001. T\n"})
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(adr_lint.main([str(root)]), 1)
        self.assertIn("sections must be", err.getvalue())
        self.assertIn("no row in", err.getvalue())

    def test_main_returns_two_for_a_missing_root(self) -> None:
        with redirect_stderr(io.StringIO()):
            self.assertEqual(adr_lint.main([str(REPO / "no-such-dir")]), 2)


class ThisRepository(unittest.TestCase):
    def test_every_adr_here_follows_the_policy(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(adr_lint.main([str(REPO)]), 0)
        self.assertIn("follow docs/ADR_POLICY.md", out.getvalue())


if __name__ == "__main__":
    unittest.main()
