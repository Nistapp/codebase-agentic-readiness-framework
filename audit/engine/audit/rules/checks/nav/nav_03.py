# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""NAV-03: Structural red flags."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Kind
from audit.stack import LOCKFILE_NAMES
from audit.rules.checks.nav._shared import _outcome

SPEC = declare("NAV-03", "Structural red flags", "B", Severity.COSMETIC)


#: Files larger than this are counted as oversized (NAV-03). Documented, not tuned.
LARGE_FILE_BYTES = 512 * 1024

#: A directory holding more than this many immediate files is a catch-all (NAV-03). Documented.
CATCH_ALL_FILES = 50


# ===========================================================================
# NAV-03 — structural red flags (informational counts, never FAIL)
# ===========================================================================


def check_nav03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    large = sorted(f.rel for f in inventory.files if f.size > LARGE_FILE_BYTES)
    lockfiles = [rel for rel in large if rel.rsplit("/", 1)[-1] in LOCKFILE_NAMES]
    oversized = [rel for rel in large if rel.rsplit("/", 1)[-1] not in LOCKFILE_NAMES]
    binaries = sorted(f.rel for f in inventory.files if f.kind is Kind.BINARY)
    minified = sorted(f.rel for f in inventory.files if f.kind is Kind.GENERATED and ".min." in f.rel.lower())

    per_dir: dict[str, int] = {}
    for entry in inventory.files:
        parent = entry.rel.rsplit("/", 1)[0] if "/" in entry.rel else "."
        per_dir[parent] = per_dir.get(parent, 0) + 1
    catch_all = sorted(directory for directory, count in per_dir.items() if count > CATCH_ALL_FILES)

    detail = (
        f"oversized(>{LARGE_FILE_BYTES} B): {len(oversized)}; "
        f"catch-all dirs(>{CATCH_ALL_FILES} files): {len(catch_all)}; "
        f"binaries: {len(binaries)}; minified: {len(minified)}"
    )
    if lockfiles:
        detail += f"; lockfiles over the size, not counted: {len(lockfiles)} ({', '.join(lockfiles[:6])})"
    flags = oversized + catch_all + binaries + minified
    if not flags:
        return _outcome(spec, Verdict.PASS, detail)

    return _outcome(
        spec,
        Verdict.PARTIAL,
        detail,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "work in a codebase without obvious structural traps",
                    f"{len(oversized)} oversized file(s), {len(catch_all)} catch-all director(y/ies), "
                    f"{len(binaries)} checked-in binary file(s) and {len(minified)} minified asset(s)",
                ),
                evidence=[Evidence(rel) for rel in (oversized + catch_all + binaries + minified)[:12]],
                remediation="Split oversized files, break up catch-all directories, and keep binaries "
                "and minified assets out of the tree (generate them in the build).",
            ),
        ],
    )
