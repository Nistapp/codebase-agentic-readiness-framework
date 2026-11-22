# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-08: Release process documented."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.checks.hyg._shared import _DOC_SUFFIXES, _basename, _finding, _outcome, _repository_level

SPEC = declare("HYG-08", "Release process documented", "A", Severity.COSMETIC, scored=False)


def _documents_containing(inventory: Inventory, needle: str) -> list[str]:
    return sorted(
        f.rel
        for f in inventory.files
        if _repository_level(f.rel)
        and needle in _basename(f.rel).lower()
        and _basename(f.rel).lower().endswith(_DOC_SUFFIXES)
    )


# ===========================================================================
# HYG-08 — release document
# ===========================================================================


def check_hyg08(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _documents_containing(inventory, "release")
    if found:
        return _outcome(spec, Verdict.PASS, f"release document present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no release document",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "know how a release is cut",
                "no text or markdown document describing the release process exists",
                remediation="Add docs/releasing.md (or RELEASE.md) describing how a version is cut and published.",
            ),
        ],
    )
