# 0001. Initial Architecture & Tooling Choices

* **Status:** Accepted
* **Date:** YYYY-MM-DD
* **Last reviewed:** YYYY-MM-DD
* **Deciders:** [@github-handle]

---

## Context

Day-0 decisions for this repository, made before any application code exists. AI coding
agents will work in this repository from commit #1, so the choices below are optimised for
**agent determinism** (one obvious way to verify work) and **bounded blast radius** (explicit
DI seams, no ambient OS access in core logic) rather than for human convenience alone.

Alternatives considered are recorded in the table below, including the option of deferring
the decision and retrofitting later.

---

## Decision

| Concern | Choice | Rationale |
|---|---|---|
| Language | TypeScript, `strict` + `noUncheckedIndexedAccess` + `isolatedModules` | Types are the cheapest contract an agent cannot silently violate. |
| Runtime | Node.js 24 LTS, ESM (`"type": "module"`), `NodeNext` resolution | Pinned via `.nvmrc` so agents and CI resolve identical runtimes. |
| Architecture | Pure core (`src/core/`) behind DI ports; OS access only in `src/infrastructure/` | Keeps the engine testable without I/O and bounds what an agent can touch. |
| Tests | Vitest, `test/` mirroring `src/` | Fast, ESM-native, typed stubs satisfy the DI interfaces. |
| Format + lint | Biome | One binary, one config, one read-only verification command (`biome ci .`). |
| Command surface | Six verbs as package scripts — `format`, `lint`, `typecheck`, `test`, `check`, `security` | Agents, humans, and CI invoke identical names; `npm run check` is the single gate. |
| Documentation | `docs/` is the source of truth, governed by `docs/STYLE_GUIDE.md`; `AGENTS.md` points at it and states the definition of done | Rules live in one place; restating them elsewhere guarantees drift. |
| Docs hosting of transient work | `artefacts/` (git-ignored contents, off-limits to agents) | Keeps unverified scratch out of agent context and out of the index. |

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| ESLint + Prettier instead of Biome | Two tools, two configs, two ignore mechanisms — and `format:check` would no longer cover lint, so the six-verb surface would keep a `lint` verb with nothing behind it. Costed concretely: a 9-file swap that redefines `lint` as a `typecheck` alias. Revisit only if a required rule set is unavailable in Biome. |
| Makefile or Taskfile as the primary runner | Adds a second language and a second definition of the gate. Acceptable only as a thin wrapper over the same package scripts. |
| `lint` as a separate code linter with no type-check verb | Conflating lint and type-check hides which gate failed and tempts agents to "fix" formatting instead of types. |
| Retrofitting standards after the first feature | Standards applied to a moving codebase become a migration project instead of a Day-0 default. |
| Tombstone/superseded ADR stubs | Git is the archive; stale stubs are consumed by agents as current instruction. ADRs here are living, current-state documents. |

---

## Consequences

### Positive
* Any agent can verify its own work with one command (`npm run check`) and get the same
  answer CI gets.
* Boundaries are enforceable by review, because the DI seam and the docs contract are both
  written down on Day 0.
* Onboarding cost for a new agent or engineer is one file (`AGENTS.md`) plus one rule set
  (`docs/STYLE_GUIDE.md`).

### Negative / Trade-offs
* Strict typing and test-type-checking cost more up-front effort per change.
* A single aggregate gate is slower than running only the check you think you need.
* Requiring an ADR for new runtime dependencies adds friction to dependency adoption
  (intentional).

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current codebase.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/NNNN-title.md`.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
