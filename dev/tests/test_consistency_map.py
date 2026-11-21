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

import importlib.util
import io
import json
import posixpath
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from collections.abc import Callable
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


#: The size each map file stays under (ADR 0012), well below the 512 KiB over which the audit's structural check
#: (``NAV-03``) flags a file.
_MAP_FILE_BYTES = 100 * 1024


class MapFilesTest(unittest.TestCase):
    """The map is a folder of files, joined by ``load_map``: each file under the size limit, the index lists them all.

    The one-file form (the map file and its names file) is still read, and its tests are here too."""

    def _write(self, folder: Path, cmap: dict[str, Any], names: Any) -> Path:
        path = folder / "consistency-map.json"
        path.write_text(json.dumps(cmap), encoding="utf-8")
        if names is not None:
            consistency_map.names_path(path).write_text(json.dumps(names), encoding="utf-8")
        return path

    def test_each_map_file_stays_under_the_size_limit(self) -> None:
        files = sorted(consistency_map.MAP_PATH.rglob("*.json"))
        self.assertGreater(len(files), 10)
        for path in files:
            self.assertLess(path.stat().st_size, _MAP_FILE_BYTES, str(path.relative_to(consistency_map.MAP_PATH)))

    def test_the_folder_holds_only_what_the_index_lists_and_each_file_is_in_the_repository_format(self) -> None:
        folder = consistency_map.MAP_PATH
        index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
        listed = {name for files in index["parts"].values() for name in files}
        self.assertEqual({p.relative_to(folder).as_posix() for p in folder.rglob("*.json")}, listed | {"index.json"})
        for path in folder.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text, json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n", path.name)

    def test_the_default_map_is_the_folder(self) -> None:
        self.assertEqual(consistency_map.MAP_PATH, consistency_map.DEV / "consistency-map")
        self.assertTrue(consistency_map.MAP_PATH.is_dir())

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

    def _write_folder(self, folder: Path, cmap: dict[str, Any], pieces: int = 3) -> Path:
        """The folder form of ``cmap``: each part cut into ``pieces`` runs of entries, listed in order by the index."""
        parts: dict[str, list[str]] = {}
        for part, entries in cmap.items():
            if part == "map_format":
                continue
            size = max(1, -(-len(entries) // pieces))
            parts[part] = []
            for number, start in enumerate(range(0, len(entries), size), 1):
                name = f"{part}-{number}.json"
                (folder / name).write_text(json.dumps(entries[start : start + size]), encoding="utf-8")
                parts[part].append(name)
        (folder / "index.json").write_text(json.dumps({"map_format": cmap["map_format"], "parts": parts}))
        return folder

    def test_the_folder_form_joins_to_the_same_map_as_the_one_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = self._write_folder(Path(folder), MAP)
            self.assertEqual(
                json.dumps(consistency_map.load_map(path), sort_keys=True), json.dumps(MAP, sort_keys=True)
            )

    def test_the_folder_form_keeps_the_order_the_index_gives(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "a.json").write_text('[{"n": 1}]')
            (root / "b.json").write_text('[{"n": 2}]')
            (root / "index.json").write_text('{"map_format": 1, "parts": {"reads": ["b.json", "a.json"]}}')
            self.assertEqual(consistency_map.load_map(root), {"map_format": 1, "reads": [{"n": 2}, {"n": 1}]})

    def test_a_folder_that_does_not_join_is_refused(self) -> None:
        cases: list[tuple[str, str, dict[str, str]]] = [
            ("index.json is missing", "", {}),
            ("must hold map_format and parts", '{"parts": {}}', {}),
            ("must be a list of file names", '{"map_format": 1, "parts": {"reads": "a.json"}}', {}),
            ("lists a.json, which is missing", '{"map_format": 1, "parts": {"reads": ["a.json"]}}', {}),
            ("lists a.json twice", '{"map_format": 1, "parts": {"reads": ["a.json", "a.json"]}}', {"a.json": "[]"}),
            (
                "does not list b.json",
                '{"map_format": 1, "parts": {"reads": ["a.json"]}}',
                {"a.json": "[]", "b.json": "[]"},
            ),
            ("must hold a list", '{"map_format": 1, "parts": {"reads": ["a.json"]}}', {"a.json": "{}"}),
            ("not a part file", '{"map_format": 1, "parts": {"reads": ["../a.json"]}}', {}),
        ]
        for message, index, files in cases:
            with self.subTest(message), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                if index:
                    (root / "index.json").write_text(index)
                for name, text in files.items():
                    (root / name).write_text(text)
                with self.assertRaisesRegex(consistency_map.MapError, message):
                    consistency_map.load_map(root)

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


def _recorder_glob() -> Callable[[str, str], bool]:
    """The engine recorder test's own glob matcher (``audit/engine/tests/test_check_reads.py``), loaded by path."""
    engine = _dev_paths.REPO / "audit" / "engine"
    for folder in (engine / "tests", engine):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location("engine_test_check_reads", engine / "tests" / "test_check_reads.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    match: Callable[[str, str], bool] = module._glob_match
    return match


class RecorderGlobParityTest(unittest.TestCase):
    """The engine's recorder test writes the map's glob matcher again, since an engine test imports no dev module."""

    def test_the_recorder_matches_globs_as_the_map_does(self) -> None:
        recorder = _recorder_glob()
        patterns = (
            "**",
            "**/AGENTS.md",
            "*/**/AGENTS.md",
            ".husky/*",
            ".husky/**",
            "docs/**/*.md",
            "a/**/b/**/*.md",
            ".github/workflows/*.yml",
            ".github/workflows/**/*.yml",
            ".roo/rules-*/**",
            "README*",
            "tests/[a-c]*.rs",
        )
        paths = (
            "",
            "AGENTS.md",
            "pkg/AGENTS.md",
            "a/b/AGENTS.md",
            ".husky/pre-commit",
            ".husky/_/husky.sh",
            "docs/a.md",
            "docs/x/y/a.md",
            "a/b/c.md",
            "a/x/b/y/c.md",
            ".github/workflows/ci.yml",
            ".github/workflows/sub/ci.yml",
            ".roo/rules-code/a.md",
            "README.md",
            "docs/README.md",
            "tests/a.rs",
            "tests/d.rs",
            "tests/common/b.rs",
        )
        for pattern in patterns:
            for path in paths:
                with self.subTest(pattern=pattern, path=path):
                    self.assertEqual(recorder(path, pattern), consistency_map._glob_matches(pattern, path))


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
        folder = {"pattern": "dist", "match": "folder-name", "ignore_case": True}
        self.assertTrue(name_matches(folder, "pkg/Dist/app.js"))
        self.assertFalse(name_matches(folder, "redist/app.js"))
        self.assertFalse(name_matches(folder, "src/dist"))


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


def _r5_map(*, mode: str | None, monotone: bool) -> dict[str, Any]:
    """One move that writes a line to ``AGENTS.md`` and one read of it, for rule R5."""
    where: dict[str, Any] = {"path": "AGENTS.md", "scope": "root", **({"monotone": True} if monotone else {})}
    move: dict[str, Any] = {
        "id": "p/row-1",
        "origin": {"path": "implement/playbooks/p.md", "row": 1},
        "action": "write",
        "content": ["prose"],
        "to": ["AGENTS.md"],
        **({"mode": mode} if mode else {}),
    }
    read = {"check": "AGT-03", "source": "engine", "where": [where], "what": {"kind": "word-list"}, "binding": "file"}
    return {"map_format": 1, "reads": [read], "moves": [move], "keeps": [], "names": [], "boundaries": []}


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
        self.assertTrue(overlaps("docs/SECURITY.md", {"path": "SECURITY*", "scope": "repository-level"}))
        self.assertFalse(overlaps("src/SECURITY.md", {"path": "SECURITY*", "scope": "repository-level"}))
        self.assertTrue(overlaps(".github/workflows/ci.yml", {"path": ".github/workflows/*.yml", "scope": "glob"}))

    def test_a_glob_place_matches_folder_by_folder(self) -> None:
        overlaps = consistency_map.place_overlaps
        self.assertTrue(overlaps("docs/a.md", {"path": "docs/**/*.md", "scope": "glob"}))
        self.assertTrue(overlaps("docs/x/a.md", {"path": "docs/**/*.md", "scope": "glob"}))
        self.assertTrue(overlaps("AGENTS.md", {"path": "**/AGENTS.md", "scope": "glob"}))
        self.assertTrue(overlaps("src/app.py", {"path": "**", "scope": "glob"}))
        self.assertFalse(overlaps(".github/workflows/sub/ci.yml", {"path": ".github/workflows/*.yml", "scope": "glob"}))
        self.assertFalse(overlaps("docs/a.md", {"path": "*.md", "scope": "glob"}))
        self.assertTrue(overlaps("docs/*.md", {"path": "docs/**/*.md", "scope": "glob"}))
        self.assertTrue(overlaps("**/*.sh", {"path": "scripts/*.sh", "scope": "glob"}))

    def test_a_glob_move_path_matches_a_root_place_folder_by_folder(self) -> None:
        overlaps = consistency_map.place_overlaps
        self.assertTrue(overlaps("*.md", {"path": "README.md", "scope": "root"}))
        self.assertFalse(overlaps("*.md", {"path": "docs/README.md", "scope": "root"}))
        self.assertTrue(overlaps("**/README.md", {"path": "README.md", "scope": "root"}))

    def test_a_folder_reaches_a_glob_place_folder_by_folder(self) -> None:
        overlaps = consistency_map.place_overlaps
        self.assertTrue(overlaps("artefacts/", {"path": "**", "scope": "glob"}))
        self.assertFalse(overlaps("docs/", {"path": "*", "scope": "glob"}))

    def test_a_wildcard_folder_reaches_the_root_at_repository_level(self) -> None:
        overlaps = consistency_map.place_overlaps
        self.assertTrue(overlaps("**/SECURITY.md", {"path": "SECURITY*", "scope": "repository-level"}))
        self.assertTrue(overlaps("*/SECURITY.md", {"path": "SECURITY*", "scope": "repository-level"}))
        self.assertFalse(overlaps("src/*/SECURITY.md", {"path": "SECURITY*", "scope": "repository-level"}))

    def test_a_folded_place_meets_a_path_in_any_case(self) -> None:
        overlaps = consistency_map.place_overlaps
        place = {"path": "docs/**/*convention*", "scope": "glob", "case": "fold"}
        self.assertTrue(overlaps("docs/Conventions.md", place))
        self.assertTrue(overlaps("DOCS/x/CONVENTIONS.md", place))
        self.assertFalse(overlaps("docs/Conventions.md", {"path": "docs/**/*convention*", "scope": "glob"}))

    def test_r1_a_folder_overlaps_only_the_places_inside_it(self) -> None:
        overlaps = consistency_map.place_overlaps
        self.assertFalse(overlaps("artefacts/", {"path": "package.json", "scope": "any-depth"}))
        self.assertFalse(overlaps("docs/", {"path": "SECURITY*", "scope": "repository-level"}))
        self.assertFalse(overlaps("docs/", {"path": "AGENTS.md", "scope": "root"}))
        self.assertTrue(overlaps("artefacts/", {"path": "artefacts", "scope": "root"}))
        self.assertTrue(overlaps("docs/", {"path": "docs/README.md", "scope": "root"}))
        self.assertTrue(overlaps(".circleci/", {"path": ".circleci/config.yml", "scope": "any-depth"}))
        self.assertTrue(overlaps("docs/", {"path": "docs/adr/*", "scope": "glob"}))

    def test_r1_an_untracked_folder_reaches_the_root_place_of_its_name(self) -> None:
        read = {"check": "CON-03", "what": {"kind": "exists"}, "where": [{"path": "artefacts", "scope": "root"}]}
        move = {"action": "untrack", "from": ["artefacts/"]}
        self.assertEqual(consistency_map.touch(move, read), "artefacts/")

    def test_r2_a_wildcard_base_name_does_not_overlap_a_literal_name(self) -> None:
        overlaps = consistency_map.place_overlaps
        self.assertFalse(overlaps(".github/workflows/*.yml", {"path": "Taskfile.yml", "scope": "any-depth"}))
        self.assertFalse(overlaps("**/dist/**", {"path": "package.json", "scope": "any-depth"}))
        self.assertFalse(overlaps("docs/*", {"path": "CONTRIBUTING.md", "scope": "repository-level"}))
        self.assertTrue(overlaps("docs/*", {"path": "CONTRIBUTING*", "scope": "repository-level"}))
        self.assertTrue(overlaps("scripts/*.sh", {"path": "*.sh", "scope": "any-depth"}))
        self.assertTrue(overlaps("ci/Taskfile.yml", {"path": "Taskfile.yml", "scope": "any-depth"}))
        self.assertTrue(overlaps(".github/workflows/*.yml", {"path": ".github/workflows/*.yml", "scope": "glob"}))

    def test_r3_a_kind_filtered_glob_read_sees_only_its_kinds(self) -> None:
        read = {"check": "EXEC-04", "what": {"kind": "key"}, "where": [{"path": "**", "scope": "glob"}]}
        touch = consistency_map.touch
        self.assertIsNone(touch({"action": "write", "content": ["key"], "to": ["docs/env.md"]}, read))
        self.assertIsNone(touch({"action": "write", "content": ["key"], "to": [".env.example"]}, read))
        self.assertEqual(touch({"action": "write", "to": ["scripts/ci/*.sh"]}, read), "scripts/ci/*.sh")
        self.assertEqual(touch({"action": "write", "to": ["src/app.py"]}, read), "src/app.py")

    def test_r3_folders_and_untracked_folders_are_exempt(self) -> None:
        read = {"check": "NAV-02", "what": {"kind": "exists"}, "where": [{"path": "**", "scope": "glob"}]}
        touch = consistency_map.touch
        self.assertEqual(touch({"action": "untrack", "from": ["notes/"]}, read), "notes/")
        self.assertEqual(touch({"action": "create", "to": ["tools/"]}, read), "tools/")
        self.assertIsNone(touch({"action": "create", "to": ["docs/index.md"]}, read))

    def test_r3b_an_untracked_path_counts_for_every_kind_it_can_match(self) -> None:
        read = {"check": "NAV-02", "what": {"kind": "exists"}, "where": [{"path": "**", "scope": "glob"}]}
        touch = consistency_map.touch
        self.assertIsNone(touch({"action": "untrack", "from": ["notes.md"]}, read))
        self.assertIsNone(touch({"action": "untrack", "from": [".env"]}, read))
        self.assertEqual(touch({"action": "untrack", "from": ["src/app.py"]}, read), "src/app.py")
        # A generated folder can still hold a file the scan names by itself: dist/Makefile is a build file.
        self.assertEqual(touch({"action": "untrack", "from": ["**/dist/**"]}, read), "**/dist/**")
        self.assertIsNone(touch({"action": "untrack", "from": ["**/*.log"]}, read))

    def test_r3b_possible_kinds(self) -> None:
        kinds = consistency_map.possible_kinds
        self.assertEqual(kinds(".env"), {"other"})
        self.assertEqual(kinds("**/*.md"), {"doc", "test", "generated"})
        self.assertLessEqual({"generated", "manifest", "build"}, kinds("**/dist/**") or set())
        self.assertIn("config", kinds(".env.*") or set())  # .env.example is a config file
        self.assertIsNone(kinds("dist/"))

    def test_r3c_a_folder_that_receives_moved_text_has_the_kinds_of_its_sources(self) -> None:
        read = {"check": "TOOL-06", "what": {"kind": "phrase"}, "where": [{"path": "**", "scope": "glob"}]}
        touch = consistency_map.touch
        self.assertIsNone(touch({"action": "move", "from": ["AGENTS.md"], "to": ["docs/"]}, read))
        self.assertEqual(touch({"action": "move", "from": ["ci.sh"], "to": ["scripts/"]}, read), "ci.sh")
        self.assertEqual(touch({"action": "move", "from": ["old/"], "to": ["scripts/"]}, read), "old/")
        self.assertEqual(consistency_map._path_kinds("scripts/", {"action": "move", "from": ["old/"]}, "to"), None)
        self.assertEqual(touch({"action": "write", "to": ["docs/"]}, read), "docs/")

    def test_r4_a_content_independent_read_is_never_touched(self) -> None:
        read = {"check": "CON-04", "what": {"kind": "exists"}, "where": [{"path": "**", "scope": "glob"}]}
        touch = consistency_map.touch
        for action in ("create", "write", "move", "untrack"):
            move = {"action": action, "from": ["a.py"], "to": ["b.py"]}
            self.assertIsNone(touch(move, read), action)
        self.assertEqual(consistency_map.CONTENT_INDEPENDENT_READS, {"CON-04"})

    def test_r4_the_con04_verdict_does_not_follow_the_target(self) -> None:
        """``check_con04`` gives one verdict on an empty target and on a full one, with and without the emitter."""
        scan = _engine_module("audit.scan")
        con = _engine_module("audit.rules.checks.con")
        target_module = _engine_module("audit.target")
        spec = next(s for s in _engine_module("audit.rules.registry").REGISTRY if s.id == "CON-04")
        self.addCleanup(con.set_emit_target, None)
        verdicts: dict[str, set[str]] = {"off": set(), "on": set()}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            empty, full = root / "empty", root / "full"
            empty.mkdir()
            for rel, text in {
                "AGENTS.md": "# Rules\n\nNever push to main.\n",
                "package.json": '{"scripts": {"test": "node test.js"}}\n',
                "src/app.py": "print(1)\n",
                "dist/app.js": "x\n",
            }.items():
                (full / rel).parent.mkdir(parents=True, exist_ok=True)
                (full / rel).write_text(text, encoding="utf-8")
            for name, path in (("empty", empty), ("full", full)):
                target = target_module.resolve_target(path)
                inventory = scan.build_inventory(target.path)
                for mode in ("off", "on"):
                    out = root / f"out-{name}-{mode}" / "report.json"
                    con.set_emit_target(out if mode == "on" else None)
                    outcome = con.check_con04(
                        spec=spec, target=target, inventory=inventory, stack=None, components=None, session=None
                    )
                    verdicts[mode].add(outcome.verdict.value)
        self.assertEqual(verdicts, {"off": {"UNKNOWN"}, "on": {"PASS"}})

    def test_r6_only_an_untrack_touches_the_text_scan_of_sec02(self) -> None:
        read = {
            "check": "SEC-02",
            "what": {"kind": "phrase"},
            "where": [{"path": "**", "scope": "glob"}, {"path": ".secrets.baseline", "scope": "root"}],
        }
        touch = consistency_map.touch
        self.assertIsNone(touch({"action": "write", "to": ["src/app.py"]}, read))
        self.assertIsNone(touch({"action": "create", "to": ["docs/env.md"]}, read))
        self.assertEqual(touch({"action": "untrack", "from": [".env"]}, read), ".env")
        # The allowlist is not the text scan: writing it can still hide or show a hit.
        self.assertEqual(touch({"action": "write", "to": [".secrets.baseline"]}, read), ".secrets.baseline")

    def test_r6_no_playbook_or_template_ships_a_secret_shaped_line(self) -> None:
        """Rule R6's premise: a playbook copies no text SEC-02 would flag into a target.

        Every line of every tracked file under ``implement/playbooks/`` and ``greenfield/templates/`` is read with
        the engine's own line test (``_scan_secrets_allowlisted`` in ``audit/engine/audit/rules/checks/sec.py``), at
        its strictest: as code and as configuration, with the short minimum length of an env-style file. The scan's
        placeholder rule still applies, so ``KEY=your_key_here`` in a template is not a hit; its file skip for
        ``.example`` files does not, so every file counts.
        """
        sec = _engine_module("audit.rules.checks.sec")

        def flagged(line: str) -> bool:
            shaped = any(
                sec._line_is_secret(line, in_code=in_code, min_len=sec._MIN_SECRET_LEN_CONFIG)
                for in_code in (False, True)
            )
            return shaped and not sec._PLACEHOLDER_RE.search(line)

        tracked = subprocess.run(
            ["git", "-C", str(_dev_paths.REPO), "ls-files", "-z", "--", "implement/playbooks", "greenfield/templates"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split("\0")
        files = [rel for rel in tracked if rel]
        hits: list[str] = []
        for rel in files:
            text = (_dev_paths.REPO / rel).read_text(encoding="utf-8")
            hits += [f"{rel}:{number}" for number, line in enumerate(text.splitlines(), start=1) if flagged(line)]
        self.assertGreater(len(files), 15)
        self.assertEqual(hits, [])
        # The test is live: a line built here, so that no key-shaped string sits in this file, is flagged.
        self.assertTrue(flagged('api_token = "' + "Zq7" * 8 + '"'))

    def test_r5_an_add_move_infers_no_pair_through_a_monotone_place(self) -> None:
        cmap = _r5_map(mode="add", monotone=True)
        self.assertEqual(consistency_map.unreviewed_pairs(cmap), [])
        # The touch can still raise the verdict, so touch() reports it; only the unreviewed count leaves it out.
        self.assertEqual(consistency_map.touch(cmap["moves"][0], cmap["reads"][0]), "AGENTS.md")
        self.assertIsNone(consistency_map.lowering_touch(cmap["moves"][0], cmap["reads"][0]))

    def test_r5_a_replace_move_or_a_plain_place_keeps_the_pair(self) -> None:
        pair = [("p/row-1", "AGT-03", "AGENTS.md")]
        self.assertEqual(consistency_map.unreviewed_pairs(_r5_map(mode="replace", monotone=True)), pair)
        self.assertEqual(consistency_map.unreviewed_pairs(_r5_map(mode=None, monotone=True)), pair)
        self.assertEqual(consistency_map.unreviewed_pairs(_r5_map(mode="add", monotone=False)), pair)

    def test_r5_an_add_move_still_touches_the_other_places_of_the_read(self) -> None:
        cmap = _r5_map(mode="add", monotone=True)
        cmap["reads"][0]["where"].append({"path": "package.json", "scope": "root"})
        cmap["moves"][0]["to"].append("package.json")
        self.assertEqual(consistency_map.unreviewed_pairs(cmap), [("p/row-1", "AGT-03", "package.json")])

    def test_r5_a_declared_pair_and_its_keep_are_never_dropped(self) -> None:
        cmap = _r5_map(mode="add", monotone=True)
        cmap["moves"][0]["touches"] = ["AGT-03"]
        self.assertEqual(consistency_map.unkept_pairs(cmap), [("p/row-1", "AGT-03")])
        home = {"path": "x.md", "section": "x.md", "quote": "q"}
        cmap["keeps"] = [{"move": "p/row-1", "check": "AGT-03", "status": "kept", "home": home}]
        self.assertEqual(consistency_map.unkept_pairs(cmap), [])
        self.assertEqual(consistency_map.keeps_problems(cmap, ["AGT-03"]), [])

    def test_r5_every_keep_of_the_map_stays_a_declared_pair(self) -> None:
        """No keep of this map leans on the inference: with the keeps gone, each kept pair is unkept again."""
        cmap = json.loads(json.dumps(MAP))
        pairs = {(keep["move"], keep["check"]) for keep in cmap["keeps"]}
        cmap["keeps"] = []
        self.assertEqual(pairs - set(consistency_map.unkept_pairs(cmap)), set())

    def test_r5_a_planted_add_move_whose_row_edits_fails(self) -> None:
        """The guard: ``adapt-agents-md`` row 15 reads "Stale lines corrected", so it may not be ``mode: add``."""
        cmap = json.loads(json.dumps(MAP))
        moves = {move["id"]: move for move in cmap["moves"]}
        moves["adapt-agents-md/row-15"]["mode"] = "add"
        problems = consistency_map.report(cmap, CATALOGUE_IDS)["mode"]
        self.assertEqual(len(problems), 1)
        self.assertIn("adapt-agents-md/row-15: mode add, but its Commits row says 'corrected'", problems[0])

    def test_r5_mode_add_needs_a_write_of_a_commits_row(self) -> None:
        text = "# P\n\n## Commits\n\n| # | Commit | Checks | Kind |\n|---|---|---|---|\n| 1 | Reach line | - | hand |\n"
        read = {"implement/playbooks/p.md": text}.__getitem__
        origin = {"path": "implement/playbooks/p.md", "row": 1}
        problems = consistency_map.mode_problems
        self.assertEqual(problems([{"id": "p/row-1", "origin": origin, "action": "write", "mode": "add"}], read), [])
        self.assertEqual(
            problems([{"id": "p/row-1", "origin": origin, "action": "create", "mode": "add"}], read),
            ["p/row-1: mode add needs the action write, not create"],
        )
        missing = {"path": "implement/playbooks/p.md", "row": 2}
        self.assertEqual(
            problems([{"id": "p/row-2", "origin": missing, "action": "write", "mode": "add"}], read),
            ["p/row-2: mode add needs a Commits row, and implement/playbooks/p.md has none for it"],
        )
        template = {"id": "t/AGENTS.md", "origin": {"path": "greenfield/templates/AGENTS.md"}, "action": "write"}
        self.assertEqual(len(problems([{**template, "mode": "add"}], read)), 1)
        self.assertEqual(problems([{**template, "mode": "replace"}], read), [])

    def test_r5_the_edit_words(self) -> None:
        edits = ("Stale lines corrected", "Fix the docs", "Stub word settled", "Dockerfile matches the pin", "Moved")
        for text in edits:
            self.assertIsNotNone(consistency_map.EDIT_WORDS.search(text), text)
        for text in ("Reach line", "Boundary rules the owner picked", "Freshness line in the instruction file"):
            self.assertIsNone(consistency_map.EDIT_WORDS.search(text), text)

    def test_r5_the_in_place_edits_stay_replace(self) -> None:
        moves = {move["id"]: move for move in MAP["moves"]}
        in_place = (
            "adapt-agents-md/row-3",
            "adapt-agents-md/row-14",
            "adapt-agents-md/row-23",
            "pin-execution-environment/row-6",
            "pin-execution-environment/row-8",
        )
        self.assertEqual(
            {move: moves[move].get("mode", "replace") for move in in_place}, dict.fromkeys(in_place, "replace")
        )
        self.assertTrue(all(move["action"] == "write" for move in MAP["moves"] if move.get("mode") == "add"))

    def test_r3_leaves_other_checks_and_places_alone(self) -> None:
        touch = consistency_map.touch
        any_kind = {"check": "NAV-03", "what": {"kind": "key"}, "where": [{"path": "**", "scope": "glob"}]}
        self.assertEqual(touch({"action": "write", "to": ["docs/env.md"]}, any_kind), "docs/env.md")
        named = {
            "check": "TOOL-07",
            "what": {"kind": "phrase"},
            "where": [{"path": "pre-commit", "scope": "any-depth"}],
        }
        self.assertEqual(touch({"action": "write", "to": [".husky/pre-commit"]}, named), ".husky/pre-commit")

    def test_r3_the_kinds_are_the_engine_scan_kinds(self) -> None:
        scan = _engine_module("audit.scan")
        known = {kind.value for kind in scan.Kind}
        for check, kinds in consistency_map.KIND_FILTERED_READS.items():
            self.assertLessEqual(kinds, known, check)
            self.assertIn(
                "**", {where["path"] for read in MAP["reads"] if read["check"] == check for where in read["where"]}
            )
        ci = _engine_module("audit.rules.checks.ci")
        local = {kind.value for kind in ci._LOCAL_SURFACE_KINDS}
        self.assertLessEqual(local, consistency_map.KIND_FILTERED_READS["CI-05"])
        self.assertEqual(consistency_map.scan_kind(".github/workflows/*.yml"), "ci")
        self.assertIsNone(consistency_map.scan_kind("scripts/"))

    def test_r3_the_kinds_are_the_kinds_the_engine_greps(self) -> None:
        """Each set but CI-05's is exactly the kinds the check's helpers pass to ``Inventory.grep``.

        The kinds are written inline in the engine, not in a constant, so the test runs the helpers on an empty
        inventory and records the ``kinds=`` of every grep. Each helper greps on every run, hit or not.
        """
        scan = _engine_module("audit.scan")
        tool = _engine_module("audit.rules.checks.tool")
        execution = _engine_module("audit.rules.checks.execution")
        nav = _engine_module("audit.rules.checks.nav")
        helpers: dict[str, list[Callable[[Any], object]]] = {
            "TOOL-05": [tool._hook_wiring],
            "TOOL-06": [tool._hook_wiring],
            "TOOL-07": [tool._local_guards, tool._hook_wiring],
            "EXEC-04": [execution._referenced_env_keys],
            "NAV-02": [lambda inventory: nav._entry_points(inventory, set(nav._DETECTORS))],
        }
        self.assertEqual(set(helpers) | {"CI-05"}, set(consistency_map.KIND_FILTERED_READS))
        with tempfile.TemporaryDirectory() as folder:
            for check, calls in helpers.items():
                inventory = scan.Inventory(root=Path(folder))
                recorded: set[str] = set()

                def grep(_pattern: object, *, kinds: Any = None, limit: int = 200) -> list[Any]:
                    self.assertIsNotNone(kinds, check)
                    recorded.update(kind.value for kind in kinds)
                    return []

                with mock.patch.object(inventory, "grep", side_effect=grep):
                    for call in calls:
                        call(inventory)
                self.assertEqual(recorded, consistency_map.KIND_FILTERED_READS[check], check)


REAL_PAIRS: list[dict[str, str]] = json.loads(
    (Path(__file__).parent / "fixtures" / "consistency-map-real-pairs.json").read_text(encoding="utf-8")
)["pairs"]


class RealPairsTest(unittest.TestCase):
    """The inference keeps every pair a reviewer found real (``fixtures/consistency-map-real-pairs.json``).

    The pairs come from a triage of the unreviewed list. Each is tested with :func:`consistency_map.touch`, so a
    pair the map has since declared in ``touches`` still counts.

    Two pairs are rubric targets the engine never reads: the row writes a doc file, and the check reads no doc
    through ``**``. Rule R3 drops them on purpose.
    """

    NOT_READ_BY_THE_ENGINE = {
        ("add-hooks-and-commit-rules/row-4", "TOOL-06"),  # writes CONTRIBUTING.md
        ("establish-docs-contract/row-6", "NAV-02"),  # writes a docs page
    }

    def test_every_real_pair_the_engine_reads_is_still_inferred(self) -> None:
        moves = {move["id"]: move for move in MAP["moves"]}
        reads = {read["check"]: read for read in MAP["reads"]}
        lost = {
            (pair["move"], pair["check"])
            for pair in REAL_PAIRS
            if consistency_map.touch(moves[pair["move"]], reads[pair["check"]]) is None
        }
        self.assertEqual(lost, self.NOT_READ_BY_THE_ENGINE)

    def test_every_real_pair_of_the_second_triage_is_inferred_or_declared(self) -> None:
        """The pairs a second triage found real (``fixtures/consistency-map-real-pairs-second-triage.json``).

        They were still unreviewed at origin/dev 9d25b46. A pair counts when :func:`consistency_map.touch` infers it
        or the move declares the check in ``touches``, since declaring it is how a reviewer closes it.
        """
        pairs = json.loads(
            (Path(__file__).parent / "fixtures" / "consistency-map-real-pairs-second-triage.json").read_text(
                encoding="utf-8"
            )
        )["pairs"]
        moves = {move["id"]: move for move in MAP["moves"]}
        reads = {read["check"]: read for read in MAP["reads"]}
        lost = [
            (pair["move"], pair["check"])
            for pair in pairs
            if consistency_map.touch(moves[pair["move"]], reads[pair["check"]]) is None
            and pair["check"] not in moves[pair["move"]].get("touches", [])
        ]
        self.assertGreaterEqual(len(pairs), 60)
        self.assertEqual(lost, [])

    def test_a_section_that_does_not_name_the_check_is_a_mention_problem(self) -> None:
        text = "# T\n\n## A\n\nKeep it on one line.\n\n## B\n\nAGT-06 reads it.\n"
        home = {"path": "x.md", "section": "x.md#t/a", "quote": "q"}
        keep: dict[str, Any] = {"move": "m", "check": "AGT-06", "home": home}
        self.assertIsNotNone(consistency_map.mention_problem(keep, lambda _path: text))
        home["section"] = "x.md#t"
        self.assertIsNone(consistency_map.mention_problem(keep, lambda _path: text))

    def test_the_report_of_this_tree_has_no_structural_problem(self) -> None:
        found = consistency_map.report(MAP, CATALOGUE_IDS)
        for kind in ("quote", "coverage", "names", "constants", "keeps", "mode"):
            self.assertEqual(found[kind], [], kind)

    def test_report_mode_exits_0_and_strict_mode_exits_1_on_a_problem(self) -> None:
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(consistency_map.main([]), 0)
        self.assertIn("consistency map:", out.getvalue())
        # This tree's map has no problem, so strict mode passes on it.
        with redirect_stdout(io.StringIO()):
            self.assertEqual(consistency_map.main(["--strict"]), 0)
        # A copy of the map with one keep removed leaves a touched pair unkept: strict mode fails, report mode not.
        cmap = json.loads(json.dumps(MAP))
        names = {"map_format": cmap["map_format"], "names": cmap.pop("names")}
        cmap["keeps"] = cmap["keeps"][1:]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "consistency-map.json"
            path.write_text(json.dumps(cmap), encoding="utf-8")
            consistency_map.names_path(path).write_text(json.dumps(names), encoding="utf-8")
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(consistency_map.main(["--map", str(path), "--strict"]), 1)
            self.assertIn("unkept: 1", out.getvalue())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(consistency_map.main(["--map", str(path)]), 0)

    def test_json_mode_lists_every_kind(self) -> None:
        with redirect_stdout(io.StringIO()) as out:
            consistency_map.main(["--format", "json"])
        self.assertEqual(set(json.loads(out.getvalue())), {*consistency_map.KINDS, "unreviewed"})


if __name__ == "__main__":
    unittest.main()
