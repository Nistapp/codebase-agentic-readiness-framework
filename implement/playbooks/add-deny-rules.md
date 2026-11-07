# Playbook: `add-deny-rules`

> Theme T7 (`AGENTS.md` and governance). Follows the anatomy in [`README.md`](README.md). Written in IR10.1;
> applied and corrected on a Gradle repository (IR10.2) and a multi-component Node repository (IR10.3). It edits
> **only the prohibitions section** of the instruction file
> ([decision 0001](../../../spec/decisions/0001-constraint-artifact.md): that section is the deny list). Everything
> else in `AGENTS.md` is [`adapt-agents-md`](adapt-agents-md.md)'s.

## Goal

The instruction file has one prohibitions section, under a heading that says so, with an explicit rule for each of
the four concerns (tests, generated files and scratch, the default branch, secrets). Every test directory is named
in a code span, so an agent cannot "fix" a failing test by editing it. Scratch and tool-state directories are
ignored and untracked. The owner has a report of what each harness configuration in the repository lets an agent
do without asking, compared with the section.

**The rule this playbook enforces: tests may change only together with the code that needs the change.** The test
rule is bounded, never a flat ban: the definition of done asks for tests, so a flat "never edit `test/`" would
contradict it.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| AGT-07 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-07--do-not-do--deny-rules-present) | One rule per concern in the prohibitions section: tests, generated files and scratch, default branch, secrets |
| CON-01 | [08-constraints.md](../../audit/checks/08-constraints.md#con-01--allowdeny-artifact-present) | The rules name real paths in code spans (the test directories, the generated folders, the scratch directory) |
| CON-02 | [08-constraints.md](../../audit/checks/08-constraints.md#con-02--test-directories-protected) | Every test directory the engine finds is named in a code span in the bounded test rule |
| CON-03 | [08-constraints.md](../../audit/checks/08-constraints.md#con-03--artefacts-excluded-from-the-index-and-agent-reads) | Scratch and tool-state directories ignored and untracked; the `.gitignore` step is shared with T6 |

**CON-04 is an input, not a check this playbook resolves.** The engine's draft deny list (`do-not-do.draft.md`,
[CON-04](../../audit/checks/08-constraints.md#con-04--draft-allowdeny-emitted), unscored) is the deterministic
starting point for the rules below. Its catalogue entry names no playbook on purpose: the draft is not a defect with
a fix. The state files keep CON-04 in T7 so the theme reads it.

## Preconditions

- The shared procedure in `SKILL.md` applies: [Stage 3](../SKILL.md#stage-3-apply) (state read first, drift first,
  worktree, one item at a time) and [Stage 4](../SKILL.md#stage-4-close-the-theme) (engine re-check, gate, ending).
- **T3 and T6 done or `partial`.** T3 ([`env-inventory-and-secrets`](env-inventory-and-secrets.md)) decided which
  env and secret files exist and which are tracked on purpose; the secrets rule states that decision, it does not
  remake it. T6 ([`establish-docs-contract`](establish-docs-contract.md)) set up the scratch directory rule (DOC-03);
  CON-03 reuses it.
- **Drift** ([Stage 3](../SKILL.md#stage-3-apply), step 2): re-list the test directories on the current integration
  branch; a finding that names one directory may be short of the full list.
- **The CON-04 draft.** Run the audit launcher with `--emit-baseline`, output outside the target:

  ```bash
  python3 brownfield-recipes/tools/engine.py <target> --out-dir <dir outside the target> --emit-baseline
  ```

  Read `do-not-do.draft.md` beside the report. Propose only entries that match this repository (a path the scan
  observed); drop the canonical patterns that match nothing here. If the draft cannot be written (CON-04 `UNKNOWN`,
  the reason is in its summary), list the paths by hand with the commands in Steps 2.
- Preferences this playbook reads, when present:

| Key | Effect |
|---|---|
| `agents_md.harness_deny` | `yes`: the owner opted in to mirroring the prohibitions into harness configuration that already exists (Steps 6). Absent or `no`: report only |
| `agents_md.release_tags` | The default-branch and release rule must agree with it |
| `ci.pr_by_agent` | The default-branch rule must agree with it ([ADR 0003](../../docs/architecture/adrs/0003-push-and-pr-policy.md)) |
| `extra.*` | Owner decisions about tracked env files or scratch folders that the rules must state, not change |

## Inputs to ask

No tool is installed. Ask:

1. **Heading.** Keep the owner's heading when it already says what an agent must not do. The engine finds the
   section by a trigger word in the heading (`Never`, `Do not`, `Don't`, `Must not`, `Prohibited`, `Forbidden`,
   `Deny`, `Off-limits`) or, failing that, by three or more prohibition lines in its body. A section found only by
   its body falls out of the check if a later edit trims it below three lines, so when the heading has no trigger
   word, propose adding one (`## Security and safety: never`); the owner decides.
2. **Which test directories.** Show the list from Steps 2. Default: name each directory in its own code span. For
   many nested test folders, offer one ignore-style pattern that covers them (a bare name such as `__tests__/`
   covers that name at any depth); the owner picks.
3. **Generated paths.** From the CON-04 draft and the build files: build output, generated clients, vendored code,
   lock files a tool regenerates. Ask which the owner wants named; a lock file is usually "regenerate with the tool,
   never edit by hand", not "never touch".
4. **Default branch.** The branch names come from the state and the repository (the same facts as the AGT-09
   sentence in [`adapt-agents-md`](adapt-agents-md.md#steps)); confirm them.
5. **Harness permission review (Steps 6).** Report only, by default. Mention that `agents_md.harness_deny=yes` is
   how the owner opts in to mirroring the prohibitions into an existing harness file; never ask the owner to create
   a harness file.

## Steps

### Generic

1. **Baseline.** Read the whole instruction file once: a prohibition stated outside the section is real governance
   the engine does not see. Note the section the engine picked (its AGT-07 evidence) and its line count.
2. **List the paths.**
   - Test directories, as the engine finds them (a path segment `test`, `tests` or `__tests__`; `spec`/`specs` are
     not counted): `git ls-files | grep -oE '^(.*/)?(test|tests|__tests__)/' | sort -u`.
   - Generated paths and scratch: the CON-04 draft's generated and test categories, the `.gitignore` entries for
     build output, and `artefacts/` (or `artifacts/`).
   - Secret stores: the T3 inventory (env files, keystores, realm or credential exports) and how each is handled.
3. **One rule per concern**, each a single line in the section, naming paths in code spans:
   - **Tests (CON-02, AGT-07):** "Never edit, skip or delete a test in `src/test/` to make a failing test pass;
     change a test only together with the code change that needs it." Name every directory from Steps 2. The
     framework's own [`AGENTS.md`](../../../AGENTS.md#never) has this form.
   - **Generated files and scratch:** "Never edit generated output by hand (`build/`, `dist/`); regenerate it with
     the command that makes it. `artefacts/` is scratch: never commit it and never treat it as a source of truth."
   - **Default branch:** "Never push to, merge into or force-push `main` or `dev`; never tag or publish a release."
     Keep it consistent with the AGT-09 sentence ([`adapt-agents-md`](adapt-agents-md.md) Steps 6): one states the
     model, this one states the prohibition; neither restates the other in different words.
   - **Secrets:** "Never open, print or commit a secret store (`.env`, `*.jks`, ...)." If some env files are
     tracked on purpose (an owner decision in the state), the rule says which and what they may hold; it does not
     claim they are ignored.

   When the file has no prohibitions section (the do-nots are scattered bullets), add one `## Do not` section with
   one line per concern and leave the scattered bullets where they are. The secrets line states every env file the
   owner tracks on purpose (names, and that it may hold local values only).

   Add a rule only where the section lacks one; reword an existing rule only to add the path span it lacks. Keep
   the owner's other prohibitions as they are.
4. **Scratch and tool state (CON-03).** For every present root among `artefacts/`, `artifacts/`,
   `.codebase-memory/`, `.opencode/`, `.agentic-tdd/`: confirm an ignore rule covers it
   (`git check-ignore -v <root>/x`) and `git ls-files <root>` prints nothing. Use
   [`establish-docs-contract`](establish-docs-contract.md#steps) step 7 for the procedure (add the rule; untrack only
   what the owner confirms is scratch). A root that does not exist needs nothing.
5. **Stub files.** A vendor pointer file (`CLAUDE.md` holding `@AGENTS.md`) does not need its own prohibitions: the
   harness reads `AGENTS.md` through it. If a vendor file carries prohibitions of its own, do not edit it here; hand
   it to the "ask about stub files" rule in [`adapt-agents-md`](adapt-agents-md.md#inputs-to-ask) (Inputs 3).
6. **Harness permission review (report only).** For each harness configuration file **present in the repository**,
   list what it lets an agent do without a prompt and compare that with the section. Formats checked against the
   vendors' current docs on 2026-11-06; re-check when applied:

   | Harness | Project file | Keys |
   |---|---|---|
   | Claude Code | `.claude/settings.json` | `permissions.allow`, `permissions.ask`, `permissions.deny` (rules such as `Bash(git push *)`, `Edit(src/test/**)`, `Read(./.env)`; deny, then ask, then allow) and `permissions.defaultMode` |
   | opencode | `opencode.json` | `permission`: `edit`, `bash`, `webfetch`, `read` and others set to `allow`, `ask` or `deny`; `bash` may map command patterns (`"git push *": "deny"`) |
   | Codex | `.codex/config.toml` (read only for a trusted project) | `approval_policy`, `sandbox_mode` |
   | Cursor, Gemini CLI, others | Their project files (`.cursorignore`, `.cursor/`, `.gemini/settings.json`) | Not confirmed on 2026-11-06; read the vendor's current docs before naming a key |

   A gap is a prohibition the configuration allows without asking (an `allow` that covers `git push`, a broad
   `Bash(python3:*)` that can rewrite a test file, an edit rule over a test directory). Put the gaps in the pull
   request description and in a state note on the AGT-07 item. **Never edit, create or delete a permission file.**
   Only when the state records `agents_md.harness_deny=yes` does the playbook add deny entries that mirror the
   prohibitions (tests, secrets, default branch) to a configuration file that already exists, in its own commit;
   it still never creates one. When no harness configuration is present, report "none present" and stop. A
   permission rule is hardening, not the deny list; the audit never scores it.
7. **Commits:** one for the section, one for any `.gitignore` change. The engine re-check
   ([Stage 4](../SKILL.md#stage-4-close-the-theme), step 1) covers AGT-07, CON-01, CON-02 and CON-03.

### Gradle and Quarkus

Profile: [`stacks/java.md`](../../stacks/java.md#boundaries). The test directory is usually `src/test/` per module;
generated output is `build/` and `.gradle/`; the Flyway or Liquibase migration folder
(`src/main/resources/db/migration/`) is a frequent CON-04 entry, usually ruled as "never edit an applied migration;
add a new one". The wrapper (`gradlew`, `gradle/wrapper/`) is regenerated, not hand-edited.

### Node (npm, NestJS, React)

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#boundaries). Test folders are `test/` (NestJS
end-to-end) and `__tests__/`; Create React App and Jest may keep `*.test.ts` beside the sources, which no directory
rule covers: say so in the test rule ("and any `*.test.ts` or `*.spec.ts` file"), knowing CON-02 counts only
directories. Generated output is `dist/`, `build/` and `coverage/`; `node_modules/` is never edited. In a per-app
layout name each app's directories (`app-a/test/`), not a root `test/` that does not exist.

## Continue on error

- **A test directory the owner does not want named** (fixtures that are data, a folder being deleted): the item is
  `partial` with `--debt "what=test directories not named in the deny list,count=N"`, or `skipped` if the owner says
  so. CON-02 keeps reading `PARTIAL`.
- **A tracked scratch file the owner wants kept:** `partial` with the count of tracked files under the root; nothing
  is untracked without the owner.
- **Harness permission gaps:** reported, not fixed (unless `agents_md.harness_deny=yes`). They are not debt on any
  check, because no check scores them; record them as a note on the AGT-07 item.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| AGT-07 | The prohibitions section; the engine's AGT-07 | Heading found; one rule each for tests, generated files, default branch, secrets; `PASS` |
| CON-01 | Each code span in the section: `test -e <path>` | At least one span matches a real path (in practice all of them); `PASS` |
| CON-02 | The test-directory list from Steps 2 against the spans | Every directory named or covered by a pattern; `PASS` |
| CON-03 | `git check-ignore -v <root>/x` and `git ls-files <root>` per present root | Ignored, nothing tracked; `PASS` |
| Review | The PR description | One line per harness configuration present (or "none present"), with its gaps |

## Rollback

`git revert` the section commit, and the `.gitignore` commit if there was one (`git revert` returns any untracked
scratch file to the index). A harness configuration commit exists only with `agents_md.harness_deny=yes` and
reverts alone.

## Do-not-do

- Do not edit anything in `AGENTS.md` outside the prohibitions section.
- Do not write a flat ban on test directories; the rule is bounded.
- Do not edit, create or delete a harness permission file unless the owner recorded `agents_md.harness_deny=yes`,
  and never create one.
- Do not untrack, ignore or delete a file the owner has not confirmed is scratch, and do not change which env files
  are tracked; state the owner's decision instead.
- Do not paste the CON-04 draft whole: an entry that matches nothing in the repository is noise.
- Do not open, print or quote a secret store while listing the paths.

## State updates

Beyond the shared lines in [Stage 3](../SKILL.md#stage-3-apply) and [Stage 4](../SKILL.md#stage-4-close-the-theme), on
the T7 branch shared with [`adapt-agents-md`](adapt-agents-md.md):

```bash
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "<launcher run>; read CON-02" \
  --verification-result "every test directory named in the prohibitions section"
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "read the prohibitions section" \
  --verification-result "four concerns covered" \
  --note "harness review: <none present | gaps listed in the PR>"
python3 brownfield-recipes/tools/progress.py pref set agents_md.harness_deny no \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
```

Record `agents_md.harness_deny` only when the owner answers; absent means report only. The theme closes once, after
both T7 playbooks ([Stage 4](../SKILL.md#stage-4-close-the-theme)).
