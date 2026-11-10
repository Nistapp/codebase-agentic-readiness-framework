# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Check Markdown prose against the plain-language rules of the style guide; optionally fail above a count.

    docs_prose_check.py [--format text|github] [--min-severity notice|warning] [--quiet]
                        [--max-issues N] [--diagram-dir DIR]... FILE...

This is the template that the implement playbook ``establish-docs-contract`` copies into a target repository, only
when the owner names a licence for the copy. The copy's first line then carries that licence, never this one. The
rules match the audit check ``DOC-05`` and the framework's own ``dev/prose_check.py``. Three rules, each reported
as ``path:line: CODE severity: message``:

* ``PL001`` a sentence is longer than 25 words (a notice), longer than 40 words (a warning), or longer than 20 words
  in a numbered step (a warning);
* ``PL002`` a vague or padded word from :data:`VAGUE` (``simply``, ``in order to`` and the others), a warning;
* ``PL003`` an explanation or tutorial page (see :func:`needs_diagram`) has no Mermaid block, a warning.

Only prose is read: paragraphs, list items and blockquotes. Fenced code, tables, headings, HTML comments and inline
code spans are skipped. A region between ``<!-- prose-check off -->`` and ``<!-- prose-check on -->`` is skipped, for
a deliberate bad example. The last line is ``Summary: N issues in M files (W warnings, K notices)``.

Exit codes: 0 by default, whatever the count (advisory). With ``--max-issues N``, 1 when more than N issues are
shown, so the script works as a ratchet: run it with ``--max-issues 0`` on the pages held clean, and with the
baseline count on every page. Add ``--min-severity warning`` to count warnings only, as the playbook does: a
sentence of 26 to 40 words is often the clearest one. 2 when a file cannot be read.

``--diagram-dir`` names a folder whose pages need a diagram; give it once per folder. Without it, the folders are
:data:`DIAGRAM_DIRS`. Standard library only, Python 3.11 or newer. The sentence splitter is a heuristic: it splits at
``.``, ``!`` or ``?`` before a space and a capital letter, a digit, a code span or an opening bracket.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_WORDS = 25
MAX_WORDS_STEP = 20
# A sentence this long is hard to follow even for a patient reader, so it is a warning, not a notice.
MAX_WORDS_WARNING = 40

WARNING = "warning"
NOTICE = "notice"
SEVERITIES = (NOTICE, WARNING)

VAGUE = (
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

#: The folders whose pages need a diagram (the style guide's "Diagrams" section). Index pages are exempt.
DIAGRAM_DIRS: tuple[str, ...] = ("docs/explanation/", "docs/tutorials/")


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    code: str
    severity: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.code} {self.severity}: {self.message}"

    def github(self) -> str:
        """The issue as a GitHub Actions workflow command (an annotation on the file and line)."""
        message = self.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        path = self.path.replace("%", "%25").replace(",", "%2C").replace(":", "%3A")
        return f"::{self.severity} file={path},line={self.line},title={self.code}::{message}"


@dataclass
class _Block:
    line: int
    text: str
    step: bool


def needs_diagram(path: str, dirs: tuple[str, ...] = DIAGRAM_DIRS) -> bool:
    """True for a page under one of ``dirs`` (not an index ``README.md``)."""
    posix = PurePosixPath(path).as_posix()
    if PurePosixPath(posix).name == "README.md":
        return False
    return any(f"/{d.rstrip('/')}/" in f"/{posix}" for d in dirs)


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
    in_fence = False
    in_comment = False
    off = False
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


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_END.split(text) if s.strip()]


def check_text(path: str, content: str, diagram_dirs: tuple[str, ...] = DIAGRAM_DIRS) -> list[Issue]:
    """All issues in one file's text."""
    issues: list[Issue] = []
    blocks, has_mermaid = _blocks(content.splitlines())
    for block in blocks:
        prose = _clean(block.text)
        limit = MAX_WORDS_STEP if block.step else MAX_WORDS
        for sentence in _sentences(prose):
            words = sum(1 for token in sentence.split() if _WORD.search(token))
            if words > limit:
                kind = "step" if block.step else "sentence"
                severity = WARNING if block.step or words > MAX_WORDS_WARNING else NOTICE
                message = f"{kind} has {words} words (limit {limit})"
                issues.append(Issue(path, block.line, "PL001", severity, message))
        for match in _VAGUE_RE.finditer(prose):
            issues.append(Issue(path, block.line, "PL002", WARNING, f"vague word '{match.group(1)}'"))
    if needs_diagram(path, diagram_dirs) and not has_mermaid:
        message = "explanation or tutorial page without a Mermaid diagram"
        issues.append(Issue(path, 1, "PL003", WARNING, message))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("files", nargs="*", type=Path, help="Markdown files to check")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--format", choices=("text", "github"), default="text", help="issue format (default: text)")
    parser.add_argument(
        "--min-severity", choices=SEVERITIES, default=NOTICE, help="hide issues below this severity (default: notice)"
    )
    parser.add_argument(
        "--max-issues", type=int, default=None, metavar="N", help="exit 1 when more than N issues are shown"
    )
    parser.add_argument(
        "--diagram-dir",
        action="append",
        default=None,
        metavar="DIR",
        help="a folder whose pages need a diagram (repeat; default: docs/explanation/ and docs/tutorials/)",
    )
    args = parser.parse_args(argv)
    if args.max_issues is not None and args.max_issues < 0:
        parser.error("--max-issues must be 0 or more")
    dirs = tuple(args.diagram_dir) if args.diagram_dir else DIAGRAM_DIRS
    shown = SEVERITIES[SEVERITIES.index(args.min_severity) :]
    counts = dict.fromkeys(SEVERITIES, 0)
    for file in args.files:
        try:
            content = file.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"docs_prose_check: cannot read {file}: {exc}", file=sys.stderr)
            return 2
        issues = [i for i in check_text(file.as_posix(), content, dirs) if i.severity in shown]
        for issue in issues:
            counts[issue.severity] += 1
            if not args.quiet:
                print(issue.github() if args.format == "github" else issue)
    print(summary(counts, len(args.files)))
    total = sum(counts.values())
    if args.max_issues is not None and total > args.max_issues:
        print(f"docs_prose_check: {total} issues, more than the limit of {args.max_issues}", file=sys.stderr)
        return 1
    return 0


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def summary(counts: dict[str, int], files: int) -> str:
    """``Summary: N issues in M files (W warnings, K notices)``."""
    total = sum(counts.values())
    detail = ", ".join(_plural(counts[s], s) for s in (WARNING, NOTICE))
    return f"Summary: {_plural(total, 'issue')} in {_plural(files, 'file')} ({detail})"


if __name__ == "__main__":
    raise SystemExit(main())
