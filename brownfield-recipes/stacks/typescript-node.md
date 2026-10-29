# TypeScript and Node

> Follows the anatomy in [`README.md`](README.md). Covers npm, pnpm and Yarn on Node; a framework
> section (NestJS) is added under its own heading, not a separate file (§1 there). `shipped`, per
> `run_context.stack_profile` (DP §5.6).

---

## Detection signals

`facts.json`'s `stack` section already read this: `ecosystems: ["node"]` from a `package.json`
anywhere in the tree; `package_managers` from the lockfile at the repository root
(`package-lock.json` → npm, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lockb` → bun);
`test_frameworks` from `vitest.config.*` or `jest.config.*`; `ci_providers` from
`.github/workflows/*.yml`. A multi-component repository with a `package.json` in each component but
none at the root reads `ecosystems: ["node"]` correctly (the engine's `node` signal has no folder
depth) but an empty `package_managers`/`ci_providers`/`test_frameworks` when the lockfile and CI config
also live only inside a component — state that gap to the user rather than reading it as "no package
manager."

## Command-surface map

The authoritative runner is `package.json`'s `scripts` (`spec/command-surface.md`'s own table); every
verb keeps its own name, including `format:check` — the colon is a legal npm script name, so none of
the Make/Gradle/pyproject aliases apply here. Typical realisation on a repository that already uses the
seven verbs: `format` → `prettier --write .`, `format:check` → `prettier --check .`, `lint` → `eslint`
(a bare `tsc`/`tsc --noEmit` re-run under `lint` is not a linter, see TOOL-02), `typecheck` → `tsc
--noEmit`, `test` → the detected runner (`vitest run` / `jest`), `check` → `format:check && typecheck
&& test` in that order, `security` → `npm audit --audit-level=high` (`pnpm audit`/`yarn npm audit` for
the other managers). `npm run <verb>` invokes any of them (`npm test` for `test` alone); `pnpm run
<verb>`; `yarn <verb>`.

## Tooling defaults

Formatter: Prettier (`.prettierrc*`, or `package.json`'s `"prettier"` key). Linter: ESLint, flat config
(`eslint.config.*`) by default since ESLint 9, with the legacy `.eslintrc*` format (or `package.json`'s
`"eslintConfig"` key) still read on an older repository — all three forms are current engine signals
(§Verified) — alternatives you may find: Biome, as a combined formatter and linter, replacing both the
Prettier and ESLint rows; its ecosystem does not run ESLint's own plugins, so a repository with
plugin-dependent rules keeps a minimal ESLint config alongside it rather than switching outright. Type
checker: `tsc` reading `tsconfig.json`'s `compilerOptions.strict`. Test runner: Vitest or Jest, both
seen across the corpus (§Verified) — a third option, Node's own built-in test runner, is untested here.
Dependency scanner: the package manager's own `audit` command; `audit-ci` or Snyk are alternatives that
pin a fixed severity threshold in config rather than a CLI flag.

## Execution determinism

Pin Node with `package.json`'s `engines.node` (the shallowest pin; a `>=` range is accepted by EXEC-01
but a `.nvmrc`/`.tool-versions` exact version is stronger and preferred for a freshly adopted
repository) — none of the three profile repos committed an `.nvmrc`, all three used `engines.node`
alone. The lockfile matching the declared package manager (`package-lock.json` for npm, etc.) must be
git-tracked at the repository root; `npm ci`/`pnpm install --frozen-lockfile`/`yarn install
--immutable` is the non-interactive setup path (EXEC-03), never a bare `install`.

## CI idiom

GitHub Actions is the provider seen in all three repositories: `actions/checkout`, then
`actions/setup-node` with `node-version` pinned to the same major as `engines.node` and `cache: npm`
(or the matching `pnpm`/`yarn` cache key), then `npm ci`, then `npm run check` (or the repository's own
`check` script) as the one gate job calls. A matrix across `ubuntu-latest`/`macos-latest`/
`windows-latest` was seen in one repository (§Verified) and is a strong signal, not a requirement.

## Baseline / ratchet

None of the three repositories carries a formal baseline file for this stack (`BASE-01` reads `FAIL` or
`UNKNOWN` on all three, not verified further here — out of this leaf's scope). ESLint has no built-in
baseline format; the common no-new-violations pattern is a committed suppression file an incremental
run writes once (`eslint --max-warnings=0` on changed files only, enforced in CI, with a separate,
unenforced full-repo run) or an `overrides` block that lowers severity for files not yet migrated to a
stricter ruleset. A `tsconfig.json` migrating to `strict` can ratchet file by file through `exclude` or
per-file `// @ts-strict-ignore`-style comments as each file is proven strict, rather than flipping the
flag repository-wide at once.

## Boundaries

None of the three repositories uses npm/pnpm/yarn workspaces (each is a single package, or — the
microservices repository — two unrelated packages composed only through Docker, not an npm workspace),
so workspace-boundary enforcement is untested here. Where workspaces are used, `eslint-plugin-import`'s
`no-restricted-paths`, or `eslint-plugin-boundaries`, encodes which workspace may import which; `tsconfig.json`'s `paths` aliases express the same boundary for the type checker, but alone enforce
nothing — an alias without a matching lint rule is not a boundary, only a convenience import path.

## Engine coverage

Reliable as the engine reads it: `CMD-01`/`CMD-02` (the npm-scripts runner resolver, `_common`, reads
`package.json` scripts directly and completely); `TOOL-01`–`TOOL-03` (Prettier/ESLint/`tsconfig.json`
strict are all in the engine's fixed filename and key lists); `EXEC-01`/`EXEC-02` (`engines.node` and
the three lockfile names are read directly). Needs independent agent verification: `TOOL-02` when the
"linter" verb is actually a `tsc`/formatter re-run under another name (the engine credits only a real
linter config, but a human-readable script name can still mislead a quick read); `EXEC-02` on a
multi-component repository, where a lockfile that exists only inside one component reads correctly as
`PASS` for that component but the engine's own root-only manifest comparison leaves consistency
`PARTIAL` — confirm by reading which component the finding actually names, not the repository as a
whole.

## Pitfalls

A `package-lock.json` listed in a component's own `.gitignore` is a real, observed failure mode in this
corpus (two of four Node projects checked): `EXEC-02` correctly reads `FAIL` ("untracked"), not a false
positive — the project genuinely cannot reproduce an install deterministically from git alone. A
Create-React-App-based component (`react-scripts`) ships with only `start`/`build`/`test` in
`package.json` and no `format`, `lint`, `typecheck`, `check` or `security` script at all — `CMD-01`'s
`FAIL` here is accurate, not an engine gap, and the remediation is to add the missing scripts, not to
distrust the verdict. None of the four Node projects checked wires a local hook chain (`TOOL-05`
`FAIL`/`UNKNOWN` throughout) or defines a `security` verb beyond the two that call `npm audit` directly
(the CRA app and the NestJS service have none).

## NestJS

Detected by `@nestjs/core` in the manifest and `nest-cli.json`'s presence; neither is in the engine's
own `ecosystems` table, so a profile-aware agent names it, the engine still only ever says `node`.
Command-surface delta from `@nestjs/schematics`' own default scaffold: `build` → `nest build`
(typechecks as a side effect, so a separate `typecheck` script is often absent); `lint` → `eslint
"{src,apps,libs,test}/**/*.ts" --fix` — the `--fix` flag is a write invocation under a read-only verb
name, a direct `CMD-04` `FAIL` the engine correctly reports, not a false positive; `test` → Jest reading
`package.json`'s own `jest` key (`rootDir: src`); a separate `test:e2e` runs a second Jest config,
`test/jest-e2e.json`. `format:check`, `check` and `security` are not in the scaffold and must be added.
Tooling default: the schematic still generates legacy `.eslintrc.js`, not flat config. The scaffolded
`tsconfig.json` sets neither `strict` nor any of its component flags (`strictNullChecks`,
`noImplicitAny` default `false`) — `TOOL-03` reading `FAIL` on an untouched Nest scaffold is accurate,
not a gap. Boundaries: Nest's own module system is the idiom — a provider a `@Module` does not list in
`exports` is invisible outside it — enforced by Nest's DI container at run time, not by a lint rule;
`eslint-plugin-boundaries` is additional, not idiomatic, and was not seen in this corpus. Env files
often live under a non-root `environments/` directory (`local.env`, `local.env.example`) rather than a
root `.env.example` — `EXEC-04` only reads root-named files, so a root-only miss here is the engine's
real, root-only scope, not a defect to argue around; tell the user where the real example file is.

## Verified

2026-10-13, against: `agentic-tdd` (npm, Prettier, `tsc --noEmit` under `lint`, no ESLint, Vitest,
GitHub Actions matrix across three OSes, `engines.node >=22.19.0`, no `.nvmrc`); the
Digital-Assistant-SDK (npm, Prettier, ESLint, Jest, `tsconfig.json` strict, GitHub Actions with
dependabot and a cross-OS workflow, `engines.node >=22`); the microservices repository's two Node
components, `udan-self-signup` (Create-React-App, no command surface beyond `start`/`build`/`test`,
gitignored lockfile) and `nestjs-keycloak-admin` (NestJS — see its own section, ESLint, Jest, gitignored
lockfile, no CI config in the repository at all). Read via `tools/facts.py` and direct inspection of
each repository's `package.json`, lockfile, `tsconfig.json` and `.github/workflows/`; no target command
was run. Tooling defaults checked against current docs the same day: flat config (`eslint.config.*`) is
the default since [ESLint 9](https://eslint.org/blog/2023/12/eslint-v9.0.0-alpha.0-released/), with
`.eslintrc*` removed in ESLint 10, so a repository on the legacy format reads correctly but is on a
deprecated path, worth a note to the user though not a check of its own; Biome's ecosystem still lacks
ESLint's own plugins, per a 2026 comparison ([reintech.io](https://reintech.io/blog/eslint-vs-biome-javascript-linting-comparison-2026)).
