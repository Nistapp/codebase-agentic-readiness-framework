# 1. Purpose & Non-Goals

> **Audience:** CTOs, engineering leads, adopters
> **Goal:** Explain what the brownfield recipes do, why an agent runs them instead of a fixed script, and what they refuse to do.
> **Status:** Live for the audit recipe (v0.1). The implementation recipe (v0.2.0): Stages 0 to 5,
> the state contract and its tools, and all thirteen playbooks are written.

---

## 1. What the recipes are

Two Markdown recipes an agent runs against an existing repository, in order: [`audit`](../../../audit/SKILL.md),
and [`implement`](../../../implement/SKILL.md) (v0.2.0), which acts on the audit's confirmed
findings one theme at a time. Its six stages, its state tools and its thirteen playbooks are written, and every
theme has been applied to two repositories. The
audit report — [documented in `schema/SCHEMA.md`](../../../audit/schema/SCHEMA.md) — is the only contract between
them: `implement` reads a finalised report and nothing else, so it can be written, reviewed and run
independently of whatever produced that report. Either recipe is plain `SKILL.md` plus
command-line tools, so any coding agent with shell access can run it — see
[How the Recipes Work](02-how-the-recipes-work.md) for the audit's six stages.

## 2. Why recipes plus tools

A fixed script cannot tell a real `.env` leak from a test fixture's deliberately fake one, or a Quarkus
app's implicit entry point from a genuinely missing one — judgment calls like these need a reader, not a
regex. An LLM alone cannot be trusted to count files, check a path exists or recompute a score
consistently. The recipes invert the obvious design: deterministic tools do the counting, validation and
rendering — the same input always produces the same output — and the agent's judgment is reserved for
exactly the places a tool cannot resolve on its own: verifying a `BLOCKER` finding against the real
source, weighing a disputed verdict, or writing an `override_reason` with evidence attached. The agent's
read of a target repository is the one fallible, best-effort step; the schema, the validator and the
catalogue are the parts that never guess.

## 3. Relationship to the deterministic engine

The engine, [`audit/engine/`](../../../audit/engine/README.md), is a separate, standard-library-only
Python engine with no LLM and no network, migrated into this repository with its own history. It never
writes to the repository it scans. The audit recipe runs it first, imports its verdicts as a starting
draft, then works through the check families on top of that draft: it verifies every `BLOCKER` the engine
raised independently, against the real evidence, before it counts; it resolves whatever the engine could
not judge on its own (`UNKNOWN`); and it may override an engine verdict, but only with a cited
`override_reason`, never by assertion. The engine is the floor, not the ceiling — see
[Trust & Safety](03-trust-and-safety.md) for exactly what it is and is not allowed to do while it runs.

## 4. Non-goals

- **No certification score.** A report's `phase1_score` measures how close one repository is to Phase 1
  readiness at one point in time; it is not a badge, a ranking or a vendor comparison.
- **No CI gate.** The audit is read-only and advisory. Nothing here fails a pull request or blocks a merge
  — that decision, if a team wants one, is theirs to build on top of a report.
- **No auto-merge, and no push unless the owner opted in.** The implementation recipe branches, changes
  and stops for the operator to review and push. It pushes the branch and opens a pull request only when the
  owner recorded `ci.pr_by_agent=yes` at triage. It never merges, tags or force-pushes
  ([ADR 0003](../../../implement/docs/architecture/adrs/0003-push-and-pr-policy.md)).
- **No Phase 2–4 work.** These recipes cover Phase 1 (Agentic Bootstrap) only. The framework's later
  phases are out of scope for this project entirely, not merely deferred.
- **Proven on two repositories only.** `implement/` (v0.2.0) was applied to a Java service and to one private
  repository. The second audit of each is final; the Java one is published as a
  [worked example](../../../audit/schema/examples/server-worked-example/README.md).
