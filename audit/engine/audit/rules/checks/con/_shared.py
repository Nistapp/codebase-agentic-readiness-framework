# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one CON check uses."""

from __future__ import annotations

import fnmatch

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.payloads import Payload

#: Directory names that make a directory a test directory. `spec` and `specs` are not among them: the framework's own
#: `specs/` folder holds feature specifications (spec-driven development), not tests, so a repository that follows
#: it has no test directory there to protect.
_TEST_DIR_NAMES: frozenset[str] = frozenset({"test", "tests", "__tests__"})


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


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


def _unknown(spec, reason: str, data: Payload | None = None) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason, data=data)


def _finding(spec, cannot: str, because: str, verdict: Verdict, evidence: list[Evidence], remediation: str) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence,
        remediation=remediation,
    )


# ===========================================================================
# CON-02 — test directories protected
# ===========================================================================


def _split_pattern(pattern: str) -> tuple[str, bool, bool]:
    """``(core, anchored, anywhere)`` of a path or pattern named in the prohibitions section.

    A leading ``/`` anchors it to the repository root, a leading ``**/`` lets it start at any depth, and a
    trailing ``/``, ``/*`` or ``/**`` only says that the path is a directory. What is left is the ``core``.
    """
    core = pattern.strip()
    anchored = core.startswith("/")
    core = core.lstrip("/")
    anywhere = core.startswith("**/")
    if anywhere:
        core = core[3:]
    changed = True
    while changed:
        changed = False
        for suffix in ("/**", "/*", "/"):
            if core.endswith(suffix):
                core = core[: -len(suffix)]
                changed = True
    return core, anchored, anywhere


def _names_directory(rel: str, pattern: str) -> bool:
    """Whether a path or pattern named in the prohibitions section covers the path ``rel``.

    Read as an ignore entry is: anchored by a leading ``/``, at any depth after ``**/``, and, with no slash
    inside it, naming a path of that name at any depth, so ``tests/`` covers ``tests`` and
    ``packages/api/tests``. A path covers every path under it. A glob is matched with ``fnmatch``.
    """
    core, anchored, anywhere = _split_pattern(pattern)
    if not core:
        return False
    if fnmatch.fnmatch(rel, core) or fnmatch.fnmatch(rel, core + "/*"):
        return True
    if anchored:
        return False
    if anywhere:
        return fnmatch.fnmatch(rel, "*/" + core) or fnmatch.fnmatch(rel, core)
    return fnmatch.fnmatch(rel.split("/")[-1], core)
