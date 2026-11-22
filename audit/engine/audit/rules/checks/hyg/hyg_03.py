# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-03: Pull-request template present."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.hyg._shared import _basename, _finding, _outcome, _repository_level

SPEC = declare("HYG-03", "Pull-request template present", "A", Severity.COSMETIC, scored=False)


# ===========================================================================
# HYG-03 — pull-request template
# ===========================================================================


def check_hyg03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = sorted(
        f.rel
        for f in inventory.files
        if _repository_level(f.rel) and _basename(f.rel).lower().startswith("pull_request_template")
    )
    if found:
        return _outcome(spec, Verdict.PASS, f"pull-request template present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no pull-request template",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "file a change with the information reviewers need",
                "no .github/pull_request_template file exists",
                remediation="Add .github/pull_request_template.md describing what a good change records.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import REPOSITORY_LEVEL, Reads, What, _at

    return Reads(
        where=(*_at(REPOSITORY_LEVEL, "pull_request_template*"),),
        what=What("exists"),
        binding="file",
        note="The base name is matched case-insensitively.",
    )
