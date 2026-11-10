# 0003. Any verb may run the dependency scan; `security` is the preferred one

* **Status:** Accepted
* **Date:** 2026-11-10
* **Last reviewed:** 2026-11-10
* **Deciders:** K. C. Ramakrishna (v0.3.5.1 question 3.1, accepted 2026-11-10)

---

## Context

[REQ-SH-030](../readiness-requirements.md#req-sh-030--dependency-vulnerability-scan) said "the `security` verb
MUST run a dependency vulnerability scan". The `TOOL-04` check gives `PASS` when any verb runs the scan, for example
a `check` that runs `osv-scanner`. A repository that scans inside `check` is as safe for an agent as one with a
`security` verb: the risk is an unscanned dependency, not the name of the verb. The requirement and the check
disagreed, and the requirement is normative, so one of them had to change.

## Decision

1. **A verb MUST run a dependency vulnerability scan.** Any verb of the [command surface](../command-surface.md)
   counts.
2. **The verb SHOULD be `security`.** It is the verb the command surface names for this gate.
3. **CI SHOULD run the same scan**, as before.

`TOOL-04` already reads the requirement this way, so no verdict moves.

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Keep MUST on `security`; `TOOL-04` gives `PARTIAL` when only another verb runs the scan | Moves verdicts on repositories that are safe today, for a naming rule. Needs an engine change and a ruleset bump. |

## Consequences

### Positive

* The requirement and `TOOL-04` agree; no engine change.
* A repository that scans inside `check` or `test` is not marked down for the verb's name.

### Negative / Trade-offs

* A repository may have no `security` verb at all and still meet the MUST. The SHOULD keeps the name visible.
