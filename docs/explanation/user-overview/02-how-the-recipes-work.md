# 2. How the Recipes Work

> **Audience:** CTOs, engineering leads, adopters
> **Goal:** Walk through the audit stages and the implementation loop at a level a reader can evaluate.
> **Status:** Audit stages live (S3.5). Implementation Stages 0 to 5 live (IR12).

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
3. **Plan a theme (live).** Record the themes merged since the last session, pick the next theme in
   dependency order, and brief the owner: what, why, the options, the debt to expect. The owner approves the
   change list.
4. **Apply (live).** One branch per theme from the integration branch, in a separate worktree. Per finding:
   re-verify, apply the playbook, verify, commit one logical change, record the end status; existing debt is
   recorded and guarded instead of mass-fixed.
5. **Close the theme (live).** Re-check the theme's checks with the engine and run the repository's gate. With
   the owner's `ci.pr_by_agent=yes`, push and open one pull request; otherwise stop at the local branch. Never
   merge.
6. **Close-out (live).** After the last theme, a full re-audit with the audit recipe, compared with the first
   report (`compare_reports.py`), and one list of what was skipped, deferred and left as debt.

## 3. What the user decides

In an audit: the intake answers (Stage 1), whether to run any of the target's own commands and which
(Stage 1), the plan before assessment starts (Stage 2), and the disposition of every finding (Stage 5) —
blockers one at a time, with their evidence, everything else in batches. In an implementation: at
intake, what to do about drifted findings; at triage, keep, skip or defer for every finding and the
preferences for the run; per theme, the option for each choice and the change list; and the merge of every
theme's branch, which only the owner or their review process does.

Both recipes ask and report in the same way. They follow one shared prompt,
[`audit/prompts/talking-to-the-user.md`](../../../audit/prompts/talking-to-the-user.md), which both skill
bundles carry. Each message puts the bottom line first. Each question gives the options, a recommendation and the
default. Each claim that matters is marked *checked*, *inferred* or *assumed*, and the labels match the evidence
the report records. The prompt fixes the layout of the audit intake, the finding confirmation, the triage, each
status report and each pull request description.

## 4. Reading the report

A report's `checks[]` carry a verdict (`PASS`, `PARTIAL`, `FAIL`, `NOT_APPLICABLE`, `UNKNOWN` or `ATTEST`)
and a severity (`BLOCKER`, `DEGRADER`, `COSMETIC`) per Phase-1 requirement, each with cited `evidence[]` or
`searches[]` — nothing is scored on an unstated hunch. `findings[]` are the issues those checks raised,
each with a disposition a person set. `summary` is computed by the tools from the checks and findings, not
written by the model, and the validator recomputes it and refuses a mismatch. `unattested[]` lists what a
human verified or the repository's owner attested to instead, which earns no score either way. Each piece
of evidence carries its own `captured_by` (`tool` or `agent`), and, when a tool recorded it, which one and
its version — so a reader can tell a deterministic reading from an agent's own search.
