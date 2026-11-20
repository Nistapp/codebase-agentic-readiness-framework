# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Stage S8 — Tier-C probe runner.

Executing a repository's own commands executes that repository's code. That is a supply-chain
decision, and this module never makes it on the operator's behalf (ADR-0002):

* disabled unless the caller passes an explicit verb allow-list
* never installs anything
* one timeout per probe, and the timeout itself is recorded as evidence
* captured output is redacted for credential shapes **at capture time**, never at render time
* only verbs the rule pack declares read-only are eligible
* a plan may name directories inside the target to put first on ``PATH`` (``node_modules/.bin``), the way
  the target's own runner does; nothing else in the environment changes
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

#: Verbs that mutate the working tree or the environment. Never probe-eligible.
MUTATING_VERBS = frozenset({"format", "install", "clean", "build"})

#: The keyword-assignment pattern. The keyword may sit inside a compound name joined by ``_`` or ``-``
#: (``GITHUB_TOKEN``, ``DB_PASSWORD``, ``AWS_SECRET_ACCESS_KEY``, ``client_secret``, ``x-api-key``), but it must be
#: a whole segment and the name must be assigned with ``:`` or ``=`` (a JSON key's closing quote may come between):
#: prose such as ``passwords must be rotated``, ``token count: 5``, ``tokens: 5`` and ``max_tokens: 5`` is left
#: alone. A name such as ``TOKEN_URL=`` is redacted too: hiding a harmless value costs less than showing a credential.
#: The value is a quoted string up to its closing quote on that line (``password = "two words"``), or to the end of
#: the line when it has none, or else one run of non-space characters; ``Bearer`` before it is part of the value.
_KEYWORD_ASSIGNMENT = (
    r"(?i)(?<![A-Za-z0-9])(?:[A-Za-z0-9]+[_-])*(?:api[_-]?key|secret|token|password|passwd|pwd)"
    r"(?:[_-][A-Za-z0-9]+)*(?![A-Za-z0-9])[\"']?[ \t]*[:=][ \t]*(?!\[REDACTED\])"
    r"(?:Bearer[ \t]+)?(?:\"[^\"\n]*\"?|'[^'\n]*'?|\S+)"
)

#: A whole PEM private key, from its BEGIN line through its END line. A key cut off by the end of the output (a
#: timeout, a crash) is redacted to the end. Read one line at a time, as ``SEC-02`` reads a file, the pattern still
#: matches the BEGIN line.
_PEM_PRIVATE_KEY = r"(?s)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"

#: ``SEC-02`` and the report validator read this tuple too. The validator names a pattern by its place here
#: ("redaction pattern 5"), so a new pattern goes at the end.
REDACTION_PATTERNS = (
    re.compile(_KEYWORD_ASSIGNMENT),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(_PEM_PRIVATE_KEY),
    re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9._\-]{16,}"),
    # Slack tokens: bot (xoxb-), user (xoxp-), app-level (xapp-) and the other xox kinds.
    re.compile(r"\b(?:xox[abposr]|xapp)-[A-Za-z0-9-]{10,}"),
)

#: The order ``redact()`` applies the patterns in, so one secret counts once: the PEM block first, because a
#: keyword before it (``secret: -----BEGIN ...``) would take the BEGIN line and leave the body; then the keyword,
#: whose value may itself have one of the other shapes.
_REDACT_ORDER = (REDACTION_PATTERNS[4], REDACTION_PATTERNS[0], *REDACTION_PATTERNS[1:4], *REDACTION_PATTERNS[5:])

OUTPUT_TAIL_LINES = 40


@dataclass
class ProbeResult:
    verb: str
    command: list[str]
    exit_code: int | None
    duration_s: float
    timed_out: bool = False
    output_tail: str = ""
    refused_reason: str | None = None
    redactions: int = 0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.refused_reason


@dataclass
class ProbePlan:
    verb: str
    command: list[str]
    read_only: bool = True
    #: Directories relative to the probe's ``cwd``, put first on ``PATH`` in this order.
    path_prepend: tuple[str, ...] = ()


def _probe_env(plan: ProbePlan, cwd: Path) -> dict[str, str] | None:
    """The environment for ``plan``: the caller's, with ``path_prepend`` first on ``PATH``; ``None`` keeps it as is."""
    if not plan.path_prepend:
        return None
    env = dict(os.environ)
    first = [str(cwd / rel) for rel in plan.path_prepend]
    env["PATH"] = os.pathsep.join([*first, env["PATH"]] if env.get("PATH") else first)
    return env


def redact(text: str) -> tuple[str, int]:
    """Redact credential-shaped substrings. Returns (clean_text, redaction_count)."""
    count = 0
    for pattern in _REDACT_ORDER:
        text, n = pattern.subn("[REDACTED]", text)
        count += n
    return text, count


def eligible(plan: ProbePlan, allow: tuple[str, ...]) -> tuple[bool, str | None]:
    if plan.verb not in allow:
        return False, f"verb {plan.verb!r} not in --allow-probe list"
    if plan.verb in MUTATING_VERBS:
        return False, f"verb {plan.verb!r} is declared mutating and is never probe-eligible"
    if not plan.read_only:
        return False, f"verb {plan.verb!r} is not declared read-only by its rule pack"
    return True, None


def run_plan(plan: ProbePlan, *, allow: tuple[str, ...], cwd: Path, timeout: int = 300) -> ProbeResult:
    """Run one probe. Refusals are recorded as evidence, never as exceptions."""
    permitted, reason = eligible(plan, allow)
    if not permitted:
        return ProbeResult(plan.verb, plan.command, None, 0.0, refused_reason=reason)

    started = time.monotonic()
    try:
        proc = subprocess.run(
            plan.command, cwd=str(cwd), env=_probe_env(plan, cwd), text=True, capture_output=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        clean, redactions = redact(partial)
        return ProbeResult(
            plan.verb,
            plan.command,
            None,
            time.monotonic() - started,
            timed_out=True,
            output_tail="\n".join(clean.splitlines()[-OUTPUT_TAIL_LINES:]),
            redactions=redactions,
        )
    except OSError as exc:
        return ProbeResult(
            plan.verb, plan.command, None, time.monotonic() - started, refused_reason=f"could not execute: {exc}"
        )

    combined = (proc.stdout or "") + (proc.stderr or "")
    clean, redactions = redact(combined)
    return ProbeResult(
        plan.verb,
        plan.command,
        proc.returncode,
        time.monotonic() - started,
        output_tail="\n".join(clean.splitlines()[-OUTPUT_TAIL_LINES:]),
        redactions=redactions,
    )


@dataclass
class ProbeSession:
    """Runs at most one probe per verb, and only what the operator permitted."""

    cwd: Path
    allow: tuple[str, ...] = ()
    timeout: int = 300
    enabled: bool = False
    results: list[ProbeResult] = field(default_factory=list)
    #: ``--no-user-config`` clears this: the IDX checks then read nothing from ``$HOME``.
    user_config: bool = True
    #: Every path outside the target a check read, for the report's provenance.
    user_reads: list[str] = field(default_factory=list)

    def note_user_read(self, path: object) -> None:
        text = str(path)
        if text not in self.user_reads:
            self.user_reads.append(text)

    def run(self, plan: ProbePlan) -> ProbeResult:
        if not self.enabled:
            result = ProbeResult(
                plan.verb, plan.command, None, 0.0, refused_reason="probes disabled (pass --run-gates)"
            )
            self.results.append(result)
            return result
        result = run_plan(plan, allow=self.allow, cwd=self.cwd, timeout=self.timeout)
        self.results.append(result)
        return result
