# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TST-02: Suite status known."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.probes import ProbePlan
from audit.rules.checks._common import resolve_verbs, runner_kind
from audit.rules.checks.tst._shared import _finding, _outcome, _unknown

SPEC = declare("TST-02", "Suite status known", "C", Severity.DEGRADER)


# ===========================================================================
# TST-02 — suite status (Tier C)
# ===========================================================================


def _runner_path(runner: str) -> tuple[str, ...]:
    """The directories a runner puts first on ``PATH`` for a script it runs, nearest first.

    ``npm run`` adds ``node_modules/.bin`` of the manifest's directory and of each directory above it; pnpm,
    yarn and bun do the same. Other runners add nothing.
    """
    if runner_kind(runner) != "package.json":
        return ()
    parts = runner.split("/")[:-1]
    return tuple("/".join([*parts[:depth], "node_modules", ".bin"]) for depth in range(len(parts), -1, -1))


def check_tst02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    binding = resolve_verbs(inventory, stack).get("test")
    if binding is None:
        return _unknown(spec, "no test verb resolves on any runner, so the suite cannot be run")

    plan = ProbePlan(verb="test", command=list(binding.argv), read_only=True, path_prepend=_runner_path(binding.runner))
    result = session.run(plan)

    if result.refused_reason:
        return _unknown(spec, f"probe not run: {result.refused_reason}")
    if result.timed_out:
        return _unknown(spec, "test probe timed out; suite status unknown")
    if result.exit_code == 0:
        return _outcome(spec, Verdict.PASS, f"test verb exited 0 in {result.duration_s:.2f}s")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"test verb exited {result.exit_code}",
        [
            _finding(
                spec,
                "trust the suite to verify a change set",
                f"the test verb ({' '.join(plan.command)}) exited {result.exit_code}",
                Verdict.FAIL,
                [Evidence(binding.runner, note=binding.command)],
                "Make the test verb exit 0 before relying on it as a gate.",
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import Reads, What, _runners

    return Reads(
        where=(*_runners(),),
        what=What("key"),
        binding="file",
        note=(
            "No file text: the resolved test verb runs as a read-only probe, only with --run-gates and "
            "--allow-probe test. Every runner manifest counts only at the root, where it is read. A "
            "package.json verb runs with node_modules/.bin first on PATH."
        ),
    )
