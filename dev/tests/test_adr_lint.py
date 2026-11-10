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


class TreeCase(unittest.TestCase):
    """Builds a throwaway repository from a mapping of paths to text."""

    def tree(self, files: dict[str, str]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root


class LintTree(TreeCase):
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


ENGINE_ADR = "audit/engine/docs/architecture/adrs/0001-use-one-thing.md"
ROOT_ROW = "[0001](../../../audit/engine/docs/architecture/adrs/0001-use-one-thing.md)\n"


class EngineIndex(TreeCase):
    def test_an_engine_adr_listed_in_both_indexes_passes(self) -> None:
        root = self.tree(
            {ENGINE_ADR: GOOD, adr_lint.INDEX: ROOT_ROW, adr_lint.ENGINE_INDEX: "[0001](adrs/0001-use-one-thing.md)\n"}
        )
        self.assertEqual(adr_lint.lint(root), [])

    def test_an_engine_adr_missing_from_the_engine_index_fails(self) -> None:
        root = self.tree({ENGINE_ADR: GOOD, adr_lint.INDEX: ROOT_ROW, adr_lint.ENGINE_INDEX: "No rows.\n"})
        self.assertEqual(adr_lint.lint(root), [f"{ENGINE_ADR}:1: no row in {adr_lint.ENGINE_INDEX}"])

    def test_the_engine_index_linking_a_deleted_adr_fails(self) -> None:
        engine_index = "[0001](adrs/0001-use-one-thing.md) [0002](adrs/0002-gone.md)\n"
        root = self.tree({ENGINE_ADR: GOOD, adr_lint.INDEX: ROOT_ROW, adr_lint.ENGINE_INDEX: engine_index})
        self.assertEqual(
            adr_lint.lint(root),
            [f"{adr_lint.ENGINE_INDEX}: links audit/engine/docs/architecture/adrs/0002-gone.md, which does not exist"],
        )

    def test_a_missing_engine_index_fails_only_when_the_engine_has_adrs(self) -> None:
        root = self.tree({ENGINE_ADR: GOOD, adr_lint.INDEX: ROOT_ROW})
        self.assertEqual(adr_lint.lint(root), [f"{adr_lint.ENGINE_INDEX}: the ADR index is missing"])
        root = self.tree(
            {
                "spec/decisions/0001-use-one-thing.md": GOOD,
                adr_lint.INDEX: "[0001](../../../spec/decisions/0001-use-one-thing.md)\n",
            }
        )
        self.assertEqual(adr_lint.lint(root), [])


class Mentions(TreeCase):
    def base(self, extra: dict[str, str]) -> Path:
        files = {
            "docs/architecture/adrs/0001-use-one-thing.md": GOOD,
            adr_lint.INDEX: "[0001](0001-use-one-thing.md)\n",
        }
        return self.tree({**files, **extra})

    def test_a_mention_of_an_existing_adr_passes(self) -> None:
        root = self.base({"docs/page.md": "See ADR 0001, ADR-0001 and ADR 1, and adrs/0001-use-one-thing.md.\n"})
        self.assertEqual(adr_lint.lint(root), [])

    def test_a_number_no_folder_holds_fails(self) -> None:
        root = self.base({"docs/page.md": "Intro.\nSee ADR 0007 for the old rule.\n"})
        self.assertEqual(adr_lint.lint(root), ["docs/page.md:2: names ADR 0007, which no ADR folder holds"])

    def test_a_path_to_a_deleted_adr_fails(self) -> None:
        root = self.base({"README.md": "Read `docs/architecture/adrs/0003-old-rule.md`.\n"})
        self.assertEqual(adr_lint.lint(root), ["README.md:1: names 0003-old-rule.md, which no ADR folder holds"])

    def test_history_scratch_fixtures_and_greenfield_are_not_read(self) -> None:
        stale = "ADR 0009 was removed.\n"
        root = self.base(
            {
                "CHANGELOG.md": stale,
                "artefacts/notes.md": stale,
                "audit/engine/tests/fixtures/x/README.md": stale,
                "dev/dist/skills/x.md": stale,
                "greenfield/templates/docs/x.md": stale,
            }
        )
        self.assertEqual(adr_lint.lint(root), [])


class ThisRepository(unittest.TestCase):
    def test_every_adr_here_follows_the_policy(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(adr_lint.main([str(REPO)]), 0)
        self.assertIn("follow docs/ADR_POLICY.md", out.getvalue())


if __name__ == "__main__":
    unittest.main()
