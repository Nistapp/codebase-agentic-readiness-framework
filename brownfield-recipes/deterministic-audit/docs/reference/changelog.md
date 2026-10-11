# Changelog Reference

> **Audience:** Operators who compare reports, and contributors
> **Source of truth:** `audit/__init__.py` (`__ruleset_revision__`), `audit/rules/registry.py` and the commit history.
> **Status:** Live.

---

A report records the ruleset revision that made it, and a ruleset hash over the catalogue and the instruction-variant
table. Two reports with different revisions were made by different rules, and a verdict can differ for that reason alone.
This page lists what changed between revisions, newest first, and says which verdicts move. The code and its tests are
the record of how; git has the rest.

| Revision | Date | Scoreable checks | What it is |
|---|---|---|---|
| `2026-10-11.1` | 2026-10-11 | 55 | S2.6: the Makefile reader, the false positives the self-audit found, and the constraint pack |
| `2026-09-28.13` | 2026-09-28 | 54 | The engine as it was imported into this repository |

---

## `2026-10-11.1`

The engine fixes of the brownfield-recipes review (S2.6, items R-04 and the self-audit of S0.5). Each change has a
one-defect fixture, and the catalogue (`brownfield-recipes/catalogue.json`) moved from 0.1.0 to 0.2.0 with it.

### Verdicts that can move

| Check | Before | Now | Why |
|---|---|---|---|
| `CMD-01`, `CMD-02` | `FAIL` for a valid Makefile | `PASS` | `format\:check` (the escaped colon), the alias `format-check` and a `check` that lists its prerequisites are read. This repository's own Makefile was the case. |
| `CMD-01` | `PASS` for a Makefile that GNU Make refuses | `FAIL` | An unescaped `format:check:` is a static pattern rule with no `%`; Make stops and no target can run. The finding is `CMD-01:Makefile`, and `CMD-02` to `CMD-04` are `UNKNOWN` and say so. |
| `CMD-01` | `FAIL` on Gradle and Maven for want of verbs | `PASS` or `FAIL` by what the build declares | `formatCheck`, Gradle's `test` and `check`, Maven's lifecycle and the Spotless, Checkstyle and dependency-check goals resolve, in the spelling of [`spec/command-surface.md`](../../../../spec/command-surface.md). A `<goal>` is no longer a verb. `format-check` resolves for pyproject task runners. |
| `CMD-02` | `FAIL` for a Gradle or Maven `check` | `UNKNOWN` | Its dependencies are set by the build's task graph, which the engine does not read. |
| `AGT-01` | `FAIL` when `todo`, `tbd` or `placeholder` was anywhere in the file | `PASS` unless it stands as a marker | A word opening a line (a list number or a heading mark may precede it) or standing in brackets is a stub marker; the word in a sentence is not. |
| `SEC-02` | `FAIL` for `token = match.group(1) or x` in source and for `api_key: "os.environ/NAME"` | `PASS` | A keyword counts only when it is assigned a literal: a quoted string that is not a reference, or, outside source code, a plain unquoted token. |
| `SEC-01`, `DOC-03`, `CON-03`, `EXEC-02` | An excluded path still counted when git tracked it | Left out | `--exclude` reaches the checks that read git's tracked set. |
| `EXEC-02` | `FAIL`, "exists but is not tracked", for a tracked lockfile below the root | `PARTIAL` | Tracked or not is read by the path the lockfile was found at; one below the root is not compared with the root manifest. |
| `EXEC-01` and others | `UNKNOWN` for a project with no manifest | Evaluated | Python is also recognised from its source files, so a standard-library-only project gets the Python checks. `EXEC-02` is `UNKNOWN` for it: it declares no dependencies. |
| `CON-01` | `UNKNOWN`, blocked, weight 0 | `PASS`, `PARTIAL`, `FAIL` or `UNKNOWN`, and scored | It reads the prohibitions section of the instruction file ([decision 0001](../../../../spec/decisions/0001-constraint-artifact.md)). The scoreable count goes from 54 to 55, so every score moves. |
| `CON-02` | A constraint file, ignore rules or CI text could protect the tests | The prohibitions section must name them | Constraint files, ignore rules and CI text are no longer read. `spec` and `specs` are not test directories. |
| `AGT-01`, `AGT-08`, `EXEC-01`, `EXEC-02` | Findings with no path shared one id (`AGT-08` twice on the Server report; `EXEC-02` twice on this repository, one for each ecosystem) | Each has an id of its own | A scope or the file's path follows the check ID (`AGT-08:vendor-files`, `AGT-08:harness-reach`, `AGT-08:CLAUDE.md>AGENTS.md`, `AGT-01:AGENTS.md`, `EXEC-01:node`, `EXEC-02:python`), so the baseline ratchet no longer merges them. Tests hold every fixture's report, and a repository with every ecosystem and every competing file, to unique ids. |
| `AGT-07` | A heading in a code fence made a section | It does not | The section is found by one helper shared with `CON-01` and `CON-02`. |

### Other changes

- `CON-04` writes `do-not-do.draft.md`, a Markdown list to paste under the prohibitions heading, in place of
  `constraints.draft.yaml`. The allow list is gone: there is none.
- `--phase` records the phase in the report's provenance and does nothing else; its help now says so.
- A check the engine's ruleset had blocked arrives in a recipe draft as `UNKNOWN`, scored as the catalogue scores it
  ([engine mapping](../../../schema/SCHEMA.md)). No check is blocked now.

### Not changed

The scoring weights, the verdict credits, the report schema (v2) and the instruction-variant table. The
`ruleset_hash` changes because the catalogue does: `CON-01` is scored and implemented.

---

## `2026-09-28.13`

The engine as it was imported into this repository (S0.3). `git log` shows the import merge and, behind it, the original
commits.
