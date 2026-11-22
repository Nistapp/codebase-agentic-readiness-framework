# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""SEC-01: .env untracked and ignored."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import scoped_rules, tracked_and_ignored, tracked_in_scope
from audit.rules.checks.sec._shared import (
    _ENV_TEMPLATE_BASENAMES,
    _gaps,
    _is_template_file,
    _outcome,
    _shape_coverage,
    _shapes_payload,
)

SPEC = declare("SEC-01", ".env untracked and ignored", "B", Severity.BLOCKER)


#: The `.env` shapes SEC-01 requires the ignore rules to cover.
_ENV_SHAPE_PROBES: tuple[tuple[str, str], ...] = (
    ("dotenv", ".env"),
    ("dotenv variant", ".env.local"),
)

_ENV_SHAPE_SUGGEST: dict[str, str] = {
    "dotenv": ".env",
    "dotenv variant": ".env.*",
}


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _is_env_name(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    if base in _ENV_TEMPLATE_BASENAMES:
        return False
    return base == ".env" or base.startswith(".env.")


def _is_env_like_name(rel: str) -> bool:
    """Whether a tracked file an ignore rule also matches has an environment-file name (issue #12).

    The basename starts with ``.env`` (``.env``, ``.env.prod``, ``.envrc``), ends with ``.env`` (``prod.env``) or
    starts with ``env.`` (``env.prod``), and is not a committed template (:func:`_is_template_file`). This wider
    name rule applies only to a tracked file past an ignore rule; any other tracked file counts only by
    :func:`_is_env_name`.
    """
    if _is_template_file(rel):
        return False
    base = rel.rsplit("/", 1)[-1]
    return base.startswith(".env") or base.endswith(".env") or base.startswith("env.")


# ===========================================================================
# SEC-01 — .env untracked and ignored
# ===========================================================================


def check_sec01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    rules = scoped_rules(target, inventory)
    covered, root_only, missing = _shape_coverage(rules, _ENV_SHAPE_PROBES)
    ignore_ok = not missing and not root_only
    shapes = _shapes_payload(rules, _ENV_SHAPE_PROBES, _ENV_SHAPE_SUGGEST)

    tracked = tracked_in_scope(target, inventory)
    if tracked is None:
        ignore_note = "ignore rules cover .env" if ignore_ok else f"ignore rules: {_gaps(root_only, missing)}"
        return _unknown(
            spec, f"git could not report tracked files, so a tracked .env cannot be ruled out ({ignore_note})"
        )

    ignored = tracked_and_ignored(target, inventory, rules) or []
    tracked_env = sorted({rel for rel in tracked if _is_env_name(rel)} | {r for r in ignored if _is_env_like_name(r)})
    if tracked_env:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"tracked: {', '.join(tracked_env)}",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "read the repository without a credential leak", f"{', '.join(tracked_env)} is tracked by git"
                    ),
                    evidence=[Evidence(rel) for rel in tracked_env],
                    path=tracked_env[0],
                    remediation="Untrack the environment file (git rm --cached), add its shape to "
                    ".gitignore, and rotate any value it held.",
                ),
            ],
            data=shapes,
        )

    if ignore_ok:
        return _outcome(spec, Verdict.PASS, "no tracked .env and ignore rules cover the shape", data=shapes)

    return _outcome(
        spec,
        Verdict.PARTIAL,
        f"no tracked .env, but ignore rules are incomplete: {_gaps(root_only, missing)}",
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "trust that a future .env stays out of history",
                    f"ignore rules are incomplete ({_gaps(root_only, missing)})",
                ),
                evidence=[Evidence(rule.source, note=rule.pattern) for rule in rules[:8]],
                remediation="Add the .env shape without a leading slash (for example `.env` and `.env.*`) to "
                ".gitignore so an environment file cannot be committed by accident, at any depth.",
            ),
        ],
        data=shapes,
    )
