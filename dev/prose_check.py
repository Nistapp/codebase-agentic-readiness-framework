# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Check Markdown prose against the plain-language rules in ``docs/COMMUNICATION_RULES.md``.

    prose_check.py [--format text|github] [--min-severity notice|warning] [--quiet] FILE...

The check is advisory: it never fails. Three rules, each reported as ``path:line: CODE severity: message``:

* ``PL001`` a sentence is longer than 25 words (a notice), longer than 40 words (a warning), or longer than 20 words
  in a numbered step (a warning);
* ``PL002`` a vague or padded word from :data:`VAGUE` (``simply``, ``in order to`` and the others), a warning;
* ``PL003`` an explanation or tutorial page (see :func:`needs_diagram`) has no Mermaid block, a warning.

A *warning* is worth fixing in the change that touches the text. A *notice* is a hint: fix it when it helps the
reader. ``--format github`` prints each issue as a GitHub Actions annotation (``::warning`` or ``::notice``), which
shows on the pull request without failing the job. ``--min-severity warning`` hides the notices.

Only prose is read: paragraphs, list items and blockquotes. Fenced code, tables, headings, HTML comments and inline
code spans are skipped. A region between ``<!-- prose-check off -->`` and ``<!-- prose-check on -->`` is skipped, for
a deliberate bad example. The last line is ``Summary: N issues in M files (W warnings, K notices)``. The exit code
is 0 whatever the count; it is 2 only when a file cannot be read.

Dev-only and standard library only. The sentence splitter is a heuristic: it splits at ``.``, ``!`` or ``?`` before a
space and a capital letter, a digit, a code span or an opening bracket.
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

# Explanation pages and tutorials must carry a diagram (STYLE_GUIDE.md section 3). Index pages are exempt.
_DIAGRAM_DIRS = (
    "docs/explanation/",
    "docs/tutorials/",
    "audit/engine/docs/architecture/user-overview/",
    "audit/engine/docs/architecture/contributor-deep-dive/",
)


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


def needs_diagram(path: str) -> bool:
    """True for an explanation page or a tutorial (not an index ``README.md``)."""
    posix = PurePosixPath(path).as_posix()
    if PurePosixPath(posix).name == "README.md":
        return False
    return any(f"/{d}" in f"/{posix}" for d in _DIAGRAM_DIRS)


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


def check_text(path: str, content: str) -> list[Issue]:
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
    if needs_diagram(path) and not has_mermaid:
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
    args = parser.parse_args(argv)
    shown = SEVERITIES[SEVERITIES.index(args.min_severity) :]
    counts = dict.fromkeys(SEVERITIES, 0)
    for file in args.files:
        try:
            content = file.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"prose_check: cannot read {file}: {exc}", file=sys.stderr)
            return 2
        issues = [i for i in check_text(file.as_posix(), content) if i.severity in shown]
        for issue in issues:
            counts[issue.severity] += 1
            if not args.quiet:
                print(issue.github() if args.format == "github" else issue)
    print(summary(counts, len(args.files)))
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
