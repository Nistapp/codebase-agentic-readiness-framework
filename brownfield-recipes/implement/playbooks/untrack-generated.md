# Playbook: `untrack-generated`

> Theme T2 (execution determinism). Follows the anatomy in [`README.md`](README.md). Written in IR05.1;
> applied and corrected on a Gradle repository (IR05.2) and a multi-component Node repository (IR05.3).

## Goal

No build output is tracked in the repository, or the output that has to stay tracked says so in its first
lines, and every concern (lint, format, test, types, security) has one authoritative root config.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| EXEC-05 | [09-execution-determinism.md](../../audit/checks/09-execution-determinism.md#exec-05--no-generated-artifacts-committed-in-tree) | Finds tracked build output, proves nothing reads the tracked copy, and untracks it with the owner's yes (or adds a header where one fits) |
| EXEC-07 | [09-execution-determinism.md](../../audit/checks/09-execution-determinism.md#exec-07--no-competing-configs-for-one-concern) | Detection and documentation only (step 8): lists competing root configs, asks which is authoritative, documents deliberate delegation |

## Preconditions

- The state file exists and Stage 1 triage is done ([`SKILL.md`](../SKILL.md#stage-1-triage)). Read it first.
- Preferences this playbook reads, when present: `layout.command_runner`, `ci.edits_authorised`,
  `tests.stack_dependent` (a stack the build scripts start), and any `extra.*` entry that already decides a
  tracked-but-ignored path (for example a secret-bearing file assigned to the secrets theme). A step that
  conflicts with one stops and asks.
- No earlier theme is needed. If the repository has a script that regenerates the output (a build verb, a
  stack start-up script), read it first: it is the evidence that untracking is safe.
- Docker and the local stack start only through the repository's scripts (workspace rule). This playbook never
  starts a container to test a reader; it reads files.

## Inputs to ask

1. **Detect first** with the signal below, then the engine's own list (the EXEC-05 finding names up to 12 paths):

   ```bash
   git ls-files -ci --exclude-standard
   ```

   This prints files that are tracked **and** match an ignore rule: the repository itself says they should not
   be tracked. Review the list by hand. It is a signal, not a verdict:

   | Path kind | What it is | Where it goes |
   |---|---|---|
   | Build output (`dist/`, `build/`, `target/`, minified bundles, source maps) | The target of this playbook | Steps 2-6 |
   | Secret-bearing file (keystore, key, `.env` with values, credentials) | **Not generated output** | Never untrack here; hand it to the secrets playbook (`env-inventory-and-secrets`, T3), which decides rotation and history. Record it in the note |
   | Vendored code, a force-added fixture, a lockfile someone ignored by mistake | Intentional or a mistake in the ignore file | Ask the owner; a lockfile is never untracked ([`pin-execution-environment`](pin-execution-environment.md)) |

   The converse also exists: tracked generated files that no ignore rule matches (the engine's `GENERATED`
   classification finds those). Treat each the same way, and add the ignore rule when the owner confirms.
2. **Readers of each path.** For every build-output candidate, search the repository for what reads the
   tracked copy, and show the owner the list:
   - compose files (bind mounts and `volumes:`), `Dockerfile*` (`COPY`, `ADD`), nginx or other proxy config
     (`root`, `alias`);
   - deploy files and scripts (`deploy/`, `scripts/`, release workflows, `Makefile` and runner scripts);
   - CI workflows that upload, publish or serve the path;
   - package manifests (`files`, `main`, `exports`) and documentation that tells people to use it.

   A reader that only exists after a build (a stack start-up script that builds the path first) does not need
   the tracked copy. A reader that runs somewhere this repository does not show (another environment's deploy
   pipeline) is **unknown**, and unknown is not safe.
3. **The owner's yes, per path, with no exception.** Show, for each path: the files git lists, the ignore rule
   that matches, every reader found, the script that regenerates it (or "none found"), and what you could not
   see. Never untrack a path a deploy path reads, or may read, without a recorded yes. A clean search is not a
   substitute for the yes. Offer:

   | Option | Pros | Cons |
   |---|---|---|
   | Untrack (`git rm --cached`) with the owner's yes (recommended) | Resolves EXEC-05 completely; the ignore rule then does its job; the working-tree copy stays | If something outside the repository fetched the tracked copy, it breaks until the build runs there; the files remain in history |
   | Add a generated-file header | Keeps the file tracked, so nothing that reads it breaks | Minified bundles, source maps, images and JSON cannot carry a header; the file stays tracked and still goes stale |
   | Skip, with the owner's reason | Zero risk | The item stays open; recorded as `skipped` and never proposed again |

   Untracking without asking is not an option, even when the ignore rule, the regenerating script and zero
   outside readers are all proven.
4. **Competing configs (EXEC-07).** Only when the engine reports a competing pair, or the owner asks: list the
   root config files per concern and ask which is authoritative.

## Steps

1. Work in a worktree from the up-to-date integration branch on the theme branch
   (`agentic-readiness/<phase>-determinism`). Set each item `in_progress`.
2. **Find** the candidates with `git ls-files -ci --exclude-standard` and the EXEC-05 evidence. Sort them by
   the path-kind table. Anything secret-bearing is noted and left alone.
3. **Collect readers** (Inputs step 2) and the regenerating command for each build-output path.
4. **Ask** the owner per path (Inputs step 3) and record the answer before touching the index. A no is
   `skipped` with the reason.
5. **Untrack** each approved path: `git rm -r --cached <path>`. The working-tree files stay, so the local run is
   unaffected. Confirm that the ignore rule matches (`git check-ignore -v <path>`); if it does not, add the rule.
   One commit per path or group, so each reverts alone.
6. **Prove it.** `git ls-files -ci --exclude-standard` no longer lists the path; `git status --porcelain` is
   clean; run the regenerating command once (the build verb or the stack script, through the repository's own
   scripts) and check that it recreates the output and that `git status` stays clean.
7. **Header route** (only if the owner chose it for a file type that carries one): add the marker the check
   looks for in the first 20 lines (`@generated`, `generated by`, `do not edit`), in the generator's template
   so the next build keeps it, not by hand in the output.
8. **EXEC-07, detection and documentation only.** Per concern, list the competing root configs. Ask which is
   authoritative. If one only delegates to the other, document that in the instruction file. Never delete,
   merge or rename a config: the choice of tool is the owner's (see `configure-quality-tools`). The engine
   counts repository-root configs only, and `biome.json` alone for lint and format is not competition.
   With no competing pair, this step is a no-op and the item is not raised.
9. Commit per logical change, each revertible alone.

### Gradle

Profile: [`stacks/java.md`](../../stacks/java.md#execution-determinism). Typical output: `build/`, `out/`,
`bin/`, `.gradle/`, generated `src/**/generated`. Check `settings.gradle` and `build.gradle` for a task that
copies from the tracked path. The wrapper (`gradle/wrapper/*`, `gradlew`) is not generated output: it is the
Gradle pin and must stay tracked, even though a broad ignore rule can match it.

### Node (npm, pnpm, yarn)

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#execution-determinism). Typical output:
`dist/`, `build/`, `coverage/`, `.next/`, minified bundles and `.map` files. A static front-end built into a
folder that a proxy container serves is the case that needs the owner's yes: read the compose file and the
proxy config for the bind mount, and read the stack script for the build that fills the folder before the proxy
starts. `package-lock.json` is never generated output in this sense.
A tracked file that an ignore rule matches is not always build output: an env file with values appears in the
same `git ls-files -ci` list and goes to the secrets theme, not here. Applied once on a repository with a
static bundle bind-mounted read-only into a proxy: the stack script rebuilt the folder before the proxy
started, so untracking was safe once the owner said yes.

## Continue on error

- A path the owner declines to untrack: `skipped`, with the owner's reason. The count of remaining tracked
  paths goes into the note. No ratchet applies.
- A reader the search cannot rule out (deploy outside the repository): `blocked` until the owner answers,
  never `done` on an assumption. Record what is unknown.
- A tracked-but-ignored secret-bearing file: not debt of this playbook. Record it in the note with the path and
  the phase that owns it; do not untrack it here.
- A repository with dozens of tracked build files: untrack by directory, one commit each, and let the owner
  approve the directories, not each file.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| EXEC-05 | `git ls-files -ci --exclude-standard` | No build output listed (a secret-bearing path may remain, noted for the secrets theme). A header-route file shows the marker in its first 20 lines |
| EXEC-05 | The regenerating command, through the repository's script | The output is recreated; `git status --porcelain` stays empty |
| EXEC-07 | Read the root configs per concern | One authoritative config per concern, or a documented delegation; no config deleted by this playbook |

## Rollback

`git revert` the untracking commit: the files return to the index from history. Nothing else changed. A removed
ignore rule or a header goes with its own commit.

## Do-not-do

- Do not untrack a path that a deploy path reads, or may read, without the owner's recorded yes.
- Do not untrack a secret-bearing file here; that is the secrets theme's decision (rotation, history).
- Do not untrack a lockfile, the Gradle wrapper or any hand-written file the ignore rule matches by accident:
  fix the rule.
- Do not delete working-tree files (`git rm` without `--cached`) and do not rewrite history.
- Do not delete, merge or rename a competing config (EXEC-07).
- Do not start containers or the local stack by hand to test a reader.

## State updates

Through [`progress.py`](../../docs/reference/tools-cli.md#progresspy), on the theme branch, `--phase` the
current step:

```bash
python3 brownfield-recipes/tools/progress.py set-status F-nnn in_progress --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "git ls-files -ci --exclude-standard" \
  --verification-result "<no build output listed; regenerating command recreates it>"
python3 brownfield-recipes/tools/progress.py skip F-nnn --target <repo> --phase <phase> \
  --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py theme T2 --status branch_open \
  --branch agentic-readiness/<phase>-determinism --target <repo> --phase <phase> --render
```

A `blocked` status is reached through `in_progress` and needs `--reason`. Only the owner skips an item.
