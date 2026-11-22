# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CMD-01: Seven verbs resolvable on one runner."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import makefile_errors, resolve_all_verbs, runner_commands
from audit.stack import VERBS
from audit.rules.payloads import VerbEntry, VerbSurface
from audit.rules.checks.cmd._shared import _ordered_runners, _outcome, _unknown

SPEC = declare("CMD-01", "Seven verbs resolvable on one runner", "B", Severity.BLOCKER)


# ===========================================================================
# CMD-01 — seven verbs resolvable on one runner
# ===========================================================================


def _makefile_parse_finding(spec, errors, severity: Severity) -> Finding:
    first = errors[0]
    return Finding(
        check=spec.id,
        severity=severity,
        phase=spec.phase,
        verdict=Verdict.FAIL,
        statement=statement(
            "run any verb through make",
            f"GNU Make refuses the Makefile at line {first.line} ({first.message}), so no target in it can run",
        ),
        evidence=[Evidence("Makefile", line=error.line, note=error.text) for error in errors],
        remediation="Escape the colon of a verb's name, `format\\:check:`, and define `format-check` as the alias, "
        "so that `make format:check` and `make format-check` both run. An unescaped `format:check:` is a "
        "static pattern rule, which needs a `%`.",
        path="Makefile",
    )


def check_cmd01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    declared = runner_commands(inventory)
    parse_errors = makefile_errors(inventory)
    if not declared and not parse_errors:
        return _unknown(
            spec,
            "no recognised verb runner (package.json, Makefile, Taskfile, "
            "pyproject, gradle, maven), so no verb can be resolved",
        )
    if not declared:
        first = parse_errors[0]
        return _outcome(
            spec,
            Verdict.FAIL,
            f"the Makefile does not parse (line {first.line}: {first.message}), so no verb on it can run",
            [_makefile_parse_finding(spec, parse_errors, spec.severity)],
            data=VerbSurface(
                verbs=tuple(VerbEntry(verb=verb, resolved=False, runner=None, command=None) for verb in VERBS),
                resolved_count=0,
                missing=tuple(VERBS),
            ),
        )

    bindings = resolve_all_verbs(inventory, stack)
    resolved = {verb: entries[0] for verb, entries in bindings.items()}
    missing = [verb for verb in VERBS if verb not in resolved]
    runners_used = _ordered_runners({binding.runner for entries in bindings.values() for binding in entries})

    detail = "; ".join(
        f"{verb} -> {resolved[verb].runner}" if verb in resolved else f"{verb} -> missing" for verb in VERBS
    )

    surface = VerbSurface(
        verbs=tuple(
            VerbEntry(
                verb=verb,
                resolved=verb in resolved,
                runner=resolved[verb].runner if verb in resolved else None,
                command=resolved[verb].command if verb in resolved else None,
            )
            for verb in VERBS
        ),
        resolved_count=len(resolved),
        missing=tuple(missing),
    )

    verdict = Verdict.PASS
    findings: list[Finding] = []
    if missing:
        verdict = Verdict.FAIL
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "run the standardized command surface literally",
                    f"{len(missing)} of {len(VERBS)} framework verbs are not defined on any runner "
                    f"({', '.join(missing)})",
                ),
                evidence=[Evidence(runner) for runner, _cmds in declared],
                remediation="Define every verb (format, format:check, lint, typecheck, test, check, "
                "security) as a script/target so an agent never has to invent a command.",
            )
        )
    elif len(runners_used) > 1:
        verdict = Verdict.PARTIAL
        findings.append(
            Finding(
                check=spec.id,
                severity=Severity.DEGRADER,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "find every verb on one runner",
                    f"verbs resolve across {len(runners_used)} runners "
                    f"({', '.join(runners_used)}), so no single runner is the contract",
                ),
                evidence=[Evidence(resolved[verb].runner, note=verb) for verb in VERBS],
                remediation="Keep one runner as the authority for all verbs; reduce any second runner "
                "to a delegation (see CMD-03).",
            )
        )
    if parse_errors:
        # Another runner carries the verbs, but a Makefile that cannot run is still a defect, so the
        # check is never a PASS beside one.
        verdict = Verdict.PARTIAL if verdict is Verdict.PASS else verdict
        findings.append(_makefile_parse_finding(spec, parse_errors, Severity.DEGRADER))
    return _outcome(spec, verdict, detail, findings, data=surface)
