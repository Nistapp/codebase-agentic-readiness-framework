# Development tooling

> **Audience:** Contributors, interns included, and AI coding agents.
> **Status:** Live. Every tool on this page runs today.

This page lists each tool that checks this repository: what it catches, which command runs it, where CI runs it,
and where its version is pinned. The rules for the gates are in [`AGENTS.md`](../../AGENTS.md). Setup is in
[`CONTRIBUTING.md`](../../CONTRIBUTING.md).

## The tools

| Tool | What it catches | Command | In CI | Version pinned in |
| --- | --- | --- | --- | --- |
| ruff | Python formatting and lint errors (rules in `ruff.toml`) | `make format`, `make format:check`, `make lint` | `static` | `dev/tools/pyproject.toml` |
| mypy | Python type errors, strict mode (`mypy.ini`) | `make typecheck` | `static` | `dev/tools/pyproject.toml` |
| unittest | Failing tests: the engine, the audit tools, the implement tools, the dev checks | `make test` (on Linux, its four suites at once; CI splits the engine's and the audit tools' suites into shards with `dev/test_shard.py`, and the dev checks too on Python 3.14) | `test-coverage`, `test-dev`, `test-py314`; unsharded in `nightly.yml` | Python standard library |
| coverage.py | Test coverage below the floor in `.coveragerc` | `make coverage` (in CI: `coverage-part`, then `coverage-combine SHARDED=1`) | `test-coverage`, `coverage`; unsharded in `nightly.yml` | `dev/tools/pyproject.toml` |
| jsonschema | The tools' schema validator disagrees with the reference package | `make crosscheck` | `crosscheck` | `dev/tools/pyproject.toml` |
| `dev/recipe_lint.py` | Broken links, bad `SKILL.md` frontmatter, a recipe `SKILL.md` that does not link the shared user prompt, oversize files, unknown tools, check IDs and requirement IDs | `make recipe-lint` | `static` | This repository |
| `dev/adr_lint.py` | An ADR with a lifecycle field, a lifecycle footer or a retired-ADR marker, a missing template section, or no row in the [ADR index](../architecture/adrs/README.md); an index row to a missing ADR | `make adr-lint` | `static` | This repository |
| `dev/build_masters.py` | An [audit master list](audit-master.md) or [implement master list](implement-master.md) that no longer matches the catalogue, the check files or the playbooks | `make masters-check`; `make update-masters` rewrites both pages | `static` | This repository |
| `dev/eval/generate_fixture_expected.py` | An eval-expected file (`dev/eval/expected/fixtures/`) that no longer matches a fresh engine run on its fixture | `make eval-expected-check`; the script without `--check` rewrites the files | `static` | This repository |
| actionlint | Workflow mistakes: syntax, expressions, action inputs, shellcheck on `run:` blocks | `make workflow-lint` | `static` | `dev/tools/actionlint/go.mod` |
| zizmor | Workflow and Dependabot security: injection, broad permissions, unpinned actions, cooldown. Runs at the pedantic persona, so a permission without a comment or a missing concurrency limit fails too | `make workflow-lint` | `static` | `dev/tools/pyproject.toml` |
| typos | Misspelled words in the tracked text, code identifiers included (word list: [`_typos.toml`](../../_typos.toml)) ([Spell check](#spell-check)) | `make spell`; `make spell-fix` writes the fixes | `static` | `dev/tools/pyproject.toml` |
| check-jsonschema | `.github/workflows/*.yml` and `.github/dependabot.yml` that do not match their SchemaStore schemas | `make workflow-lint` | `static` | `dev/tools/pyproject.toml` |
| detect-secrets | Key-shaped strings not in `.secrets.baseline` | `make security` (part: `security-secrets`) | `security-secrets` | `dev/tools/pyproject.toml` |
| osv-scanner | A known vulnerability in a dev tool or its dependencies (Python, Node, Go lockfiles), unless [`osv-scanner.toml`](../../dev/tools/osv-scanner.toml) accepts it ([Dependency audit](#dependency-audit)) | `make security` (part: `security-deps`) | `security-deps` | `dev/tools/osv/go.mod` |
| markdownlint-cli2 | Markdown rule violations (`.markdownlint-cli2.jsonc`) | `make docs-lint`; `make changelog-fix` rewrites `CHANGELOG.md` with the fixes | `docs`; `format-changelog` in `release-please.yml` | `dev/tools/package.json` |
| `dev/prose_check.py` | Long sentences, vague words, explanation pages without a diagram ([`COMMUNICATION_RULES.md`](../COMMUNICATION_RULES.md)). Advisory: warnings and notices, never a failure | `make docs-prose [FILES=...]` | `docs` (annotations on changed Markdown) | This repository |
| mermaid-cli | A Mermaid block that does not render | `make docs-mermaid FILES=<file.md>` | `docs` | `dev/tools/package.json` |
| skills-ref | A skill bundle that breaks the Agent Skills specification | `make validate-skills` | Release only | `dev/tools/pyproject.toml` |
| `dev/commit_lint.py` | A commit subject that is not Conventional Commits | `make commit-lint` | `commits` | This repository |
| The audit engine | A readiness finding that `.audit-baseline.json` does not have | `make self-audit` | `self-audit` | This repository |
| actions/attest | Signs build provenance for the release files; users check it with `gh attestation verify` ([Install the skills](../how-to/install-the-skills.md#step-2b-optional-check-the-build-provenance)) | — | `release.yml`, release only | `.github/workflows/release.yml` (action pinned by SHA) |
| CodeQL | Security flaws in the Python code and the workflows. Advisory: alerts go to the Security tab ([Code scanning](branch-protection.md#code-scanning)) | — | `codeql.yml`, outside `CI Gate` | `.github/workflows/codeql.yml` (action pinned by SHA) |
| OpenSSF Scorecard | Weak security practices of the repository (Branch-Protection, Pinned-Dependencies, Token-Permissions, Signed-Releases, ...). Advisory: alerts go to the Security tab; the score is published on scorecard.dev and in the README badge ([Scorecard alerts](branch-protection.md#scorecard-alerts)) | — | `scorecard.yml`, on push to `dev` and weekly | `.github/workflows/scorecard.yml` (action pinned by SHA) |
| release-please | Computes the next version from the commit subjects, writes `CHANGELOG.md`, tags and creates the GitHub release (`release-please-config.json`) | — | `release-please.yml`, on each push to `main` | `.github/workflows/release-please.yml` (action pinned by SHA) |
| uv | Runs the Python tools through `uvx` and `uv run` | — | All jobs | `dev/tools/pyproject.toml` |
| Node | Runs the Node tools through `npx` | — | `docs` | `.nvmrc` |
| Go | Builds and runs actionlint and osv-scanner through `go tool` | — | `check`, `security` | the `go` line of each Go tool module |

`make check` runs `format:check`, `typecheck`, `test`, the engine's rule check, `crosscheck`, `recipe-lint`,
`adr-lint`, `masters-check`, `eval-expected-check`, `workflow-lint` and `spell`, in sequence. CI's `CI Gate`
passes only when the `check`, `security`, `coverage`, `self-audit`, `docs` and `commits` jobs pass ([Branch protection](branch-protection.md#the-required-checks)).

## Spell check

`make spell` runs typos on every tracked file that `.gitignore` does not hide. It skips the data paths that
[`_typos.toml`](../../_typos.toml) excludes: the fixtures, the worked examples, `CHANGELOG.md` and the lockfiles.
typos splits code identifiers into words, so a typo inside a variable name fails too. Each finding shows the file,
the line and the suggested word.

To fix a finding, do one of these:

1. Correct the word. `make spell-fix` writes every suggested fix; review the diff before you commit.
2. If the word is correct here (a project term, a regex stem or a code token), add it to `[default.extend-words]` in
   `_typos.toml`. Add a comment that says why.

## Dependency audit

`make security` runs osv-scanner after the secrets scan
([ADR 0007](../architecture/adrs/0007-security-verb-audits-dependencies-with-osv-scanner.md)). It reads the
dev-tool lockfiles (Python, Node and each Go tool module) and asks osv.dev for known vulnerabilities. It needs Go
1.27 or newer and the network. The first run builds osv-scanner, which takes about 30 seconds.

The scan fails when it finds a vulnerability that no `osv-scanner.toml` accepts. Each ignore file covers the
lockfiles in its own folder: [`dev/tools/osv-scanner.toml`](../../dev/tools/osv-scanner.toml) for `uv.lock` and
`package-lock.json`, and `dev/tools/<tool>/osv-scanner.toml` for a Go tool module. OpenSSF Scorecard reads the same
files, so an accepted vulnerability raises no Scorecard alert either.

The output has one table row per vulnerability: the OSV link, the package, its version, the fixed version and the
lockfile. To fix a finding, do one of these:

1. Raise the tool or the dependency to the fixed version. Follow
   [Change a tool version](../../RELEASE_PROCESS.md#change-a-tool-version).
2. If no fix reaches this repository, add an entry to the `osv-scanner.toml` next to the lockfile. Give the `id` and
   a `reason`.
   Set `ignoreUntil` to a date at most six months ahead. `dev/tests/test_tool_pins.py` checks the entry.

When an `ignoreUntil` date passes, the scan fails again. Look at the advisory again, then fix or renew it.

## Ratchets

A ratchet holds a count that may only go down, or a floor that may only go up. A change that makes a count go up
fails its gate. When a count goes down, lower the baseline in the same change.

| Ratchet | File | Checked by |
| --- | --- | --- |
| ruff, mypy and Markdown lint counts | `.quality-baseline.json` | `make format:check`, `make typecheck`, `make docs-lint` |
| Known key-shaped strings | `.secrets.baseline` | `make security` |
| Coverage floor | `.coveragerc` (`fail_under`) | `make coverage` (runs as CI does: an empty `HOME` and `CI=true`) |
| Readiness findings | `.audit-baseline.json` | `make self-audit` |

## Local hooks

[`lefthook.yml`](../../lefthook.yml) runs these before a commit lands, after you run `lefthook install` once:

| Hook | Runs | On |
| --- | --- | --- |
| `protected-branch` | Stops a commit on `dev` or `main` | Every commit |
| `format-check` | `make format-check` | Staged Python files |
| `docs-lint` | `make docs-lint` | Staged Markdown in the ratchet paths |
| `workflow-lint` | `make workflow-lint` | Staged files under `.github/` |
| `spell` | typos, at the pinned version | Staged files, except the paths `_typos.toml` excludes |
| `secrets` | detect-secrets on the staged files | Every commit |
| `conventional-commits` | `dev/commit_lint.py --message-file` | The commit message |

The hooks are a convenience. CI runs the same checks, and a skipped hook does not skip CI.

## How the versions are pinned

Each tool version is written once:

- Python tools: `dev/tools/pyproject.toml`, group `tools`, locked in `dev/tools/uv.lock`.
- Node tools: `dev/tools/package.json`, locked in `dev/tools/package-lock.json`.
- Go tools: one module each, with a Go `tool` requirement and checksums in its `go.sum`: osv-scanner in
  `dev/tools/osv/`, actionlint in `dev/tools/actionlint/`. The Go module proxy serves them.

The `Makefile`, `lefthook.yml`, `dev/mermaid_check.py` and the workflows read each version from those files.
Nothing is installed into the project: the tools run through `uvx`, `npx` and `go tool`. Dependabot watches these
files and opens a pull request only for a security fix that is not a major version
([ADR 0003](../architecture/adrs/0003-dependabot-security-pull-requests-only.md)).
`dev/tests/test_tool_pins.py` fails when a version is not exact, when a lockfile disagrees with its manifest, or when
another file repeats a version.

To change a version, follow [Change a tool version](../../RELEASE_PROCESS.md#change-a-tool-version).

## Agent tools (MCP)

MCP servers make an agent faster. No gate, CI job or release step needs one. Anything that must be right runs
through `make`.

`.mcp.json` at the repository root registers one server, `codebase-memory-mcp` (the code index). It names the bare
command, so each person installs the server and keeps its version. No version is written in the repository.
`dev/tests/test_mcp_config.py` checks the file, and checks that `.claude/settings.json` approves no project server
for you.

How each harness treats a project MCP file (checked 2026-11-09 in each harness's own docs):

| Harness | Reads | First start in this repository |
| --- | --- | --- |
| Claude Code | `.mcp.json` | Asks you to approve the server, once per person |
| VS Code with Copilot | `.mcp.json` or `.vscode/mcp.json` | Starts it when the folder is trusted |
| Cursor | `.cursor/mcp.json` | You turn each server on or off |
| Gemini CLI | `.gemini/settings.json` (`mcpServers`) | Starts it after you trust the folder |
| opencode | `opencode.json` (`mcp`) | Connects it with no prompt |
| Codex CLI | `.codex/config.toml` (`[mcp_servers]`) | Loads it only for a trusted project |
| Antigravity | Its own user-level list (`agy mcp add`) | Starts it in every repository |

For a harness that does not read `.mcp.json`, `dev/mcp_config.py` translates the entry into that harness's format:

| Command | What it does |
| --- | --- |
| `python3 dev/mcp_config.py show --harness <name> [--scope project\|user]` | Prints the target file and the entry. Writes nothing |
| `python3 dev/mcp_config.py write --harness <name> [--scope project\|user]` | Adds the entry to the file. Stops if a different entry has the same name |
| `python3 dev/mcp_config.py detect` | Names the harness from the variable it sets (`CLAUDECODE`, `ANTIGRAVITY_AGENT`, `OPENCODE`), or says to ask |
| `python3 dev/mcp_config.py check` | Is each server's command on `PATH`? Prints its version, or the install routes |
| `python3 dev/mcp_config.py status --harness <name>` | Has the person answered the setup offer for this harness? |
| `python3 dev/mcp_config.py record --harness <name> --answer accepted\|declined` | Records the answer in `.agentic-readiness/setup.json` |

A language server is an optional aid beside the index. `pyrightconfig.json` gives pyright and basedpyright the same
import paths as `mypy.ini`, and `dev/tests/test_pyright_config.py` keeps the two in step. `make typecheck` stays the
gate. Routes per harness: [Set up the agent tools](../how-to/set-up-agent-tools.md#optional-a-language-server).

The names are `claude-code`, `vscode`, `cursor`, `gemini`, `opencode`, `codex`, `antigravity` and `other`. The tool
installs nothing. If
the server is not installed, it fails to start and the agent reads files instead.

## Settings on GitHub

These checks run on GitHub, outside the repository files:

| Setting | What it does | Documented in |
| --- | --- | --- |
| Rulesets on `dev` and `main` | Pull request required, `CI Gate`, `Check source branch` on `main` | [Branch protection](branch-protection.md) |
| Dependabot alerts and security updates | Alerts on vulnerable dependencies; security pull requests into `dev` | [ADR 0003](../architecture/adrs/0003-dependabot-security-pull-requests-only.md) |
| Secret scanning and push protection | Refuses a push that holds a known secret format | [`SECURITY.md`](../../SECURITY.md) |
| CODEOWNERS | Requests a review from the maintainer | [`.github/CODEOWNERS`](../../.github/CODEOWNERS) |
