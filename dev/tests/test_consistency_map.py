# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The consistency map, ``dev/consistency-map.json``, against its schema, the catalogue and the engine's constants.

Every check in ``audit/catalogue.json`` has exactly one reads entry, in catalogue order. A reads entry that names
engine constants (``module:NAME``) must list exactly the paths those constants hold, so a file added to or removed
from a check's list in the engine fails this test until the map follows (ADR 0012).

The names list holds the file names the engine gives a meaning to. A greenfield template whose scaffolded path
matches one needs a ``create`` moves entry with an ``intent``, so a template cannot take such a name by accident.

Every playbook Commits row has one moves entry. A ``kept`` keeps entry quotes, verbatim with whitespace collapsed,
a sentence that sits inside the section its address names, in the working tree.
"""

from __future__ import annotations

import fnmatch
import importlib
import json
import posixpath
import re
import sys
import unittest
from typing import Any
from unittest import mock

import _dev_paths
from docindex.extract import _section_nodes
from test_consistency_map_schema import SCHEMA, _problems

ENGINE = _dev_paths.REPO / "audit" / "engine"
BOOTSTRAP = _dev_paths.REPO / "greenfield" / "bootstrap"
TEMPLATES = _dev_paths.REPO / "greenfield" / "templates"
PLAYBOOKS = _dev_paths.REPO / "implement" / "playbooks"
_COMMITS_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
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


def name_matches(name: dict[str, Any], path: str) -> bool:
    """Whether a repository-relative path matches a names entry, as the entry's ``match`` and ``ignore_case`` say."""
    pattern = str(name["pattern"])
    if name.get("ignore_case"):
        pattern, path = pattern.lower(), path.lower()
    match = name["match"]
    if match == "exact":
        return path == pattern
    if match == "base-name":
        return fnmatch.fnmatchcase(posixpath.basename(path), pattern)
    if match == "glob":
        return fnmatch.fnmatchcase(path, pattern)
    return pattern in path


def _scaffolded_paths() -> dict[str, str]:
    """Each template file (``greenfield/templates/...``) and the path the scaffolder writes it to."""
    if str(BOOTSTRAP) not in sys.path:
        sys.path.insert(0, str(BOOTSTRAP))
    bootstrap = importlib.import_module("bootstrap")
    paths: dict[str, str] = {}
    for file in sorted(TEMPLATES.rglob("*")):
        if file.is_file():
            rel = file.relative_to(TEMPLATES).as_posix()
            target = bootstrap.target_path_for(rel)
            if target is not None:
                paths[f"greenfield/templates/{rel}"] = target
    return paths


def undeclared_names(paths: dict[str, str], cmap: dict[str, Any]) -> list[str]:
    """Templates whose scaffolded path matches a names entry but have no ``create`` moves entry with an intent."""
    declared = {
        (move["origin"]["path"], tuple(move.get("to", [])))
        for move in cmap["moves"]
        if move["action"] == "create" and move.get("intent")
    }
    problems = []
    for origin, target in sorted(paths.items()):
        hits = sorted({check for name in cmap["names"] if name_matches(name, target) for check in name["checks"]})
        if hits and (origin, (target,)) not in declared:
            problems.append(f"{origin} -> {target} has a name read by {', '.join(hits)} and no declared intent")
    return problems


def names_constant_problems(names: list[dict[str, Any]]) -> list[str]:
    """Patterns that are not in the constants their entry names, and constant values no entry covers."""
    problems: list[str] = []
    covered: dict[str, set[str]] = {}
    for name in names:
        for reference in name.get("constants", []):
            covered.setdefault(reference, set()).add(name["pattern"])
        references = name.get("constants", [])
        if references:
            held: set[str] = set()
            for reference in references:
                values, found = _constant_values(reference)
                held |= values
                problems += found
            if name["pattern"] not in held:
                problems.append(f"{name['pattern']!r} is not a value of {', '.join(references)}")
    for reference, patterns in sorted(covered.items()):
        values, _ = _constant_values(reference)
        problems += [f"{reference}: {value!r} has no names entry" for value in sorted(values - patterns)]
    return problems


def commits_rows(text: str) -> list[int]:
    """The numbers of the rows in a playbook's ``## Commits`` table."""
    rows: list[int] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Commits"
            continue
        match = _COMMITS_ROW.match(line) if inside else None
        if match:
            rows.append(int(match.group(1)))
    return rows


def _normalised(text: str) -> str:
    return " ".join(text.split())


def section_text(path: str, address: str, text: str) -> str | None:
    """The lines of the section at ``address`` and its subsections, or ``None`` when the file has no such section."""
    nodes, _, parsed = _section_nodes(path, text)
    if address != path and address not in {node.address for node in nodes}:
        return None
    return "\n".join(
        line.text
        for line, holder in zip(parsed.document.lines, parsed.holders, strict=True)
        if address == path or holder == address or holder.startswith(address + "/")
    )


def quote_problem(home: dict[str, Any], read: Any = None) -> str | None:
    """Why a keeps home does not hold, or ``None``. ``read`` maps a path to its text (the working tree by default)."""
    path, address = home["path"], home["section"]
    if not (address == path or address.startswith(path + "#")):
        return f"{address} is not a section of {path}"
    text = read(path) if read else (_dev_paths.REPO / path).read_text(encoding="utf-8")
    body = section_text(path, address, text)
    if body is None:
        return f"{path} has no section {address}"
    if _normalised(home["quote"]) not in _normalised(body):
        return f"{address} does not hold the quote {home['quote']!r}"
    return None


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


class NamesTest(unittest.TestCase):
    def test_each_pattern_is_listed_once(self) -> None:
        keys = [(name["pattern"], name["match"], bool(name.get("ignore_case"))) for name in MAP["names"]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_names_cover_the_engine_constants_they_name(self) -> None:
        self.assertEqual(names_constant_problems(MAP["names"]), [])

    def test_every_template_with_an_engine_name_declares_its_intent(self) -> None:
        self.assertEqual(undeclared_names(_scaffolded_paths(), MAP), [])

    def test_a_template_named_docs_agents_md_fails(self) -> None:
        paths = {"greenfield/templates/docs/agents.md": "docs/agents.md"}
        problems = undeclared_names(paths, MAP)
        self.assertEqual(len(problems), 1)
        self.assertIn("AGT-08", problems[0])

    def test_the_scaffolder_renames_are_followed(self) -> None:
        paths = _scaffolded_paths()
        self.assertEqual(paths["greenfield/templates/github/workflows/ci.yml"], ".github/workflows/ci.yml")
        self.assertEqual(paths["greenfield/templates/core-index.ts"], "src/core/index.ts")

    def test_the_match_kinds(self) -> None:
        self.assertTrue(
            name_matches({"pattern": "AGENTS.md", "match": "base-name", "ignore_case": True}, "a/agents.md")
        )
        self.assertFalse(name_matches({"pattern": "AGENTS.md", "match": "base-name"}, "a/agents.md"))
        self.assertTrue(name_matches({"pattern": "README.md", "match": "exact"}, "README.md"))
        self.assertFalse(name_matches({"pattern": "README.md", "match": "exact"}, "docs/README.md"))
        self.assertTrue(
            name_matches({"pattern": ".github/workflows/*.yml", "match": "glob"}, ".github/workflows/a/b.yml")
        )
        self.assertTrue(
            name_matches({"pattern": "branch-protection", "match": "substring"}, "docs/branch-protection.md")
        )


class MovesTest(unittest.TestCase):
    def test_move_ids_are_unique(self) -> None:
        ids = [move["id"] for move in MAP["moves"]]
        self.assertEqual(sorted({i for i in ids if ids.count(i) > 1}), [])

    def test_every_commits_row_has_one_moves_entry(self) -> None:
        declared: dict[str, list[int]] = {}
        for move in MAP["moves"]:
            if "row" in move["origin"]:
                declared.setdefault(move["origin"]["path"], []).append(move["origin"]["row"])
        for playbook in sorted(PLAYBOOKS.glob("*.md")):
            rows = commits_rows(playbook.read_text(encoding="utf-8"))
            if not rows:
                continue
            path = playbook.relative_to(_dev_paths.REPO).as_posix()
            self.assertEqual(sorted(declared.get(path, [])), sorted(rows), path)

    def test_a_row_move_is_named_after_its_playbook_and_row(self) -> None:
        for move in MAP["moves"]:
            origin = move["origin"]
            if "row" in origin:
                self.assertEqual(move["id"], f"{posixpath.basename(origin['path'])[:-3]}/row-{origin['row']}")


class KeepsTest(unittest.TestCase):
    def test_each_keep_points_at_a_move_and_a_catalogue_check(self) -> None:
        moves = {move["id"] for move in MAP["moves"]}
        for keep in MAP["keeps"]:
            self.assertIn(keep["move"], moves)
            self.assertIn(keep["check"], CATALOGUE_IDS)

    def test_each_pair_is_kept_once(self) -> None:
        pairs = [(keep["move"], keep["check"]) for keep in MAP["keeps"]]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_every_kept_quote_sits_in_its_section(self) -> None:
        problems = [quote_problem(keep["home"]) for keep in MAP["keeps"] if keep["status"] == "kept"]
        self.assertEqual([problem for problem in problems if problem], [])

    def test_a_quote_moved_out_of_its_section_fails(self) -> None:
        text = "# T\n\n## A\n\nKeep it on one line.\n\n## B\n\nOther.\n"
        home = {"path": "x.md", "section": "x.md#t/b", "quote": "Keep it on one line."}
        self.assertIn("does not hold the quote", quote_problem(home, lambda _path: text) or "")
        home["section"] = "x.md#t/a"
        self.assertIsNone(quote_problem(home, lambda _path: text))
        home["section"] = "x.md#t"
        self.assertIsNone(quote_problem(home, lambda _path: text))

    def test_a_reworded_quote_fails(self) -> None:
        text = "# T\n\nKeep it on\none line.\n"
        home = {"path": "x.md", "section": "x.md#t", "quote": "Keep it on one line."}
        self.assertIsNone(quote_problem(home, lambda _path: text))
        home["quote"] = "Keep it on a single line."
        self.assertIn("does not hold the quote", quote_problem(home, lambda _path: text) or "")


if __name__ == "__main__":
    unittest.main()
