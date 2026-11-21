# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Rule-pack registry — one table, mirroring docs/architecture/contributor-deep-dive/02-check-catalogue.md.

The catalogue page is the design of record; this module is its executable form. A change to either
updates both in the same change set (enforced socially, and by the self-verification docstring in
the catalogue's § Adding a Check).

Three things live here and nowhere else:

* the **id → metadata** table (tier, severity, phase anchor, scored/not)
* **framework anchors**: the Phase-1 heading each pack traces back to, resolvable by ``--verify-rules``
* **applicability**: which packs apply to a detected stack, so an unsupported ecosystem degrades to
  ``UNKNOWN`` instead of passing silently
"""

from __future__ import annotations

import re
from pathlib import Path

from audit.findings import Severity
from audit.rules.checks import agt, base, ci, cmd, con, doc, execution, idx, nav, sec, tool, tst
from audit.rules.spec import PACK_ANCHORS as PACK_ANCHORS
from audit.rules.spec import Anchor as Anchor
from audit.rules.spec import CheckSpec as CheckSpec
from audit.rules.spec import declare as _c

_S = Severity

#: The catalogue. Order here is the order in the report and in ``--list-checks``.
_CATALOGUE: tuple[CheckSpec, ...] = (
    *idx.SPECS,
    *agt.SPECS,
    *doc.SPECS,
    *cmd.SPECS,
    *tool.SPECS,
    *ci.SPECS,
    *base.SPECS,
    *con.SPECS,
    *execution.SPECS,
    *tst.SPECS,
    *nav.SPECS,
    *sec.SPECS,
    # -- HYG (informational, never scored) -------------------------------
    _c("HYG-01", "README present and non-placeholder", "A", _S.COSMETIC, scored=False),
    _c("HYG-02", "CODEOWNERS present", "A", _S.COSMETIC, scored=False),
    _c("HYG-03", "Pull-request template present", "A", _S.COSMETIC, scored=False),
    _c("HYG-04", "Issue templates present", "A", _S.COSMETIC, scored=False),
    _c("HYG-05", "CONTRIBUTING present", "A", _S.COSMETIC, scored=False),
    _c("HYG-06", "SECURITY present", "A", _S.COSMETIC, scored=False),
    _c("HYG-07", "CHANGELOG present and recent", "A", _S.COSMETIC, scored=False),
    _c("HYG-08", "Release process documented", "A", _S.COSMETIC, scored=False),
    _c("HYG-09", "Dependency update automation configured", "A", _S.COSMETIC, scored=False),
    _c("HYG-10", "License present", "A", _S.COSMETIC, scored=False),
    _c("HYG-11", "Branch protection declared as code", "B", _S.COSMETIC, scored=False),
    _c(
        "HYG-13",
        "Contributing rules written",
        "B",
        _S.COSMETIC,
        scored=False,
        rule="The CONTRIBUTING document (root, .github/, .gitlab/ or docs/) points to the setup command, names the gate "
        "command and says CI runs the same, and states the rules for branches, commits and pull requests; no "
        "CONTRIBUTING document is UNKNOWN, because HYG-05 owns that finding.",
    ),
)


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


REGISTRY: tuple[CheckSpec, ...] = _attach_implementations(_CATALOGUE)

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
