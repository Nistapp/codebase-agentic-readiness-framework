# Agentic readiness audit: example-service

> [!NOTE]
> **Draft.** This report is not final and can still change. 0 findings await a decision.

> [!NOTE]
> This audit reports; it does not gate. A check that could not be settled is UNKNOWN: it earns no credit and is never shown as a pass.

## Provenance

| Field | Value |
|---|---|
| Target | `/work/example-service` |
| Commit | none recorded |
| Status | draft |
| Started | `2026-10-10T09:00:00+00:00` |
| Finalised | — |
| Recipe | `brownfield-audit` 0.1.0, catalogue `0.1.0` |
| Engine | No engine report is part of this report. |
| Framework revision | — |
| Agent (self-reported) | `claude-code` with `claude-sonnet-5-5` |
| Probes | none: no command of the target was run |
| Report schema | `0.1` |

## Readiness summary

- **Phase-1 score: 1.00**, over 1 scored check
- **0 blockers remaining**
- **Unattested:** 0 requirements that no check settles, listed below

No scored check is UNKNOWN. No agent finding is waiting for a person's decision.

The score is the weighted share of the scored checks that the repository meets. The weights are BLOCKER 3, DEGRADER 2, COSMETIC 1; PASS earns full credit, PARTIAL half, and FAIL and UNKNOWN none. The framework sets no pass mark, and a score says nothing about whether agents will write correct code.

### Unattested requirements

A person's review or the owner's declaration verifies these requirements, so no check gives them a verdict, and they are outside the score. One leaves this list only when a person records an outcome or the owner declares it.

No unattested requirement is recorded in this report.

## Checks by verdict and severity

The first table counts every check in the report. The second counts the scored checks only.

| Verdict | Checks | Credit | Meaning |
|---|---:|---:|---|
| PASS | 1 | 1 | The requirement is met. |
| PARTIAL | 0 | 0.5 | Part of the requirement is met. |
| FAIL | 0 | 0 | The requirement is not met. |
| UNKNOWN | 0 | 0 | The evidence could not be gathered. It is never read as a pass. |
| NOT_APPLICABLE | 0 | outside the score | The check does not apply to this repository. |
| **Total** | **1** |  |  |

| Severity | Weight | Meaning | Scored checks | Not met |
|---|---:|---|---:|---:|
| BLOCKER | 3 | Agent work is impossible, unsafe or unverifiable. Fix before onboarding agents. | 0 | 0 |
| DEGRADER | 2 | Agent work is possible but unreliable or wasteful. | 1 | 0 |
| COSMETIC | 1 | Hygiene. Fix when convenient. | 0 | 0 |

## Checks that need attention

Each row is a finding, or a check that has none. A check is listed when it is not met, was overridden, was judged by the agent, or raised a finding. Evidence is grouped by who captured it, and a quote or command output is under Evidence in full. The decision on a finding is one of these:

- **interactive**: Decided by the person, on this finding alone.
- **batch**: Decided by the person, as one of a group of findings that are not blockers.
- **policy**: Set by the confirmation policy, not by a person.

### Blocker checks

There is no BLOCKER check in this report.

### Degrader checks

0 of the 1 scored DEGRADER check are not met.

| Check | Verdict | What we found | Evidence | Fix | Decision |
|---|---|---|---|---|---|
| `AGT-11` Instructions are specific and not inferable<br>agent, confidence high | **PASS** | AGENTS.md states a release rule and a boundary that the code does not reveal. | **agent** `AGENTS.md:14-15` (quote in Evidence in full) | — | — |

### Cosmetic checks

There is no COSMETIC check in this report.

## Overrides of the engine's verdicts

No engine verdict was overridden.

## Evidence in full

Quotes and command output that the tables above point to, each under the check that cites it.

### AGT-11: Instructions are specific and not inferable

- `AGENTS.md:14-15` · captured by agent
  ```text
  Never run `npm publish` by hand; releases go through the release workflow.
  ```

## Coverage

**Examined:** nothing is recorded

No scope was skipped.

## Stack and components

| Stack | Detected |
|---|---|
| Ecosystems | — |
| Package managers | — |
| CI providers | — |
| Test frameworks | — |
| Hook managers | — |

No component is recorded.

## Run context

| Field | Value |
|---|---|
| Evaluation mode | no |
| Confirmation policy | `interactive` |
| Provider exposure acknowledged | yes: the model provider receives what the agent reads from the target |
| Code index | `none` |
| Excluded | none |
| Known components | none |
| Stack profile | — |

## Appendix — all checks

All 1 check, grouped by family. The engine's structured payloads, such as the verb matrix, are in the JSON report.

### AGT

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `AGT-11` | Instructions are specific and not inferable | DEGRADER | agent | yes | PASS | — | AGENTS.md states a release rule and a boundary that the code does not reveal. |

---

Rendered from the JSON report by `render_report.py`. The JSON report is the record.
