# Playbook: `env-inventory-and-secrets`

> Theme T3 (secrets and environment). Follows the anatomy in [`README.md`](README.md). Written in IR06.1;
> applied and corrected on a Gradle/Quarkus repository (IR06.2) and a multi-app Node repository (IR06.3).

## Goal

An agent can list every variable a script, build or application reads without seeing one value: a committed
example file declares the names (required or optional), no secret-bearing file is tracked without a recorded
owner decision, and the ignore rules cover every secret shape the audit probes.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| EXEC-04 | [09-execution-determinism.md](../../audit/checks/09-execution-determinism.md#exec-04--env-var-inventory-complete) | Builds the names-only inventory and commits an example file that declares every variable the code reads |
| SEC-01 | [12-security-hygiene.md](../../audit/checks/12-security-hygiene.md#sec-01--env-untracked-and-ignored) | Finds tracked `.env`-shaped files and hands each to the owner for a decision; never edits one |
| SEC-02 | [12-security-hygiene.md](../../audit/checks/12-security-hygiene.md#sec-02--no-key-shaped-strings-in-tracked-files) | Counts key-shaped lines by path and line number, wires the repository's existing scanner, never prints a hit |
| SEC-03 | [12-security-hygiene.md](../../audit/checks/12-security-hygiene.md#sec-03--ignore-patterns-cover-secret-shapes) | Adds the missing secret shapes to the ignore file, with a tracked-file check before and after |

## Preconditions

- The state file exists and Stage 1 triage is done ([`SKILL.md`](../SKILL.md#stage-1-triage)). Read it first and
  respect every `skipped` item and preference. A tracked secret-bearing file the owner decided to keep is a
  recorded exception, not a finding to re-raise.
- Preferences this playbook reads, when present: `extra.t3` (what the owner already chose for a tracked key
  file), `layout.command_runner` (per-app layout means one example file per app), `ci.edits_authorised`,
  `scanner.choice` (a dependency scanner is not a secret scanner), `format.mass_reformat`.
- No earlier theme is needed. If the command-surface theme already named the `security` verb, reuse it in the
  scanner step; do not create a second one.
- **Hard rules, every step:** never print, quote, log or copy a value from any env, properties, realm,
  keystore or credentials file, not in a commit message, a status file or a summary. Count lines, list key
  names. Do not open a `.env`-like file at all (the audit does not, even to confirm a finding). If a judgment
  needs the value ("is this real?"), ask the owner. Rotation and history rewrite are the owner's job: the
  playbook reports and stops.

## Inputs to ask

1. **Example file name and place.** Detect first: an existing example file (`.env.example`, `.env.sample`,
   `.env.template`, `env.example`, `*.env.example`) is extended, not replaced. If none exists, offer:

   | Option | Pros | Cons |
   |---|---|---|
   | One `.env.example` at the root | The engine reads it with no configuration; one place | Not a dotenv the code loads when the variables are CI or repository variables: it is a documentation file |
   | `scripts/ci/env.example` beside the scripts and their README | Sits next to the code that reads the variables; the engine accepts the `env.example` basename | A reader at the root does not find it; two homes if the app also needs a local example |
   | One example file per app and per service (follows a per-app `layout.command_runner`) | Matches the layout; each app's variables stay with the app | Several files to keep aligned; step 5 adds a cross-check |

   Recommend the second for CI and script variables, the third when the repository is per-app. Record the choice
   as a preference. Ask also whether optional framework overrides (for example `QUARKUS_*`) are listed; the
   default is yes, marked optional, names only.
2. **Tracked secret-bearing files.** For each path from step 3, show the owner the path and the reason it was
   flagged (never its content) and ask: untrack, keep as a documented exception, or skip. Only the owner can
   say a tracked local-development file holds throwaway values or must stay for developers' setup. A keep or a
   skip is recorded in the owner's words; a skip is final.
3. **Scanner.** Detect what the repository already runs (a script that CI calls, a `.gitleaks.toml`, a
   `.secrets.baseline`, a pre-commit entry). If one exists, use it and add no tool (the tool is the owner's
   choice). Only a repository with none gets this table, with a recommendation:

   | Tool | Last release | Pros | Cons |
   |---|---|---|---|
   | gitleaks (MIT) | v8.30.1, 2026-03-21; repo active 2026-10 | Single binary; fast; history and working-tree scans; config file; large user base | Pattern based, so entropy-only secrets are missed; false positives need an allowlist |
   | trufflehog (AGPL-3.0) | v3.99.7, 2026-10-24 | Verifies some hits against the live service; many detectors | AGPL licence; verification makes network calls with a found credential, which an owner may not want |
   | detect-secrets (Apache-2.0) | v1.5.0, 2024-05-06; repo last pushed 2026-04 | Baseline file ratchets existing debt; plugin model | Python dependency; no release in over two years; slower on large trees |

   Currency checked 2026-10-30 (GitHub releases API, PyPI). Re-check it when the playbook is applied: it
   dates. Adding a local scanner step to the command surface belongs to the command-surface and CI themes:
   note it, do not do it here.
4. **Realm, vault or identity-provider exports** that contain a secret field (for example a Keycloak realm
   JSON). These are owner-review only: list the paths and the count of secret-field keys per file; ask nothing
   about values; do not edit or template them.

## Steps

### Generic

1. **Baseline.** Record `git ls-files -ci --exclude-standard` (tracked files an ignore rule matches) and the
   list of tracked paths whose names match a secret shape: `.env`, `.env.*`, `*.env`, `*.pem`, `*.key`,
   `*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `*.crt`, `*.cer`, `id_rsa*`, `id_ed25519*`, `.aws/credentials`.
   Paths only. Also list `!` negation lines in every ignore file: a negation can re-include a secret shape that
   a rule above it ignores.
2. **Inventory the reads, names only.** Search for variable reads with a pattern per source kind (the stack
   subsections give the patterns). Never open a `.env`-like file for this; the code and the scripts are the
   source. In a repository whose scripts and apps were added after the audit, run the inventory over the
   current tree, not the audit's list (new script directories carry variables the audit never saw). Output
   one table: `name | required or optional | read by (script, app or CI) | source file:line`.
   Rules for the table:
   - Shell `${VAR:-default}` or `${VAR-}` marks an optional variable; `${VAR:?msg}` or a bare `${VAR}` under
     `set -u` marks a required one.
   - **Shell builtins and script-internal names are not variables.** `SECONDS`, `RANDOM`, `PWD`, `HOME`,
     `BASH_SOURCE`, loop counters and any name the script assigns before it reads it are not inputs. The
     engine reports some of them as missing (audit-engine defect A8). Do not add them to the example file;
     record each as a false positive with the reason, and say in the example file's header that the
     engine's list is not the inventory.
   - A name assigned in a script and read by a later script is an input of the second one only if no caller sets
     it. A literal assigned at the top of a script (`NAME=value`, no `${NAME:-...}`) is a constant, not an input,
     even when its name looks like a setting; a name that appears only inside a printed hint is container-side.
   - A name the code reads through a multi-line call (the key on the next line) is missed by a one-line grep:
     check each declared-but-unread name with a plain `grep -rn NAME` before calling it stale.
3. **Find tracked secret-bearing files** from the baseline and apply the owner's answer (Inputs step 2).
   Untracking, when the owner chooses it, is `git rm --cached <path>`: keep the working-tree file, fix any doc
   that names it, and do not rotate or rewrite history. If the file is read by a stack script or a compose
   file, find the reader first and say what breaks; verify through the repository's own script, never by
   starting containers by hand. A kept file stays as it is (no edit, no ignore rule changed for it).
4. **Write the example file(s)** (Inputs step 1). In a per-app repository write one file per app plus one for
   the script areas (CI, deploy, identity-provider scripts), each with its own false-positive header. Extend an
   existing example file: add the names it lacks, mark a declared name the code never reads `# legacy` (do not
   delete it). In a public-bundle app (`REACT_APP_*`, `VITE_*`) say in the header that every value is published.
   Names only: `NAME=` with a one-line comment (what reads it, required or optional, a placeholder format
   such as `<aws-role-arn>`; low-entropy, never a real-looking value).
   Optional variables are commented out or marked `# optional`. Do not copy a value from any real file.
5. **Cross-check.** Every name in the inventory is in an example file or is on the false-positive list with a
   reason; every name in an example file is read somewhere (a stale name is removed or marked legacy). In a
   per-app layout, check each app's file against its own reads.
6. **SEC-03 ignore rules.**
   1. Run `git ls-files` against each missing shape. A shape that a tracked file already uses (an intentional
      public certificate, a test fixture) gets a named `!` exception with a comment, never a silent gap.
   2. Add the missing shapes from the check's own suggestion list (the audit's SEC-03 output names them): SSH
      private keys, PKCS#12, PFX, keystore, `.crt`, `.cer`, the AWS credentials folder. Append, do not reorder.
      `*.cer` and `*.crt` share one caveat: a future public certificate needs a named `!` line. Verify with
      `git check-ignore -q` on one sample path per shape, including one under a directory a negation re-includes.
   3. Read each existing `!` line: if it re-includes a secret shape, report it to the owner (do not remove it).
      When the owner keeps the files, add one comment above the negation block saying they are retained by owner
      decision (comment only, no rule change), so the next reader does not try to untrack them.
   4. Re-run `git ls-files -ci --exclude-standard`. A path newly listed was tracked and is now matched by a
      rule: hand it to step 3. An ignore rule never untracks a file, which is why a force-added key stays
      tracked until `git rm --cached`.
7. **SEC-02.** Run the scanner the repository already has (Inputs step 3). Record hit counts by path and line,
   never the line. A hit is a candidate for the owner, not an edit. Test fixtures with obviously fake tokens
   are listed as such and recorded in the scanner's allowlist only if the owner agrees.
8. **Realm and identity exports** (Inputs step 4): write the path list and counts into the state note and
   "Found on the way". No change to the files.
9. **Docs.** Add the example file(s) to the instruction file's variables paragraph and to the CI README, if either
   documents variables by hand: one pointer, not a second copy. If the instruction file says env files are
   ignored and a tracked one exists, record the contradiction; the AGENTS.md theme fixes it. A deploy doc that
   names variables by hand gets one pointer line to the example file, not a copy.
10. Commit per logical change (example file, ignore rules, untracking), each revertible alone.

### Gradle and Quarkus

Profile: [`stacks/java.md`](../../stacks/java.md#execution-determinism). Reads to search, names only:
`System.getenv("NAME")`, `@ConfigProperty(name = "x.y")` and `${NAME}` or `${NAME:default}` in
`application.properties`/`application.yaml`; a Quarkus property `a.b.c` is overridable by the variable
`A_B_C` and the framework's `QUARKUS_*` set (optional by definition). `gradle.properties` keys read with
`providers.environmentVariable("NAME")` or `System.getenv` in `build.gradle`. Keystores and JKS files are the
usual force-added file: SEC-03's `*.jks` rule can already exist while one is tracked.

### Node (npm, CRA, NestJS)

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#execution-determinism). Reads to search,
names only: `process.env.NAME` and `process.env['NAME']`, `ConfigService.get('NAME')` and
`configService.getOrThrow`, schema files (`Joi.object`, `class-validator` environment classes), `REACT_APP_*`
and `VITE_*` (build-time, bundled into the public output, which makes them inventory entries and a
publication risk: say so in the example file's comment), `dotenv`/`env_file` loads. A tracked `local.env` the
owner calls a by-design local file is listed, never opened.

### Dockerfiles, compose and CI

`ARG NAME` and `ENV NAME` in Dockerfiles; `${NAME}`, `${NAME:-x}` and `env_file:` in compose files (the
`env_file` path is a tracked-file candidate for step 3); `vars.NAME`, `secrets.NAME` and `env:` in workflow
files. Repository variables and secrets are not in the repo: the example file is their only declaration.

## Continue on error

- Key-shaped lines the scanner reports in tracked files: counted by path, recorded as debt on SEC-02, not edited.
  The existing CI scan stays as the guard against new ones; a repository with no scan gets a report-only step
  noted for the CI theme.
- A tracked secret-bearing file the owner keeps: a recorded exception (`skipped` with the owner's words, or the
  item `partial` with the path named). It stays as it is; the check keeps reading FAIL in re-audit and the
  note says why.
- A variable whose owner or requiredness cannot be told from the code: listed as `unknown` in the table, asked
  once, never guessed.
- An ignore shape that would hide an intentional tracked file: add the named `!` exception rather than skip the
  shape.
- No mass edit, no rewrite of a properties or env file to make a scan pass.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| EXEC-04 | Re-run the audit's EXEC-04, or compare the inventory table with the example file | Every inventory name is declared or on the false-positive list with a reason; no value in the file |
| SEC-01 | `git ls-files` filtered to `.env`/`.env.*` shapes | None tracked, or each remaining path is a recorded owner exception (the re-audit still reads FAIL; the note says why) |
| SEC-02 | The repository's scanner | Hit count equals the recorded baseline or lower; no new path |
| SEC-03 | Re-run the audit's SEC-03; `git ls-files -ci --exclude-standard` | All eleven shapes covered; the ls-files list is empty or each path is a recorded exception |

## Rollback

`git revert` the commit: the example file, the ignore rules and the untracking each revert alone. Untracking
only removes the path from the index; `git revert` returns it. Nothing was rotated, so nothing else needs
undoing.

## Do-not-do

- Do not print, quote, log or copy a value from any env, properties, realm, keystore or credentials file, and
  do not open a `.env`-like file.
- Do not rotate a credential, remove one from history or run a history-rewriting command: report and stop.
- Do not touch a tracked env file the owner keeps; do not add an ignore rule or `git rm --cached` for it.
- Do not re-raise a finding the owner rejected or skipped; new observations go to "Found on the way".
- Do not template, edit or "clean" realm or identity-provider exports.
- Do not install a scanner the owner has not approved.
- Do not put shell builtins or script-internal names in the example file.
- Do not start containers or the local stack by hand to test a change; use the repository's scripts.

## State updates

Through [`progress.py`](../../docs/reference/tools-cli.md#progresspy), on the theme branch, `--phase` the
current step:

```bash
python3 brownfield-recipes/tools/progress.py set-status F-nnn in_progress --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "git ls-files -ci --exclude-standard" \
  --verification-result "<empty, or only the recorded exceptions>"
python3 brownfield-recipes/tools/progress.py skip F-nnn --target <repo> --phase <phase> \
  --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py pref set layout.env_example <path> --target <repo> --phase <phase> \
  --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py theme T3 --status branch_open \
  --branch agentic-readiness/<phase>-secrets-env --target <repo> --phase <phase> --render
```

`theme T3 --status pr_open` requires `--pr <number>`, so open the PR first and commit the final state files
after it (a theme with a skipped item still closes when every other item is `done`).

Only the owner skips an item. A keystore decision is already a preference (`extra.t3`) when the owner made
it; do not ask again, confirm it in one line.
