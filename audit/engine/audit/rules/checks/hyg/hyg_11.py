# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""HYG-11: Branch protection declared as code."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import BranchRules, declared_branch_rules
from audit.scan import Inventory
from audit.stack import CI_PROVIDERS
from audit.rules.checks.hyg._shared import _DOC_SUFFIXES, _basename, _finding, _outcome

SPEC = declare("HYG-11", "Branch protection declared as code", "B", Severity.COSMETIC, scored=False)


#: CI providers that expose branch protection as configuration-as-code.
_PROTECTION_PROVIDERS = frozenset({"github", "gitlab"})


# ===========================================================================
# HYG-11 — branch protection declared as code
# ===========================================================================


#: An integration branch name: with another protected branch beside it, the repository runs a two-branch model
#: (work branch -> integration -> release), and the release branch needs a source-branch check.
_INTEGRATION_BRANCHES = frozenset({"dev", "develop", "development", "integration", "next"})

#: Per CI provider, the variables that hold a pull request's source branch.
_SOURCE_BRANCH_TOKENS: dict[str, tuple[str, ...]] = {
    "github": ("github.head_ref", "GITHUB_HEAD_REF", "pull_request.head.ref"),
    "gitlab": ("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME",),
}

#: Keys whose value uses the source branch for something else: a concurrency group, a checkout ref.
_NOT_A_SOURCE_CHECK_RE = re.compile(r"^\s*-?\s*(?:group|ref)\s*:")


def _protection_pages(inventory: Inventory) -> tuple[list[str], list[str]]:
    """Files whose path names branch protection: ``(documents, other files)``. A document records the rules; any
    other such file (``.github/branch-protection.yml``) is read as configuration."""
    named = sorted(
        f.rel for f in inventory.files if "branch-protection" in f.rel.lower() or "branch_protection" in f.rel.lower()
    )
    documents = [rel for rel in named if _basename(rel).lower().endswith(_DOC_SUFFIXES)]
    return documents, [rel for rel in named if rel not in documents]


def _two_branch_model(rules: BranchRules) -> bool:
    literal = set(rules.literal_branches)
    integration = literal & _INTEGRATION_BRANCHES
    return bool(integration) and len(set(rules.branches) - integration) >= 1


def _source_branch_check(inventory: Inventory) -> tuple[str, int] | None:
    """The first workflow line that reads a pull request's source branch, outside a concurrency group or a
    checkout ref."""
    for provider, globs in CI_PROVIDERS.items():
        tokens = _SOURCE_BRANCH_TOKENS.get(provider)
        if not tokens:
            continue
        for rel in sorted(inventory.match(*globs)):
            for number, line in enumerate((inventory.read(rel) or "").splitlines(), start=1):
                code = line.split(" #", 1)[0]
                if code.lstrip().startswith("#") or _NOT_A_SOURCE_CHECK_RE.match(code):
                    continue
                if any(token in code for token in tokens):
                    return rel, number
    return None


def check_hyg11(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    rules = declared_branch_rules(inventory)
    documents, configs = _protection_pages(inventory)
    sources = sorted(set(rules.sources) | set(configs))
    if sources:
        declared = f"branch protection declared as code at {', '.join(sources)}"
        if not _two_branch_model(rules):
            return _outcome(spec, Verdict.PASS, declared)
        source_check = _source_branch_check(inventory)
        if source_check:
            rel, line = source_check
            return _outcome(spec, Verdict.PASS, f"{declared}; source-branch check at {rel}:{line}")
        protected = ", ".join(rules.branches)
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"{declared}; {protected} are protected but no CI job checks a pull request's source branch",
            [
                _finding(
                    spec,
                    Verdict.PARTIAL,
                    "rely on the release branch accepting changes from the integration branch only",
                    f"the rules protect {protected}, and no workflow reads the pull request's source branch",
                    evidence=[Evidence(rel, note="declares branch rules") for rel in sources],
                    remediation="Add a CI job on pull requests into the release branch that fails unless the source "
                    "branch is the integration branch, and make it a required status check (rulesets cannot "
                    "restrict the source branch).",
                ),
            ],
        )

    if rules.unreadable:
        return _outcome(
            spec,
            Verdict.UNKNOWN,
            f"{', '.join(rules.unreadable)} cannot be read as a ruleset (invalid JSON, or no rules list)",
        )

    if documents:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"branch protection recorded at {documents[0]}, not declared as code",
            [
                _finding(
                    spec,
                    Verdict.PARTIAL,
                    "review a change to the protected-branch rules like any other change",
                    f"{documents[0]} describes the rules, but no ruleset file or Terraform resource declares them",
                    evidence=[Evidence(rel, note="describes the rules") for rel in documents],
                    remediation="Export the rules as code: a JSON file per ruleset under .github/rulesets/ on "
                    "GitHub, or a Terraform protection resource. Keep the page as the summary.",
                ),
            ],
        )

    recognised = sorted(_PROTECTION_PROVIDERS & set(stack.ci_providers))
    if recognised:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"{', '.join(recognised)} offers branch protection as code, none found",
            [
                _finding(
                    spec,
                    Verdict.FAIL,
                    "reproduce the protected-branch rules as code",
                    f"the {', '.join(recognised)} provider is detected but no branch-protection configuration exists",
                    remediation="Declare branch protection in code (a JSON file per ruleset under .github/rulesets/ "
                    "on GitHub, or a Terraform protection resource) so it is reviewed like any other change.",
                ),
            ],
        )

    return _outcome(
        spec,
        Verdict.UNKNOWN,
        "no CI provider recognised; whether branch protection can be declared as code is provider-dependent",
    )
