# 0003. Any verb may run the dependency scan; `security` is the preferred one

## Context

[REQ-SH-030](../readiness-requirements.md#req-sh-030--dependency-vulnerability-scan) asks for a dependency
vulnerability scan. The `TOOL-04` check gives `PASS` when any verb runs the scan, for example a `check` that runs
`osv-scanner`. A repository that scans inside `check` is as safe for an agent as one with a `security` verb: the
risk is an unscanned dependency, not the name of the verb. The requirement is normative, so it must say the same
as the check.

## Decision

1. **A verb MUST run a dependency vulnerability scan.** Any verb of the [command surface](../command-surface.md)
   counts.
2. **The verb SHOULD be `security`.** It is the verb the command surface names for this gate.
3. **CI SHOULD run the same scan.**

`TOOL-04` reads the requirement this way.

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| MUST on `security`; `TOOL-04` gives `PARTIAL` when only another verb runs the scan | Marks down safe repositories for a naming rule. Needs an engine change and a ruleset bump. |

## Consequences

### Positive

* The requirement and `TOOL-04` agree; no engine change.
* A repository that scans inside `check` or `test` is not marked down for the verb's name.

### Negative / Trade-offs

* A repository may have no `security` verb at all and still meet the MUST. The SHOULD keeps the name visible.
