# AGENTS.md

> **Template Version:** 2.0.0
> **Purpose:** This file tells AI coding agents how to work in this repository. It holds only what an agent cannot
> infer from the code: the commands, the boundaries, the rules for documents and releases, and the prohibitions.
> **How to use it:** Replace every `<placeholder>` with a fact you checked in this repository. Delete a line you
> cannot make true. Do not add an overview, a tech-stack table or coding rules a linter already enforces. Delete
> this block when you are done. Keep the file under 400 lines.

This file is read by `<the harnesses that really load it, for example Claude Code (through the CLAUDE.md
import), opencode, Codex and Cursor>`.

---

## 1. Commands

These seven verbs are the only sanctioned way to verify work. CI runs the same script names. Do not invent
ad-hoc invocations (`npx vitest`, `tsc file.ts`) and do not run a check that CI does not run.

```bash
npm run format        # format: rewrite formatting in place
npm run format:check  # format:check: read-only, formatting and lint rules
npm run lint          # lint: read-only
npm run typecheck     # typecheck: tsc --noEmit for src/ and test/
npm test              # test: the full suite
npm run check         # check: THE gate (format:check, typecheck, test)
npm run security      # security: dependency-CVE gate
```

Run one test, not the suite:

```bash
npx vitest run test/<path>/<file>.test.ts -t '<test name>'
```

`<Runtime and version, for example Node.js 24 with ESM; any precondition a command needs.>`
<A rule the tools do not enforce, for example: local imports end in .js (NodeNext).>

Run `npm run check` before every commit and pull request. If you cannot make it pass, report the blocker.

`<If the repository has a code index, query it before you read whole files.>`

---

## 2. Boundaries

Each rule names a path that exists.

- `<src/core/>` holds pure logic. It never imports from `<src/infrastructure/>` or `<src/cli/>`.
- `<src/infrastructure/>` holds every filesystem, git and OS operation. It implements interfaces from `<src/core/interfaces.ts>`.
- `<src/cli/>` is the composition root. It reads `process.env` and wires the dependencies.
- `<dist/>` is generated. Regenerate it with `npm run build`.
- `<Naming rules a linter does not enforce, for example: files are kebab-case.ts; interfaces start with I.
  Delete the line if there are none.>`

---

## 3. Documentation

- `docs/` is the single source of truth for permanent documentation. `docs/README.md` indexes it.
- Every `.md` file under `docs/` follows `docs/STYLE_GUIDE.md`. Link to its rules; never restate them here.
- Decisions are ADRs in `docs/architecture/adrs/`. Every ADR you add, change or delete follows `docs/ADR_POLICY.md`.
- `artefacts/` is scratch: plans, notes, work in progress. Its contents are git-ignored. It is never a source of
  truth, and you read it only when a human gives you a file path.
- **Definition of done:** when a change alters a public interface, observable behaviour, the architecture or a
  decision, update the affected documentation and the decision records in the same change set.

---

## 4. Branches and releases

Branch from `<dev>` and open pull requests into `<dev>`; `<main>` receives releases only. An agent may push its
branch and open a pull request; it never merges, tags, publishes a release or pushes to `<main>` or `<dev>`.
`<Releases are cut by the release tool the repository tracks, if any.>`

Commits follow Conventional Commits: `<type>(<scope>): <description>`. `<The hook that enforces it.>`

---

## 5. How to write for people

These rules apply to chat replies, plans, reports, commit messages, pull request descriptions and docs.

- **Reader:** write for `<a new engineer who knows TypeScript and Node, but not this repository or its terms>`.
- **Bottom line first:** put the answer, the result or the decision you need in the first two lines.
- **Plain language:** short sentences (at most 25 words), active voice, one term per meaning.
- **Reports:** a status report says what is done, not done, blocked and next. A done report says what changed, how
  it was checked and what was not done.
- **Decisions:** give the context, two to four options with pros and cons, your recommendation and the default.

---

## 6. Never

- Never open, print, log or commit `.env` or any other secret store. Secrets go in `.env`; the template goes in
  `.env.example`.
- Never edit `<.github/workflows/>` or `<dist/>` by hand.
- Never skip, delete or weaken a test or a lint rule to get a gate green.
- Never ship a public method without a positive and a negative test. Never let a unit test touch the real
  filesystem, git or network; inject a stub.
- Never verify work with an ad-hoc command. Use the seven verbs in section 1.
- Never add a runtime dependency without an ADR that records the decision.
- Never commit to `<main>` or `<dev>`, and never merge, tag or publish a release.
- Never describe a planned feature as if it exists.
