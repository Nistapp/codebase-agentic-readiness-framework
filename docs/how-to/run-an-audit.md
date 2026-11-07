# How to Run an Audit

> **Goal:** Produce a validated, user-confirmed readiness report for an existing repository without modifying it.
> **Audience:** Operators / Engineers
> **Status:** Live. The recipe is [`brownfield-recipes/audit/SKILL.md`](../../audit/SKILL.md) (S3.5).

---

## Prerequisites

- [ ] A coding agent with shell access (Claude Code, opencode, Codex, Cursor)
- [ ] Python 3.11+ on `PATH`
- [ ] A clone of this repository
- [ ] Read access to the target repository

---

## Step-by-Step Instructions

### Step 1: Optional: write an intake file

Pre-answer Stage 0's questions in `audit-intake.<label>.json`, matching
[`audit-intake.schema.json`](../../schema/audit-intake.schema.json), so a re-audit or a headless run needs
no interview. Whoever is present when the agent starts still hears the provider-exposure statement; writing
the file in advance does not skip that.

### Step 2: Start the agent with the kickoff prompt

Paste [`audit/prompts/kickoff.md`](../../audit/prompts/kickoff.md), or invoke the installed skill
(`agentic-readiness-audit`), naming the target repository's path.

### Step 3: Answer Stage 0, and approve Stage 1's plan

Without an intake file, the agent asks Stage 0's questions one at a time and stops rather than guesses at
an ambiguous answer; see [`SKILL.md`](../../audit/SKILL.md#stage-0--intake). Then, in Stage 1, review the
stack profile the agent chose (shipped or derived), the thirteen check families it will work through, what
is excluded, and which commands (if any) it may run read-only against the target, before it starts Stage 2.

### Step 4: Confirm findings

In Stage 4, decide on each `BLOCKER` finding on its own, with its evidence in front of you, then decide on
the remaining findings in batches; see [`SKILL.md`](../../audit/SKILL.md#stage-4--confirm). An evaluation
run (`eval_mode: true`) skips this stage: `accept-all` confirms every finding by policy, `defer-all` leaves
them all pending, and either way its report is a draft, never final.

### Step 5: Collect the outputs

Stage 5 writes `<label>.audit-report.<stamp>.json` and `<label>.audit-report.<stamp>.md` beside the draft,
in the output directory the intake named. An evaluation run stops at the draft instead; `finalise` always
refuses one.

---

## Verification

- `python3 brownfield-recipes/tools/validate_report.py <report>` exits `0`.
- The report's `status` is `final`, and its `summary.phase1_score` and `blockers_remaining` read as
  expected for the repository.
