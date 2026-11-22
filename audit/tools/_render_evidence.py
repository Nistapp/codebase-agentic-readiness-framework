# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Evidence and search text of the report renderer, from one piece of evidence to one table cell.

Private to ``render_report.py``. Every function is pure.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from _render_terms import BR, EVIDENCE_IN_CELL
from _render_text import code, count, fenced, text


# --- Evidence ---------------------------------------------------------------------------------------------------------


def captured(item: Mapping[str, Any]) -> str:
    if item["captured_by"] == "tool":
        return f"captured by tool {code(item['tool'])} {text(item['tool_version'])}"
    return "captured by agent"


def evidence_lines(items: Sequence[Mapping[str, Any]]) -> list[str]:
    """One list item for each piece of evidence, with its quote or output in a fenced block under it."""
    lines: list[str] = []
    for item in items:
        kind = item["kind"]
        extra: list[str] = []
        if kind == "file":
            where = item["path"] + (f":{item['lines']}" if item.get("lines") else "")
            head = code(where)
            if item.get("note"):
                head += f" — {text(item['note'])}"
            tail = item.get("quote", "")
        elif kind == "command":
            head = f"Command {code(item['command'])}"
            if item.get("exit_code") is not None:
                extra.append(f"exit {item['exit_code']}")
            if item.get("timed_out"):
                extra.append("timed out")
            if item.get("duration_s") is not None:
                extra.append(f"{item['duration_s']:g} s")
            if item.get("redactions"):
                extra.append(count(item["redactions"], "redaction"))
            if extra:
                head += f" ({', '.join(extra)})"
            tail = item.get("output_tail", "")
        else:
            head = f"Index query {code(item['query'])} through {code(item['index_tool'])}"
            if item.get("result_summary"):
                head += f": {text(item['result_summary'])}"
            tail = item.get("quote", "")
        lines.append(f"- {head} · {captured(item)}")
        lines += fenced(tail, indent="  ")
    return lines


def search_text(search: Mapping[str, Any]) -> str:
    hits = count(search["hits"], "hit") if search["hits"] else "no hits"
    return f"`{search['tool']}` for {code(search['pattern'])} in {code(search['scope'])}: {hits}"


def evidence_item_text(item: Mapping[str, Any]) -> str:
    """One piece of evidence on one line, for a table cell. A quote or command output is left to "Evidence in full"."""
    notes: list[str] = []
    if item["kind"] == "file":
        head = code(item["path"] + (f":{item['lines']}" if item.get("lines") else ""))
        if item.get("note"):
            notes.append(text(item["note"]))
        if item.get("quote"):
            notes.append("quote in Evidence in full")
    elif item["kind"] == "command":
        head = f"command {code(item['command'])}"
        if item.get("exit_code") is not None:
            notes.append(f"exit {item['exit_code']}")
        if item.get("timed_out"):
            notes.append("timed out")
        if item.get("duration_s") is not None:
            notes.append(f"{item['duration_s']:g} s")
        if item.get("redactions"):
            notes.append(count(item["redactions"], "redaction"))
        if item.get("output_tail"):
            notes.append("output in Evidence in full")
    else:
        head = f"{code(item['query'])} through {code(item['index_tool'])}"
        if item.get("result_summary"):
            notes.append(text(item["result_summary"]))
    return head + (f" ({'; '.join(notes)})" if notes else "")


def capped(lines: Sequence[str], total: int) -> list[str]:
    """The first `EVIDENCE_IN_CELL` lines, and a line that says how many more the JSON report holds."""
    shown = list(lines[:EVIDENCE_IN_CELL])
    if total > EVIDENCE_IN_CELL:
        shown.append(f"and {total - EVIDENCE_IN_CELL} more, in the JSON report")
    return shown


def evidence_cell(
    items: Sequence[Mapping[str, Any]], searches: Sequence[Mapping[str, Any]], engine: Mapping[str, Any] | None
) -> str:
    """The evidence and searches of one row, grouped by who captured them, one per line. Empty when there are none.

    A tool's name and version are named only when they are not the engine's, which the provenance already names.
    """
    expected = f"{engine['name']} {engine['version']}" if engine else None
    lines: list[str] = []
    for who in ("tool", "agent"):
        mine = [item for item in items if item["captured_by"] == who]
        if not mine:
            continue
        identity = ""
        if who == "tool":
            names = sorted({f"{item['tool']} {item['tool_version']}" for item in mine})
            if names != [expected]:
                identity = f" ({', '.join(code(name) for name in names)})"
        shown = capped([evidence_item_text(item) for item in mine], len(mine))
        shown[0] = f"**{who}**{identity} {shown[0]}"
        lines += shown
    if searches:
        shown = capped([search_text(search) for search in searches], len(searches))
        shown[0] = f"**searches** {shown[0]}"
        lines += shown
    return BR.join(lines)
