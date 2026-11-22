# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""SEC-03: Ignore patterns cover secret shapes."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.ignore import IgnoreRule, decide_path
from audit.rules.checks._common import scoped_rules, tracked_and_ignored
from audit.rules.payloads import SecretShape, SecretShapes
from audit.rules.checks.sec._shared import _MAX_SECRET_FILES, _gaps, _outcome, _shape_coverage, _shapes_payload

SPEC = declare("SEC-03", "Ignore patterns cover secret shapes", "B", Severity.DEGRADER)


#: The ignore-rule shapes SEC-03 requires, as (label, representative path).
_SECRET_SHAPES: tuple[tuple[str, str], ...] = (
    ("dotenv", ".env"),
    ("dotenv variant", ".env.local"),
    ("ssh private key", "id_rsa"),
    ("PEM", "server.pem"),
    ("key", "server.key"),
    ("PKCS#12", "server.p12"),
    ("PFX", "server.pfx"),
    ("keystore", "app.keystore"),
    ("certificate (.crt)", "server.crt"),
    ("certificate (.cer)", "server.cer"),
    ("AWS credentials", ".aws/credentials"),
)

#: Suggested `.gitignore` entry per shape, surfaced in the report so the fix is concrete.
_SECRET_SHAPE_SUGGEST: dict[str, str] = {
    "dotenv": ".env",
    "dotenv variant": ".env.*",
    "ssh private key": "id_rsa*",
    "PEM": "*.pem",
    "key": "*.key",
    "PKCS#12": "*.p12",
    "PFX": "*.pfx",
    "keystore": "*.keystore",
    "certificate (.crt)": "*.crt",
    "certificate (.cer)": "*.cer",
    "AWS credentials": ".aws/*",
}

#: The shapes SEC-03 calls key material when a tracked file matches one past an ignore rule: every shape of
#: :data:`_SECRET_SHAPES` but the dotenv ones, which are SEC-01's. Each is matched by its suggested ignore entry, at
#: any depth (``.aws/*`` is read as ``**/.aws/*``), so the two lists cannot drift apart.
_KEY_MATERIAL_RULES: tuple[tuple[str, IgnoreRule], ...] = tuple(
    (label, IgnoreRule(pattern=("**/" + glob) if "/" in glob else glob, source="SEC-03"))
    for label, glob in _SECRET_SHAPE_SUGGEST.items()
    if label not in {"dotenv", "dotenv variant"}
)


def _key_material(rel: str) -> str | None:
    """The key shape (:data:`_KEY_MATERIAL_RULES`) a path's name matches, or ``None``."""
    for label, rule in _KEY_MATERIAL_RULES:
        if decide_path(rel, [rule]).ignored:
            return label
    return None


# ===========================================================================
# SEC-03 — ignore patterns cover secret shapes
# ===========================================================================


def check_sec03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    rules = scoped_rules(target, inventory)
    no_rules_shapes = SecretShapes(
        shapes=tuple(
            SecretShape(label=label, probe=sample, suggested=_SECRET_SHAPE_SUGGEST.get(label, ""), covered=False)
            for label, sample in _SECRET_SHAPES
        ),
        missing=tuple(label for label, _sample in _SECRET_SHAPES),
    )
    if not rules:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no ignore rules exist",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.FAIL,
                    statement=statement(
                        "rely on the repository to keep secret shapes out",
                        "no .gitignore (or equivalent ignore file) exists",
                    ),
                    remediation="Add a .gitignore covering secrets (.env*, *.pem, *.key, *.p12, "
                    "*.pfx, *.keystore, id_rsa*, *.crt, *.cer, .aws/*).",
                )
            ],
            data=no_rules_shapes,
        )

    covered, root_only, missing = _shape_coverage(rules, _SECRET_SHAPES)
    shapes = _shapes_payload(rules, _SECRET_SHAPES, _SECRET_SHAPE_SUGGEST)
    detail = f"covered: {', '.join(covered)}" if covered else "no secret shapes covered"
    committed = _committed_key_material(target, inventory, rules)
    if not missing and not root_only and not committed:
        return _outcome(spec, Verdict.PASS, detail, data=shapes)

    findings: list[Finding] = []
    summary = [detail]
    verdict = Verdict.PASS
    if missing or root_only:
        verdict = Verdict.PARTIAL if covered or root_only else Verdict.FAIL
        summary.append(_gaps(root_only, missing))
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=verdict,
                statement=statement(
                    "trust that secret shapes cannot be committed",
                    f"ignore rules are incomplete ({_gaps(root_only, missing)})",
                ),
                evidence=[Evidence(rule.source, note=rule.pattern) for rule in rules[:8]],
                remediation="Add the missing shapes to .gitignore — for example `.env.*`, `*.pem`, "
                "`*.key`, `*.p12`, `*.pfx`, `*.keystore`, `id_rsa*`, `*.crt`, `*.cer`, "
                "`.aws/*`.",
            )
        )
    if committed:
        verdict = Verdict.FAIL
        paths = [rel for rel, _label in committed]
        summary.append(f"tracked although ignored: {', '.join(paths[:_MAX_SECRET_FILES])}")
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "trust that the ignore rules kept key material out of history",
                    f"{len(paths)} key file(s) an ignore rule matches are tracked by git",
                ),
                evidence=[Evidence(rel, note=label) for rel, label in committed[:_MAX_SECRET_FILES]],
                path=paths[0],
                remediation="Untrack the key file (git rm --cached), keep its ignore rule, and rotate the key "
                "or certificate it held.",
            )
        )
    return _outcome(spec, verdict, "; ".join(summary), findings, data=shapes)


def _committed_key_material(target, inventory, rules: list[IgnoreRule]) -> list[tuple[str, str]]:
    """``(path, shape)`` for each tracked file an ignore rule matches whose name is a key shape (issue #12).

    Empty when git cannot report the tracked set: the coverage half of SEC-03 still stands on its own.
    """
    return [
        (rel, label)
        for rel in tracked_and_ignored(target, inventory, rules) or []
        if (label := _key_material(rel)) is not None
    ]
