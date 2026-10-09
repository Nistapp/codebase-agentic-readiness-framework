# How to Run an Audit

> **Goal:** Produce a validated, user-confirmed readiness report for an existing repository without modifying it.
> **Audience:** Operators / Engineers
> **Status:** Planned (placeholder).

> [!NOTE]
> Planned. The audit recipe does not exist yet. Filled in by roadmap step S3.5.

---

## Prerequisites

- [ ] A coding agent with shell access (Claude Code, opencode, Codex, Cursor)
- [ ] Python 3.11+ on `PATH`
- [ ] A clone of this repository
- [ ] Read access to the target repository

---

## Step-by-Step Instructions

### Step 1: Optional: write an intake file

- TBD: pre-answer the intake questions in `audit-intake.json`.

### Step 2: Start the agent with the kickoff prompt

- TBD: paste `audit/prompts/kickoff.md`, or invoke the installed skill.

### Step 3: Approve the plan

- TBD: review the families and scope the agent proposes.

### Step 4: Confirm findings

- TBD: blockers one by one; other findings in batches.

### Step 5: Collect the outputs

- TBD: `audit-report.json` and `audit-report.md` in the output directory.

---

## Verification

- TBD: `python3 brownfield-recipes/tools/validate_report.py <report>` exits 0 and the report status is `final`.
