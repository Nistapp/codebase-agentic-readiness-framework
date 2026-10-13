# How to Add a Stack Profile

> **Goal:** Contribute a tested profile for a toolchain the recipes do not yet cover.
> **Audience:** Operators / Engineers
> **Status:** Live. Four profiles exist: [`README.md`](../../stacks/README.md),
> [`typescript-node.md`](../../stacks/typescript-node.md), [`java.md`](../../stacks/java.md) and
> [`python.md`](../../stacks/python.md) — read one of them alongside this page as a worked example.

---

## Prerequisites

- [ ] An open-source repository in the target stack, to test the profile against
- [ ] A read of [`stacks/README.md`](../../stacks/README.md) in full — it is short, and this page does
      not repeat its anatomy or its contribution rules, only walks through applying them

---

## Step-by-Step Instructions

### Step 1: Copy the profile anatomy

Start a new `stacks/<id>.md` from [`stacks/README.md`](../../stacks/README.md) §2's ten section
headings, in that order: Detection signals, Command-surface map, Tooling defaults, Execution
determinism, CI idiom, Baseline / ratchet, Boundaries, Engine coverage, Pitfalls, Verified. A framework
that shares a toolchain with an existing profile (Spring Boot on Maven, Django on pip) gets a `###`
section inside that file, not a new one — see `typescript-node.md`'s `## NestJS` or `java.md`'s Quarkus
coverage for the pattern.

### Step 2: Fill each section from the stack's own conventions

Prefer what a repository already uses over a personal preference: a profile recommends a default, it
does not mandate one where the stack supports several (state the alternatives you considered). State
plainly where the facts tool's own signal is empty or misleading for this stack (`typescript-node.md`'s
note on a multi-component repository with no root lockfile is the model for that). Write **Engine
coverage** last, once the rest is settled: read the engine's own source for the checks that back this
stack (`audit/rules/checks/_common.py` and the family files under
[`deterministic-audit/audit/rules/checks/`](../../deterministic-audit/audit/rules/checks/)), and say
which verdicts are reliable as the engine reads them and which need an agent's own read of the build
file — `java.md`'s Gradle/Maven engine-coverage sections and `python.md`'s `source_only` discussion are
worked examples of a real gap found this way, not invented.

### Step 3: Test on a real repository

Run the audit (or read the target directly if a full recipe run is not available yet) against at least
one real repository in the stack. Record what it showed — a real `FAIL`, not a false positive, is better
evidence for Pitfalls than a hypothetical one. A toolchain with no repository available at all (Maven's
own section in `java.md`) is still written, grounded in the engine's source, and says plainly that it is
untested rather than silently passing off a guess as a checked claim.

### Step 4: Record the test under Verified

Date, the tool versions in play, and the repository (or repositories) used, with a commit SHA if the
checkout can drift. A section checked against no repository says so there too, not just in its own body.

---

## Verification

- [ ] `python3 brownfield-recipes/tools/recipe_lint.py .` is clean.
- [ ] The file is 150 lines or fewer (the recipe linter does not check this for `stacks/`; it is the
      folder's own rule, per [`stacks/README.md`](../../stacks/README.md) §2).
- [ ] `make check` still passes.
