# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""DOC-04: ADR directory and index."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.checks.doc._shared import _has_exact, _outcome

SPEC = declare("DOC-04", "ADR directory and index", "A", Severity.COSMETIC)


#: The two ADR locations the framework's own docs use.
_ADR_DIRS: tuple[str, ...] = ("docs/architecture/adrs", "docs/adr")

_ADR_FILE_RE = re.compile(r"^\d{3,4}-[A-Za-z0-9._-]+\.md$")


# ===========================================================================
# DOC-04 — ADR directory and index
# ===========================================================================


def _adr_dir(inventory: Inventory) -> str | None:
    for directory in _ADR_DIRS:
        if any(f.rel.startswith(directory + "/") for f in inventory.files):
            return directory
    return None


#: ``0000-template.md`` is the blank a new ADR is copied from, not a decision.
_ADR_TEMPLATE_RE = re.compile(r"^\d{3,4}-(?:adr-)?template[._-]", re.IGNORECASE)


def _adr_entries(inventory: Inventory, directory: str) -> list[str]:
    return sorted(
        f.rel
        for f in inventory.files
        if f.rel.startswith(directory + "/")
        and _ADR_FILE_RE.match(f.rel.rsplit("/", 1)[-1])
        and not _ADR_TEMPLATE_RE.match(f.rel.rsplit("/", 1)[-1])
    )


#: A status line or field that retires the record: `Status: Superseded`, `* **Status:** Deprecated`,
#: `| Status | Rejected |` or front matter `status: superseded by ADR-0005`.
_TOMBSTONE_STATUS_RE = re.compile(
    r"^[ \t>*_|#-]*status[ \t*_:|-]*(superseded|deprecated|rejected|obsolete)\b", re.IGNORECASE | re.MULTILINE
)
#: A line that opens by pointing at the record that replaced this one.
_TOMBSTONE_POINTER_RE = re.compile(
    r"^[ \t>*_-]*(superseded\s+by|replaced\s+by|deprecated\s+(by|in\s+favou?r\s+of))\b",
    re.IGNORECASE | re.MULTILINE,
)
#: The MADR form: a `## Status` heading whose first line of text retires the record.
_STATUS_SECTION_RE = re.compile(
    r"^#{1,6}\s*status\s*\n(?:[ \t]*\n)*[ \t>*_-]*(superseded|deprecated|rejected|obsolete)\b",
    re.IGNORECASE | re.MULTILINE,
)


def _adr_tombstone(text: str) -> int | None:
    """The 1-based line that marks this ADR as retired, or ``None`` for a current record.

    Only a status line or field, a `## Status` section, or a line that opens with "superseded by",
    "replaced by" or "deprecated by / in favour of" counts. A word like "superseded" inside a sentence or a
    table of alternatives does not, so an ADR may still discuss a rejected option.
    """
    hits = [
        m.start() for rx in (_TOMBSTONE_STATUS_RE, _TOMBSTONE_POINTER_RE, _STATUS_SECTION_RE) for m in rx.finditer(text)
    ]
    if not hits:
        return None
    return text.count("\n", 0, min(hits)) + 1


def _adr_index(inventory: Inventory, directory: str) -> str | None:
    """A README/index beside the ADRs, falling back to the parent directory's README."""
    for candidate in (f"{directory}/README.md", f"{directory}/index.md", f"{directory}/_index.md"):
        if _has_exact(inventory, candidate):
            return candidate
    parent = directory.rsplit("/", 1)[0]
    for candidate in (f"{parent}/README.md", f"{parent}/index.md"):
        if _has_exact(inventory, candidate):
            return candidate
    return None


def check_doc04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    directory = _adr_dir(inventory)
    if directory is None:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no ADR directory",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "find the decisions of record", "no ADR directory (docs/architecture/adrs/ or docs/adr/) exists"
                    ),
                    remediation="Add docs/architecture/adrs/ with NNNN-short-title.md files and a "
                    "README index that lists them.",
                ),
            ],
        )

    entries = _adr_entries(inventory, directory)
    if not entries:
        return _outcome(spec, Verdict.PARTIAL, f"{directory}/ exists but holds no numbered ADR")

    index = _adr_index(inventory, directory)
    findings: list[Finding] = []
    summaries: list[str] = []

    if index is None:
        summaries.append(f"{len(entries)} ADR(s) present but no index file")
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "discover the decisions of record from one page",
                    f"{directory}/ holds {len(entries)} ADR(s) but no index lists them",
                ),
                evidence=[Evidence(rel) for rel in entries[:12]],
                remediation="Add a README (or index) beside the ADRs, or list them from the architecture README.",
            )
        )
    else:
        text = inventory.read(index) or ""
        listed = [
            rel
            for rel in entries
            if rel.rsplit("/", 1)[-1] in text or re.search(rf"\b{rel.rsplit('/', 1)[-1][:4]}\b", text)
        ]
        if len(listed) < len(entries):
            summaries.append(f"{len(listed)}/{len(entries)} ADR(s) listed in {index}")
            findings.append(
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "find every decision of record",
                        f"{index} lists {len(listed)} of {len(entries)} ADRs in {directory}/",
                    ),
                    evidence=[Evidence(index)],
                    remediation="Add a row to the ADR index for each entry, in the same change set that adds the ADR.",
                )
            )

    tombstones = [(rel, line) for rel in entries if (line := _adr_tombstone(inventory.read(rel) or "")) is not None]
    if tombstones:
        summaries.append(f"{len(tombstones)} ADR(s) marked superseded, deprecated or rejected")
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "trust that every ADR it loads is a current decision",
                    f"{len(tombstones)} ADR(s) in {directory}/ are marked superseded, deprecated or rejected, "
                    "and an agent can apply them as current rules",
                ),
                evidence=[Evidence(rel, line, note="retired record") for rel, line in tombstones[:12]],
                remediation="Delete each retired ADR, with its index row and every reference to it; git keeps its "
                "history. When a decision changed, overwrite the current ADR in place and list the old choice under "
                "Alternatives Considered.",
            )
        )

    if findings:
        return _outcome(spec, Verdict.PARTIAL, "; ".join(summaries), findings)
    return _outcome(spec, Verdict.PASS, f"{len(entries)} ADR(s) indexed in {index}")
