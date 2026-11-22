# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""DOC-03: artefacts/ exists and is ignored."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.ignore import decide
from audit.rules.checks._common import directory_decision, is_sanctioned_member, scoped_rules, tracked_in_scope
from audit.scan import Inventory
from audit.rules.checks.doc._shared import _outcome

SPEC = declare("DOC-03", "artefacts/ exists and is ignored", "B", Severity.DEGRADER)


#: Scratch directories the documentation contract keeps off-limits; both spellings are seen in the wild.
_SCRATCH_ROOTS: tuple[str, ...] = ("artefacts", "artifacts")


def _inventory_scratch(inventory: Inventory) -> list[str]:
    return sorted(f.rel for f in inventory.files if f.rel.split("/", 1)[0] in _SCRATCH_ROOTS)


# ===========================================================================
# DOC-03 — artefacts/ present and ignored
# ===========================================================================


def check_doc03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    scratch = _inventory_scratch(inventory)
    inventory_roots = {rel.split("/", 1)[0] for rel in scratch}
    fs_roots = {root for root in _SCRATCH_ROOTS if (target.path / root).is_dir()}
    present_roots = sorted(inventory_roots | fs_roots)

    tracked = tracked_in_scope(target, inventory)
    rules = scoped_rules(target, inventory)
    tracked_scratch = sorted(
        rel
        for rel in (tracked or set())
        if rel.split("/", 1)[0] in _SCRATCH_ROOTS and not is_sanctioned_member(rel, rel.split("/", 1)[0], rules)
    )

    if not present_roots and not tracked_scratch:
        return _outcome(spec, Verdict.PASS, "no scratch directory in use")

    if tracked_scratch:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"tracked: {', '.join(tracked_scratch[:8])}",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "treat the scratch directory as transient",
                        f"{len(tracked_scratch)} path(s) under {', '.join(present_roots or ['scratch'])}/"
                        f" are tracked by git",
                    ),
                    evidence=[Evidence(rel) for rel in tracked_scratch[:12]],
                    path=tracked_scratch[0],
                    remediation="Untrack the scratch contents (git rm --cached) — the ignore rule only "
                    "keeps future files out.",
                ),
            ],
        )

    decisions = {root: directory_decision(root, rules) for root in present_roots}
    for root in present_roots:
        if not decisions[root].ignored:
            for rel in scratch:
                inside = decide(rel, rules)
                if rel.startswith(root + "/") and inside.ignored:
                    decisions[root] = inside
                    break
    covered = any(decision.ignored for decision in decisions.values())
    if not covered:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"{', '.join(present_roots)}/ present but not matched by any ignore rule",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "rely on transient scratch staying out of the repository",
                        f"{', '.join(present_roots)}/ exists but no ignore rule covers it",
                    ),
                    evidence=[Evidence(rel) for rel in scratch[:12]],
                    remediation=f"Add `{present_roots[0]}/` to .gitignore so scratch documents cannot "
                    f"be committed and agents do not read them as source of truth.",
                ),
            ],
        )

    if tracked is None:
        return _outcome(
            spec,
            Verdict.UNKNOWN,
            f"ignore rules cover {', '.join(present_roots)}/, but git could not report the tracked set",
        )

    by = sorted({d.rule.source for d in decisions.values() if d.ignored and d.rule is not None})
    via = f" by {', '.join(by)}" if by else ""
    return _outcome(spec, Verdict.PASS, f"{', '.join(present_roots)}/ present, ignored{via}, and untracked")
