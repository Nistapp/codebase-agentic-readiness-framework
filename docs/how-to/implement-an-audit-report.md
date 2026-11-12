# How to Implement an Audit Report

> **Goal:** Apply confirmed findings to the target one theme at a time, one reviewed commit per change.
> **Audience:** Operators / Engineers
> **Status:** Live. The [implementation recipe](../../implement/SKILL.md) runs all six stages; start it with
> [`implement/prompts/kickoff.md`](../../implement/prompts/kickoff.md).

---

## Prerequisites

- [ ] A final audit report: the `.json` and `.md` pair `report.py finalise` wrote, outside the target. Their folder
      is the **workspace**, where the run keeps its state
- [ ] A clean working tree in the target, on the integration branch (for example `dev`)
- [ ] Python 3.11+ on `PATH`
- [ ] The recipe: a framework checkout, or the `agentic-readiness-implement` skill installed beside the
      `agentic-readiness-audit` skill, from the same build ([installing the skills](../../audit/README.md#as-an-installed-skill))

---

## Step-by-Step Instructions

### Step 1: Point `init` at the report

The audit's output folder is the implement workspace. The report stays there, and the state goes beside it.
Nothing of the run's own goes into the target, and nothing is committed or pushed for it
([ADR 0004](../../implement/docs/architecture/adrs/0004-implement-state-lives-in-the-audit-workspace.md)).

1. Keep the workspace until the run ends. The skips and preferences live only there.
2. Do not copy, commit or edit the report. `progress.py init` records the SHA-256 of the `.json`.
   `check_drift.py` reports `report_changed` when the file differs.
3. Start the agent with [`implement/prompts/kickoff.md`](../../implement/prompts/kickoff.md), with the path to the
   final report's `.json`. Its Stage 0 validates the report, runs the drift check and creates the state:

   ```bash
   python3 implement/tools/progress.py init \
     --report <workspace>/<label>.audit-report.<stamp>.json \
     --target <repo> --default-branch <integration branch> --phase <session id>
   ```

   `init` refuses a draft or an invalid report, a workspace inside the target, and an existing state.
4. The two state files land beside the report: `<label>-agentic-readiness-state.json` and
   `<label>-agentic-readiness-STATE.md`. The target does not change.

### Step 2: Triage once

The agent validates the report, runs the drift check, and tells you which findings moved since the audit (Stage 0).
It also warns you when the report's catalogue version differs from the recipe's: check IDs or severities may have
changed, so it re-reads each check file before acting.

Then it walks the queued findings theme by theme (Stage 1). For each one you choose keep, skip or defer, with a
reason; a skip is final for every later session. You also state the preferences that bind the run: tools you
prefer, scope limits such as "no mass reformat", and whether the agent may push a branch and open a pull request
(`ci.pr_by_agent`; without `yes` it stops at a local branch, [ADR 0003](../../implement/docs/architecture/adrs/0003-push-and-pr-policy.md)).
The agent records each answer with `progress.py` in the workspace as you give it, and stops. Triage changes nothing
in the target.

### Step 3: Approve each theme's plan

Each theme is one session. The agent first records the themes whose pull requests you merged since the last session,
then picks the next theme in dependency order and briefs you (Stage 2): what it fixes, why (the finding statements),
what the repository already has, the options with pros and cons and a recommendation, and the debt it expects to
record. You choose, and approve the change list. Nothing changes before that.

For a value only you have (a code owner, a security contact, a review date), the agent asks you to supply it,
offers to draft one for your review, or records your skip so it does not ask again.

When a step needs a tool your repository lacks, such as a Markdown linter for a README, the agent stops and asks.
It offers two to four options and a recommendation, plus "none". It asks whether to run the tool once or add it to
the repository. Discuss as long as you like; it installs nothing until you name one. "Install whatever you need"
picks no tool, so it still asks about each one. If you choose none, it records that. It then lists the check it
could not run in every report and pull request.

Two themes bring the framework's writing rules to your repository. The `AGENTS.md` theme (T7) adds a "How to write
for people" section; the agent drafts the reader persona and you confirm it. The docs theme (T6) adds "Plain
language" and "Diagrams" sections to your style guide. It records the prose debt of your existing pages and never
rewrites them, unless you name pages for a rewrite. It can also copy a prose check with a ratchet, but only under a
licence you name; by default it adds no tool.

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

After the last theme is merged (Stage 5), the agent records the last merge. Then you run a second audit with the
audit recipe on a pinned commit. It writes to an output folder of its own. The first report stays in the workspace,
and neither report is ever copied or edited. The agent compares the two:

```bash
python3 implement/tools/compare_reports.py <first report> <second report> \
  --state <workspace>/<label>-agentic-readiness-state.json
```

Each move is labelled: explained by the state, by an engine change between the audits, or unexplained. The
close-out summary lists the score before and after, every skipped item with your reason, every deferred item, and
every debt entry with its count and baseline.

---

## When the versions differ

Each report says which framework release made it (`provenance.framework.release`). The agent's tools compare it with
their own release in Stage 0. [Versions](../reference/versions.md) has the whole rule. You can meet four cases:

| What the agent tells you | Why | What to do |
|---|---|---|
| `the report has schema '0.1' (made by framework v0.1.0); these tools read schema '0.2'. Run a new audit ...` | The report comes from a release with another report schema. The tools read only their own. | Run a new audit with this framework. Or install the release that made the report. |
| `the report was made by framework v0.3.3; these tools are v0.3.2. Update the framework ...` | The report is newer than the tools, which may not know its checks. The run stops. | Install release v0.3.3 or later of both skills. Or run a new audit with v0.3.2. |
| `the report was made by framework v0.3.1; these tools are v0.3.2. Verdicts can differ ...` | A warning. The run goes on. | Decide if you want a new audit before the agent acts on the findings. |
| `the report was made at framework commit ...; these tools run at ...` | Both come from checkouts of one release, at two commits. A warning. | Run a new audit if the checks changed in between. |

## A real run

The [worked example](../../audit/schema/examples/server-worked-example/README.md) holds the before and after reports,
the comparison and the state of one real repository (the second audit is final: the owner decided every
finding). Read the comparison first: it shows how `compare_reports.py` labels each move and where a person
annotated one.

## Verification

- `python3 implement/tools/progress.py show --workspace <workspace>` lists no item as `queued` or `in_progress`;
  every item is `done`, `partial` (with debt), `failed` or `blocked` (with a reason), `deferred` or `skipped`.
- Every theme with items is `merged` in the state, with its pull request and merge commit.
- `compare_reports.py` on the two reports labels every moved check, and the target's own gate passes on the
  integration branch.
