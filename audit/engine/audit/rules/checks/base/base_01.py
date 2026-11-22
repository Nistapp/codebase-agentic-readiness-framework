# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""BASE-01: Baseline artifact exists."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.checks.base._shared import (
    _DOCS,
    _baseline_artifacts,
    _counting_tools,
    _finding,
    _outcome,
    _recognised,
    _unknown,
)

SPEC = declare("BASE-01", "Baseline artifact exists", "A", Severity.DEGRADER)


#: A documented baseline/suppression *mechanism* (BASE-01), distinct from a comparison step (BASE-03).
_DOC_BASELINE_RE = re.compile(
    r"(?i)(?:quality\s+baseline|baseline\s+(?:file|report|artifact|artefact|count|json)"
    r"|no[- ]new[- ]violations?|violation\s+budget"
    r"|suppress(?:ion|ed)?\s+(?:file|list|count))"
)


def _documented_baseline(inventory: Inventory) -> str | None:
    for rel in _DOCS:
        text = inventory.read(rel)
        if text and _DOC_BASELINE_RE.search(text):
            return rel
    return None


# ===========================================================================
# BASE-01 — baseline artifact exists
# ===========================================================================


def check_base01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    artifacts = _baseline_artifacts(inventory)
    documented = _documented_baseline(inventory)
    if artifacts or documented:
        evidence = artifacts or [documented or "<repository>"]
        return _outcome(
            spec,
            Verdict.PASS,
            f"baseline/suppression mechanism present: "
            f"{', '.join(evidence)}" + ("" if artifacts else f" (documented in {documented})"),
        )

    tools = _counting_tools(inventory, stack)
    if tools:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"quality tooling is configured but no baseline artifact is committed: {', '.join(tools[:6])}",
            [
                _finding(
                    spec,
                    "diff today's findings against an accepted baseline",
                    "quality tooling is configured but no baseline or suppression artifact is committed",
                    Verdict.PARTIAL,
                    [Evidence(rel) for rel in tools[:6]],
                    "Commit a baseline or suppression artifact (for example `baseline.json`, an "
                    "eslint/ruff baseline, or `.gitleaksignore`), or document the equivalent mechanism in "
                    "`AGENTS.md`.",
                )
            ],
        )

    if _recognised(inventory, stack):
        return _outcome(
            spec,
            Verdict.FAIL,
            "no baseline or suppression artifact",
            [
                _finding(
                    spec,
                    "distinguish pre-existing debt from new debt",
                    "no baseline or suppression artifact is committed",
                    Verdict.FAIL,
                    [Evidence("<repository>")],
                    "Commit a baseline/suppression artifact, or document the equivalent mechanism in `AGENTS.md`.",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem or configuration, so a baseline cannot be ruled out")


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, ROOT, Reads, What, _at, _runners

    return Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".eslint-baseline*",
                ".ruff-baseline*",
                ".mypy-baseline*",
                "baseline.json",
                "*baseline*.json",
                "*baseline*.xml",
                "coverage-baseline.*",
                "*.baseline",
                ".secrets.baseline",
                ".snyk",
                ".gitleaksignore",
            ),
            *_at(ROOT, "AGENTS.md", "CLAUDE.md", "setup.cfg", "tox.ini"),
            *_at(
                ANY_DEPTH,
                ".eslintrc*",
                "eslint.config.*",
                "biome.json",
                "biome.jsonc",
                ".ruff.toml",
                "ruff.toml",
                ".flake8",
                "pylintrc",
                ".pylintrc",
                "mypy.ini",
                ".mypy.ini",
                ".golangci.yml",
                ".golangci.yaml",
                "clippy.toml",
                ".gitleaks.toml",
                "sonar-project.properties",
                ".semgrep.yml",
                ".semgrep.yaml",
            ),
            *_runners(),
            *_at(
                ANY_DEPTH,
                "package.json",
                "pyproject.toml",
                "setup.py",
                "requirements*.txt",
                "Pipfile",
                "pom.xml",
                "build.gradle",
                "build.gradle.kts",
                "go.mod",
                "Cargo.toml",
                "Gemfile",
                "composer.json",
            ),
        ),
        what=What(
            "phrase",
            (
                "quality baseline",
                "baseline file",
                "baseline report",
                "baseline artifact",
                "baseline count",
                "baseline json",
                "no new violations",
                "violation budget",
                "suppression file",
                "suppression list",
                "suppression count",
            ),
        ),
        binding="file",
        note=(
            "A baseline name at any depth, or a mechanism phrase in the root AGENTS.md or CLAUDE.md, passes; "
            "the phrase words are joined by \\s+ so they may span lines. The counting-tool configs, root "
            "pyproject.toml, setup.cfg and tox.ini and the lint, typecheck and security verbs only give "
            "PARTIAL. With no detected ecosystem, a project manifest at any depth still makes the check apply."
        ),
    )
