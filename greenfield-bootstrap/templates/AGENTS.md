# AGENTS.md

> **Template Version:** 1.1.0
> **Purpose:** This file governs how AI coding agents (Antigravity, Claude Code, Gemini CLI, etc.) work inside this repository.
> **Action:** Read it in full before making any change to the codebase.

---

## 1. Project Overview

**[Project Name]** is a Node.js / TypeScript project built to world-class enterprise standards. It uses an agentic pipeline orchestration model where specialized sub-agents handle specific tasks (e.g., Design, Contracts, Implementation, Refactoring, Security).

**Key Design Invariants:**
- **Zero Specification Drift:** Code and architecture specs MUST remain synchronized.
- **Empirical Grounding:** Never document aspirational features as existing facts.
- **Strict Typing:** No `any` types; all code must pass strict TypeScript checks.
- **Test-Driven:** Every public method requires positive and negative tests.
- **Clean Architecture:** Strict DI (Dependency Injection) boundaries between core logic and infrastructure.

---

## 2. Architectural Boundaries

Agents MUST respect the following structural rules:

- **Core Engine (`src/core/`)**: Pure logic. Zero OS dependencies. Must NEVER import from `src/infrastructure/` or `src/cli/`.
- **Dependency Injection**: All DI interfaces live in `src/core/interfaces.ts`.
- **Infrastructure (`src/infrastructure/`)**: All filesystem, git, and OS-level operations belong here and must implement interfaces from `src/core/interfaces.ts`.
- **CLI / Wiring (`src/cli/`)**: The composition root. Handles DI wiring, `process.env` reads, and session management.

---

## 3. Tech Stack & Tooling

| Concern | Tool | Rule |
|---|---|---|
| Language | TypeScript 7.x | Strict mode, `noUncheckedIndexedAccess`, `isolatedModules` |
| Runtime | Node.js 24.x | ESM (`"type": "module"`) |
| Imports | NodeNext | Always use `.js` extensions in local import paths |
| Format | Biome | `npm run format` (write) / `npm run format:check` (verify) |
| Lint | Biome | `npm run lint` (read-only) |
| Type-check | `tsc --noEmit` | `npm run typecheck` — covers `src/` and `test/` |
| Full gate | `npm run check` | `format:check` → `typecheck` → `test` |
| Dependency audit | `npm run security` | `npm audit --audit-level=high` |
| Tests | Vitest 4.x | `npm test`. Coverage thresholds enforced via `npm run test:coverage` |
| Build | `tsc` + asset copy | `npm run build` / `npm run build:full` |
| Git Hooks | Husky + commitlint | Conventional Commits required |

### 3.1 Standardized command surface

These six verbs are the **only** sanctioned way to verify work in this repository. Use
them exactly as written — do not invent ad-hoc invocations (`npx vitest`, `tsc file.ts`,
`eslint .`) and do not run a check that CI does not run.

```bash
npm run format        # rewrite formatting in place
npm run format:check  # read-only verify: formatting + lint rules
npm run lint          # read-only lint
npm run typecheck     # tsc --noEmit for src/ and test/ — MUST be zero errors
npm test              # full suite — MUST be 100% pass
npm run check         # THE gate: format:check → typecheck → test
npm run security      # dependency-CVE gate
```

> [!IMPORTANT]
> `npm run check` is the single pre-commit and pre-PR gate, and CI invokes the identical
> script name. If you cannot make `npm run check` pass, report the blocker — never relax
> the gate (no `.skip`, no silenced rule, no weakened assertion) to get green.

---

## 4. Codebase-Memory-MCP Integration

The `codebase-memory-mcp` tool is mandatory. You must use it proactively before reading full files.

**Priority Order:**
1. `get_architecture` — Understand structure.
2. `search_graph` / `query_graph` — Find symbols and relationships.
3. `trace_path` — Understand call chains.
4. `get_code_snippet` — Read specific function bodies.
5. `detect_changes` — Check index freshness after edits.

**File Reading Policy:**
- **NEVER** open entire large files without a compelling reason. Query by symbol name instead.
- **`artefacts/` is prohibited.** It holds transient, unverified scratch documents. Agents MUST NOT crawl, glob, grep, or read files there, and MUST NOT treat its contents as architectural source of truth. Access is permitted only when the human passes a specific file path in their prompt.

---

## 5. Coding Standards

### 5.1 TypeScript Rules
- **Strict mode is non-negotiable.** `npm run typecheck` must produce zero errors.
- **No `any`.** Use `unknown` and narrow explicitly.
- **No `@ts-ignore` or `as any`.**
- **No `const enum`.** (Breaks `isolatedModules`). Use standard `enum`.
- **Async Handling:** All async functions must explicitly handle errors. No silent rejections.
- **Test Files:** Are type-checked via `tsconfig.test.json`. Ensure mocks/stubs match DI interfaces exactly.

### 5.2 Naming & Style
- **Files:** `kebab-case.ts`
- **Classes/Types:** `PascalCase`
- **Interfaces:** `IPascalCase` (Prefixed with `I`)
- **Private Fields:** `#fieldName` (ES2022 hard-private)
- **Test Helpers:** Suffix with `Stub` or `Mock`.
- **Formatting:** Handled automatically by Biome (`npm run format`).

### 5.3 Documentation Rules
- **`docs/` is the single source of truth** for permanent documentation; `artefacts/` is transient and off-limits to agents (see §4).
- **Every `.md` file under `docs/` MUST follow `docs/STYLE_GUIDE.md`** — the canonical authoring rules. Link to the relevant section rather than restating rules here, because restated rules drift.
- **Definition of done:** when a change alters a public interface, observable behaviour, architecture, or an ADR, update the affected documentation pages, their source anchors, and the ADR index tables **in the same change set**. Pure internal refactors with no observable or documentation impact do not require doc edits.
- New or revised ADRs MUST follow `docs/STYLE_GUIDE.md` § ADR Lifecycle and be registered in `docs/architecture/README.md`.

---

## 6. Testing Standards

- **Framework:** Vitest (import from `vitest`, not `jest`).
- **Location:** `test/` directory, mirroring `src/` structure.
- **Coverage:** Every public method requires ≥1 positive and ≥1 negative test. Enforced by coverage thresholds in CI.
- **Mocks:** Use `vi.fn()` and fully typed stubs. Do NOT mock entire modules unless strictly necessary.
- **No Real I/O:** Tests must NOT touch the real filesystem, git, or network. Use injected DI stubs.
- **Pass Rate:** 100% required. Never `.skip` or comment out failing tests.
- **Gate:** Run `npm run check` before committing — the identical command CI runs.

---

## 7. Git Conventions

### 7.1 Branching
- `main` = Production (released code only).
- `dev` = Active development.
- Feature branches = `feat/<slug>`, `fix/<slug>`, `refactor/<slug>`.
- **All PRs to `main` MUST originate from `dev`.**

### 7.2 Commits (Conventional Commits)
Format: `<type>(<scope>): <description>`
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `perf`, `revert`.
- Enforced locally by `commitlint` via Husky.
- AI Agents use: `chore(ai): pass-[N] - <description>`.

---

## 8. Documentation Standards (Diátaxis)

`docs/STYLE_GUIDE.md` is the canonical rule set for everything written under `docs/`. This
section only states the layout and the triggers; the style guide states the rules.

- **Single Source of Truth:** `docs/` is the only valid directory for permanent documentation.
- **Categories:** content is classified as tutorial, how-to, reference, or explanation; architecture material lives under `docs/architecture/`.
- **ADRs:** Architectural Decision Records live in `docs/architecture/adrs/NNNN-short-title.md` and are indexed in `docs/architecture/README.md`. New runtime dependencies or architectural changes require an ADR.
- **Transience:** Agent scratchpads, implementation plans, and WIP research go in `artefacts/` (git-ignored contents, and off-limits to agents per §4).
- **Glossary:** domain terms are defined once in `docs/architecture/glossary.md` and used consistently everywhere else.

---

## 9. Environment & Secrets

- Secrets belong in `.env` (NEVER committed).
- Template secrets belong in `.env.example`.
- **NEVER** log, echo, or output the contents of `.env` or sensitive variables to the terminal.
- Do not read `process.env` directly in core logic. Read it at the CLI layer and pass it via a configuration object.

---

## 10. Explicit "Do Not Do" Rules

1. ❌ **Do not** introduce runtime dependencies without an approved ADR.
2. ❌ **Do not** use `any`, `// @ts-ignore`, or `as any`.
3. ❌ **Do not** merge failing tests. Fix them.
4. ❌ **Do not** skip `codebase-memory-mcp` indexing at the start of a session.
5. ❌ **Do not** make real API/Network/Disk calls in unit tests.
6. ❌ **Do not** manually modify files in `dist/`.
7. ❌ **Do not** commit directly to `main`.
8. ❌ **Do not** bypass Biome formatting or linting checks.
9. ❌ **Do not** document aspirational features as existing facts.
10. ❌ **Do not** edit files under `docs/` without following `docs/STYLE_GUIDE.md`.
11. ❌ **Do not** verify work with an ad-hoc command. Use the six standardized verbs in §3.1.
12. ❌ **Do not** read, grep, or glob `artefacts/` unless the human passes an explicit file path (§4).
