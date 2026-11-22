# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-07: CHANGELOG present and recent."""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.hyg._shared import _finding, _named_documents, _outcome

SPEC = declare("HYG-07", "CHANGELOG present and recent", "A", Severity.COSMETIC, scored=False)


#: How recent a changelog change must be, measured against the `HEAD` commit date — never wall clock.
RECENT_WINDOW = dt.timedelta(days=365)


def _git_output(target_path: Path, *args: str) -> str | None:
    """Run a read-only git query. ``None`` when git is absent, fails, or the path is not a repo."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(target_path), *args],
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _commit_date(target_path: Path, *pathspec: str) -> dt.datetime | None:
    """The committer date of the last commit touching ``pathspec`` (or ``HEAD``)."""
    raw = _git_output(target_path, "log", "-1", "--format=%cI", *pathspec)
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


# ===========================================================================
# HYG-07 — CHANGELOG present and recent
# ===========================================================================


def check_hyg07(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("changelog", "changes", "history"))
    if not found:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no CHANGELOG document",
            [
                _finding(
                    spec,
                    Verdict.FAIL,
                    "see what changed between two versions",
                    "no CHANGELOG (or CHANGES/HISTORY) document exists",
                    remediation="Add CHANGELOG.md and record notable changes under a version heading.",
                ),
            ],
        )

    primary = found[0]
    head_date = _commit_date(target.path, "HEAD")
    changelog_date = _commit_date(target.path, "--", primary)
    if head_date is None or changelog_date is None:
        return _outcome(spec, Verdict.UNKNOWN, f"{primary} present, but git could not date it against HEAD")

    age = head_date - changelog_date
    if age <= RECENT_WINDOW:
        return _outcome(spec, Verdict.PASS, f"{primary} last changed {age.days} day(s) before HEAD")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"{primary} last changed {age.days} day(s) before HEAD (window {RECENT_WINDOW.days})",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "trust that the changelog reflects the current release",
                f"{primary} has not changed in {age.days} days of repository history",
                evidence=[Evidence(primary)],
                path=primary,
                remediation="Record the current release in the changelog in the same change set that cuts it.",
            ),
        ],
    )
