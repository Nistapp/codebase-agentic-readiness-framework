# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The engine page ``02-check-catalogue.md`` lists the engine's checks as the registry declares them.

The page's check tables carry hand-written evidence rules, which the registry does not hold, so the tables are
checked here rather than generated. Each row's ID, title, tier, severity and status must agree with the registry,
in the registry's order, and the summary table must count what the rows hold.
"""

from __future__ import annotations

import re
import unittest
from collections import Counter
from typing import Any

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import build_catalogue
from _dev_paths import REPO

PAGE = REPO / "audit/engine/docs/architecture/contributor-deep-dive/02-check-catalogue.md"
ROW = re.compile(r"^\| `([A-Z]{2,5}-[0-9]{2})` \| (.+) \|$")
SUMMARY_ROW = re.compile(r"^\| `([A-Z]{2,5})` [^|]+\| (\d+) \| (\S+) \| (\S+) \| (\S+) \|$")
EMITTER_TIER = "—"


def page_rows() -> list[tuple[str, list[str]]]:
    """Each check row of the page, in page order: the ID and the other cells."""
    rows: list[tuple[str, list[str]]] = []
    for line in PAGE.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            rows.append((match.group(1), [cell.strip() for cell in match.group(2).split(" | ")]))
    return rows


def summary_rows() -> dict[str, tuple[int, int, int, int]]:
    """The summary table: each family's check count and its counts of tier A, B and C."""
    found: dict[str, tuple[int, int, int, int]] = {}
    for line in PAGE.read_text(encoding="utf-8").splitlines():
        match = SUMMARY_ROW.match(line)
        if match:
            counts = [0 if cell == "—" else int(cell) for cell in match.groups()[2:]]
            found[match.group(1)] = (int(match.group(2)), counts[0], counts[1], counts[2])
    return found


class EngineCheckPage(unittest.TestCase):
    engine: list[dict[str, Any]]
    rows: list[tuple[str, list[str]]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = build_catalogue.engine_checks(REPO)
        cls.rows = page_rows()

    def test_the_rows_are_the_engine_checks_in_registry_order(self) -> None:
        self.assertEqual([check_id for check_id, _ in self.rows], [check["id"] for check in self.engine])

    def test_each_row_agrees_with_the_registry(self) -> None:
        by_id = {check["id"]: check for check in self.engine}
        for check_id, cells in self.rows:
            check = by_id[check_id]
            with self.subTest(check=check_id):
                self.assertEqual(cells[0].replace("`", ""), check["title"], "the title differs from the registry's")
                tier = "Emitter" if check["tier"] == EMITTER_TIER else check["tier"]
                self.assertEqual(cells[1], tier)
                if len(cells) == 5:
                    if check["scored"]:
                        self.assertEqual(cells[2], check["severity"])
                    else:
                        self.assertIn(cells[2], ("*informational*", "—"), "an unscored check shows no severity")
                else:
                    self.assertFalse(check["scored"], "a row without a severity column is an informational check")
                self.assertEqual(cells[-1].startswith("Implemented"), check["status"] == "implemented")

    def test_the_summary_counts_the_scored_checks_and_the_emitter(self) -> None:
        counted = [c for c in self.engine if c["scored"] or c["tier"] == EMITTER_TIER]
        expected: dict[str, tuple[int, int, int, int]] = {}
        for family in dict.fromkeys(c["pack"] for c in counted):
            tiers = Counter(c["tier"] for c in counted if c["pack"] == family)
            total = sum(tiers.values())
            expected[family] = (total, tiers["A"], tiers["B"], tiers["C"])
        self.assertEqual(summary_rows(), expected)


if __name__ == "__main__":
    unittest.main()
