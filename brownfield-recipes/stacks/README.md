# Stack profiles

> **Audience:** Agents running the audit or implementation recipes, and contributors adding or updating a
> profile.
> **Scope:** Governs every `<id>.md` file in this folder. One file per toolchain; a framework that shares a
> toolchain (NestJS on Node, Quarkus on Gradle) gets a section inside that file, not a file of its own.

---

## 1. What a profile is

A stack profile maps the pack's stack-neutral checks and playbooks onto one toolchain's real commands and
tools: which file names detect it, how each of the seven verbs (`format`, `format:check`, `lint`,
`typecheck`, `test`, `check`, `security`) is usually realised, which formatter/linter/type-checker/test
runner/dependency scanner are the stack's defaults, and so on. Checks and playbooks never hard-code a
toolchain; a profile is where that knowledge lives, so the same check file reads correctly for Node, Java or
Python.

## 2. Anatomy

Every profile follows this fixed shape, in this order:

```
Detection signals      files and dependencies that identify the stack and its framework (what
                       facts.json's ecosystems, package_managers, ci_providers, test_frameworks and
                       hook_managers already found; the profile does not re-derive what the facts tool
                       already read)
Command-surface map    how each verb is usually realised, and the runner (npm scripts / Makefile /
                       Taskfile / Gradle / Maven)
Tooling defaults       recommended formatter, linter, type checker, test runner, coverage tool,
                       dependency scanner, with "alternatives you may find" so an existing choice is
                       respected, never replaced without being asked
Execution determinism  version pinning and lockfile expectations for this stack
CI idiom               how to run the verbs in the common CI providers for this stack
Baseline / ratchet     how to adopt "no new violations" for this stack
Boundaries             how component boundaries are expressed, and how to enforce them
Engine coverage        which engine checks are reliable for this stack as they stand, and which need
                       independent agent verification for it (DP §5.6 names six sections; this one is
                       the roadmap's addition, S3.4)
Pitfalls               stack-specific false positives and false negatives
Verified               date, tool versions the profile was last checked against, and the repository
                       (or repositories) used
```

A profile is documentation (`GFDL-1.3-only`, see
[`docs/reference/licensing.md`](../docs/reference/licensing.md)), capped at 150 lines so an agent can hold
the whole thing in mind at once. A profile that would outgrow the budget splits a crowded section (for
example, a framework) into its own `###`-level block rather than a new file, following §1 above.

## 3. Detected, not guessed

The audit and implementation recipes run `tools/facts.py` before loading a profile (DP §5.6's Stage 0/1
flow): the agent states what `facts.json` found, the user confirms or corrects it, and only then does the
agent load `stacks/<id>.md` if one ships, or derive equivalent guidance from the check files and the
greenfield TS/Node reference if it does not — telling the user which it is doing either way. A profile's
Detection signals section exists so a reader can sanity-check that mapping, not so an agent re-scans the
repository by hand.

## 4. Shipped versus derived

A toolchain with no profile here is not unsupported: the agent derives guidance from the check files'
stack-neutral rubrics and says so. `run_context.stack_profile` records which happened (`shipped` or
`derived`) and the profile id, and eval results and generated reports carry the same label, so "shipped and
tested" is never confused with "the agent's best guess this run."

## 5. Contributing a profile

1. Copy this file's anatomy (§2) section by section; do not invent a different shape.
2. Fill each section from the stack's own conventions, preferring what a repository already uses over a
   personal preference — a profile recommends, it does not mandate a specific tool where the stack supports
   several.
3. Write the Engine coverage section last, once the rest is settled: name each check family the engine
   backs for this stack, and say which of those verdicts this stack's own conventions can make unreliable
   (a build tool the engine does not resolve, a convention the engine's detection misses).
4. Test the profile against at least one real repository in the stack: run the audit, and record what it
   showed.
5. Record the test under Verified: the date, the tool versions in play, and the repository used. A section
   checked against no repository says so, plainly, rather than omitting the caveat.
6. Keep the file at 150 lines or fewer, and confirm `python3 brownfield-recipes/tools/recipe_lint.py` is
   clean before proposing the profile (it checks links, not the line budget, for this folder — the budget
   here is this file's own rule).

## 6. One profile, one file

Each file is this folder's single source for its stack: nothing about a toolchain's command surface or
tooling defaults is duplicated into a check file or a playbook, which stay stack-neutral and link here
instead.
