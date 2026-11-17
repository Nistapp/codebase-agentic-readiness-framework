# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The completeness sweep, diff mode: which normative items of an old state vanished from a new one (``--diff``).

:func:`compare` takes the sweep's items at the old state and at the new state and sorts each old item into one of
four groups:

- **unchanged**: an item at the new state has the same normalised text at the same path and section address;
- **moved**: an item at the new state has the same normalised text, but only at another path or address. A moved
  item is counted, not listed;
- **path re-point**: no item has the same text, but one has the same text once every path token is masked
  (:func:`mask_paths`). The item's only change is a path or a file name, so it is listed apart, with that item;
- **vanished**: none of the above. The item is listed with its closest items at the new state.

Normalised text (:func:`normalise`) is the item's text with each run of whitespace turned into one space, trimmed.

**Closest items.** The ratio of an old item and a new item is ``difflib.SequenceMatcher(None, new, old).ratio()``
on their normalised texts. The closest items are the :data:`CLOSEST` new items with the highest ratio, highest
first; a tie goes to the lower path, then the lower address, then the lower text. A path re-point's item is the
closest one among those with the same masked text.

**Path tokens.** A token is a run of word characters, ``.``, ``/``, ``#``, ``~`` and ``-`` that ends in a word
character or ``/``. It is a path token when it holds a ``/`` and a word character (``audit/SKILL.md``,
``../guide.md#steps``, ``templates/``), or ends in a ``.md`` or ``.py`` name, with an optional ``#anchor``
(``SKILL.md``, ``recipe_lint.py``). :func:`mask_paths` replaces each path token with :data:`PATH_MARK`.

**Restricting the paths.** :func:`restrict` keeps the files that equal, or lie under, one of a list of paths. The
command line's ``--paths`` uses it on both sides, in place of the sweep scope, so a path that exists at one side
only (an old layout such as ``brownfield-recipes/...``) still works.

The output (:func:`to_json`, :func:`to_text`) is deterministic: the vanished and re-pointed items in the old sweep's
order (path, address, document order), ratios rounded to four places, no timestamp, no absolute path and no line
number. This module imports nothing outside the standard library and this package.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable, Sequence

from .sweep import Item

__all__ = [
    "CLOSEST",
    "DIFF_FORMAT",
    "PATH_MARK",
    "DiffReport",
    "Match",
    "Repoint",
    "Vanished",
    "compare",
    "mask_paths",
    "normalise",
    "restrict",
    "to_json",
    "to_text",
]

CLOSEST = 3
DIFF_FORMAT = 1
PATH_MARK = "<path>"

_WHITESPACE = re.compile(r"\s+")
_TOKEN = re.compile(r"[\w./#~-]*[\w/]")
_WORD = re.compile(r"\w")
_FILE_NAME = re.compile(r"\.(?:md|py)(?:#[\w-]*)?$")


# --- The data -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Match:
    """An item at the new state and its ratio against an old item."""

    item: Item
    ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.item.address,
            "kind": self.item.kind,
            "path": self.item.path,
            "ratio": round(self.ratio, 4),
            "text": self.item.text,
        }


@dataclass(frozen=True)
class Vanished:
    """An old item with no exact match at the new state, and its closest items there."""

    item: Item
    closest: tuple[Match, ...]


@dataclass(frozen=True)
class Repoint:
    """An old item whose only change is a path or a file name, and the new item it became."""

    item: Item
    target: Match


@dataclass(frozen=True)
class DiffReport:
    """The comparison of two sweeps: the listed items and the count of each group."""

    vanished: tuple[Vanished, ...]
    repointed: tuple[Repoint, ...]
    old_items: int
    new_items: int
    unchanged: int
    moved: int

    def counts(self) -> dict[str, int]:
        return {
            "moved": self.moved,
            "new_items": self.new_items,
            "old_items": self.old_items,
            "path_repoint": len(self.repointed),
            "unchanged": self.unchanged,
            "vanished": len(self.vanished),
        }


# --- Texts and paths ------------------------------------------------------------------------------------------------


def normalise(text: str) -> str:
    """``text`` with each run of whitespace turned into one space, trimmed."""
    return _WHITESPACE.sub(" ", text).strip()


def _is_path(token: str) -> bool:
    return ("/" in token and _WORD.search(token) is not None) or _FILE_NAME.search(token) is not None


def mask_paths(text: str) -> str:
    """The normalised ``text`` with each path token replaced by :data:`PATH_MARK`."""
    return _TOKEN.sub(lambda found: PATH_MARK if _is_path(found.group()) else found.group(), normalise(text))


def _under(path: str, prefix: str) -> bool:
    prefix = prefix.rstrip("/")
    return bool(prefix) and (path == prefix or path.startswith(prefix + "/"))


def restrict(files: Iterable[str], paths: Sequence[str]) -> list[str]:
    """The ``files`` that equal or lie under one of ``paths``, sorted."""
    return sorted({file for file in files if any(_under(file, path) for path in paths)})


# --- The comparison -------------------------------------------------------------------------------------------------


def _order(item: Item) -> tuple[str, str, str]:
    return (item.path, item.address, item.text)


def _closest(text: str, candidates: Sequence[tuple[str, Item]], count: int) -> list[Match]:
    """The ``count`` candidates closest to ``text``, highest ratio first, ties by path, address and text."""
    matcher = SequenceMatcher(None)
    matcher.set_seq2(text)
    best: list[tuple[tuple[float, str, str, str], Match]] = []
    for candidate_text, candidate in candidates:
        matcher.set_seq1(candidate_text)
        if len(best) == count:
            floor = -best[-1][0][0]
            # Both bounds are at least the ratio; a candidate that only ties the floor may still win on its path.
            if matcher.real_quick_ratio() < floor or matcher.quick_ratio() < floor:
                continue
        ratio = matcher.ratio()
        key = (-ratio, *_order(candidate))
        if len(best) == count and key >= best[-1][0]:
            continue
        best.append((key, Match(item=candidate, ratio=ratio)))
        best.sort(key=lambda entry: entry[0])
        del best[count:]
    return [match for _key, match in best]


def compare(old: Sequence[Item], new: Sequence[Item], *, closest: int = CLOSEST) -> DiffReport:
    """Sort each ``old`` item into unchanged, moved, path re-point or vanished, against the ``new`` items."""
    candidates = sorted(((normalise(item.text), item) for item in new), key=lambda entry: _order(entry[1]))
    places: dict[str, set[tuple[str, str]]] = {}
    by_mask: dict[str, list[tuple[str, Item]]] = {}
    for text, item in candidates:
        places.setdefault(text, set()).add((item.path, item.address))
        by_mask.setdefault(mask_paths(text), []).append((text, item))
    unchanged = moved = 0
    vanished: list[Vanished] = []
    repointed: list[Repoint] = []
    for item in old:
        text = normalise(item.text)
        found = places.get(text)
        if found is not None:
            if (item.path, item.address) in found:
                unchanged += 1
            else:
                moved += 1
            continue
        same_mask = by_mask.get(mask_paths(text))
        if same_mask:
            repointed.append(Repoint(item=item, target=_closest(text, same_mask, 1)[0]))
            continue
        vanished.append(Vanished(item=item, closest=tuple(_closest(text, candidates, closest))))
    return DiffReport(
        vanished=tuple(vanished),
        repointed=tuple(repointed),
        old_items=len(old),
        new_items=len(new),
        unchanged=unchanged,
        moved=moved,
    )


# --- Output ---------------------------------------------------------------------------------------------------------


def to_json(
    report: DiffReport,
    *,
    old: str,
    new: str | None,
    selection: str,
    paths: Sequence[str] | None = None,
) -> str:
    """The comparison as deterministic JSON: sorted keys, two-space indent, a final newline.

    ``old`` is the old git ref; ``new`` the new one, ``None`` for the working tree. ``paths`` is the ``--paths``
    list, ``None`` when the sweep scope was used.
    """
    data = {
        "counts": report.counts(),
        "format": DIFF_FORMAT,
        "new": new,
        "old": old,
        "path_repoint": [{**entry.item.to_dict(), "target": entry.target.to_dict()} for entry in report.repointed],
        "paths": None if paths is None else list(paths),
        "triggers": selection,
        "vanished": [
            {**entry.item.to_dict(), "closest": [match.to_dict() for match in entry.closest]}
            for entry in report.vanished
        ],
    }
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _one_line(text: str) -> str:
    return text.replace("\n", " ; ")


def _block(item: Item) -> list[str]:
    triggers = ", ".join(item.triggers) if item.triggers else "-"
    body = [f"  {line}" for line in item.text.split("\n")]
    return [item.address, f"  kind: {item.kind}", f"  triggers: {triggers}", *body]


def to_text(report: DiffReport, *, old: str, new: str | None) -> str:
    """The comparison as text: the vanished items, the path re-points, then the count of each group."""
    target = new if new is not None else "the working tree"
    parts: list[str] = [f"# Vanished from {old} to {target}: {len(report.vanished)}\n"]
    for entry in report.vanished:
        lines = _block(entry.item)
        lines.append("  closest:")
        lines.extend(
            f"    {match.ratio:.4f}  {match.item.address}: {_one_line(match.item.text)}" for match in entry.closest
        )
        parts.append("\n".join(lines) + "\n")
    parts.append(f"# Path re-point: {len(report.repointed)}\n")
    for repoint in report.repointed:
        lines = _block(repoint.item)
        lines.append(f"  now: {repoint.target.item.address}: {_one_line(repoint.target.item.text)}")
        parts.append("\n".join(lines) + "\n")
    counts = report.counts()
    rows = [
        ("items at the old state", counts["old_items"]),
        ("items at the new state", counts["new_items"]),
        ("unchanged", counts["unchanged"]),
        ("moved verbatim", counts["moved"]),
        ("path re-point", counts["path_repoint"]),
        ("vanished", counts["vanished"]),
    ]
    parts.append("# Counts\n" + "".join(f"{count:6d}  {name}\n" for name, count in rows))
    return "\n".join(parts)
