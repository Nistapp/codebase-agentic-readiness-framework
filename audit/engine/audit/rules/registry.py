# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Rule-pack registry — the catalogue, assembled from the check families.

Each check family module under ``audit/rules/checks/`` declares its checks (``SPECS``) beside their
implementations; this module joins the families, in the written order of ``FAMILIES``, into one
catalogue. ``docs/architecture/contributor-deep-dive/02-check-catalogue.md`` is the design of record. A
change to a check's declaration updates that page in the same change set (enforced socially, and by
the self-verification docstring in the catalogue's § Adding a Check).

Three things are joined or kept here:

* the **id → metadata** table (tier, severity, phase anchor, scored/not), in catalogue order
* **framework anchors**: the Phase-1 heading each pack traces back to, resolvable by ``--verify-rules``
* **applicability**: which packs apply to a detected stack, so an unsupported ecosystem degrades to
  ``UNKNOWN`` instead of passing silently
"""

from __future__ import annotations

import re
from pathlib import Path

from audit.rules.checks import agt, base, ci, cmd, con, doc, execution, hyg, idx, nav, sec, tool, tst
from audit.rules.spec import PACK_ANCHORS as PACK_ANCHORS
from audit.rules.spec import Anchor as Anchor
from audit.rules.spec import CheckSpec as CheckSpec

#: The check families, in catalogue order. Within a family, its ``SPECS`` give the order. This order is the order
#: in the report and in ``--list-checks``, and ``ruleset_hash`` reads it.
FAMILIES = (idx, agt, doc, cmd, tool, ci, base, con, execution, tst, nav, sec, hyg)


def _attach_implementations(specs: tuple[CheckSpec, ...]) -> tuple[CheckSpec, ...]:
    """Wire implemented checks from audit/rules/checks/*. Nothing implemented ⇒ all planned."""
    try:
        from audit.rules.checks import IMPLEMENTATIONS
    except ImportError:  # a partially built tree must still list and run
        return specs

    for spec in specs:
        impl = IMPLEMENTATIONS.get(spec.id)
        if impl is not None:
            spec.impl = impl
            if spec.status == "planned":
                spec.status = "implemented"
    return specs


#: The catalogue: every family's declared checks, in order, wired to their implementations.
REGISTRY: tuple[CheckSpec, ...] = _attach_implementations(tuple(spec for family in FAMILIES for spec in family.SPECS))

REGISTRY_BY_ID: dict[str, CheckSpec] = {spec.id: spec for spec in REGISTRY}


# ---------------------------------------------------------------------------
# queries
# ---------------------------------------------------------------------------


def applicable_checks(stack) -> list[CheckSpec]:
    return [spec for spec in REGISTRY if spec.applies_to(stack)]


def scoreable() -> list[CheckSpec]:
    return [s for s in REGISTRY if s.scored and s.status != "blocked"]


def informational() -> list[CheckSpec]:
    return [s for s in REGISTRY if not s.scored]


# ---------------------------------------------------------------------------
# framework anchor resolution (--verify-rules)
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def _normalise(text: str) -> str:
    """Strip markdown decoration and emoji so anchors survive cosmetic edits to the framework."""
    text = re.sub(r"[*_`#]", "", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2190-\u21FF\u2600-\u27BF\uFE0F]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def resolve_anchors(specs, framework_root: Path) -> list[tuple[str, Anchor]]:
    """Return the (pack, anchor) pairs whose heading is not found. Empty ⇒ all resolve."""
    headings: dict[str, set[str]] = {}
    missing: list[tuple[str, Anchor]] = []
    for pack, anchor in PACK_ANCHORS.items():
        if pack not in {s.pack for s in specs}:
            continue
        if anchor.file not in headings:
            path = framework_root / anchor.file
            if not path.is_file():
                missing.append((pack, anchor))
                headings[anchor.file] = set()
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            headings[anchor.file] = {_normalise(match.group(1)) for match in _HEADING_RE.finditer(text)}
        wanted = _normalise(anchor.heading)
        if not any(wanted in heading for heading in headings[anchor.file]):
            missing.append((pack, anchor))
    return missing


#: A directory is the framework checkout when it holds the file every rule pack anchors to.
_FRAMEWORK_MARKER = "docs/framework/phased-approach.md"


def find_framework_root(start: Path | None = None) -> Path | None:
    """Locate the framework checkout by walking up from ``start`` (default: this package).

    This tool lives inside the framework repository, so the default resolves to the repository root
    with no flag. ``None`` means the tool was moved out of the repository (a ``.pyz`` copied
    elsewhere, say); callers then need an explicit ``--framework``.
    """
    here = (start if start is not None else Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / _FRAMEWORK_MARKER).is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# ruleset identity (recorded in every report's provenance)
# ---------------------------------------------------------------------------


def ruleset_hash() -> str:
    """SHA-256 over the catalogue and the instruction-variant table.

    Two reports with different hashes were produced by different rules; that is the whole point.
    Changing a variant table entry changes the hash, so a silently rotted table is visible in the
    report rather than inferred from a suspicious verdict.
    """
    import hashlib

    import audit.rules.variants as variants

    parts = [f"{s.id}|{s.tier}|{s.severity.value}|{int(s.scored)}|{s.status}|{s.evidence_rule}" for s in REGISTRY]
    for harness in variants.HARNESSES:
        parts.append(
            f"H|{harness.tool}|{harness.agents_md}|{int(harness.nested)}|{','.join(harness.paths)}|{harness.doc_url}"
            + (f"|gated:{','.join(harness.config)}" if harness.paths_need_config else "")
        )
    for row in variants.SHADOW_PAIRS:
        parts.append("S|" + "|".join(row))
    for row in variants.CONFIG_INDIRECTION:
        parts.append("I|" + "|".join(row))
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]
