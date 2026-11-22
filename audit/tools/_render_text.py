# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Text helpers of the report renderer: untrusted input becomes safe Markdown.

Private to ``render_report.py``. Every function is pure.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence


# --- Text: untrusted input becomes safe Markdown -----------------------------------------------------------------

# Characters that always mean something in the middle of a line, and an underscore that is not between two letters or
# digits (inside a word it is plain text, but `__tests__` would be bold).
_SPECIAL = re.compile(r"[\\`*\[\]<|]|(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])")
_BLOCK_START = re.compile(r"^(?:([#>+=~-])|(\d+)([.)]))")
_BACKTICKS = re.compile(r"`+")


def clean(value: str) -> str:
    """`value` with line ends as `\\n` and each control or format character written out as `{U+XXXX}`.

    Newline and tab stay. A line or paragraph separator becomes a newline. The format characters include the ones that
    reorder or hide text (right-to-left override, zero-width space), which can make a path read as another path.
    """
    out: list[str] = []
    for char in value.replace("\r\n", "\n").replace("\r", "\n"):
        category = unicodedata.category(char)
        if char in ("\n", "\t"):
            out.append(char)
        elif category in ("Zl", "Zp"):
            out.append("\n")
        elif category in ("Cc", "Cf"):
            out.append(f"{{U+{ord(char):04X}}}")
        else:
            out.append(char)
    return "".join(out)


def flat(value: str) -> str:
    """`clean` text on one line, with each run of white space as one space."""
    return " ".join(clean(value).split())


def text(value: str) -> str:
    """Prose from the report, on one line, with every Markdown special character escaped."""
    return _SPECIAL.sub(lambda found: "\\" + found.group(0), flat(value))


def prose(value: str) -> str:
    """`text` for a paragraph that starts with the value: a first character that Markdown would read as a heading, a
    quote, a list item or a rule is escaped too."""
    escaped = text(value)
    return _BLOCK_START.sub(
        lambda found: f"\\{found.group(1)}" if found.group(1) else f"{found.group(2)}\\{found.group(3)}", escaped
    )


def delimiter(content: str, *, least: int = 1) -> str:
    """A run of backticks longer than any run in `content`, so that nothing inside can close the span or the fence."""
    longest = max((len(run) for run in _BACKTICKS.findall(content)), default=0)
    return "`" * max(least, longest + 1)


def code(value: str) -> str:
    """A code span for a path, a command or a name. An empty value is shown as a dash."""
    content = flat(value)
    if not content:
        return "—"
    mark = delimiter(content)
    pad = " " if content.startswith("`") or content.endswith("`") else ""
    return f"{mark}{pad}{content}{pad}{mark}"


def fenced(value: str, indent: str = "") -> list[str]:
    """A fenced block for a quote or an output tail, indented to sit inside a list item. Nothing if it is blank."""
    body = clean(value).rstrip("\n")
    if not body.strip():
        return []
    mark = delimiter(body, least=3)
    lines = [f"{indent}{mark}text"]
    lines += [f"{indent}{line}" if line else "" for line in body.split("\n")]
    lines.append(f"{indent}{mark}")
    return lines


def cell(markup: str) -> str:
    """A table cell: any `|` that is not already escaped is escaped, so that a value cannot add a column."""
    out: list[str] = []
    index = 0
    while index < len(markup):
        char = markup[index]
        if char == "\\":
            out.append(markup[index : index + 2])
            index += 2
            continue
        out.append("\\|" if char == "|" else char)
        index += 1
    return "".join(out)


ALIGNMENTS = {"left": "---", "center": ":---:", "right": "---:"}


def table(headers: Sequence[str], rows: Sequence[Sequence[str]], aligns: Sequence[str] | None = None) -> list[str]:
    """A GFM table. A cell is made safe by `cell`, so `<br>` in a value would be the renderer's own line break."""
    marks = [ALIGNMENTS[a] for a in aligns] if aligns else ["---"] * len(headers)
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(marks) + "|"]
    lines += ["| " + " | ".join(cell(item) for item in row) + " |" for row in rows]
    return lines


def blocks(*parts: Sequence[str]) -> list[str]:
    """The non-empty blocks of lines with one blank line between each pair."""
    lines: list[str] = []
    for part in parts:
        if part:
            if lines:
                lines.append("")
            lines.extend(part)
    return lines


def count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def joined(values: Sequence[str], empty: str = "—") -> str:
    return ", ".join(code(value) for value in values) if values else empty


def yes_no(flag: bool) -> str:
    return "yes" if flag else "no"


def score_text(score: float) -> str:
    """The score to two decimal places, half up. The report stores it to four places and the spec shows it to two."""
    return str(Decimal(repr(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
