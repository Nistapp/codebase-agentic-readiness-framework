# python-agentic-bootstrap

Scaffolder for **greenfield projects that must be agentic-ready from commit #1** — the
executable form of the [Codebase Agentic Readiness Framework](https://github.com/Nistapp/codebase-agentic-readiness-framework)
greenfield track.

Run it in an empty directory and get the recommended structure: TypeScript strict harness,
`AGENTS.md` governance, `docs/STYLE_GUIDE.md` documentation contract, GitHub CI/CD, release
automation, and the standardized six-verb command surface — a publishable npm package
skeleton, ready for the first commit.

**Status: design phase.** No implementation code yet. [`DESIGN.md`](DESIGN.md) is the
reviewed contract the implementation will follow.

---

## The one rule

> **`templates/**` in the framework repo owns every byte of file content. This script owns
> structure, substitution, and verification only.**

The script never carries a second copy of a template file, and never rewrites template
content — if a template is wrong, it is fixed in the framework repo, not patched here.
That single rule is why the script can stay ~200 lines and why the two repos cannot drift.

---

## Language and distribution

| | Now (v1) | Later (v2) |
|---|---|---|
| Implementation | Python 3, stdlib only, one file | Node / TypeScript, published as an npm package |
| How it runs | `python3 bootstrap.py <target>` from a clone | `npx create-agentic-ready <target>` |
| Why | Zero setup, no toolchain, no build step, no lockfile in a docs-only repo | Distribution to other teams, and ecosystem consistency — every other tool in the framework ships as an npm package |

Both versions consume the **same template contract**, so v2 is a re-wrapper of the same
mapping rules, not a rewrite. `create-agentic-ready` was verified unclaimed on npm.

---

## Non-goals for v1

Deterministic templates only. No LLM calls. No license selection (personal use for now).
No re-targeting to non-TypeScript stacks. No drift/upgrade mode for existing projects.
See [`DESIGN.md`](DESIGN.md) § Roadmap for what moves into v2+.
