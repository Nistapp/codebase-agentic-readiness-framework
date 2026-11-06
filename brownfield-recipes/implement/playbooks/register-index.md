# Playbook: `register-index`

> Theme T8 (hygiene and index freshness). Follows the anatomy in [`README.md`](README.md). Written in IR11.1;
> applied and corrected on a Gradle repository (IR11.2) and a multi-component Node repository (IR11.3). Its sibling
> [`add-repo-hygiene`](add-repo-hygiene.md) owns the hygiene files of the same theme.

## Goal

An agent that opens the repository can reach the code index without being told how: the index server is registered
where the harness the team uses reads it, an index exists for this checkout, and the repository says when to refresh
it. An audit run on any machine reaches the same verdict, because the registration an audit relies on is committed,
not left in one developer's home directory.

**The rule this playbook enforces: user-level configuration needs consent.** The playbook never edits a file under
`$HOME` or an XDG directory unless the owner said so and the state records it. A committed project-level file is
offered, never assumed: it makes every contributor's agent start a local tool.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| IDX-01 | [01-discovery-and-index.md](../../audit/checks/01-discovery-and-index.md#idx-01--codebase-memory-mcp-registered-for-this-repository) | A project-level MCP config that names the index server for the harness the team uses, or a documented user-level registration with the gap recorded |
| IDX-02 | [01-discovery-and-index.md](../../audit/checks/01-discovery-and-index.md#idx-02--an-index-exists-for-this-checkout) | The index is built for this checkout (`index_repository`) and answers a structural query |
| IDX-03 | [01-discovery-and-index.md](../../audit/checks/01-discovery-and-index.md#idx-03--index-freshness-vs-head) | A freshness rule in the instruction file and a freshness query (`detect_changes`) as the evidence |

**IDX-01 and IDX-02 are blockers; IDX-03 is a degrader.** Work in the order listed: nothing can be indexed before the
server is reachable, and freshness means nothing before an index exists.

**What the engine can and cannot see.**

- IDX-01 reads project-level files in the target (`opencode.json`, `.mcp.json`, `.cursor/mcp.json`,
  `.vscode/mcp.json`, `.gemini/settings.json`, `.codex/config.toml`) and, unless `--no-user-config` is given, user-level
  files under `$HOME`. A harness whose file is not in that list reads `UNKNOWN` or `FAIL` although it works; ask which
  harness the team uses and look there directly.
- IDX-02 reads a machine-local store. The store is not part of the repository, so the result depends on the machine.
- IDX-03 compares the store's recorded revision with `HEAD`. The store schema records the project root and index time
  but no revision, so the engine's own verdict is `UNKNOWN` by construction. A tool freshness query is the stronger
  evidence. Do not describe that `UNKNOWN` as a soft failure, and do not claim the playbook makes the engine verdict
  `PASS`.
- `--no-user-config` makes an audit independent of the machine: the engine reads no user-level file, and IDX-01 then
  says "no project-level config" when none is committed. A committed project-level file is the only way an
  `--no-user-config` audit finds the registration.

## Preconditions

- The shared procedure in `SKILL.md` applies: [Stage 3](../SKILL.md#stage-3-apply) (state read first, drift first,
  worktree, one item at a time) and [Stage 4](../SKILL.md#stage-4-close-the-theme) (engine re-check, gate, ending).
- A skipped IDX-03 (moment in time, remedy is re-indexing) is not re-proposed.
- **Drift** ([Stage 3](../SKILL.md#stage-3-apply), step 2): a finding that says "the index predates `HEAD`" is true only
  for the moment it was measured; re-measure instead of repeating it.
- **T7 done or `partial`.** The freshness rule is a line in the instruction file
  ([`adapt-agents-md`](adapt-agents-md.md) owns that file; this playbook adds one line, in the section the T7 work
  chose).
- The index tool is installed on the machine that runs the playbook. If it is not, stop and tell the owner; this
  playbook installs nothing.
- Preferences this playbook reads, when present:

| Key | Effect |
|---|---|
| `index.registration` | `project-file`, `document-only` or `none`: what the owner chose for this repository (Inputs 2) |
| `index.user_config_consent` | `yes`: the owner allowed one named user-level edit. Absent or `no`: never edit a user-level file |
| `index.freshness` | `agents-md-rule` (default), `hook` or `auto-refresh-documented` (Inputs 3) |
| `agents_md.harness_deny` | Independent; a committed MCP config is not a permission file, but check both are consistent |

## Inputs to ask

No dependency is installed. Ask:

1. **Which harness, and what is already registered.** Detect from `AGENTS.md`, the vendor pointer files, and the project
   directories (`.vscode/`, `.cursor/`, `.claude/`, `.gemini/`, `.codex/`). List every config file found, project-level
   first, then user-level (read-only: report the path and whether it names the server, never print the file).
2. **Registration form.** The playbook offers both forms; the owner picks one per repository,
   and the answer is recorded as `index.registration`:

   | Form | What the repository gets | Pros | Cons |
   |---|---|---|---|
   | `project-file`: a committed project-level config for the harness the team uses (detected, not assumed) | One small file, for example `.mcp.json` for Claude Code | A `--no-user-config` audit passes; contributors get the registration for free | The file names a command that may be installed at a different path on each machine; every contributor's agent starts a local tool without asking, so it is a team decision |
   | `document-only`: a section in `AGENTS.md` or a docs page saying how to register the server at user level | Text only | No committed config, no consent question | IDX-01 (a blocker) stays `FAIL` under `--no-user-config`; the item is `partial` |

   If the server command differs between machines, the project file uses the bare command name so each machine's `PATH`
   resolves it, and the page says which one to install. Offer one file per harness the team uses, not one for every
   harness.
3. **Freshness.** Default `agents-md-rule`: one line in the instruction file. Alternatives,
   offered only if the owner asks: a git hook that calls the refresh (machine-specific command, skipped by
   `--no-verify`), or a statement that the tool refreshes itself (an unverifiable claim; document it only with the
   freshness query beside it).
4. **User-level edit.** Ask only if the owner wants the playbook to edit a file under `$HOME`. Show the exact file and
   the exact change first. Without a recorded `index.user_config_consent=yes`, do not touch it; give the owner the text
   to add.

## Steps

### Generic

1. **Baseline.** Run the audit launcher with `--no-user-config` for IDX-01 to IDX-03, and once without it. Record both
   verdicts: the difference shows how much depends on the developer's home directory.
2. **Register (IDX-01).** Per Inputs 2:
   - `project-file`: create the harness's project config with one server entry named `codebase-memory-mcp`. Use the file
     name and key the harness's current documentation names (formats change; check the vendor's page and cite the date).
     Keep the entry minimal (a command, no secrets, no machine-specific absolute path). Do not edit an existing project
     config's other entries.
   - `document-only`: add a short section to the docs page or `AGENTS.md` that says how to register the server for each
     harness the team uses. Mark IDX-01 `partial` with the reason.
3. **Build the index (IDX-02).** Run `index_repository` for this checkout (root path), then confirm it answers:
   `list_projects` shows the project and root, and `get_architecture` returns a summary whose file counts match the
   repository (`git ls-files | wc -l` within the engine's own filtering). An index of another checkout, or of a path
   under a different name, is not this checkout's. Do this on the integration branch's latest commit, or on the branch
   the playbook is working in, and say which.
4. **Freshness (IDX-03).** Add one line to the instruction file: the agent re-indexes at the start of a task and after
   the last commit, and checks freshness with `detect_changes`. Write the sentence in the file's own voice, in the
   section where the file already keeps tool guidance, and keep it within the 400-line budget. Run `detect_changes` and
   record the result as the evidence; if it names changed files, re-index and run it again.
5. **Commits:** one for the project config (if any), one for the instruction-file line. The engine re-check
   ([Stage 4](../SKILL.md#stage-4-close-the-theme), step 1) runs with and without `--no-user-config`.

### Gradle and Quarkus

Profile: [`stacks/java.md`](../../stacks/java.md). Generated sources under `build/` and `.gradle/` are not part of the
index; confirm `get_architecture` does not list them. If the repository's tool-state directory (`.codebase-memory/`)
exists, check it is ignored and untracked (CON-03, owned by [`add-deny-rules`](add-deny-rules.md)).

### Node (npm, NestJS, React)

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md). `node_modules/`, `dist/` and `build/` are not
indexed. In a repository with several apps, one index covers the root; the freshness check names the root, not an app.

## Continue on error

- **IDX-01 under `--no-user-config` with the `document-only` form:** `partial`, `--debt "what=no project-level
  registration,count=1"`. This is the owner's choice, not an error; the note says so.
- **IDX-03 engine verdict `UNKNOWN`:** the store records no revision. The item is `partial` when the freshness rule is
  written and `detect_changes` is clean; the note quotes the tool result and the engine limitation. It is never `done`
  on the engine's word alone. This is not a bug of the repository.
- **An index that cannot be built** (tool error, out of memory): `blocked` with the error quoted; do not work around it.
- None of this is a count of violations, so no ratchet or baseline file applies: report-only is the wiring.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| IDX-01 | Launcher with `--no-user-config`; read the project config | `project-file`: names `codebase-memory-mcp`, `PASS`. `document-only`: `FAIL` under the flag, item `partial` |
| IDX-02 | `list_projects` and `get_architecture` | The project is listed with this root; counts match; `PASS` |
| IDX-03 | `detect_changes` against `HEAD`; the instruction file's line | No drift reported, and the rule is written; the engine reports `UNKNOWN`, which the note explains |

## Rollback

`git revert` the commits (project config, instruction-file line). The index itself is machine-local and harmless to
leave; delete the project with `delete_project` only if the owner asks. No user-level file is edited without recorded
consent, so there is nothing to put back there; when consent was given, the state records the exact edit so it can be
undone.

## Do-not-do

- Do not edit a file under `$HOME` or an XDG directory without a recorded `index.user_config_consent=yes`.
- Do not commit a config with an absolute path to one developer's machine, a token or any secret.
- Do not create configuration for harnesses the team does not use.
- Do not install the index tool, add a git hook or edit CI.
- Do not print or quote a user-level config file; report the path and whether it names the server.
- Do not claim the engine's IDX-03 verdict can pass today, and do not read its `UNKNOWN` as stale.
- Do not index a different checkout and report it as this one's.

## State updates

Beyond the shared lines in [Stage 3](../SKILL.md#stage-3-apply) and [Stage 4](../SKILL.md#stage-4-close-the-theme), on
the T8 branch shared with [`add-repo-hygiene`](add-repo-hygiene.md):

```bash
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "engine.py <repo> --no-user-config; read IDX-01" \
  --verification-result "project config names the server"
python3 brownfield-recipes/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --debt "what=engine cannot verify freshness (store records no revision),count=1" \
  --note "freshness rule written; detect_changes clean on <sha>"
python3 brownfield-recipes/tools/progress.py pref set index.registration <project-file|document-only> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py pref set index.user_config_consent no \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py pref set index.freshness agents-md-rule \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
```

Record a preference only when the owner answers; absent means the default above, and `index.user_config_consent` absent
means no user-level edit. The theme closes once, after both T8 playbooks
([Stage 4](../SKILL.md#stage-4-close-the-theme)).
