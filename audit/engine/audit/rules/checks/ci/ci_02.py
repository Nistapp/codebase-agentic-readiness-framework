# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CI-02: Local↔CI parity."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.probes import MUTATING_VERBS
from audit.rules.checks._common import resolve_verbs
from audit.stack import VERBS
from audit.rules.checks.ci._shared import (
    _ASSIGNMENT_RE,
    _all_run_commands,
    _body_commands,
    _command_verb,
    _finding,
    _outcome,
    _unknown,
    _workflows,
)

SPEC = declare("CI-02", "Local↔CI parity", "B", Severity.BLOCKER)


#: The read-only verbs a CI pipeline may be expected to exercise (everything but a write verb).
READ_ONLY_VERBS: tuple[str, ...] = tuple(v for v in VERBS if v not in MUTATING_VERBS)
#: Programs that run a script file named as their first operand.
_SHELLS: frozenset[str] = frozenset({"bash", "sh", "zsh", "source", "."})


def _script_path(command: str, inventory) -> str | None:
    """The repository script a CI command runs (``scripts/ci/test.sh``, ``bash ./build.sh``), else ``None``.

    Only a shell script the inventory holds counts: a path with a ``/`` or a ``.sh``/``.bash`` name, run
    directly or through ``bash``/``sh``/``zsh``/``source``/``.``. Paths resolve from the repository root,
    where a CI step starts unless it sets a working directory.
    """
    words = [word for word in command.split() if not _ASSIGNMENT_RE.match(word)]
    if words and words[0] in _SHELLS:
        words = [word for word in words[1:] if not word.startswith("-")]
    if not words:
        return None
    rel = words[0].strip("'\"")
    while rel.startswith("./"):
        rel = rel[2:]
    if rel.startswith(("/", "$", "~")) or not ("/" in rel or rel.endswith((".sh", ".bash"))):
        return None
    return rel if inventory.has(rel) else None


def _script_commands(inventory, commands: list[tuple[str, int, str]]) -> list[tuple[str, int, str]]:
    """Every ``(script, line_no, command)`` inside the scripts the CI commands run, one level deep."""
    scripts = sorted({rel for _wf, _line, command in commands if (rel := _script_path(command, inventory))})
    out: list[tuple[str, int, str]] = []
    for rel in scripts:
        text = inventory.read(rel)
        if text:
            out.extend((rel, line, command) for line, command in _body_commands(list(enumerate(text.splitlines(), 1))))
    return out


# ===========================================================================
# CI-02 — local↔CI parity
# ===========================================================================


def check_ci02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    local = resolve_verbs(inventory, stack)
    if not local:
        return _unknown(spec, "no local verb resolves on any runner, so CI cannot be compared to it")

    workflows = _workflows(inventory)
    if not workflows:
        return _unknown(spec, "no workflow file, so there is no CI to compare (CI-01 reports the absence)")

    commands = _all_run_commands(inventory, workflows)
    commands += _script_commands(inventory, commands)
    ci_verbs = {verb for _rel, _line, command in commands if (verb := _command_verb(command)) is not None}
    if not ci_verbs:
        return _unknown(
            spec,
            "no CI command maps to a framework verb, directly or one script deep, so parity cannot be judged "
            f"(local verbs: {', '.join(sorted(local))})",
        )

    extra = sorted(verb for verb in ci_verbs if verb not in local)
    missing = sorted(verb for verb in READ_ONLY_VERBS if verb in local and verb not in ci_verbs)

    detail = (
        f"CI verbs: {', '.join(sorted(ci_verbs))}; local read-only verbs not exercised: {', '.join(missing) or 'none'}"
    )

    if extra:
        return _outcome(
            spec,
            Verdict.FAIL,
            detail,
            [
                _finding(
                    spec,
                    "run the same command surface locally that CI runs",
                    f"CI invokes framework verb(s) with no local definition: {', '.join(extra)}",
                    Verdict.FAIL,
                    [
                        Evidence(rel, line=line, note=command)
                        for rel, line, command in commands
                        if _command_verb(command) in extra
                    ],
                    "Define the missing verb(s) on the local runner, or stop invoking them from CI, so the "
                    "two surfaces agree.",
                )
            ],
        )

    return _outcome(spec, Verdict.PASS, detail)
