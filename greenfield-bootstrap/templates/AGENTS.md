# AGENTS.md

> **Template Version:** 1.0.0
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
| Lint/Format | Biome | Run `npm run check` and `npm run format` |
| Tests | Vitest 4.x | Run `npm test`. Coverage enforced via `npm run test:coverage` |
| Git Hooks | Husky + commitlint | Conventional Commits required |

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

---

## 5. Coding Standards

### 5.1 TypeScript Rules
- **Strict mode is non-negotiable.** `npm run lint` must produce zero errors.
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

---

## 6. Testing Standards

- **Framework:** Vitest (import from `vitest`, not `jest`).
- **Location:** `test/` directory, mirroring `src/` structure.
- **Coverage:** Every public method requires ≥1 positive and ≥1 negative test. Enforced by coverage thresholds in CI.
- **Mocks:** Use `vi.fn()` and fully typed stubs. Do NOT mock entire modules unless strictly necessary.
- **No Real I/O:** Tests must NOT touch the real filesystem, git, or network. Use injected DI stubs.
- **Pass Rate:** 100% required. Never `.skip` or comment out failing tests.

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

All documentation must follow the guidelines in `docs/STYLE_GUIDE.md`.

- **Single Source of Truth:** `docs/` is the only valid directory for permanent documentation.
- **ADRs:** Architectural Decision Records live in `docs/architecture/adrs/`. New dependencies or architectural changes require an ADR.
- **Transience:** Agent scratchpads, implementation plans, and WIP research go in `artefacts/` (which is git-ignored).

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
