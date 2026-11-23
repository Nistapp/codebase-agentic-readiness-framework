# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CI-03: CI-only steps flagged."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import runner_commands, runner_target
from audit.rules.checks.ci._shared import _all_run_commands, _command_verb, _finding, _outcome, _workflows

SPEC = declare("CI-03", "CI-only steps flagged", "B", Severity.DEGRADER)


#: Package-manager subcommands that are tooling, not project scripts. Never flagged as CI-only.
_PM_BUILTINS: frozenset[str] = frozenset(
    {
        "ci",
        "install",
        "i",
        "publish",
        "pack",
        "version",
        "exec",
        "init",
        "link",
        "dedupe",
        "prune",
        "update",
        "outdated",
        "ls",
        "why",
        "config",
        "cache",
        "login",
        "logout",
        "whoami",
        "doctor",
        "help",
        "start",
        "stop",
        "restart",
        "add",
        "remove",
        "uninstall",
        "stage",
    }
)


# ===========================================================================
# CI-03 — CI-only steps flagged
# ===========================================================================


def check_ci03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    local_targets: set[str] = set()
    for _runner, commands in runner_commands(inventory):
        local_targets.update(commands)

    findings: list[Finding] = []
    for rel, line, command in _all_run_commands(inventory, _workflows(inventory)):
        if _command_verb(command) is not None:
            continue  # CI-02's subject, not repeated here
        target = runner_target(command)
        if target is None or target in _PM_BUILTINS or target in local_targets:
            continue
        findings.append(
            _finding(
                spec,
                "reproduce a CI step on the local command surface",
                f"{rel}:{line} runs `{command}` with no local runner entry for `{target}`",
                Verdict.FAIL,
                [Evidence(rel, line=line, note=command)],
                f"Add a local script/target for `{target}`, or document why the step is CI-only.",
            )
        )

    if not findings:
        return _outcome(spec, Verdict.PASS, "no CI-only steps")
    return _outcome(spec, Verdict.FAIL, f"{len(findings)} CI-only step(s)", findings)


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, ROOT, Reads, What, _at, _runners

    return Reads(
        where=(
            *_at(GLOB, ".github/workflows/*.yml", ".github/workflows/*.yaml"),
            *_at(ANY_DEPTH, ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"),
            *_at(ROOT, ".circleci/config.yml"),
            *_at(GLOB, ".buildkite/**/*.yml"),
            *_runners(),
        ),
        what=What(
            "key",
            (
                "run",
                "script",
                "command",
                "commands",
                "bash",
            ),
        ),
        binding="line",
        threshold="no CI-only step",
        note=(
            "A step command that calls a runner target that is no verb, no package-manager built-in and no "
            "target of any local runner fails. Commands split at shell operators outside quotes; echo and "
            "printf text and heredoc bodies are not commands."
        ),
    )
