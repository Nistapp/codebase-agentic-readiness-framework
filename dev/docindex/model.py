# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The document index's data model: frozen nodes and edges, and their one deterministic JSON form.

An index is a graph over a repository's documents. It has three kinds of node:

- a **file** node, addressed by its repository path (POSIX, relative), with a file ``kind`` and a ``zone``;
- a **section** node, addressed ``<path>#<slug>/<slug>/...``: the file path and the chain of GitHub-style heading
  slugs from the top heading down. It holds the heading ``title`` and ``level`` and two hashes: ``own_hash`` over
  the section's own text without its child sections, and ``tree_hash`` over the section with its children;
- an **id** node, addressed by the ID itself (a check ID such as ``CMD-01``, a requirement ID such as
  ``REQ-SH-060``), with an ID ``kind``, a ``title`` and the address of the node that defines it (``defined_by``).

An edge joins two addresses. Its ``kind`` is ``contains``, ``links`` (which keeps the link's ``anchor``),
``mentions``, ``runs`` or ``bundles``, and its ``confidence`` is ``exact`` or ``name-match``. ``name-match`` marks
a weaker edge: one found by a name (a bare file name in prose, an ID defined in several places with no one
nearest), or a link to a folder, whose address has no node because the index has no folder nodes.

:func:`to_json` writes the one serialised form: sorted keys, sorted node and edge lists, no timestamps, no absolute
paths and no line numbers, so two builds of the same tree are byte-identical. ``index.schema.json`` beside this
module is its JSON Schema. This module imports nothing outside the standard library.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Union

#: The version of the serialised form. A change to the form replaces it; no reader keeps an older one.
INDEX_FORMAT = 1

FILE_KINDS = ("markdown", "python", "json", "yaml", "other")
ZONES = ("recipe", "docs", "spec", "engine", "tools", "dev", "fixture")
ID_KINDS = ("check", "requirement", "playbook", "adr", "tool", "schema")
EDGE_KINDS = ("contains", "links", "mentions", "runs", "bundles")
CONFIDENCES = ("exact", "name-match")

#: The values of a serialised node's ``node`` key, in the order nodes with the same address sort.
NODE_TYPES = ("file", "section", "id")

_HEX = frozenset("0123456789abcdef")


def content_hash(text: str) -> str:
    """The SHA-256 of ``text`` (UTF-8) as 64 lowercase hex digits. The caller normalises the text first."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_choice(value: str, choices: tuple[str, ...], what: str) -> None:
    if value not in choices:
        raise ValueError(f"{what} {value!r} is not one of {', '.join(choices)}")


def _check_repo_path(path: str) -> None:
    """A repository path: relative, POSIX, with no empty, ``.`` or ``..`` part."""
    if not path or path.startswith("/") or "\\" in path or "#" in path or (len(path) > 1 and path[1] == ":"):
        raise ValueError(f"{path!r} is not a relative POSIX repository path")
    if any(part in ("", ".", "..") for part in path.split("/")):
        raise ValueError(f"{path!r} is not a normalised repository path")


def _check_hash(value: str, what: str) -> None:
    if len(value) != 64 or not set(value) <= _HEX:
        raise ValueError(f"{what} {value!r} is not 64 lowercase hex digits")


@dataclass(frozen=True)
class FileNode:
    """A file of the repository. Its address is its repository path."""

    path: str
    kind: str
    zone: str

    def __post_init__(self) -> None:
        _check_repo_path(self.path)
        _check_choice(self.kind, FILE_KINDS, "file kind")
        _check_choice(self.zone, ZONES, "zone")

    @property
    def address(self) -> str:
        return self.path

    def to_dict(self) -> dict[str, Any]:
        return {"address": self.path, "kind": self.kind, "node": "file", "zone": self.zone}


@dataclass(frozen=True)
class SectionNode:
    """A heading's section of a file. Its address is ``<path>#<slug>/<slug>/...``."""

    address: str
    title: str
    level: int
    own_hash: str
    tree_hash: str

    def __post_init__(self) -> None:
        path, sep, chain = self.address.partition("#")
        _check_repo_path(path)
        if not sep or not chain or any(not slug for slug in chain.split("/")):
            raise ValueError(f"section address {self.address!r} is not '<path>#<slug>[/<slug>...]'")
        if not 1 <= self.level <= 6:
            raise ValueError(f"section level {self.level} is not 1 to 6")
        _check_hash(self.own_hash, "own_hash")
        _check_hash(self.tree_hash, "tree_hash")

    @property
    def path(self) -> str:
        """The repository path of the file that holds the section."""
        return self.address.partition("#")[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "level": self.level,
            "node": "section",
            "own_hash": self.own_hash,
            "title": self.title,
            "tree_hash": self.tree_hash,
        }


@dataclass(frozen=True)
class IdNode:
    """A named ID. Its address is the ID; ``defined_by`` is the address of the node that defines it."""

    address: str
    kind: str
    title: str
    defined_by: str

    def __post_init__(self) -> None:
        if not self.address or self.address != self.address.strip():
            raise ValueError(f"ID {self.address!r} is empty or has surrounding whitespace")
        _check_choice(self.kind, ID_KINDS, "ID kind")
        if not self.defined_by:
            raise ValueError(f"ID {self.address!r} has no defining node")

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "defined_by": self.defined_by,
            "kind": self.kind,
            "node": "id",
            "title": self.title,
        }


Node = Union[FileNode, SectionNode, IdNode]


@dataclass(frozen=True)
class Edge:
    """A directed edge between two node addresses. Only a ``links`` edge may keep an ``anchor``."""

    kind: str
    source: str
    target: str
    confidence: str = "exact"
    anchor: str | None = None

    def __post_init__(self) -> None:
        _check_choice(self.kind, EDGE_KINDS, "edge kind")
        _check_choice(self.confidence, CONFIDENCES, "confidence")
        if not self.source or not self.target:
            raise ValueError(f"{self.kind} edge has an empty end: {self.source!r} -> {self.target!r}")
        if self.anchor is not None and self.kind != "links":
            raise ValueError(f"a {self.kind} edge cannot keep an anchor")

    def sort_key(self) -> tuple[str, str, str, str, str]:
        return (self.source, self.kind, self.target, self.anchor or "", self.confidence)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "confidence": self.confidence,
            "kind": self.kind,
            "source": self.source,
            "target": self.target,
        }
        if self.anchor is not None:
            out["anchor"] = self.anchor
        return out


def _node_type(node: Node) -> str:
    if isinstance(node, FileNode):
        return "file"
    if isinstance(node, SectionNode):
        return "section"
    return "id"


def node_sort_key(node: Node) -> tuple[str, int]:
    """Nodes sort by address, then by node type (file, section, id)."""
    return (node.address, NODE_TYPES.index(_node_type(node)))


@dataclass(frozen=True)
class Index:
    """A whole index. The order of ``nodes`` and ``edges`` does not matter: :func:`to_dict` sorts them."""

    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for node in self.nodes:
            if node.address in seen:
                raise ValueError(f"two nodes have the address {node.address!r}")
            seen.add(node.address)
        if len(set(self.edges)) != len(self.edges):
            raise ValueError("the index holds the same edge twice")


def to_dict(index: Index) -> dict[str, Any]:
    """The serialisable form of ``index``: the format version and the sorted node and edge lists."""
    return {
        "edges": [edge.to_dict() for edge in sorted(index.edges, key=Edge.sort_key)],
        "index_format": INDEX_FORMAT,
        "nodes": [node.to_dict() for node in sorted(index.nodes, key=node_sort_key)],
    }


def to_json(index: Index) -> str:
    """The one serialised form: sorted keys, two-space indent, UTF-8 text, and a final newline."""
    return json.dumps(to_dict(index), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _node_from_dict(data: Mapping[str, Any]) -> Node:
    node = data.get("node")
    if node == "file":
        return FileNode(path=data["address"], kind=data["kind"], zone=data["zone"])
    if node == "section":
        return SectionNode(
            address=data["address"],
            title=data["title"],
            level=data["level"],
            own_hash=data["own_hash"],
            tree_hash=data["tree_hash"],
        )
    if node == "id":
        return IdNode(address=data["address"], kind=data["kind"], title=data["title"], defined_by=data["defined_by"])
    raise ValueError(f"unknown node type {node!r}")


def from_dict(data: Mapping[str, Any]) -> Index:
    """Read the form :func:`to_dict` writes. Another ``index_format`` is refused, not converted."""
    if data.get("index_format") != INDEX_FORMAT:
        raise ValueError(f"index_format {data.get('index_format')!r} is not {INDEX_FORMAT}")
    nodes = tuple(_node_from_dict(item) for item in data["nodes"])
    edges = tuple(
        Edge(
            kind=item["kind"],
            source=item["source"],
            target=item["target"],
            confidence=item["confidence"],
            anchor=item.get("anchor"),
        )
        for item in data["edges"]
    )
    return Index(nodes=nodes, edges=edges)


def from_json(text: str) -> Index:
    """Read the text :func:`to_json` writes."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("an index is a JSON object")
    return from_dict(data)
