# python-agentic-bootstrap

> SPDX-License-Identifier: GFDL-1.3-only

Scaffolder for **greenfield projects that must be agentic-ready from commit #1** — the
executable form of the [greenfield track](../README.md) of this framework.

Run it in an empty directory and get the recommended structure: TypeScript strict harness,
`AGENTS.md` governance, `docs/STYLE_GUIDE.md` documentation contract, GitHub CI/CD, release
automation, and the standardized seven-verb command surface — a publishable npm package
skeleton, ready for the first commit.

**Status: v1 implemented and verified.** [`bootstrap.py`](bootstrap.py) — Python 3, stdlib only,
no dependencies to install — renders [`greenfield/templates/`](../templates/) into a new project.
[`DESIGN.md`](DESIGN.md) is the contract it implements.

Run it from the root of a clone of this repository:

```bash
python3 greenfield/bootstrap/bootstrap.py ~/Projects/my-new-pkg --name my-new-pkg --org nistapp --cli --install
python3 greenfield/bootstrap/bootstrap.py --help   # every flag: --templates --dry-run --no-git --with-infra
```

Always scaffold into a throwaway directory first, never into a real repo: the script
refuses a non-empty target unless `--force`, but the scaffolder's output deserves a look before
it lands anywhere real.

---

## The one rule

> **`greenfield/templates/**` owns every byte of file content. This script owns
> structure, substitution, and verification only.**

The script never carries a second copy of a template file, and never rewrites template
content — if a template is wrong, it is fixed in `greenfield/templates/`, not patched here.
The script reads the templates beside it in the same repository, so the two cannot drift.

---

## Language and distribution

| | Now (v1) | Later (v2) |
|---|---|---|
| Implementation | Python 3, stdlib only, one file | Node / TypeScript, published as an npm package |
| How it runs | `python3 greenfield/bootstrap/bootstrap.py <target>` from a clone | `npx create-agentic-ready <target>` |
| Why | Zero setup, no toolchain, no build step, no lockfile | Distribution to other teams, and ecosystem consistency — every other tool in the framework ships as an npm package |

Both versions consume the **same template contract**, so v2 is a re-wrapper of the same
mapping rules, not a rewrite. `create-agentic-ready` was verified unclaimed on npm.

---

## Non-goals for v1

Deterministic templates only. No LLM calls. No license selection (personal use for now).
No re-targeting to non-TypeScript stacks. No drift/upgrade mode for existing projects.
See [`DESIGN.md`](DESIGN.md) § Roadmap for what moves into v2+.
