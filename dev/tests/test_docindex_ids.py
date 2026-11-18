# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the index's ``id`` nodes and its ``mentions``, ``runs`` and ``bundles`` edges, the reports and
``query``: in-process, on a temporary git repository, plus one assertion on this repository (every check of
``audit/catalogue.json`` and every ``### REQ-`` heading of ``spec/`` is an ``id`` node with a defining node)."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import doc_index
from docindex import extract, ids, model
from docindex.gitread import WorkTree
from test_docindex_extract import _problems

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Ids Test",
    "GIT_AUTHOR_EMAIL": "ids@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Ids Test",
    "GIT_COMMITTER_EMAIL": "ids@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

BUNDLE = "build/bundle-a"

_CONFIG: dict[str, Any] = {
    "default_zone": "docs",
    "exclude": {"list_only": ["tests/fixtures/"], "skip": ["artefacts/"]},
    "file_kinds": {".json": "json", ".md": "markdown", ".py": "python", ".yaml": "yaml", ".yml": "yaml"},
    "ids": {
        "adr": {
            "address": "{folder}/ADR-{id}",
            "define": {"files": "^(?:.*/)?adrs/(\\d{4})-[^/]+\\.md$"},
            "defined_in": ["adrs/", "sub/adrs/"],
            "pattern": "\\bADR[- ]?(\\d{4})\\b",
        },
        "check": {
            "define": {"json": {"id": "id", "list": "checks", "title": "title"}},
            "defined_in": ["cat/catalogue.json"],
            "pattern": "\\b([A-Z]{2,4}-\\d{2})\\b",
        },
        "playbook": {
            "define": {"files": "^plays/([a-z0-9-]+)\\.md$"},
            "defined_in": ["plays/"],
            "pattern": "\\bplays/([a-z0-9-]+)\\.md\\b",
        },
        "requirement": {
            "define": {"heading": "(REQ-[A-Z]+-\\d{3})\\b", "level": 3},
            "defined_in": ["spec/"],
            "pattern": "\\b(REQ-[A-Z]+-\\d{3})\\b",
        },
        "schema": {
            "define": {"files": "^schemas/([a-z0-9-]+\\.schema\\.json)$"},
            "defined_in": ["schemas/"],
            "pattern": "\\b([a-z0-9-]+\\.schema\\.json)\\b",
        },
        "tool": {
            "address": "tool:{id}",
            "define": {"files": "^(tools/[a-z][a-z0-9_]*\\.py)$"},
            "defined_in": ["tools/"],
            "pattern": "(?<![\\w./-])(tools/[A-Za-z_][A-Za-z0-9_]*\\.py)",
            "runs": True,
        },
    },
    "zones": {"build/": "dev", "recipe/": "recipe", "spec/": "spec", "tests/fixtures/": "fixture", "tools/": "tools"},
}

GUIDE = """# Guide

Check AB-01, REQ-XY-001 and ZZ-99, and follow plays/fix-it.md.

## Span

Run `python3 tools/run_me.py --x` first.

## Block

```bash
python3 tools/run_me.py
```

## Data

```json
{"tool": "tools/run_me.py", "schema": "thing.schema.json"}
```

## Prose

Plain tools/run_me.py here, not ../tools/run_me.py.

## Linked

Text.

## Lonely

Nothing here.
"""

REQS = """# Reqs

### REQ-XY-001 — One thing

Text naming REQ-XY-002 and REQ-XY-001.

### REQ-XY-002: Two

```markdown
### REQ-XY-000 — Example
```

## REQ-XY-003 — Wrong level
"""

_FILES = {
    "cat/catalogue.json": json.dumps({"checks": [{"id": "AB-01", "title": "First"}, {"id": "AB-02", "title": "Sec"}]}),
    "spec/reqs.md": REQS,
    "adrs/0001-first.md": "# 0001 First\n\nThis is ADR 0001.\n",
    "adrs/README.md": "# ADRs\n",
    "sub/adrs/0001-sub.md": "# 0001 Sub\n",
    "sub/page.md": "# Page\n\nSee ADR 0001.\n",
    "other/page.md": "# Page\n\nSee ADR 0001 and [the guide](../recipe/guide.md#linked).\n",
    "tools/run_me.py": '"""Run me: the tool.\n\nMore text.\n"""\n\nprint("tools/run_me.py")\n',
    "tools/_private.py": "X = 1\n",
    "plays/fix-it.md": "# Playbook fix-it\n",
    "plays/README.md": "# Playbooks\n",
    "schemas/thing.schema.json": '{"title": "Thing"}\n',
    "recipe/guide.md": GUIDE,
    "lib/code.py": 'CHECK = "AB-02"  # and REQ-XY-002\n',
    "recipe/data.yml": "check: AB-01\n",
    "tests/fixtures/case/notes.md": "AB-02 in a fixture\n",
}

_BUNDLES = {BUNDLE: ["recipe/*.md", "tools/run_me.py", "cat/catalogue.json", "missing.md"]}


class _Repo(unittest.TestCase):
    """A temporary git repository holding :data:`_FILES`, and its extraction with :data:`_BUNDLES`."""

    root: Path
    result: extract.Extraction
    index: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)
        cls.root = Path(folder.name)
        cls._git("init", "-q")
        for path, text in _FILES.items():
            file = cls.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
        cls._git("add", "-A")
        cls._git("commit", "-q", "-m", "files")
        cls.result = extract.extract(WorkTree(cls.root), _CONFIG, bundles=_BUNDLES)
        cls.index = model.to_dict(cls.result.index)

    @classmethod
    def _git(cls, *args: str) -> None:
        subprocess.run(["git", *args], cwd=cls.root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True)

    def _ids(self) -> dict[str, dict[str, Any]]:
        return {node["address"]: node for node in self.index["nodes"] if node["node"] == "id"}

    def _edges(self, kind: str) -> set[tuple[str, str, str]]:
        return {
            (edge["source"], edge["target"], edge["confidence"]) for edge in self.index["edges"] if edge["kind"] == kind
        }

    def _section(self, path: str, title: str) -> str:
        found: list[str] = [
            node["address"]
            for node in self.index["nodes"]
            if node["node"] == "section" and node["address"].startswith(f"{path}#") and node["title"] == title
        ]
        self.assertEqual(len(found), 1, (path, title))
        return found[0]


class IdNodesTest(_Repo):
    def test_each_kind_defines_its_ids(self) -> None:
        nodes = {address: (node["kind"], node["title"], node["defined_by"]) for address, node in self._ids().items()}
        self.assertEqual(
            nodes,
            {
                "AB-01": ("check", "First", "cat/catalogue.json"),
                "AB-02": ("check", "Sec", "cat/catalogue.json"),
                "REQ-XY-001": ("requirement", "One thing", self._section("spec/reqs.md", "REQ-XY-001 — One thing")),
                "REQ-XY-002": ("requirement", "Two", self._section("spec/reqs.md", "REQ-XY-002: Two")),
                "adrs/ADR-0001": ("adr", "0001 First", "adrs/0001-first.md"),
                "sub/adrs/ADR-0001": ("adr", "0001 Sub", "sub/adrs/0001-sub.md"),
                "fix-it": ("playbook", "Playbook fix-it", "plays/fix-it.md"),
                "thing.schema.json": ("schema", "Thing", "schemas/thing.schema.json"),
                "tool:tools/run_me.py": ("tool", "Run me: the tool.", "tools/run_me.py"),
            },
        )

    def test_every_defining_node_is_in_the_index(self) -> None:
        addresses = {node["address"] for node in self.index["nodes"]}
        for node in self._ids().values():
            with self.subTest(id=node["address"]):
                self.assertIn(node["defined_by"], addresses)

    def test_the_summary_counts_the_ids(self) -> None:
        self.assertEqual(
            self.result.summary.ids_by_kind,
            (("adr", 2), ("check", 2), ("playbook", 1), ("requirement", 2), ("schema", 1), ("tool", 1)),
        )
        text = extract.summary_text(self.result.summary)
        self.assertIn("  ids: adr 2, check 2, playbook 1, requirement 2, schema 1, tool 1\n", text)

    def test_a_taken_address_or_a_second_definition_is_a_problem(self) -> None:
        config = {"ids": {"check": dict(_CONFIG["ids"]["check"], address="cat/catalogue.json")}}
        found = ids.define(config, ["cat/catalogue.json"], lambda path: _FILES.get(path), [], ["cat/catalogue.json"])
        self.assertEqual(found.nodes, ())
        self.assertEqual(len(found.problems), 2)
        twice = json.dumps({"checks": [{"id": "AB-01", "title": "A"}, {"id": "AB-01", "title": "B"}]})
        only_checks = {"ids": {"check": _CONFIG["ids"]["check"]}}
        found = ids.define(only_checks, ["cat/catalogue.json"], lambda _path: twice, [], [])
        self.assertEqual([node.title for node in found.nodes], ["A"])
        self.assertEqual(len(found.problems), 1)

    def test_the_index_is_valid_against_the_schema_and_stable(self) -> None:
        self.assertEqual(_problems(self.index), [])
        self.assertEqual(model.to_dict(model.from_dict(self.index)), self.index)
        again = extract.extract(WorkTree(self.root), _CONFIG, bundles=_BUNDLES).index
        self.assertEqual(model.to_json(again), model.to_json(self.result.index))

    def test_a_config_with_no_ids_adds_no_id_node(self) -> None:
        config = {key: value for key, value in _CONFIG.items() if key != "ids"}
        index = extract.extract(WorkTree(self.root), config).index
        self.assertFalse(any(isinstance(node, model.IdNode) for node in index.nodes))
        self.assertFalse(any(edge.kind in ("mentions", "runs", "bundles") for edge in index.edges))


class MentionsTest(_Repo):
    def test_a_section_mentions_the_ids_it_names(self) -> None:
        mentions = self._edges("mentions")
        guide = "recipe/guide.md#guide"
        self.assertIn((guide, "AB-01", "exact"), mentions)
        self.assertIn((guide, "REQ-XY-001", "exact"), mentions)
        self.assertIn((guide, "fix-it", "exact"), mentions)
        self.assertIn((self._section("recipe/guide.md", "Data"), "thing.schema.json", "exact"), mentions)
        self.assertIn((self._section("recipe/guide.md", "Data"), "tool:tools/run_me.py", "exact"), mentions)

    def test_an_unknown_id_or_one_in_an_unparsed_fixture_gives_no_edge(self) -> None:
        targets = {target for _source, target, _confidence in self._edges("mentions")}
        self.assertNotIn("ZZ-99", targets)
        self.assertNotIn("REQ-XY-000", targets)
        self.assertNotIn("REQ-XY-003", targets)
        self.assertFalse(any(source.startswith("tests/fixtures/") for source, _t, _c in self._edges("mentions")))

    def test_python_json_and_yaml_files_mention_from_the_file_node(self) -> None:
        mentions = self._edges("mentions")
        self.assertIn(("lib/code.py", "AB-02", "exact"), mentions)
        self.assertIn(("lib/code.py", "REQ-XY-002", "exact"), mentions)
        self.assertIn(("recipe/data.yml", "AB-01", "exact"), mentions)

    def test_the_defining_node_does_not_mention_its_own_id(self) -> None:
        mentions = self._edges("mentions")
        one = self._section("spec/reqs.md", "REQ-XY-001 — One thing")
        self.assertIn((one, "REQ-XY-002", "exact"), mentions)
        self.assertNotIn((one, "REQ-XY-001", "exact"), mentions)
        self.assertFalse(any(source.startswith("adrs/0001-first.md") for source, _t, _c in mentions))
        self.assertFalse(any(source.startswith("cat/catalogue.json") for source, _t, _c in mentions))
        self.assertFalse(any(source == "tools/run_me.py" for source, _t, _c in mentions))

    def test_a_shared_adr_number_resolves_to_the_nearest_folder(self) -> None:
        mentions = self._edges("mentions")
        self.assertIn(("sub/page.md#page", "sub/adrs/ADR-0001", "exact"), mentions)
        self.assertIn(("other/page.md#page", "adrs/ADR-0001", "name-match"), mentions)

    def test_a_path_inside_another_path_is_no_tool_mention(self) -> None:
        prose = self._section("recipe/guide.md", "Prose")
        self.assertEqual({t for s, t, _c in self._edges("mentions") if s == prose}, {"tool:tools/run_me.py"})


class RunsTest(_Repo):
    def test_runs_come_from_code_spans_and_command_blocks_only(self) -> None:
        self.assertEqual(
            self._edges("runs"),
            {
                (self._section("recipe/guide.md", "Span"), "tool:tools/run_me.py", "exact"),
                (self._section("recipe/guide.md", "Block"), "tool:tools/run_me.py", "exact"),
            },
        )


class BundlesTest(_Repo):
    def test_a_bundle_node_ships_its_members(self) -> None:
        self.assertEqual(
            sorted(self._edges("bundles")),
            [
                (BUNDLE, "cat/catalogue.json", "exact"),
                (BUNDLE, "recipe/guide.md", "exact"),
                (BUNDLE, "tools/run_me.py", "exact"),
            ],
        )
        node = next(node for node in self.index["nodes"] if node["address"] == BUNDLE)
        self.assertEqual((node["node"], node["kind"], node["zone"]), ("file", "other", "dev"))

    def test_the_summary_counts_members_and_names_an_empty_entry(self) -> None:
        summary = self.result.summary
        self.assertEqual(summary.bundles, ((BUNDLE, 3),))
        self.assertEqual(summary.files, len(_FILES))
        self.assertEqual(summary.id_problems, (f"bundle {BUNDLE}: the entry missing.md names no indexed file",))

    def test_bundle_entries_name_files_folders_and_markdown_under_folders(self) -> None:
        files = ["a/b.md", "a/c/d.md", "a/e.py", "ab.md", "f.txt"]
        self.assertEqual(ids.bundle_members(["a/*.md"], files), (["a/b.md", "a/c/d.md"], []))
        self.assertEqual(ids.bundle_members(["a/"], files), (["a/b.md", "a/c/d.md", "a/e.py"], []))
        self.assertEqual(ids.bundle_members(["f.txt", "g.txt"], files), (["f.txt"], ["g.txt"]))

    def test_the_bundles_also_come_from_the_config_key(self) -> None:
        config = dict(_CONFIG, **{extract.BUNDLE_FILES: _BUNDLES})
        index = extract.extract(WorkTree(self.root), config).index
        self.assertEqual(model.to_json(index), model.to_json(self.result.index))


class ReportsTest(_Repo):
    def test_the_three_reports(self) -> None:
        found = ids.reports(self.result.index)
        self.assertIn(self._section("recipe/guide.md", "Lonely"), found.unlinked_sections)
        self.assertNotIn(self._section("recipe/guide.md", "Linked"), found.unlinked_sections)
        self.assertNotIn("recipe/guide.md#guide", found.unlinked_sections)
        self.assertFalse(any(not address.startswith("recipe/") for address in found.unlinked_sections))
        self.assertEqual(found.unnamed_bundle_files, ((BUNDLE, "recipe/guide.md"),))
        self.assertEqual(found.unmentioned_checks, ("AB-02",))
        text = ids.reports_text(found)
        self.assertIn("check IDs that no recipe file mentions: 1\n  AB-02\n", text)
        self.assertIn(f"bundled files that no file of their bundle names: 1\n  {BUNDLE}: recipe/guide.md\n", text)


class QueryTest(_Repo):
    def _query(self, *argv: str) -> tuple[int, str, str]:
        return ids.query_main(list(argv), lambda _at: self.result.index)

    def test_a_node_and_its_edges(self) -> None:
        code, out, err = self._query("AB-01")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual(json.loads(lines[0])["defined_by"], "cat/catalogue.json")
        self.assertEqual(lines[1], "outgoing: 0")
        self.assertIn("  mentions recipe/guide.md#guide (exact)", lines)
        self.assertIn("  mentions recipe/data.yml (exact)", lines)

    def test_outgoing_edges_keep_the_anchor(self) -> None:
        code, out, _err = self._query("other/page.md#page")
        self.assertEqual(code, 0)
        linked = self._section("recipe/guide.md", "Linked")
        self.assertIn(f"  links {linked} (exact, anchor #linked)", out.splitlines())

    def test_the_reports_and_the_errors(self) -> None:
        code, out, _err = self._query("--report")
        self.assertEqual(code, 0)
        self.assertIn("check IDs that no recipe file mentions: 1", out)
        code, out, err = self._query("NO-01")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("no node has the address 'NO-01'", err)
        for argv in ((), ("AB-01", "--report")):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                self._query(*argv)
            self.assertEqual(caught.exception.code, 2)


class ThisRepositoryTest(unittest.TestCase):
    """The ids of this repository's own config, and the entry point's bundles."""

    index: model.Index

    @classmethod
    def setUpClass(cls) -> None:
        cls.index = extract.extract(WorkTree(doc_index.REPO), doc_index.full_config()).index

    def _nodes(self) -> dict[str, model.Node]:
        return {node.address: node for node in self.index.nodes}

    def test_every_catalogue_check_is_an_id_node_defined_by_the_catalogue(self) -> None:
        catalogue = json.loads((doc_index.REPO / "audit" / "catalogue.json").read_text(encoding="utf-8"))
        checks = [check["id"] for check in catalogue["checks"]]
        self.assertGreater(len(checks), 50)
        nodes = self._nodes()
        for check in checks:
            with self.subTest(check=check):
                node = nodes.get(check)
                assert isinstance(node, model.IdNode), check
                self.assertEqual((node.kind, node.defined_by), ("check", "audit/catalogue.json"))
                self.assertIsInstance(nodes.get(node.defined_by), model.FileNode)

    def test_every_spec_requirement_heading_is_an_id_node_defined_by_its_section(self) -> None:
        heading = re.compile(r"^### (REQ-[A-Z]+-[0-9]+)\b")
        found: list[tuple[str, str]] = []
        for path in WorkTree(doc_index.REPO).files():
            if not (path.startswith("spec/") and path.endswith(".md")):
                continue
            fenced = False
            for line in (doc_index.REPO / path).read_text(encoding="utf-8").splitlines():
                if re.match(r"^\s*(```|~~~)", line):
                    fenced = not fenced
                    continue
                match = heading.match(line)
                if match and not fenced:
                    found.append((path, match.group(1)))
        self.assertGreater(len(found), 50)
        nodes = self._nodes()
        for path, requirement in found:
            with self.subTest(requirement=requirement):
                node = nodes.get(requirement)
                assert isinstance(node, model.IdNode), requirement
                self.assertEqual(node.kind, "requirement")
                section = nodes.get(node.defined_by)
                assert isinstance(section, model.SectionNode), node.defined_by
                self.assertEqual(section.path, path)
                self.assertTrue(section.title.startswith(requirement))

    def test_the_entry_point_passes_both_bundles(self) -> None:
        bundles = doc_index.bundle_files(doc_index.load_config())
        self.assertEqual(
            sorted(bundles),
            ["dev/dist/skills/agentic-readiness-audit", "dev/dist/skills/agentic-readiness-implement"],
        )
        self.assertIn("audit/checks/*.md", bundles["dev/dist/skills/agentic-readiness-audit"])
        self.assertIn("audit/engine/audit/", bundles["dev/dist/skills/agentic-readiness-audit"])
        self.assertIn("implement/tools/progress.py", bundles["dev/dist/skills/agentic-readiness-implement"])
        nodes = self._nodes()
        members: dict[str, set[str]] = {}
        for edge in self.index.edges:
            if edge.kind == "bundles":
                self.assertIsInstance(nodes.get(edge.target), model.FileNode)
                members.setdefault(edge.source, set()).add(edge.target)
        self.assertEqual(sorted(members), sorted(bundles))
        self.assertIn("audit/SKILL.md", members["dev/dist/skills/agentic-readiness-audit"])
        self.assertIn("implement/SKILL.md", members["dev/dist/skills/agentic-readiness-implement"])

    def test_query_through_the_entry_point(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = doc_index.query(["CMD-01"])
        self.assertEqual(code, 0, err.getvalue())
        self.assertEqual(json.loads(out.getvalue().splitlines()[0])["kind"], "check")

    def _main(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = doc_index.main(list(argv))
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
        return code, out.getvalue(), err.getvalue()

    def test_the_entry_point_routes_query_with_its_exit_codes(self) -> None:
        code, out, err = self._main("query", "CMD-01")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual(json.loads(lines[0])["defined_by"], "audit/catalogue.json")
        self.assertEqual(lines[1], "outgoing: 0")
        self.assertNotIn("not implemented yet", err)
        code, out, err = self._main("query", "NO-SUCH-ADDRESS")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("no node has the address 'NO-SUCH-ADDRESS'", err)
        for argv in (("query",), ("query", "CMD-01", "--report")):
            with self.subTest(argv=argv):
                self.assertEqual(self._main(*argv)[0], 2)

    def test_the_entry_point_prints_the_reports(self) -> None:
        code, out, err = self._main("query", "--report")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("recipe sections that nothing links to and that mention no ID: ", out)
        self.assertIn("bundled files that no file of their bundle names: ", out)
        self.assertIn("check IDs that no recipe file mentions: ", out)


if __name__ == "__main__":
    unittest.main()
