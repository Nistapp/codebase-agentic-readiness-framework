# Design — v1 Scaffolder Contract

This file is the reviewed contract for the v1 Python implementation. Decisions are recorded
as **Decision → Alternatives considered → Reason**, in that order.

Source of truth for file content: `~/Projects/codebase-agentic-readiness-framework/greenfield-bootstrap/templates/**`.

---

## D1. Language: Python 3 (stdlib only), single file

**Decision:** v1 is one Python file, no third-party dependencies, run as
`python3 bootstrap.py <target-dir>`.

**Alternatives considered:**
1. TypeScript / Node script (`.mjs` or compiled `.ts`).
2. Bash script.
3. Go/Rust single binary.

**Reason:** the script must run *before* the target project's toolchain exists, and a
TypeScript implementation needs its own `package.json`, lockfile, and either a build step or
`tsx` to execute — in a repository that today contains nothing but Markdown. Python 3 is
present on this machine (3.11.15) and on macOS/Linux dev boxes by default, and the whole job
is directory creation plus string substitution, which the standard library covers with
`pathlib`, `shutil`, and `argparse`. The technical difference is small; the deciding factors
are distribution and maintenance home (see D2).

---

## D2. Distribution path: Python now, npm package later, one template contract

**Decision:** v1 stays a local tool. v2 is a published Node/TypeScript package
(`npx create-agentic-ready`), consuming the identical template contract and CLI surface.

**Alternatives considered:**
1. Go straight to the TypeScript npm package.
2. Keep it Python forever.

**Reason:** destination matters more than language. `shared/Tool-Ecosystem.md` states that
every tool in the framework ships as an independent npm package, so the long-term home for a
Day-0 scaffolder is npm. But building that now costs a package repo, a publish pipeline, and
a build step while the template set is still settling — and the template set is what the
script is worth anything for. A Python v1 lets the contract be exercised today at zero setup;
because v2 re-wraps the same mapping rules, none of the v1 work is thrown away.
`create-agentic-ready` and `create-agentic-readiness` were both verified unclaimed on npm.

---

## D3. No LLM calls in v1

**Decision:** the generator is fully deterministic. Given the same flags and the same
templates, it produces byte-identical output.

**Alternatives considered:**
1. Opt-in `--enrich` flag writing prose only (README intro, `AGENTS.md` §1, first ADR's
   Context, `.env.example` comments).
2. LLM-generated content by default.

**Reason:** the scaffold must be reviewable as a diff and testable as a file set. Generation
that varies per run cannot be regression-tested, and a hallucinated flag in `package.json`,
a workflow, or `tsconfig.json` breaks commit #1 — the failure mode the framework's own
[Risks and Mitigations](../../codebase-agentic-readiness-framework/shared/Risks-and-Mitigations.md)
records as R2 (unsupported generated claims) and R8 (false confidence). Prose is a defensible
LLM job and stays on the roadmap; config is not.

---

## D4. Template content is never duplicated in the script

**Decision:** the script reads `greenfield-bootstrap/templates/**` at runtime and writes the
target. It contains no embedded file bodies.

**Alternatives considered:**
1. Embed all templates in the script so it is a single self-contained file.
2. Ship a copy of the templates inside this repo.

**Reason:** both alternatives create a second source of truth for file content, which is the
exact defect the framework documentation was just cleaned of (restated rules drift). Runtime
reading also lets the framework improve a template and have every future scaffold pick it up
for free. A `--templates <path>` flag keeps it usable from any clone or vendored copy.

---

## D5. Generated skeleton ships with no tests; `check` is green at commit #1

**Decision:** the generated project contains no test files. The generated `vitest.config.ts`
sets `passWithNoTests: true`, and the generated CI does not run a coverage-threshold step
until the first real test lands.

**Alternatives considered:**
1. Generate one real module + test pair so thresholds are meaningful immediately.
2. Ship no tests and leave the 80% coverage thresholds active, accepting a red coverage gate.

**Reason:** `vitest run` exits non-zero when no test files match, and the template's coverage
thresholds (statements 80 / branches 75 / functions 80 / lines 80) cannot be satisfied by an
empty suite — so a fresh scaffold would fail `npm run check` and its own CI at commit #1,
which is precisely what the greenfield promise forbids. Placeholder tests asserting `1 + 1 === 2`
are filler and would be deleted on the first real change. The honest resolution is an
explicitly deferred coverage gate plus a marked `passWithNoTests`, removed with the first test.

**Consequence for the framework repo:** this requires edits to the templates themselves
(`vitest.config.ts`, `github/workflows/ci.yml`) — fixed there, not patched by this script (D4).

---

## D6. License selection is out of scope for v1

**Decision:** the generator does not ask for or write a `LICENSE` file, and writes no
`license` field into `package.json`.

**Alternatives considered:** default MIT; default Apache-2.0; keep the recipe's AGPL-3.0.

**Reason:** v1 is for personal use, so a license choice is premature and would bake an
opinionated default into a generated remote package. Deferred to v2, where it becomes a
required flag rather than a silent default.

---

## CLI surface

| Flag | Default | Purpose |
|---|---|---|
| `<target-dir>` | `.` | Destination; must be empty unless `--force`. |
| `--name` | target dir name (validated against npm naming rules) | Package name; scoped if `--org` is given. |
| `--org` | none | npm scope, e.g. `nistapp` → `@nistapp/<name>`. |
| `--description` | placeholder | `package.json` description. |
| `--author`, `--email` | from `git config` | `package.json` author and `CODEOWNERS`/`SECURITY.md` substitution. |
| `--github-owner` | from `git config user.name` | `CODEOWNERS`, workflow URLs. |
| `--cli` / `--lib` | `--lib` | `--cli` adds `bin` + `src/cli/index.ts`; `--lib` is exports-only. |
| `--templates <path>` | framework clone resolved relative to this repo | Template source override. |
| `--install` | off | Run `npm install` after generating. |
| `--no-git` | git on | Skip `git init` and the first commit. |
| `--dry-run` | off | Print the full plan; write nothing. |
| `--force` | off | Allow a non-empty target directory. |

---

## Template mapping

| Template path | Target path |
|---|---|
| `templates/github/**` | `.github/**` (leading dot added) |
| `templates/interfaces.ts` | `src/core/interfaces.ts` |
| `templates/docs/**`, `templates/infra/**` | unchanged |
| dotfiles (`.editorconfig`, `.env.example`, `.gitignore`, `.nvmrc`) | unchanged |

**Placeholders substituted:** `[Project Name]`, `<project-name>`, `<org>`, `<your-name>`,
`<your-email>`, `<your-github-username>`, `YYYY-MM-DD`.

## Files generated (no template exists)

`package.json` (npm-publish shaped: `exports`, `types`, `files: ["dist"]`, `engines`,
`repository`, `publishConfig`, `prepublishOnly: check && build:full`, the six verbs),
`README.md`, `.husky/pre-commit`, `.husky/commit-msg`, `artefacts/.gitkeep`,
`specs/.gitkeep`, `docs/architecture/adrs/0001-*.md` (rendered from the ADR template with
today's date), and — with `--cli` — `src/cli/index.ts`.

## Gates and verification

1. **Refuse a non-empty target** without `--force`.
2. **`--dry-run`** prints the plan and writes nothing.
3. **Post-write failure gate:** exit non-zero and list offenders if any `<placeholder>` or
   `[Placeholder]` survives, or any expected file is missing. A scaffold that silently ships
   `<your-email>` is worse than one that fails loudly.
4. **Verification when `--install` is given:** `npm run check`, `npm run build`,
   `npm pack --dry-run`, plus an `npm view <name>` collision check.
5. **Manual steps printed at the end:** `nvm use`, set the remote default branch to `dev`,
   enable npm Trusted Publishing for `release-and-sync.yml`.

---

## Known template defects the generator must resolve

Every item below was verified against the templates. Per D4, all template-content fixes
happen in the framework repo; this list is the generator's checklist of what it must not
paper over.

| # | Defect | Resolution |
|---|---|---|
| 1 | `copy:agents` uses `rm -rf` / `cp -r` — breaks on Windows | Fix template: `shx` (as agentic-tdd does) or drop the script when unused |
| 2 | No `package.json` template exists | Generator owns it; must be publish-shaped |
| 3 | Zero tests ⇒ `vitest run` exits 1 and 80% thresholds unreachable ⇒ red gate at commit #1 | D5: `passWithNoTests` + deferred coverage step |
| 4 | Pin drift: recipe says `vitest@^4` (latest 5.0.1), `typescript@^7` (real: 7.0.2), `@types/node` latest tag 22.20.3 vs agentic-tdd's `^25` | Pin deliberately at implementation time; `engines`/`.nvmrc`/CI must agree |
| 5 | Node target inconsistent: `.nvmrc` 24, this box 22.23.1, agentic-tdd CI 22 | One target in `engines` + `.nvmrc` + CI matrix |
| 6 | `enforce-dev-base.yml` assumes remote `dev` exists and is not default | Print the explicit `gh` step; the script cannot know the remote |
| 7 | `biome.json` ignores `*.md`/`*.json`/`*.yml` ⇒ generated docs are never format-checked | Note in generated README; decide whether markdown formatting is enforced |
| 8 | Publishable package pieces missing: `LICENSE`, `README.md`, pinned `release-please-config.json` | Generator covers README (and LICENSE once D6 is revisited) |

---

## Roadmap

| Version | Scope |
|---|---|
| v1 (this) | Python, deterministic, structure + substitution + gates, npm-package skeleton |
| v2 | TypeScript npm package (`create-agentic-ready`), same contract; license flag; re-targeting to non-TS stacks |
| v3 | Optional `--enrich` LLM mode (prose paths only) and `--check` drift mode (diff a project's baseline files against current templates) |

---

## Open questions

1. Node target for generated projects: 24 (current template `.nvmrc`) or 22 (this machine and agentic-tdd CI)?
2. Should the generated `package.json` include `shx`, or drop the agent-copy script until a project needs it?
3. Should the generated repo be scoped (`@nistapp/...`) by default, or unscoped unless `--org` is passed?
4. Generated repo default branch: `dev` as the working branch with `main` production-only (per the recipe), or `main` until the first release?
