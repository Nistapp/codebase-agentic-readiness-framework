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

- The shared procedure in `SKILL.md` applies: [Stage 3](../SKILL.md#stage-3-apply) (state read first, drift first,
  worktree, one item at a time) and [Stage 4](../SKILL.md#stage-4-close-the-theme) (engine re-check, gate, ending).
- If the owner skipped the commit-convention finding, write only the hook chain.
- T1 done: the formatter and linter verbs exist, with a changed-files form
  ([`define-command-surface`](define-command-surface.md), [`configure-quality-tools`](configure-quality-tools.md)). A
  hook calls those verbs; it never defines its own commands.
- Preferences read, when present: `format.mass_reformat` (a `no` means hooks check changed files only, never the
  full tree), `lint.mode`, `layout.command_runner`, `hooks.manager`, `commit.convention`.
- **Drift** ([Stage 3](../SKILL.md#stage-3-apply), step 2): a finding saying "no hook manager" can be stale; look for
  `lefthook.yml`, `.pre-commit-config.yaml`, `.husky/`, `.githooks/` and `core.hooksPath` on the current default branch.

## Inputs to ask

1. **Hook manager.** Detect first and keep what exists. Never replace a working manager. If nothing exists,
   recommend the manager that matches the stack (the stack profile's Tooling defaults, `audit/stacks/`), not this
   framework's own choice. Offer the others as alternatives. Currency checked 2026-11-09 (npm registry and
   downloads API, PyPI, GitHub API); re-check when applied.

   | Stack | Recommend | Version, date | Pros | Cons |
   |---|---|---|---|---|
   | Node or TypeScript with a root `package.json` | Husky + lint-staged | husky 9.1.7, 2024-11-18; lint-staged 17.6.0, 2026-09-26 (about 50 and 41 million npm downloads a week) | The Node default; installed by the package manager, pinned by the lockfile; `prepare: husky` wires it | Runs only after `npm install`; needs a root manifest |
   | Python | pre-commit | v4.7.0, 2026-10-12 | Large hook catalogue, mature, the Python default | Needs Python on every machine; pins hook repositories by revision |
   | Mixed stacks, Node with no root manifest, Java, or no profile | lefthook | v2.2.2, 2026-10-13 (about 9.5 million npm downloads a week) | One Go binary, no Node or Python needed, one committed `lefthook.yml`, parallel hooks | A binary to install per developer; fewer ready-made hooks |

   Alternatives you may find, and keep: simple-git-hooks (Node, 2.14.0, 2026-08-28), or a committed
   `.githooks/` folder. A build task sets `core.hooksPath` for it, often in Gradle or Maven repositories. A quiet
   release history alone is no reason to reject a tool. Husky had no release since 2024-11-18. Its repository is
   not archived, and it is the most used manager (checked 2026-11-09). Reject a tool only when it is archived or
   has an open security advisory. Installing a binary is a developer step the owner approves, not a repository dependency.
2. **Hook content.** Default below; the owner may remove, never add a slow hook silently.
3. **Commit rule** (skip when already skipped in the state file):

   | Option | What | Engine reads it as |
   |---|---|---|
   | A. Document the PR-title rule | The repository squash-merges and a CI check rejects non-conventional PR titles; the PR title is what lands on the default branch. Write this in the contributing doc and record the finding `skipped` with that reason | TOOL-06 stays `FAIL` (the engine does not read CI; "TOOL-06's own blind spot"); owner-accepted |
   | B. A commit-message rule in a `commit-msg` stage, matched to the stack | Node: commitlint (`@commitlint/cli` 21.2.4) in `.husky/commit-msg`. Python: a pre-commit `commit-msg` hook (conventional-pre-commit, commitizen or gitlint). Others: the manager's `commit-msg` stage | `PASS`. commitlint needs Node; with no root manifest its version cannot be pinned by a lockfile, so prefer the Python or lefthook route there |
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
3. **Install documentation.** Add the one-time install command to the instruction file and the contributing doc.
   That is `npm install` for Husky, `pre-commit install` or `lefthook install`. For a binary manager, add the
   binary install line too. Say that CI is the real gate.
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

### Node with a root manifest

Use Husky + lint-staged. Add `husky` and `lint-staged` as dev dependencies (the lockfile pins them), set
`"prepare": "husky"` in `package.json`, and write `.husky/pre-commit` as `npx lint-staged`. Configure lint-staged
to run the formatter's check on the staged files only. The engine reads `.husky/` as wired only when a script
names `husky` (`TOOL-05`). For the commit rule, `.husky/commit-msg` runs `npx --no -- commitlint --edit "$1"`.

### Node (npm, per-app layout)

With no root manifest a Node-based manager has no home, so lefthook is the recommendation here.
The hook runs each app's changed-files verb from that app's directory (`layout.command_runner`).

With lefthook (IR07.3):

- Use one command per app with `root: <app>/` and `npx --no-install prettier --check {staged_files}`; the file
  list is then relative to that app. `glob` patterns are matched against the path from the repository root, and a
  `**` needs at least one folder in between: list a direct-child pattern and a nested one for each folder
  (`app/src/*.ts` and `app/src/**/*.ts`). Check with a throwaway config that prints `{staged_files}`.
- Test with `lefthook run pre-commit` in a scratch clone (no `lefthook install`, so nothing is written into a shared
  git directory) and a staged file with a format violation and a fake token. gitleaks allowlists the well-known
  example keys (such as the AWS documentation key); use a token-shaped value that is not on that list.
- A hook blocks on the files the commit touches, including a staged file that was already unformatted before the
  change. That is the ratchet working; say so in the install text rather than adding an exception.
- Fetch the test binary into a scratch directory and compare its SHA-256 with the digest GitHub publishes for the
  release asset; do not put it on the owner's `PATH`.

## Continue on error

- If the changed-files verb reveals existing debt in a staged file, the hook blocks only on files the commit
  touches and the debt is not mass-fixed; the formatter ratchet from T1 applies. Record the debt counts from T1,
  not new ones.
- A hook that cannot be made fast: leave it out and record the reason; the item stays `partial`.
- An unavailable binary on a machine: the hook is local convenience, CI still gates; not an error.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| TOOL-05 | `test -f <manager config>` (`.husky/pre-commit`, `.pre-commit-config.yaml`, `lefthook.yml`) and `git config core.hooksPath` or the install step in the docs | The engine's wiring file exists; the install step is documented |
| TOOL-05 (behaviour) | In a scratch worktree, stage a file with a deliberate format violation and a fake secret, run the hook | The commit is refused with a clear message; a clean staged change passes in a few seconds |
| TOOL-06 | Option A: the contributing doc names the title check and the state records `skipped` with the owner's reason. Option B or C: the config and the `commit-msg` stage exist; a bad message is refused | As stated |

The engine reads TOOL-06 as a file or stage check; option A leaves it `FAIL` by design.

## Rollback

`git revert` the commits (config, docs, rule each revert alone). Developers run the manager's uninstall
(`lefthook uninstall`, `pre-commit uninstall`; for Husky, `git config --unset core.hooksPath`).

## Do-not-do

- Do not install the hook manager on the owner's machine or add it as a repository dependency without approval.
- Do not run tests, a full lint, a full-tree format or any network call in a hook.
- Do not advise `--no-verify` or add a bypass variable.
- Do not re-propose a `skipped` commit-convention finding.
- Do not pick a manager by what looks familiar or by what this framework uses: detect, then recommend by stack.
- Do not duplicate the secret-scanner version: reuse the CI pin.

## State updates

Beyond the shared lines in [Stage 3](../SKILL.md#stage-3-apply) (`in_progress`, the theme rows) and
[Stage 4](../SKILL.md#stage-4-close-the-theme) (the ending):

```bash
python3 implement/tools/progress.py pref set hooks.manager <husky|pre-commit|lefthook|...> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py skip F-nnn --target <repo> --phase <phase> --by owner \
  --reason "<the owner's words: why the title check is enough>"
python3 implement/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "test -f <manager config>" --verification-result "present; install documented"
```
