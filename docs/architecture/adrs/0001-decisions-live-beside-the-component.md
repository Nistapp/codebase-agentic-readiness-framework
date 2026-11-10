# 0001. Decisions Live Beside the Component They Govern

## Context

The repository holds parts that change for different reasons: requirements (`spec/`), the audit recipe and its tools,
the implement recipe and its tools, and the audit engine. Each has its own decision records, in its own folder.
Without a root index, a reader who starts at the root cannot find them, and the engine's DOC-04 check finds no ADR
directory at the root.

## Decision

A decision is recorded in the ADR folder of the component it governs: `spec/decisions/`,
`audit/docs/architecture/adrs/`, `implement/docs/architecture/adrs/`, or `audit/engine/docs/architecture/adrs/`. A
decision that spans components goes in this folder. This folder's [`README.md`](README.md) indexes all of them, and is
updated in the same change set as any ADR added elsewhere.
Every ADR, in every folder, is written and changed under the [ADR policy](../../ADR_POLICY.md).

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| Records in each component folder, with no root index | A reader who starts at the root cannot find them, and DOC-04 finds no ADR directory at the root. |

## Consequences

* An ADR stays next to the code it explains and moves with it.
* The root has one place to start, and the engine's DOC-04 check finds a numbered ADR and an index here.
* The index can drift from the folders it lists. Adding an ADR without a row here is a defect in that change.
