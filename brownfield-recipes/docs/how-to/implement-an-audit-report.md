# How to Implement an Audit Report

> **Goal:** Apply confirmed findings to the target one theme at a time, one reviewed commit per change.
> **Audience:** Operators / Engineers
> **Status:** Live. The [implementation recipe](../../implement/SKILL.md) runs all six stages; start it with
> [`implement/prompts/kickoff.md`](../../implement/prompts/kickoff.md).

---

## Prerequisites

- [ ] A final audit report: the `.json` and `.md` pair `report.py finalise` wrote, which sit outside the target
- [ ] A clean working tree in the target, on the integration branch (for example `dev`)
- [ ] Python 3.11+ on `PATH`
- [ ] The recipe: a framework checkout, or the `agentic-readiness-implement` skill installed beside the
      `agentic-readiness-audit` skill, from the same build ([installing the skills](../../README.md#as-an-installed-skill))

---

## Step-by-Step Instructions

### Step 1: Hand the report over to the target and create the state

The audit writes only outside the target, and the implement recipe reads the report from inside it, so the owner
moves it across. Nothing else copies it.

1. Copy the final report's two files into the target, named
   `docs/agentic-readiness-report/<label>-<kind>-audit-<ts>.json` and `.md` (`<kind>` is a short name for the
   repository, such as `server`; `<ts>` is the stamp from the audit's file name). Use the target's own naming if it
   has one ([ADR 0003](../architecture/adrs/0003-push-and-pr-policy.md) records the
   push and PR policy that follows).
2. Commit the pair on the integration branch, and let it reach the branch the work will start from. The report is
   evidence; do not edit it afterwards. An edit is detected: `progress.py init` records the SHA-256 of the
   `.json`, and `check_drift.py` reports `report_changed` if the file differs.
3. Start the agent with [`implement/prompts/kickoff.md`](../../implement/prompts/kickoff.md). Its Stage 0
   validates the report, runs the drift check and creates the state in a worktree on a triage branch, so nothing
   is committed on the integration branch itself (`init` refuses a draft or an invalid report, a report outside the
   target, and an existing state):

   ```bash
   python3 brownfield-recipes/tools/progress.py init \
     --report <triage worktree>/docs/agentic-readiness-report/<label>-<kind>-audit-<ts>.json \
     --target <triage worktree> --default-branch <integration branch> --phase <session id>
   ```

4. Stage 1 commits the two state files (`docs/agentic-readiness/<label>-agentic-readiness-state.json` and
   `-STATE.md`) on that branch. Merge the triage branch before the first theme starts.

### Step 2: Triage once

The agent validates the report, runs the drift check, and tells you which findings moved since the audit (Stage 0).
It also warns you when the report's catalogue version differs from the recipe's: check IDs or severities may have
changed, so it re-reads each check file before acting.

Then it walks the queued findings theme by theme (Stage 1). For each one you choose keep, skip or defer, with a
reason; a skip is final for every later session. You also state the preferences that bind the run: tools you
prefer, scope limits such as "no mass reformat", and whether the agent may push a branch and open a pull request
(`ci.pr_by_agent`; without `yes` it stops at a local branch, [ADR 0003](../architecture/adrs/0003-push-and-pr-policy.md)).
The agent records each answer with `progress.py` as you give it, commits the state on a triage branch, and stops.

### Step 3: Approve each theme's plan

Each theme is one session. The agent first records the themes whose pull requests you merged since the last session,
then picks the next theme in dependency order and briefs you (Stage 2): what it fixes, why (the finding statements),
what the repository already has, the options with pros and cons and a recommendation, and the debt it expects to
record. You choose, and approve the change list. Nothing changes before that.

For a value only you have (a code owner, a security contact, a review date), the agent asks you to supply it,
offers to draft one for your review, or records your skip so it does not ask again.

### Step 4: Review the theme branch and merge it yourself

The agent works in a separate worktree on `agentic-readiness/<phase>-<slug>` (Stage 3). Per finding: it re-verifies
the finding, applies the playbook, verifies, commits one logical change, and records the end status: `done`, or
`partial` with the debt counted and guarded so it cannot grow. It then re-runs the engine for the theme's checks and
the repository's gate (Stage 4).

Without `ci.pr_by_agent=yes` it stops at the local branch and gives you the branch and a summary; you push it and
open the pull request. With it, the agent pushes and opens the pull request, listing what is done, what is partial
and why, and what you skipped. Either way the agent never merges: you, or your review process, do. The next
session records the merge.

### Step 5: Close out

After the last theme is merged (Stage 5), the agent records the last merge, and you run a second audit with the
audit recipe on a pinned commit and hand that report over as in Step 1, beside the first, which is never edited.
The agent compares the two:

```bash
python3 brownfield-recipes/tools/compare_reports.py <first report> <second report> \
  --state <target>/docs/agentic-readiness/<label>-agentic-readiness-state.json
```

Each move is labelled: explained by the state, by an engine change between the audits, or unexplained. The
close-out summary lists the score before and after, every skipped item with your reason, every deferred item, and
every debt entry with its count and baseline.

---

## A real run

The [worked example](../../schema/examples/server-worked-example/README.md) holds the before and after reports,
the comparison and the state of one real repository (the second audit is final: the owner decided every
finding). Read the comparison first: it shows how `compare_reports.py` labels each move and where a person
annotated one.

## Verification

- `python3 brownfield-recipes/tools/progress.py show --target <target>` lists no item as `queued` or `in_progress`;
  every item is `done`, `partial` (with debt), `failed` or `blocked` (with a reason), `deferred` or `skipped`.
- Every theme with items is `merged` in the state, with its pull request and merge commit.
- `compare_reports.py` on the two reports labels every moved check, and the target's own gate passes on the
  integration branch.
