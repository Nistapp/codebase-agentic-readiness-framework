# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`CI` pack — continuous integration.

Anchor: `docs/framework/phased-approach.md` § Key Deliverables. The normative sentence is the
one-command-surface note in the Phase 1 activities block.

Implemented here: `CI-01` … `CI-03` and `CI-05` (`CI-04` is an agent-run check with no engine id).

The pack verifies that a repository's CI is *the same command surface* an agent runs locally, not a
second, secret one. Workflow files are read through `audit.scan`; the local verbs they are compared
against come from `audit.rules.checks._common`.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **CI-01** — a workflow file exists (`audit.stack.CI_PROVIDERS` globs) **and** at least one of them
  declares a pull-request trigger (GitHub `pull_request`/`pull_request_target`, GitLab
  `merge_request`, Azure `pr:`, Jenkins `changeRequest`). Workflows present but no such trigger ⇒
  `PARTIAL`. No workflow file at all ⇒ `FAIL` — a PR-triggered pipeline is a Phase-1 deliverable.
* **CI-02** — the set of framework verbs (`audit.stack.VERBS`) the workflows invoke, against the
  verbs `CMD-01` resolves locally. A CI command whose verb has no local definition is a parity
  break ⇒ `FAIL`. The read-only local verbs the CI never exercises are reported in `detail` but do
  not fail the check, because CI may legitimately delegate to the composed `check` gate. With **no
  resolvable local verb** there is nothing to compare ⇒ `UNKNOWN`.
* **CI-03** — every CI command that invokes a runner target (`npm run <x>`, `make <x>`, …) with no
  local runner entry is listed as a finding, so an agent can see which CI steps it cannot reproduce.
  Framework-verb invocations are `CI-02`'s subject and are not repeated here; package-manager
  plumbing (`npm ci`, `npm publish`) and shell automation (`gh`, `echo`) are not project tools and
  are ignored. No findings ⇒ `PASS`.
* **CI-05** — the workflow files are linted, per CI provider, by a tool that knows that provider:
  actionlint, zizmor or `check-jsonschema --builtin-schema vendor.github-workflows` for GitHub;
  `check-jsonschema` with the provider's built-in schema (or the matching pre-commit hook id) for
  GitLab, Azure, CircleCI and Buildkite; `glab ci lint` and `circleci config validate` count too.
  A linter named in a local surface (a runner manifest, a build file, a hook config, a script) ⇒
  local; named only in a workflow file (a `run:` step or a `uses:` action) ⇒ CI only. Every
  lintable provider linted locally ⇒ `PASS`; at least one linted only in CI, or one linted and
  another not ⇒ `PARTIAL`; workflows exist and nothing lints them ⇒ `FAIL`. No workflow file
  (`CI-01`'s subject), or only providers with no known offline linter (Jenkins) ⇒ `UNKNOWN`.

Deliberate limits, recorded rather than hidden. **YAML is not parsed.** This module is a minimal,
documented text scan: it recognises `run:` / `script:` / `command:` scalar and block-scalar steps,
splits them on shell operators, and matches triggers by pattern. Anchors, expressions, `uses:`
steps, matrix expansion and full YAML semantics are out of scope, so a command hidden inside an
expression is not seen. **Verb mapping is textual**, reusing the runner-indirection idea from
`CMD-01`; an ecosystem outside that set is not mapped. Neither limit produces a `PASS` by guessing:
an unmapped command is simply not counted as evidence. **CI-05 matches tool names in text**: a
local file that names `actionlint` in a comment counts, and a linter started through an indirection
the scan cannot see (a script it does not read) is missed. Documentation files, lockfiles and
dependency-update configs (Dependabot, Renovate) never count: they name a tool without running it.
"""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.probes import MUTATING_VERBS
from audit.rules.checks._common import resolve_verbs, runner_commands, runner_target
from audit.stack import CI_PROVIDERS, VERBS
from audit.rules.payloads import Payload
from audit.scan import Kind

#: The read-only verbs a CI pipeline may be expected to exercise (everything but a write verb).
READ_ONLY_VERBS: tuple[str, ...] = tuple(v for v in VERBS if v not in MUTATING_VERBS)

#: Pull-request trigger patterns, per CI provider. Matched against the raw workflow text.
_PR_TRIGGER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "github": (re.compile(r"(?m)^\s*pull_request(?:_target)?\s*:"), re.compile(r"\bon\s*:\s*\[[^\]]*pull_request")),
    "gitlab": (re.compile(r"merge_request", re.IGNORECASE),),
    "azure": (re.compile(r"(?m)^\s*pr\s*:"),),
    "jenkins": (re.compile(r"changeRequest", re.IGNORECASE),),
}

#: Step keys that carry commands, across the workflow dialects this scan understands.
_STEP_KEY_RE = re.compile(r"^(\s*)(?:-\s+)?(run|script|command|commands|bash)\s*:\s*(.*)$")
_BLOCK_SCALAR_VALUES = frozenset({"|", "|-", "|+", ">", ">-", ">+", ""})
_COMMAND_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")

#: Direct tool invocations, mapped to the framework verb they satisfy. `format:check` precedes
#: `format` and `security` precedes the rest so the more specific form wins.
_DIRECT_VERB_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (verb, tuple(re.compile(p) for p in patterns))
    for verb, patterns in (
        (
            "format:check",
            (
                r"\bprettier\b[^&|;]*--check\b",
                r"\bruff\s+format\b[^&|;]*--(?:check|diff)\b",
                r"\bbiome\s+ci\b",
                r"\bblack\b[^&|;]*--check\b",
                r"\bcargo\s+fmt\b[^&|;]*--check\b",
                r"\bdotnet\s+format\b[^&|;]*--verify-no-changes\b",
            ),
        ),
        (
            "format",
            (
                r"\bprettier\b[^&|;]*(?:--write|-w)\b",
                r"\bruff\s+format\b",
                r"\bbiome\s+format\b",
                r"\bblack\b",
                r"\bgofmt\b[^&|;]*\s-w\b",
                r"\bcargo\s+fmt\b",
            ),
        ),
        (
            "typecheck",
            (
                r"\btsc\b",
                r"\bmypy\b",
                r"\bpyright\b",
                r"\bbasedpyright\b",
                r"\bcargo\s+check\b",
                r"\bgo\s+vet\b",
            ),
        ),
        (
            "lint",
            (
                r"\beslint\b",
                r"\bruff\s+check\b",
                r"\bflake8\b",
                r"\bpylint\b",
                r"\bgolangci-lint\b",
                r"\bclippy\b",
                r"\brubocop\b",
                r"\bbiome\s+(?:check|lint)\b",
                r"\bstylelint\b",
            ),
        ),
        (
            "test",
            (
                r"\bvitest\b",
                r"\bjest\b",
                r"\bmocha\b",
                r"\bpytest\b",
                r"python3?\s+-m\s+(?:unittest|pytest)",
                r"\bgo\s+test\b",
                r"\bcargo\s+test\b",
                r"\bdotnet\s+test\b",
                r"\brspec\b",
                r"\bphpunit\b",
            ),
        ),
        (
            "security",
            (
                r"\bnpm\s+audit\b",
                r"\b(?:pnpm|yarn|bun)\s+audit\b",
                r"\bpip-audit\b",
                r"\bsafety\s+check\b",
                r"\bosv-scanner\b",
                r"\bcargo\s+audit\b",
                r"\bgovulncheck\b",
                r"\bsnyk\b",
                r"\btrivy\b",
                r"\bgrype\b",
                r"\bbundler-audit\b",
                r"\bcomposer\s+audit\b",
                r"\baudit-ci\b",
            ),
        ),
    )
)

#: Package-manager subcommands that are tooling, not project scripts. Never flagged as CI-only.
_PM_BUILTINS: frozenset[str] = frozenset(
    {
        "ci",
        "install",
        "i",
        "publish",
        "pack",
        "version",
        "exec",
        "init",
        "link",
        "dedupe",
        "prune",
        "update",
        "outdated",
        "ls",
        "why",
        "config",
        "cache",
        "login",
        "logout",
        "whoami",
        "doctor",
        "help",
        "start",
        "stop",
        "restart",
        "add",
        "remove",
        "uninstall",
        "stage",
    }
)


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
_NOT_A_SURFACE: frozenset[str] = frozenset(
    {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lock",
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "pdm.lock",
        "Cargo.lock",
        "go.sum",
        "Gemfile.lock",
        "composer.lock",
        "dependabot.yml",
        "dependabot.yaml",
        "renovate.json",
        ".renovaterc",
        ".renovaterc.json",
    }
)


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


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _finding(
    spec,
    cannot: str,
    because: str,
    verdict: Verdict,
    evidence: list[Evidence],
    remediation: str,
    path: str | None = None,
) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence,
        remediation=remediation,
        path=path,
    )


# ---------------------------------------------------------------------------
# workflow discovery and a minimal, documented YAML scan
# ---------------------------------------------------------------------------


def _workflows(inventory) -> list[tuple[str, str]]:
    """Every present workflow file as ``(provider, rel)``, in provider order then path order."""
    found: list[tuple[str, str]] = []
    for provider, globs in CI_PROVIDERS.items():
        for rel in sorted(inventory.match(*globs)):
            found.append((provider, rel))
    return found


def _has_pr_trigger(provider: str, text: str) -> bool:
    patterns = _PR_TRIGGER_PATTERNS.get(provider)
    if not patterns:
        # circleci / buildkite declare triggers in the VCS integration, not the checked-in file.
        return False
    return any(pattern.search(text) for pattern in patterns)


def _split_commands(raw: str) -> list[str]:
    command = raw.strip()
    if command.startswith("- "):
        command = command[2:].strip()
    if not command or command.startswith("#"):
        return []
    return [part for part in (p.strip() for p in _COMMAND_SPLIT_RE.split(command)) if part]


def _iter_run_commands(text: str) -> list[tuple[int, str]]:
    """Extract ``(line_no, command)`` from run-style steps. A minimal, documented text scan."""
    lines = text.splitlines()
    commands: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = _STEP_KEY_RE.match(lines[index])
        if not match:
            index += 1
            continue
        indent = len(match.group(1))
        value = match.group(3).strip()
        if value and value not in _BLOCK_SCALAR_VALUES:
            commands.extend((index + 1, cmd) for cmd in _split_commands(value))
            index += 1
            continue
        # Block scalar (or a list under `script:`/`commands:`): collect the indented body.
        body: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            if candidate.strip() == "":
                body.append("")
                cursor += 1
                continue
            if len(candidate) - len(candidate.lstrip()) <= indent:
                break
            body.append(candidate)
            cursor += 1
        for offset, raw in enumerate(body, start=index + 2):
            commands.extend((offset, cmd) for cmd in _split_commands(raw))
        index = cursor
    return commands


def _command_verb(command: str) -> str | None:
    """The framework verb a command invokes, by runner indirection or direct tool, else ``None``."""
    target = runner_target(command)
    if target in VERBS:
        return target
    for verb, patterns in _DIRECT_VERB_PATTERNS:
        if any(pattern.search(command) for pattern in patterns):
            return verb
    return None


def _all_run_commands(inventory, workflows) -> list[tuple[str, int, str]]:
    """Every ``(rel, line_no, command)`` across the workflows, deterministically ordered."""
    out: list[tuple[str, int, str]] = []
    for _provider, rel in workflows:
        text = inventory.read(rel)
        if text:
            out.extend((rel, line, command) for line, command in _iter_run_commands(text))
    return out


# ===========================================================================
# CI-01 — pipeline present, triggered on PRs
# ===========================================================================


def check_ci01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    workflows = _workflows(inventory)
    if not workflows:
        providers = ", ".join(sorted(stack.ci_providers)) or "none"
        return _outcome(
            spec,
            Verdict.FAIL,
            f"no CI workflow file (detected providers: {providers})",
            [
                _finding(
                    spec,
                    "rely on CI to verify a change set",
                    "no CI workflow file exists",
                    Verdict.FAIL,
                    [Evidence(rel) for rel in sorted(inventory.paths())[:1]] or [Evidence("<repository>")],
                    "Add a PR-triggered workflow (for example .github/workflows/ci.yml) that runs the same "
                    "verbs the local command surface defines.",
                )
            ],
        )

    triggered = [(provider, rel) for provider, rel in workflows if _has_pr_trigger(provider, inventory.read(rel) or "")]
    if triggered:
        detail = "; ".join(f"{rel} ({provider})" for provider, rel in triggered)
        return _outcome(spec, Verdict.PASS, f"PR-triggered: {detail}")

    providers = ", ".join(sorted({provider for provider, _rel in workflows}))
    return _outcome(
        spec,
        Verdict.PARTIAL,
        f"{len(workflows)} workflow(s) ({providers}) but none declares a PR trigger",
        [
            _finding(
                spec,
                "trust CI to run before a change reaches the default branch",
                "workflow files exist but none declares a pull-request trigger",
                Verdict.PARTIAL,
                [Evidence(rel) for _provider, rel in workflows],
                "Add a pull-request trigger (GitHub `on: pull_request`, GitLab `merge_request`, …) so the "
                "pipeline runs on the PR rather than only after merge.",
            )
        ],
    )


# ===========================================================================
# CI-02 — local↔CI parity
# ===========================================================================


def check_ci02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    local = resolve_verbs(inventory, stack)
    if not local:
        return _unknown(spec, "no local verb resolves on any runner, so CI cannot be compared to it")

    commands = _all_run_commands(inventory, _workflows(inventory))
    ci_verbs = {verb for _rel, _line, command in commands if (verb := _command_verb(command)) is not None}

    extra = sorted(verb for verb in ci_verbs if verb not in local)
    missing = sorted(verb for verb in READ_ONLY_VERBS if verb in local and verb not in ci_verbs)

    detail = (
        f"CI verbs: {', '.join(sorted(ci_verbs)) or 'none'}; "
        f"local read-only verbs not exercised: {', '.join(missing) or 'none'}"
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


# ===========================================================================
# CI-03 — CI-only steps flagged
# ===========================================================================


def check_ci03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    local_targets: set[str] = set()
    for _runner, commands in runner_commands(inventory):
        local_targets.update(commands)

    findings: list[Finding] = []
    for rel, line, command in _all_run_commands(inventory, _workflows(inventory)):
        if _command_verb(command) is not None:
            continue  # CI-02's subject, not repeated here
        target = runner_target(command)
        if target is None or target in _PM_BUILTINS or target in local_targets:
            continue
        findings.append(
            _finding(
                spec,
                "reproduce a CI step on the local command surface",
                f"{rel}:{line} runs `{command}` with no local runner entry for `{target}`",
                Verdict.FAIL,
                [Evidence(rel, line=line, note=command)],
                f"Add a local script/target for `{target}`, or document why the step is CI-only.",
            )
        )

    if not findings:
        return _outcome(spec, Verdict.PASS, "no CI-only steps")
    return _outcome(spec, Verdict.FAIL, f"{len(findings)} CI-only step(s)", findings)


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


IMPLEMENTATIONS = {
    "CI-01": check_ci01,
    "CI-02": check_ci02,
    "CI-03": check_ci03,
    "CI-05": check_ci05,
}
