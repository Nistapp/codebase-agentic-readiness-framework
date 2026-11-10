# Decisions of record

Decisions are recorded next to the component they govern. This page indexes all five groups. The rule for where a new
one goes is [ADR 0001](0001-decisions-live-beside-the-component.md). Add a row here in the same change as the ADR.
The root router is [`docs/README.md`](../../README.md).

## Repository level: `docs/architecture/adrs/`

| ADR | Title | Summary |
| --- | --- | --- |
| [0001](0001-decisions-live-beside-the-component.md) | Decisions Live Beside the Component They Govern | Each ADR lives in the folder of the component it governs; this page indexes all of them. |
| [0002](0002-dev-integrates-main-releases.md) | `dev` Integrates Every Change; `main` Takes Only Promotions From `dev` and the Release Pull Request | Every change merges into `dev`; `main` takes only promotions from `dev` and the release pull request. |
| [0003](0003-dependabot-security-pull-requests-only.md) | Dependabot Opens Security Pull Requests Only; Major Versions Are Advisory | Dependabot opens security pull requests only; a major-version upgrade is the maintainer's manual step. |
| [0004](0004-plain-language-rules-and-a-prose-check.md) | Plain-Language Rules in One File, Checked by a Standard-Library Prose Check | `docs/COMMUNICATION_RULES.md` holds the writing rules; `make docs-prose` checks them and never fails. |
| [0005](0005-release-please-cuts-releases.md) | Release-Please Computes the Version, Writes the Changelog and Tags the Release | release-please sets the version from commit subjects, writes `CHANGELOG.md` and tags `vX.Y.Z`. |
| [0006](0006-first-run-agent-tool-offer.md) | One Committed `.mcp.json`; Agents Offer Each Person a One-Time Setup for Their Harness | One committed `.mcp.json`; each agent offers its person a one-time, consented setup for their harness. |
| [0007](0007-security-verb-audits-dependencies-with-osv-scanner.md) | The Security Verb Audits the Dev Tools' Dependencies with osv-scanner | `make security` runs osv-scanner over every dev-tool lockfile after the secrets scan. |
| [0008](0008-one-release-version-and-current-schemas-only.md) | Stamp One Release Version in Every Report and State, and Read Only the Current Schemas | Reports and state files carry the one release version; readers accept only the current schemas. |
| [0009](0009-adrs-hold-only-the-current-decision.md) | ADRs Hold Only the Current Decision; Stale and Unnecessary Ones Are Deleted | Agents read ADRs as instructions, so an ADR states only today's decision and a stale one is deleted. |

## Requirements: `spec/decisions/`

| ADR | Title | Summary |
| --- | --- | --- |
| [0001](../../../spec/decisions/0001-constraint-artifact.md) | Use the prohibitions section as the deny list | The deny list is the instruction file's prohibitions section; there is no separate allow list. |
| [0002](../../../spec/decisions/0002-lint-in-the-gate.md) | Lint is gated through `format:check` | `check` is `format:check`, `typecheck` and `test`; `format:check` must include the lint rules. |
| [0003](../../../spec/decisions/0003-dependency-scan-verb.md) | Any verb may run the dependency scan; `security` is the preferred one | A verb must run a dependency scan; it should be `security`, and CI should run it too. |

## Audit recipe and tools: `audit/docs/architecture/adrs/`

| ADR | Title | Summary |
| --- | --- | --- |
| [0001](../../../audit/docs/architecture/adrs/0001-tools-import-engine.md) | Tools Import the Engine in Process | Audit tools import the engine in process through `load_engine`; the engine never imports the tools. |

## Implement recipe and tools: `implement/docs/architecture/adrs/`

Number 0001 is retired in this group.

| ADR | Title | Summary |
| --- | --- | --- |
| [0002](../../../implement/docs/architecture/adrs/0002-progress-writes-state-in-target.md) | `progress.py` Writes the State Files Inside the Target | `progress.py` may write only the target's two state files under `docs/agentic-readiness/`. |
| [0003](../../../implement/docs/architecture/adrs/0003-push-and-pr-policy.md) | The Implement Recipe Pushes and Opens a Pull Request Only When the Owner Opted In | The recipe stops at a local branch unless the owner opted in to a push and one pull request. |

## Audit engine: `audit/engine/docs/architecture/adrs/`

The engine's own index is in its [`architecture/README.md`](../../../audit/engine/docs/architecture/README.md#adr-index).

| ADR | Title | Summary |
| --- | --- | --- |
| [0001](../../../audit/engine/docs/architecture/adrs/0001-report-not-a-gate.md) | The Audit Reports; It Does Not Gate | A completed scan exits 0 whatever it finds; `--fail-on` exists but is off by default. |
| [0002](../../../audit/engine/docs/architecture/adrs/0002-read-only-and-tier-c-opt-in.md) | Read-Only by Default; Tier-C Probes Are Opt-In | The engine never writes to or installs into the target; Tier-C probes run only on explicit request. |
| [0003](../../../audit/engine/docs/architecture/adrs/0003-component-depth-declared-depth-1.md) | Component Depth: Declared Components, Depth 1 | Only components a build manifest declares are scored, and only at depth 1. |
| [0004](../../../audit/engine/docs/architecture/adrs/0004-no-llm-in-v1.md) | No LLM Calls in v1 | The engine is deterministic and standard-library only, with no model calls. |
| [0005](../../../audit/engine/docs/architecture/adrs/0005-module-layout-and-zipapp-distribution.md) | Module Layout and Zipapp Distribution | The package tree is the source; a zipapp is the distributable; nothing needs installing. |
| [0006](../../../audit/engine/docs/architecture/adrs/0006-private-check-helpers-and-ignore-engine.md) | Private Check Helpers and the Ignore Engine | Checks share two private helpers, `audit/ignore.py` and `rules/checks/_common.py`; no new stage or pack. |
| [0007](../../../audit/engine/docs/architecture/adrs/0007-json-report-render-contract.md) | The JSON Report Is the Render Contract; the Markdown Is a Template Over It | The JSON report (schema v2) is the contract; the Markdown report is a code template over it. |
| [0008](../../../audit/engine/docs/architecture/adrs/0008-what-counts-as-the-repository.md) | What Counts as the Repository | Runners rank depth first; templates, examples and fixtures are set aside, and the report lists them. |
| [0009](../../../audit/engine/docs/architecture/adrs/0009-nested-ignore-files-and-negation.md) | Nested Ignore Files and Negation | Four checks use a scoped matcher that honours nested `.gitignore` files and negation; the walk is unchanged. |
