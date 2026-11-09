# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Plain-language measures of Markdown prose, for `DOC-05`.

The engine's own port of the three rules of the framework's dev-only prose check (`dev/prose_check.py`, ADR 0004 of
the framework): long sentences, vague words, and explanation or tutorial pages without a Mermaid diagram. The engine
may not import dev code, and it reads, never runs, so the rules are written again here. The same text gives the same
counts as that check: the tests hold the two in step on shared cases.

Only prose is read: paragraphs, list items and blockquotes. Fenced code, tables, headings, HTML comments and inline
code spans are skipped, and so is a region between ``<!-- prose-check off -->`` and ``<!-- prose-check on -->``.

Deliberate limits, recorded rather than hidden. The sentence splitter is a heuristic: it splits at ``.``, ``!`` or
``?`` before a space and a capital letter, a digit, a code span or an opening bracket. The rules are for English, so
:func:`english_share` measures how much of the prose is common English function words; the check reports ``UNKNOWN``
below :data:`ENGLISH_MIN_SHARE` rather than judge text in another language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

#: A sentence longer than this is long; in a numbered step the limit is lower.
MAX_WORDS = 25
MAX_WORDS_STEP = 20

VAGUE: tuple[str, ...] = (
    "simply",
    "just",
    "obviously",
    "clearly",
    "basically",
    "easily",
    "utilize",
    "utilise",
    "leverage",
    "in order to",
    "and/or",
    "etc",
)
_VAGUE_RE = re.compile(r"(?<![\w/-])(" + "|".join(re.escape(w) for w in VAGUE) + r")(?![\w/-])", re.IGNORECASE)

#: Common English function words. In English prose they are about half of all words; in another language, few.
ENGLISH_WORDS = frozenset(
    "a an the and or but if of to in on at by for from with as is are was were be been it its this that these those "
    "not no do does can will must should may you we they he she i your our their which who what when where how".split()
)
#: Below this share of function words, the prose is not taken as English.
ENGLISH_MIN_SHARE = 0.2

#: Explanation pages and tutorials carry a diagram (the framework's style guide, § Diagrams). Index pages are exempt.
DIAGRAM_DIRS: tuple[str, ...] = ("docs/explanation/", "docs/tutorials/")

_FENCE = re.compile(r"^\s*(```|~~~)")
_MERMAID = re.compile(r"^\s*(```|~~~)\s*mermaid\b")
_OFF = "<!-- prose-check off -->"
_ON = "<!-- prose-check on -->"
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|(\d+)[.)])\s+")
_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_REF_LINK = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
_URL = re.compile(r"<?https?://\S+>?")
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_ALERT = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*")
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9`(\[\"*_])")
_WORD = re.compile(r"[A-Za-z0-9]")
_LETTERS = re.compile(r"[^\W\d_]+")


@dataclass
class _Block:
    line: int
    text: str
    step: bool


@dataclass
class ProseCounts:
    """What one or more pages hold: sentences, words, long sentences, vague words and diagrams."""

    sentences: int = 0
    words: int = 0
    long_sentences: int = 0
    vague_words: int = 0
    function_words: int = 0
    letter_words: int = 0
    #: ``(path, line)`` of each long sentence and each vague word, in reading order.
    long_at: list[tuple[str, int]] = field(default_factory=list)
    vague_at: list[tuple[str, int, str]] = field(default_factory=list)

    def add(self, other: ProseCounts) -> None:
        self.sentences += other.sentences
        self.words += other.words
        self.long_sentences += other.long_sentences
        self.vague_words += other.vague_words
        self.function_words += other.function_words
        self.letter_words += other.letter_words
        self.long_at.extend(other.long_at)
        self.vague_at.extend(other.vague_at)


def needs_diagram(path: str) -> bool:
    """True for an explanation page or a tutorial under `docs/` (not an index ``README.md`` or ``index.md``)."""
    posix = PurePosixPath(path)
    if posix.name.lower() in ("readme.md", "index.md"):
        return False
    return any(path.startswith(d) for d in DIAGRAM_DIRS)


def _clean(text: str) -> str:
    """Prose without markup: a code span or a URL counts as one word, a link as its text."""
    text = _CODE_SPAN.sub(" CODE ", text)
    text = _IMAGE.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    text = _REF_LINK.sub(r"\1", text)
    text = _URL.sub(" URL ", text)
    text = _HTML_TAG.sub(" ", text)
    return text.replace("**", "").replace("__", "")


def _blocks(lines: list[str]) -> tuple[list[_Block], bool]:
    """Prose blocks (paragraphs, list items, blockquote paragraphs) and whether a Mermaid block exists."""
    blocks: list[_Block] = []
    has_mermaid = False
    in_fence = in_comment = off = False
    current: _Block | None = None

    def close() -> None:
        nonlocal current
        if current is not None and current.text.strip():
            blocks.append(current)
        current = None

    for number, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if _FENCE.match(line):
            if not in_fence and _MERMAID.match(line):
                has_mermaid = True
            in_fence = not in_fence
            close()
            continue
        if in_fence:
            continue
        if stripped == _OFF:
            off = True
            close()
            continue
        if stripped == _ON:
            off = False
            continue
        if off:
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            close()
            continue
        quote = False
        while stripped.startswith(">"):
            quote = True
            stripped = stripped[1:].strip()
        if quote:
            stripped = _ALERT.sub("", stripped)
        if not stripped or stripped.startswith(("#", "|")) or re.fullmatch(r"[-*_=\s]{3,}", stripped):
            close()
            continue
        item = _LIST_ITEM.match(stripped)
        if item:
            close()
            current = _Block(number, stripped[item.end() :], step=item.group(1) is not None)
            continue
        if current is None:
            current = _Block(number, stripped, step=False)
        else:
            current.text += " " + stripped
    close()
    return blocks, has_mermaid


def measure(path: str, content: str) -> tuple[ProseCounts, bool]:
    """The prose counts of one page, and whether it has a Mermaid block."""
    counts = ProseCounts()
    blocks, has_mermaid = _blocks(content.splitlines())
    for block in blocks:
        prose = _clean(block.text)
        limit = MAX_WORDS_STEP if block.step else MAX_WORDS
        for sentence in (s for s in _SENTENCE_END.split(prose) if s.strip()):
            words = sum(1 for token in sentence.split() if _WORD.search(token))
            if not words:
                continue
            counts.sentences += 1
            counts.words += words
            if words > limit:
                counts.long_sentences += 1
                counts.long_at.append((path, block.line))
        for match in _VAGUE_RE.finditer(prose):
            counts.vague_words += 1
            counts.vague_at.append((path, block.line, match.group(1).lower()))
        tokens = [t.lower() for t in _LETTERS.findall(prose.replace("CODE", " ").replace("URL", " "))]
        counts.letter_words += len(tokens)
        counts.function_words += sum(1 for t in tokens if t in ENGLISH_WORDS)
    return counts, has_mermaid


def english_share(counts: ProseCounts) -> float:
    """The share of the prose's words that are common English function words (0 when there are none)."""
    return counts.function_words / counts.letter_words if counts.letter_words else 0.0
