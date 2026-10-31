# Playbook: `add-hooks-and-commit-rules`

> Theme T4 (local hooks and commit convention). Follows the anatomy in [`README.md`](README.md). Written in
> IR07.1; applied and corrected on a Gradle/Quarkus repository (IR07.2) and a multi-app Node repository (IR07.3).

## Goal

A commit runs a fast local hook chain before it is created, with one committed configuration and a documented
one-time install. The commit-message convention is either enforced locally or explicitly recorded as enforced
elsewhere (the pull-request title) by the owner's decision.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| TOOL-05 | [05-tooling.md](../../audit/checks/05-tooling.md#tool-05--local-hook-chain-active) | Commits a hook-manager configuration the engine reads as wired, with fast changed-files hooks |
| TOOL-06 | [05-tooling.md](../../audit/checks/05-tooling.md#tool-06--commit-convention-enforced) | Offers three options; the owner may skip when the title check is enough (see Commit rule) |

## Preconditions

- The state file exists and Stage 1 triage is done. Read it first. **Respect every `skipped` item**: if the
  owner skipped the commit-convention finding, do not re-propose it; write only the hook chain.
- T1 done: the formatter and linter verbs exist, with a changed-files form ([`define-command-surface`](define-command-surface.md),
  [`configure-quality-tools`](configure-quality-tools.md)). A hook calls those verbs; it never defines its own
  commands.
- Preferences read, when present: `format.mass_reformat` (a `no` means hooks check changed files only, never the
  full tree), `lint.mode`, `layout.command_runner`, `hooks.manager`, `commit.convention`.
- **Run the drift check first.** A finding saying "no hook manager" can be stale; look for `lefthook.yml`,
  `.pre-commit-config.yaml`, `.husky/`, `.githooks/` and `core.hooksPath` on the current default branch.
- Public/private boundary as in the other playbooks.

## Inputs to ask

1. **Hook manager.** Detect first and use what exists. If nothing, offer this set. Currency checked 2026-10-31
   (GitHub releases API, npm registry); re-check when applied.

   | Tool | Version, date | Pros | Cons |
   |---|---|---|---|
   | lefthook (recommended) | v2.2.2, 2026-10-13 (about 9 million npm downloads a week) | One Go binary, no Node or Python needed, polyglot, one committed `lefthook.yml`, parallel hooks | A binary to install per developer; fewer ready-made hooks |
   | pre-commit | v4.7.0, 2026-10-13 | Large hook catalogue, mature | Needs Python on every machine; pins hook repositories by revision |
   | husky + lint-staged | husky 9.1.7, **2024-11-18** | Node standard | **Dropped: no release in over 12 months.** Needs a root Node manifest; runs only after `npm install` |
   | A Gradle git-hooks plugin | not verified | Java only | Not checked for maintenance, no help for a Node repository; do not offer unless a maintained one is verified at apply time |

   Installing the binary is a developer step the owner approves, not a repository dependency.
2. **Hook content.** Default below; the owner may remove, never add a slow hook silently.
3. **Commit rule** (skip when already skipped in the state file):

   | Option | What | Engine reads it as |
   |---|---|---|
   | A. Document the PR-title rule | The repository squash-merges and a CI check rejects non-conventional PR titles; the PR title is what lands on the default branch. Write this in the contributing doc and record the finding `skipped` with that reason | TOOL-06 stays `FAIL` (the engine does not read CI; "TOOL-06's own blind spot"); owner-accepted |
   | B. commitlint in a `commit-msg` stage | Config file plus a hook stage | `PASS`. Needs Node and `@commitlint/cli` (21.2.4); in a repository with no root manifest the version cannot be pinned by a lockfile |
   | C. Both | A and B | `PASS`; carries B's costs |

   Recommend A where squash merges and a title check exist (the history that matters is the squash commit);
   otherwise B. Only the owner skips; record the owner's words.

## Steps

### Generic

1. **Baseline.** Time the formatter's changed-files check and the secret scan on a typical staged change. A hook
   that takes more than a few seconds will be bypassed.
2. **Configuration.** Commit one hook-manager config. The `pre-commit` stage runs, in parallel:
   - the formatter's check on **staged files only** (the T1 changed-files form, never the full tree),
   - the secret scanner on staged changes, at the version already pinned in CI (one pin, shared).
   No tests, no full lint, no type check, no network access in a hook: those stay in the gate and in CI.
3. **Install documentation.** Add the one-time install command (`lefthook install` or the manager's equivalent)
   and the binary install line to the instruction file and the contributing doc. Say that CI is the real gate.
   Never advise `--no-verify`; when a hook fails, fix the cause.
4. **Commit rule** per the owner's option. For A: the contributing doc names the PR-title workflow and the type
   list it enforces. For B or C: add the config and the `commit-msg` stage, with the same type list as the
   title rule so the two cannot disagree.
5. **Verify** with a deliberately bad staged file in a scratch worktree (see Verification). Commit config, docs
   and rule separately.

### Gradle and Quarkus

No Node is needed; the binary manager runs the Gradle formatter task limited to staged files through the
changed-files verb. If the formatter only supports a whole-project run, hook it as report-only or leave the
formatter out and say why (never run a full-tree format in a hook).

### Node (npm, per-app layout)

With no root manifest a Node-based manager has no home, which is another reason the binary manager is the default.
The hook runs each app's changed-files verb from that app's directory (`layout.command_runner`).

## Continue on error

- If the changed-files verb reveals existing debt in a staged file, the hook blocks only on files the commit
  touches and the debt is not mass-fixed; the formatter ratchet from T1 applies. Record the debt counts from T1,
  not new ones.
- A hook that cannot be made fast: leave it out and record the reason; the item stays `partial`.
- An unavailable binary on a machine: the hook is local convenience, CI still gates; not an error.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| TOOL-05 | `test -f lefthook.yml` (or the manager's config) and `git config core.hooksPath` or the install step in the docs | The engine's wiring file exists; the install step is documented |
| TOOL-05 (behaviour) | In a scratch worktree, stage a file with a deliberate format violation and a fake secret, run the hook | The commit is refused with a clear message; a clean staged change passes in a few seconds |
| TOOL-06 | Option A: the contributing doc names the title check and the state records `skipped` with the owner's reason. Option B or C: the config and the `commit-msg` stage exist; a bad message is refused | As stated |

The engine reads TOOL-06 as a file or stage check; option A leaves it `FAIL` by design.

## Rollback

`git revert` the commits (config, docs, rule each revert alone). Developers run `lefthook uninstall`.

## Do-not-do

- Do not install the hook manager on the owner's machine or add it as a repository dependency without approval.
- Do not run tests, a full lint, a full-tree format or any network call in a hook.
- Do not advise `--no-verify` or add a bypass variable.
- Do not re-propose a `skipped` commit-convention finding.
- Do not pick a manager by what looks familiar: detect, then offer the table.
- Do not duplicate the secret-scanner version: reuse the CI pin.

## State updates

```bash
python3 brownfield-recipes/tools/progress.py pref set hooks.manager <lefthook|pre-commit|...> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py skip F-nnn --target <repo> --phase <phase> --by owner \
  --reason "<the owner's words: why the title check is enough>"
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "test -f lefthook.yml" --verification-result "present; install documented"
```

Only the owner skips an item.
