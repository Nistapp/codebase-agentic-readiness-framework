# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The consistency map, ``dev/consistency-map.json``, against its schema, the catalogue and the engine's constants.

Every check in ``audit/catalogue.json`` has exactly one reads entry, in catalogue order. A reads entry that names
engine constants (``module:NAME``) must list exactly the paths those constants hold, so a file added to or removed
from a check's list in the engine fails this test until the map follows (ADR 0012).

The names list holds the file names the engine gives a meaning to. A greenfield template whose scaffolded path
matches one needs a ``create`` moves entry with an ``intent``, so a template cannot take such a name by accident.

Every playbook Commits row has one moves entry. A ``kept`` keeps entry quotes, verbatim with whitespace collapsed,
a sentence that sits inside the section its address names, in the working tree. The helpers are the gate's own,
from ``dev/consistency_map.py``; the gate itself is tested at the end.
"""

from __future__ import annotations

import io
import json
import posixpath
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

import _dev_paths
import consistency_map
from test_consistency_map_schema import SCHEMA, _problems

PLAYBOOKS = consistency_map.PLAYBOOKS
MAP: dict[str, Any] = consistency_map.load_map()
CATALOGUE_IDS: list[str] = [
    check["id"]
    for check in json.loads((_dev_paths.REPO / "audit" / "catalogue.json").read_text(encoding="utf-8"))["checks"]
]


_engine_module = consistency_map._engine_module
constant_problems = consistency_map.read_constant_problems
names_constant_problems = consistency_map.names_constant_problems
name_matches = consistency_map.name_matches
undeclared_names = consistency_map.undeclared_names
commits_rows = consistency_map.commits_rows
quote_problem = consistency_map.quote_problem
_scaffolded_paths = consistency_map.scaffolded_paths


class MapShapeTest(unittest.TestCase):
    def test_the_map_follows_its_schema(self) -> None:
        self.assertEqual(_problems(MAP, SCHEMA), [])


#: The size over which the audit's structural check (``NAV-03``, ``LARGE_FILE_BYTES`` in the engine's ``nav.py``)
#: flags a file. Each map file stays under it.
_LARGE_FILE_BYTES = 512 * 1024


class MapFilesTest(unittest.TestCase):
    """The map is two files, joined by ``load_map``: each part once, one format, each file under the size limit."""

    def _write(self, folder: Path, cmap: dict[str, Any], names: Any) -> Path:
        path = folder / "consistency-map.json"
        path.write_text(json.dumps(cmap), encoding="utf-8")
        if names is not None:
            consistency_map.names_path(path).write_text(json.dumps(names), encoding="utf-8")
        return path

    def test_each_map_file_stays_under_the_structural_size_limit(self) -> None:
        for path in (consistency_map.MAP_PATH, consistency_map.names_path(consistency_map.MAP_PATH)):
            self.assertLess(path.stat().st_size, _LARGE_FILE_BYTES, path.name)

    def test_the_names_file_sits_beside_the_map_file(self) -> None:
        self.assertEqual(
            consistency_map.names_path(Path("dev/consistency-map.json")), Path("dev/consistency-map-names.json")
        )

    def test_the_two_files_join_into_one_map(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = self._write(Path(folder), {"map_format": 1, "reads": []}, {"map_format": 1, "names": [{"n": 1}]})
            self.assertEqual(consistency_map.load_map(path), {"map_format": 1, "reads": [], "names": [{"n": 1}]})

    def test_files_that_do_not_join_are_refused(self) -> None:
        cases: list[tuple[str, dict[str, Any], Any]] = [
            ("holds names", {"map_format": 1, "names": []}, {"map_format": 1, "names": []}),
            ("is missing", {"map_format": 1}, None),
            ("must hold", {"map_format": 1}, {"map_format": 1, "names": [], "reads": []}),
            ("has map_format 2", {"map_format": 1}, {"map_format": 2, "names": []}),
        ]
        for message, cmap, names in cases:
            with self.subTest(message), tempfile.TemporaryDirectory() as folder:
                path = self._write(Path(folder), cmap, names)
                with self.assertRaisesRegex(consistency_map.MapError, message):
                    consistency_map.load_map(path)

    def test_a_map_that_does_not_join_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = self._write(Path(folder), {"map_format": 1}, None)
            with redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as stop:
                consistency_map.main(["--map", str(path)])
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("consistency-map-names.json is missing", err.getvalue())


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


_RULES = "# Implement\n\n## Hard rules\n\n- **Never weaken a gate.** Never lower a baseline.\n\n## Stages\n\nOther.\n"
_ENFORCER = "def refuse() -> None:\n    pass\n\n\nclass GateTest:\n    def test_it(self) -> None:\n        pass\n"


def _boundary(**fields: Any) -> dict[str, Any]:
    home = {"path": "skill.md", "section": "skill.md#implement/hard-rules", "quote": "Never lower a baseline."}
    return {"id": "B-01", "statement": "s", "home": home, "enforcement": "prose", **fields}


def _scratch(path: str) -> str:
    """A scratch reader: a recipe with one hard rule, and one Python file that defines the enforcers."""
    files = {"skill.md": _RULES, "tool.py": _ENFORCER}
    if path not in files:
        raise FileNotFoundError(path)
    return files[path]


class BoundariesTest(unittest.TestCase):
    def test_every_boundary_in_the_map_holds(self) -> None:
        self.assertEqual(consistency_map.boundary_problems(MAP["boundaries"]), [])

    def test_the_run_boundaries_of_the_design_are_listed(self) -> None:
        quotes = " ".join(boundary["home"]["quote"] for boundary in MAP["boundaries"])
        self.assertIn("Never commit to the default branch", quotes)
        self.assertIn("The close-out changes nothing in the target", quotes)
        self.assertIn("Never delete, skip or weaken a test", quotes)

    def test_each_cited_enforcer_exists(self) -> None:
        for boundary in MAP["boundaries"]:
            if boundary["enforcement"] == "prose":
                self.assertNotIn("enforced_by", boundary, boundary["id"])
                continue
            path = _dev_paths.REPO / boundary["enforced_by"]
            self.assertTrue(path.is_file(), boundary["id"])
            symbols = consistency_map.defined_symbols(path.read_text(encoding="utf-8"))
            self.assertIn(boundary["symbol"], symbols, boundary["id"])

    def test_a_removed_home_quote_fails(self) -> None:
        self.assertEqual(consistency_map.boundary_problems([_boundary()], _scratch), [])

        def removed(path: str) -> str:
            return _scratch(path).replace(" Never lower a baseline.", "")

        problems = consistency_map.boundary_problems([_boundary()], removed)
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("B-01: "), problems)
        self.assertIn("does not hold the quote", problems[0])

    def test_a_removed_home_quote_is_reported_in_the_map(self) -> None:
        cmap = json.loads(json.dumps(MAP))
        cmap["boundaries"][0]["home"]["quote"] = "A sentence the recipe never had."
        found = consistency_map.report(cmap, CATALOGUE_IDS)
        self.assertEqual(len(found["boundary"]), 1)
        self.assertIn("B-01", found["boundary"][0])
        self.assertIn("boundary: 1", consistency_map.format_text(found, []))

    def test_a_missing_enforcer_fails(self) -> None:
        check = consistency_map.boundary_problems
        tool = {"enforcement": "tool-refusal", "enforced_by": "tool.py"}
        self.assertEqual(check([_boundary(**tool, symbol="refuse")], _scratch), [])
        test = {"enforcement": "test", "enforced_by": "tool.py", "symbol": "GateTest.test_it"}
        self.assertEqual(check([_boundary(**test)], _scratch), [])
        self.assertEqual(check([_boundary(**tool, symbol="gone")], _scratch), ["B-01: tool.py defines no gone"])
        moved = {"enforcement": "eval", "enforced_by": "moved.py", "symbol": "refuse"}
        self.assertEqual(check([_boundary(**moved)], _scratch), ["B-01: moved.py does not exist"])

    def test_a_misdeclared_enforcement_fails(self) -> None:
        check = consistency_map.boundary_problems
        self.assertEqual(
            check([_boundary(enforcement="eval")], _scratch),
            ["B-01: the eval enforcement needs enforced_by and symbol"],
        )
        self.assertEqual(
            check([_boundary(enforced_by="tool.py")], _scratch),
            ["B-01: a prose boundary names no enforced_by or symbol"],
        )

    def test_a_repeated_id_fails(self) -> None:
        problems = consistency_map.boundary_problems([_boundary(), _boundary()], _scratch)
        self.assertEqual(problems, ["B-01: the id is used twice"])


def _small_map() -> dict[str, Any]:
    return {
        "map_format": 1,
        "reads": [
            {
                "check": "AGT-06",
                "source": "engine",
                "where": [{"path": "AGENTS.md", "scope": "root"}],
                "what": {"kind": "word-list"},
                "binding": "line",
            },
            {
                "check": "TST-04",
                "source": "engine",
                "where": [{"path": "README.md", "scope": "root"}],
                "what": {"kind": "fenced-command"},
                "binding": "line",
            },
        ],
        "moves": [
            {
                "id": "p/row-1",
                "origin": {"path": "implement/playbooks/p.md", "row": 1},
                "action": "write",
                "content": ["rule-line"],
                "to": ["AGENTS.md"],
                "touches": ["AGT-06"],
            },
            {
                "id": "p/row-2",
                "origin": {"path": "implement/playbooks/p.md", "row": 2},
                "action": "move",
                "from": ["README.md"],
                "to": ["docs/"],
            },
        ],
        "keeps": [],
        "names": [],
        "boundaries": [],
    }


class GateTest(unittest.TestCase):
    def test_a_declared_touch_without_a_keep_is_unkept(self) -> None:
        self.assertEqual(consistency_map.unkept_pairs(_small_map()), [("p/row-1", "AGT-06")])

    def test_a_keep_closes_the_pair(self) -> None:
        cmap = _small_map()
        home = {"path": "x.md", "section": "x.md", "quote": "q"}
        cmap["keeps"] = [{"move": "p/row-1", "check": "AGT-06", "status": "kept", "home": home}]
        self.assertEqual(consistency_map.unkept_pairs(cmap), [])

    def test_a_keep_for_an_undeclared_touch_is_a_problem(self) -> None:
        cmap = _small_map()
        cmap["keeps"] = [{"move": "p/row-2", "check": "TST-04", "status": "accepted", "reason": "r"}]
        problems = consistency_map.keeps_problems(cmap, ["AGT-06", "TST-04"])
        self.assertEqual(problems, ["p/row-2 -> TST-04: the move does not declare this check in touches"])

    def test_an_undeclared_inferred_touch_is_only_unreviewed(self) -> None:
        cmap = _small_map()
        self.assertEqual(consistency_map.unreviewed_pairs(cmap), [("p/row-2", "TST-04", "README.md")])
        self.assertNotIn(("p/row-2", "TST-04"), consistency_map.unkept_pairs(cmap))

    def test_content_that_cannot_hold_the_read_does_not_touch(self) -> None:
        move = {"action": "write", "content": ["prose"], "to": ["README.md"]}
        read = _small_map()["reads"][1]
        self.assertIsNone(consistency_map.touch(move, read))
        move["content"] = ["fenced-command"]
        self.assertEqual(consistency_map.touch(move, read), "README.md")

    def test_place_overlaps(self) -> None:
        overlaps = consistency_map.place_overlaps
        self.assertTrue(overlaps("AGENTS.md", {"path": "AGENTS.md", "scope": "root"}))
        self.assertFalse(overlaps("docs/AGENTS.md", {"path": "AGENTS.md", "scope": "root"}))
        self.assertTrue(overlaps("docs/AGENTS.md", {"path": "AGENTS.md", "scope": "any-depth"}))
        self.assertTrue(overlaps("docs/", {"path": "SECURITY*", "scope": "repository-level"}))
        self.assertFalse(overlaps("src/", {"path": "SECURITY*", "scope": "repository-level"}))
        self.assertTrue(overlaps(".github/workflows/ci.yml", {"path": ".github/workflows/*.yml", "scope": "glob"}))

    def test_a_section_that_does_not_name_the_check_is_a_mention_problem(self) -> None:
        text = "# T\n\n## A\n\nKeep it on one line.\n\n## B\n\nAGT-06 reads it.\n"
        home = {"path": "x.md", "section": "x.md#t/a", "quote": "q"}
        keep: dict[str, Any] = {"move": "m", "check": "AGT-06", "home": home}
        self.assertIsNotNone(consistency_map.mention_problem(keep, lambda _path: text))
        home["section"] = "x.md#t"
        self.assertIsNone(consistency_map.mention_problem(keep, lambda _path: text))

    def test_the_report_of_this_tree_has_no_structural_problem(self) -> None:
        found = consistency_map.report(MAP, CATALOGUE_IDS)
        for kind in ("quote", "coverage", "names", "constants", "keeps"):
            self.assertEqual(found[kind], [], kind)

    def test_report_mode_exits_0_and_strict_mode_exits_1(self) -> None:
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(consistency_map.main([]), 0)
        self.assertIn("consistency map:", out.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(consistency_map.main(["--strict"]), 1)

    def test_json_mode_lists_every_kind(self) -> None:
        with redirect_stdout(io.StringIO()) as out:
            consistency_map.main(["--format", "json"])
        self.assertEqual(set(json.loads(out.getvalue())), {*consistency_map.KINDS, "unreviewed"})


if __name__ == "__main__":
    unittest.main()
