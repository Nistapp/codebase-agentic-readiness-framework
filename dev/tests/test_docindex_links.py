# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the ``links`` edges of the index (``docindex.links``), in-process on a temporary git repository."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from docindex import extract, links, markdown, model
from docindex.gitread import WorkTree

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Links Test",
    "GIT_AUTHOR_EMAIL": "links@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Links Test",
    "GIT_COMMITTER_EMAIL": "links@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}

_CONFIG: dict[str, Any] = {
    "default_zone": "docs",
    "exclude": {"list_only": ["tests/fixtures/"], "skip": ["artefacts/"]},
    "file_kinds": {".md": "markdown", ".py": "python"},
}

GUIDE = """---
title: links in [frontmatter](page.md)
---

# Guide

See [the page](page.md) and [its steps](page.md#steps), and [notes](#notes) here.

```text
[in a fence](fenced.md)
```

![a diagram](diagram.png)
Visit [a site](https://example.com/page.md), [mail](mailto:someone@example.invalid) or [far](//example.com/x.md).
A [broken one](missing.md), a [bad anchor](page.md#nowhere) and [an escape](../../outside.md).
Run recipe_lint.py often; tool.py is in two folders; guide.md is this file.

## Notes

`[a code span](span.md)` is code, and so is fenced.md here in prose.
[![badge](diagram.png)](page.md#steps "with a title") and \\[not a link](page.md).
[again](page.md) and [again](./page.md).
"""

_FILES = {
    "docs/guide.md": GUIDE,
    "docs/page.md": "# Page\n\n## Steps\n\nText.\n",
    "docs/fenced.md": "# Fenced\n",
    "docs/folders.md": "# Folders\n\n[tools](../tools/), [dev](../dev), [here](./), [root](../) and [a file](page.md).\n",
    "docs/diagram.png": "not really a picture\n",
    "dev/recipe_lint.py": "x = 1\n",
    "dev/tool.py": "x = 1\n",
    "tools/tool.py": "x = 1\n",
    "tests/fixtures/case/page.md": "[fixture link](nowhere.md)\n",
}


class _Repo(unittest.TestCase):
    """A temporary git repository with :data:`_FILES` committed, and its index."""

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self._git("init", "-q")
        for path, text in _FILES.items():
            file = self.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "files")
        self.result = extract.extract(WorkTree(self.root), _CONFIG)

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def _links(self, source: str) -> set[tuple[str, str, str | None]]:
        return {
            (edge.target, edge.confidence, edge.anchor)
            for edge in self.result.index.edges
            if edge.kind == "links" and edge.source == source
        }


class LinkEdgesTest(_Repo):
    def test_a_relative_link_goes_to_the_file_node(self) -> None:
        self.assertIn(("docs/page.md", "exact", None), self._links("docs/guide.md#guide"))

    def test_a_link_with_an_anchor_goes_to_the_section_node_and_keeps_the_anchor(self) -> None:
        guide = self._links("docs/guide.md#guide")
        self.assertIn(("docs/page.md#page/steps", "exact", "steps"), guide)
        self.assertIn(("docs/guide.md#guide/notes", "exact", "notes"), guide)
        notes = self._links("docs/guide.md#guide/notes")
        self.assertIn(("docs/page.md#page/steps", "exact", "steps"), notes)

    def test_the_frontmatter_link_comes_from_the_file_node(self) -> None:
        self.assertEqual(self._links("docs/guide.md"), {("docs/page.md", "exact", None)})

    def test_a_link_inside_a_fence_or_a_code_span_is_ignored(self) -> None:
        targets = {target for target, _confidence, _anchor in self._links("docs/guide.md#guide")}
        self.assertNotIn("docs/fenced.md", targets)
        self.assertNotIn("docs/span.md", {target for target, _c, _a in self._links("docs/guide.md#guide/notes")})
        self.assertFalse(any("span" in link.target or "fenced" in link.target for link in self.result.problems))

    def test_an_image_is_ignored_but_a_link_around_an_image_is_kept(self) -> None:
        every = {edge.target for edge in self.result.index.edges if edge.kind == "links"}
        self.assertNotIn("docs/diagram.png", every)
        self.assertIn(("docs/page.md#page/steps", "exact", "steps"), self._links("docs/guide.md#guide/notes"))

    def test_external_targets_are_ignored(self) -> None:
        for edge in self.result.index.edges:
            with self.subTest(edge=edge):
                self.assertNotIn("example", edge.target)
                self.assertNotIn("mailto", edge.target)

    def test_a_broken_link_is_kept_with_a_flag(self) -> None:
        guide = self._links("docs/guide.md#guide")
        self.assertIn(("docs/missing.md", "exact", None), guide)
        self.assertIn(("docs/page.md", "exact", "nowhere"), guide)
        self.assertIn(("../outside.md", "exact", None), guide)
        flagged = {(link.source, link.target, link.path, link.anchor, link.problem) for link in self.result.problems}
        self.assertEqual(
            flagged,
            {
                ("docs/guide.md#guide", "missing.md", "docs/missing.md", None, "missing"),
                ("docs/guide.md#guide", "page.md#nowhere", "docs/page.md", "nowhere", "anchor"),
                ("docs/guide.md#guide", "../../outside.md", "../outside.md", None, "outside"),
            },
        )
        text = extract.summary_text(self.result.summary)
        self.assertIn("  broken link (kept in the index): docs/guide.md#guide -> missing.md (missing)\n", text)
        broken = {
            (edge.target, edge.broken)
            for edge in self.result.index.edges
            if edge.kind == "links" and edge.source == "docs/guide.md#guide" and edge.broken is not None
        }
        self.assertEqual(
            broken, {("docs/missing.md", "missing"), ("docs/page.md", "anchor"), ("../outside.md", "outside")}
        )
        self.assertTrue(all(edge.broken is None for edge in self.result.index.edges if edge.kind != "links"))

    def test_a_bare_file_name_gets_a_name_match_edge(self) -> None:
        guide = self._links("docs/guide.md#guide")
        self.assertIn(("dev/recipe_lint.py", "name-match", None), guide)
        names = {target for target, confidence, _anchor in guide if confidence == "name-match"}
        self.assertEqual(names, {"dev/recipe_lint.py"})  # tool.py is in two folders; guide.md is the file itself
        notes = self._links("docs/guide.md#guide/notes")
        self.assertIn(("docs/fenced.md", "name-match", None), notes)

    def test_a_link_to_a_folder_is_a_name_match_edge(self) -> None:
        self.assertEqual(
            self._links("docs/folders.md#folders"),
            {
                ("tools", "name-match", None),
                ("dev", "name-match", None),
                ("docs", "name-match", None),
                (".", "name-match", None),
                ("docs/page.md", "exact", None),
            },
        )
        addresses = {node.address for node in self.result.index.nodes}
        self.assertFalse({"tools", "dev", "docs", "."} & addresses)  # the index has no folder nodes
        self.assertFalse(any(link.source.startswith("docs/folders.md") for link in self.result.problems))

    def test_the_same_link_twice_is_one_edge_and_an_escaped_bracket_is_no_link(self) -> None:
        notes = self._links("docs/guide.md#guide/notes")
        exact = sorted((target, anchor or "") for target, confidence, anchor in notes if confidence == "exact")
        self.assertEqual(exact, [("docs/page.md", ""), ("docs/page.md#page/steps", "steps")])

    def test_a_fixture_is_not_parsed_for_links(self) -> None:
        self.assertEqual(self._links("tests/fixtures/case/page.md"), set())
        self.assertFalse(any(link.source.startswith("tests/") for link in self.result.problems))

    def test_the_index_round_trips_and_is_deterministic(self) -> None:
        text = model.to_json(self.result.index)
        self.assertEqual(model.to_json(model.from_json(text)), text)
        self.assertEqual(model.to_json(extract.extract(WorkTree(self.root), _CONFIG).index), text)
        self.assertNotIn(str(self.root), text)


class FindLinksTest(unittest.TestCase):
    def _targets(self, text: str) -> list[str]:
        return [found.text for found in links.find_links(markdown.parse("a/b.md", text))]

    def test_destination_forms(self) -> None:
        text = (
            "[a](x.md) [b](<y z.md>) [c](p(1).md) [d](q.md 'title') [e](r.md (title))\n"
            "[ref][label] [checkbox] [ ] [g]( t.md ) [h]()\n"
        )
        self.assertEqual(self._targets(text), ["x.md", "y z.md", "p(1).md", "q.md", "r.md", "t.md"])

    def test_a_nested_bracket_and_a_link_in_a_heading(self) -> None:
        self.assertEqual(self._targets("# See [the [x] page](x.md)\n\n[a [b](c.md) d]\n"), ["x.md", "c.md"])

    def test_external_schemes(self) -> None:
        external = ("https://a.example", "http://a.example", "mailto:x@a.example", "ftp://a.example", "//a.example")
        for target in external:
            with self.subTest(target=target):
                self.assertTrue(links.is_external(target))
        for target in ("x.md", "../x.md#a", "#a", "dir/"):
            with self.subTest(target=target):
                self.assertFalse(links.is_external(target))


class ResolveTest(unittest.TestCase):
    def test_paths_and_anchors(self) -> None:
        self.assertEqual(links.resolve("a/b.md", "c.md"), ("a/c.md", None))
        self.assertEqual(links.resolve("a/b.md", "../c.md#x"), ("c.md", "x"))
        self.assertEqual(links.resolve("a/b.md", "#x"), ("a/b.md", "x"))
        self.assertEqual(links.resolve("a/b.md", "c.md#"), ("a/c.md", None))
        self.assertEqual(links.resolve("a/b.md", "./d/../my%20file.md"), ("a/my file.md", None))
        self.assertEqual(links.resolve("a/b.md", "../../up.md"), ("../up.md", None))
        self.assertEqual(links.resolve("b.md", "dir/"), ("dir", None))
        self.assertEqual(links.resolve("a/b.md", "/root.md"), ("root.md", None))


if __name__ == "__main__":
    unittest.main()
