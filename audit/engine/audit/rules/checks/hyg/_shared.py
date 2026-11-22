# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one HYG check uses."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.scan import Inventory
from audit.rules.payloads import Payload

#: Suffixes treated as documents for the presence checks that accept "any name plus a doc suffix".
_DOC_SUFFIXES = (".md", ".rst", ".txt", ".markdown", ".adoc")

#: Renovate files the engine can parse with the standard library; the others count on presence.
_RENOVATE_JSON = frozenset({"renovate.json", ".renovaterc", ".renovaterc.json"})


def _outcome(
    spec, verdict: Verdict, summary: str = "", findings: list[Finding] | None = None, data: Payload | None = None
) -> CheckOutcome:
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=summary,
        data=data,
        findings=findings or [],
    )


def _finding(
    spec,
    verdict: Verdict,
    cannot: str,
    because: str,
    *,
    evidence: list[Evidence] | None = None,
    path: str | None = None,
    remediation: str | None = None,
) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence or [],
        path=path,
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# artifact locators (all read the inventory; none touches the filesystem directly)
# ---------------------------------------------------------------------------


def _basename(rel: str) -> str:
    return rel.rsplit("/", 1)[-1]


#: The top-level directories where a repository-level file may live besides the root itself.
_REPOSITORY_LEVEL_DIRS = frozenset({".github", ".gitlab", "docs"})


def _repository_level(rel: str) -> bool:
    """Whether ``rel`` is at the root or under ``.github/``, ``.gitlab/`` or ``docs/`` (ADR-0008)."""
    return "/" not in rel or rel.split("/", 1)[0] in _REPOSITORY_LEVEL_DIRS


def _present(inventory: Inventory, *names: str) -> list[str]:
    """Repository-level files whose path equals, or ends with, one of ``names``."""
    wanted = tuple(name.strip("/") for name in names)
    return sorted(
        f.rel
        for f in inventory.files
        if _repository_level(f.rel)
        and (f.rel.strip("/") in wanted or any(f.rel.strip("/").endswith("/" + name) for name in wanted))
    )


def _named_documents(inventory: Inventory, prefixes: tuple[str, ...], *, root_only: bool = False) -> list[str]:
    """Repository-level files whose basename starts with a prefix and is a bare name or a document suffix."""
    out: list[str] = []
    for entry in inventory.files:
        if root_only and "/" in entry.rel:
            continue
        if not _repository_level(entry.rel):
            continue
        base = _basename(entry.rel).lower()
        if not any(base.startswith(prefix) for prefix in prefixes):
            continue
        if base.endswith(_DOC_SUFFIXES) or "." not in base:
            out.append(entry.rel)
    return sorted(out)
