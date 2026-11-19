# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Writes the ``reads`` part of ``dev/consistency-map.json`` from the engine's declarations (ADR 0012).

Each implemented engine check declares what it reads beside the registry, in ``audit/rules/reads.py`` under
``audit/engine/``. This script turns that table into the map's reads entries, in catalogue order. A check with no
engine code (``source`` ``agent``) keeps the entry the map already holds, since no code declares it.

``python3 dev/consistency_map_reads.py`` exits 0 when the map's reads equal the generated ones, and 1 with the
differing check IDs when they do not. ``--write`` rewrites the reads part in place and leaves every other part of the
map as it was. A catalogue check with neither an engine declaration nor an agent entry, or an engine declaration for
a check the catalogue does not list, is an error (exit 2).
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEV = Path(__file__).resolve().parent
REPO = DEV.parent
MAP_PATH = DEV / "consistency-map.json"
ENGINE = REPO / "audit" / "engine"
CATALOGUE = REPO / "audit" / "catalogue.json"


class ReadsError(Exception):
    """The catalogue, the engine declarations and the map's agent entries do not line up."""


def engine_declarations() -> dict[str, Any]:
    """The engine's ``READS`` table, keyed by check ID."""
    if str(ENGINE) not in sys.path:
        sys.path.insert(0, str(ENGINE))
    table: dict[str, Any] = importlib.import_module("audit.rules.reads").READS
    return table


def _where(place: Any) -> dict[str, Any]:
    """One declared place as a map ``where`` item.

    ``via`` only when an upstream step reads the place, ``case`` only when it is matched in lower case, and
    ``unexercised`` only when no fixture can reach it: most items stay two keys long.
    """
    item: dict[str, Any] = {"path": place.path, "scope": place.scope}
    if place.via is not None:
        item["via"] = place.via
    if place.case != "exact":
        item["case"] = place.case
    if place.unexercised is not None:
        item["unexercised"] = place.unexercised
    return item


def to_entry(check: str, declared: Any) -> dict[str, Any]:
    """One engine declaration as a map reads entry."""
    entry: dict[str, Any] = {
        "binding": declared.binding,
        "check": check,
        "source": "engine",
        "what": {"kind": declared.what.kind, **({"text": list(declared.what.text)} if declared.what.text else {})},
        "where": [_where(place) for place in declared.where],
    }
    if declared.constants:
        entry["constants"] = list(declared.constants)
    for field in ("named_by_text", "note", "threshold", "window"):
        value = getattr(declared, field)
        if value is not None:
            entry[field] = value
    return entry


def generated_reads(
    current: Sequence[dict[str, Any]], catalogue_ids: Sequence[str], declarations: dict[str, Any]
) -> list[dict[str, Any]]:
    """The reads part as the engine declares it, with the map's own entries for the agent checks."""
    unknown = sorted(set(declarations) - set(catalogue_ids))
    if unknown:
        raise ReadsError(f"engine declarations for checks the catalogue does not list: {', '.join(unknown)}")
    agent = {entry["check"]: entry for entry in current if entry.get("source") == "agent"}
    out: list[dict[str, Any]] = []
    missing: list[str] = []
    for check in catalogue_ids:
        if check in declarations:
            out.append(to_entry(check, declarations[check]))
        elif check in agent:
            out.append(agent[check])
        else:
            missing.append(check)
    if missing:
        raise ReadsError(f"no engine declaration and no agent entry for: {', '.join(missing)}")
    return out


def differing_checks(current: Sequence[dict[str, Any]], generated: Sequence[dict[str, Any]]) -> list[str]:
    """The check IDs whose entry differs, is missing or is extra, in generated order then current order."""
    have = {entry["check"]: entry for entry in current}
    want = {entry["check"]: entry for entry in generated}
    differ = [check for check in want if have.get(check) != want[check]]
    differ += [check for check in have if check not in want]
    if not differ and [entry["check"] for entry in current] != list(want):
        differ.append("(order)")
    return differ


def render(cmap: dict[str, Any]) -> str:
    """The map file's text, in the format the repository keeps it."""
    return json.dumps(cmap, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--map", type=Path, default=MAP_PATH, help="the map file (default: dev/consistency-map.json)")
    parser.add_argument("--write", action="store_true", help="rewrite the map's reads part from the engine")
    args = parser.parse_args(argv)
    cmap = json.loads(args.map.read_text(encoding="utf-8"))
    catalogue_ids = [check["id"] for check in json.loads(CATALOGUE.read_text(encoding="utf-8"))["checks"]]
    try:
        generated = generated_reads(cmap["reads"], catalogue_ids, engine_declarations())
    except ReadsError as exc:
        print(f"consistency_map_reads.py: {exc}", file=sys.stderr)
        return 2
    differ = differing_checks(cmap["reads"], generated)
    if args.write:
        if differ:
            args.map.write_text(render({**cmap, "reads": generated}), encoding="utf-8")
        print(f"consistency_map_reads.py: {len(differ)} reads entries rewritten")
        return 0
    if differ:
        print(
            "consistency_map_reads.py: the map's reads differ from the engine's declarations for "
            f"{', '.join(differ)}; run python3 dev/consistency_map_reads.py --write",
            file=sys.stderr,
        )
        return 1
    print(f"consistency_map_reads.py: {len(generated)} reads entries match the engine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
