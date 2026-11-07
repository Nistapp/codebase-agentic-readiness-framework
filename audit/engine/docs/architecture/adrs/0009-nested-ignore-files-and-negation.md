# 0009. Nested Ignore Files and Negation

* **Status:** Accepted
* **Date:** 2026-11-05
* **Last reviewed:** 2026-11-05
* **Deciders:** [@nistapp]

---

## Context

ADR-0006 gave the engine one ignore matcher, a documented subset kept exactly as the walk had it: root ignore
files only, `!` lines dropped, anchoring and `**` not interpreted. Four checks ask a different question from the
walk. `DOC-03` and `CON-03` ask whether the scratch directory is kept out of git; `SEC-01` and `SEC-03` ask
whether the ignore rules cover a secret shape. Two defects followed.

1. **A nested `.gitignore` was invisible.** This repository keeps `artefacts/.gitignore` containing `*`, with
   `!.gitignore` and `!README.md`. No root rule names `artefacts/`, so both checks reported "matched by no ignore
   rule" (issue #22), and the tracked `README.md` read as scratch committed by mistake (issue #12).
2. **`!` never re-included.** Dropping the line was documented, but it made `SEC-03` credit a shape that a
   later `!server.crt` had opened again, and made a deliberate exception look like a defect.

The operator's remedy, `--exclude`, made it worse: excluding `artefacts/**` (as every self-audit does) also removed
the nested `.gitignore` from the inventory, so the rule that ignores the directory was no longer read.

---

## Decision

**Two matchers, one per question.** The walk keeps the ADR-0006 matcher unchanged, so what the scan traverses does
not move. The four checks above use a **scoped matcher** in `audit/ignore.py`:

1. **`load_scoped_rules(root, nested)`** reads the root ignore files (`.gitignore`, `.cbmignore`, `.cursorignore`,
   `.aiderignore`, `.rooignore`) and every nested `.gitignore` it is given. Each rule carries `base` (the directory of
   its file), `negated` and `dir_only`. Rules are ordered shallowest file first and lines in file order.
2. **`decide(rel, rules, is_dir=False)`** applies them in git's order: the last matching rule wins, so a deeper file
   and a later line override; an ignored parent directory hides everything under it, and a `!` rule cannot bring a
   file back out of one. The result says whether the path is ignored, which rule decided, and `reincluded` when a `!`
   rule overrode an earlier ignore rule for that path.
3. **The glob subset** is interpreted: a leading `/` or an inner `/` anchors the rule to its file's directory, a
   trailing `/` makes it directory-only, `*` and `?` stop at `/`, `**` crosses it, `[...]` is a class.
4. **Which nested files.** `scoped_rules` (`audit/rules/checks/_common.py`) takes the nested `.gitignore` files in
   the inventory and the ones git tracks. The tracked ones are read even under `--exclude`: the operator took a
   directory's files out of the evidence, not the rule that decides whether the directory is ignored. A file under a
   set-aside directory scopes nothing outside it and is left out.
5. **What the checks do with it.**
   * A directory counts as kept out when it is ignored itself or a new file in it would be
     (`directory_decision`); the summary names the ignore file that decided.
   * A tracked file under a scratch root is sanctioned, not scratch, when it is the directory's own `.gitignore` or
     a `!` rule re-includes it beside an ignoring rule (`is_sanctioned_member`). Every other tracked member still
     fails `DOC-03` and `CON-03`.
   * `SEC-01` and `SEC-03` probe each shape through `decide`, so a `!` that re-includes the probe uncovers the shape
     and a `!` for another name does not. A rule with a leading `/` still reads "root-anchored only".
6. **The parser stays the authority.** Neither matcher runs `git check-ignore`. When git cannot report the tracked
   set the checks stay `UNKNOWN`, as before.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Change the one matcher for the walk too | It would shift what every check reads, for a question only four checks ask. The walk keeps ADR-0006's behaviour; a later change can move it with its own ruleset bump. |
| Shell out to `git check-ignore -v` | Needs git and a work tree; the engine must answer on a bare directory. It would also make the verdict depend on the host's git version and global excludes file. Left as an optional confirmation for a later revision. |
| Exempt `artefacts/` from `--exclude` | Special-cases one name. Reading the tracked ignore files is general and says why. |
| Treat every tracked file under a scratch root as allowed when the root is ignored | It would hide `artefacts/plan.md` force-added past the rule, which is the defect `DOC-03` exists to find. |
| Read nested ignore files of every kind | `.cbmignore` and the other names are tool files read at the root; only `.gitignore` nests in git. |

---

## Consequences

### Positive

* `DOC-03` and `CON-03` pass for a scratch directory that ignores itself, and name the file that does.
* `SEC-03` honours an exception instead of silently ignoring it.
* The four checks share one matcher, so they cannot disagree about one path.

### Negative / Trade-offs

* There are two matchers until the walk moves. A nested `.gitignore` still does not prune the walk, so an ignored
  directory's contents are in the inventory when they exist on disk.
* Only the documented subset is interpreted: no `\` escapes beyond `\#` and `\!`, no character-class ranges beyond
  what `re` reads, no core.excludesFile or `.git/info/exclude`. A rule outside the subset reads as no match.
* Issue #12 (a tracked file that an ignore rule covers) is answered for the scratch roots only. Issue #22
  (untracked ignored runtime data in evidence) is not touched: the walk still lists such files.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/NNNN-title.md`.

See the [style guide](../../../../../docs/STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
