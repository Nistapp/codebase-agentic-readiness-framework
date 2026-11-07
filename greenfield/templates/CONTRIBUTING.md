# Contributing

Thank you for considering contributing to this project!

## Getting Started

1. Fork the repository and clone it locally.
2. Ensure you have Node.js 24+ installed (`nvm use`).
3. Run `npm install` to install dependencies.
4. Create a feature branch from `dev`: `git checkout -b feat/<slug>`.

## Development Workflow

1. Make your changes in `src/`.
2. Add or update tests in `test/` (mirrors `src/` structure).
3. Run `npm run check` (format:check → typecheck → test) and `npm run security` to verify — the identical commands CI runs.
4. Commit using Conventional Commits: `<type>(<scope>): <description>`.
5. Push and open a PR against `dev`.

## Coding Standards

- See `AGENTS.md` for the full coding standards.
- TypeScript `strict` mode — zero errors from `npm run typecheck`.
- No `any`. Use `unknown` and narrow.
- Named imports only. Group: Node built-ins → third-party → internal.
- Files: `kebab-case.ts`. Types: `PascalCase`. Interfaces: `I`-prefixed.

## Architecture Rules

- `src/core/` must have **zero** imports from `src/infrastructure/` or `src/cli/`.
- New OS operations → `src/infrastructure/` + interface in `src/core/interfaces.ts`.
- New runtime dependencies require an ADR in `docs/architecture/adrs/`.

## Testing

- Framework: Vitest. Import from `vitest`.
- No real I/O in tests — use DI stubs.
- Every public method: ≥1 positive + ≥1 negative test.
- Never `.skip` a failing test — fix it.
- Gate: `npm run check` before every commit.

## Documentation

- `docs/` is the single source of truth for permanent documentation; `artefacts/` is transient scratch (agents must not read it unless you pass an explicit path).
- Every `.md` file under `docs/` MUST follow [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md).
- A change that alters a public interface, observable behaviour, architecture, or an ADR MUST update the affected doc pages and their source anchors in the same PR.
- New ADRs: `docs/architecture/adrs/NNNN-short-title.md`, plus a row in `docs/architecture/README.md`.
