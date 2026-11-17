# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The completeness sweep, report mode: every normative item of the in-scope Markdown files, as a checklist.

**Units.** One unit is a paragraph, a list item, a table row or a fenced command block. The lines of a paragraph or
a list item are joined, each run of whitespace becomes one space, and a list marker (``-``, ``*``, ``+``, ``1.``,
``1)``), a task box (``[ ]``, ``[x]``), a nested number (``4.2``, ``1.2.3.``) and a block-quote ``>`` are dropped
from the front. A blank line ends a unit. Headings, HTML comments, thematic breaks, the YAML frontmatter and a
table's header and delimiter rows are not units. A table row's text is its cells, trimmed and joined with ``" | "``.

Lines in a code fence are not prose: no trigger is looked for in them. A fence is a *command block* when its info
string starts with a shell tag (:data:`SHELL_TAGS`) or one of its lines starts with ``$``, ``make``, ``python3`` or
``git``. A command block is one normative item of kind ``command``, its text the fence's inner lines, each trimmed
and whitespace-normalised, joined with ``\\n``. Any other fence is skipped whole.

**Normative.** A unit is normative when one of these holds:

- it holds a trigger word of the selected groups (``sweep.triggers.group1`` and ``group2`` in the project config;
  ``--triggers group1`` selects the first group only). A trigger matches case-insensitively as a whole word: not
  inside a longer word and not joined to one by a hyphen, so ``first-run`` holds no ``first``. A trigger of two
  words matches across any run of whitespace;
- it holds a pattern trigger, in either selection: ``limit`` (a number with a unit or a limit word: ``500 lines``,
  ``25 characters``, ``90%``, ``up to 3``), ``exit-code`` (``exit 2``, ``exits 0``, ``exit code 1``) or
  ``path-write`` (one sentence holds a write verb, such as write, edit, change, create or delete, and a path: a
  code span with ``/`` or a file extension, or a bare path with a file extension);
- it is a command block;
- it is a body row of a table whose header names a tool or a command (:data:`_TOOL_HEADER`).

**Kinds.** Each item gets the first kind in this order whose rule holds; :data:`KINDS` holds the names:

1. ``prohibition``: never, do not, don't, may not, must not, nothing, only;
2. ``required-step``: must, required, requires, need, needs, always, each, every, shall, have to, has to;
3. ``ordering``: before, after, first;
4. ``stop-condition``: stop, stops, refuse, refuses, halt, abort;
5. ``threshold``: at most, at least, or the ``limit`` pattern;
6. ``output-format``: output, outputs, format, formats, formatted, print, prints, stdout, stderr, JSON;
7. ``command``: a command block (and a command block is always this kind, since its lines are not prose);
8. ``tool-contract``: a row of a tool or command table, or the ``exit-code`` pattern;
9. ``question``: ask or asks, then the user, the person, the maintainer, the owner, the operator or the human;
   or confirm with;
10. ``default``: default, defaults, by default, otherwise.

A normative item that no rule fits is a ``required-step``. Each item records its triggers: the trigger words found,
in their configured form, and the names of the pattern triggers, sorted.

**Output.** :func:`to_json` and :func:`to_text` sort the items by path and section address, keeping document order
within one section. The JSON has no timestamp, no absolute path and no line number; :attr:`Item.lines` is for
in-memory use only. This module imports nothing outside the standard library and this package.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .gitread import Tree
from .markdown import Document, Line, parse

__all__ = [
    "KINDS",
    "PATTERN_TRIGGERS",
    "SELECTIONS",
    "SHELL_TAGS",
    "Item",
    "Report",
    "items_of",
    "scope",
    "select_triggers",
    "summary",
    "sweep",
    "to_json",
    "to_text",
]

KINDS = (
    "prohibition",
    "required-step",
    "ordering",
    "stop-condition",
    "threshold",
    "output-format",
    "command",
    "tool-contract",
    "question",
    "default",
)
PATTERN_TRIGGERS = ("exit-code", "limit", "path-write")
SELECTIONS = ("group1", "all")
SHELL_TAGS = frozenset(
    {"bash", "console", "fish", "powershell", "ps1", "pwsh", "sh", "shell", "shell-session", "shellsession", "zsh"}
)
SWEEP_FORMAT = 1

_FENCE_OPEN = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*$")
_COMMAND_LINE = re.compile(r"^(?:\$|(?:make|python3|git)(?![\w-]))")
_LIST_MARKER = re.compile(r"^[ \t]*(?:[-*+]|\d{1,9}[.)])(?:[ \t]+|$)")
_TASK_BOX = re.compile(r"^\[[ xX]\](?:[ \t]+|$)")
_NESTED_NUMBER = re.compile(r"^\d+(?:\.\d+)+\.?(?:[ \t]+|$)")
_QUOTE = re.compile(r"^[ \t]{0,3}>[ \t]?")
_THEMATIC = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_TABLE_DELIMITER = re.compile(r"^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_WHITESPACE = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_TOOL_HEADER = re.compile(r"(?<![\w-])(?:tools?|commands?|scripts?|verbs?|cli)(?![\w-])", re.IGNORECASE)


def _words(*words: str) -> re.Pattern[str]:
    """A case-insensitive pattern for any of ``words``, each a whole word; a space matches any whitespace run."""
    alternatives = "|".join(r"\s+".join(re.escape(part) for part in word.split()) for word in words)
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.IGNORECASE)


_UNITS = (
    r"%|percent|lines?|characters?|chars?|words?|bytes?|[kmg]i?b|seconds?|minutes?|hours?|days?|ms|turns?|files?"
    r"|items?|times?|levels?|columns?|steps?|findings?|tokens?|commits?|rows?|entries|attempts?|retries|runs?"
    r"|sentences?|pages?|headings?"
)
_LIMIT = re.compile(
    rf"(?<![\w.])\d+(?:[.,]\d+)?[ \t]*(?:{_UNITS})(?![\w-])"
    r"|(?<![\w-])(?:up\s+to|no\s+more\s+than|more\s+than|fewer\s+than|less\s+than|maximum|minimum)\s+(?:of\s+)?\d+",
    re.IGNORECASE,
)
_EXIT_CODE = re.compile(
    r"(?<![\w-])exit(?:s|ed|ing)?(?:\s+with)?(?:\s+(?:code|status))?\s+\d+(?![\w-])",
    re.IGNORECASE,
)
_WRITE_VERB = _words(
    *("write", "writes", "writing", "written", "wrote", "edit", "edits", "edited", "editing", "change", "changes"),
    *("changed", "modify", "modifies", "modified", "create", "creates", "created", "delete", "deletes", "deleted"),
)
_PATH = re.compile(r"`[^`\s]*(?:/|\.[A-Za-z0-9]{1,6})[^`\s]*`|(?<![\w/.-])[\w.-]+/[\w./-]*\.[A-Za-z0-9]{1,6}(?!\w)")

#: The word rules of the kinds; ``threshold`` also holds on the ``limit`` pattern, and ``command`` and
#: ``tool-contract`` are rules on the unit (see :func:`_holds`).
_KIND_WORDS: dict[str, re.Pattern[str]] = {
    "prohibition": _words("never", "do not", "don't", "may not", "must not", "nothing", "only"),
    "required-step": _words(
        "must", "required", "requires", "need", "needs", "always", "each", "every", "shall", "have to", "has to"
    ),
    "ordering": _words("before", "after", "first"),
    "stop-condition": _words("stop", "stops", "refuse", "refuses", "halt", "abort"),
    "threshold": _words("at most", "at least"),
    "output-format": _words(
        "output", "outputs", "format", "formats", "formatted", "print", "prints", "stdout", "stderr", "json"
    ),
    "question": re.compile(
        r"(?<![\w-])(?:asks?\s+(?:the\s+)?(?:user|person|maintainer|owner|operator|human)|confirm\s+with)(?![\w-])",
        re.IGNORECASE,
    ),
    "default": _words("default", "defaults", "by default", "otherwise"),
}


# --- The data -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    """One normative item. ``lines`` are its 1-based line numbers, for in-memory use only (never in the output)."""

    path: str
    address: str
    kind: str
    triggers: tuple[str, ...]
    text: str
    lines: tuple[int, ...] = field(default=(), compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "kind": self.kind,
            "path": self.path,
            "text": self.text,
            "triggers": list(self.triggers),
        }


@dataclass(frozen=True)
class Report:
    """The sweep of a list of files: every normative item, and the item count of each file (0 included)."""

    items: tuple[Item, ...]
    counts: tuple[tuple[str, int], ...]


@dataclass
class _Unit:
    numbers: list[int]
    parts: list[str]
    command: bool = False
    tool_row: bool = False


# --- Triggers and kinds ---------------------------------------------------------------------------------------------


def select_triggers(config: Mapping[str, Any], selection: str) -> tuple[str, ...]:
    """The trigger words of ``selection`` (``group1`` or ``all``) from the project config's ``sweep.triggers``."""
    if selection not in SELECTIONS:
        raise ValueError(f"unknown trigger selection {selection!r}; use one of {', '.join(SELECTIONS)}")
    groups = config.get("sweep", {}).get("triggers", {})
    names = ("group1",) if selection == "group1" else ("group1", "group2")
    words: list[str] = []
    for name in names:
        group = groups.get(name)
        if not isinstance(group, list) or not all(isinstance(word, str) and word.strip() for word in group):
            raise ValueError(f"the config has no list of trigger words at sweep.triggers.{name}")
        words.extend(word for word in group if word not in words)
    return tuple(words)


def _triggers(text: str, words: Sequence[str]) -> tuple[str, ...]:
    found = {word for word in words if _words(word).search(text)}
    if _LIMIT.search(text):
        found.add("limit")
    if _EXIT_CODE.search(text):
        found.add("exit-code")
    if any(_WRITE_VERB.search(sentence) and _PATH.search(sentence) for sentence in _SENTENCE_END.split(text)):
        found.add("path-write")
    return tuple(sorted(found))


def _holds(kind: str, unit: _Unit, text: str) -> bool:
    if kind == "command":
        return unit.command
    if kind == "tool-contract":
        return unit.tool_row or _EXIT_CODE.search(text) is not None
    if kind == "threshold" and _LIMIT.search(text):
        return True
    return _KIND_WORDS[kind].search(text) is not None


def _kind(unit: _Unit, text: str) -> str:
    """The first kind of :data:`KINDS` whose rule holds; a command block is always ``command``."""
    if unit.command:
        return "command"
    return next((kind for kind in KINDS if _holds(kind, unit, text)), "required-step")


# --- Units ----------------------------------------------------------------------------------------------------------


def _strip_front(text: str) -> str:
    """Drop a list marker, a task box and a nested number from the front of a unit's first line."""
    text = _LIST_MARKER.sub("", text, count=1)
    text = _TASK_BOX.sub("", text, count=1)
    return _NESTED_NUMBER.sub("", text, count=1)


def _cells(row: str) -> str:
    body = row.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return " | ".join(_WHITESPACE.sub(" ", cell.strip()) for cell in _CELL_SPLIT.split(body))


def _fence_end(lines: Sequence[Line], start: int) -> int:
    """The index of the last line of the fence that opens at ``start``."""
    opening = _FENCE_OPEN.match(lines[start].text)
    char, length = (opening.group(1)[0], len(opening.group(1))) if opening else ("`", 3)
    index = start + 1
    while index < len(lines) and lines[index].fence:
        closing = _FENCE_CLOSE.match(lines[index].text)
        if closing and closing.group(1)[0] == char and len(closing.group(1)) >= length:
            return index
        index += 1
    return index - 1


def _command_block(lines: Sequence[Line], start: int, end: int) -> _Unit | None:
    opening = _FENCE_OPEN.match(lines[start].text)
    info = opening.group(2).strip().split() if opening else []
    tag = info[0].lower() if info else ""
    closed = end > start and _FENCE_CLOSE.match(lines[end].text) is not None
    inner = lines[start + 1 : end] if closed else lines[start + 1 : end + 1]  # an unclosed fence runs to the end
    texts = [_WHITESPACE.sub(" ", line.text.strip()) for line in inner]
    texts = [text for text in texts if text]
    if not texts:
        return None
    if tag not in SHELL_TAGS and not any(_COMMAND_LINE.match(text) for text in texts):
        return None
    return _Unit(numbers=[line.number for line in lines[start : end + 1]], parts=["\n".join(texts)], command=True)


def _units(document: Document) -> list[_Unit]:
    lines = document.lines
    units: list[_Unit] = []
    current: _Unit | None = None

    def flush() -> None:
        nonlocal current
        if current is not None and any(part.strip() for part in current.parts):
            units.append(current)
        current = None

    index = 0
    while index < len(lines):
        line = lines[index]
        text = line.text
        if line.fence:
            flush()
            end = _fence_end(lines, index)
            block = _command_block(lines, index, end)
            if block is not None:
                units.append(block)
            index = end + 1
            continue
        if line.table_row:
            flush()
            end = index
            while end + 1 < len(lines) and lines[end + 1].table_row and not lines[end + 1].fence:
                end += 1
            rows = lines[index : end + 1]
            has_header = len(rows) >= 2 and _TABLE_DELIMITER.match(rows[1].text) is not None
            tool_table = has_header and _TOOL_HEADER.search(rows[0].text) is not None
            for row in rows[2:] if has_header else rows:
                units.append(_Unit(numbers=[row.number], parts=[_cells(row.text)], tool_row=tool_table))
            index = end + 1
            continue
        index += 1
        if line.frontmatter or line.comment or line.heading or not text.strip() or _THEMATIC.match(text):
            flush()
            continue
        quote = _QUOTE.match(text)
        while quote:
            text = text[quote.end() :]
            quote = _QUOTE.match(text)
        if not text.strip():
            flush()
            continue
        if line.list_item and _LIST_MARKER.match(text):
            flush()
        if current is None:
            current = _Unit(numbers=[], parts=[])
            text = _strip_front(text) if line.list_item else _NESTED_NUMBER.sub("", text.lstrip(), count=1)
        current.numbers.append(line.number)
        current.parts.append(text.strip())
    flush()
    return units


def items_of(document: Document, triggers: Sequence[str]) -> list[Item]:
    """The normative items of one parsed file, in document order."""
    items: list[Item] = []
    for unit in _units(document):
        text = unit.parts[0] if unit.command else _WHITESPACE.sub(" ", " ".join(unit.parts)).strip()
        found: tuple[str, ...] = () if unit.command else _triggers(text, triggers)
        if not (found or unit.command or unit.tool_row):
            continue
        section = document.section_of(unit.numbers[0])
        address = section.address if section is not None else f"{document.path}#"
        items.append(
            Item(
                path=document.path,
                address=address,
                kind=_kind(unit, text),
                triggers=found,
                text=text,
                lines=tuple(unit.numbers),
            )
        )
    return items


# --- Scope and the sweep --------------------------------------------------------------------------------------------


def _under(path: str, prefix: str) -> bool:
    prefix = prefix.rstrip("/")
    return path == prefix or path.startswith(prefix + "/")


def scope(files: Iterable[str], config: Mapping[str, Any], bundle_sources: Sequence[str] = ()) -> list[str]:
    """The in-scope Markdown files among the tracked ``files``, sorted.

    A file is in scope when it is a Markdown file (a suffix that ``file_kinds`` maps to ``markdown``, else ``.md``)
    and lies at or under one of ``bundle_sources`` or of the config's ``sweep.paths``, or its name is one of
    ``sweep.file_names``; and it lies under none of ``exclude.skip`` and ``exclude.list_only``. A source that the
    files do not hold is skipped.
    """
    kinds = config.get("file_kinds", {})
    suffixes = tuple(sorted(suffix for suffix, kind in kinds.items() if kind == "markdown")) or (".md",)
    sweep_config = config.get("sweep", {})
    sources = [*bundle_sources, *sweep_config.get("paths", [])]
    names = set(sweep_config.get("file_names", []))
    exclude = config.get("exclude", {})
    excluded = [*exclude.get("skip", []), *exclude.get("list_only", [])]
    result: set[str] = set()
    for path in files:
        if not path.endswith(suffixes) or any(_under(path, prefix) for prefix in excluded):
            continue
        if path.rsplit("/", 1)[-1] in names or any(_under(path, source) for source in sources):
            result.add(path)
    return sorted(result)


def sweep(tree: Tree, paths: Sequence[str], triggers: Sequence[str]) -> Report:
    """Sweep each of ``paths`` in ``tree``. A path that the tree cannot read is skipped and not counted."""
    items: list[Item] = []
    counts: list[tuple[str, int]] = []
    for path in sorted(set(paths)):
        text = tree.read(path)
        if text is None:
            continue
        found = items_of(parse(path, text), triggers)
        items.extend(found)
        counts.append((path, len(found)))
    items.sort(key=lambda item: (item.path, item.address))
    return Report(items=tuple(items), counts=tuple(counts))


# --- Output ---------------------------------------------------------------------------------------------------------


def to_json(report: Report, *, selection: str, at: str | None = None) -> str:
    """The report as deterministic JSON: sorted keys, two-space indent, a final newline."""
    data = {
        "at": at,
        "counts": dict(report.counts),
        "format": SWEEP_FORMAT,
        "items": [item.to_dict() for item in report.items],
        "triggers": selection,
    }
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def to_text(report: Report) -> str:
    """The report as text: one block per item, a blank line between blocks."""
    blocks: list[str] = []
    for item in report.items:
        triggers = ", ".join(item.triggers) if item.triggers else "-"
        body = "\n".join(f"  {line}" for line in item.text.split("\n"))
        blocks.append(f"{item.address}\n  kind: {item.kind}\n  triggers: {triggers}\n{body}\n")
    return "\n".join(blocks)


def summary(report: Report) -> str:
    """The item count of each file and the total, for stderr."""
    lines = [f"{count:6d}  {path}" for path, count in report.counts]
    lines.append(f"{len(report.items):6d}  items in {len(report.counts)} files")
    return "\n".join(lines) + "\n"
