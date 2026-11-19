# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The consistency map, ``dev/consistency-map.json``, against its schema, the catalogue and the engine's constants.

Every check in ``audit/catalogue.json`` has exactly one reads entry, in catalogue order. A reads entry that names
engine constants (``module:NAME``) must list exactly the paths those constants hold, so a file added to or removed
from a check's list in the engine fails this test until the map follows (ADR 0012).
"""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from typing import Any
from unittest import mock

import _dev_paths
from test_consistency_map_schema import SCHEMA, _problems

ENGINE = _dev_paths.REPO / "audit" / "engine"
MAP: dict[str, Any] = json.loads((_dev_paths.DEV / "consistency-map.json").read_text(encoding="utf-8"))
CATALOGUE_IDS: list[str] = [
    check["id"]
    for check in json.loads((_dev_paths.REPO / "audit" / "catalogue.json").read_text(encoding="utf-8"))["checks"]
]


def _engine_module(name: str) -> Any:
    if str(ENGINE) not in sys.path:
        sys.path.insert(0, str(ENGINE))
    return importlib.import_module(name)


def _constant_values(reference: str) -> tuple[set[str], list[str]]:
    """The strings a ``module:NAME`` constant holds, and the problems found while reading it."""
    module_name, _, attribute = reference.partition(":")
    module = _engine_module(module_name)
    if not hasattr(module, attribute):
        return set(), [f"{reference}: no such constant"]
    value = getattr(module, attribute)
    if not isinstance(value, (tuple, list, frozenset, set)) or not all(isinstance(item, str) for item in value):
        return set(), [f"{reference}: not a tuple, list or set of strings"]
    return set(value), []


def constant_problems(read: dict[str, Any]) -> list[str]:
    """Differences between a reads entry's paths and the union of the engine constants it names."""
    references = read.get("constants", [])
    if not references:
        return []
    held: set[str] = set()
    problems: list[str] = []
    for reference in references:
        values, found = _constant_values(reference)
        held |= values
        problems += found
    declared = {where["path"] for where in read["where"]}
    check = read["check"]
    problems += [f"{check}: the engine reads {path!r}, the map does not list it" for path in sorted(held - declared)]
    problems += [f"{check}: the map lists {path!r}, the engine constants do not" for path in sorted(declared - held)]
    return problems


class MapShapeTest(unittest.TestCase):
    def test_the_map_follows_its_schema(self) -> None:
        self.assertEqual(_problems(MAP, SCHEMA), [])


class ReadsCoverageTest(unittest.TestCase):
    def test_every_catalogue_check_has_one_reads_entry_in_catalogue_order(self) -> None:
        self.assertEqual([read["check"] for read in MAP["reads"]], CATALOGUE_IDS)

    def test_each_place_is_listed_once_per_entry(self) -> None:
        for read in MAP["reads"]:
            places = [(where["path"], where["scope"]) for where in read["where"]]
            self.assertEqual(len(places), len(set(places)), read["check"])

    def test_a_window_is_given_only_with_a_window_binding(self) -> None:
        for read in MAP["reads"]:
            self.assertEqual("window" in read, read["binding"] == "window", read["check"])


class ConstantsTest(unittest.TestCase):
    def test_each_entry_matches_the_engine_constants_it_names(self) -> None:
        problems = [problem for read in MAP["reads"] for problem in constant_problems(read)]
        self.assertEqual(problems, [])

    def test_the_fast_path_entry_names_its_constant(self) -> None:
        (tst04,) = [read for read in MAP["reads"] if read["check"] == "TST-04"]
        self.assertIn("audit.rules.checks.tst:_FASTPATH_DOCS", tst04.get("constants", []))

    def test_a_name_removed_from_the_engine_list_fails(self) -> None:
        (tst04,) = [read for read in MAP["reads"] if read["check"] == "TST-04"]
        tst = _engine_module("audit.rules.checks.tst")
        shorter = tuple(name for name in tst._FASTPATH_DOCS if name != "CONTRIBUTING.md")
        with mock.patch.object(tst, "_FASTPATH_DOCS", shorter):
            problems = constant_problems(tst04)
        self.assertEqual(problems, ["TST-04: the map lists 'CONTRIBUTING.md', the engine constants do not"])

    def test_a_name_added_to_the_engine_list_fails(self) -> None:
        (tst04,) = [read for read in MAP["reads"] if read["check"] == "TST-04"]
        tst = _engine_module("audit.rules.checks.tst")
        with mock.patch.object(tst, "_FASTPATH_DOCS", (*tst._FASTPATH_DOCS, "docs/TESTING.md")):
            problems = constant_problems(tst04)
        self.assertEqual(problems, ["TST-04: the engine reads 'docs/TESTING.md', the map does not list it"])

    def test_an_unknown_constant_fails(self) -> None:
        read = {"check": "TST-04", "constants": ["audit.rules.checks.tst:_NO_SUCH_NAME"], "where": []}
        self.assertEqual(constant_problems(read), ["audit.rules.checks.tst:_NO_SUCH_NAME: no such constant"])


if __name__ == "__main__":
    unittest.main()
