# Documentation Contract (`DOC`)

> Follows the anatomy in [`README.md`](README.md). Four checks, all `method: automated`. See
> [Why These Checks §4](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#4-documentation-contract-doc)
> for the consequence behind this family: without a declared, canonical home for permanent knowledge,
> documentation scatters and nothing is canonical — an agent cannot tell a settled architecture decision
> from a stale scratch note.

No check in this family has an MVP implementation playbook yet (`catalogue.json`'s `playbooks` is empty
for all four): `add-docs-contract` and `add-adr-scaffold` are backlog items (DP §5.5's starting map; the
roadmap's backlog §5 item 3), not among the seven playbooks `S5.2`–`S5.3` ship. Until one exists, each
check's **Remediation** says what to create directly; a human applies it, or a later roadmap step adds the
playbook.

---

## DOC-01 — `docs/` exists

Why it matters   `docs/` is the declared home for permanent documentation; without it on day one,
                  documentation has nowhere canonical to start
                  ([greenfield-bootstrap/README.md § 5.1 Diátaxis Framework](../../../greenfield-bootstrap/README.md#51-diátaxis-framework)).
Severity         DEGRADER
Engine           `DOC-01`. Any Markdown file (`.md` or `.markdown`, case-insensitive) anywhere under
                 `docs/` is `PASS`. No such file but the directory exists on disk is `PARTIAL` — the
                 engine checks the filesystem directly here, because an empty directory with nothing
                 tracked is otherwise invisible to the inventory. Neither existing is `FAIL`. `UNKNOWN` is
                 never used: the directory's state is always knowable without git or a probe. Distrust a
                 `PARTIAL` only if the repository keeps documentation entirely outside `docs/` by a
                 deliberate, differently named convention — verify by reading the instruction file for
                 where it says permanent documentation actually lives (`AGT-03`'s own evidence).
Method           automated
Look for         A directory listing of `docs/`; if markdown is absent, confirm the directory's on-disk
                 presence directly rather than trust the inventory alone for an empty folder.
Rubric           PASS: at least one Markdown file exists anywhere under `docs/`.
                 PARTIAL: `docs/` exists on disk but holds no Markdown file.
                 FAIL: no `docs/` directory exists at all.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — the engine treats this as always decidable.
Evidence to cite A `file` evidence item citing `docs/` (for the PARTIAL/FAIL cases) or one representative
                 Markdown path under it (for PASS), with the file count in `note`.
Absence proof    A FAIL records a `glob` search entry for `docs/**/*.md` (and `.markdown`) scoped to the
                 repository root, with a `0` hit count.
Remediation      No MVP playbook yet (backlog: `add-docs-contract`). Create `docs/` with, at minimum, a
                 project overview and `docs/STYLE_GUIDE.md` (`DOC-02`).
Pitfalls         A repository whose only documentation is a root `README.md` is correctly `FAIL` here —
                 a root README is not `docs/`, and conflating the two hides a real gap.

## DOC-02 — `docs/STYLE_GUIDE.md` exists

Why it matters   Agents need authoring rules they can cite instead of restating per page, or rules get
                  restated and drift
                  ([greenfield-bootstrap/README.md § 5.2 Templates & Guides](../../../greenfield-bootstrap/README.md#52-templates--guides)).
Severity         DEGRADER
Engine           `DOC-02`. Exact presence of `docs/STYLE_GUIDE.md` is the primary evidence; the entry
                 instruction file (canonical, else `CLAUDE.md` — the same reader `AGT-03` uses) naming
                 `STYLE_GUIDE.md` anywhere in its text is the second half. Present and named is `PASS`;
                 present but unnamed is `PARTIAL`; absent is `FAIL` regardless of what the instruction file
                 says. `AGT-03` passing is not a precondition — the two checks read independently and may
                 disagree about the "named" half if `AGT-03`'s broader match (any of three terms) differs
                 from this check's narrower one (the literal filename). Distrust a `FAIL` on a path
                 variant (`docs/style-guide.md`, a different case) — verify by listing `docs/` directly for
                 a near-miss filename before accepting the absence.
Method           automated
Look for         The exact path `docs/STYLE_GUIDE.md`; the instruction file's text for the literal string
                 `STYLE_GUIDE.md`.
Rubric           PASS: `docs/STYLE_GUIDE.md` exists and the instruction file names it.
                 PARTIAL: the file exists but no instruction file names it.
                 FAIL: `docs/STYLE_GUIDE.md` does not exist, at that exact path.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — presence is always knowable from the inventory.
Evidence to cite A `file` evidence item citing `docs/STYLE_GUIDE.md`, plus a second citing the instruction
                 file and the line naming it, when present.
Absence proof    A FAIL records a `glob` search for `docs/STYLE_GUIDE.md` exactly, with a `0` hit count;
                 a PARTIAL's "unnamed" half records a `grep` search for the literal string `STYLE_GUIDE.md`
                 scoped to the instruction file, also with a `0` hit count.
Remediation      No MVP playbook yet (backlog: `add-docs-contract`). Create `docs/STYLE_GUIDE.md` and name
                 it from the instruction file (ties into `AGT-03`).
Pitfalls         A project that names a *different* canonical style document (not literally
                 `STYLE_GUIDE.md`) by a project-specific convention still fails this check as written — the
                 catalogue scores the framework's own filename, not an equivalent concept under another
                 name; note that distinction in the finding rather than silently overriding to PASS.

## DOC-03 — `artefacts/` exists and is ignored

Why it matters   Transient scratch must be separable and off-limits, or an agent reads work-in-progress
                  notes as the current, settled requirement
                  ([greenfield-bootstrap/README.md § 6.2 Agent Scratchpad](../../../greenfield-bootstrap/README.md#62-agent-scratchpad--artefacts)).
Severity         DEGRADER
Engine           `DOC-03`. No scratch directory (`artefacts/` or `artifacts/`) present anywhere, on disk or
                 in the inventory, is `PASS` ("no scratch directory in use" — there is nothing to get
                 wrong). Any path under the directory that git tracks is `FAIL` outright, independent of
                 ignore rules (the directory's purpose is defeated the moment one file is committed).
                 Otherwise: the directory must be matched by an ignore rule (the engine's own subset
                 matcher, `audit.ignore` — anchoring and `**` approximated, not a full `.gitignore`
                 implementation); unmatched is `FAIL`. Matched, with git able to confirm nothing is
                 tracked, is `PASS`; matched but git cannot report the tracked set at all is `UNKNOWN`
                 (the same degradation `SEC-01` uses when git is unavailable — absence of evidence is not
                 a pass). Distrust a `FAIL` on the ignore-rule match when the project uses a `.gitignore`
                 construct the engine's approximated matcher does not parse (a negated pattern, a complex
                 brace expansion) — verify by testing `git check-ignore` on a sample path directly.
Method           automated
Look for         `.gitignore` (and any other ignore file the engine's loader reads) for a rule covering the
                 scratch directory; `git ls-files` (or the equivalent) for whether anything under it is
                 tracked.
Rubric           PASS: no scratch directory exists anywhere, or one exists, is matched by an ignore rule,
                 and nothing under it is tracked.
                 PARTIAL: not used by this check (every outcome the engine reaches is PASS, FAIL or
                 UNKNOWN; an agent who finds a genuine partial state — some scratch content tracked,
                 the rest correctly ignored — reports it as the FAIL it already is under "any tracked path
                 fails outright", not as a softer PARTIAL the catalogue does not define here).
                 FAIL: a scratch directory exists and either something under it is tracked, or no ignore
                 rule covers it at all.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: the directory is matched by an ignore rule but git cannot report the tracked
                 set (no git, or the command failed).
Evidence to cite A `file` evidence item citing the scratch directory and the matching `.gitignore` line
                 (for PASS), or the tracked paths found (for FAIL), or a `command` evidence item for the
                 `git ls-files`-equivalent call that could not run (for UNKNOWN).
Absence proof    A FAIL for "not matched by any ignore rule" records the ignore-rule search performed
                 (tool `grep`, the directory name as pattern, `.gitignore` as scope, `0` hits).
Remediation      No MVP playbook yet (backlog: this is also `CON-03`'s concern, REQ-SH-018 is shared
                 between the two checks). Add `artefacts/` (or the project's own scratch directory name)
                 to `.gitignore`, and `git rm --cached` anything already tracked under it.
Pitfalls         A directory ignored by a broad rule that also happens to ignore the scratch path
                 (`*.tmp/`, `build/**`) is a real PASS by this check's own logic — do not demand a rule
                 that names the scratch directory specifically if a broader one already covers it; the
                 engine's matcher already accounts for this and the agent should not second-guess a
                 genuine match.

## DOC-04 — ADR directory and index

Why it matters   Architectural decisions need a location and a registry, or the rationale lives only in
                  chat and pull requests, and agents re-litigate settled decisions
                  ([greenfield-bootstrap/README.md § 5.2 Templates & Guides](../../../greenfield-bootstrap/README.md#52-templates--guides)).
Severity         COSMETIC
Engine           `DOC-04`. Looks for `docs/architecture/adrs/` or `docs/adr/` holding at least one file
                 matching the numbered-ADR filename pattern (3–4 digits, a hyphen, a slug, `.md`). No such
                 directory is `FAIL`; a directory with no numbered entry is `PARTIAL`; entries with no
                 index (a `README.md`/`index.md`/`_index.md` beside them, or the parent directory's own
                 README) is `PARTIAL`; an index that lists some but not all entries (matched by filename or
                 the first four characters of the ADR number) is `PARTIAL`; every entry listed is `PASS`.
                 Distrust a `PARTIAL` on "index omits some" when the index links to entries by a title that
                 does not embed the filename or number fragment the engine's matcher looks for — verify by
                 reading the index for a link to each ADR's actual path.
Method           automated
Look for         `docs/architecture/adrs/` first (the convention this project's own docs use), else
                 `docs/adr/`; the index file beside the entries, or the architecture README that lists them
                 instead.
Rubric           PASS: a numbered-ADR directory exists, holds at least one entry, and an index lists every
                 entry.
                 PARTIAL: the directory exists with entries but no index, or an index that omits some, or
                 the directory exists with no numbered entry at all.
                 FAIL: no ADR directory (at either known location) exists.
                 NOT_APPLICABLE: never — `REQ-SH-019` is a `SHOULD`, but the catalogue still scores it as
                 `DOC-04`, at `COSMETIC` severity, so it is never excused as not applicable.
                 UNKNOWN when: never — directory and file presence are always knowable from the inventory.
Evidence to cite A `file` evidence item per unlisted entry (for the omits-some case), or the directory path
                 alone (for the no-directory or no-entry cases).
Absence proof    A FAIL records a `glob` search for `docs/architecture/adrs/*.md` and `docs/adr/*.md`, each
                 with a `0` hit count.
Remediation      No MVP playbook yet (backlog: `add-adr-scaffold`). Add `docs/architecture/adrs/` with
                 `NNNN-short-title.md` entries and a `README.md` index that links each one.
Pitfalls         `COSMETIC` severity means this check never blocks a Phase-1 score on its own, but a
                 missing ADR index is still worth recording precisely — cosmetic is a severity, not a
                 licence to skip the evidence and absence-search rules this family shares with every
                 other.
