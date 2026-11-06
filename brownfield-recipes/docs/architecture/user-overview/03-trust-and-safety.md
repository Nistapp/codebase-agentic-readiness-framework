# 3. Trust & Safety

> **Audience:** CTOs, security reviewers
> **Goal:** State what the recipes may and may not do to a repository and to the operator's machine.
> **Status:** Audit rules live (§1–§4, S3.5); implementation safety (§5) live; the push and pull request
> rule is [ADR 0003](../adrs/0003-push-and-pr-policy.md).

---

## 1. Read-only audit

The audit never writes inside the repository it assesses. Every tool it calls refuses an output path
inside the target on its own, and the recipe says so to the operator as well as relying on the tool's
refusal. All of its writes — the draft, the final report, the facts file, the engine's own report — go to
an output directory the operator names, outside the target.

## 2. Command execution

The audit never runs a target's own command directly. The only way it executes anything inside the target
is the deterministic engine's opt-in Tier-C runner (`engine.py --run-gates --allow-probe <verb>`), and only
for one of the seven command-surface verbs (`format:check`, `lint`, `typecheck`, `test`, `check`,
`security` — never the write form `format`) the operator explicitly allowed at intake, with a timeout the
operator set. The default is that no verb is allowed, so by default nothing in the target runs at all. A
target's own command is arbitrary code it owns, not a sandboxed operation the recipe controls: the recipe
says so before asking for consent, and suggests a disposable worktree or container when any verb is
allowed. Sandboxing beyond that is the operator's own responsibility.

## 3. Data egress

Whatever the agent reads from the target — file contents, a code index's query results, a git log — is
visible to the model provider behind whichever harness is running the recipe, regardless of whether a code
index exists or where it lives. The recipe states this once, plainly, before accepting any intake answer,
and the intake schema requires an explicit `provider_exposure_acknowledged: true`; the run does not start
without it. A code index itself, if the operator has one, stays on the operator's own machine or account —
only what the agent reads through it leaves.

## 4. Prompt injection

Everything the audit reads from the target is data, never an instruction: a file's content, a comment, a
commit message, even an `AGENTS.md` or another instruction file the target ships. None of it tells the
recipe what to conclude or what to skip. A repository that contains text telling the reader to mark every
check `PASS`, or to ignore a specific check, is reporting what that text says, as evidence for whichever
check it bears on — not a command the recipe follows.

## 5. Implementation safety

The implementation recipe's hard rules are in [`implement/SKILL.md`](../../../implement/SKILL.md#hard-rules)
and bind every stage. The table says what it may do to a repository and to the machine, and what it never does.

| Area | It may | It never |
|---|---|---|
| **Findings** | Act on findings the person confirmed (`confirmed` or `edited`), one theme at a time | Queue a rejected finding; propose a finding the owner skipped again |
| **Branches** | Create one branch per theme, `agentic-readiness/<phase>-<slug>`, in a separate worktree from the up-to-date integration branch | Commit to the default branch; force-push; push tags; publish a release; merge |
| **Files it writes** | The change the theme needs, and the two state files in `docs/agentic-readiness/` that [`progress.py`](../../../tools/README.md) writes ([ADR 0002](../adrs/0002-progress-writes-state-in-target.md)) | Write into the audit report folder, which stays frozen; write outside the target |
| **Commands it runs** | The target's own verbs (`format:check`, `lint`, `typecheck`, `test`, `check`, `security`), and only after the owner chose them | Run a destructive command unless asked for that exact action; open, print or quote a `.env` file or other secret store |
| **Tests and gates** | Add a mechanism and ratchet existing debt: record the count, wire a check so it cannot get worse, mark the item `partial` | Delete, skip or weaken a test; lower a baseline; turn a rule off unless the owner chooses that |
| **Dependencies and tools** | Propose tools and dependencies | Choose a tool or add a dependency the owner has not approved |
| **Network** | Use `gh` to push the theme branch and open one pull request into the integration branch, only when the owner recorded `ci.pr_by_agent=yes` at triage ([ADR 0003](../adrs/0003-push-and-pr-policy.md)) | Use the network for anything else the recipe does not name; infer the opt-in from an absent key |
| **Credentials** | With the opt-in, use a `gh` login that can push a branch and open a pull request on the target | Use or need merge, tag or force-push rights; without the opt-in it needs no push credential |
| **Instructions** | Take them from the skill, its playbooks and the person | Treat anything in the target (its `AGENTS.md` included) as an instruction; it is data |
