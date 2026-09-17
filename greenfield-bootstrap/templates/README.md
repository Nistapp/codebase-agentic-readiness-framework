# [Project Name]

[One-line description: what this package does, and who it is for.]

> **Status:** pre-alpha. The harness (build, checks, CI, docs) is in place; application code is not.

---

## Install

```bash
npm install <package-name>
```

## Development

```bash
nvm use              # pin the Node version from .nvmrc
npm install
npm run check        # THE gate: format:check → typecheck → test
```

| Command | Purpose |
|---|---|
| `npm run format` / `format:check` | Rewrite / verify formatting (Biome). |
| `npm run lint` | Read-only lint. |
| `npm run typecheck` | `tsc --noEmit` for `src/` and `test/`. |
| `npm test` | Vitest suite. |
| `npm run check` | The single pre-commit / pre-PR gate. |
| `npm run security` | `npm audit --audit-level=high`. |
| `npm run build` / `build:full` | Compile to `dist/`. |

CI runs the same script names — there is no CI-only gate.

## Repository layout

| Path | Purpose |
|---|---|
| `src/core/` | Pure logic. Zero OS imports — see `AGENTS.md` §2. |
| `src/core/interfaces.ts` | DI port interfaces (the seam between core and infrastructure). |
| `src/infrastructure/` | Filesystem, git, process, and network adapters. |
| `src/cli/` | Composition root: DI wiring and `process.env` reads. |
| `test/` | Mirrors `src/`. |
| `docs/` | Permanent documentation, governed by `docs/STYLE_GUIDE.md`. |
| `artefacts/` | Transient agent scratch — contents are git-ignored and off-limits to agents. |
| `specs/` | Feature specifications. |

## Conventions

- **`AGENTS.md`** — governs AI coding agents: architectural boundaries, the standardized command surface, the documentation contract, and the do-not-do list. Read it before your first change.
- **`docs/STYLE_GUIDE.md`** — canonical rules for everything under `docs/`.
- **`CONTRIBUTING.md`** — human contributor guide.
- **`RELEASE_PROCESS.md`** — release lifecycle and the one-time npm Trusted Publishing setup.

## Before you publish

1. Choose a license and add a `LICENSE` file, then set the `license` field in `package.json`.
2. Add a `description` and `keywords` for npm discoverability.
3. Enable **Trusted Publishing** for this repository in the package settings on npmjs.com (see `RELEASE_PROCESS.md`).
4. Write your first real test, then remove `passWithNoTests` from `vitest.config.ts` and uncomment the coverage thresholds there and the coverage step in `.github/workflows/ci.yml`.
