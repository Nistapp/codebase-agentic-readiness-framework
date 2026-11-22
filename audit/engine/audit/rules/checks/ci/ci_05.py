# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CI-05: Workflow files are linted."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.stack import LOCKFILE_NAMES
from audit.scan import Kind
from audit.rules.checks.ci._shared import _finding, _outcome, _unknown, _workflows

SPEC = declare("CI-05", "Workflow files are linted", "B", Severity.DEGRADER)


#: CI-05: the linters that understand each provider's workflow files. A pattern is matched against
#: one line of text; pre-commit hook ids from check-jsonschema are listed so a hook config counts.
_WORKFLOW_LINTERS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    provider: tuple((name, re.compile(pattern)) for name, pattern in linters)
    for provider, linters in (
        (
            "github",
            (
                ("actionlint", r"\bactionlint\b"),
                ("zizmor", r"\bzizmor\b"),
                ("check-jsonschema", r"vendor\.github-workflows|\bcheck-github-workflows\b"),
            ),
        ),
        (
            "gitlab",
            (
                ("check-jsonschema", r"vendor\.gitlab-ci|\bcheck-gitlab-ci\b"),
                ("glab ci lint", r"\bglab\s+ci\s+lint\b"),
            ),
        ),
        ("azure", (("check-jsonschema", r"vendor\.azure-pipelines|\bcheck-azure-pipelines\b"),)),
        (
            "circleci",
            (
                ("check-jsonschema", r"vendor\.circle-ci|\bcheck-circle-ci\b"),
                ("circleci config validate", r"\bcircleci\s+config\s+validate\b"),
            ),
        ),
        ("buildkite", (("check-jsonschema", r"vendor\.buildkite|\bcheck-buildkite"),)),
    )
}

#: CI-05: file kinds that make up the local surface (runner manifests, build files, hook configs,
#: scripts, extension-less files such as `.husky/pre-commit` and `justfile`). Docs and sources never count.
_LOCAL_SURFACE_KINDS: tuple[Kind, ...] = (Kind.MANIFEST, Kind.BUILD, Kind.CONFIG, Kind.SCRIPT, Kind.OTHER)

#: CI-05: files that name a tool without running it — lockfiles and dependency-update configs. Never local evidence.
_NOT_A_SURFACE: frozenset[str] = LOCKFILE_NAMES | frozenset(
    {
        "dependabot.yml",
        "dependabot.yaml",
        "renovate.json",
        ".renovaterc",
        ".renovaterc.json",
    }
)


# ===========================================================================
# CI-05 — workflow files are linted
# ===========================================================================


def _local_linter_hits(inventory, provider: str, workflow_rels: set[str]) -> list[tuple[str, int, str]]:
    """``(rel, line, linter)`` for each local-surface line that names one of the provider's linters."""
    hits: set[tuple[str, int, str]] = set()
    for name, pattern in _WORKFLOW_LINTERS[provider]:
        for rel, line, _text in inventory.grep(pattern, kinds=_LOCAL_SURFACE_KINDS):
            if rel not in workflow_rels and rel.rsplit("/", 1)[-1] not in _NOT_A_SURFACE:
                hits.add((rel, line, name))
    return sorted(hits)


def _ci_linter_hits(inventory, provider: str, workflow_rels: set[str]) -> list[tuple[str, int, str]]:
    """``(rel, line, linter)`` for each workflow line (a `run:` step or a `uses:` action) naming a linter."""
    hits: set[tuple[str, int, str]] = set()
    for rel in sorted(workflow_rels):
        for number, text in enumerate((inventory.read(rel) or "").splitlines(), start=1):
            for name, pattern in _WORKFLOW_LINTERS[provider]:
                if pattern.search(text):
                    hits.add((rel, number, name))
    return sorted(hits)


def check_ci05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    workflows = _workflows(inventory)
    if not workflows:
        return _unknown(spec, "no workflow file, so there is nothing to lint (CI-01 reports the absence)")

    workflow_rels = {rel for _provider, rel in workflows}
    by_provider: dict[str, list[str]] = {}
    for provider, rel in workflows:
        by_provider.setdefault(provider, []).append(rel)
    lintable = [provider for provider in by_provider if provider in _WORKFLOW_LINTERS]
    if not lintable:
        names = ", ".join(sorted(by_provider))
        return _unknown(spec, f"no offline workflow linter is known for {names}")

    local: dict[str, list[tuple[str, int, str]]] = {}
    ci_only: dict[str, list[tuple[str, int, str]]] = {}
    for provider in lintable:
        local[provider] = _local_linter_hits(inventory, provider, workflow_rels)
        ci_only[provider] = _ci_linter_hits(inventory, provider, workflow_rels)

    def seen(hits: list[tuple[str, int, str]]) -> str:
        return ", ".join(sorted({f"{name} ({rel})" for rel, _line, name in hits}))

    detail = "; ".join(
        f"{provider}: local {seen(local[provider]) or 'none'}, CI {seen(ci_only[provider]) or 'none'}"
        for provider in lintable
    )
    unlinted = [provider for provider in lintable if not local[provider] and not ci_only[provider]]
    if len(unlinted) == len(lintable):
        return _outcome(
            spec,
            Verdict.FAIL,
            detail,
            [
                _finding(
                    spec,
                    "check a workflow change before it is pushed",
                    f"no linter for the {provider} workflow files runs locally or in CI",
                    Verdict.FAIL,
                    [Evidence(rel) for rel in by_provider[provider]],
                    "Add a workflow linter to the local command surface or a hook and run it in CI "
                    "(GitHub: actionlint and zizmor; other providers: check-jsonschema with the "
                    "provider's built-in schema).",
                    path=by_provider[provider][0],
                )
                for provider in unlinted
            ],
        )

    not_local = [provider for provider in lintable if not local[provider]]
    if not not_local:
        return _outcome(spec, Verdict.PASS, detail)

    findings = []
    for provider in not_local:
        in_ci = bool(ci_only[provider])
        findings.append(
            _finding(
                spec,
                "check a workflow change before it is pushed",
                (
                    f"the {provider} workflow linter runs only in CI"
                    if in_ci
                    else f"no linter for the {provider} workflow files runs locally or in CI"
                ),
                Verdict.PARTIAL,
                [Evidence(rel, line=line, note=name) for rel, line, name in ci_only[provider]]
                or [Evidence(rel) for rel in by_provider[provider]],
                "Expose the workflow linter on the local command surface or in a hook, so an agent "
                "can run the same check before it pushes.",
                path=by_provider[provider][0],
            )
        )
    return _outcome(spec, Verdict.PARTIAL, detail, findings)
