# Decisions of record

Decisions are recorded next to the component they govern. This page indexes the three sets; the rule for where a new
one goes is [ADR 0001](0001-decisions-live-beside-the-component.md).

## Repository level

| ADR | Decision |
| --- | --- |
| [0001](0001-decisions-live-beside-the-component.md) | Decisions live beside the component they govern; this folder indexes them |

## Requirements: `spec/decisions/`

| ADR | Decision |
| --- | --- |
| [0001](../../../spec/decisions/0001-constraint-artifact.md) | Use the prohibitions section as the deny list |
| [0002](../../../spec/decisions/0002-lint-in-the-gate.md) | Lint is gated through `format:check` |

## Recipes and tools: `brownfield-recipes/docs/architecture/adrs/`

| ADR | Decision |
| --- | --- |
| [0001](../../../brownfield-recipes/docs/architecture/adrs/0001-tools-import-engine.md) | Tools import the engine in process |
| [0002](../../../brownfield-recipes/docs/architecture/adrs/0002-progress-writes-state-in-target.md) | `progress.py` writes the state files inside the target |
| [0003](../../../brownfield-recipes/docs/architecture/adrs/0003-push-and-pr-policy.md) | Push and pull request policy of the implement recipe |

## Audit engine: `brownfield-recipes/deterministic-audit/docs/architecture/adrs/`

The engine's decisions are indexed in the table in its
[`architecture/README.md`](../../../brownfield-recipes/deterministic-audit/docs/architecture/README.md); the ADRs
themselves are in [`adrs/`](../../../brownfield-recipes/deterministic-audit/docs/architecture/adrs/). ADR 0001 to 0009
cover the report-not-a-gate rule, read-only operation, component depth, no LLM calls, the module layout, the ignore
engine, the report contract, what counts as the repository, and nested ignore files.
