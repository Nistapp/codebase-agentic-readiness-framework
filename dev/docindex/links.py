# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The ``links`` edges of the index: the inline Markdown links of one parsed file, and its bare file names.

:func:`find_links` reads a :class:`~docindex.markdown.Document` and returns each inline link ``[text](target)``:

- on every line outside a code fence (the parser's ``fence`` flag), the YAML frontmatter and HTML comments
  included, as on GitHub's source view and as ``dev/recipe_lint.py`` reads them;
- never an image (``![alt](src)``), though an image inside a link's text leaves the link itself; never a link
  inside an inline code span; never a reference-style link (``[text][ref]``), a bracket without a ``(`` after it,
  or an escaped ``\\[``;
- never an external target: a URI scheme (``https:``, ``mailto:``, ...) or a protocol-relative ``//host``.

The destination follows CommonMark: ``<...>``, or a run with no space and balanced parentheses, then an optional
title. A link whose destination is empty is no link to a file and is left out.

:func:`resolve` turns a target into a repository path and an anchor. The path part is URL-decoded and resolved
against the folder of the source file; a target with no path part (``#anchor``) is the source file itself. The
anchor is the text after the first ``#``, kept as written; an empty anchor is none.

:func:`link_edges` makes the edges of one file. A **links** edge runs from the address of the section that holds
the link (the file node for the text before the first heading and the frontmatter) to the target file node or,
with an anchor that names a heading of a parsed Markdown file, to that section node. It keeps the anchor. Its
confidence is ``exact``, except for a link to a folder: the index has no folder nodes, so no node has that address,
and the edge is ``name-match``. A link whose target does not resolve is kept, not dropped: its edge still points at
the resolved path, and a :class:`Link` with a ``problem`` flags it (:data:`PROBLEMS`).

A **name-match** edge comes from a bare file name in prose: a token such as ``recipe_lint.py`` or
``check-a-recipe-change.md`` that has an extension, is not part of a path (no ``/`` next to it), and lies outside
a code fence, the frontmatter, an HTML comment and every link. Inline code spans count as prose here. The name
selects a file of the index: the file of that name in the source's own folder, else the only indexed file of that
name. A name that several files carry, and none in the source's folder, gives no edge. A file's mention of its own
name gives none either. The edge runs from the holding section to the file node, with confidence ``name-match``.

Every edge is unique: a second link from the same section to the same target adds nothing. This module imports
nothing outside the standard library and this package.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from typing import Collection, Mapping, Sequence
from urllib.parse import unquote

from .markdown import Document
from .model import Edge

__all__ = [
    "PROBLEMS",
    "Found",
    "Link",
    "LinkContext",
    "LinkEdges",
    "find_links",
    "find_names",
    "is_external",
    "link_edges",
    "resolve",
]

#: Why a link's target does not resolve: the path leaves the repository, no tracked file or folder has the path,
#: or the anchor names no heading of the (parsed Markdown) target.
PROBLEMS = ("outside", "missing", "anchor")

_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")
_NAME = re.compile(r"(?<![\w./\\-])\w[\w.-]*(?![\w/\\-])")
_EXTENSION = re.compile(r"\.[A-Za-z0-9]+$")


@dataclass(frozen=True)
class Found:
    """One link target or bare file name of a file, as written, and its 1-based line (in memory only)."""

    line: int
    text: str


@dataclass(frozen=True)
class Link:
    """A link that does not resolve, kept with its flag. ``target`` is as written; ``path`` as resolved."""

    source: str
    target: str
    path: str
    anchor: str | None
    problem: str

    def describe(self) -> str:
        return f"{self.source} -> {self.target} ({self.problem})"


@dataclass(frozen=True)
class LinkContext:
    """What a link resolves against: the tracked files, the heading slugs of each parsed Markdown file (slug to
    section address), the indexed files by file name, and every folder that holds a tracked file (``.`` too)."""

    files: frozenset[str]
    anchors: Mapping[str, Mapping[str, str]]
    by_name: Mapping[str, tuple[str, ...]]
    folders: frozenset[str]

    @classmethod
    def build(
        cls, files: Collection[str], anchors: Mapping[str, Mapping[str, str]], indexed: Collection[str]
    ) -> LinkContext:
        """The context for the tracked ``files``, the parsed files' ``anchors`` and the ``indexed`` file paths."""
        folders = {"."}
        for path in files:
            parts = path.split("/")
            for end in range(1, len(parts)):
                folders.add("/".join(parts[:end]))
        by_name: dict[str, list[str]] = {}
        for path in sorted(indexed):
            by_name.setdefault(posixpath.basename(path), []).append(path)
        return cls(
            files=frozenset(files),
            anchors=anchors,
            by_name={name: tuple(paths) for name, paths in by_name.items()},
            folders=frozenset(folders),
        )


@dataclass(frozen=True)
class LinkEdges:
    """The ``links`` edges of one file, in the order found, and its unresolved links."""

    edges: tuple[Edge, ...]
    problems: tuple[Link, ...]


# --- Finding links on a line ----------------------------------------------------------------------------------------


def _escaped(text: str, index: int) -> bool:
    """Whether the character at ``index`` follows an odd run of backslashes."""
    count = 0
    while index - count - 1 >= 0 and text[index - count - 1] == "\\":
        count += 1
    return count % 2 == 1


def _code_spans(text: str) -> list[tuple[int, int]]:
    """The ``[start, end)`` ranges of the line's inline code spans: a backtick run up to a run of the same length."""
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        if text[index] != "`" or _escaped(text, index):
            index += 1
            continue
        run = index
        while run < len(text) and text[run] == "`":
            run += 1
        width = run - index
        search = run
        close = -1
        while search < len(text):
            if text[search] != "`":
                search += 1
                continue
            end = search
            while end < len(text) and text[end] == "`":
                end += 1
            if end - search == width:
                close = end
                break
            search = end
        if close < 0:
            index = run  # an unmatched run is literal backticks
            continue
        spans.append((index, close))
        index = close
    return spans


def _closing_bracket(text: str, start: int, code: Sequence[tuple[int, int]]) -> int:
    """The index of the ``]`` that closes the ``[`` at ``start``, or -1."""
    depth = 0
    index = start
    while index < len(text):
        span = next((end for begin, end in code if begin == index), None)
        if span is not None:
            index = span
            continue
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _skip_space(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t":
        index += 1
    return index


def _destination(text: str, start: int) -> tuple[str, int] | None:
    """The destination of a link whose ``(`` is at ``start - 1``, and the index after its ``)``; ``None`` if the
    parenthesis does not hold a well-formed destination and title."""
    index = _skip_space(text, start)
    if index < len(text) and text[index] == "<":
        close = index + 1
        while close < len(text) and text[close] != ">":
            if text[close] in "<\n" and not _escaped(text, close):
                return None
            close += 2 if text[close] == "\\" else 1
        if close >= len(text):
            return None
        target, index = text[index + 1 : close], close + 1
    else:
        depth = 0
        begin = index
        while index < len(text):
            char = text[index]
            if char == "\\" and index + 1 < len(text):
                index += 2
                continue
            if char in " \t":
                break
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            index += 1
        if depth != 0:
            return None
        target = text[begin:index]
    spaced = _skip_space(text, index)
    if spaced < len(text) and text[spaced] in "\"'(" and spaced > index:
        closer = ")" if text[spaced] == "(" else text[spaced]
        end = spaced + 1
        while end < len(text) and (text[end] != closer or _escaped(text, end)):
            end += 1
        if end >= len(text):
            return None
        spaced = _skip_space(text, end + 1)
    if spaced >= len(text) or text[spaced] != ")":
        return None
    return target, spaced + 1


def _scan(text: str) -> tuple[list[str], list[tuple[int, int]]]:
    """The link destinations of one line, images left out, and the ``[start, end)`` ranges of every link and
    image span."""
    code = _code_spans(text)
    targets: list[str] = []
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        inside = next((end for begin, end in code if begin <= index < end), None)
        if inside is not None:
            index = inside
            continue
        if text[index] != "[" or _escaped(text, index):
            index += 1
            continue
        image = index > 0 and text[index - 1] == "!" and not _escaped(text, index - 1)
        close = _closing_bracket(text, index, code)
        if close < 0 or close + 1 >= len(text) or text[close + 1] != "(":
            index += 1
            continue
        parsed = _destination(text, close + 2)
        if parsed is None:
            index += 1
            continue
        target, after = parsed
        spans.append((index - 1 if image else index, after))
        if not image and target:
            targets.append(target)
        index = after
    return targets, spans


def is_external(target: str) -> bool:
    """Whether ``target`` names another site or a scheme: ``https://...``, ``mailto:...``, ``//host``, ..."""
    return bool(_SCHEME.match(target)) or target.startswith("//")


def find_links(document: Document) -> list[Found]:
    """Each inline link target of ``document`` outside a code fence, images and external targets left out."""
    found: list[Found] = []
    for line in document.lines:
        if line.fence:
            continue
        targets, _spans = _scan(line.text)
        found.extend(Found(line.number, target) for target in targets if not is_external(target))
    return found


def find_names(document: Document, names: Collection[str]) -> list[Found]:
    """Each bare file name of ``names`` in the prose of ``document``: outside fences, the frontmatter, comments and
    links. Only a name with an extension counts."""
    found: list[Found] = []
    for line in document.lines:
        if line.fence or line.frontmatter or line.comment:
            continue
        text = line.text
        _targets, spans = _scan(text)
        for begin, end in reversed(spans):
            text = text[:begin] + " " * (end - begin) + text[end:]
        text = text.replace("`", " ")
        for match in _NAME.finditer(text):
            name = match.group(0).rstrip(".")
            if _EXTENSION.search(name) and name in names:
                found.append(Found(line.number, name))
    return found


# --- Resolving ------------------------------------------------------------------------------------------------------


def resolve(source: str, target: str) -> tuple[str, str | None]:
    """The repository path and the anchor of the relative ``target`` of a link in the file at ``source``.

    The path is normalised (``.`` and ``..`` parts folded); a path that leaves the repository keeps its leading
    ``..``. The repository root is ``.``.
    """
    path_part, sep, anchor = target.partition("#")
    path_part = unquote(path_part)
    if not path_part:
        path = source
    elif path_part.startswith("/"):
        path = posixpath.normpath(path_part.lstrip("/") or ".")
    else:
        path = posixpath.normpath(posixpath.join(posixpath.dirname(source), path_part))
    return path, (anchor if sep and anchor else None)


def _problem(path: str, anchor: str | None, context: LinkContext) -> str | None:
    if path == ".." or path.startswith("../"):
        return "outside"
    if path not in context.files and path not in context.folders:
        return "missing"
    slugs = context.anchors.get(path)
    if anchor is not None and slugs is not None and anchor not in slugs:
        return "anchor"
    return None


def link_edges(document: Document, holders: Sequence[str], context: LinkContext) -> LinkEdges:
    """The ``links`` edges of the parsed ``document`` and its unresolved links.

    ``holders[n]`` is the index address of the section that holds line ``n + 1`` (the file path for a line before
    the first heading).
    """
    path = document.path
    edges: dict[Edge, None] = {}
    problems: dict[Link, None] = {}
    for found in find_links(document):
        source = holders[found.line - 1]
        resolved, anchor = resolve(path, found.text)
        problem = _problem(resolved, anchor, context)
        target = resolved
        if anchor is not None and problem is None:
            target = context.anchors.get(resolved, {}).get(anchor, resolved)
        confidence = "name-match" if resolved in context.folders else "exact"  # no node has a folder's address
        edges.setdefault(Edge(kind="links", source=source, target=target, confidence=confidence, anchor=anchor), None)
        if problem is not None:
            problems.setdefault(Link(source, found.text, resolved, anchor, problem), None)
    folder = posixpath.dirname(path)
    for found in find_names(document, context.by_name):
        candidates = context.by_name[found.text]
        local = posixpath.join(folder, found.text) if folder else found.text
        if local in candidates:
            chosen = local
        elif len(candidates) == 1:
            chosen = candidates[0]
        else:
            continue
        if chosen != path:
            edge = Edge(kind="links", source=holders[found.line - 1], target=chosen, confidence="name-match")
            edges.setdefault(edge, None)
    return LinkEdges(edges=tuple(edges), problems=tuple(problems))
