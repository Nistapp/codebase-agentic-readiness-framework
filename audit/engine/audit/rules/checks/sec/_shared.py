# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Helpers that more than one SEC check uses."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Finding, Verdict
from audit.ignore import IgnoreRule, decide
from audit.rules.payloads import Payload, SecretShape, SecretShapes

#: Committed templates that legitimately hold key *names* without secrets.
_ENV_TEMPLATE_BASENAMES: frozenset[str] = frozenset(
    {
        ".env.example",
        ".env.sample",
        ".env.template",
        ".env.dist",
        ".env.defaults",
        "env.example",
    }
)

_MAX_SECRET_FILES = 25


def _outcome(
    spec, verdict: Verdict, summary: str = "", findings: list[Finding] | None = None, data: Payload | None = None
) -> CheckOutcome:
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=summary,
        data=data,
        findings=findings or [],
    )


def _is_template_file(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    return base in _ENV_TEMPLATE_BASENAMES or base.endswith((".example", ".sample", ".template", ".dist"))


def _path_covered(rel: str, rules: list[IgnoreRule]) -> bool:
    """Whether the rules ignore ``rel`` after every ``!`` exception, at the root and in a nested directory.

    A rule anchored with a leading ``/`` covers the root only (``/.env`` skips ``a/.env``); that is
    :func:`_root_only`. A rule that names a path with a slash inside it (``.aws/*``) is read as git reads it,
    anchored to the directory of its ignore file, and is credited as it always was.
    """
    return decide(rel, rules).ignored and (_nested_ignored(rel, rules) or not _leading_slash_rule(rel, rules))


def _nested_ignored(rel: str, rules: list[IgnoreRule]) -> bool:
    return decide("pkg/" + rel, rules).ignored


def _leading_slash_rule(rel: str, rules: list[IgnoreRule]) -> bool:
    rule = decide(rel, rules).rule
    return rule is not None and rule.pattern.startswith("/")


def _root_only(rel: str, rules: list[IgnoreRule]) -> bool:
    """Whether ``rel`` is covered only by a root-anchored rule (``/.env``), which skips the nested ``a/.env``."""
    return decide(rel, rules).ignored and not _path_covered(rel, rules)


def _shape_coverage(
    rules: list[IgnoreRule], probes: tuple[tuple[str, str], ...]
) -> tuple[list[str], list[str], list[str]]:
    """``(covered, root_only, missing)`` labels. Root-anchored rules cover the root, not nested files."""
    covered = [label for label, sample in probes if _path_covered(sample, rules)]
    root_only = [label for label, sample in probes if _root_only(sample, rules)]
    missing = [label for label, sample in probes if label not in covered and label not in root_only]
    return covered, root_only, missing


def _shapes_payload(
    rules: list[IgnoreRule], probes: tuple[tuple[str, str], ...], suggest: dict[str, str]
) -> SecretShapes:
    covered, root_only, missing = _shape_coverage(rules, probes)
    return SecretShapes(
        shapes=tuple(
            SecretShape(
                label=label,
                probe=sample,
                suggested=suggest.get(label, ""),
                covered=label in covered,
                root_only=label in root_only,
            )
            for label, sample in probes
        ),
        covered=tuple(covered),
        missing=tuple(missing),
        root_only=tuple(root_only),
    )


def _gaps(root_only: list[str], missing: list[str]) -> str:
    """The reason ignore coverage is incomplete, saying which shapes cover the root only."""
    parts = []
    if root_only:
        parts.append(
            f"root-anchored only: {', '.join(root_only)} (the rule covers the root, not nested files such as `a/.env`)"
        )
    if missing:
        parts.append(f"missing: {', '.join(missing)}")
    return "; ".join(parts)
