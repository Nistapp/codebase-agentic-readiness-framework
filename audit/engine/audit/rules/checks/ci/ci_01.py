# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CI-01: Pipeline present, triggered on PRs."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.ci._shared import _finding, _outcome, _workflows

SPEC = declare("CI-01", "Pipeline present, triggered on PRs", "B", Severity.BLOCKER)


#: Pull-request trigger patterns, per CI provider. Matched against the raw workflow text.
_PR_TRIGGER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "github": (re.compile(r"(?m)^\s*pull_request(?:_target)?\s*:"), re.compile(r"\bon\s*:\s*\[[^\]]*pull_request")),
    "gitlab": (re.compile(r"merge_request", re.IGNORECASE),),
    "azure": (re.compile(r"(?m)^\s*pr\s*:"),),
    "jenkins": (re.compile(r"changeRequest", re.IGNORECASE),),
}


def _has_pr_trigger(provider: str, text: str) -> bool:
    patterns = _PR_TRIGGER_PATTERNS.get(provider)
    if not patterns:
        # circleci / buildkite declare triggers in the VCS integration, not the checked-in file.
        return False
    return any(pattern.search(text) for pattern in patterns)


# ===========================================================================
# CI-01 — pipeline present, triggered on PRs
# ===========================================================================


def check_ci01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    workflows = _workflows(inventory)
    if not workflows:
        providers = ", ".join(sorted(stack.ci_providers)) or "none"
        return _outcome(
            spec,
            Verdict.FAIL,
            f"no CI workflow file (detected providers: {providers})",
            [
                _finding(
                    spec,
                    "rely on CI to verify a change set",
                    "no CI workflow file exists",
                    Verdict.FAIL,
                    [Evidence("<repository>")],
                    "Add a PR-triggered workflow (for example .github/workflows/ci.yml) that runs the same "
                    "verbs the local command surface defines.",
                )
            ],
        )

    triggered = [(provider, rel) for provider, rel in workflows if _has_pr_trigger(provider, inventory.read(rel) or "")]
    if triggered:
        detail = "; ".join(f"{rel} ({provider})" for provider, rel in triggered)
        return _outcome(spec, Verdict.PASS, f"PR-triggered: {detail}")

    providers = ", ".join(sorted({provider for provider, _rel in workflows}))
    return _outcome(
        spec,
        Verdict.PARTIAL,
        f"{len(workflows)} workflow(s) ({providers}) but none declares a PR trigger",
        [
            _finding(
                spec,
                "trust CI to run before a change reaches the default branch",
                "workflow files exist but none declares a pull-request trigger",
                Verdict.PARTIAL,
                [Evidence(rel) for _provider, rel in workflows],
                "Add a pull-request trigger (GitHub `on: pull_request`, GitLab `merge_request`, …) so the "
                "pipeline runs on the PR rather than only after merge.",
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, ROOT, Reads, What, _at

    return Reads(
        where=(
            *_at(GLOB, ".github/workflows/*.yml", ".github/workflows/*.yaml"),
            *_at(ANY_DEPTH, ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"),
            *_at(ROOT, ".circleci/config.yml"),
            *_at(GLOB, ".buildkite/**/*.yml"),
        ),
        what=What(
            "key",
            (
                "pull_request",
                "pull_request_target",
                "merge_request",
                "pr",
                "changeRequest",
            ),
        ),
        binding="file",
        threshold="a workflow with a pull-request trigger",
        note=(
            "GitHub needs the key at a line start or pull_request in an on: [...] list, Azure pr: at a line "
            "start; GitLab and Jenkins match anywhere, CircleCI and Buildkite never count. Inventory.match "
            "also compares the base name, so .gitlab-ci.yml, Jenkinsfile and azure-pipelines.yml are found at"
            " any depth."
        ),
    )
