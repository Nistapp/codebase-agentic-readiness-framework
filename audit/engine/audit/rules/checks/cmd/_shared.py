# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one CMD check uses."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Finding, Verdict
from audit.rules.checks._common import makefile_errors, runner_rank
from audit.rules.payloads import Payload

_SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")

_NPM_RE = re.compile(r"\b(?:npm|pnpm|bun)\s+(?:run\s+)?([A-Za-z0-9:_-]+)")
_YARN_RE = re.compile(r"\byarn\s+(?:run\s+)?([A-Za-z0-9:_-]+)")
# A shell passes `format\:check` and `'format:check'` to make as `format:check`, so both name that target.
_TASK_RE = re.compile(r"\b(?:make|task|just|mise)\s+(?:-\S+\s+)*['\"]?([A-Za-z0-9:_\\-]+)")
_RUNNER_INVOCATIONS = (_NPM_RE, _YARN_RE, _TASK_RE)


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


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _no_runner(spec, inventory, cannot: str) -> CheckOutcome:
    """``UNKNOWN`` for a repository with no runner to read. A Makefile that does not parse is no runner, and
    ``CMD-01`` owns that defect, so it is named here and not reported again."""
    if makefile_errors(inventory):
        return _unknown(spec, f"the Makefile does not parse (see CMD-01), so {cannot}")
    return _unknown(spec, f"no recognised verb runner, so {cannot}")


def _segments(command: str) -> list[str]:
    return [s for s in _SEGMENT_SPLIT.split(command) if s.strip()]


def _runner_target(segment: str) -> str | None:
    """The verb/script a segment invokes through a package manager, Make, or a task runner."""
    for pattern in _RUNNER_INVOCATIONS:
        match = pattern.search(segment)
        if match:
            return match.group(1).replace("\\:", ":")
    return None


def _ordered_runners(runners: set[str]) -> list[str]:
    return sorted(runners, key=runner_rank)
