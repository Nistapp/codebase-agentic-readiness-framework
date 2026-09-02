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
3. Run `npm run lint && npm test` to verify.
4. Commit using Conventional Commits: `<type>(<scope>): <description>`.
5. Push and open a PR against `dev`.

## Coding Standards

- See `AGENTS.md` for the full coding standards.
- TypeScript `strict` mode — zero errors from `npm run lint`.
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
