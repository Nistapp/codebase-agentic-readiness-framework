# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The index extractor: a repository's tracked files in, an :class:`~docindex.model.Index` out.

:func:`extract` reads a :class:`~docindex.gitread.Tree` (the working tree, or the tree at a git ref) and the
project config, and builds:

- a **file** node for every tracked file, except those under a prefix of ``exclude.skip`` (``artefacts/``). Its
  ``kind`` comes from ``file_kinds``: the longest suffix of the config that ends the path, else ``other``. Its
  ``zone`` comes from ``zones``: the longest path prefix that the path lies at or under, else ``default_zone``
  (``docs`` when the config names none);
- a **section** node for every heading of every Markdown file, parsed with :mod:`docindex.markdown`. A file under a
  prefix of ``exclude.list_only`` (the fixture trees) is listed as a file node and not parsed. Python, JSON and YAML
  files get no sections;
- a **contains** edge from each Markdown file to each of its top sections, and from each section to each of its
  child sections.

A section's address is the parser's ``<path>#<slug>/<slug>/...``. A heading with no slug text (``#`` alone, or
``## !!!``) has the empty slug on GitHub; the index writes :data:`EMPTY_SEGMENT` in its place, since an address
segment cannot be empty. ``slugify`` never writes a parenthesis, so the placeholder meets no real slug.

The parser's file-level section (the text before the first heading, level 0) is not a node: the file node stands for
it. A tracked path that a node cannot hold (one with a ``#`` or a backslash) is left out and named in
:attr:`Summary.unindexed`.

The section count and the 2,226 headings of the plan
---------------------------------------------------------

A count at commit ``d680388`` found 2,226 headings outside code fences in the repository's Markdown. The index's
section count differs from it, for these reasons:

- The index has no file-level sections. A count of the parser's sections would add one per Markdown file.
- The fixture trees (``exclude.list_only``) are listed, not parsed, so their headings are not sections; and
  ``artefacts/`` is not read at all. A plain count of every ``#`` line takes both in.
- The parser follows CommonMark more closely than a line count: a ``#`` line inside a list item, an HTML comment
  or the YAML frontmatter is no heading, and a setext heading (a line underlined with ``===`` or ``---``) is one.
- The tree has grown since ``d680388``: later commits added Markdown files and headings.

Measured when this module was written (checked): ``build --at d680388`` counts 1,891 sections in 185 Markdown
files. The Markdown of the fixture trees holds 382 lines that start like an ATX heading (a plain ``rg`` count on a
later tree, fences not excluded). So the fixtures account for most of the gap, and the parser's stricter rules for
the rest (inferred, not counted line by line).

:func:`summary_text` writes the counts that make the comparison possible: the Markdown files and the sections per
zone, and the files listed but not parsed. This module imports nothing outside the standard library and this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .gitread import Tree
from .markdown import parse
from .model import Edge, FileNode, Index, Node, SectionNode

__all__ = ["EMPTY_SEGMENT", "Extraction", "Summary", "extract", "file_kind", "summary_text", "zone_of"]

#: The address segment that stands for a heading's empty slug.
EMPTY_SEGMENT = "(empty)"

_DEFAULT_ZONE = "docs"
_DEFAULT_KINDS = {".md": "markdown"}


def _under(path: str, prefix: str) -> bool:
    """Whether ``path`` is ``prefix`` or lies under it. A trailing ``/`` on the prefix does not matter."""
    prefix = prefix.rstrip("/")
    return path == prefix or path.startswith(prefix + "/")


def file_kind(path: str, config: Mapping[str, Any]) -> str:
    """The file kind of ``path``: the kind of the longest ``file_kinds`` suffix that ends it, else ``other``.

    A config with no ``file_kinds`` maps ``.md`` to ``markdown``, as the sweep's scope does.
    """
    kinds: Mapping[str, str] = config.get("file_kinds", _DEFAULT_KINDS)
    matches = [suffix for suffix in kinds if path.endswith(suffix)]
    if not matches:
        return "other"
    return kinds[max(matches, key=lambda suffix: (len(suffix), suffix))]


def zone_of(path: str, config: Mapping[str, Any]) -> str:
    """The zone of ``path``: the zone of the longest ``zones`` prefix it lies at or under, else ``default_zone``."""
    zones: Mapping[str, str] = config.get("zones", {})
    matches = [prefix for prefix in zones if _under(path, prefix)]
    if not matches:
        return str(config.get("default_zone", _DEFAULT_ZONE))
    return zones[max(matches, key=lambda prefix: (len(prefix.rstrip("/")), prefix))]


@dataclass(frozen=True)
class Summary:
    """The counts of one extraction, for the stderr summary. Each per-zone tuple is sorted by zone."""

    files: int
    listed_only: int
    markdown_by_zone: tuple[tuple[str, int], ...]
    sections_by_zone: tuple[tuple[str, int], ...]
    unindexed: tuple[str, ...] = ()

    @property
    def markdown_files(self) -> int:
        return sum(count for _zone, count in self.markdown_by_zone)

    @property
    def sections(self) -> int:
        return sum(count for _zone, count in self.sections_by_zone)


@dataclass(frozen=True)
class Extraction:
    """The index of one tree and the counts behind it."""

    index: Index
    summary: Summary


def _section_nodes(path: str, text: str) -> tuple[list[SectionNode], list[Edge]]:
    """The section nodes of one Markdown file and the ``contains`` edges from the file and between sections."""
    document = parse(path, text)
    # The parent chain is rebuilt from the levels, as the parser builds it, and not looked up by the parser's
    # address: a top heading with the empty slug has the file-level section's address there.
    stack: list[tuple[int, str]] = []  # (level, index address) of the open headings
    nodes: list[SectionNode] = []
    edges: list[Edge] = []
    for section in document.sections:
        if section.parent is None:
            continue  # the file-level section: the file node stands for it
        while stack and stack[-1][0] >= section.level:
            stack.pop()
        parent = stack[-1][1] if stack else path
        segment = section.slug or EMPTY_SEGMENT
        address = f"{parent}/{segment}" if stack else f"{path}#{segment}"
        stack.append((section.level, address))
        nodes.append(
            SectionNode(
                address=address,
                title=section.title,
                level=section.level,
                own_hash=section.own_hash,
                tree_hash=section.tree_hash,
            )
        )
        edges.append(Edge(kind="contains", source=parent, target=address))
    return nodes, edges


def _counts(counter: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counter.items()))


def extract(tree: Tree, config: Mapping[str, Any]) -> Extraction:
    """Build the index of ``tree`` with the project ``config``: file and section nodes and ``contains`` edges."""
    exclude: Mapping[str, Iterable[str]] = config.get("exclude", {})
    skip = list(exclude.get("skip", []))
    list_only = list(exclude.get("list_only", []))
    nodes: list[Node] = []
    edges: list[Edge] = []
    unindexed: list[str] = []
    markdown_by_zone: dict[str, int] = {}
    sections_by_zone: dict[str, int] = {}
    listed_only = 0
    for path in tree.files():
        if any(_under(path, prefix) for prefix in skip):
            continue
        kind = file_kind(path, config)
        zone = zone_of(path, config)
        try:
            node = FileNode(path=path, kind=kind, zone=zone)
        except ValueError:
            unindexed.append(path)
            continue
        nodes.append(node)
        if any(_under(path, prefix) for prefix in list_only):
            listed_only += 1
            continue
        if kind != "markdown":
            continue
        text = tree.read(path)
        if text is None:
            continue
        sections, contains = _section_nodes(path, text)
        nodes.extend(sections)
        edges.extend(contains)
        markdown_by_zone[zone] = markdown_by_zone.get(zone, 0) + 1
        sections_by_zone[zone] = sections_by_zone.get(zone, 0) + len(sections)
    summary = Summary(
        files=sum(1 for node in nodes if isinstance(node, FileNode)),
        listed_only=listed_only,
        markdown_by_zone=_counts(markdown_by_zone),
        sections_by_zone=_counts(sections_by_zone),
        unindexed=tuple(sorted(unindexed)),
    )
    return Extraction(index=Index(nodes=tuple(nodes), edges=tuple(edges)), summary=summary)


def summary_text(summary: Summary, prog: str = "build") -> str:
    """The stderr summary: the totals, then the parsed Markdown files and their sections per zone."""
    sections = dict(summary.sections_by_zone)
    lines = [
        f"{prog}: {summary.files} files, {summary.markdown_files} Markdown files parsed, "
        f"{summary.sections} sections, {summary.listed_only} files listed and not parsed",
    ]
    for zone, count in summary.markdown_by_zone:
        lines.append(f"  {zone}: {count} Markdown files, {sections.get(zone, 0)} sections")
    for path in summary.unindexed:
        lines.append(f"  not indexed (a node cannot hold the path): {path}")
    return "\n".join(lines) + "\n"
