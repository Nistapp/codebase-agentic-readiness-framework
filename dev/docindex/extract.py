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
  child sections;
- a **links** edge for each inline link and each bare file name of a parsed Markdown file (:mod:`docindex.links`).
  A link's anchor resolves against the slugs of the target file's headings, so a second pass runs after every file
  is parsed. A link whose target does not resolve keeps its edge and is flagged in :attr:`Extraction.problems` and
  in the summary's ``broken link`` lines;
- an **id** node for each ID that the config's ``ids`` kinds define, and the **mentions** edges from the sections
  of every parsed Markdown file and from every Python, JSON and YAML file outside ``exclude.list_only``, and the
  **runs** edges from the sections to the tools (:mod:`docindex.ids`, which states the rules);
- a node for each bundle and a **bundles** edge from it to each file it ships. The bundles come from the caller:
  the entry point reads them from the project's bundle module and passes them in the config's
  :data:`BUNDLE_FILES` key (or the ``bundles`` argument). The model has no bundle node type, so a bundle's node is
  a file node at the bundle's build folder (``dev/dist/skills/<bundle>``, git-ignored, so no tracked file holds
  the address); its kind and zone follow the config's rules like any path.

A section's address is the parser's ``<path>#<slug>/<slug>/...``. A heading with no slug text (``#`` alone, or
``## !!!``) has the empty slug on GitHub; the index writes :data:`EMPTY_SEGMENT` in its place, since an address
segment cannot be empty. ``slugify`` never writes a parenthesis, so the placeholder meets no real slug.

A path entry of the config that no tracked file lies at or under (a typo, or a folder the tree at an older ref
lacks) is named in :attr:`Summary.config_problems` (:func:`docindex.config.unmatched`), as a warning.

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
from typing import Any, Iterable, Mapping, Sequence

from . import ids
from .config import BUNDLE_FILES, unmatched
from .gitread import Tree
from .links import Link, LinkContext, link_edges
from .markdown import Document, parse
from .model import Edge, FileNode, Index, Node, SectionNode

__all__ = [
    "BUNDLE_FILES",
    "EMPTY_SEGMENT",
    "MENTION_KINDS",
    "Extraction",
    "Summary",
    "extract",
    "file_kind",
    "summary_text",
    "zone_of",
]

#: The file kinds, other than Markdown, that are read as plain text for ID mentions.
MENTION_KINDS = ("python", "json", "yaml")

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
    broken_links: tuple[str, ...] = ()
    ids_by_kind: tuple[tuple[str, int], ...] = ()
    bundles: tuple[tuple[str, int], ...] = ()
    id_problems: tuple[str, ...] = ()
    config_problems: tuple[str, ...] = ()

    @property
    def markdown_files(self) -> int:
        return sum(count for _zone, count in self.markdown_by_zone)

    @property
    def sections(self) -> int:
        return sum(count for _zone, count in self.sections_by_zone)


@dataclass(frozen=True)
class Extraction:
    """The index of one tree, the counts behind it, and the links whose targets do not resolve (sorted)."""

    index: Index
    summary: Summary
    problems: tuple[Link, ...] = ()


@dataclass(frozen=True)
class _Parsed:
    """One parsed Markdown file: its document, the index address that holds each line, slug to address, and its
    headings in document order."""

    document: Document
    holders: tuple[str, ...]
    anchors: dict[str, str]
    headings: tuple[ids.Heading, ...] = ()


def _section_nodes(path: str, text: str) -> tuple[list[SectionNode], list[Edge], _Parsed]:
    """The section nodes of one Markdown file, the ``contains`` edges from the file and between sections, and the
    parse that the links pass reads."""
    document = parse(path, text)
    # The parent chain is rebuilt from the levels, as the parser builds it, and not looked up by the parser's
    # address: a top heading with the empty slug has the file-level section's address there.
    stack: list[tuple[int, str]] = []  # (level, index address) of the open headings
    nodes: list[SectionNode] = []
    edges: list[Edge] = []
    holders = [path] * len(document.lines)  # the frontmatter and the text before the first heading: the file
    anchors: dict[str, str] = {}
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
        for number in range(section.start, section.end + 1):
            holders[number - 1] = address
        if section.slug:
            anchors[section.slug] = address
    headings = tuple(ids.Heading(path=path, address=node.address, level=node.level, title=node.title) for node in nodes)
    return nodes, edges, _Parsed(document=document, holders=tuple(holders), anchors=anchors, headings=headings)


def _counts(counter: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counter.items()))


def _id_edges(
    tree: Tree,
    config: Mapping[str, Any],
    parsed: Sequence[_Parsed],
    scanned: Sequence[str],
    definitions: ids.Definitions,
) -> list[Edge]:
    """The ``mentions`` and ``runs`` edges of the parsed Markdown files and of the ``scanned`` files."""
    kinds = ids.id_kinds(config)
    edges: list[Edge] = []
    for one in parsed:
        lines = zip(one.holders, (line.text for line in one.document.lines))
        edges.extend(ids.mention_edges(kinds, definitions, lines))
        edges.extend(ids.run_edges(kinds, definitions, one.document, one.holders))
    for path in scanned:
        text = tree.read(path)
        if text is not None:
            edges.extend(ids.mention_edges(kinds, definitions, ((path, line) for line in text.splitlines())))
    return edges


def _bundles(
    bundles: Mapping[str, Sequence[str]], indexed: Sequence[str], taken: set[str], config: Mapping[str, Any]
) -> tuple[list[Node], list[Edge], list[tuple[str, int]], list[str]]:
    """One node per bundle, its ``bundles`` edges, the member count of each bundle, and the problems."""
    nodes: list[Node] = []
    edges: list[Edge] = []
    counts: list[tuple[str, int]] = []
    problems: list[str] = []
    for address, entries in sorted(bundles.items()):
        if address in taken:
            problems.append(f"bundle {address}: the address is taken by another node; the bundle is left out")
            continue
        try:
            node = FileNode(path=address, kind=file_kind(address, config), zone=zone_of(address, config))
        except ValueError as exc:
            problems.append(f"bundle {address}: {exc}")
            continue
        members, empty = ids.bundle_members(entries, indexed)
        nodes.append(node)
        taken.add(address)
        edges.extend(Edge(kind="bundles", source=address, target=path) for path in members)
        counts.append((address, len(members)))
        problems.extend(f"bundle {address}: the entry {entry} names no indexed file" for entry in empty)
    return nodes, edges, counts, problems


def extract(tree: Tree, config: Mapping[str, Any], bundles: Mapping[str, Sequence[str]] | None = None) -> Extraction:
    """Build the index of ``tree`` with the project ``config``: file, section and ``id`` nodes, one node per bundle,
    and the ``contains``, ``links``, ``mentions``, ``runs`` and ``bundles`` edges.

    ``bundles`` maps each bundle's address to its entries (:func:`docindex.ids.bundle_members`); when it is
    ``None``, the config's :data:`BUNDLE_FILES` key holds them, if the entry point filled it.
    """
    exclude: Mapping[str, Iterable[str]] = config.get("exclude", {})
    skip = list(exclude.get("skip", []))
    list_only = list(exclude.get("list_only", []))
    nodes: list[Node] = []
    edges: list[Edge] = []
    unindexed: list[str] = []
    markdown_by_zone: dict[str, int] = {}
    sections_by_zone: dict[str, int] = {}
    parsed: list[_Parsed] = []
    scanned: list[str] = []
    listed_only = 0
    tracked = tree.files()
    for path in tracked:
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
        if kind in MENTION_KINDS:
            scanned.append(path)
        if kind != "markdown":
            continue
        text = tree.read(path)
        if text is None:
            continue
        sections, contains, one = _section_nodes(path, text)
        nodes.extend(sections)
        edges.extend(contains)
        parsed.append(one)
        markdown_by_zone[zone] = markdown_by_zone.get(zone, 0) + 1
        sections_by_zone[zone] = sections_by_zone.get(zone, 0) + len(sections)
    context = LinkContext.build(
        files=tracked,
        anchors={one.document.path: one.anchors for one in parsed},
        indexed=[node.path for node in nodes if isinstance(node, FileNode)],
    )
    problems: list[Link] = []
    seen = set(edges)
    for one in parsed:
        found = link_edges(one.document, one.holders, context)
        for edge in found.edges:
            if edge not in seen:
                seen.add(edge)
                edges.append(edge)
        problems.extend(found.problems)
    problems.sort(key=lambda link: (link.source, link.target, link.problem))
    indexed = [node.path for node in nodes if isinstance(node, FileNode)]
    taken = {node.address for node in nodes}
    definitions = ids.define(
        config,
        files=indexed,
        read=tree.read,
        headings=[heading for one in parsed for heading in one.headings],
        taken=taken,
    )
    nodes.extend(definitions.nodes)
    taken.update(node.address for node in definitions.nodes)
    for edge in _id_edges(tree, config, parsed, scanned, definitions):
        if edge not in seen:
            seen.add(edge)
            edges.append(edge)
    bundle_nodes, bundle_edges, bundle_counts, bundle_problems = _bundles(
        bundles if bundles is not None else config.get(BUNDLE_FILES, {}), indexed, taken, config
    )
    nodes.extend(bundle_nodes)
    edges.extend(bundle_edges)
    ids_by_kind: dict[str, int] = {}
    for id_node in definitions.nodes:
        ids_by_kind[id_node.kind] = ids_by_kind.get(id_node.kind, 0) + 1
    summary = Summary(
        files=len(indexed),
        listed_only=listed_only,
        markdown_by_zone=_counts(markdown_by_zone),
        sections_by_zone=_counts(sections_by_zone),
        unindexed=tuple(sorted(unindexed)),
        broken_links=tuple(link.describe() for link in problems),
        ids_by_kind=_counts(ids_by_kind),
        bundles=tuple(bundle_counts),
        id_problems=tuple(sorted([*definitions.problems, *bundle_problems])),
        config_problems=tuple(unmatched(config, tracked)),
    )
    index = Index(nodes=tuple(nodes), edges=tuple(edges))
    return Extraction(index=index, summary=summary, problems=tuple(problems))


def summary_text(summary: Summary, prog: str = "build") -> str:
    """The stderr summary: the totals, then the parsed Markdown files and their sections per zone."""
    sections = dict(summary.sections_by_zone)
    lines = [
        f"{prog}: {summary.files} files, {summary.markdown_files} Markdown files parsed, "
        f"{summary.sections} sections, {summary.listed_only} files listed and not parsed",
    ]
    for zone, count in summary.markdown_by_zone:
        lines.append(f"  {zone}: {count} Markdown files, {sections.get(zone, 0)} sections")
    if summary.ids_by_kind:
        lines.append("  ids: " + ", ".join(f"{kind} {count}" for kind, count in summary.ids_by_kind))
    for bundle, count in summary.bundles:
        lines.append(f"  bundle {bundle}: {count} files")
    for problem in summary.id_problems:
        lines.append(f"  id or bundle problem: {problem}")
    for problem in summary.config_problems:
        lines.append(f"  config problem (the entry has no effect): {problem}")
    for path in summary.unindexed:
        lines.append(f"  not indexed (a node cannot hold the path): {path}")
    for link in summary.broken_links:
        lines.append(f"  broken link (kept in the index): {link}")
    return "\n".join(lines) + "\n"
