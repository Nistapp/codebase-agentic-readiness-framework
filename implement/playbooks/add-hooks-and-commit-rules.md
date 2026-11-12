# Playbook: `add-hooks-and-commit-rules`

> Theme T4 (local hooks and commit convention). Follows the anatomy in [`README.md`](README.md). Written in
> IR07.1; applied and corrected on a Gradle/Quarkus repository (IR07.2) and a multi-app Node repository (IR07.3).

## Goal

A commit runs a fast local hook chain before it is created, with one committed configuration and a documented
one-time install. The commit-message convention runs in two places with one type list: a local `commit-msg` stage,
so an agent learns of a bad subject before it pushes, and a CI step, which no `--no-verify` can skip. The owner may
instead record the pull-request title check as enough. A guard in the same chain refuses a commit on a protected
branch, so an agent learns it is on the wrong branch before it commits, not when the push is refused.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| TOOL-05 | [05-tooling.md](../../audit/checks/05-tooling.md#tool-05--local-hook-chain-active) | Commits a hook-manager configuration the engine reads as wired, with fast changed-files hooks |
| TOOL-06 | [05-tooling.md](../../audit/checks/05-tooling.md#tool-06--commit-convention-enforced) | Writes the commit rule as a local `commit-msg` stage and a CI step (`PASS`); the owner may skip when the title check is enough (see Commit rule) |
| TOOL-07 | [05-tooling.md](../../audit/checks/05-tooling.md#tool-07--local-guard-against-commits-to-a-protected-branch) | Adds a `pre-commit` guard in the same manager that names every protected branch (see [Branch guard](#branch-guard)) |

## Preconditions

- The shared procedure in `SKILL.md` applies: [Stage 3](../SKILL.md#stage-3-apply) (state read first, drift first,
  worktree, one item at a time) and [Stage 4](../SKILL.md#stage-4-close-the-theme) (engine re-check, gate, ending).
- If the owner skipped the commit-convention finding, write only the hook chain.
- T1 done: the formatter and linter verbs exist, with a changed-files form
  ([`define-command-surface`](define-command-surface.md), [`configure-quality-tools`](configure-quality-tools.md)). A
  hook calls those verbs; it never defines its own commands.
- Preferences read, when present: `format.mass_reformat` (a `no` means hooks check changed files only, never the
  full tree), `lint.mode`, `layout.command_runner`, `hooks.manager`, `commit.convention`, `commit.tool`,
  `hooks.protected_branches`.
- **Drift** ([Stage 3](../SKILL.md#stage-3-apply), step 2): a finding saying "no hook manager" can be stale; look for
  `lefthook.yml`, `.pre-commit-config.yaml`, `.husky/`, `.githooks/` and `core.hooksPath` on the current default branch.
  A `TOOL-06` `PARTIAL` names which half is missing: "only in a local hook" needs the CI step, "only in CI" needs
  the local stage. Keep the half that exists and add the other with the same tool and type list.

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
3. **Commit rule** (skip when already skipped in the state file). One tool, run in both places, so the two
   cannot disagree. Detect first: keep a tool the repository already runs in either place. Otherwise recommend by
   stack (preference `commit.tool`). Versions checked 2026-11-09 (npm registry, PyPI, GitHub API); re-check when
   applied.

   | Stack | Tool | Local `commit-msg` stage | CI step (over the commits the pull request adds) |
   |---|---|---|---|
   | Node with a root manifest | commitlint (`@commitlint/cli` 21.2.4, 2026-10-18), a dev dependency | `.husky/commit-msg`: `npx --no -- commitlint --edit "$1"` | `npx commitlint --from "$BASE" --to "$HEAD" --verbose` |
   | Python | commitizen (4.19.3, 2026-10-24), or gitlint (0.19.1, 2023-03-10) when the repository already uses it | pre-commit hook `commitizen` (or `gitlint`) with `stages: [commit-msg]` | `cz check --rev-range "$BASE..$HEAD"` (or `gitlint --commits "$BASE..$HEAD"`) |
   | Mixed, Java, Node with no root manifest, or no profile | a commit-lint script in the repository ([template](#commit-lint-script-template)) | lefthook `commit-msg` stage, or `.githooks/commit-msg`, running the script with `--message-file` | the same script with `--range "$BASE..$HEAD"` |

   conventional-pre-commit (4.5.0, 2026-10-29) checks one message file only, with no range form, so it cannot
   be the CI half; keep it where it exists and run its type list through commitizen or the script in CI.
   The engine sees the CI step by the tool's name, by the same script path in the hook and the workflow, or
   through a runner target (`make commit-lint`, `npm run lint:commits`) whose command runs either.

   | Option | What | Engine reads it as |
   |---|---|---|
   | A. The pull-request title check only | The repository squash-merges, and a CI check (`amannn/action-semantic-pull-request`, v6.1.2, 2026-11-05) rejects a non-conventional title, which becomes the squash commit's subject. Write this in the contributing doc and record the finding `skipped` with that reason | `PARTIAL` (CI only); owner-accepted |
   | B. The commit rule, local and in CI | The tool above in the `commit-msg` stage and as a CI step | `PASS` |
   | C. Both | A and B, with one type list | `PASS`; carries B's costs |

   Recommend B, or C where squash merges and a title check already exist. Only the owner skips; record the
   owner's words.
4. **Protected branches** (`TOOL-07`). The guard names the branches the declared rules protect: the literal
   names in `.github/rulesets/*.json`, `.github/settings.yml` or Terraform (`HYG-11`'s evidence). With no declared
   rules, propose the default branch (`git symbolic-ref refs/remotes/origin/HEAD`) and the integration branch when
   the state or `AGENTS.md` names one. Record the answer as `hooks.protected_branches`. Never guard a branch the
   owner did not confirm.

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
   list it enforces. For B or C: add the config and the `commit-msg` stage, then the CI step for the provider
   (see [Commit rule in CI](#commit-rule-in-ci)), with the same type list as the title rule so they cannot
   disagree. Commit the local stage and the CI step separately, so either reverts alone.
5. **Branch guard** in the same manager (see [Branch guard](#branch-guard)), naming the Inputs 4 branches.
6. **Verify** with a deliberately bad staged file in a scratch worktree (see Verification). Commit config, docs,
   rule and guard separately.

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

### Branch guard

One guard, in the manager the repository already uses, in the `pre-commit` stage. Its message names the fix:
`git switch -c <type>/<topic>` carries the staged change to a new branch. It is a convenience: the server's rules
are the enforcement, and `--no-verify` skips it. Replace `main` and `dev` with the Inputs 4 branches.

| Stack (manager) | Guard |
|---|---|
| Python (pre-commit) | The `no-commit-to-branch` hook of pre-commit-hooks (v6.0.0, 2025-08-09; checked 2026-11-09). Add it to an existing `pre-commit-hooks` entry, or add the entry. Without `--branch` it guards `main` and `master` only |
| Node with a root manifest (Husky) | The shell lines below at the top of `.husky/pre-commit`, before `npx lint-staged` |
| Mixed, Java, Node with no root manifest (lefthook) | A `pre-commit` command, as below. A `pre-push` command does not stop a commit |
| A committed `.githooks/` folder | The shell lines below in `.githooks/pre-commit`, executable, with `core.hooksPath` already set |

pre-commit:

```yaml
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: no-commit-to-branch
        args: [--branch, main, --branch, dev]
```

Husky or `.githooks/pre-commit` (POSIX shell):

```sh
branch="$(git branch --show-current)"
case "$branch" in
  main|dev)
    echo "Do not commit on '$branch'. Run: git switch -c <type>/<topic>, then commit again." >&2
    exit 1
    ;;
esac
```

lefthook:

```yaml
pre-commit:
  commands:
    protected-branch:
      run: >-
        branch="$(git branch --show-current)";
        case "$branch" in main|dev)
        echo "Do not commit on '$branch'. Run: git switch -c <type>/<topic>, then commit again." >&2; exit 1;;
        esac
```

The engine reads the branch names in the guard itself: in the lefthook command's own block, or anywhere in a hook
script. A guard in a script the hook calls is not seen, so keep the guard in the hook.

### Commit rule in CI

The step checks every non-merge commit the pull request adds. It needs the full history (a shallow clone has no
base commit) and must pass, not fail, when there is no base (a new branch). Put it in the workflow that already
runs the gate, in a job of its own.

GitHub Actions. `BASE` covers a pull request, a merge-queue group and a push:

```yaml
  commits:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pinned sha> # the repository's existing checkout pin
        with:
          persist-credentials: false
          fetch-depth: 0
      - name: Check the commit subjects
        env:
          BASE: ${{ github.event.pull_request.base.sha || github.event.merge_group.base_sha || github.event.before }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha || github.event.merge_group.head_sha || github.sha }}
        run: |
          if [[ -z "$BASE" || "$BASE" =~ ^0+$ ]] || ! git cat-file -e "$BASE^{commit}" 2>/dev/null; then
            echo "No base commit to compare with (a new branch); nothing to check."
            exit 0
          fi
          <the CI command from the table, with "$HEAD_SHA" as the head>
```

When the step runs a Node or Python tool, set it up as the gate's other jobs do (`actions/setup-node` and
`npm ci`, or `astral-sh/setup-uv`), at the version the repository already pins.

GitLab CI. Merge-request pipelines carry the base in `CI_MERGE_REQUEST_DIFF_BASE_SHA`:

```yaml
commits:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  variables:
    GIT_DEPTH: "0"
  script:
    - <the CI command from the table, with BASE="$CI_MERGE_REQUEST_DIFF_BASE_SHA" and HEAD="$CI_COMMIT_SHA">
```

Another provider: the same three parts (full history, the pull request's base and head, a pass with no base).

### Commit-lint script template

For the mixed or Java route, or when the owner wants no new tool. A trimmed form of this framework's own
`dev/commit_lint.py`; set `TYPES` to the repository's convention (`commit.convention`) and put the script where
the repository keeps its scripts. Standard library only; needs Python 3.9 or newer.

```python
"""Check that commit subjects follow Conventional Commits: ``type(scope)!: subject``.

    commit_lint.py --range <base>..<head>   every non-merge commit in the range (CI)
    commit_lint.py --message-file <file>    the first line of one message (the commit-msg hook)

Exit 0 when every subject passes, 1 when one fails, 2 on a usage or git error.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

TYPES = ("feat", "fix", "docs", "test", "chore", "ci", "refactor", "perf", "build", "style", "revert")
SUBJECT = re.compile(r"^(?:" + "|".join(TYPES) + r")(?:\([a-z0-9._-]+\))?!?: \S.*$")


def subjects(revision_range):
    out = subprocess.run(
        ["git", "log", "--no-merges", "--format=%h%x00%s", revision_range],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        sys.exit(f"commit_lint: {out.stderr.strip() or 'git log failed'}")
    return [tuple(line.split("\x00", 1)) for line in out.stdout.splitlines()]


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--range", dest="revision_range")
    group.add_argument("--message-file", type=Path)
    args = parser.parse_args()
    if args.message_file:
        lines = [l for l in args.message_file.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
        pairs = [("message", lines[0].rstrip() if lines else "")]
    else:
        pairs = subjects(args.revision_range)
    bad = [(sha, subject) for sha, subject in pairs if not SUBJECT.match(subject)]
    for sha, subject in bad:
        print(f"{sha}: not a Conventional Commits subject: {subject!r}")
    print(f"allowed types: {', '.join(TYPES)}" if bad else f"commit_lint: {len(pairs)} subject(s) checked")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
```

With no Python on the machines (some Java repositories), a POSIX shell hook does the local half, and the CI step
loops over `git log --no-merges --format=%s "$BASE..$HEAD"` with the same pattern:

```sh
#!/bin/sh
# .githooks/commit-msg: the first non-comment line must be a Conventional Commits subject.
subject=$(grep -v '^#' "$1" | head -n 1)
printf '%s\n' "$subject" | grep -Eq '^(feat|fix|docs|test|chore|ci|refactor|perf|build|style|revert)(\([a-z0-9._-]+\))?!?: [^ ]' || {
  echo "commit-msg: not a Conventional Commits subject: $subject" >&2
  exit 1
}
```

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
| TOOL-06 | Option A: the contributing doc names the title check and the state records `skipped` with the owner's reason. Option B or C: the config and the `commit-msg` stage exist; a bad message is refused locally | As stated |
| TOOL-06 (CI) | Option B or C: push a scratch branch with one bad subject and open a draft pull request only with the owner's approval; or run the CI command locally over `<base>..HEAD` | The CI step fails on the bad subject and passes on a clean range; the engine reads `TOOL-06` `PASS` |
| TOOL-07 | In a scratch clone, check out a protected branch (`git switch -c` a local copy named like it is enough), stage a change and run the hook (`pre-commit run no-commit-to-branch`, `lefthook run pre-commit`, or the hook script); then the same on a work branch | Refused on each protected branch with the fix in the message; passes on the work branch; the engine reads `TOOL-07` `PASS` |

The engine reads `TOOL-06` from files only: option A gives `PARTIAL` (CI only) by design.

## Rollback

`git revert` the commits (config, docs, rule each revert alone). Developers run the manager's uninstall
(`lefthook uninstall`, `pre-commit uninstall`; for Husky, `git config --unset core.hooksPath`).

## Do-not-do

- Do not install the hook manager on the owner's machine or add it as a repository dependency without approval.
- Do not run tests, a full lint, a full-tree format or any network call in a hook.
- Do not advise `--no-verify` or add a bypass variable, in the branch guard either.
- Do not re-propose a `skipped` commit-convention finding.
- Do not pick a manager by what looks familiar or by what this framework uses: detect, then recommend by stack.
- Do not duplicate the secret-scanner version: reuse the CI pin.

## State updates

Beyond the shared lines in [Stage 3](../SKILL.md#stage-3-apply) (`in_progress`, the theme rows) and
[Stage 4](../SKILL.md#stage-4-close-the-theme) (the ending):

```bash
python3 implement/tools/progress.py pref set hooks.manager <husky|pre-commit|lefthook|...> \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set commit.tool <commitlint|commitizen|gitlint|script> \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set hooks.protected_branches "main,dev" \
  --workspace <workspace> --phase <phase> --reason "<the owner's words, or: from .github/rulesets/>" --by owner
python3 implement/tools/progress.py skip F-nnn --workspace <workspace> --phase <phase> --by owner \
  --reason "<the owner's words: why the title check is enough>"
python3 implement/tools/progress.py set-status F-nnn done --workspace <workspace> --phase <phase> \
  --commit <sha> --verification-command "test -f <manager config>" --verification-result "present; install documented"
```
