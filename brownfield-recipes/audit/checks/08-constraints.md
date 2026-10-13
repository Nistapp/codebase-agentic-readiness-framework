# Constraints (`CON`)

> Follows the anatomy in [`README.md`](README.md). Four checks, all `method: automated`. See
> [Why These Checks §9](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#9-constraints-con)
> for the consequence behind this family: Constraint Engineering is what bounds an agent's blast radius,
> and Phase 1 establishes the initial lists. Every check here reads against
> [decision 0001](../../../spec/decisions/0001-constraint-artifact.md): **the deny list is the
> prohibitions section of the instruction file** — the section whose heading says what an agent must
> not do ("Do Not Do" is the template's own heading; "Never", "Prohibited", "Forbidden" and "Deny" are
> accepted too). There is no separate allow list; what an agent *may* change is the architectural
> boundaries ([REQ-SH-010](../../../spec/readiness-requirements.md#req-sh-010--architectural-boundaries-declared)),
> and the deny list only narrows that. Harness-native enforcement (Claude Code permission rules,
> `.cursorignore`, and the like) is optional hardening the audit never scores.
>
> **An absence is reported once, by the check that owns it.** With no instruction file, `AGT-01`
> reports it and `CON-01`/`CON-02` are `UNKNOWN`. With no prohibitions section, `AGT-07` reports it and
> `CON-01`/`CON-02` are `UNKNOWN` again. Do not re-raise either absence as a `CON-01`/`CON-02` finding
> of its own — read `AGT-01`'s and `AGT-07`'s verdicts first, in that order, before judging this family.

---

## CON-01 — Allow/deny artifact present

Why it matters   An agent cannot respect a boundary that exists only in someone's head; the deny list
                  must be a concrete, written artifact, not an unstated expectation
                  ([Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         BLOCKER
Engine           `CON-01`. Reads the prohibitions section decision 0001 names and collects every code
                 span in it. A span is a path or pattern when it has no command syntax (no shell
                 operator, flag or quote character) and holds a slash, a glob character or a dot, or is
                 a bare word that exists on disk — the scan also checks the literal path against the
                 filesystem directly, because the scan itself leaves out `node_modules/`-style excludes
                 that a deny list often names. At least one named path or pattern that matches something
                 in the repository is `PASS`. Paths are named but none matches anything is `PARTIAL`. No
                 path or pattern is named at all is `FAIL`. No instruction file, or no prohibitions
                 section, is `UNKNOWN` — `AGT-01` or `AGT-07` already owns that finding. Distrust a
                 `FAIL` or `PARTIAL` when the section's prose clearly names a path but without
                 backticks, so no code span exists to read — verify by reading the section's actual
                 text, not just its code spans.
Method           automated
Look for         Every code span inside the prohibitions section specifically, not the section's prose;
                 for each span that reads as a path or pattern, whether it matches a real file or
                 directory of the repository.
Rubric           PASS: the prohibitions section names, in a code span, at least one path or pattern that
                 matches a file or directory of the repository.
                 PARTIAL: the section names paths or patterns in code spans, but none of them matches
                 anything in the repository.
                 FAIL: the section names no path or pattern in any code span.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file exists, or the file has no prohibitions section —
                 either absence is `AGT-01`'s or `AGT-07`'s own finding, not this check's.
Evidence to cite A `file` evidence item per named code span, citing the instruction file, line and the
                 span's text; for `PASS`, cite only the spans that matched something real.
Absence proof    A FAIL cites the prohibitions section's own heading line as the evidence that it was
                 read in full and found to name no code span at all.
Remediation      `add-deny-rules`
Pitfalls         A path written in prose without backticks ("do not touch the migrations folder") is
                 invisible to this check even though a human reader would understand it perfectly — the
                 artifact decision 0001 names is specifically a code-span list, so credit nothing from
                 prose alone; recommend adding the backticked form rather than treating the prose as
                 already satisfying the check.

## CON-02 — Test directories protected

Why it matters   Tests are the safety net; an agent that may freely edit them is not actually gated by
                  them, and can make a failure disappear instead of fixing it
                  ([shared/Overview.md § Principles](../../../shared/Overview.md#principles)).
Severity         BLOCKER
Engine           `CON-02`. Locates every test directory (a path segment named `test`, `tests` or
                 `__tests__`; `spec`/`specs` are feature-specification folders, not tests, and are never
                 counted), then checks whether the prohibitions section's code spans name each one, or
                 a pattern that covers it, read as an ignore entry (a leading `/` anchors to the root, a
                 leading `**/` means any depth, a bare name with no inner slash covers that name at any
                 depth). Every test directory named is `PASS`; some is `PARTIAL`; none is `FAIL`. No
                 instruction file or no prohibitions section is `UNKNOWN` (owned by `AGT-01`/`AGT-07`),
                 and so is a repository with no test directory at all — there is nothing to protect.
                 Constraint files, `.gitignore` rules and CI text are never read as evidence here; they
                 are not the artifact decision 0001 names. Distrust a `FAIL` when the test suite lives in
                 a directory name this fixed set does not recognise (Ruby's own `spec/` is the clearest
                 case, deliberately excluded since the framework's `specs/` folder means something
                 different) — verify by reading the project's own test configuration for where its
                 suite actually lives before treating the gap as real.
Method           automated
Look for         Every test directory the scan's directory-name rule finds; the prohibitions section's
                 code spans, read as ignore-style patterns, against each one.
Rubric           PASS: the prohibitions section names, in code spans, every test directory found.
                 PARTIAL: it names some test directories but not all.
                 FAIL: it names none of the test directories found.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file or no prohibitions section exists (owned elsewhere),
                 or no test directory exists in the repository at all.
Evidence to cite A `file` evidence item citing the prohibitions section's heading line and, for a FAIL
                 or PARTIAL, the full list of test directories found but not named.
Absence proof    A FAIL or PARTIAL names every uncovered test directory explicitly in the finding
                 statement, citing the prohibitions section as the evidence it was read in full and
                 found not to cover them.
Remediation      `add-deny-rules`
Pitfalls         A Ruby repository with tests only under `spec/` reads as `UNKNOWN`, not `FAIL` — this is
                 decision 0001's own documented trade (a directory-name rule that cannot distinguish a
                 test `spec/` from the framework's feature-specification `specs/`), not a defect to
                 route around by crediting `spec/` as a test directory here.

## CON-03 — `artefacts/` excluded from the index and agent reads

Why it matters   Scratch notes must not become context an agent treats as source of truth; a tracked or
                  unignored scratch directory pollutes every session that follows
                  ([greenfield-bootstrap/README.md § 6.2 Agent Scratchpad](../../../greenfield-bootstrap/README.md#62-agent-scratchpad--artefacts)).
Severity         DEGRADER
Engine           `CON-03`. Checks the scratch spellings (`artefacts/`, `artifacts/`) and the agent/tool
                 state directories (`.codebase-memory/`, `.opencode/`, `.agentic-tdd/`): any of these
                 that exist must be matched by an ignore rule, and nothing under any of them may be
                 tracked by git. A tracked file under any of these roots is `FAIL` outright, regardless
                 of ignore coverage — the rule did not keep it out, however it reads now. With nothing
                 tracked, full ignore coverage of every present root is `PASS`; partial coverage, or a
                 present root covered by no rule at all, is `FAIL`; no candidate root present at all is
                 `PASS` by construction. When coverage is confirmed but git cannot report the tracked
                 set (no git, or the command failed), the untracked half degrades to `UNKNOWN` rather
                 than being inferred — the same degradation `SEC-01` and `DOC-03` use. Distrust a `FAIL`
                 when a broader ignore rule covers the scratch path incidentally (`*.tmp/` happening to
                 match `artefacts/`) — the engine credits this as a real `PASS`, so do not second-guess
                 it as "too lucky to count"; conversely, verify the ignore rule's own anchoring if a
                 `PASS` looks surprising, since the engine's ignore matching is a documented subset, not
                 full gitignore semantics.
Method           automated
Look for         `.gitignore` (and any other ignore file the engine's loader reads) for a rule covering
                 each present candidate root; `git ls-files` (or the equivalent) for whether anything
                 under any of them is tracked.
Rubric           PASS: no candidate root exists, or every root that exists is matched by an ignore rule
                 and nothing under any of them is tracked.
                 PARTIAL: ignore rules cover some present roots but not all, with nothing tracked under
                 any of them.
                 FAIL: any file under a candidate root is tracked by git, regardless of ignore coverage;
                 or a present root is matched by no ignore rule at all.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: every present root is covered by an ignore rule but git could not report
                 the tracked set.
Evidence to cite A `file` evidence item citing the matching `.gitignore` line (for PASS/PARTIAL
                 coverage), or the tracked paths found (for FAIL), or a `command` evidence item for the
                 `git ls-files`-equivalent call that could not run (for UNKNOWN).
Absence proof    A FAIL for "no ignore rule covers it" records the ignore-rule search performed (tool
                 `grep`, the root's name as pattern, every ignore file as scope, `0` hits); a FAIL for a
                 tracked path cites the path directly.
Remediation      `add-deny-rules`. [`DOC-03`](03-documentation-contract.md) judges the same
                 [REQ-SH-018](../../../spec/readiness-requirements.md#req-sh-018--scratch-and-tool-state-directories-ignored)
                 from the documentation-contract side; add `artefacts/` (or the project's own scratch
                 directory name) to `.gitignore`, and `git rm --cached` anything already tracked under
                 it, to resolve both at once.
Pitfalls         `CON-03` and `DOC-03` share one requirement but read different evidence (`CON-03` adds
                 the tool-state roots `.codebase-memory/`, `.opencode/` and `.agentic-tdd/`, which
                 `DOC-03` does not check) — a `PASS` on one is not proof of a `PASS` on the other; read
                 both before concluding the requirement is fully met.

## CON-04 — Draft allow/deny emitted

Why it matters   The scan knows what is dangerous in *this* repository; without it, every adoption starts
                  from a generic template that fits nobody and an agent (or a human) has to rediscover
                  the same paths by exploring
                  ([Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         COSMETIC
Engine           `CON-04`. Not a scored check (`catalogue.json`: `scored: false`) — a drafting aid that
                 still returns a `CheckOutcome` like every other check. It scans the repository for six
                 categories of dangerous path (secrets, migrations, generated code, tests, infrastructure
                 as code, production configuration) and, only when the operator passed `--emit-baseline`,
                 writes a Markdown draft (`do-not-do.draft.md`) beside the report: one entry per
                 category, canonical patterns plus whatever the scan actually observed, in code spans
                 ready to paste under the instruction file's prohibitions heading. Without the flag it
                 is `UNKNOWN`; it is also `UNKNOWN`, never `FAIL`, if writing the draft would land inside
                 the target (ADR-0002) or would silently replace an existing draft without `--force`. A
                 clean emission is `PASS`.
Method           automated
Look for         The draft file itself, `do-not-do.draft.md`, written beside the report's `--out`
                 location; if it was not emitted, whether `--emit-baseline` was passed to the run at all.
Rubric           PASS: the draft was written to `do-not-do.draft.md` beside the report.
                 PARTIAL: not used by this check (the engine's outcome is binary: the draft was written
                 or it was not, for a documented reason).
                 FAIL: not used by this check — a run that cannot or should not write the draft (no
                 flag, a target path, an existing file with no `--force`) is `UNKNOWN`, not a defect.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: `--emit-baseline` was not passed; the resolved output path would land
                 inside the target; or a draft already exists and `--force` was not given.
Evidence to cite A `file` evidence item citing the written draft's path (for PASS), or a `command`/`file`
                 evidence item citing the reason emission was skipped (for UNKNOWN).
Absence proof    Not applicable — this check never records a FAIL, so no absence search applies; an
                 UNKNOWN's `summary` states the specific reason (no flag, in-target path, or an existing
                 file) directly, which is the audit trail in place of a search.
Remediation      none — `CON-04` is itself a remediation input, not a defect with a fix. Its draft is
                 `add-deny-rules`'s deterministic starting point, not something `add-deny-rules` fixes
                 on this check's behalf.
Pitfalls         **Open point, carried from S2.6 (settled here as D51, not implemented in this leaf):**
                 the recipe's own launcher, `tools/engine.py`, does not pass `--emit-baseline` through to
                 the engine today, so `CON-04` reports `UNKNOWN` ("draft not emitted") on every recipe
                 run and no `do-not-do.draft.md` exists for `add-deny-rules` (S5.3.3) to read. The chosen
                 fix is a launcher option: `tools/engine.py` gains a passthrough flag that forwards to
                 the engine's own `--emit-baseline`, requested by the audit recipe's Stage 2 the first
                 time it runs the engine (S3.5.3.1). Rejected: the facts tool (`facts.py` never runs the
                 engine, and the draft needs the engine's own category scan, not a second one) and
                 having the model write the candidate list itself (decision 0001's own "Alternatives
                 Considered" already rejects this — the scan is deterministic and tested, so a model
                 should not rediscover the same paths). This is a tool change and is not made in this
                 leaf; it is deferred to `S3.5.3.1`.
