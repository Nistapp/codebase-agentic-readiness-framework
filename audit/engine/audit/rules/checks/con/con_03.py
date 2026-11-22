# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CON-03: artefacts/ excluded from index and agent reads."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import directory_decision, is_sanctioned_member, scoped_rules, tracked_in_scope
from audit.scan import Inventory
from audit.target import Target
from audit.rules.checks.con._shared import _finding, _outcome, _unknown

SPEC = declare("CON-03", "artefacts/ excluded from index and agent reads", "B", Severity.DEGRADER)


#: Scratch spellings and agent/tool state directories CON-03 requires to be ignored.
_SCRATCH_ROOTS: tuple[str, ...] = ("artefacts", "artifacts")
_STATE_ROOTS: tuple[str, ...] = (".codebase-memory", ".opencode", ".agentic-tdd")
_CON_ROOTS: tuple[str, ...] = _SCRATCH_ROOTS + _STATE_ROOTS


def _present_roots(target: Target, inventory: Inventory) -> list[str]:
    """The candidate scratch/state roots that exist, from the filesystem and from the scan."""
    present = {root for root in _CON_ROOTS if (target.path / root).is_dir()}
    present.update(entry.rel.split("/", 1)[0] for entry in inventory.files)
    return sorted(root for root in present if root in _CON_ROOTS)


# ===========================================================================
# CON-03 — artefacts/ and agent state excluded from index and reads
# ===========================================================================


def check_con03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    tracked = tracked_in_scope(target, inventory)
    rules = scoped_rules(target, inventory)
    tracked_members = sorted(
        rel
        for rel in (tracked or set())
        if rel.split("/", 1)[0] in _CON_ROOTS and not is_sanctioned_member(rel, rel.split("/", 1)[0], rules)
    )

    if tracked_members:
        roots = sorted({rel.split("/", 1)[0] for rel in tracked_members})
        return _outcome(
            spec,
            Verdict.FAIL,
            f"tracked: {', '.join(tracked_members[:8])}",
            [
                _finding(
                    spec,
                    "treat scratch and agent-state directories as transient",
                    f"{len(tracked_members)} path(s) under {', '.join(roots)}/ are tracked by git",
                    Verdict.FAIL,
                    [Evidence(rel) for rel in tracked_members[:12]],
                    "Untrack the contents (git rm --cached) — an ignore rule only keeps future files out.",
                )
            ],
        )

    present = _present_roots(target, inventory)
    if not present:
        return _outcome(spec, Verdict.PASS, "no scratch or agent-state directory in use")

    decisions = {root: directory_decision(root, rules) for root in present}
    covered = [root for root in present if decisions[root].ignored]
    uncovered = [root for root in present if not decisions[root].ignored]

    if uncovered and not covered:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"{', '.join(root + '/' for root in uncovered)} present but matched by no ignore rule",
            [
                _finding(
                    spec,
                    "keep scratch and agent-state directories out of the index and out of reads",
                    f"{', '.join(root + '/' for root in uncovered)} exists but no ignore rule covers it",
                    Verdict.FAIL,
                    [Evidence(root + "/") for root in uncovered],
                    f"Add {', '.join(root + '/' for root in uncovered)} to .gitignore so agents and the "
                    f"index do not read transient state as source of truth.",
                )
            ],
        )

    if uncovered:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"ignore rules cover {', '.join(root + '/' for root in covered)} but not "
            f"{', '.join(root + '/' for root in uncovered)}",
            [
                _finding(
                    spec,
                    "keep every scratch and agent-state directory out of the index and reads",
                    f"ignore rules do not cover {', '.join(root + '/' for root in uncovered)}",
                    Verdict.PARTIAL,
                    [Evidence(root + "/") for root in uncovered],
                    f"Add {', '.join(root + '/' for root in uncovered)} to .gitignore.",
                )
            ],
        )

    if tracked is None:
        covered_list = ", ".join(root + "/" for root in covered)
        return _unknown(spec, f"ignore rules cover {covered_list}, but git could not report the tracked set")

    by = sorted({d.rule.source for d in decisions.values() if d.ignored and d.rule is not None})
    via = f" by {', '.join(by)}" if by else ""
    return _outcome(
        spec, Verdict.PASS, f"{', '.join(root + '/' for root in covered)} present, ignored{via}, and untracked"
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit import ignore
    from audit.rules.checks import con
    from audit.rules.reads import ANY_DEPTH, ROOT, Reads, What, _held

    return Reads(
        where=(
            *_held(con, "_CON_ROOTS", ROOT),
            *_held(ignore, "IGNORE_FILE_NAMES", ROOT, {".gitignore": ANY_DEPTH}),
        ),
        what=What("exists"),
        binding="file",
        threshold="every present folder ignored and untracked",
        note=(
            "The top-level scratch and agent-state folders in the scan or on disk, the tracked files under "
            "them, and the ignore rules as DOC-03 reads them."
        ),
    )
