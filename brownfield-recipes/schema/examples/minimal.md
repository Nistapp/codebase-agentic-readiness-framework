# Agentic readiness audit: example-service

Repository `example-service` with no commit recorded. Started `2026-10-10T09:00:00+00:00`.

> [!NOTE]
> **Draft.** This report is not final and can still change. 0 findings await a decision.

## Readiness summary

- **Phase-1 score: 1.00**, over 1 scored check
- **0 blockers remaining**
- **Unattested:** 0 requirements that no check settles, listed below

No scored check is UNKNOWN. No agent finding is waiting for a person's decision.

The score is the weighted share of the scored checks that the repository meets. The weights are BLOCKER 3, DEGRADER 2, COSMETIC 1; PASS earns full credit, PARTIAL half, and FAIL and UNKNOWN none. The framework sets no pass mark, and a score says nothing about whether agents will write correct code.

### Unattested requirements

A person's review or the owner's declaration verifies these requirements, so no check gives them a verdict, and they are outside the score. One leaves this list only when a person records an outcome or the owner declares it.

No unattested requirement is recorded in this report.

## Blockers remaining

No scored BLOCKER check is open.

## Overrides of the engine's verdicts

No engine verdict was overridden.

## Checks

1 check: 1 PASS.

- **PASS**: The requirement is met. Full credit.
- **PARTIAL**: Part of the requirement is met. Half credit.
- **FAIL**: The requirement is not met. No credit.
- **UNKNOWN**: The evidence could not be gathered. No credit, and never read as a pass.
- **NOT_APPLICABLE**: The check does not apply to this repository. It is outside the score.
- **BLOCKER**: Agent work is impossible, unsafe or unverifiable. Fix before onboarding agents.
- **DEGRADER**: Agent work is possible but unreliable or wasteful.
- **COSMETIC**: Hygiene. Fix when convenient.

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `AGT-11` | Instructions are specific and not inferable | DEGRADER | agent | yes | PASS | — | AGENTS.md states a release rule and a boundary that the code does not reveal. |

## Check details

Each check below is one that is not met, was overridden, was judged by the agent, or raised a finding, in order of severity. A check that passed and was settled by a tool has only its row in the table above; its evidence is in the JSON report.

### DEGRADER checks

#### AGT-11: Instructions are specific and not inferable

**PASS** · DEGRADER · agent · scored · confidence high

AGENTS.md states a release rule and a boundary that the code does not reveal.

**Evidence**

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

## Provenance

| Field | Value |
|---|---|
| Report status | draft |
| Schema version | `0.1` |
| Repository label | `example-service` |
| Path | `/work/example-service` |
| Commit | none recorded |
| Branch | — |
| Started | `2026-10-10T09:00:00+00:00` |
| Finalised | — |
| Recipe | `brownfield-audit` 0.1.0 |
| Catalogue version | `0.1.0` |
| Framework revision | — |
| Engine | No engine report is part of this report. |
| Agent (self-reported) | `claude-code` with `claude-sonnet-5-5` |

## Run context

| Field | Value |
|---|---|
| Evaluation mode | no |
| Confirmation policy | `interactive` |
| Provider exposure acknowledged | yes: the model provider receives what the agent reads from the target |
| Code index | `none` |
| Probes | none: no command of the target was run |
| Excluded | none |
| Known components | none |
| Stack profile | — |

---

Rendered from the JSON report by `render_report.py`. The JSON report is the record.
