# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The ``id`` nodes of the index and the ``mentions``, ``runs`` and ``bundles`` edges; the reports and ``query``.

**ID kinds.** The project config's ``ids`` object holds one entry per ID kind (:data:`docindex.model.ID_KINDS`):

- ``pattern``: a regex whose group 1 is the ID as a text names it (``CMD-01``, ``REQ-SH-060``, ``0011`` for
  ``ADR 0011``, ``register-index`` for ``implement/playbooks/register-index.md``);
- ``defined_in``: the files and folders that define such IDs, in order of preference (see *Mentions*);
- ``define``: how they define them, one of three forms:

  - ``{"json": {"list": L, "id": K, "title": T}}``: each object of the list ``L`` of a JSON file of ``defined_in``
    defines the ID in its key ``K``, titled by its key ``T``. The **file** node defines it (the catalogue's checks);
  - ``{"heading": R, "level": N}``: each Markdown heading of level ``N`` under ``defined_in`` whose title starts
    with a match of ``R`` defines the ID in group 1 of ``R``. Its **section** defines it, and the title is the rest
    of the heading after the ID and a dash or a colon (the spec's ``### REQ-...`` requirements);
  - ``{"files": R}``: each file under ``defined_in`` whose whole path matches ``R`` defines the ID in group 1. The
    **file** defines it. Its title is the first heading of a Markdown file, the ``title`` of a JSON file, or the
    first line of a Python module's docstring; else empty (ADRs, playbooks, tools, schemas);

- ``address``: the template of the node's address, with ``{id}`` and ``{folder}`` (the folder of the defining file);
  ``{id}`` when the config names none. A template keeps addresses unique: the ID of a tool is its path, which the
  tool's file node already holds (``tool:{id}``), and ADR numbers repeat across the ADR folders
  (``{folder}/ADR-{id}``);
- ``runs``: ``true`` for the kind whose IDs a command runs (tools).

The core reads every path and pattern from the config; it imports nothing from the folders it reads. An ID whose
address another node already holds, or that a second place defines again, is kept once (the first definition, in
``defined_in`` order, then path order) and named in :attr:`Definitions.problems`.

**Mentions.** A ``mentions`` edge runs from a section (Markdown) or a file (Python, JSON and YAML, read as plain text
for IDs only) to an ``id`` node, for each match of a kind's ``pattern`` that names a defined ID. Every line of a
Markdown file counts, the code fences, the frontmatter and HTML comments included, as ``dev/recipe_lint.py`` reads
check and requirement IDs (``check_catalogue_references``, ``check_requirement_references``). A match that names no
defined ID gives no edge. Nor does a mention inside the node that defines the ID: the catalogue file's own check IDs,
an ADR's own number, a tool's own path. When several IDs share the text (``ADR 0001`` is in four ADR folders), the
one defined nearest the mentioning file wins: the longest common folder prefix, then the ``defined_in`` order. The
edge is ``exact`` when one ID has the text or the nearest is the only nearest, else ``name-match``.

**Runs.** A ``runs`` edge runs from a section to an ID of a ``runs`` kind (a tool) whose text appears in an inline
code span of a prose line or on a line of a command block: a fence whose info string is a shell tag or whose lines
start like a command, as the sweep defines it (:mod:`docindex.sweep`).

**Bundles.** :func:`bundle_members` resolves the entries of one bundle against the tracked files: an entry that ends
in ``/`` is every file under that folder, an entry that ends in ``/*.md`` every Markdown file under that folder, at
any depth, and any other entry the one file at that path. The extractor makes one node per bundle and a ``bundles``
edge to each member.

**Reports** (:func:`reports`, plan 9.4). Three lists, a report only and never a gate: a recipe section (a section of
a file in the ``recipe`` zone) that no ``links`` edge targets and that mentions no ID; a bundled file that no
section or file of its bundle names (by a ``links``, ``mentions`` or ``runs`` edge to the file, a section of it, or
an ID it defines); a check ID that no recipe file mentions.

**Query.** :func:`query_main` takes the arguments of ``query <address>``: the node as one line of JSON, then its
outgoing and incoming edges; or of ``query --report``: the three reports. The entry point calls it
(``dev/doc_index.py``, ``query``).

This module imports nothing outside the standard library and this package.
"""

from __future__ import annotations

import ast
import json
import posixpath
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from .gitread import GitError
from .links import _code_spans
from .markdown import Document
from .model import Edge, FileNode, IdNode, Index, Node, SectionNode
from .sweep import _command_block, _fence_end
from .usage import UsageParser

__all__ = [
    "Definitions",
    "Heading",
    "IdKind",
    "Reports",
    "bundle_members",
    "define",
    "id_kinds",
    "mention_edges",
    "query_main",
    "query_text",
    "reports",
    "reports_text",
    "run_edges",
]

#: The zone whose sections and files the reports call the recipes.
RECIPE_ZONES = ("recipe",)

_TITLE_SEPARATORS = " \t—–-:"


@dataclass(frozen=True)
class Heading:
    """A heading of a parsed Markdown file: the file, the section's index address, its level and title."""

    path: str
    address: str
    level: int
    title: str


@dataclass(frozen=True)
class IdKind:
    """One ID kind of the config. ``define`` is the raw ``define`` object."""

    kind: str
    pattern: re.Pattern[str]
    defined_in: tuple[str, ...]
    define: Mapping[str, Any]
    address: str = "{id}"
    runs: bool = False


@dataclass(frozen=True)
class Definitions:
    """The ``id`` nodes of a tree; ``by_text`` maps (kind, ID text) to its nodes in order of preference."""

    nodes: tuple[IdNode, ...]
    by_text: Mapping[tuple[str, str], tuple[IdNode, ...]]
    problems: tuple[str, ...] = ()


def _under(path: str, prefix: str) -> bool:
    prefix = prefix.rstrip("/")
    return path == prefix or path.startswith(prefix + "/")


def id_kinds(config: Mapping[str, Any]) -> list[IdKind]:
    """The ID kinds of ``config``, sorted by kind. A kind with no ``define`` defines nothing and is left out."""
    kinds: list[IdKind] = []
    for kind, entry in sorted(config.get("ids", {}).items()):
        if "define" not in entry:
            continue
        kinds.append(
            IdKind(
                kind=kind,
                pattern=re.compile(entry["pattern"]),
                defined_in=tuple(entry.get("defined_in", ())),
                define=entry["define"],
                address=str(entry.get("address", "{id}")),
                runs=bool(entry.get("runs", False)),
            )
        )
    return kinds


# --- Defining -------------------------------------------------------------------------------------------------------


def _file_title(path: str, text: str, first_heading: str | None) -> str:
    if first_heading is not None:
        return first_heading
    if path.endswith(".json"):
        try:
            data = json.loads(text)
        except ValueError:
            return ""
        title = data.get("title") if isinstance(data, dict) else None
        return title if isinstance(title, str) else ""
    if path.endswith(".py"):
        try:
            docstring = ast.get_docstring(ast.parse(text))
        except (SyntaxError, ValueError):
            return ""
        return docstring.strip().splitlines()[0].strip() if docstring and docstring.strip() else ""
    return ""


def _defined(
    kind: IdKind,
    files: Sequence[str],
    read: Callable[[str], str | None],
    headings: Sequence[Heading],
    first_headings: Mapping[str, str],
) -> list[tuple[str, str, str, str]]:
    """(ID text, title, defining address, folder of the defining file) for each definition of ``kind``, in
    ``defined_in`` order, then in path order."""
    found: list[tuple[str, str, str, str]] = []
    define = kind.define
    for place in kind.defined_in:
        if "json" in define:
            spec = define["json"]
            for path in (path for path in files if _under(path, place)):
                text = read(path)
                try:
                    data = json.loads(text) if text is not None else None
                except ValueError:
                    continue
                items = data.get(spec["list"], []) if isinstance(data, dict) else []
                for item in items if isinstance(items, list) else []:
                    if isinstance(item, dict) and isinstance(item.get(spec["id"]), str):
                        title = item.get(spec.get("title", "title"), "")
                        found.append((item[spec["id"]], str(title), path, posixpath.dirname(path)))
        elif "heading" in define:
            pattern = re.compile(define["heading"])
            level = int(define.get("level", 0))
            for heading in headings:
                if not _under(heading.path, place) or (level and heading.level != level):
                    continue
                match = pattern.match(heading.title)
                if match is None:
                    continue
                title = heading.title[match.end() :].strip(_TITLE_SEPARATORS)
                found.append((match.group(1), title, heading.address, posixpath.dirname(heading.path)))
        elif "files" in define:
            pattern = re.compile(define["files"])
            for path in (path for path in files if _under(path, place)):
                match = pattern.fullmatch(path)
                if match is None:
                    continue
                first = first_headings.get(path)
                text = read(path) if first is None else ""
                title = _file_title(path, text or "", first)
                found.append((match.group(1), title, path, posixpath.dirname(path)))
    return found


def define(
    config: Mapping[str, Any],
    files: Sequence[str],
    read: Callable[[str], str | None],
    headings: Sequence[Heading],
    taken: Iterable[str],
) -> Definitions:
    """The ``id`` nodes that ``files`` (the indexed paths, sorted) and the parsed ``headings`` define.

    ``read`` reads a file's text; ``taken`` holds the addresses of the index's other nodes.
    """
    used = set(taken)
    first_headings: dict[str, str] = {}
    for heading in headings:
        first_headings.setdefault(heading.path, heading.title)
    nodes: list[IdNode] = []
    by_text: dict[tuple[str, str], list[IdNode]] = {}
    problems: list[str] = []
    for kind in id_kinds(config):
        for text, title, defined_by, folder in _defined(kind, files, read, headings, first_headings):
            address = kind.address.format(id=text, folder=folder)
            if address in used:
                problems.append(f"{kind.kind} {text}: the address {address} is taken; {defined_by} is left out")
                continue
            try:
                node = IdNode(address=address, kind=kind.kind, title=title, defined_by=defined_by)
            except ValueError as exc:
                problems.append(f"{kind.kind} {text}: {exc}")
                continue
            used.add(address)
            nodes.append(node)
            by_text.setdefault((kind.kind, text), []).append(node)
    return Definitions(
        nodes=tuple(nodes),
        by_text={key: tuple(value) for key, value in by_text.items()},
        problems=tuple(sorted(problems)),
    )


# --- Mentions and runs ----------------------------------------------------------------------------------------------


def _file_of(address: str) -> str:
    return address.partition("#")[0]


def _inside(source: str, definer: str) -> bool:
    """Whether ``source`` is the defining node or lies inside it (a section of the defining file, or a child
    section of the defining section)."""
    if source == definer:
        return True
    return source.startswith(definer + ("/" if "#" in definer else "#"))


def _common(left: str, right: str) -> int:
    count = 0
    for a, b in zip(left.split("/"), right.split("/")):
        if a != b:
            break
        count += 1
    return count


def _choose(candidates: Sequence[IdNode], source: str) -> tuple[IdNode, str] | None:
    """The ID that a mention from ``source`` names, and the edge's confidence; ``None`` for none."""
    if len(candidates) == 1:
        return candidates[0], "exact"
    if not candidates:
        return None
    folder = posixpath.dirname(_file_of(source))
    scores = [_common(posixpath.dirname(_file_of(node.defined_by)), folder) for node in candidates]
    best = max(scores)
    chosen = candidates[scores.index(best)]
    return chosen, ("exact" if scores.count(best) == 1 else "name-match")


def _resolve(kind: IdKind, text: str, source: str, definitions: Definitions) -> tuple[IdNode, str] | None:
    picked = _choose(definitions.by_text.get((kind.kind, text), ()), source)
    if picked is None or _inside(source, picked[0].defined_by):
        return None
    return picked


def mention_edges(kinds: Sequence[IdKind], definitions: Definitions, lines: Iterable[tuple[str, str]]) -> list[Edge]:
    """The ``mentions`` edges of ``lines``: (address of the holding node, text) pairs, in order. Unique, in the
    order found."""
    edges: dict[Edge, None] = {}
    for source, text in lines:
        for kind in kinds:
            for match in kind.pattern.finditer(text):
                picked = _resolve(kind, match.group(1), source, definitions)
                if picked is not None:
                    node, confidence = picked
                    edges.setdefault(
                        Edge(kind="mentions", source=source, target=node.address, confidence=confidence), None
                    )
    return list(edges)


def _run_texts(document: Document) -> list[tuple[int, str]]:
    """(1-based line number, text) of each code span of a prose line and each inner line of a command block."""
    lines = document.lines
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.fence:
            end = _fence_end(lines, index)
            if _command_block(lines, index, end) is not None:
                found.extend((inner.number, inner.text) for inner in lines[index + 1 : end + 1])
            index = end + 1
            continue
        found.extend((line.number, line.text[begin:close]) for begin, close in _code_spans(line.text))
        index += 1
    return found


def run_edges(
    kinds: Sequence[IdKind], definitions: Definitions, document: Document, holders: Sequence[str]
) -> list[Edge]:
    """The ``runs`` edges of one parsed Markdown file. ``holders[n]`` is the address that holds line ``n + 1``."""
    edges: dict[Edge, None] = {}
    runnable = [kind for kind in kinds if kind.runs]
    if not runnable:
        return []
    for number, text in _run_texts(document):
        source = holders[number - 1]
        for kind in runnable:
            for match in kind.pattern.finditer(text):
                picked = _resolve(kind, match.group(1), source, definitions)
                if picked is not None:
                    node, confidence = picked
                    edges.setdefault(Edge(kind="runs", source=source, target=node.address, confidence=confidence), None)
    return list(edges)


# --- Bundles --------------------------------------------------------------------------------------------------------


def bundle_members(entries: Sequence[str], files: Sequence[str]) -> tuple[list[str], list[str]]:
    """The sorted files of ``files`` that the bundle ``entries`` name, and the entries that name none."""
    members: set[str] = set()
    empty: list[str] = []
    for entry in entries:
        if entry.endswith("/*.md"):
            folder = entry[: -len("/*.md")]
            hits = [path for path in files if _under(path, folder) and path != folder and path.endswith(".md")]
        elif entry.endswith("/"):
            hits = [path for path in files if _under(path, entry) and path != entry.rstrip("/")]
        else:
            hits = [entry] if entry in files else []
        if not hits:
            empty.append(entry)
        members.update(hits)
    return sorted(members), sorted(set(empty))


# --- Reports --------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Reports:
    """The three lists of plan 9.4, each sorted."""

    unlinked_sections: tuple[str, ...]
    unnamed_bundle_files: tuple[tuple[str, str], ...]
    unmentioned_checks: tuple[str, ...]


def reports(index: Index, recipe_zones: Sequence[str] = RECIPE_ZONES) -> Reports:
    """The reports of ``index``: never a gate, only lists."""
    files = {node.path: node for node in index.nodes if isinstance(node, FileNode)}
    ids = {node.address: node for node in index.nodes if isinstance(node, IdNode)}

    def zone(address: str) -> str | None:
        node = files.get(_file_of(address))
        return node.zone if node is not None else None

    linked = {edge.target for edge in index.edges if edge.kind == "links"}
    mentioning = {edge.source for edge in index.edges if edge.kind == "mentions"}
    unlinked = sorted(
        node.address
        for node in index.nodes
        if isinstance(node, SectionNode)
        and zone(node.address) in recipe_zones
        and node.address not in linked
        and node.address not in mentioning
    )

    members: dict[str, set[str]] = {}
    for edge in index.edges:
        if edge.kind == "bundles":
            members.setdefault(edge.source, set()).add(edge.target)
    named_by: dict[str, set[str]] = {}  # file -> the files whose nodes name it
    for edge in index.edges:
        if edge.kind not in ("links", "mentions", "runs"):
            continue
        target = edge.target
        if target in ids:
            target = ids[target].defined_by
        named_by.setdefault(_file_of(target), set()).add(_file_of(edge.source))
    unnamed: list[tuple[str, str]] = []
    for bundle, inside in sorted(members.items()):
        for path in sorted(inside):
            if not (named_by.get(path, set()) - {path}) & inside:
                unnamed.append((bundle, path))

    mentioned = {edge.target for edge in index.edges if edge.kind == "mentions" and zone(edge.source) in recipe_zones}
    unmentioned = sorted(
        node.address for node in ids.values() if node.kind == "check" and node.address not in mentioned
    )
    return Reports(
        unlinked_sections=tuple(unlinked),
        unnamed_bundle_files=tuple(unnamed),
        unmentioned_checks=tuple(unmentioned),
    )


def reports_text(result: Reports) -> str:
    """The reports as text: one block per report, a count line, then one line per item."""
    lines = [f"recipe sections that nothing links to and that mention no ID: {len(result.unlinked_sections)}"]
    lines += [f"  {address}" for address in result.unlinked_sections]
    lines.append(f"bundled files that no file of their bundle names: {len(result.unnamed_bundle_files)}")
    lines += [f"  {bundle}: {path}" for bundle, path in result.unnamed_bundle_files]
    lines.append(f"check IDs that no recipe file mentions: {len(result.unmentioned_checks)}")
    lines += [f"  {address}" for address in result.unmentioned_checks]
    return "\n".join(lines) + "\n"


# --- Query ----------------------------------------------------------------------------------------------------------


def _edge_text(edge: Edge, end: str) -> str:
    details = edge.confidence + (f", anchor #{edge.anchor}" if edge.anchor is not None else "")
    return f"  {edge.kind} {end} ({details})"


def query_text(index: Index, address: str) -> str | None:
    """The node at ``address`` as one line of JSON, then its outgoing and incoming edges; ``None`` if no node has
    the address."""
    node: Node | None = next((node for node in index.nodes if node.address == address), None)
    if node is None:
        return None
    outgoing = sorted((edge for edge in index.edges if edge.source == address), key=Edge.sort_key)
    incoming = sorted(
        (edge for edge in index.edges if edge.target == address),
        key=lambda edge: (edge.kind, edge.source, edge.anchor or "", edge.confidence),
    )
    lines = [json.dumps(node.to_dict(), sort_keys=True, ensure_ascii=False), f"outgoing: {len(outgoing)}"]
    lines += [_edge_text(edge, edge.target) for edge in outgoing]
    lines.append(f"incoming: {len(incoming)}")
    lines += [_edge_text(edge, edge.source) for edge in incoming]
    return "\n".join(lines) + "\n"


def query_main(
    argv: Sequence[str], build: Callable[[str | None], Index], *, prog: str = "doc_index.py query"
) -> tuple[int, str, str]:
    """Run ``query`` and return (exit code, stdout text, stderr text).

    ``build`` returns the index of the working tree (``None``) or of a git ref. Exit 0 with the node or the
    reports, 1 when no node has the address, a git call fails or the arguments are wrong (a usage error).
    """
    parser = UsageParser(prog=prog, description="Show one node and its edges, or the reports.")
    parser.add_argument("address", nargs="?", metavar="ADDRESS", help="a file path, a section address or an ID")
    parser.add_argument("--report", action="store_true", help="print the reports of plan 9.4 instead (never a gate)")
    parser.add_argument("--at", metavar="GIT_REF", help="query the index at this git ref, not the working tree")
    args = parser.parse_args(list(argv))
    if (args.address is None) == (not args.report):
        parser.error("give an ADDRESS or --report, not both")
    try:
        index = build(args.at)
    except GitError as exc:
        return 1, "", f"{prog}: {exc}\n"
    if args.report:
        return 0, reports_text(reports(index)), ""
    text = query_text(index, args.address)
    if text is None:
        return 1, "", f"{prog}: no node has the address {args.address!r}\n"
    return 0, text, ""
