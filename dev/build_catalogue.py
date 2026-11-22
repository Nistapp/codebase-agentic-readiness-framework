# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Build the check catalogue from the engine registry and the overlay, or check that it is current.

    build_catalogue.py --check   exit 1 when audit/catalogue.json differs from what the sources give
                                 (``make catalogue-check``; ``make masters-check`` runs it first)
    build_catalogue.py --write   rewrite audit/catalogue.json in place (``make update-catalogue``)

``audit/catalogue.json`` is generated; never edit it by hand. Its sources:

- The engine registry (``audit/engine/audit/rules/registry.py``): each engine check's id, title, phase, severity,
  scored flag and status, and the order of the checks. An engine check is ``automated`` and its ``engine_id`` is its
  own id.
- ``audit/catalogue-overlay.json``: what the engine does not know. ``catalogue_version``, and for each check its
  ``req_ids``, its ``playbooks`` and, for an engine check added after ruleset 2026-11-06.1, its ``since_ruleset``
  (history, so it stays hand-stated). An agent-only check has no engine check: its overlay entry states every field
  (``method`` is ``agent``), and it sits after the engine checks of its family with a lower number.
- ``audit/checks/NN-*.md``: each family's name, from the ``# <name> (`<FAMILY>`)`` heading.

The fingerprint is computed as ``catalogue.schema.json`` defines it. A change to it still needs a decision on the
``catalogue_version`` bump in the overlay (the rules are in the schema) and ``make update-secrets-baseline``.
Exit 2 when a source is malformed: an engine check with no overlay entry, an overlay entry with no engine check that
is not agent-only, an unknown field, or a family with no heading. The engine is imported in process, read-only; the
engine never imports this module. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = Path("audit/catalogue.json")
OVERLAY = Path("audit/catalogue-overlay.json")
CHECKS_DIR = Path("audit/checks")
ENGINE_DIR = Path("audit/engine")

FAMILY_HEADING = re.compile(r"^# (.+?) \(`([A-Z]{2,5})`\)", re.MULTILINE)
#: The fields an overlay entry of an engine check may hold; ``since_ruleset`` is optional.
ENGINE_FIELDS = ("req_ids", "since_ruleset", "playbooks")
#: The fields an overlay entry of an agent-only check holds, all required.
AGENT_FIELDS = ("title", "phase", "severity", "scored", "method", "status", "req_ids", "playbooks")
#: The catalogue's key order for one check (``catalogue.schema.json``).
CHECK_KEYS = (
    "id",
    "family",
    "title",
    "phase",
    "severity",
    "scored",
    "method",
    "status",
    "req_ids",
    "engine_id",
    "since_ruleset",
    "playbooks",
)

Check = dict[str, Any]


class SourceError(Exception):
    """A source the catalogue is built from is malformed."""


def engine_checks(root: Path = ROOT) -> list[Check]:
    """The engine's checks, in registry order, with the fields the catalogue shares with ``--list-checks``."""
    engine = str(root / ENGINE_DIR)
    if engine not in sys.path:
        sys.path.insert(0, engine)
    registry: Any = importlib.import_module("audit.rules.registry").REGISTRY
    return [
        {
            "id": spec.id,
            "pack": spec.pack,
            "title": spec.title,
            "tier": spec.tier,
            "phase": spec.phase,
            "severity": spec.severity.value,
            "scored": spec.scored,
            "status": spec.status,
        }
        for spec in registry
    ]


def read_family_names(root: Path) -> dict[str, str]:
    """Each family's name, from the ``# <name> (`<FAMILY>`)`` heading of its file in ``audit/checks/``."""
    names: dict[str, str] = {}
    for path in sorted((root / CHECKS_DIR).glob("[0-9][0-9]-*.md")):
        match = FAMILY_HEADING.search(path.read_text(encoding="utf-8"))
        if match:
            names[match.group(2)] = match.group(1)
    return names


def fingerprint(checks: Sequence[Check]) -> str:
    """First 16 hex digits of SHA-256 over one line per check, as ``catalogue.schema.json`` defines it."""
    lines = [
        "|".join(
            [
                c["id"],
                str(c["phase"]),
                c["severity"],
                str(int(c["scored"])),
                c["method"],
                ",".join(sorted(c["req_ids"])),
                c["engine_id"] or "",
            ]
        )
        for c in checks
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def _number(check_id: str) -> int:
    return int(check_id.split("-")[1])


def _ordered(entry: Check) -> Check:
    return {key: entry[key] for key in CHECK_KEYS if key in entry}


def build(overlay: dict[str, Any], engine: Sequence[Check], family_names: dict[str, str]) -> dict[str, Any]:
    """The catalogue the sources give, as a dict in the committed key order."""
    entries: dict[str, Any] = overlay.get("checks", {})
    if not isinstance(entries, dict):
        raise SourceError("the overlay's checks must be an object keyed by check id")
    engine_ids = {e["id"] for e in engine}
    checks: list[Check] = []
    for e in engine:
        extra = entries.get(e["id"])
        if not isinstance(extra, dict):
            raise SourceError(f"{e['id']} is in the engine but has no entry in {OVERLAY}")
        unknown = sorted(set(extra) - set(ENGINE_FIELDS))
        if unknown:
            raise SourceError(f"{e['id']}: unknown overlay field(s) {', '.join(unknown)} for an engine check")
        for field in ("req_ids", "playbooks"):
            if field not in extra:
                raise SourceError(f"{e['id']}: the overlay entry has no {field}")
        checks.append(
            _ordered(
                {
                    "id": e["id"],
                    "family": e["pack"],
                    "title": e["title"],
                    "phase": e["phase"],
                    "severity": e["severity"],
                    "scored": e["scored"],
                    "method": "automated",
                    "status": e["status"],
                    "engine_id": e["id"],
                    **extra,
                }
            )
        )
    for check_id, extra in entries.items():
        if check_id in engine_ids:
            continue
        if not isinstance(extra, dict) or extra.get("method") != "agent":
            raise SourceError(f"{check_id} is in {OVERLAY} but not in the engine, and is not an agent-only check")
        missing = [field for field in AGENT_FIELDS if field not in extra]
        unknown = sorted(set(extra) - set(AGENT_FIELDS))
        if missing or unknown:
            raise SourceError(f"{check_id}: an agent-only check states exactly {', '.join(AGENT_FIELDS)}")
        family = check_id.split("-")[0]
        agent = _ordered({"id": check_id, "family": family, "engine_id": None, **extra})
        after = [
            index for index, c in enumerate(checks) if c["family"] == family and _number(c["id"]) < _number(check_id)
        ]
        if not after:
            raise SourceError(f"{check_id}: the family {family} has no engine check with a lower number")
        checks.insert(after[-1] + 1, agent)
    families = list(dict.fromkeys(c["family"] for c in checks))
    unnamed = [family for family in families if family not in family_names]
    if unnamed:
        raise SourceError(f"no '# <name> (`<FAMILY>`)' heading in {CHECKS_DIR} for {', '.join(unnamed)}")
    return {
        "catalogue_version": overlay["catalogue_version"],
        "fingerprint": fingerprint(checks),
        "families": [{"id": family, "name": family_names[family]} for family in families],
        "checks": checks,
    }


def render(root: Path = ROOT, engine: Sequence[Check] | None = None) -> str:
    """The text of ``audit/catalogue.json`` the sources under ``root`` give."""
    overlay = json.loads((root / OVERLAY).read_text(encoding="utf-8"))
    if not isinstance(overlay, dict) or "catalogue_version" not in overlay:
        raise SourceError(f"{OVERLAY} must be an object with catalogue_version and checks")
    catalogue = build(overlay, engine_checks(root) if engine is None else engine, read_family_names(root))
    return json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None, root: Path = ROOT, engine: Sequence[Check] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="exit 1 when audit/catalogue.json is stale")
    mode.add_argument("--write", action="store_true", help="rewrite audit/catalogue.json in place")
    args = parser.parse_args(argv)
    try:
        text = render(root, engine)
    except (SourceError, OSError, KeyError, ValueError) as exc:
        print(f"build_catalogue: {exc}", file=sys.stderr)
        return 2
    path = root / CATALOGUE
    stale = not path.is_file() or path.read_text(encoding="utf-8") != text
    if args.write:
        if stale:
            path.write_text(text, encoding="utf-8")
            print(f"build_catalogue: wrote {CATALOGUE}")
        return 0
    if stale:
        print(
            f"build_catalogue: {CATALOGUE} is stale; run `make update-catalogue` and commit the result",
            file=sys.stderr,
        )
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
