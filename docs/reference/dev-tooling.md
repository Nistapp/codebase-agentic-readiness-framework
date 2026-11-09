# Development tooling

> **Audience:** Contributors, interns included, and AI coding agents.
> **Status:** Live. Every tool on this page runs today.

This page lists each tool that checks this repository: what it catches, which command runs it, where CI runs it,
and where its version is pinned. The rules for the gates are in [`AGENTS.md`](../../AGENTS.md). Setup is in
[`CONTRIBUTING.md`](../../CONTRIBUTING.md).

## The tools

| Tool | What it catches | Command | In CI | Version pinned in |
| --- | --- | --- | --- | --- |
| ruff | Python formatting and lint errors (rules in `ruff.toml`) | `make format`, `make format:check`, `make lint` | `check` | `dev/tools/pyproject.toml` |
| mypy | Python type errors, strict mode (`mypy.ini`) | `make typecheck` | `check` | `dev/tools/pyproject.toml` |
| unittest | Failing tests: the engine, the audit tools, the implement tools, the dev checks | `make test` | `check` | Python standard library |
| coverage.py | Test coverage below the floor in `.coveragerc` | `make coverage` | `coverage` | `dev/tools/pyproject.toml` |
| jsonschema | The tools' schema validator disagrees with the reference package | `make crosscheck` | `check` | `dev/tools/pyproject.toml` |
| `dev/recipe_lint.py` | Broken links, bad `SKILL.md` frontmatter, oversize files, unknown tools, check IDs and requirement IDs | `make recipe-lint` | `check` | This repository |
| actionlint | Workflow mistakes: syntax, expressions, action inputs, shellcheck on `run:` blocks | `make workflow-lint` | `check` | `dev/tools/pyproject.toml` (`actionlint-py`) |
| zizmor | Workflow and Dependabot security: injection, broad permissions, unpinned actions, cooldown | `make workflow-lint` | `check` | `dev/tools/pyproject.toml` |
| check-jsonschema | `.github/workflows/*.yml` and `.github/dependabot.yml` that do not match their SchemaStore schemas | `make workflow-lint` | `check` | `dev/tools/pyproject.toml` |
| detect-secrets | Key-shaped strings not in `.secrets.baseline` | `make security` | `security` | `dev/tools/pyproject.toml` |
| osv-scanner | A known vulnerability in a dev tool or its dependencies (Python, Node, Go lockfiles), unless [`osv-scanner.toml`](../../dev/tools/osv-scanner.toml) accepts it ([Dependency audit](#dependency-audit)) | `make security` | `security` | `dev/tools/osv/go.mod` |
| markdownlint-cli2 | Markdown rule violations (`.markdownlint-cli2.jsonc`) | `make docs-lint`; `make changelog-fix` rewrites `CHANGELOG.md` with the fixes | `docs`; `format-changelog` in `release-please.yml` | `dev/tools/package.json` |
| `dev/prose_check.py` | Long sentences, vague words, explanation pages without a diagram ([`COMMUNICATION_RULES.md`](../COMMUNICATION_RULES.md)). Advisory: warnings and notices, never a failure | `make docs-prose [FILES=...]` | `docs` (annotations on changed Markdown) | This repository |
| mermaid-cli | A Mermaid block that does not render | `make docs-mermaid FILES=<file.md>` | `docs` | `dev/tools/package.json` |
| skills-ref | A skill bundle that breaks the Agent Skills specification | `make validate-skills` | Release only | `dev/tools/pyproject.toml` |
| `dev/commit_lint.py` | A commit subject that is not Conventional Commits | `make commit-lint` | `commits` | This repository |
| The audit engine | A readiness finding that `.audit-baseline.json` does not have | `make self-audit` | `self-audit` | This repository |
| CodeQL | Security flaws in the Python code and the workflows. Advisory: alerts go to the Security tab ([Code scanning](branch-protection.md#code-scanning)) | — | `codeql.yml`, outside `CI Gate` | `.github/workflows/codeql.yml` (action pinned by SHA) |
| release-please | Computes the next version from the commit subjects, writes `CHANGELOG.md`, tags and creates the GitHub release (`release-please-config.json`) | — | `release-please.yml`, on each push to `main` | `.github/workflows/release-please.yml` (action pinned by SHA) |
| uv | Runs the Python tools through `uvx` and `uv run` | — | All jobs | `dev/tools/pyproject.toml` |
| Node | Runs the Node tools through `npx` | — | `docs` | `.nvmrc` |
| Go | Builds and runs osv-scanner through `go tool` | — | `security` | `dev/tools/osv/go.mod` (`go` line) |

`make check` runs `format:check`, `typecheck`, `test`, the engine's rule check, `crosscheck`, `recipe-lint` and
`workflow-lint`, in sequence. CI's `CI Gate` passes only when the `check`, `security`, `coverage`, `self-audit`,
`docs` and `commits` jobs pass ([Branch protection](branch-protection.md#the-required-checks)).

## Dependency audit

`make security` runs osv-scanner after the secrets scan
([ADR 0006](../architecture/adrs/0006-security-verb-audits-dependencies-with-osv-scanner.md)). It reads the three
dev-tool lockfiles and asks osv.dev for known vulnerabilities. It needs Go 1.27 or newer and the network. The first
run builds osv-scanner, which takes about 30 seconds.

The scan fails when it finds a vulnerability that [`dev/tools/osv-scanner.toml`](../../dev/tools/osv-scanner.toml)
does not accept. The output has one table row per vulnerability: the OSV link, the package, its version, the fixed
version and the lockfile. To fix a finding, do one of these:

1. Raise the tool or the dependency to the fixed version. Follow
   [Change a tool version](../../RELEASE_PROCESS.md#change-a-tool-version).
2. If no fix reaches this repository, add an entry to `osv-scanner.toml`. Give the `id` and a `reason`.
   Set `ignoreUntil` to a date at most six months ahead. `dev/tests/test_tool_pins.py` checks the entry.

When an `ignoreUntil` date passes, the scan fails again. Look at the advisory again, then fix or renew it.

## Ratchets

A ratchet holds a count that may only go down, or a floor that may only go up. A change that makes a count go up
fails its gate. When a count goes down, lower the baseline in the same change.

| Ratchet | File | Checked by |
| --- | --- | --- |
| ruff, mypy and Markdown lint counts | `.quality-baseline.json` | `make format:check`, `make typecheck`, `make docs-lint` |
| Known key-shaped strings | `.secrets.baseline` | `make security` |
| Coverage floor | `.coveragerc` (`fail_under`) | `make coverage` |
| Readiness findings | `.audit-baseline.json` | `make self-audit` |

## Local hooks

[`lefthook.yml`](../../lefthook.yml) runs these before a commit lands, after you run `lefthook install` once:

| Hook | Runs | On |
| --- | --- | --- |
| `protected-branch` | Stops a commit on `dev` or `main` | Every commit |
| `format-check` | `make format-check` | Staged Python files |
| `docs-lint` | `make docs-lint` | Staged Markdown in the ratchet paths |
| `workflow-lint` | `make workflow-lint` | Staged files under `.github/` |
| `secrets` | detect-secrets on the staged files | Every commit |
| `conventional-commits` | `dev/commit_lint.py --message-file` | The commit message |

The hooks are a convenience. CI runs the same checks, and a skipped hook does not skip CI.

## How the versions are pinned

Each tool version is written once:

- Python tools: `dev/tools/pyproject.toml`, group `tools`, locked in `dev/tools/uv.lock`.
- Node tools: `dev/tools/package.json`, locked in `dev/tools/package-lock.json`.
- osv-scanner: `dev/tools/osv/go.mod`, a Go `tool` requirement, with checksums in `dev/tools/osv/go.sum`.

The `Makefile`, `lefthook.yml`, `dev/mermaid_check.py` and the workflows read each version from those files.
Nothing is installed into the project: the tools run through `uvx`, `npx` and `go tool`. Dependabot watches these
files and opens a pull request only for a security fix that is not a major version
([ADR 0003](../architecture/adrs/0003-dependabot-security-pull-requests-only.md)).
`dev/tests/test_tool_pins.py` fails when a version is not exact, when a lockfile disagrees with its manifest, or when
another file repeats a version.

To change a version, follow [Change a tool version](../../RELEASE_PROCESS.md#change-a-tool-version).

## Settings on GitHub

These checks run on GitHub, outside the repository files:

| Setting | What it does | Documented in |
| --- | --- | --- |
| Rulesets on `dev` and `main` | Pull request required, `CI Gate`, `Check source branch` on `main` | [Branch protection](branch-protection.md) |
| Dependabot alerts and security updates | Alerts on vulnerable dependencies; security pull requests into `dev` | [ADR 0003](../architecture/adrs/0003-dependabot-security-pull-requests-only.md) |
| Secret scanning and push protection | Refuses a push that holds a known secret format | [`SECURITY.md`](../../SECURITY.md) |
| CODEOWNERS | Requests a review from the maintainer | [`.github/CODEOWNERS`](../../.github/CODEOWNERS) |
