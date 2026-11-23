# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-05: Seven verbs named."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import entry_instruction_file, resolve_verbs, runner_commands
from audit.stack import FORMAT_CHECK_ALIASES, VERBS
from audit.rules.payloads import VerbEntry, VerbSurface
from audit.rules.checks.agt._shared import _unknown

SPEC = declare("AGT-05", "Seven verbs named", "B", Severity.DEGRADER)


# ---------------------------------------------------------------------------
# AGT-05 — seven verbs named, and they resolve
# ---------------------------------------------------------------------------


#: Each verb's spellings the spec accepts (``spec/command-surface.md`` § Spelling per runner): its own name, and for
#: ``format:check`` also ``format-check`` and ``formatCheck``. A runner script under any other name is not a verb.
_VERB_SPELLINGS: dict[str, tuple[str, ...]] = {
    verb: (verb, *sorted({alias for aliases in FORMAT_CHECK_ALIASES.values() for alias in aliases}))
    if verb == "format:check"
    else (verb,)
    for verb in VERBS
}


def _mentioned_verbs(text: str) -> set[str]:
    """Which framework verbs the instruction file names, as whole tokens, in a spelling the spec accepts.

    The lookarounds keep ``format`` from being found inside ``format:check`` and ``test`` from being
    found inside ``tests``: a verb is named only when it stands as itself.
    """
    found: set[str] = set()
    for verb, spellings in _VERB_SPELLINGS.items():
        for spelling in spellings:
            pattern = re.compile(r"(?<![\w:-])" + re.escape(spelling) + r"(?![\w:-])")
            if pattern.search(text):
                found.add(verb)
                break
    return found


def _verb_binding_surface(resolved: dict) -> VerbSurface:
    return VerbSurface(
        verbs=tuple(
            VerbEntry(
                verb=v,
                resolved=v in resolved,
                runner=resolved[v].runner if v in resolved else None,
                command=resolved[v].command if v in resolved else None,
            )
            for v in VERBS
        ),
        resolved_count=len(resolved),
        missing=tuple(v for v in VERBS if v not in resolved),
    )


def check_agt05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    named = _mentioned_verbs(text)
    missing_names = [v for v in VERBS if v not in named]
    names_complete = not missing_names

    # Resolution half. With no runner manifest the resolution evidence is *unavailable*, not
    # negative: CMD-01 reports UNKNOWN in that case too, so this check degrades rather than piling
    # a second failure onto an unrecognised ecosystem.
    if not runner_commands(inventory):
        if names_complete:
            return CheckOutcome(
                spec.id,
                spec.title,
                spec.tier,
                spec.severity,
                spec.phase,
                Verdict.PARTIAL,
                spec.status,
                summary=f"all {len(VERBS)} verbs named, but no runner defines them",
                data=_verb_binding_surface({}),
                findings=[
                    Finding(
                        check=spec.id,
                        severity=Severity.DEGRADER,
                        phase=spec.phase,
                        verdict=Verdict.PARTIAL,
                        statement=statement(
                            "run the named verbs",
                            f"{name or 'the instruction file'} names every verb but no runner manifest defines them",
                        ),
                        evidence=[Evidence(name)] if name else [],
                        remediation="Add the verbs to a runner (package.json scripts, "
                        "a Makefile, a Taskfile) so the names execute.",
                    )
                ],
            )
        return _unknown(
            spec, "no verb runner and no complete verb list to resolve; CMD-01 owns the missing-runner finding"
        )

    resolved = resolve_verbs(inventory, stack)
    missing_resolution = [v for v in VERBS if v not in resolved]
    resolves_complete = not missing_resolution

    if names_complete and resolves_complete:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.PASS,
            spec.status,
            summary=f"all {len(VERBS)} verbs named in {name or 'the entry file'} and resolved on a runner",
            data=_verb_binding_surface(resolved),
        )

    verdict = Verdict.PARTIAL if (names_complete or resolves_complete) else Verdict.FAIL
    because = []
    if missing_names:
        because.append(f"not named: {', '.join(missing_names)}")
    if missing_resolution:
        because.append(f"not resolved: {', '.join(missing_resolution)}")
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary="; ".join(because),
        data=_verb_binding_surface(resolved),
        findings=[
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=verdict,
                statement=statement("use the project's own commands instead of inventing them", "; ".join(because)),
                remediation="List all seven verbs in AGENTS.md and define each on one "
                "runner so the instruction and the manifest agree.",
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ROOT, Reads, What, _at, _runners

    return Reads(
        where=(
            *_at(ROOT, "AGENTS.md", "CLAUDE.md"),
            *_runners(),
        ),
        what=What(
            "word-list",
            (
                "format",
                "format:check",
                "lint",
                "typecheck",
                "test",
                "check",
                "security",
            ),
        ),
        binding="file",
        threshold="all seven named and resolved",
        note=(
            "Each verb must stand as a whole token (format inside format:check does not count). format:check "
            "also counts as format-check or formatCheck, the spellings spec/command-surface.md accepts; no "
            "other script name counts. The resolution half reads the runner manifests as CMD-01 does."
        ),
    )
