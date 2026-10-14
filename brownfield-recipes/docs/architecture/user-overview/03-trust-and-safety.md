# 3. Trust & Safety

> **Audience:** CTOs, security reviewers
> **Goal:** State what the recipes may and may not do to a repository and to the operator's machine.
> **Status:** Audit rules live (§1–§4, S3.5); implementation safety (§5) is Planned.

> [!NOTE]
> Planned: §5, implementation safety. Those rules are in the design plan and roadmap only (A18). Filled in
> by roadmap step S5.4.

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

- TBD: branch only, per-item approval, never weaken tests, never push. Planned (S5.4).
