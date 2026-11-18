# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The Markdown parser that the sweep and the extractor share: one file's text in, lines and sections out.

:func:`parse` reads one file and returns a :class:`Document`:

- ``lines``: one :class:`Line` per line of the file, with flags that say whether the line is YAML frontmatter, in a
  code fence, an HTML comment, part of a heading, a table row or part of a list item.
- ``sections``: one :class:`Section` per heading, in document order, after a file-level section that holds the text
  before the first heading. A section's address is ``<path>#<slug>/<slug>/...``, the chain of heading slugs from the
  top level down; the file-level section's address is ``<path>#`` and its level is 0. It is always present, and it
  is empty when the file starts with a heading.

What counts as a heading:

- an ATX heading: ``#`` to ``######`` after at most three spaces, then a space, a tab or the end of the line. A
  closing run of ``#`` after a space is dropped (CommonMark);
- a setext heading: a paragraph of plain lines underlined by a line of ``=`` (level 1) or ``-`` (level 2). A
  paragraph in a list item, a block quote, a table or an HTML comment is never a setext heading, so ``- item``
  followed by ``---`` is a list and a thematic break;
- never a line in a code fence, in an HTML comment or in the YAML frontmatter.

A code fence opens on a line of three or more backticks or tildes, at any indent (so a fence inside a list item
counts too). It closes on a line of the same character, at least as long as the opening run, with nothing after it.
An unclosed fence runs to the end of the file. The frontmatter is a first line ``---`` up to the next line ``---``;
without the closing line, the first line is a thematic break.

Slugs follow GitHub (github-slugger): the heading text, its inline links reduced to their text, lower case,
punctuation dropped except ``-`` and ``_``, each space turned into ``-``. A slug seen before in the same file gets
``-1``, ``-2``, ... in document order, and a generated slug is itself remembered, so every slug in a file is unique.
A heading with no slug text (``#`` alone, ``## !!!``) gets the empty slug first, as on GitHub; a caller that needs a
non-empty address segment must handle that case.

Each section carries two SHA-256 hashes of its normalised text (:func:`normalise`): ``own_hash`` over its own text
(its heading and the lines up to the next heading) and ``tree_hash`` over its own text and every child section. The
file-level section's ``tree_hash`` covers the whole body.

Line numbers (``Line.number``, ``Section.start`` and the like) are for in-memory use only: the sweep's text report
and a caller's diagnostics may use them, but no committed file may hold one. This module imports nothing outside the
standard library and this package.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from .model import content_hash

__all__ = [
    "Document",
    "Line",
    "Section",
    "Slugger",
    "normalise",
    "parse",
    "slugify",
]

_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_ATX_CLOSING = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_THEMATIC = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_FENCE_OPEN = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*$")
_LIST_MARKER = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])([ \t]+|$)")
_QUOTE = re.compile(r"^ {0,3}>")
_COMMENT_OPEN = re.compile(r"^ {0,3}<!--")
_TABLE_DELIMITER = re.compile(r"^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
_INLINE_LINK = re.compile(r"(?<!!)\[([^\]\n]*)\]\([^)\n]*\)")
_SLUG_DROP = re.compile(r"[^\w\s-]")
_WHITESPACE = re.compile(r"\s+")


# --- Slugs ----------------------------------------------------------------------------------------------------------


def slugify(heading: str) -> str:
    """GitHub's anchor for a heading text, before the duplicate suffix.

    An inline link counts as its text. Then, as ``dev/recipe_lint.py``'s ``slugify`` does: lower case, every
    character that is not a word character, a whitespace character or ``-`` dropped, and each space turned into
    ``-`` (two spaces give two hyphens, as on GitHub).
    """
    text = _INLINE_LINK.sub(r"\1", heading)
    return _SLUG_DROP.sub("", text.lower()).replace(" ", "-")


class Slugger:
    """GitHub's duplicate rule for the slugs of one file: ``foo``, ``foo-1``, ``foo-2``, ... in document order.

    As in github-slugger, a generated slug is remembered too, so the headings ``Foo``, ``Foo`` and ``Foo 1`` give
    ``foo``, ``foo-1`` and ``foo-1-1``: the slugs of one file are always unique.
    """

    def __init__(self) -> None:
        self._occurrences: dict[str, int] = {}

    def slug(self, heading: str) -> str:
        original = slugify(heading)
        result = original
        while result in self._occurrences:
            self._occurrences[original] += 1
            result = f"{original}-{self._occurrences[original]}"
        self._occurrences[result] = 0
        return result


# --- The data -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """One line of a file, without its line ending. ``number`` counts from 1 and is for in-memory use only.

    ``fence`` holds for the opening and closing fence lines and every line between them. ``heading`` holds for an
    ATX heading line and for every line of a setext heading, its underline included. ``table_row`` holds for a GFM
    table's header, delimiter and body rows. ``list_item`` holds for a list item's marker line and for each
    non-blank line that continues the item (indented or lazy), a fenced block inside the item included.
    """

    number: int
    text: str
    frontmatter: bool = False
    fence: bool = False
    comment: bool = False
    heading: bool = False
    table_row: bool = False
    list_item: bool = False


@dataclass(frozen=True)
class Section:
    """A heading's section, or the file-level section (``level`` 0, ``slug`` and ``title`` empty).

    ``start`` is the section's first line (its heading's first line); ``end`` its own last line, before the next
    heading; ``tree_end`` the last line of the section with its children. Both ends are inclusive, and ``end`` is
    ``start - 1`` for an empty file-level section. ``parent`` is the address of the enclosing section (the
    file-level section for a top heading) and ``None`` for the file-level section. ``own_text`` is the section's
    own lines as written, joined with ``\\n``.
    """

    address: str
    slug: str
    title: str
    level: int
    start: int
    end: int
    tree_end: int
    parent: str | None
    own_text: str
    own_hash: str
    tree_hash: str


@dataclass(frozen=True)
class Document:
    """One parsed file: its repository path, its lines and its sections in document order."""

    path: str
    lines: tuple[Line, ...]
    sections: tuple[Section, ...]

    def line(self, number: int) -> Line:
        """The line with the 1-based ``number``."""
        if not 1 <= number <= len(self.lines):
            raise IndexError(f"{self.path} has no line {number}")
        return self.lines[number - 1]

    def section_of(self, number: int) -> Section | None:
        """The innermost section whose own text holds line ``number``; ``None`` for a frontmatter line."""
        if self.line(number).frontmatter:
            return None
        for section in reversed(self.sections):
            if section.start <= number <= section.end:
                return section
        return None


# --- Normalising and hashing ----------------------------------------------------------------------------------------


def _indent(text: str) -> int:
    expanded = text.expandtabs(4)
    return len(expanded) - len(expanded.lstrip(" "))


def _starts_block(line: Line, text: str) -> bool:
    """Whether a non-fence, non-blank line starts a new unit rather than continuing a paragraph."""
    return bool(
        line.heading
        or line.table_row
        or line.comment
        or _ATX.match(text)
        or _THEMATIC.match(text)
        or _LIST_MARKER.match(text)
        or _QUOTE.match(text)
    )


def normalise(lines: Sequence[Line]) -> str:
    """The text of ``lines`` in the form that is hashed.

    Lines end in LF and lose their trailing whitespace. Runs of blank lines become one, and leading and trailing
    blank lines go. Outside a code fence, the lines of one paragraph (a list item's text, a block quote's text) are
    joined with one space and each run of whitespace becomes one space, so re-wrapping a paragraph keeps its hash.
    A line that starts a block (a heading, a list marker, a table row, a quote, a thematic break, an HTML comment)
    starts a new line of the result and keeps its indent. A fenced block keeps its lines as written, blank lines
    included, less their trailing whitespace.
    """
    units: list[str] = []
    joinable = False
    in_quote = False
    blank = False
    for line in lines:
        text = line.text.rstrip()
        if line.fence:
            units.append(text)
            joinable = in_quote = blank = False
            continue
        if not text.strip():
            if units and not blank:
                units.append("")
            joinable = in_quote = False
            blank = True
            continue
        blank = False
        starts = _starts_block(line, text)
        quote = _QUOTE.match(text)
        if in_quote and quote:
            rest = text.lstrip()[1:]
            if rest.strip() and not _starts_block(line, rest.lstrip()) and not line.table_row:
                units[-1] += " " + _WHITESPACE.sub(" ", rest.strip())
                continue
        if joinable and not starts:
            units[-1] += " " + _WHITESPACE.sub(" ", text.strip())
            continue
        stripped = text.lstrip()
        units.append(text[: len(text) - len(stripped)] + _WHITESPACE.sub(" ", stripped))
        underline = line.heading and _SETEXT.match(text) is not None
        joinable = not (line.table_row or underline or (line.heading and _ATX.match(text)))
        in_quote = quote is not None
    while units and units[-1] == "":
        units.pop()
    return "\n".join(units)


def _hash(lines: Sequence[Line]) -> str:
    return content_hash(normalise(lines))


# --- Parsing --------------------------------------------------------------------------------------------------------


@dataclass
class _Flags:
    frontmatter: bool = False
    fence: bool = False
    comment: bool = False
    heading: bool = False
    table_row: bool = False
    list_item: bool = False


@dataclass(frozen=True)
class _Heading:
    start: int  # 0-based index of the heading's first line
    level: int
    title: str


def _split(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.endswith("\n"):
        text = text[:-1]
    return text.split("\n") if text else []


def _frontmatter_end(lines: Sequence[str]) -> int:
    """The number of frontmatter lines (0 when the file has none)."""
    if not lines or lines[0].rstrip() != "---":
        return 0
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            return index + 1
    return 0


def _cells(row: str) -> int:
    body = row.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return len(re.split(r"(?<!\\)\|", body))


def _is_table_start(lines: Sequence[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    header, delimiter = lines[index], lines[index + 1]
    if "|" not in header or "|" not in delimiter or not _TABLE_DELIMITER.match(delimiter):
        return False
    return _cells(header) == _cells(delimiter)


def _atx_title(match: re.Match[str]) -> str:
    return _ATX_CLOSING.sub("", match.group(2) or "").strip()


class _Parser:
    """One pass over the lines: fences, comments, lists, tables, then headings."""

    def __init__(self, lines: Sequence[str]) -> None:
        self.lines = lines
        self.flags = [_Flags() for _ in lines]
        self.headings: list[_Heading] = []
        self.fence: tuple[str, int] | None = None  # the fence character and the opening run's length
        self.fence_in_list = False
        self.comment_in_list = False
        self.in_comment = False
        self.in_table = False
        self.list_indents: list[int] = []  # the content indents of the open list items, outermost first
        self.after_blank = False
        self.paragraph: int | None = None  # the first line of the open plain paragraph
        self.delimiter = -1  # the index of the open table's delimiter row

    def run(self, start: int) -> None:
        for index in range(start):
            self.flags[index].frontmatter = True
        for index in range(start, len(self.lines)):
            self.step(index)

    def _end_paragraph(self) -> None:
        self.paragraph = None

    def step(self, index: int) -> None:
        text = self.lines[index]
        flags = self.flags[index]
        if self.fence is not None:
            flags.fence = True
            flags.list_item = self.fence_in_list
            closing = _FENCE_CLOSE.match(text)
            if closing and closing.group(1)[0] == self.fence[0] and len(closing.group(1)) >= self.fence[1]:
                self.fence = None
            return
        if self.in_comment:
            flags.comment = True
            flags.list_item = self.comment_in_list
            if "-->" in text:
                self.in_comment = False
            return
        if not text.strip():
            self.after_blank = True
            self.in_table = False
            self._end_paragraph()
            return
        after_blank, self.after_blank = self.after_blank, False
        indent = _indent(text)
        setext = _SETEXT.match(text)
        if setext and self.paragraph is not None and not self.in_table:
            self._setext(index, setext.group(1)[0])
            return
        atx = _ATX.match(text)
        thematic = _THEMATIC.match(text)
        fence = _FENCE_OPEN.match(text)
        if fence and fence.group(1)[0] == "`" and "`" in fence.group(2):
            fence = None
        marker = None if thematic else self._marker(text)
        quote = _QUOTE.match(text)
        comment = _COMMENT_OPEN.match(text)
        block = bool(atx or thematic or fence or marker or quote or comment)

        in_list = self._list_membership(indent, marker, after_blank, block)
        flags.list_item = in_list

        if index == self.delimiter:
            flags.table_row = True
            return
        if self.in_table:
            if block:
                self.in_table = False
            else:
                flags.table_row = True
                return
        if fence:
            flags.fence = True
            self.fence = (fence.group(1)[0], len(fence.group(1)))
            self.fence_in_list = in_list
            self._end_paragraph()
            return
        if comment:
            flags.comment = True
            self.in_comment = "-->" not in text[text.index("<!--") + 4 :]
            self.comment_in_list = in_list
            self._end_paragraph()
            return
        if atx and not in_list:
            flags.heading = True
            self.headings.append(_Heading(index, len(atx.group(1)), _atx_title(atx)))
            self._end_paragraph()
            return
        if not block and _is_table_start(self.lines, index):
            flags.table_row = True
            self.in_table = True
            self.delimiter = index + 1
            self._end_paragraph()
            return
        if block or in_list:
            self._end_paragraph()
            return
        if self.paragraph is None and indent < 4:
            self.paragraph = index

    def _marker(self, text: str) -> re.Match[str] | None:
        """The line's list marker, if it starts a list item here (CommonMark's rules for the first item)."""
        marker = _LIST_MARKER.match(text)
        if marker is None or self.list_indents:
            return marker
        if _indent(marker.group(1)) >= 4:
            return None  # an indented code block or a paragraph's continuation
        if self.paragraph is not None:
            # A first item may interrupt a paragraph only if it is not empty and, when ordered, starts at 1.
            ordered = marker.group(2)[0].isdigit()
            if not marker.group(3) or (ordered and int(marker.group(2)[:-1]) != 1):
                return None
        return marker

    def _list_membership(self, indent: int, marker: re.Match[str] | None, after_blank: bool, block: bool) -> bool:
        """Update the open list items for a non-blank line and say whether the line belongs to one."""
        if marker is not None:
            marker_indent = _indent(marker.group(1))
            while self.list_indents and self.list_indents[-1] > marker_indent:
                self.list_indents.pop()
            width = len(marker.group(2)) + (len(marker.group(3).expandtabs(4)) if marker.group(3) else 1)
            self.list_indents.append(marker_indent + width)
            return True
        if not self.list_indents:
            return False
        if indent >= self.list_indents[0]:
            while self.list_indents and self.list_indents[-1] > indent:
                self.list_indents.pop()
            return True
        if not after_blank and not block:
            return True  # a lazy continuation line
        self.list_indents.clear()
        return False

    def _setext(self, index: int, char: str) -> None:
        start = self.paragraph
        assert start is not None
        for number in range(start, index + 1):
            self.flags[number].heading = True
        title = " ".join(self.lines[number].strip() for number in range(start, index))
        self.headings.append(_Heading(start, 1 if char == "=" else 2, title))
        self._end_paragraph()


def parse(path: str, text: str) -> Document:
    """Parse the Markdown ``text`` of the file at the repository ``path``."""
    raw = _split(text)
    body_start = _frontmatter_end(raw)
    parser = _Parser(raw)
    parser.run(body_start)
    lines = tuple(
        Line(
            number=index + 1,
            text=raw[index],
            frontmatter=flags.frontmatter,
            fence=flags.fence,
            comment=flags.comment,
            heading=flags.heading,
            table_row=flags.table_row,
            list_item=flags.list_item,
        )
        for index, flags in enumerate(parser.flags)
    )
    return Document(path=path, lines=lines, sections=_sections(path, lines, body_start, parser.headings))


def _section(
    lines: tuple[Line, ...],
    address: str,
    slug: str,
    heading: _Heading | None,
    start: int,
    end: int,
    tree_end: int,
    parent: str | None,
) -> Section:
    own = lines[start:end]
    return Section(
        address=address,
        slug=slug,
        title=heading.title if heading else "",
        level=heading.level if heading else 0,
        start=start + 1,
        end=end,
        tree_end=tree_end,
        parent=parent,
        own_text="\n".join(line.text for line in own),
        own_hash=_hash(own),
        tree_hash=_hash(lines[start:tree_end]),
    )


def _sections(path: str, lines: tuple[Line, ...], body_start: int, headings: Sequence[_Heading]) -> tuple[Section, ...]:
    total = len(lines)
    file_address = f"{path}#"
    first = headings[0].start if headings else total
    sections = [_section(lines, file_address, "", None, body_start, first, total, None)]
    slugger = Slugger()
    stack: list[tuple[int, str, str]] = []  # (level, slug, address) of the open headings
    for number, heading in enumerate(headings):
        own_end = headings[number + 1].start if number + 1 < len(headings) else total
        tree_end = next((later.start for later in headings[number + 1 :] if later.level <= heading.level), total)
        while stack and stack[-1][0] >= heading.level:
            stack.pop()
        parent = stack[-1][2] if stack else file_address
        slug = slugger.slug(heading.title)
        address = f"{path}#" + "/".join([entry[1] for entry in stack] + [slug])
        stack.append((heading.level, slug, address))
        sections.append(_section(lines, address, slug, heading, heading.start, own_end, tree_end, parent))
    return tuple(sections)
