# Decisions of record

Decisions are recorded next to the component they govern. This page indexes all five groups. The rule for where a new
one goes is [ADR 0001](0001-decisions-live-beside-the-component.md). Add a row here in the same change as the ADR.
The root router is [`docs/README.md`](../../README.md).

## Repository level: `docs/architecture/adrs/`

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [0001](0001-decisions-live-beside-the-component.md) | Decisions Live Beside the Component They Govern | Accepted | 2026-11-05 |
| [0002](0002-dev-integrates-main-releases.md) | `dev` Integrates Every Change; `main` Takes Only Promotions From `dev` | Accepted | 2026-11-08 |
| [0003](0003-dependabot-security-pull-requests-only.md) | Dependabot Opens Security Pull Requests Only; Major Versions Are Advisory | Accepted | 2026-11-08 |
| [0004](0004-plain-language-rules-and-a-prose-check.md) | Plain-Language Rules in One File, Checked by a Standard-Library Prose Check | Accepted | 2026-11-08 |

## Requirements: `spec/decisions/`

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [0001](../../../spec/decisions/0001-constraint-artifact.md) | Use the prohibitions section as the deny list | Accepted | 2026-10-10 |
| [0002](../../../spec/decisions/0002-lint-in-the-gate.md) | Lint is gated through `format:check` | Accepted | 2026-11-05 |

## Audit recipe and tools: `audit/docs/architecture/adrs/`

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [0001](../../../audit/docs/architecture/adrs/0001-tools-import-engine.md) | Tools Import the Engine in Process | Accepted | 2026-10-10 |

## Implement recipe and tools: `implement/docs/architecture/adrs/`

The numbers continue from the audit group; both groups were one set before v0.3.

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [0002](../../../implement/docs/architecture/adrs/0002-progress-writes-state-in-target.md) | `progress.py` Writes the State Files Inside the Target | Accepted | 2026-10-29 |
| [0003](../../../implement/docs/architecture/adrs/0003-push-and-pr-policy.md) | The Implement Recipe Pushes and Opens a Pull Request Only When the Owner Opted In | Accepted | 2026-11-05 |

## Audit engine: `audit/engine/docs/architecture/adrs/`

The engine's own index is in its [`architecture/README.md`](../../../audit/engine/docs/architecture/README.md#adr-index).

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [0001](../../../audit/engine/docs/architecture/adrs/0001-report-not-a-gate.md) | The Audit Reports; It Does Not Gate | Accepted | 2026-09-28 |
| [0002](../../../audit/engine/docs/architecture/adrs/0002-read-only-and-tier-c-opt-in.md) | Read-Only by Default; Tier-C Probes Are Opt-In | Accepted | 2026-09-28 |
| [0003](../../../audit/engine/docs/architecture/adrs/0003-component-depth-declared-depth-1.md) | Component Depth: Declared Components, Depth 1 | Accepted | 2026-09-28 |
| [0004](../../../audit/engine/docs/architecture/adrs/0004-no-llm-in-v1.md) | No LLM Calls in v1 | Accepted | 2026-09-28 |
| [0005](../../../audit/engine/docs/architecture/adrs/0005-module-layout-and-zipapp-distribution.md) | Module Layout and Zipapp Distribution | Accepted | 2026-09-28 |
| [0006](../../../audit/engine/docs/architecture/adrs/0006-private-check-helpers-and-ignore-engine.md) | Private Check Helpers and the Ignore Engine | Accepted | 2026-09-28 |
| [0007](../../../audit/engine/docs/architecture/adrs/0007-json-report-render-contract.md) | The JSON Report Is the Render Contract; the Markdown Is a Template Over It | Accepted | 2026-09-30 |
| [0008](../../../audit/engine/docs/architecture/adrs/0008-what-counts-as-the-repository.md) | What Counts as the Repository | Accepted | 2026-11-05 |
| [0009](../../../audit/engine/docs/architecture/adrs/0009-nested-ignore-files-and-negation.md) | Nested Ignore Files and Negation | Accepted | 2026-11-05 |
