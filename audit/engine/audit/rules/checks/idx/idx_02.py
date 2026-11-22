# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""IDX-02: An index exists for this checkout."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks.idx._shared import (
    _candidate_dbs,
    _finding,
    _locate_store,
    _outcome,
    _read_projects,
    _resolve,
    _shown,
    _unknown,
)

SPEC = declare("IDX-02", "An index exists for this checkout", "A", Severity.BLOCKER)


# ===========================================================================
# IDX-02 — an index exists for this checkout
# ===========================================================================


def check_idx02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    store, searched = _locate_store(target, session)
    locations = f"searched: {', '.join(searched)}"

    if store is None:
        return _unknown(spec, f"index store could not be located; {locations}")

    shown = _shown(store, target)
    dbs = _candidate_dbs(store)
    if not dbs:
        return _unknown(spec, f"index store located ({shown}) but holds no readable database; {locations}")

    roots: list[str] = []
    readable = False
    for db in dbs:
        rows = _read_projects(db)
        if rows is None:
            continue
        readable = True
        roots.extend(str(row.get("root_path", "")) for row in rows)

    if not readable:
        return _unknown(
            spec, f"index store located ({shown}) but no database could be read with the standard library; {locations}"
        )

    wanted = target.path.resolve()
    if any(_resolve(root) == wanted for root in roots if root):
        return _outcome(spec, Verdict.PASS, f"index store {shown} contains a project rooted at <repository>")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"index store {shown} records no project rooted at <repository> ({len(roots)} project(s) present)",
        [
            _finding(
                spec,
                "query a current index of this checkout",
                "the index store contains no project whose root resolves to <repository>",
                Verdict.FAIL,
                [Evidence(str(store))],
                "Index this checkout with codebase-memory-mcp so agents have a graph to query.",
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at

    return Reads(
        where=(*_at(ROOT, ".codebase-memory/graph.db.zst"),),
        what=What("exists"),
        binding="file",
        note=(
            "The store is looked for in AUDIT_INDEX_STORE, then three folders under $HOME, then this team "
            "artifact in the target; only a *.db store is opened, and its projects table is read for a "
            "root_path that resolves to the target."
        ),
    )
