# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-06: Architectural boundaries declared."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import entry_instruction_file
from audit.scan import Inventory
from audit.rules.checks.agt._shared import _unknown

SPEC = declare("AGT-06", "Architectural boundaries declared", "B", Severity.DEGRADER)


# ---------------------------------------------------------------------------
# AGT-06 — architectural boundaries declared
# ---------------------------------------------------------------------------

_BOUNDARY_CONTEXT_RE = re.compile(
    r"(?i)\b(must|never|only|prohibit|forbidden|boundar|module|owns?|responsible|responsibility|"
    r"import|depend|layer|allow|deny|exclude|separate|isolat)\b"
)
_PATH_TOKEN_RE = re.compile(
    r"`([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]*)+)`"
    r"|(?<![\w/`])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]*)+)"
)


def _path_is_real(inventory: Inventory, token: str) -> bool:
    """True when a mentioned path resolves to a file or a directory prefix in the target."""
    token = token.strip("`").lstrip("./").rstrip("/")
    if not token:
        return False
    if inventory.has(token):
        return True
    return any(f.rel == token or f.rel.startswith(token + "/") for f in inventory.files)


def check_agt06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    referenced: dict[str, int] = {}
    for no, line in enumerate(text.splitlines(), start=1):
        if not _BOUNDARY_CONTEXT_RE.search(line):
            continue
        for match in _PATH_TOKEN_RE.finditer(line):
            token = match.group(1) or match.group(2)
            if _path_is_real(inventory, token):
                referenced.setdefault(token.strip("`").rstrip("/"), no)

    count = len(referenced)
    if count >= 2:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.PASS,
            spec.status,
            summary=f"{count} boundary rules reference real paths",
        )

    verdict = Verdict.PARTIAL if count == 1 else Verdict.FAIL
    why = (
        f"only {count} boundary rule references a path that exists in this repository"
        if count
        else "no boundary rule references a path that exists in this repository"
    )
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=why,
        findings=[
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=verdict,
                statement=statement("learn where code may live and what may cross a boundary", why),
                evidence=[Evidence(name, line=line, note=token) for token, line in referenced.items()],
                remediation="State at least two boundaries as rules naming real paths — for example "
                "where application code lives and where tests live.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at

    return Reads(
        where=(*_at(ROOT, "AGENTS.md", "CLAUDE.md"),),
        what=What("word-list"),
        binding="line",
        threshold="two or more boundary rules naming real paths",
        note=(
            "A line with one of 18 rule words (must, never, only, module, owns, import, layer and others) "
            "and, on the same line, a path token with a slash that names a scanned file or a folder above "
            "one."
        ),
        named_by_text="each path token of a boundary line is looked up with Inventory.has",
    )
