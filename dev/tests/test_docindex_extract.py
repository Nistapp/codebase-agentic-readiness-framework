# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the index extractor (file and section nodes, contains edges), on temporary git repositories.

The section count is not compared with a fixed number: ``docindex.extract``'s docstring explains how it differs
from the plan's 2,226 headings (no file-level sections, the fixture trees listed and not parsed, ``artefacts/`` not
read, the parser's CommonMark rules, and a tree that has grown since).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import doc_index
from docindex import extract, model
from docindex.gitread import GitError, RefTree, WorkTree

SCHEMA: dict[str, Any] = json.loads((doc_index.DEV / "docindex" / "index.schema.json").read_text(encoding="utf-8"))

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Extract Test",
    "GIT_AUTHOR_EMAIL": "extract@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Extract Test",
    "GIT_COMMITTER_EMAIL": "extract@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

#: The temporary repository's config: no fixture file is named like the repository's own instruction files.
_CONFIG: dict[str, Any] = {
    "default_zone": "docs",
    "exclude": {"list_only": ["tests/fixtures/"], "skip": ["artefacts/"]},
    "file_kinds": {".json": "json", ".md": "markdown", ".py": "python", ".yaml": "yaml", ".yml": "yaml"},
    "zones": {
        "Makefile": "dev",
        "recipe/": "recipe",
        "recipe/docs/": "docs",
        "tests/fixtures/": "fixture",
        "tools/": "tools",
    },
}

GUIDE = """---
title: The guide
---

Text before the first heading.

# Guide

Intro.

## Steps

### First

Do this.

## Steps

```bash
# not a heading
```

Setext
------

# Notes
"""

_FILES = {
    "recipe/GUIDE.md": GUIDE,
    "recipe/docs/page.md": "No heading at all.\n",
    "recipe/run.py": "# a comment, not a heading\n",
    "tools/data.json": "{}\n",
    "tools/ci.yml": "on: push\n",
    "Makefile": "all:\n",
    "README.md": "#\n\n## Under the empty one\n\n# Other\n",
    "tests/fixtures/case/RULES.md": "# Fixture heading\n",
    "artefacts/notes.md": "# Scratch\n",
}


def _problems(value: dict[str, Any]) -> list[str]:
    """Check an index against the keywords that ``index.schema.json`` uses; not a general validator."""
    defs = SCHEMA["$defs"]
    problems: list[str] = []
    if set(value) != set(SCHEMA["required"]) or value["index_format"] != SCHEMA["properties"]["index_format"]["const"]:
        problems.append("top level")
    items = [(node, defs[node["node"]]) for node in value["nodes"]] + [(edge, defs["edge"]) for edge in value["edges"]]
    for item, schema in items:
        if not set(schema["required"]) <= set(item) <= set(schema["properties"]):
            problems.append(f"keys of {item}")
        for key, rule in schema["properties"].items():
            if key not in item:
                continue
            rule = defs[rule["$ref"].rsplit("/", 1)[-1]] if "$ref" in rule else rule
            if "enum" in rule and item[key] not in rule["enum"]:
                problems.append(f"{key} of {item}")
            if "const" in rule and item[key] != rule["const"]:
                problems.append(f"{key} of {item}")
            if "pattern" in rule and not re.search(rule["pattern"], item[key]):
                problems.append(f"{key} of {item}")
            if "minimum" in rule and not rule["minimum"] <= item[key] <= rule["maximum"]:
                problems.append(f"{key} of {item}")
    return problems


class _Repo(unittest.TestCase):
    """A temporary git repository; :meth:`_commit` writes files and commits them."""

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self._git("init", "-q")

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def _commit(self, files: dict[str, str]) -> str:
        for path, text in files.items():
            file = self.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "change")
        return self._git("rev-parse", "HEAD")

    def _index(self, config: dict[str, Any] = _CONFIG) -> dict[str, Any]:
        return model.to_dict(extract.extract(WorkTree(self.root), config).index)


def _nodes(index: dict[str, Any], node: str) -> dict[str, dict[str, Any]]:
    return {item["address"]: item for item in index["nodes"] if item["node"] == node}


def _contains(index: dict[str, Any]) -> list[tuple[str, str]]:
    return [(edge["source"], edge["target"]) for edge in index["edges"] if edge["kind"] == "contains"]


class SmallTreeTest(_Repo):
    def setUp(self) -> None:
        super().setUp()
        self._commit(_FILES)
        self.index = self._index()

    def test_every_tracked_file_has_a_kind_and_a_zone(self) -> None:
        files = {address: (node["kind"], node["zone"]) for address, node in _nodes(self.index, "file").items()}
        self.assertEqual(
            files,
            {
                "Makefile": ("other", "dev"),
                "README.md": ("markdown", "docs"),
                "recipe/GUIDE.md": ("markdown", "recipe"),
                "recipe/docs/page.md": ("markdown", "docs"),
                "recipe/run.py": ("python", "recipe"),
                "tests/fixtures/case/RULES.md": ("markdown", "fixture"),
                "tools/ci.yml": ("yaml", "tools"),
                "tools/data.json": ("json", "tools"),
            },
        )

    def test_markdown_headings_become_sections(self) -> None:
        sections = _nodes(self.index, "section")
        guide = {address: (node["title"], node["level"]) for address, node in sections.items() if "GUIDE" in address}
        self.assertEqual(
            guide,
            {
                "recipe/GUIDE.md#guide": ("Guide", 1),
                "recipe/GUIDE.md#guide/steps": ("Steps", 2),
                "recipe/GUIDE.md#guide/steps/first": ("First", 3),
                "recipe/GUIDE.md#guide/steps-1": ("Steps", 2),
                "recipe/GUIDE.md#guide/setext": ("Setext", 2),
                "recipe/GUIDE.md#notes": ("Notes", 1),
            },
        )
        for node in sections.values():
            self.assertRegex(node["own_hash"], r"^[0-9a-f]{64}$")
            self.assertRegex(node["tree_hash"], r"^[0-9a-f]{64}$")

    def test_contains_edges_run_from_the_file_and_from_each_parent(self) -> None:
        edges = [edge for edge in _contains(self.index) if edge[0].startswith("recipe/GUIDE.md")]
        self.assertEqual(
            sorted(edges),
            [
                ("recipe/GUIDE.md", "recipe/GUIDE.md#guide"),
                ("recipe/GUIDE.md", "recipe/GUIDE.md#notes"),
                ("recipe/GUIDE.md#guide", "recipe/GUIDE.md#guide/setext"),
                ("recipe/GUIDE.md#guide", "recipe/GUIDE.md#guide/steps"),
                ("recipe/GUIDE.md#guide", "recipe/GUIDE.md#guide/steps-1"),
                ("recipe/GUIDE.md#guide/steps", "recipe/GUIDE.md#guide/steps/first"),
            ],
        )
        self.assertTrue(all(edge["confidence"] == "exact" for edge in self.index["edges"]))
        self.assertEqual({edge["kind"] for edge in self.index["edges"]}, {"contains"})

    def test_a_file_with_no_heading_and_other_kinds_have_no_sections(self) -> None:
        sources = {source for source, _target in _contains(self.index)}
        for path in ("recipe/docs/page.md", "recipe/run.py", "tools/data.json", "tools/ci.yml", "Makefile"):
            with self.subTest(path=path):
                self.assertNotIn(path, sources)
                self.assertFalse(any(address.startswith(f"{path}#") for address in _nodes(self.index, "section")))

    def test_an_empty_slug_gets_the_placeholder_segment(self) -> None:
        sections = _nodes(self.index, "section")
        empty = f"README.md#{extract.EMPTY_SEGMENT}"
        self.assertEqual(sections[empty]["title"], "")
        self.assertIn(f"{empty}/under-the-empty-one", sections)
        self.assertIn("README.md#other", sections)
        self.assertIn(("README.md", "README.md#other"), _contains(self.index))
        self.assertIn(("README.md", empty), _contains(self.index))

    def test_fixtures_are_listed_and_not_parsed(self) -> None:
        self.assertIn("tests/fixtures/case/RULES.md", _nodes(self.index, "file"))
        addresses = [item["address"] for item in self.index["nodes"]]
        self.assertFalse(any(address.startswith("tests/fixtures/case/RULES.md#") for address in addresses))

    def test_artefacts_are_excluded(self) -> None:
        addresses = [item["address"] for item in self.index["nodes"]]
        self.assertFalse(any(address.startswith("artefacts/") for address in addresses))

    def test_the_index_is_valid_against_the_schema(self) -> None:
        self.assertEqual(_problems(self.index), [])
        self.assertEqual(model.to_dict(model.from_dict(self.index)), self.index)

    def test_two_runs_are_byte_identical(self) -> None:
        first = model.to_json(extract.extract(WorkTree(self.root), _CONFIG).index)
        second = model.to_json(extract.extract(WorkTree(self.root), _CONFIG).index)
        self.assertEqual(first.encode("utf-8"), second.encode("utf-8"))
        self.assertNotIn(str(self.root), first)

    def test_the_summary_counts_markdown_files_and_sections_by_zone(self) -> None:
        summary = extract.extract(WorkTree(self.root), _CONFIG).summary
        self.assertEqual(summary.files, 8)
        self.assertEqual(summary.listed_only, 1)
        self.assertEqual(summary.markdown_by_zone, (("docs", 2), ("recipe", 1)))
        self.assertEqual(summary.sections_by_zone, (("docs", 3), ("recipe", 6)))
        text = extract.summary_text(summary, prog="build")
        self.assertTrue(text.startswith("build: 8 files, 3 Markdown files parsed, 9 sections, 1 files listed"))
        self.assertIn("  recipe: 1 Markdown files, 6 sections\n", text)


class AtRefTest(_Repo):
    def test_an_older_commit_is_indexed_as_it_was(self) -> None:
        old = self._commit({"a.md": "# Old\n", "b.md": "# Kept\n"})
        self._commit({"a.md": "# New\n\n## Child\n", "c.py": "x = 1\n"})
        (self.root / "b.md").write_text("# Changed on disk\n", encoding="utf-8")
        at_old = model.to_dict(extract.extract(RefTree(self.root, old), _CONFIG).index)
        self.assertEqual(set(_nodes(at_old, "file")), {"a.md", "b.md"})
        self.assertEqual(set(_nodes(at_old, "section")), {"a.md#old", "b.md#kept"})
        now = self._index()
        self.assertEqual(set(_nodes(now, "file")), {"a.md", "b.md", "c.py"})
        self.assertEqual(set(_nodes(now, "section")), {"a.md#new", "a.md#new/child", "b.md#changed-on-disk"})

    def test_the_same_tree_gives_the_same_index_at_a_ref_and_on_disk(self) -> None:
        head = self._commit(_FILES)
        at_head = model.to_json(extract.extract(RefTree(self.root, head), _CONFIG).index)
        self.assertEqual(at_head, model.to_json(extract.extract(WorkTree(self.root), _CONFIG).index))

    def test_a_ref_that_names_no_commit_is_refused(self) -> None:
        self._commit({"a.md": "# A\n"})
        with self.assertRaises(GitError):
            RefTree(self.root, "no-such-ref")


class ConfigRulesTest(unittest.TestCase):
    def test_the_longest_suffix_and_prefix_win(self) -> None:
        config = {"file_kinds": {".md": "markdown", ".schema.json": "json", ".json": "other"}}
        self.assertEqual(extract.file_kind("a/b.schema.json", config), "json")
        self.assertEqual(extract.file_kind("a/b.json", config), "other")
        self.assertEqual(extract.file_kind("Makefile", config), "other")
        self.assertEqual(extract.zone_of("recipe/docs/x.md", _CONFIG), "docs")
        self.assertEqual(extract.zone_of("recipe/x.md", _CONFIG), "recipe")
        self.assertEqual(extract.zone_of("Makefile", _CONFIG), "dev")
        self.assertEqual(extract.zone_of("Makefile.bak", _CONFIG), "docs")
        self.assertEqual(extract.zone_of("recipes/x.md", _CONFIG), "docs")

    def test_an_empty_config_still_parses_markdown(self) -> None:
        self.assertEqual(extract.file_kind("a.md", {}), "markdown")
        self.assertEqual(extract.zone_of("a.md", {}), "docs")


class ThisRepositoryTest(unittest.TestCase):
    def test_the_build_succeeds_and_the_counts_are_positive(self) -> None:
        result = extract.extract(WorkTree(doc_index.REPO), doc_index.load_config())
        summary = result.summary
        self.assertGreater(summary.files, 0)
        self.assertGreater(summary.markdown_files, 0)
        self.assertGreater(summary.sections, 0)
        self.assertGreater(summary.listed_only, 0)
        self.assertEqual(summary.unindexed, ())
        index = model.to_dict(result.index)
        self.assertEqual(_problems(index), [])
        files = _nodes(index, "file")
        self.assertFalse(any(path.startswith("artefacts/") for path in files))
        fixtures = [path for path in files if path.startswith("audit/engine/tests/fixtures/")]
        self.assertGreater(len(fixtures), 0)
        self.assertTrue(all(files[path]["zone"] == "fixture" for path in fixtures))


if __name__ == "__main__":
    unittest.main()
