# 0001. Decisions Live Beside the Component They Govern

* **Status:** Accepted
* **Date:** 2026-11-05
* **Last reviewed:** 2026-11-05
* **Deciders:** [@nistapp] (MR07.1, Q13)

---

## Context

The repository holds three kinds of thing that change for different reasons: requirements (`spec/`), the recipes and
their tools, and the audit engine. Each already had its own decision records, in its own folder. A reader who starts at
the root had no way to know they exist, and the repository's own audit found no ADR directory at the root.

## Decision

A decision is recorded in the ADR folder of the component it governs: `spec/decisions/`,
`brownfield-recipes/docs/architecture/adrs/`, or the engine's `docs/architecture/adrs/`. A decision that spans
components goes in this folder. This folder's [`README.md`](README.md) indexes all of them, and is updated in the same
change set as any ADR added elsewhere.

## Consequences

* An ADR stays next to the code it explains and moves with it.
* The root has one place to start, and the engine's DOC-04 check finds a numbered ADR and an index here.
* The index can drift from the folders it lists. Adding an ADR without a row here is a defect in that change.
