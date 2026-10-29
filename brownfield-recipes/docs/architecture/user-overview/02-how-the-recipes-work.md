# 2. How the Recipes Work

> **Audience:** CTOs, engineering leads, adopters
> **Goal:** Walk through the audit stages and the implementation loop at a level a reader can evaluate.
> **Status:** Audit stages live (S3.5); the implementation loop (§2) is Planned.

> [!NOTE]
> Planned: §2, the implementation loop. Stage design for it is in the design plan only. Filled in by
> roadmap step S5.4.

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

- TBD: verify, explain, propose, approve, apply, verify, commit, per finding. Planned (S5.4).

## 3. What the user decides

In an audit: the intake answers (Stage 1), whether to run any of the target's own commands and which
(Stage 1), the plan before assessment starts (Stage 2), and the disposition of every finding (Stage 5) —
blockers one at a time, with their evidence, everything else in batches. Planned for the implementation
loop: plan approval and each change, once S5.4 exists.

## 4. Reading the report

A report's `checks[]` carry a verdict (`PASS`, `PARTIAL`, `FAIL`, `NOT_APPLICABLE`, `UNKNOWN` or `ATTEST`)
and a severity (`BLOCKER`, `DEGRADER`, `COSMETIC`) per Phase-1 requirement, each with cited `evidence[]` or
`searches[]` — nothing is scored on an unstated hunch. `findings[]` are the issues those checks raised,
each with a disposition a person set. `summary` is computed by the tools from the checks and findings, not
written by the model, and the validator recomputes it and refuses a mismatch. `unattested[]` lists what a
human verified or the repository's owner attested to instead, which earns no score either way. Each piece
of evidence carries its own `captured_by` (`tool` or `agent`), and, when a tool recorded it, which one and
its version — so a reader can tell a deterministic reading from an agent's own search.
