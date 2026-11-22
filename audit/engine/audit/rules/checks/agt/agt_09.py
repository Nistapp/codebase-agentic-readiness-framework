# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""AGT-09: Branch and release boundary declared."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import declared_branch_rules, entry_instruction_file
from audit.rules.checks.agt._shared import _unknown, _first_line

SPEC = declare("AGT-09", "Branch and release boundary declared", "B", Severity.DEGRADER)


# ---------------------------------------------------------------------------
# AGT-09 — branch and release boundary
# ---------------------------------------------------------------------------

_BRANCH_RE = re.compile(r"(?i)\b(branch(?:es|ing)?|main|dev|trunk)\b")
#: "release" is read broadly: an explicit restriction on pushing, tagging or publishing bounds what
#: an agent may release, so any of these counts as the release half of the boundary.
_RELEASE_RE = re.compile(r"(?i)\b(tag|release|publish|deploy|push)\b")


def _names_branch(text: str, branch: str) -> bool:
    """True when ``text`` names ``branch`` as a whole name: ``dev`` is not named by ``devops`` or ``dev/x``."""
    return re.search(rf"(?<![\w./-]){re.escape(branch)}(?![\w/-])", text) is not None


def check_agt09(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")

    branch_line = _first_line(text, _BRANCH_RE)
    release_line = _first_line(text, _RELEASE_RE)
    rules = declared_branch_rules(inventory)
    unnamed = [branch for branch in rules.literal_branches if not _names_branch(text, branch)]
    unnamed_why = (
        f"{', '.join(unnamed)} {'is' if len(unnamed) == 1 else 'are'} protected by the declared rules "
        f"({', '.join(rules.sources)}) but not named"
        if unnamed
        else ""
    )

    if branch_line and release_line and not unnamed:
        return CheckOutcome(
            spec.id,
            spec.title,
            spec.tier,
            spec.severity,
            spec.phase,
            Verdict.PASS,
            spec.status,
            summary="the branch model and the release boundary are stated",
        )
    if branch_line and release_line:
        verdict = Verdict.PARTIAL
        why = unnamed_why
    elif branch_line:
        verdict = Verdict.PARTIAL
        why = "the branch model is stated but nothing says whether an agent may tag or release"
    elif release_line:
        verdict = Verdict.PARTIAL
        why = "a release boundary is stated but the branches that exist are not"
    else:
        verdict = Verdict.FAIL
        why = "neither the branch model nor the release boundary is stated"
    if unnamed and why != unnamed_why:
        why = f"{why}; {unnamed_why}"

    evidence = [Evidence(name, line=line) for line in (branch_line, release_line) if line]
    if unnamed:
        evidence.extend(Evidence(source, note="declares a protected branch") for source in rules.sources)
    remediation = (
        "State the branches that exist (for example main and dev) and whether an agent may tag or publish a release."
    )
    if unnamed:
        remediation += f" Name {', '.join(unnamed)}, which the declared branch rules protect."
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=why,
        findings=[
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=verdict,
                statement=statement("know which branch to work on and whether it may cut a release", why),
                evidence=evidence,
                remediation=remediation,
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, ROOT, Reads, What, _at

    return Reads(
        where=(
            *_at(ROOT, "AGENTS.md", "CLAUDE.md"),
            *_at(GLOB, ".github/rulesets/**/*.json"),
            *_at(ANY_DEPTH, ".github/settings.yml"),
            *_at(GLOB, "**/*.tf"),
        ),
        what=What(
            "word-list",
            (
                "branch",
                "branches",
                "branching",
                "main",
                "dev",
                "trunk",
                "tag",
                "release",
                "publish",
                "deploy",
                "push",
            ),
        ),
        binding="file",
        threshold="a branch word, a release word and every protected branch named",
        note=(
            "Each literal branch the declared rules protect (ruleset JSON, the Settings app's branches:, "
            "Terraform protection resources) must stand as a whole word anywhere in the entry file. "
            ".github/settings.yml passes Inventory.has at any depth but is read at the root only."
        ),
    )
