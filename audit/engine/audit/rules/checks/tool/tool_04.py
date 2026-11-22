# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TOOL-04: Dependency / security scan verb."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import follow_makefile, resolve_verbs, runner_commands, runner_target
from audit.stack import CI_PROVIDERS
from audit.rules.checks.tool._shared import _finding, _outcome, _recognised, _unknown

SPEC = declare("TOOL-04", "Dependency / security scan verb", "A", Severity.DEGRADER)


#: Dependency-audit invocations. The verb is evidence; it is never executed.
_AUDIT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?audit\b",
        r"\bpip-audit\b",
        r"\bpip\s+audit\b",
        r"\bsafety\s+check\b",
        r"\bosv-scanner\b",
        r"\bcargo\s+audit\b",
        r"\bgovulncheck\b",
        r"\bsnyk\b",
        r"\btrivy\b",
        r"\bgrype\b",
        r"\bbundler-audit\b",
        r"\bbundle\s+audit\b",
        r"\bcomposer\s+audit\b",
        r"\baudit-ci\b",
        r"\bdotnet\s+list\s+package\b[^&|;]*--vulnerable\b",
    )
)


# ===========================================================================
# TOOL-04 — dependency / security scan verb
# ===========================================================================


def _is_audit_command(command: str) -> bool:
    return any(pattern.search(command) for pattern in _AUDIT_PATTERNS)


def _makefile_audit(inventory, command: str) -> tuple[str, str] | None:
    """The first line a root-Makefile verb's ``command`` runs that is a dependency audit (``follow_makefile``)."""
    return follow_makefile(inventory, command, _is_audit_command)


#: CI actions and templates that run a dependency audit. Matched on the ``uses:`` (or GitLab ``template:``) value.
_CI_AUDIT_ACTIONS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"\buses:\s*['\"]?google/osv-scanner-action\b",
        r"\buses:\s*['\"]?actions/dependency-review-action\b",
        r"\buses:\s*['\"]?aquasecurity/trivy-action\b",
        r"\buses:\s*['\"]?snyk/actions\b",
        r"\buses:\s*['\"]?anchore/scan-action\b",
        r"\buses:\s*['\"]?pypa/gh-action-pip-audit\b",
        r"\btemplate:\s*['\"]?(?:Jobs/|Security/)?Dependency-Scanning\b",
    )
)


def _audit_in(command: str, inventory) -> bool:
    """True when ``command`` runs a dependency audit, directly or through the root Makefile."""
    return _is_audit_command(command) or _makefile_audit(inventory, command) is not None


def _ci_audit_steps(inventory) -> list[tuple[str, int, str]]:
    """``(workflow, line, what)`` for each CI line that runs a dependency audit: a scanner command, a scanner action
    or template, or a runner target whose command runs one."""
    targets: dict[str, str] = {}
    for _runner, commands in reversed(runner_commands(inventory)):
        targets.update(commands)
    hits: list[tuple[str, int, str]] = []
    for globs in CI_PROVIDERS.values():
        for rel in sorted(inventory.match(*globs)):
            for number, line in enumerate((inventory.read(rel) or "").splitlines(), start=1):
                if line.lstrip().startswith("#"):
                    continue
                if _is_audit_command(line) or any(pattern.search(line) for pattern in _CI_AUDIT_ACTIONS):
                    hits.append((rel, number, line.strip()[:120]))
                    continue
                target = runner_target(line)
                if target in targets and _audit_in(targets[target], inventory):
                    hits.append((rel, number, f"{target} ({targets[target][:80]})"))
    return hits


def _local_audit(inventory, stack) -> tuple[list[str], object]:
    """The local verbs that run a dependency audit, as summary lines, and the ``security`` binding (or ``None``)."""
    bindings = resolve_verbs(inventory, stack)
    found = [f"{verb} -> {b.command}" for verb, b in sorted(bindings.items()) if _is_audit_command(b.command)]
    if not found:
        for verb, binding in sorted(bindings.items()):
            if binding.runner != "Makefile":
                continue
            hit = _makefile_audit(inventory, binding.command)
            if hit:
                where, line = hit
                through = f" (target {where})" if where else ""
                found.append(f"{verb} -> {binding.command}; runs `{line}`{through}")
    return found, bindings.get("security")


def check_tool04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    local, security = _local_audit(inventory, stack)
    ci_steps = _ci_audit_steps(inventory)
    ci_seen = "; ".join(f"{rel}:{line} {what}" for rel, line, what in ci_steps[:3])

    if local and ci_steps:
        return _outcome(spec, Verdict.PASS, f"{'; '.join(local)}; CI: {ci_seen}")
    if local:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"{'; '.join(local)}; CI runs no dependency audit",
            [
                _finding(
                    spec,
                    "rely on every change being checked for a known vulnerability",
                    "the dependency audit runs only when someone runs the verb; no CI step runs it",
                    Verdict.PARTIAL,
                    [
                        Evidence(rel)
                        for rel in sorted({r for globs in CI_PROVIDERS.values() for r in inventory.match(*globs)})
                    ]
                    or [Evidence(runner) for runner, _cmds in runner_commands(inventory)],
                    "Run the same verb in CI as its own job, beside the check job (it may need the network).",
                )
            ],
        )
    if ci_steps:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"CI runs a dependency audit ({ci_seen}) but no local verb does",
            [
                _finding(
                    spec,
                    "learn about a vulnerable dependency before it pushes",
                    "only CI runs a dependency audit; no local verb runs it",
                    Verdict.PARTIAL,
                    [Evidence(rel, line=line, note=what) for rel, line, what in ci_steps],
                    "Add a security verb that runs the same scanner, and have CI run that verb.",
                )
            ],
        )

    if security is not None:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"security verb on {security.runner} runs no dependency audit ({security.command})",
            [
                _finding(
                    spec,
                    "know whether a dependency carries a known vulnerability",
                    "a security verb exists but it does not run a dependency-audit check",
                    Verdict.PARTIAL,
                    [Evidence(security.runner, note=security.command)],
                    "Make the security verb run a dependency audit (npm audit, pip-audit, osv-scanner, "
                    "cargo audit, govulncheck, snyk), and run that verb in CI.",
                )
            ],
        )

    if _recognised(stack, inventory):
        return _outcome(
            spec,
            Verdict.FAIL,
            "no verb runs a dependency audit",
            [
                _finding(
                    spec,
                    "know whether a dependency carries a known vulnerability",
                    "no resolvable verb runs a dependency-audit check",
                    Verdict.FAIL,
                    [Evidence(runner) for runner, _cmds in runner_commands(inventory)],
                    "Add a dependency-audit verb (npm audit, pip-audit, osv-scanner, cargo audit, govulncheck, "
                    "snyk) and run it in CI.",
                )
            ],
        )

    return _unknown(
        spec,
        "no recognised ecosystem, runner manifest or dependency-audit verb, so a dependency scan cannot be ruled out",
    )
