# Playbook: `pin-execution-environment`

> Theme T2 (execution determinism). Follows the anatomy in [`README.md`](README.md). Written in IR05.1;
> applied and corrected on a Gradle repository (IR05.2) and a multi-component Node repository (IR05.3).

## Goal

Every run of the repository gets the same toolchain and the same dependency versions: each ecosystem has a
committed pin (JDK, Node, package manager), each component has a tracked lockfile that matches its manifest, and
the pins in CI, Dockerfiles and version files agree with each other.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| EXEC-01 | [09-execution-determinism.md](../../audit/checks/09-execution-determinism.md#exec-01--toolchain-pinned--wrapper-committed) | Commits a pin for every detected ecosystem and makes every other place that names a version agree with it |
| EXEC-02 | [09-execution-determinism.md](../../audit/checks/09-execution-determinism.md#exec-02--lockfile-committed-and-consistent) | Commits a lockfile that resolves exactly what the manifest resolves today |
| EXEC-03 | [09-execution-determinism.md](../../audit/checks/09-execution-determinism.md#exec-03--non-interactive-setup-path) | Check only (step 9): [`define-command-surface`](define-command-surface.md) owns the fix |

## Preconditions

- The state file exists and Stage 1 triage is done ([`SKILL.md`](../SKILL.md#stage-1-triage)). Read it first.
- Preferences this playbook reads, when present: `layout.command_runner` (per component or one root runner; a
  per-component preference forbids a root workspace manifest), `ci.edits_authorised` (whether workflow files may
  be changed), `format.mass_reformat`, `extra.*` entries that name a pin the owner already chose (for example a
  JDK toolchain block). A step that conflicts with one stops and asks.
- No earlier theme is needed. Run it before any scanner step that reads a lockfile
  ([`configure-quality-tools`](configure-quality-tools.md) blocks `security` until the lockfile exists), and
  before the CI theme, which copies these pins into workflows.
- The integration branch builds today. Take a baseline first (step 1): a lockfile is only safe if it changes no
  resolved version.

## Inputs to ask

1. **Detect first.** List, per ecosystem and per component: the toolchain pin that exists (`gradle-wrapper.properties`,
   `java { toolchain }`, `.nvmrc`, `.node-version`, `.tool-versions`, `engines`, `packageManager`,
   `.python-version`), the lockfile that exists and whether `git ls-files` tracks it, and **every other place that
   names a version**: CI workflows (`java-version`, `node-version`), every `Dockerfile*` `FROM`, compose images,
   `README` and `AGENTS.md` prerequisites. Version drift between those places is a finding of its own; copy the
   values from the files, never from the finding text, which may be stale.
2. **The version itself is the owner's call.** The playbook never assumes a runtime major. Offer the supported
   releases from the project's own schedule (Node: <https://nodejs.org/en/about/previous-releases>; JDK: the
   vendor's support table), say which one CI, the Dockerfiles and the dependencies already use, name the one that
   is in active or maintenance LTS, and say what has to be checked before moving (does the framework and its
   build tool run on that major, does `npm ci` or `./gradlew build` still succeed). When the repository already
   agrees on one version in most places, recommend that one and make the outliers follow it. Record the answer
   as a preference.
3. **Mechanism (Node).** Detect an existing version manager or pin file and keep it. If none exists, offer:

   | Option | Pros | Cons |
   |---|---|---|
   | `.nvmrc` + `engines.node` + `packageManager` per component (recommended) | Read by the engine (`.nvmrc`, `engines.node`); works with nvm, fnm and `actions/setup-node` `node-version-file`; no extra tool in the repository | Three places per component to keep aligned (the file, `engines`, the Dockerfile `FROM`); step 6 adds the cross-check |
   | `.tool-versions` with mise or asdf | One file for Node and other runtimes; the engine reads it | A tool every contributor and CI image must install; an extra concept for a small repository |
   | Volta (`volta` block in `package.json`) | Pins Node and the package manager per project | **Dropped:** the project's own README states it is unmaintained (last release v2.0.2, 2024-12-05); the engine's pin table does not list it |

   Tool currency checked 2026-10-30 (GitHub releases API, Node's `dist/index.json`): nvm v0.40.8 (2026-09-21),
   fnm v1.39.0 (2026-03-06), mise v2026.10.24 (2026-10-30), asdf v0.20.2 (2026-09-22), `actions/setup-node`
   v7.1.0 (2026-10-08). Node release lines then: 22 "Jod" (v22.23.4, 2026-10-20), 24 "Krypton" (v24.22.2,
   2026-10-27), 26 "Lithium" (v26.13.0, 2026-10-28); 25 and 23 are non-LTS. Re-check the table when the playbook
   is applied: it dates.
4. **Mechanism (Gradle).** The wrapper is the Gradle pin; keep it. For the JDK offer:

   | Option | Pros | Cons |
   |---|---|---|
   | `java { toolchain { languageVersion = JavaLanguageVersion.of(N) } }` (recommended) | Built in; the build no longer depends on `JAVA_HOME`; CI and local runs use the same JDK | Gradle fails if no matching JDK is installed, unless a resolver plugin is added |
   | Toolchain block + `org.gradle.toolchains.foojay-resolver-convention` (1.0.0, 2025-05-19) in `settings.gradle` | Downloads the missing JDK automatically | Network fetch of a JDK during a build; one more plugin in `settings.gradle`; owner approves it first |
   | `.sdkmanrc` or `.tool-versions` only | Cheap hint for developers | Not read by Gradle or the engine; does not pin CI |

5. **Lock width (Gradle).** Recommend `dependencyLocking { lockAllConfigurations() }` and one `gradle.lockfile`:
   built into Gradle, read by Dependabot and by OSV-Scanner. Locking only `runtimeClasspath` and
   `compileClasspath` gives a smaller file but leaves test and plugin classpaths free to drift, so EXEC-02 reads
   only partly met. A version catalog alone is not a lock. Record the choice as a preference.
6. **Monorepo or several components with no root manifest.** Per-component lockfiles are accepted when the owner
   chose a per-component layout (`layout.command_runner`). The playbook then verifies each component and records
   the item `partial` with the reason; it does not add a root workspace manifest unless the owner asks, because
   that changes install paths and image builds. The engine reads only the root manifest, so a nested lockfile
   reads `PARTIAL` by design ([check pitfall](../../audit/checks/09-execution-determinism.md#exec-02--lockfile-committed-and-consistent)).

## Steps

1. **Baseline.** Work in a worktree from the up-to-date integration branch on the theme branch
   (`agentic-readiness/<phase>-determinism`). Set each T2 item `in_progress`. Record what resolves today: the
   dependency report (`./gradlew dependencies --configuration <c>`, `npm ls --all`) per component, saved outside
   the repository. Nothing below may change it.
2. **Pin the toolchain** with the mechanism chosen in Inputs, once per ecosystem and per component. Use the
   exact version the owner chose, not a range, in the version file.
3. **Pin the package manager** where the ecosystem has a field for it (`packageManager` in `package.json`;
   the Gradle wrapper for Gradle). Keep the version you already use.
4. **Lock the dependencies.** Generate the lockfile with the tool's own command, from the pinned toolchain, and
   commit it with the manifest. Never hand-edit a lockfile.
5. **Compare.** Re-run the step 1 reports. The resolved versions must be identical. A difference is a defect in
   this change (a wrong toolchain, a floating version, a forced version the lock did not honour): fix the cause
   before committing, never record it as debt.
6. **Cross-check every other place that names a version** (found in Inputs step 1): CI workflows, `Dockerfile*`
   `FROM` lines, compose images, documented prerequisites. Make each agree with the pin, or read it from the pin
   (`node-version-file: .nvmrc`, `java-version-file`). Edit workflow files only when `ci.edits_authorised` allows;
   otherwise list the mismatches as debt and stop short of the edit. The CI theme repeats this check.
7. **Keep claims true.** A comment or document that says "versions are locked" must be true after this change or
   be corrected: `dependabot.yml` headers and `AGENTS.md` lines are typical. A claim that is stale for a reason
   other than this playbook (an `AGENTS.md` description of lockfiles, say) is recorded and left to the
   `AGENTS.md` theme.
8. **Tell the scanner theme.** If a scanner reads the lockfile (OSV-Scanner reads `gradle.lockfile` and
   `package-lock.json`), note in the item that the lockfile now exists, so `configure-quality-tools` can unblock
   its `security` verb.
9. **EXEC-03 (check only).** Read the instruction file and the runner for one non-interactive setup command per
   component. If [`define-command-surface`](define-command-surface.md) has not added it, add it there; this
   playbook adds no setup script. Record the engine's limit when the documented command is a project script it
   does not recognise.
10. Commit per logical change (toolchain pin, lockfile, version alignment, doc claim), each revertible alone.

### Gradle

Profile: [`stacks/java.md`](../../stacks/java.md#execution-determinism).

- Add the toolchain block to `build.gradle` first, then the locking block, then generate the lock. The order
  matters: a lock written under the wrong JDK records the wrong resolution.
- `dependencyLocking { lockAllConfigurations() }`, then `./gradlew dependencies --write-locks` writes one
  `gradle.lockfile` at the project root. Commit it.
- A build with `resolutionStrategy { force ... }` or an `enforcedPlatform` BOM is the case to watch: the lock
  records what resolves *after* those rules, so the before and after reports must match exactly. A mismatch means
  a rule moved.
- Every dependency bump from now on regenerates the lockfile (`--write-locks`, or `--update-locks <group:name>`).
  Say so in the instruction file next to the build verbs.
- The engine cannot see `dependencyLocking`, so EXEC-02 reads `UNKNOWN` for an unlocked Gradle build and may not
  read the locked one as `PASS` either. Verify by reading `build.gradle` and `gradle.lockfile` directly and
  record the engine's limit in the item.
- Invoke only through the wrapper (`./gradlew`).

### Node (npm, pnpm, yarn)

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#execution-determinism).

- Per component: the version file (`.nvmrc` holding the exact version), `engines.node` with the matching major
  range, and `packageManager` (`npm@x.y.z`). `.nvmrc` is the stronger pin; `engines` is what the engine and
  `npm` itself read.
- Keep the existing lockfile if it is tracked and `npm ci` passes. Regenerate it only when `npm ci` fails on
  the pinned Node; if that happens, the manifest and lockfile disagree and the owner decides how to repair it.
- Setup is `npm ci` (never a bare `npm install`). Run it in every component on the pinned major and run the
  component's build once.
- Create React App components ship `react-scripts` 5, whose build chain predates recent Node majors: build on
  the chosen major before committing the pin, and surface a failure to the owner rather than lowering the pin
  silently.
- CI uses `actions/setup-node` with `node-version-file` pointing at the component's `.nvmrc`
  (`cache-dependency-path` for the component's lockfile).
- Docker images build only through the repository's own scripts, never by hand. Align the Dockerfile `FROM`
  and any dev Dockerfile with the pin.

## Continue on error

- A lockfile that changes a resolved version is not debt: fix the cause before committing.
- A mismatch in a file the owner has not authorised editing (CI, a Dockerfile in another team's folder) is
  debt: count the mismatched places, record them with `--debt`, mark the item `partial`, and list each place
  in the note. There is nothing to ratchet; the CI theme closes it.
- Per-component lockfiles with no root manifest, by the owner's layout choice: `partial` with the reason
  "lockfiles per component by owner choice; engine reads the root only". Not a defect.
- A component whose build fails on the pinned major: record `blocked` with the error and the owner's options
  (a different major, an upgrade of the failing dependency). Never pin a version the build cannot use.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| EXEC-01 | Read the pin file per ecosystem; `grep` the version in every workflow and `Dockerfile*` | One pin per ecosystem and component; every other place names the same version |
| EXEC-02 | Gradle: `./gradlew dependencies` compared to the step 1 report, read `gradle.lockfile`. Node: `npm ci` per component, then `git status --porcelain` | Gradle: identical resolved versions, lockfile tracked. Node: `npm ci` succeeds and leaves the tree clean |
| EXEC-03 | Read the instruction file | One non-interactive setup command per component (owned by `define-command-surface`) |

Also run the repository's own gate (`./gradlew build`, `npm run build` per component) once on the pinned
toolchain, and read the CI run on the branch: it must be green. The engine's re-audit can still read EXEC-02 as
`UNKNOWN` (Gradle) or `PARTIAL` (nested lockfile): record that as an engine limit with the evidence above.

## Rollback

Each step is its own commit. Revert the alignment, version-pin and doc commits. For Gradle also delete
`gradle.lockfile` and the `dependencyLocking` block; the toolchain block is removed by its own revert. For Node
delete the version file and the `engines` and `packageManager` fields. No dependency version changed, so no
runtime change needs undoing.

## Do-not-do

- Do not choose a runtime major for the owner, and do not move a major in this theme without the owner's
  decision and a green build on it.
- Do not hand-edit a lockfile or regenerate one that already passes.
- Do not run `npm install`, `npm update` or `./gradlew dependencies --update-locks` to "refresh" while
  locking: the point is to record what resolves today.
- Do not add a root workspace manifest to a per-component repository unless the owner asks.
- Do not edit workflow files without `ci.edits_authorised`.
- Do not build images or start containers by hand: use the repository's scripts.
- Do not install a version manager the owner did not approve.

## State updates

Through [`progress.py`](../../docs/reference/tools-cli.md#progresspy), on the theme branch, `--phase` the
current step:

```bash
python3 brownfield-recipes/tools/progress.py set-status F-nnn in_progress --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "./gradlew dependencies (before and after)" \
  --verification-result "<resolved versions identical; gradle.lockfile tracked>"
python3 brownfield-recipes/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --debt "what=version mismatch in CI,count=2" --note "<places, why not edited>"
python3 brownfield-recipes/tools/progress.py pref set tools.node_major <value> --reason "<owner's words>" \
  --by owner --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py theme T2 --status branch_open \
  --branch agentic-readiness/<phase>-determinism --target <repo> --phase <phase> --render
```

A `blocked` status is reached through `in_progress` and needs `--reason`. Record each owner choice as a
preference: runtime major, pin mechanism, Gradle lock width, accepted per-component lockfiles.
