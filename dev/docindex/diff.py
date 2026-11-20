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

Three rules then take the bulk out of the section and edge groups, so that a reviewer reads the changes a person
made:

- **edges whose confidence changed**: an edge lost and gained with the same kind, ends, anchor and ``broken`` flag
  but another confidence (an ID mention that turned ``exact`` or ``name-match``). It is one change, not two;
- **name-match links that changed resolution**: a ``links`` edge with confidence ``name-match`` and no anchor (a
  bare file name in prose) to a file node, lost or gained only because the name now selects another file or none.
  That holds when the number of file nodes with the target's base name differs between the two sides, or the target
  file exists on one side only, *and* the text that holds the name did not change: the source is a section that is
  not added, removed, renamed or edited (a file-level source, the text before the first heading, has no hash of its
  own, so the count rule alone decides). These edges are grouped by base name (:class:`NameResolution`). A
  name-match link lost from edited text, or with the same count on both sides, stays among the edges lost;
- **files regenerated**: a file that ``generated`` names (the config's ``generated`` key: a path or folder prefix,
  as in ``zones``, and the command that writes it). Its sections leave the added, removed, moved, renamed and
  edited groups, and the edges whose *source* lies in it leave the lost and gained groups; a :class:`Regenerated`
  counts them, one per file. Edges *into* a generated file stay listed: a link elsewhere that lost its anchor in a
  generated page is a real break. A move or rename stays listed unless both of its ends lie in generated files.

Files are not compared as nodes: a file's change shows in its sections and its edges.

The removed sections are paired parents first (by the depth of the address, then by address), so a child sees the
pairing of its parent. Every list of a :class:`IndexDiff` is sorted. :func:`to_text` groups the report by kind of
change; :func:`to_json` writes deterministic JSON (sorted keys, no timestamps, no line numbers). This module imports
nothing outside the standard library and this package.
"""

from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass
from typing import Any, Callable, Collection, Mapping, Sequence

from . import extract
from .gitread import Tree
from .markdown import normalise
from .model import Edge, FileNode, IdNode, Index, SectionNode, content_hash

__all__ = [
    "DIFF_FORMAT",
    "EDGE_KINDS",
    "BodyHashes",
    "ConfidenceChanged",
    "Edited",
    "IdLost",
    "IndexDiff",
    "Moved",
    "NameResolution",
    "Regenerated",
    "Renamed",
    "body_hashes",
    "compare",
    "to_json",
    "to_text",
]

#: The version of the JSON form of the report. Format 2 added ``regenerated``, ``name_resolution`` and
#: ``edges.confidence_changed``, and their counts.
DIFF_FORMAT = 2

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
class ConfidenceChanged:
    """One edge, lost with the ``old`` confidence and gained with the ``new`` one."""

    old: Edge
    new: Edge


@dataclass(frozen=True)
class NameResolution:
    """The name-match links of one bare file name that changed only because the name selects another file.

    ``files_before`` and ``files_after`` count the file nodes with that base name on each side.
    """

    name: str
    files_before: int
    files_after: int
    lost: tuple[Edge, ...] = ()
    gained: tuple[Edge, ...] = ()


@dataclass(frozen=True)
class Regenerated:
    """A generated file's changes, as counts: its sections and the edges whose source lies in it."""

    path: str
    by: str
    sections_added: int = 0
    sections_removed: int = 0
    sections_moved: int = 0
    sections_edited: int = 0
    edges_lost: int = 0
    edges_gained: int = 0


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
    confidence_changed: tuple[ConfidenceChanged, ...] = ()
    name_resolution: tuple[NameResolution, ...] = ()
    regenerated: tuple[Regenerated, ...] = ()

    def counts(self) -> dict[str, int]:
        """The size of each group, keyed as in the JSON form. A name-resolution change counts each of its edges; a
        regenerated file counts once."""
        return {
            "edges_confidence_changed": len(self.confidence_changed),
            "edges_gained": len(self.edges_gained),
            "edges_lost": len(self.edges_lost),
            "files_regenerated": len(self.regenerated),
            "ids_lost_definition": len(self.ids_undefined),
            "ids_lost_mentions": len(self.ids_unmentioned),
            "name_match_resolution": sum(len(entry.lost) + len(entry.gained) for entry in self.name_resolution),
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


def _path(address: str) -> str:
    return address.partition("#")[0]


def _under(path: str, prefix: str) -> bool:
    prefix = prefix.rstrip("/")
    return path == prefix or path.startswith(prefix + "/")


def _generator(generated: Mapping[str, str]) -> Callable[[str], str | None]:
    """A function from an address to the command that writes its file (the longest matching ``generated`` path
    or folder prefix), or ``None``."""

    def by(address: str) -> str | None:
        path = _path(address)
        matches = [prefix for prefix in generated if _under(path, prefix)]
        if not matches:
            return None
        return generated[max(matches, key=lambda prefix: (len(prefix.rstrip("/")), prefix))]

    return by


def _file_names(index: Index) -> tuple[frozenset[str], dict[str, int]]:
    """The file node paths of ``index``, and the number of file nodes per base name."""
    paths = frozenset(node.path for node in index.nodes if isinstance(node, FileNode))
    names: dict[str, int] = {}
    for path in paths:
        name = posixpath.basename(path)
        names[name] = names.get(name, 0) + 1
    return paths, names


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


def compare(
    old: Index,
    new: Index,
    *,
    old_body: BodyHashes,
    new_body: BodyHashes,
    generated: Mapping[str, str] | None = None,
) -> IndexDiff:
    """The differences from the ``old`` index to the ``new`` one; ``old_body`` and ``new_body`` give the body
    hashes of each side's sections (:func:`body_hashes`). ``generated`` maps a path or folder prefix to the command
    that writes the files under it (the config's ``generated`` key); none by default."""
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
    changed_text = {
        *pairing.added,
        *(node.address for node in pairing.removed),
        *(entry.old for entry in pairing.renamed),
        *(entry.new for entry in pairing.renamed),
        *(entry.address for entry in edited),
        *(entry.old_address for entry in edited),
    }
    by = _generator(generated or {})
    regenerated: dict[str, dict[str, int]] = {}

    def collapse(address: str, group: str) -> bool:
        if by(address) is None:
            return False
        counts = regenerated.setdefault(_path(address), {})
        counts[group] = counts.get(group, 0) + 1
        return True

    def collapse_pair(old_address: str, new_address: str) -> bool:
        return by(old_address) is not None and collapse(new_address, "sections_moved")

    added = [node for node in pairing.added.values() if not collapse(node.address, "sections_added")]
    removed = [node for node in pairing.removed if not collapse(node.address, "sections_removed")]
    moved = [entry for entry in pairing.moved if not collapse_pair(entry.old, entry.new)]
    renamed = [entry for entry in pairing.renamed if not collapse_pair(entry.old, entry.new)]
    edited = [entry for entry in edited if not collapse(entry.address, "sections_edited")]
    lost = [edge for edge in lost if not collapse(edge.source, "edges_lost")]
    gained = [edge for edge in new_edges - old_edges if not collapse(edge.source, "edges_gained")]
    confidence_changed, lost, gained = _confidence_changes(lost, gained)
    name_resolution, lost, gained = _name_resolution(old, new, lost, gained, changed_text)
    return IndexDiff(
        added=tuple(sorted(added, key=lambda node: node.address)),
        removed=tuple(sorted(removed, key=lambda node: node.address)),
        moved=tuple(sorted(moved, key=lambda entry: (entry.old, entry.new))),
        renamed=tuple(sorted(renamed, key=lambda entry: (entry.old, entry.new))),
        edited=tuple(sorted(edited, key=lambda entry: (entry.address, entry.old_address))),
        edges_lost=tuple(sorted(lost, key=_edge_key)),
        edges_gained=tuple(sorted(gained, key=_edge_key)),
        ids_undefined=tuple(ids_undefined),
        ids_unmentioned=tuple(ids_unmentioned),
        confidence_changed=tuple(confidence_changed),
        name_resolution=tuple(name_resolution),
        regenerated=tuple(
            Regenerated(path=path, by=by(path) or "", **counts) for path, counts in sorted(regenerated.items())
        ),
    )


def _same_but_confidence(edge: Edge) -> tuple[str, str, str, str, str]:
    return (edge.kind, edge.source, edge.target, edge.anchor or "", edge.broken or "")


def _confidence_changes(
    lost: Sequence[Edge], gained: Sequence[Edge]
) -> tuple[list[ConfidenceChanged], list[Edge], list[Edge]]:
    """Pair each lost edge with the gained edge that differs from it in confidence only."""
    gained_by_key = {_same_but_confidence(edge): edge for edge in gained}
    pairs: list[ConfidenceChanged] = []
    paired: set[Edge] = set()
    for edge in sorted(lost, key=_edge_key):
        other = gained_by_key.get(_same_but_confidence(edge))
        if other is not None and other.confidence != edge.confidence:
            pairs.append(ConfidenceChanged(old=edge, new=other))
            paired.update((edge, other))
    return pairs, [edge for edge in lost if edge not in paired], [edge for edge in gained if edge not in paired]


def _name_resolution(
    old: Index, new: Index, lost: Sequence[Edge], gained: Sequence[Edge], changed_text: Collection[str]
) -> tuple[list[NameResolution], list[Edge], list[Edge]]:
    """Take out the bare-name links that changed only because their name selects another file or none."""
    old_files, old_names = _file_names(old)
    new_files, new_names = _file_names(new)

    def resolution(edge: Edge, here: frozenset[str], there: frozenset[str]) -> str | None:
        if edge.kind != "links" or edge.confidence != "name-match" or edge.anchor is not None:
            return None
        if edge.target not in here or edge.source in changed_text:
            return None
        name = posixpath.basename(edge.target)
        if old_names.get(name, 0) == new_names.get(name, 0) and edge.target in there:
            return None
        return name

    groups: dict[str, tuple[list[Edge], list[Edge]]] = {}
    kept: tuple[list[Edge], list[Edge]] = ([], [])
    for side, edges, here, there in ((0, lost, old_files, new_files), (1, gained, new_files, old_files)):
        for edge in edges:
            name = resolution(edge, here, there)
            if name is None:
                kept[side].append(edge)
            else:
                groups.setdefault(name, ([], []))[side].append(edge)
    entries = [
        NameResolution(
            name=name,
            files_before=old_names.get(name, 0),
            files_after=new_names.get(name, 0),
            lost=tuple(sorted(group[0], key=_edge_key)),
            gained=tuple(sorted(group[1], key=_edge_key)),
        )
        for name, group in sorted(groups.items())
    ]
    return entries, kept[0], kept[1]


# --- Output ---------------------------------------------------------------------------------------------------------


def _edge_dict(edge: Edge) -> dict[str, Any]:
    out = edge.to_dict()
    out.setdefault("anchor", None)
    return out


def _regenerated_dict(entry: Regenerated) -> dict[str, Any]:
    return {
        "by": entry.by,
        "edges_gained": entry.edges_gained,
        "edges_lost": entry.edges_lost,
        "path": entry.path,
        "sections_added": entry.sections_added,
        "sections_edited": entry.sections_edited,
        "sections_moved": entry.sections_moved,
        "sections_removed": entry.sections_removed,
    }


def _resolution_dict(entry: NameResolution) -> dict[str, Any]:
    return {
        "files_after": entry.files_after,
        "files_before": entry.files_before,
        "gained": [_edge_dict(edge) for edge in entry.gained],
        "lost": [_edge_dict(edge) for edge in entry.lost],
        "name": entry.name,
    }


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
    ``null`` when the edge keeps none, and a ``broken`` key only when its target does not resolve. The JSON form
    always lists every edge of a name-resolution change; ``--detail`` changes the text form only.
    """
    data = {
        "counts": report.counts(),
        "edges": {
            "confidence_changed": [
                {"new": _edge_dict(entry.new), "old": _edge_dict(entry.old)} for entry in report.confidence_changed
            ],
            "gained": [_edge_dict(edge) for edge in report.edges_gained],
            "lost": [_edge_dict(edge) for edge in report.edges_lost],
        },
        "format": DIFF_FORMAT,
        "ids": {
            "lost_definition": [_id_dict(entry) for entry in report.ids_undefined],
            "lost_mentions": [_id_dict(entry) for entry in report.ids_unmentioned],
        },
        "name_resolution": [_resolution_dict(entry) for entry in report.name_resolution],
        "new": new,
        "old": old,
        "regenerated": [_regenerated_dict(entry) for entry in report.regenerated],
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


def _edge_line(edge: Edge, *, confidence: bool = True) -> str:
    anchor = f" (anchor #{edge.anchor})" if edge.anchor is not None else ""
    flag = f" [{edge.confidence}]" if confidence and edge.confidence != "exact" else ""
    broken = f" [broken: {edge.broken}]" if edge.broken is not None else ""
    return f"{edge.kind}: {edge.source} -> {edge.target}{anchor}{flag}{broken}"


def _confidence_line(entry: ConfidenceChanged) -> str:
    return f"{_edge_line(entry.new, confidence=False)}: {entry.old.confidence} -> {entry.new.confidence}"


def _resolution_lines(entries: Sequence[NameResolution], detail: bool) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        files = f"{entry.files_before} -> {entry.files_after} files"
        lines.append(f"{entry.name}: {files}; {len(entry.lost)} lost, {len(entry.gained)} gained")
        if detail:
            lines.extend(f"  lost: {_edge_line(edge)}" for edge in entry.lost)
            lines.extend(f"  gained: {_edge_line(edge)}" for edge in entry.gained)
    return lines


def _resolution_count(entries: Sequence[NameResolution]) -> str:
    """The group's edge count, then the count per name, largest first: ``57 (40 build.gradle, 11 uv.lock)``."""
    sizes = sorted(((len(e.lost) + len(e.gained), e.name) for e in entries), key=lambda item: (-item[0], item[1]))
    total = sum(size for size, _name in sizes)
    return f"{total} ({', '.join(f'{size} {name}' for size, name in sizes)})" if sizes else "0"


def _regenerated_line(entry: Regenerated) -> str:
    sections = (
        f"{entry.sections_edited} sections edited, {entry.sections_added} added, {entry.sections_removed} removed, "
        f"{entry.sections_moved} moved or renamed"
    )
    return f"{entry.path} (by {entry.by}): {sections}; {entry.edges_lost} edges lost, {entry.edges_gained} gained"


def _group(title: str, count: int | str, lines: Sequence[str]) -> str:
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


def to_text(report: IndexDiff, *, old: str, new: str | None, detail: bool = False) -> str:
    """The report as text: a heading line, then one group per kind of change, each sorted, empty groups included.

    Under an ID, the indented lines list its old edges that went; they are not counted in the group's size. The
    name-resolution group has one line per base name, and its heading names the edge count per name; with
    ``detail``, each name's edges follow it. A regenerated file is one line of counts.
    """
    target = new if new is not None else "the working tree"
    rows: list[tuple[str, int | str, list[str]]] = [
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
        (
            "Edges whose confidence changed",
            len(report.confidence_changed),
            [_confidence_line(entry) for entry in report.confidence_changed],
        ),
        (
            "Name-match links that changed resolution",
            _resolution_count(report.name_resolution),
            _resolution_lines(report.name_resolution, detail),
        ),
        ("Files regenerated", len(report.regenerated), [_regenerated_line(entry) for entry in report.regenerated]),
    ]
    head = f"# Index diff from {old} to {target}: {report.changes} changes\n"
    return "\n".join([head, *(_group(title, count, lines) for title, count, lines in rows)])
