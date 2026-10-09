# Readiness summary

Normative. This page defines the headline of a readiness report: two numbers and one list, always shown together. It adds no other score, level or grade. A report that shows the score without the blockers and the unattested list misleads, so a report MUST show all three.

The summary is computed from the verdicts of the checks that verify the [requirements](readiness-requirements.md). Verdicts and methods are defined in [README.md](README.md#verification-methods).

## Severity

Every check carries a severity. The severity says what an unmet check costs today, and it sets the check's weight.

| Severity | Meaning | Weight |
|---|---|---|
| BLOCKER | Agent work is impossible, unsafe or unverifiable. Fix before onboarding agents. | 3 |
| DEGRADER | Agent work is possible but unreliable or wasteful. | 2 |
| COSMETIC | Hygiene. Fix when convenient. | 1 |

## The two numbers

### Phase-1 score

The score is the weighted share of the scored checks that the repository meets.

- **Scored checks** are the checks of phase 1 that apply to the repository and that are not informational, not blocked and not emitters.
- **Credit** per verdict: PASS 1, PARTIAL 0.5, FAIL 0, UNKNOWN 0.
- **Weight** per check: its severity weight.
- Requirements that no check settles, those verified by `human` or `attested`, have no verdict. They stay out of both sides of the fraction and appear in the unattested list instead.

```text
score = sum(weight x credit) / sum(weight)     over the scored checks that have a verdict
```

The score is 0 when there are no such checks. It is stored rounded to four decimal places and shown to two.

Example: a BLOCKER check that passes, a DEGRADER check that is PARTIAL and a COSMETIC check that is UNKNOWN give (3 x 1 + 2 x 0.5 + 1 x 0) / (3 + 2 + 1) = 0.6667.

UNKNOWN stays in the denominator at zero credit. A check that could not gather its evidence lowers the score; it is never treated as met and never dropped.

The verdict that counts is the report's verdict for the check, after any override. An override of a tool's verdict needs counter-evidence and a recorded reason, as the `automated` method requires.

### Blockers remaining

Blockers remaining is the number of scored BLOCKER checks whose verdict is not PASS: FAIL, PARTIAL or UNKNOWN. The report shows how many are in each state, on the same line, for example "7 blockers remaining: 5 FAIL, 1 PARTIAL, 1 UNKNOWN".

It counts checks, not findings. One check can raise several findings, and a check that is UNKNOWN raises none, so a count of findings would hide the checks nobody could verify.

## The unattested list

The report lists every requirement verified by `human` or `attested`, by requirement ID, with its status: pending review or unattested. The list is not a number and does not enter the score. A requirement leaves the list only when a person records an outcome or the owner makes the declaration.

## Qualifiers

Two facts qualify the headline and are shown beside it. They are not additional scores.

- How many scored checks are UNKNOWN. A high count means the score understates the repository rather than certifies it.
- Whether any agent verdict is still waiting for a person to confirm it.

## What the summary does not say

- It defines no maturity level, grade or pass mark, and it does not call a repository "ready". The framework sets no pass mark for Phase 1.
- It does not say that agents will produce correct code. A repository can score 1 and still ship a defect.
- A score for another phase is defined when the requirements of that phase exist.
