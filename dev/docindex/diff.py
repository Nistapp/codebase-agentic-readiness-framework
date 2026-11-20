# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The index diff: what a change moved, renamed, edited or lost in the document index.

:func:`compare` takes the index of the old state and of the new state (each built by :func:`docindex.extract.extract`
from a :class:`~docindex.gitread.Tree`, so the old side is read with ``git show``, never a checkout) and sorts the
differences into these groups:

- **sections added** and **removed**: a section address on one side only that no rule below pairs;
- **moved**: a removed and an added section with the same ``own_hash`` (the heading line and the section's own text,
  so a move keeps the level and the title). When several added sections have that hash, the one in the same file
  wins, then the first by address;
- **renamed**: a removed and an added section at the same place in the tree (the same parent, after the moves and
  renames of its ancestors, and the same level) whose own text less the heading is the same, under a new title.
  ``own_hash`` covers the heading line, so the rule compares the *body hash*: the SHA-256 of the section's own lines
  without its heading lines, normalised as :func:`docindex.markdown.normalise` does (:func:`body_hashes`);
- **edited**: a section at the same address on both sides with a new ``own_hash``. A section whose address changed
  only because an ancestor moved or was renamed is the same section: it is reported once, as edited, when its
  ``own_hash`` changed, and else not at all;
- **edges lost** and **gained**: the ``links``, ``mentions``, ``runs`` and ``bundles`` edges (``contains`` edges are
  the tree itself, which the section groups describe), with their anchors and confidence. The ends of each old edge
  are first mapped through the moves and renames, so an edge that only followed its section is no change;
- **IDs that lost their definition**: an ``id`` node of the old side that the new side does not define. Its old
  ``mentions`` and ``runs`` edges are listed with it and not again among the edges lost, since the mentioning text
  may be unchanged: only the definition went;
- **IDs that lost every mention**: an ``id`` node on both sides that the old side mentions and the new side does
  not. Its lost ``mentions`` edges are among the edges lost too.

Files are not compared as nodes: a file's change shows in its sections and its edges.

The removed sections are paired parents first (by the depth of the address, then by address), so a child sees the
pairing of its parent. Every list of a :class:`IndexDiff` is sorted. :func:`to_text` groups the report by kind of
change; :func:`to_json` writes deterministic JSON (sorted keys, no timestamps, no line numbers). This module imports
nothing outside the standard library and this package.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from . import extract
from .gitread import Tree
from .markdown import normalise
from .model import Edge, IdNode, Index, SectionNode, content_hash

__all__ = [
    "DIFF_FORMAT",
    "EDGE_KINDS",
    "BodyHashes",
    "Edited",
    "IdLost",
    "IndexDiff",
    "Moved",
    "Renamed",
    "body_hashes",
    "compare",
    "to_json",
    "to_text",
]

#: The version of the JSON form of the report.
DIFF_FORMAT = 1

#: The edge kinds the diff compares.
EDGE_KINDS = ("links", "mentions", "runs", "bundles")

#: The edge kinds that follow an ID's definition: they go with it when the definition goes.
_ID_EDGE_KINDS = ("mentions", "runs")

#: A reader of body hashes: a file path to the body hash of each of its sections, keyed by the section's address.
BodyHashes = Callable[[str], Mapping[str, str]]


@dataclass(frozen=True)
class Moved:
    """A section that kept its ``own_hash`` at a new address."""

    old: str
    new: str
    title: str


@dataclass(frozen=True)
class Renamed:
    """A section that kept its place and its body under a new title."""

    old: str
    new: str
    old_title: str
    new_title: str


@dataclass(frozen=True)
class Edited:
    """A section with a new ``own_hash``. ``old_address`` differs from ``address`` when an ancestor moved."""

    address: str
    old_address: str


@dataclass(frozen=True)
class IdLost:
    """An ID that lost its definition or its last mention. ``edges`` are the old edges to it that went."""

    id: str
    kind: str
    defined_by: str
    edges: tuple[Edge, ...]


@dataclass(frozen=True)
class IndexDiff:
    """The differences between two indexes. Each tuple is sorted."""

    added: tuple[SectionNode, ...] = ()
    removed: tuple[SectionNode, ...] = ()
    moved: tuple[Moved, ...] = ()
    renamed: tuple[Renamed, ...] = ()
    edited: tuple[Edited, ...] = ()
    edges_lost: tuple[Edge, ...] = ()
    edges_gained: tuple[Edge, ...] = ()
    ids_undefined: tuple[IdLost, ...] = ()
    ids_unmentioned: tuple[IdLost, ...] = ()

    def counts(self) -> dict[str, int]:
        """The size of each group, keyed as in the JSON form."""
        return {
            "edges_gained": len(self.edges_gained),
            "edges_lost": len(self.edges_lost),
            "ids_lost_definition": len(self.ids_undefined),
            "ids_lost_mentions": len(self.ids_unmentioned),
            "sections_added": len(self.added),
            "sections_edited": len(self.edited),
            "sections_moved": len(self.moved),
            "sections_removed": len(self.removed),
            "sections_renamed": len(self.renamed),
        }

    @property
    def changes(self) -> int:
        """The number of reported changes, all groups together."""
        return sum(self.counts().values())


# --- Body hashes ----------------------------------------------------------------------------------------------------


def body_hashes(tree: Tree) -> BodyHashes:
    """The body-hash reader of ``tree``: each Markdown file is parsed once, on first use.

    A section's body hash is the hash of its own lines without its heading lines. The addresses are the index's, as
    :mod:`docindex.extract` writes them. A file that does not exist gives no hashes.
    """
    cache: dict[str, dict[str, str]] = {}

    def read(path: str) -> Mapping[str, str]:
        if path not in cache:
            text = tree.read(path)
            hashes: dict[str, str] = {}
            if text is not None:
                nodes, _edges, parsed = extract._section_nodes(path, text)
                sections = [section for section in parsed.document.sections if section.parent is not None]
                for node, section in zip(nodes, sections):
                    own = parsed.document.lines[section.start - 1 : section.end]
                    hashes[node.address] = content_hash(normalise([line for line in own if not line.heading]))
            cache[path] = hashes
        return cache[path]

    return read


# --- Comparing ------------------------------------------------------------------------------------------------------


def _parent(address: str) -> str:
    """The address of a section's parent: the enclosing section, or the file for a top section."""
    path, _sep, chain = address.partition("#")
    if "/" not in chain:
        return path
    return f"{path}#{chain.rsplit('/', 1)[0]}"


def _segment(address: str) -> str:
    return address.partition("#")[2].rsplit("/", 1)[-1]


def _child(parent: str, segment: str) -> str:
    return f"{parent}/{segment}" if "#" in parent else f"{parent}#{segment}"


def _depth(address: str) -> int:
    return address.partition("#")[2].count("/")


def _sections(index: Index) -> dict[str, SectionNode]:
    return {node.address: node for node in index.nodes if isinstance(node, SectionNode)}


def _ids(index: Index) -> dict[str, IdNode]:
    return {node.address: node for node in index.nodes if isinstance(node, IdNode)}


def _edge_key(edge: Edge) -> tuple[str, str, str, str, str, str]:
    return (edge.kind, edge.source, edge.target, edge.anchor or "", edge.confidence, edge.broken or "")


def _remap(edge: Edge, mapping: Mapping[str, str]) -> Edge:
    return Edge(
        kind=edge.kind,
        source=mapping.get(edge.source, edge.source),
        target=mapping.get(edge.target, edge.target),
        confidence=edge.confidence,
        anchor=edge.anchor,
        broken=edge.broken,
    )


@dataclass
class _Pairing:
    """The pairing of the removed sections with the added ones."""

    mapping: dict[str, str]
    moved: list[Moved]
    renamed: list[Renamed]
    edited: list[Edited]
    removed: list[SectionNode]
    added: dict[str, SectionNode]


def _pair(
    old: Mapping[str, SectionNode],
    new: Mapping[str, SectionNode],
    old_body: BodyHashes,
    new_body: BodyHashes,
) -> _Pairing:
    added = {address: node for address, node in new.items() if address not in old}
    result = _Pairing(mapping={}, moved=[], renamed=[], edited=[], removed=[], added=added)
    for address in sorted((a for a in old if a not in new), key=lambda a: (_depth(a), a)):
        node = old[address]
        parent = _parent(address)
        mapped_parent = result.mapping.get(parent, parent)
        implied = _child(mapped_parent, _segment(address)) if mapped_parent != parent else None
        if implied is not None and implied in added:
            result.mapping[address] = implied
            if added.pop(implied).own_hash != node.own_hash:
                result.edited.append(Edited(address=implied, old_address=address))
            continue
        same_hash = sorted(
            (a for a, candidate in added.items() if candidate.own_hash == node.own_hash),
            key=lambda a: (a.partition("#")[0] != node.path, a),
        )
        if same_hash:
            target = same_hash[0]
            del added[target]
            result.mapping[address] = target
            result.moved.append(Moved(old=address, new=target, title=node.title))
            continue
        body = old_body(node.path).get(address)
        renamed = sorted(
            a
            for a, candidate in added.items()
            if _parent(a) == mapped_parent
            and candidate.level == node.level
            and candidate.title != node.title
            and body is not None
            and new_body(candidate.path).get(a) == body
        )
        if renamed:
            target = renamed[0]
            result.mapping[address] = target
            result.renamed.append(
                Renamed(old=address, new=target, old_title=node.title, new_title=added.pop(target).title)
            )
            continue
        result.removed.append(node)
    return result


def compare(old: Index, new: Index, *, old_body: BodyHashes, new_body: BodyHashes) -> IndexDiff:
    """The differences from the ``old`` index to the ``new`` one; ``old_body`` and ``new_body`` give the body
    hashes of each side's sections (:func:`body_hashes`)."""
    old_sections, new_sections = _sections(old), _sections(new)
    pairing = _pair(old_sections, new_sections, old_body, new_body)
    edited = list(pairing.edited)
    for address in sorted(set(old_sections) & set(new_sections)):
        if old_sections[address].own_hash != new_sections[address].own_hash:
            edited.append(Edited(address=address, old_address=address))
    old_ids, new_ids = _ids(old), _ids(new)
    undefined = {address for address in old_ids if address not in new_ids}
    old_edges = {_remap(edge, pairing.mapping) for edge in old.edges if edge.kind in EDGE_KINDS}
    new_edges = {edge for edge in new.edges if edge.kind in EDGE_KINDS}
    with_definition: dict[str, list[Edge]] = {}
    lost: list[Edge] = []
    for edge in old_edges - new_edges:
        if edge.target in undefined and edge.kind in _ID_EDGE_KINDS:
            with_definition.setdefault(edge.target, []).append(edge)
        else:
            lost.append(edge)
    ids_undefined = [
        IdLost(
            id=address,
            kind=old_ids[address].kind,
            defined_by=old_ids[address].defined_by,
            edges=tuple(sorted(with_definition.get(address, []), key=_edge_key)),
        )
        for address in sorted(undefined)
    ]
    old_mentions: dict[str, list[Edge]] = {}
    for edge in old_edges:
        if edge.kind == "mentions":
            old_mentions.setdefault(edge.target, []).append(edge)
    new_mentioned = {edge.target for edge in new_edges if edge.kind == "mentions"}
    ids_unmentioned = [
        IdLost(
            id=address,
            kind=new_ids[address].kind,
            defined_by=new_ids[address].defined_by,
            edges=tuple(sorted(old_mentions[address], key=_edge_key)),
        )
        for address in sorted(new_ids)
        if address in old_ids and address in old_mentions and address not in new_mentioned
    ]
    return IndexDiff(
        added=tuple(sorted(pairing.added.values(), key=lambda node: node.address)),
        removed=tuple(sorted(pairing.removed, key=lambda node: node.address)),
        moved=tuple(sorted(pairing.moved, key=lambda entry: (entry.old, entry.new))),
        renamed=tuple(sorted(pairing.renamed, key=lambda entry: (entry.old, entry.new))),
        edited=tuple(sorted(edited, key=lambda entry: (entry.address, entry.old_address))),
        edges_lost=tuple(sorted(lost, key=_edge_key)),
        edges_gained=tuple(sorted(new_edges - old_edges, key=_edge_key)),
        ids_undefined=tuple(ids_undefined),
        ids_unmentioned=tuple(ids_unmentioned),
    )


# --- Output ---------------------------------------------------------------------------------------------------------


def _edge_dict(edge: Edge) -> dict[str, Any]:
    out = edge.to_dict()
    out.setdefault("anchor", None)
    return out


def _id_dict(entry: IdLost) -> dict[str, Any]:
    return {
        "defined_by": entry.defined_by,
        "edges": [_edge_dict(edge) for edge in entry.edges],
        "id": entry.id,
        "kind": entry.kind,
    }


def _section_dict(node: SectionNode) -> dict[str, Any]:
    return {"address": node.address, "level": node.level, "title": node.title}


def to_json(report: IndexDiff, *, old: str, new: str | None) -> str:
    """The report as deterministic JSON: sorted keys, two-space indent, a final newline.

    ``old`` is the old git ref; ``new`` the new one, ``None`` for the working tree. Every edge has an ``anchor`` key,
    ``null`` when the edge keeps none, and a ``broken`` key only when its target does not resolve.
    """
    data = {
        "counts": report.counts(),
        "edges": {
            "gained": [_edge_dict(edge) for edge in report.edges_gained],
            "lost": [_edge_dict(edge) for edge in report.edges_lost],
        },
        "format": DIFF_FORMAT,
        "ids": {
            "lost_definition": [_id_dict(entry) for entry in report.ids_undefined],
            "lost_mentions": [_id_dict(entry) for entry in report.ids_unmentioned],
        },
        "new": new,
        "old": old,
        "sections": {
            "added": [_section_dict(node) for node in report.added],
            "edited": [{"address": entry.address, "old_address": entry.old_address} for entry in report.edited],
            "moved": [{"new": entry.new, "old": entry.old, "title": entry.title} for entry in report.moved],
            "removed": [_section_dict(node) for node in report.removed],
            "renamed": [
                {"new": entry.new, "new_title": entry.new_title, "old": entry.old, "old_title": entry.old_title}
                for entry in report.renamed
            ],
        },
    }
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _edge_line(edge: Edge) -> str:
    anchor = f" (anchor #{edge.anchor})" if edge.anchor is not None else ""
    confidence = f" [{edge.confidence}]" if edge.confidence != "exact" else ""
    broken = f" [broken: {edge.broken}]" if edge.broken is not None else ""
    return f"{edge.kind}: {edge.source} -> {edge.target}{anchor}{confidence}{broken}"


def _group(title: str, count: int, lines: Sequence[str]) -> str:
    return f"# {title}: {count}\n" + "".join(f"  {line}\n" for line in lines)


def _quoted(title: str) -> str:
    return json.dumps(title, ensure_ascii=False)


def _id_lines(entries: Sequence[IdLost], what: str) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        lines.append(f"{entry.id} ({entry.kind}), defined by {entry.defined_by}")
        lines.extend(f"  {what}: {_edge_line(edge)}" for edge in entry.edges)
    return lines


def _edited_line(entry: Edited) -> str:
    if entry.address == entry.old_address:
        return entry.address
    return f"{entry.address} (was {entry.old_address})"


def to_text(report: IndexDiff, *, old: str, new: str | None) -> str:
    """The report as text: a heading line, then one group per kind of change, each sorted, empty groups included.

    Under an ID, the indented lines list its old edges that went; they are not counted in the group's size.
    """
    target = new if new is not None else "the working tree"
    rows: list[tuple[str, int, list[str]]] = [
        ("Sections added", len(report.added), [f"{node.address} {_quoted(node.title)}" for node in report.added]),
        ("Sections removed", len(report.removed), [f"{node.address} {_quoted(node.title)}" for node in report.removed]),
        ("Sections moved", len(report.moved), [f"{entry.old} -> {entry.new}" for entry in report.moved]),
        (
            "Sections renamed",
            len(report.renamed),
            [
                f"{entry.old} -> {entry.new} ({_quoted(entry.old_title)} -> {_quoted(entry.new_title)})"
                for entry in report.renamed
            ],
        ),
        ("Sections edited", len(report.edited), [_edited_line(entry) for entry in report.edited]),
        ("Edges lost", len(report.edges_lost), [_edge_line(edge) for edge in report.edges_lost]),
        ("Edges gained", len(report.edges_gained), [_edge_line(edge) for edge in report.edges_gained]),
        (
            "IDs that lost their definition",
            len(report.ids_undefined),
            _id_lines(report.ids_undefined, "lost with it"),
        ),
        ("IDs that lost every mention", len(report.ids_unmentioned), _id_lines(report.ids_unmentioned, "was")),
    ]
    head = f"# Index diff from {old} to {target}: {report.changes} changes\n"
    return "\n".join([head, *(_group(title, count, lines) for title, count, lines in rows)])
