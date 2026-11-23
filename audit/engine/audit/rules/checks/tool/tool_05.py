# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TOOL-05: Local hook chain active."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.tool._shared import _finding, _hook_wiring, _manifest_evidence, _outcome, _unknown

SPEC = declare("TOOL-05", "Local hook chain active", "B", Severity.DEGRADER)


# ===========================================================================
# TOOL-05 — local hook chain active
# ===========================================================================


def check_tool05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    wired, configured = _hook_wiring(inventory)

    if wired:
        return _outcome(spec, Verdict.PASS, f"wired: {', '.join(sorted(set(wired)))}")

    if configured:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"hooks present but not wired: {', '.join(sorted(set(configured)))}",
            [
                _finding(
                    spec,
                    "rely on local hooks to run before a commit",
                    f"a hook manager is present but not wired ({', '.join(sorted(set(configured)))})",
                    Verdict.PARTIAL,
                    [Evidence(rel.split(" ")[0]) for rel in sorted(set(configured))],
                    "Wire the hooks: set `core.hooksPath`, add a `prepare`/install script, or commit a "
                    "`.pre-commit-config.yaml`.",
                )
            ],
        )

    if stack.ecosystems:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no hook chain configured",
            [
                _finding(
                    spec,
                    "rely on local hooks to run before a commit",
                    "no hook manager is configured",
                    Verdict.FAIL,
                    _manifest_evidence(inventory),
                    "Adopt a hook manager (pre-commit, lefthook, husky) and wire it so checks run before a "
                    "commit rather than only in CI.",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem and no hook configuration, so a hook chain cannot be ruled out")


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, Reads, What, _at, _runners

    return Reads(
        where=(
            *_at(ANY_DEPTH, ".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml"),
            *_at(GLOB, ".githooks/*", ".husky/*", "**"),
            *_runners(),
        ),
        what=What("exists"),
        binding="file",
        note=(
            "A hook-manager file at any depth, or core.hooksPath in any manifest, config, script, CI or build"
            " file (glob **), is wired; .husky/ is wired only when a root package.json script names husky. "
            "With no hook chain, the FAIL cites the runner manifests that the runner resolver finds."
        ),
    )
