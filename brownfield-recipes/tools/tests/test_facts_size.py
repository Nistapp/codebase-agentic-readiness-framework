# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The facts tool's `size` section: the engine's file count against Q30's thresholds, with no verdict.

Boundary tests call `facts.size_class` and `facts.size_section` directly, with a stub inventory built in-process, since
building a real inventory of a hundred thousand files is not a unit test. The end-to-end tests run the tool on a small
repository made in a temporary directory, as the other sections' tests do. Standard library only.
"""

from __future__ import annotations

import types
from typing import Any

import _paths  # noqa: F401
import facts
from test_facts import RepoCase

THRESHOLDS = {"small_below": 1000, "medium_below": 10000, "large_below": 100000}


def stub_inventory(files: int, *, truncated: bool = False, size: int = 1) -> Any:
    return types.SimpleNamespace(files=[types.SimpleNamespace(size=size) for _ in range(files)], truncated=truncated)


class BoundaryTests(RepoCase):
    """Each boundary from the roadmap's own pairs: 999/1,000, 9,999/10,000, 99,999/100,000."""

    def test_under_a_thousand_is_small(self) -> None:
        self.assertEqual(facts.size_class(files=999, truncated=False), "small")

    def test_a_thousand_is_medium(self) -> None:
        self.assertEqual(facts.size_class(files=1000, truncated=False), "medium")

    def test_under_ten_thousand_is_medium(self) -> None:
        self.assertEqual(facts.size_class(files=9999, truncated=False), "medium")

    def test_ten_thousand_is_large(self) -> None:
        self.assertEqual(facts.size_class(files=10000, truncated=False), "large")

    def test_under_a_hundred_thousand_is_large(self) -> None:
        self.assertEqual(facts.size_class(files=99999, truncated=False), "large")

    def test_a_hundred_thousand_is_huge(self) -> None:
        self.assertEqual(facts.size_class(files=100000, truncated=False), "huge")

    def test_zero_files_is_small(self) -> None:
        self.assertEqual(facts.size_class(files=0, truncated=False), "small")


class TruncatedTests(RepoCase):
    def test_a_truncated_walk_is_huge_whatever_its_count(self) -> None:
        for files in (0, 1, 999, 1000, 50_000, 99_999, 100_000):
            with self.subTest(files=files):
                self.assertEqual(facts.size_class(files=files, truncated=True), "huge")


class SectionShapeTests(RepoCase):
    def test_the_section_is_the_inventorys_own_counts_and_the_thresholds(self) -> None:
        section = facts.size_section(stub_inventory(3, size=10))
        self.assertEqual(list(section), ["class", "files", "bytes", "truncated", "thresholds"])
        self.assertEqual(
            section, {"class": "small", "files": 3, "bytes": 30, "truncated": False, "thresholds": THRESHOLDS}
        )

    def test_bytes_is_the_sum_of_every_files_size(self) -> None:
        inventory = types.SimpleNamespace(files=[types.SimpleNamespace(size=n) for n in (1, 20, 300)], truncated=False)
        self.assertEqual(facts.size_section(inventory)["bytes"], 321)

    def test_truncated_is_carried_through_and_wins_over_the_count(self) -> None:
        section = facts.size_section(stub_inventory(3, truncated=True))
        self.assertEqual((section["class"], section["files"], section["truncated"]), ("huge", 3, True))

    def test_the_thresholds_are_always_the_same_three_numbers(self) -> None:
        self.assertEqual(facts.size_section(stub_inventory(0))["thresholds"], THRESHOLDS)
        self.assertEqual(facts.size_section(stub_inventory(100_000, truncated=True))["thresholds"], THRESHOLDS)
        self.assertEqual((facts.SMALL_BELOW, facts.MEDIUM_BELOW, facts.LARGE_BELOW), (1000, 10000, 100000))


class ToolIntegrationTests(RepoCase):
    def written_size(self, *extra: str) -> dict[str, Any]:
        if self.out.exists():
            self.out.unlink()
        self.run_ok(*extra)
        document: dict[str, Any] = self.written()
        size: dict[str, Any] = document["size"]
        return size

    def test_a_small_repository_is_small(self) -> None:
        size = self.written_size()
        self.assertEqual(size, {"class": "small", "files": 1, "bytes": 2, "truncated": False, "thresholds": THRESHOLDS})

    def test_the_counts_always_equal_the_inventorys_own(self) -> None:
        self.fill({"a.txt": "x\n", "b.txt": "x\n", "c.txt": "x\n"})
        self.run_ok()
        document = self.written()
        size, inventory = document["size"], document["inventory"]
        self.assertEqual(
            (size["files"], size["bytes"], size["truncated"]),
            (inventory["files"], inventory["bytes"], inventory["truncated"]),
        )
        excluded_size = self.written_size("--exclude", "a.txt")
        excluded_inventory = self.written()["inventory"]
        self.assertEqual(
            (excluded_size["files"], excluded_size["bytes"]), (excluded_inventory["files"], excluded_inventory["bytes"])
        )

    def test_a_walk_the_cap_cut_short_is_huge_whatever_its_count(self) -> None:
        self.fill({"a.txt": "x\n", "b.txt": "x\n", "c.txt": "x\n"})
        size = self.written_size("--max-files", "2")
        self.assertEqual(size, {"class": "huge", "files": 2, "bytes": 4, "truncated": True, "thresholds": THRESHOLDS})

    def test_a_walk_that_just_fits_the_cap_is_not_truncated_or_huge(self) -> None:
        self.fill({"a.txt": "x\n", "b.txt": "x\n"})
        size = self.written_size("--max-files", "3")
        self.assertEqual((size["class"], size["truncated"]), ("small", False))


if __name__ == "__main__":
    import unittest

    unittest.main()
