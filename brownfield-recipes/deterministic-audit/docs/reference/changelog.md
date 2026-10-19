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
| `2026-10-19.1` | 2026-10-19 | 55 | S4.4.2.1: `AGT-07`'s heading-word detector gap, found on Digital-Assistant-Server (S4.3.3, `D62`) — a prohibitions heading with no trigger word now also qualifies when its own body already reads as a do-not list |
| `2026-10-15.3` | 2026-10-15 | 55 | S3.6.4: real-defect fixes found by the Digital-Assistant-SDK dry run (S3.6.3) — `TOOL-03`'s comment-intolerant JSON parse, `EXEC-04`'s truncated identifier capture, and `EXEC-02`'s undersized content-read cap — plus `CI-03`'s npm staged-publish fix (`3fb090d`, S3.6.1), which moved a verdict without a revision bump at the time |
| `2026-10-11.1` | 2026-10-11 | 55 | S2.6: the Makefile reader, the false positives the self-audit found, and the constraint pack |
| `2026-09-28.13` | 2026-09-28 | 54 | The engine as it was imported into this repository |

---

## `2026-10-19.1`

`AGT-07`'s heading-word detector gap, the first fix from the rubric-tightening loop (S4.4.2.1). Found on
Digital-Assistant-Server (S4.3.3): its `AGENTS.md` has a real prohibitions section headed "Security &
Safety Guardrails" — five "must not" bullets covering secrets only — but the heading carries none of
`AGT-07`'s trigger words, so the engine reported `FAIL` ("no prohibitions section") instead of `PARTIAL`.
KC accepted the S4.3.3 agent's override to `PARTIAL` as correct (`D62`), reversing an earlier
`S4.3.2.2` judgment call that had kept the engine's literal `FAIL`.

### Verdicts that can move

| Check | Before | Now | Why |
|---|---|---|---|
| `AGT-07` | `FAIL` when the prohibitions heading carries no trigger word, however many prohibition lines sit beneath it | `PARTIAL`/`PASS` when that heading's own direct body has at least 3 lines matching the prohibition-line vocabulary (`never`, `do not`, `must not`, …) | `prohibitions_section` (`audit/rules/checks/_common.py`), shared by `AGT-07`, `CON-01` and `CON-02`, only recognised a heading by a trigger word in its title. A heading's own direct body (to the next heading of any level, so a nested subsection's content is not borrowed) now also qualifies it. |
| `CON-01` | `UNKNOWN` ("no prohibitions section to read") whenever `AGT-07`'s heading match failed | Scored normally once a section is found by either route | `CON-01` reads `prohibitions_section`'s result directly; it was never wrong on its own, only starved of a section to read. |
| `CON-02` | Same `UNKNOWN`, same cause | Scored normally | Same fix, same shared helper. |

### The example report

`examples/digital-assistant-sdk/` is not regenerated: Digital-Assistant-SDK's `AGENTS.md` has no
prohibitions-shaped heading at all (re-run and confirmed directly against `d44bbc672`), so `AGT-07`,
`CON-01` and `CON-02` are unchanged there. The moved verdicts above are confirmed against
Digital-Assistant-Server directly (`7f351b0`, read-only, output outside the target) rather than a
committed example, matching `S4.3.2.2`'s own corrected sheet exactly: `AGT-07` `PARTIAL`, `CON-01`
`PASS`, `CON-02` `FAIL`.

### Not changed

The scoring weights, the verdict credits, the report schema (v2) and the instruction-variant table. The
`ruleset_hash` is unchanged: it hashes the catalogue and the variant table, neither of which this fix
touches — only the revision string, which this page's own docstring (`audit/__init__.py`) says to bump
for exactly this kind of detector change.

---

## `2026-10-15.3`

Three real defects found by a live, interactive audit run against Digital-Assistant-SDK (S3.6.3), recorded in
`artefacts/audit-runs/digital-assistant-sdk/digital-assistant-sdk.engine-defects.20261015T041602Z.md`, fixed in
S3.6.4. Also folds in `CI-03`'s fix (`3fb090d`, S3.6.1), which changed a verdict but was never given its own
revision bump — this revision is the first to carry it.

### Verdicts that can move

| Check | Before | Now | Why |
|---|---|---|---|
| `TOOL-03` | `PARTIAL` for a `tsconfig.json`/`jsconfig.json` with a `//` or `/* */` comment (or a trailing comma a stripped comment leaves behind) | `PASS` when `strict`/`checkJs` is actually `true` | `_json_true` parsed the file with plain `json.loads`, which TypeScript's own parser does not require; it now strips comments and trailing commas first. |
| `EXEC-04` | A missing key named one character short, e.g. `UDA_LOG_LEVELN` for a reference to `process.env.UDA_LOG_LEVELNumber` | The full identifier | The extraction regexes capped their capture group at `[A-Z0-9_]*` (upper-case and digits only), so a mixed-case identifier was truncated at its first lower-case run. The class now also accepts lower-case after the leading upper-case character. |
| `EXEC-02` | `PARTIAL` ("consistency unverified") for any lockfile over 256 KiB, even a consistent one | Verified normally up to 2 MiB | `CONTENT_READ_LIMIT` (`audit/scan.py`) was 256 KiB; a real `package-lock.json` at 514 KiB tripped it. Raised to 2 MiB. `NAV-03`'s separate 512 KiB oversized-file threshold is unrelated and unchanged. |
| `CI-03` | `FAIL` for a CI step that runs `npm stage publish` (npm's native staged-publish subcommand) | `PASS` | Already fixed in `3fb090d` (S3.6.1); listed here because that fix never bumped the ruleset revision. |

### The example report

`examples/digital-assistant-sdk/` is regenerated at the same commit as before, `d44bbc672` (clean, `fix/packaging-types-deps`
of Digital-Assistant-SDK). `CI-03`, `EXEC-02` and `TOOL-03` move `FAIL`/`PARTIAL` → `PASS`; `EXEC-04` stays `FAIL` but
now names `UDA_LOG_LEVELNumber` instead of the truncated `UDA_LOG_LEVELN`. Blockers are unchanged at 6 (none of the
moved checks were blocking). Phase-1 score: `0.6352` → `0.6721`.

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
| `AGT-05` | `PARTIAL`, "not resolved: format:check", for a Makefile that defines it | `PASS` | It asks whether the seven verbs resolve on a runner, so it moves with the reader that `CMD-01` uses. This repository's own report showed it. |
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
- The engine replaces an output only with `--force`. The existing-file check looked at the JSON path alone, so
  `--format both`, the default, replaced the Markdown beside the report, and `--emit-baseline` replaced the `CON-04`
  draft, without asking. Every output is now checked before the scan writes anything, a refusal names each file that
  exists and exits 1 with a message rather than a traceback, and a refused run leaves no partial report or new draft.
  `--format md` writes nothing and is not refused. A draft path inside the target is not checked: none is written there.
- A check the engine's ruleset had blocked arrives in a recipe draft as `UNKNOWN`, scored as the catalogue scores it
  ([engine mapping](../../../schema/SCHEMA.md)). No check is blocked now.

### The example report

`examples/digital-assistant-sdk/` is regenerated: the engine at this revision, run read-only on Digital-Assistant-SDK at
`d44bbc672`, a clean commit of `fix/packaging-types-deps`. The previous report scanned a dirty working tree of `dev`
(`748797977412`, 2026-10-06), which no longer exists, so it cannot be reproduced. Twenty verdicts differ between the
two reports, and they are the repository's: the engine at `2026-09-28.13`, run on `d44bbc672`, gives the same verdict
for all 69 checks as the engine now does. What the engine changed on that repository:

| What | `2026-09-28.13` | `2026-10-11.1` |
|---|---|---|
| `SEC-02` | `FAIL`: 16 lines in 10 files | `FAIL`: 6 lines in 4 files. Of the six files that dropped out, four held property reads, `process.env` and other expressions; two held a ten-character test literal (`'mock-token'`), which the old rule read as twelve because it counted the quote and the comma after it |
| Blockers | 12 | 6 (the six `SEC-02` findings) |
| Phase-1 score | 0.6513 | 0.6352 (`CON-01` is scored, and `UNKNOWN` here because `AGENTS.md` has no prohibitions section) |
| Scoreable checks | 54 | 55 |
| `AGT-08` finding id | `AGT-08` | `AGT-08:harness-reach` |

### Not changed

The scoring weights, the verdict credits, the report schema (v2) and the instruction-variant table. The
`ruleset_hash` changes because the catalogue does: `CON-01` is scored and implemented.

---

## `2026-09-28.13`

The engine as it was imported into this repository (S0.3). `git log` shows the import merge and, behind it, the original
commits.
