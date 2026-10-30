# Playbook: `define-command-surface`

> Theme T1 (command surface and quality tools). Follows the anatomy in [`README.md`](README.md). Written in
> IR04.1; applied and corrected on a Gradle repository (IR04.2) and a multi-component Node repository (IR04.3).

## Goal

The repository exposes the seven verbs of [`spec/command-surface.md`](../../../spec/command-surface.md) on one
authoritative runner per component, `check` composes `format:check`, `typecheck` and `test` in that order, any
second runner only delegates, and no read-only verb writes to the working tree.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| CMD-01 | [04-command-surface.md](../../audit/checks/04-command-surface.md#cmd-01--seven-verbs-resolvable-on-one-runner) | Defines every missing verb on the authoritative runner |
| CMD-02 | [04-command-surface.md](../../audit/checks/04-command-surface.md#cmd-02--check-composes-the-read-only-verbs) | Makes `check` compose the three concerns |
| CMD-03 | [04-command-surface.md](../../audit/checks/04-command-surface.md#cmd-03--no-divergent-second-definition) | Turns any second runner into a delegate |
| CMD-04 | [04-command-surface.md](../../audit/checks/04-command-surface.md#cmd-04--write-verbs-separated-from-read-only-verbs) | Splits write forms out of read-only verbs |
| EXEC-03 | [09-execution-determinism.md](../../audit/checks/09-execution-determinism.md#exec-03--non-interactive-setup-path) | Names the non-interactive setup command beside the verbs (short section in Steps) |
| TST-01 | [10-tests.md](../../audit/checks/10-tests.md#tst-01--test-verb-exists-suite-non-empty) | Makes `test` resolve on the runner (short section in Steps) |

The tools behind `format`, `format:check`, `lint`, `typecheck` and `security` are chosen by
[`configure-quality-tools`](configure-quality-tools.md). Run the two playbooks together, in one theme branch:
this one owns the verb names and their wiring, that one owns which tool each verb runs.

## Preconditions

- The state file exists and Stage 1 triage is done ([`SKILL.md`](../SKILL.md#stage-1-triage)). Read it first.
- Preferences this playbook reads, when present: `layout.command_runner` (per component or one root runner),
  `format.mass_reformat` (forbids a whole-tree rewrite), `tests.stack_dependent` (whether `test` needs a live
  local stack), `ci.edits_authorised` (whether build files and CI may be changed). A step that conflicts with
  one stops and asks.
- No earlier theme is needed. T1 runs first because later themes (CI, hooks, baselines, `AGENTS.md`) name
  these verbs.
- A tool choice made by `configure-quality-tools` for each verb, or a recorded decision that the verb is
  `blocked` (see the `security` lockfile rule there).

## Inputs to ask

1. **Detect first.** Read every runner manifest (`package.json` scripts, `Makefile`, `Taskfile.yml`,
   `pyproject.toml` task tables, `build.gradle`/`build.gradle.kts`, `pom.xml`), the instruction file and
   `CONTRIBUTING.md`. List, per component, which of the seven verbs resolve, on which runner, and which
   read-only verb calls a writer. Keep what exists and works; never rename a working verb to a new runner.
2. **Runner shape.** Use the runner the repository already builds with as the authoritative one. Offer:

   | Option | When | Pros | Cons |
   |---|---|---|---|
   | Native runner (recommended) | Always the default | The spelling `spec/command-surface.md` fixes; the engine resolves it; one runner, no new tool | On Gradle and Maven, CMD-02 stays `UNKNOWN` in the engine; the agent verifies it (Verification) |
   | Thin root `Makefile` on top | The owner wants the same `make <verb>` in every repository of an estate | One invocation style everywhere | A second runner: every target MUST delegate, or CMD-01 reads `PARTIAL` and CMD-03 `FAIL`; adds Make to every host |
   | Scripts folder (`scripts/verbs/*.sh`) | Only when no runner exists at all | Matches an existing `scripts/` habit | No row in the spec: the engine cannot resolve it and every spelling needs owner confirmation |

   A wrapper is offered only on top of the native runner, never instead of it.
3. **Multi-component repositories** (several apps, no root manifest). Each component gets the seven verbs on
   its own runner. An optional root dispatcher (a `Makefile` or script) only delegates to each component's
   verb and composes nothing itself. Do not propose a root workspace manifest unless the owner asks: it
   restructures installs and lockfiles. Record the choice as `layout.command_runner` if Stage 1 did not.
4. **`check` with a failing new tool.** `check` composes `format:check`, `typecheck` and `test` only. A tool
   that fails on today's code runs inside `check` in ratchet mode (changed files only), so `check` is green on
   the integration branch; the full-repository run is a report-only CI step. Including a strict, failing check
   in `check` is allowed only if the owner chooses it; record that as a preference.
5. **Stack-dependent tests.** When `test` needs a live local stack (`tests.stack_dependent`), keep it in
   `check` and say so in the instruction file. Do not drop `test` from `check` and do not add `-x test`, unless
   the owner chooses it and it is recorded.
6. **Infra-only components** (compose files, proxy config) with no build tool: ask whether `check` should run
   an existing validation script for them, or leave them outside the verbs.

## Steps

1. Work in a worktree from the up-to-date integration branch, on the theme branch
   (`agentic-readiness/<phase>-command-surface`). Set each T1 item `in_progress` before touching it.
2. **Name every verb** on the authoritative runner, spelled as the runner row in
   [`spec/command-surface.md`](../../../spec/command-surface.md#spelling-per-runner) says. The command each verb
   runs comes from `configure-quality-tools`.
3. **Compose `check`**: `format:check`, then `typecheck`, then `test`, by calling the verbs by name (indirection)
   rather than repeating their commands. `lint` and `security` stay standalone verbs, not part of `check`.
4. **Split writers out of read-only verbs** (CMD-04). A read-only verb that carries `--fix`, `--write` or calls
   `format` becomes two verbs: the read-only one keeps the name (`lint` without `--fix`) and the writer gets a
   separate name (`lint:fix`, or folded into `format`). Never leave the writer under the read-only name.
5. **Delegate any second runner** (CMD-03). A root `Makefile`, `Taskfile` or dispatcher script calls the
   authoritative runner's verb (`npm run check`, `./gradlew check`, `make -C <component> check`) and composes
   nothing of its own.
6. **TST-01: the `test` verb.** `test` runs the whole suite through the runner (`npm test`, `./gradlew test`).
   A component with test files but no `test` verb gets one; a component with no tests at all keeps a `test`
   verb that runs the runner's default (and fails or passes as the tool does), and the empty suite is recorded
   for T5, not invented here.
7. **EXEC-03: the setup command.** Next to the verbs, the instruction file names the one non-interactive setup
   command per component (`npm ci`; `./gradlew assemble`, which fetches Gradle and the dependencies through the
   wrapper). Do not add a new setup script in T1;
   pinning versions is `pin-execution-environment` (T2).
8. **Write the verbs down.** The instruction file (`AGENTS.md`, else `CONTRIBUTING.md`) lists the exact command
   for each verb per component (`spec/command-surface.md` rule 4). Fill an existing placeholder; do not
   rewrite the file, which is T7's job.
9. Commit per logical change (verbs, then the split writer, then the doc lines), each revertible alone.

### Gradle

Profile: [`stacks/java.md`](../../stacks/java.md#command-surface-map).

- Register `format`, `formatCheck`, `lint`, `typecheck` and `security` as aggregate tasks in `build.gradle`
  (`tasks.register('lint') { dependsOn ... }`), each depending on the tool's own task. `formatCheck` is the
  only accepted Gradle spelling of `format:check`; do not register `format-check`.
- `test` and `check` are Gradle's lifecycle tasks. Wire `check` with `check.dependsOn formatCheck, typecheck`;
  `test` is already a dependency. Gradle orders them by the task graph, not by the list: add
  `mustRunAfter` (`typecheck` after `formatCheck`, `test` after `typecheck`) so the spec's order holds.
- Applying a quality plugin (Spotless, PMD, Checkstyle, SpotBugs) adds its own tasks to lifecycle `check`
  automatically. Read `./gradlew check --dry-run` after each plugin and make sure every task it adds is in
  ratchet or baseline mode (`configure-quality-tools`), or `check` turns red on today's code.
- `typecheck` = `compileJava compileTestJava` (javac is the type checker). `-Xlint:all -Werror` is a later,
  owner-chosen hardening, not T1.
- Invoke only through the wrapper (`./gradlew <task>`), never a system `gradle`.

### Node (npm, pnpm, yarn)

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#command-surface-map).

- Verbs are `package.json` scripts with their own names, `format:check` included.
- `check` = `npm run format:check && npm run typecheck && npm test`. The greenfield
  [`package.json` template](../../../greenfield-bootstrap/templates/package.json) shows the full set; use it as a
  reference, never copy it.
- A NestJS scaffold's `lint` carries `--fix`: make `lint` read-only and add `lint:fix` for the writer
  ([NestJS section](../../stacks/typescript-node.md#nestjs)).
- A Create React App component ships only `start`, `build`, `test`, `eject`. Add the missing verbs as scripts;
  `react-scripts test` is interactive by default, so `test` sets `CI=true` (or `--watchAll=false`) to run once.
- `typecheck` = `tsc --noEmit -p tsconfig.json` (and a second `-p` for a separate test config when one exists).
  Check whether the component is TypeScript or JavaScript before offering a type check at all.

## Continue on error

This playbook installs names and wiring, so its own debt is rare. What counts:

- A verb that resolves but fails on today's code because its tool has debt: the debt belongs to the
  `configure-quality-tools` item (TOOL-01..04) and is recorded there; the CMD item is `done` when the verb
  resolves and `check` is green in ratchet mode.
- A verb that cannot be defined yet because its tool needs another theme (for example `security` waiting for a
  lockfile from T2): set the CMD-01 item `partial` with the missing verb named in the debt, and the TOOL item
  `blocked`. Never add a placeholder verb that prints "skipped" and exits 0.
- A `test` verb that needs a live stack: not debt; record it in the item's notes and in the instruction file.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| CMD-01 | Run each verb once (`npm run <verb>`, `./gradlew <task>`, per component); read the runner manifest | All seven resolve on one runner per component; each exits as its tool says, not "command not found" |
| CMD-02 | npm: read the `check` script. Gradle: `./gradlew check --dry-run` | npm: the three verbs by name, in order. Gradle: the task list holds the format-check, compile and `test` tasks; the engine's `UNKNOWN` here is its documented limit, not a gap |
| CMD-03 | Read every second runner's `check` target | Each calls the authoritative runner's `check` and nothing else |
| CMD-04 | `git status --porcelain` before and after running every read-only verb | Empty both times: no read-only verb wrote a file |
| EXEC-03 | Read the instruction file | One non-interactive setup command per component |
| TST-01 | Run `test` | The runner executes the suite (stack-dependent suites: with the stack up, as recorded) |

On a multi-component repository the engine may still read CMD-01 at the root as `PARTIAL` or `FAIL`, because
it does not resolve verbs inside components. Record that in the item's notes as an engine limit, with the
per-component evidence above, not as a remaining gap.

## Rollback

Each step is its own commit: revert the doc-line commit, the writer-split commit and the verb commit, in that
order. The verbs add no dependency by themselves; tool dependencies roll back with `configure-quality-tools`.

## Do-not-do

- Do not create a second runner that composes its own `check`.
- Do not make `check` pass by dropping `test` or `typecheck`, or by `-x test`, unless the owner chose it.
- Do not add a verb that does nothing (`echo skipped`), and do not leave `--fix` or `--write` under a
  read-only verb name.
- Do not restructure a multi-component repository into one workspace.
- Do not rewrite the instruction file; add the command lines only.

## State updates

Through [`progress.py`](../../docs/reference/tools-cli.md#progresspy), on the theme branch, `--phase` the
current step:

```bash
python3 brownfield-recipes/tools/progress.py set-status F-nnn in_progress --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "./gradlew check --dry-run" --verification-result "<what it showed>"
python3 brownfield-recipes/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --debt "what=security verb waits for T2 lockfile,count=1" --note "<which verb, why>"
python3 brownfield-recipes/tools/progress.py theme T1 --status branch_open \
  --branch agentic-readiness/<phase>-command-surface --target <repo> --phase <phase> --render
```

A `blocked` status is reached through `in_progress` (`queued` to `blocked` is not a valid transition) and
needs `--reason`. Record any new owner choice (runner shape, a failing check allowed in `check`) with
`progress.py pref set <key> <value> --by owner`.
