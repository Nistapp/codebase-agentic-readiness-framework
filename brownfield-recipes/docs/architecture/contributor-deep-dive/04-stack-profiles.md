# 4. Stack Profiles

> **Audience:** Engineers, contributors
> **Goal:** Explain how stack profiles adapt stack-neutral checks and playbooks to a toolchain. The
> anatomy and contribution steps are in [`stacks/README.md`](../../../stacks/README.md), and this page
> does not repeat them.
> **Status:** Live. `S3.4` is closed: all four files exist —
> [`stacks/README.md`](../../../stacks/README.md),
> [`stacks/typescript-node.md`](../../../stacks/typescript-node.md) (with a NestJS section),
> [`stacks/java.md`](../../../stacks/java.md) (Gradle and Quarkus, with Maven marked untested) and
> [`stacks/python.md`](../../../stacks/python.md).

---

## 1. Detection and confirmation

A profile never re-derives what [`facts.py`](../../../tools/facts.py) already read: `ecosystems`,
`package_managers`, `ci_providers`, `test_frameworks` and `hook_managers` are facts, and a profile's
Detection signals section exists only so a reader can sanity-check the mapping from those facts to the
toolchain's own conventions. The audit recipe states what `facts.json` found, the user confirms or
corrects it, and only then does the agent load a profile if one ships, or derive guidance from the
check files if it does not — telling the user which it is doing either way
([`stacks/README.md`](../../../stacks/README.md) §3). `run_context.stack_profile` records which
happened (`shipped` or `derived`) and the profile id, so "shipped and tested" is never confused with
"the agent's best guess this run" (§4 there).

## 2. Profile anatomy

Every profile follows one fixed, ordered shape — Detection signals, Command-surface map, Tooling
defaults, Execution determinism, CI idiom, Baseline / ratchet, Boundaries, Engine coverage, Pitfalls,
Verified — capped at 150 lines, set out in [`stacks/README.md`](../../../stacks/README.md) §2. Engine
coverage is this roadmap's own addition beyond the design plan's six sections (§2 there): it says which
engine checks are reliable for the stack as it stands and which need independent agent verification, so
a profile is also where an engine gap specific to one toolchain gets written down once a real repository
exposes it, rather than argued afresh on every audit.

## 3. Tested stacks

| Profile | Toolchain | Checked against | Real gaps found |
|---|---|---|---|
| [`typescript-node.md`](../../../stacks/typescript-node.md) | npm, pnpm, Yarn, with a NestJS section | `agentic-tdd`, the Digital-Assistant-SDK, and the microservices repo's two Node components | A gitignored lockfile (`EXEC-02` `FAIL`); a Nest-schematic `lint` script running `eslint --fix` under a read-only verb name (`CMD-04` `FAIL`); a scaffolded `tsconfig.json` with no strict flag (`TOOL-03` `FAIL`) |
| [`java.md`](../../../stacks/java.md) | Gradle, with Quarkus; Maven marked untested | The Digital-Assistant-Server | No formatter/linter/dependency-scanner task registered by name; CI workflows that never run a Gradle verb; an `AGENTS.md` describing a Maven layout the repository does not have |
| [`python.md`](../../../stacks/python.md) | pip, uv, poetry | The engine repo's own pre-migration tree (`source_only`, no manifest at all) | `EXEC-02`'s Python lockfile table omits `pip` entirely, so a plain `requirements.txt` project is told it is missing a `poetry`/`uv`/`pipenv` lockfile |

Each profile's own Verified section is the source of record for dates, tool versions and the repository
used; this table only points at it.
