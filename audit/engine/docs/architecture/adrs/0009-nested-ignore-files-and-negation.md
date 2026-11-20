# 0009. Nested Ignore Files and Negation

## Context

The walk and four checks ask whether an ignore rule covers a path. The walk asks it to decide what the audit
reads. `DOC-03` and `CON-03` ask whether the scratch directory is kept out of git; `SEC-01` and `SEC-03` ask
whether the ignore rules cover a secret shape. A simple matcher fails all of them in four ways.

1. **A nested `.gitignore` is invisible.** This repository keeps `artefacts/.gitignore` containing `*`, with
   `!.gitignore` and `!README.md`. No root rule names `artefacts/`. Both checks would report "matched by no ignore
   rule", and the walk would read every scratch file.
2. **`!` never re-includes.** With the line dropped, `SEC-03` credits a shape that a later `!server.crt` opens
   again. The walk drops `.env.example` beside `.env.*` and `!.env.example`, so `EXEC-04` misses the template.
3. **An anchored rule never matches.** `/.claude/worktrees/` read as a plain glob misses `.claude/worktrees`. The
   walk then reads each agent worktree, a full copy of the tree, as part of the repository.
4. **A tracked file is part of the repository.** Git keeps tracking a file an ignore rule covers. A walk that drops
   it hides force-added key material and committed build output from every check.

The operator's remedy, `--exclude`, makes it worse: excluding `artefacts/**` also removes the nested `.gitignore`
from the inventory, so the rule that ignores the directory is not read.

## Decision

**One scoped matcher in `audit/ignore.py`, for the walk and the checks.**

1. **`load_scoped_rules(root, nested)`** reads the root ignore files (`.gitignore`, `.cbmignore`, `.cursorignore`,
   `.aiderignore`, `.rooignore`) and every nested `.gitignore` it is given. Each rule carries `base` (the directory of
   its file), `negated` and `dir_only`. Rules are ordered shallowest file first and lines in file order.
2. **`decide(rel, rules, is_dir=False)`** applies them in git's order: the last matching rule wins, so a deeper file
   and a later line override; an ignored parent directory hides everything under it, and a `!` rule cannot bring a
   file back out of one. The result says whether the path is ignored, which rule decided, and `reincluded` when a `!`
   rule overrode an earlier ignore rule for that path.
3. **The glob subset** is interpreted: a leading `/` or an inner `/` anchors the rule to its file's directory, a
   trailing `/` makes it directory-only, `*` and `?` stop at `/`, `**` crosses it, `[...]` is a class.
4. **The walk** (`build_inventory` in `audit/scan.py`) starts from the root files. It adds each nested
   `.gitignore` as it enters that directory (`load_ignore_file`). It asks `decide_path` for each path, since the
   parents are already decided. A file git tracks is never skipped by a rule. The walk enters an ignored
   directory only when git tracks a file in it. There it reads only the tracked files. `Inventory.ignored_dirs`
   names each directory it did not enter, and the report lists them. `HARD_EXCLUDE_DIRS` and `--exclude` still
   apply to tracked files, except `dist/` and `build/` (`TRACKED_ONLY_DIRS`): the walk enters them to reach the
   files git tracks, and only those, so `EXEC-05` and `NAV-03` see committed build output. When git cannot report
   the tracked set, the rules alone decide and every `HARD_EXCLUDE_DIRS` folder stays out.
5. **Which nested files the checks read.** `scoped_rules` (`audit/rules/checks/_common.py`) takes the nested
   `.gitignore` files in the inventory and the ones git tracks. The tracked ones are read even under `--exclude`: the
   operator took a directory's files out of the evidence, not the rule that decides whether the directory is
   ignored. A file under a set-aside directory scopes nothing outside it and is left out.
6. **What the checks do with it.**
   * A directory counts as kept out when it is ignored itself or a new file in it would be
     (`directory_decision`); the summary names the ignore file that decided.
   * A tracked file under a scratch root is sanctioned, not scratch, when it is the directory's own `.gitignore` or
     a `!` rule re-includes it beside an ignoring rule (`is_sanctioned_member`). Every other tracked member still
     fails `DOC-03` and `CON-03`.
   * `SEC-01` and `SEC-03` probe each shape through `decide`, so a `!` that re-includes the probe uncovers the shape
     and a `!` for another name does not. A rule with a leading `/` still reads "root-anchored only".
   * The tracked files a rule also matches are one list, `tracked_and_ignored`: the in-scope tracked set passed
     through `decide`, never `git ls-files -ci`. `SEC-01` fails on an env-like name in it and `SEC-03` on key
     material (issue #12).
7. **The parser stays the authority.** The matcher never runs `git check-ignore`. When git cannot report the tracked
   set the checks stay `UNKNOWN`.

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| A second, simpler matcher for the walk (`fnmatch` on the path and base name, `!` dropped, no anchoring) | It read git-ignored worktrees and build output and dropped re-included templates, so verdicts came from files outside the repository and missed files inside it. Two matchers also gave two answers to one question. |
| Build the inventory from `git ls-files` plus `git ls-files --others --exclude-standard` | Exact on a work tree, but it needs git, and the verdict would depend on the host's git version and global excludes file. A second code path would still be needed for a bare directory. |
| Shell out to `git check-ignore -v` | The same dependence on git and the host's configuration. Left as an optional confirmation for a later revision. |
| Drop tracked files that an ignore rule covers | Git tracks them, so they are part of the repository a reader and a CI run see; hiding them hides committed key material and build output. |
| Exempt `artefacts/` from `--exclude` | Special-cases one name. Reading the tracked ignore files is general and says why. |
| Treat every tracked file under a scratch root as allowed when the root is ignored | It would hide `artefacts/plan.md` force-added past the rule, which is the defect `DOC-03` exists to find. |
| Read nested ignore files of every kind | `.cbmignore` and the other names are tool files read at the root; only `.gitignore` nests in git. |

## Consequences

### Positive

* The walk, `DOC-03`, `CON-03`, `SEC-01` and `SEC-03` share one matcher, so they cannot disagree about one path.
* Untracked, ignored runtime data (databases, caches, worktrees) stays out of the inventory and the evidence.
* A re-included template such as `.env.example` and a force-added tracked file stay in the inventory.
* The report names the directories the walk skipped, so a surprising verdict can be explained.

### Negative / Trade-offs

* What the walk reads moved on every target with anchored, nested or negated rules or tracked ignored files;
  that change carried its own ruleset revision.
* Only the documented subset is interpreted: no `\` escapes beyond `\#` and `\!`, no character-class ranges beyond
  what `re` reads, no core.excludesFile or `.git/info/exclude`. A rule outside the subset reads as no match.
* A tracked file under another `HARD_EXCLUDE_DIRS` name (`vendor/`, `node_modules/`, `target/`) is not walked.
  `EXEC-05` does not see a committed `target/` or a vendored tree.
