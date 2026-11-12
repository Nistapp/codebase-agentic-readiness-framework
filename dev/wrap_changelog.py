# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Wrap the lines of ``CHANGELOG.md`` that markdownlint's line-length rule (MD013) refuses and cannot fix.

    wrap_changelog.py [FILE]   rewrite FILE (default ``CHANGELOG.md``) in place

release-please copies a ``BREAKING CHANGE:`` footer into the changelog as one bullet, often several hundred characters
long. ``markdownlint --fix`` does not wrap lines, so the release pull request failed the ``docs`` job. ``make
changelog-fix`` runs this script before markdownlint.

A line is wrapped only when MD013 would refuse it, as this repository configures the rule (``.markdownlint-cli2.jsonc``:
120 columns, not strict): it is longer than :data:`WIDTH` and has whitespace after column :data:`WIDTH`. A bullet ends
in a long link and has no space after column 120, so the rule accepts it and it stays as written. A bullet (``-`` or
``*``) wraps with its continuation lines indented by two spaces; a paragraph line wraps flush. Headings, tables, block
quotes, HTML and fenced code are never touched. Words and links are never split. Running it twice changes nothing.

Exit 0 when the file was read and written (changed or not), 2 when it cannot be read. Standard library only.
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path
from typing import Sequence

#: The line length of MD013 in ``.markdownlint-cli2.jsonc``.
WIDTH = 120

BULLET = re.compile(r"^(?P<indent> *)(?P<marker>[-*] )(?P<text>\S.*)$")
FENCE = re.compile(r"^ *(```|~~~)")
UNTOUCHED = ("#", "|", ">", "<")
#: A word that would make a continuation line a new block: a list marker, an ordered-list number, a heading, a quote,
#: a table row or a thematic break.
STARTS_BLOCK = re.compile(r"^(?:[-*+=]+|[0-9]+[.)]|#+|>|\|)$")


def refused(line: str) -> bool:
    """True when MD013 (120 columns, not strict) refuses ``line``: too long, with whitespace after the limit."""
    return len(line) > WIDTH and re.search(r"\s", line[WIDTH:]) is not None


def wrap_line(line: str) -> list[str]:
    """``line`` as one or more lines of at most :data:`WIDTH` columns, as far as unbreakable words allow."""
    bullet = BULLET.match(line)
    if bullet:
        first = bullet.group("indent") + bullet.group("marker")
        rest = bullet.group("indent") + " " * len(bullet.group("marker"))
        text = bullet.group("text")
    else:
        first = rest = " " * (len(line) - len(line.lstrip(" ")))
        text = line.strip()
    lines = textwrap.wrap(
        text,
        width=WIDTH,
        initial_indent=first,
        subsequent_indent=rest,
        break_long_words=False,
        break_on_hyphens=False,
    )
    # A continuation line must not start a new block: pull such a first word back onto the line before, even when
    # that line then runs past WIDTH.
    fixed = lines[:1]
    for line in lines[1:]:
        word, _, remainder = line.strip().partition(" ")
        while STARTS_BLOCK.match(word) and word:
            fixed[-1] += " " + word
            word, _, remainder = remainder.partition(" ")
        if word:
            fixed.append(rest + " ".join(part for part in (word, remainder) if part))
    return fixed


def wrap(text: str) -> str:
    """``text`` with each line that MD013 refuses wrapped; every other line kept byte for byte."""
    return wrap_counted(text)[0]


def wrap_counted(text: str) -> tuple[str, int]:
    """:func:`wrap`, and the number of lines it wrapped."""
    out: list[str] = []
    wrapped = 0
    in_fence = False
    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or line.lstrip().startswith(UNTOUCHED) or not refused(line):
            out.append(line)
            continue
        out.extend(wrap_line(line))
        wrapped += 1
    return "\n".join(out), wrapped


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        print("usage: wrap_changelog.py [FILE]", file=sys.stderr)
        return 2
    path = Path(args[0] if args else "CHANGELOG.md")
    try:
        before = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"wrap_changelog: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    after, wrapped = wrap_counted(before)
    if after != before:
        path.write_text(after, encoding="utf-8")
    print(f"wrap_changelog: {path}: {wrapped} line(s) wrapped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
