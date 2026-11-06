# 2. How the Recipes Work

> **Audience:** CTOs, engineering leads, adopters
> **Goal:** Walk through the audit stages and the implementation loop at a level a reader can evaluate.
> **Status:** Audit stages live (S3.5). Implementation Stages 0 and 1 live; Stages 2 to 5 Planned (IR12).

> [!NOTE]
> Planned: implementation Stages 2 to 5 (plan a theme, apply, close the theme, close-out). Their outline is in
> [`implement/SKILL.md`](../../../implement/SKILL.md#stages); the stage text is written in IR12.

---

## 1. Audit stages

The audit recipe ([`audit/SKILL.md`](../../../audit/SKILL.md)) works through six stages, in order, against
one repository at a time, writing nothing inside it:

1. **Intake.** Answer who is running this, what the agent may read or run, and under what confirmation
   policy, before anything else happens. A run never starts without acknowledging that the model provider
   sees whatever the agent reads from the repository.
2. **Recon.** Inventory the repository and detect its stack (a shipped profile, or a derived best guess,
   labelled as which).
3. **Assess.** Run the deterministic engine once, import its verdicts, then work through the thirteen
   check families: verify every blocker independently, resolve what the engine could not judge, and record
   every issue found as a finding with its evidence.
4. **Synthesize.** Read the whole draft back, not check by check, to catch what a per-check pass cannot:
   one root cause scored under two checks, or two families whose findings contradict each other.
5. **Confirm.** The person decides on each blocker alone; the rest are decided in batches. A headless
   evaluation run skips this stage by a fixed policy instead of asking anyone.
6. **Finalise.** Write the final report and its Markdown rendering — unless this is an evaluation run, in
   which case there is no final report, only the draft.

## 2. Implementation loop

The implementation recipe ([`implement/SKILL.md`](../../../implement/SKILL.md)) takes a final,
owner-confirmed audit report and closes its confirmed findings in the audited repository, one theme at a
time. Everything a later session needs to resume lives in a state file inside the target, described in the
[state contract](../../../implement/state.md).

1. **Intake (live).** Validate the report and refuse one that is not `final` (`validate_report.py`); check
   how far the repository has moved since the audit (`check_drift.py`) and re-verify every finding whose
   evidence changed; create the state file from the report, or read the existing one to resume
   (`progress.py init` or `show`).
2. **Triage (live).** Walk the confirmed findings theme by theme. The owner keeps, skips or defers each, with
   a reason, and states preferences that bind the whole run (`progress.py skip`, `defer`, `pref`). A skipped
   finding is never proposed again.
3. **Plan a theme, apply, close the theme, close-out.** Planned (IR12): one branch per theme from the
   integration branch, a playbook per finding class, existing debt recorded instead of mass-fixed, and a
   full re-audit at the end compared with the first report (`compare_reports.py`).

## 3. What the user decides

In an audit: the intake answers (Stage 1), whether to run any of the target's own commands and which
(Stage 1), the plan before assessment starts (Stage 2), and the disposition of every finding (Stage 5) —
blockers one at a time, with their evidence, everything else in batches. In an implementation: at
intake, what to do about drifted findings; at triage, keep, skip or defer for every finding and the
preferences for the run. Plan approval and each change are Planned (IR12).

## 4. Reading the report

A report's `checks[]` carry a verdict (`PASS`, `PARTIAL`, `FAIL`, `NOT_APPLICABLE`, `UNKNOWN` or `ATTEST`)
and a severity (`BLOCKER`, `DEGRADER`, `COSMETIC`) per Phase-1 requirement, each with cited `evidence[]` or
`searches[]` — nothing is scored on an unstated hunch. `findings[]` are the issues those checks raised,
each with a disposition a person set. `summary` is computed by the tools from the checks and findings, not
written by the model, and the validator recomputes it and refuses a mismatch. `unattested[]` lists what a
human verified or the repository's owner attested to instead, which earns no score either way. Each piece
of evidence carries its own `captured_by` (`tool` or `agent`), and, when a tool recorded it, which one and
its version — so a reader can tell a deterministic reading from an agent's own search.
