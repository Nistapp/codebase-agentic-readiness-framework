# Agent Governance (`AGT`)

> Follows the anatomy in [`README.md`](README.md). Eleven checks, split across two halves of this file:
> `AGT-01` to `AGT-06` here, `AGT-07` to `AGT-11` in the second half. See
> [Why These Checks §3](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#3-agent-governance-agt)
> for the consequence behind this family: `AGENTS.md` is the only artifact an agent is guaranteed to
> read, so everything the team knows and has not written there is invisible to it.

---

## The A14 rubric (R-16): score content, not presence

`AGT-01`, `AGT-03`, `AGT-04`, `AGT-06`, `AGT-07` and `AGT-09` all read the same canonical file
(`AGENTS.md`, falling back to `CLAUDE.md`) and judge what it says, not merely that it exists. Amendment
A14 — the review's R-16 — governs every one of those rubrics:

- **Score non-inferable instructions,** not restated boilerplate: verified commands, boundary rules
  naming real paths, prohibitions, and conventions that differ from a tool's defaults. A rule an agent
  could derive from the code itself (a generic "write tests" with no project-specific gate) earns nothing;
  a rule it could not derive (which two directories may not import each other, which branch is protected,
  which command the team actually runs) does.
- **The overview is optional.** A project-overview section (DP §5.4 item 1) is welcome but never scored —
  R-16's evidence is that repository overviews do not raise task success, while specific, non-standard
  instructions do. No check in this family penalises a file for lacking one; `AGT-01`'s own minimum-length
  floor does not require overview prose, only that the file is not a stub.
- **A length budget applies, so restating drifts instead of linking is a finding.** The budget is
  **400 lines** (D50): a canonical `AGENTS.md` under that line count that still covers everything this
  family asks for is doing its job; one over it is answered by linking to `docs/` rather than inlining
  more text, which is the project's own style guide's own rule (never restate, link instead). Each check
  below that reads the file for content adds this as its own finding, scored `DEGRADER`, independent of
  that check's own severity and verdict — a file can `PASS` its specific rubric and still carry a
  length-budget finding.
- **The remediation playbook drafts minimal content and asks for a human edit.** `adapt-agents-md`
  (S5.2.3) never fills a section with generic prose; it proposes the shortest sentence that states the
  project's own fact, and nothing in this family's rubrics rewards a playbook-generated file that a human
  has not reviewed.

`AGT-11` (second half) is where A14's "non-inferable" judgment is made directly, because no engine rule
can tell a derivable instruction from a specific one; this section exists so every other check in the
family shares its vocabulary and its length-budget number instead of re-deriving them.

---

## AGT-01 — Instruction file present, canonical, and non-trivial

Why it matters   `AGENTS.md` is the entry point every harness is guaranteed to read; without it an agent
                  infers conventions from whatever code it happens to open first
                  ([greenfield-bootstrap/README.md § 6.1 AGENTS.md](../../../greenfield-bootstrap/README.md#61-agentsmd)).
Severity         BLOCKER
Engine           `AGT-01`. Collects every path that plausibly is an instruction file (the variant table's
                 canonical paths, aliases, overrides and harness patterns), then: no file at all is `FAIL`;
                 a canonical root `AGENTS.md` under 400 characters, or containing a stub marker (`TODO`,
                 `TBD`, `placeholder`, `lorem ipsum`, `<describe...>`, `coming soon`, `fill this in`), is
                 `FAIL`; a mis-cased candidate (`agents.md`, `Agents.MD`, ...) is `FAIL` (case-sensitive
                 filesystems will not find it); content that lives only in vendor-specific files with no
                 canonical root file is `PARTIAL`; an override file beside the canonical one
                 (makes it inert for one harness) is `PARTIAL`. Distrust a `FAIL` on length alone when the
                 file is short but entirely non-inferable (rare, but possible for a very small repository);
                 verify by reading the file and judging the A14 rubric directly rather than the character
                 count.
Method           automated
Look for         The file itself: open `AGENTS.md` at the repository root (index query first if the index
                 tool surfaces the file list; direct read otherwise). Check its line count against the
                 400-line budget separately from the engine's own verdict.
Rubric           PASS: `AGENTS.md` exists at the repository root in canonical case, is not shadowed by a
                 harness override in the same directory, is at least 400 characters, and contains no stub
                 marker.
                 PARTIAL: the file exists but is mis-cased, is shadowed by an override, or instruction
                 content lives only in vendor-specific files with no canonical root file.
                 FAIL: no instruction file exists anywhere in the repository, or the only candidate is a
                 stub (under 400 characters, or carrying a stub marker).
                 NOT_APPLICABLE: never — every repository can have a root instruction file.
                 UNKNOWN when: a candidate file exists but cannot be read (encoding, permissions).
Evidence to cite A `file` evidence item citing `AGENTS.md` (or the mis-cased/override/vendor path a finding
                 names), with the stub marker or character count in `note` when that is the reason.
                 The length-budget finding (A14) cites the same file with `note` giving its line count
                 against 400.
Absence proof    A FAIL for "no instruction file exists" records a `glob` search entry for each basename
                 class the engine's variant table checks (canonical, aliases, overrides, harness patterns)
                 with its scope and a `0` hit count.
Remediation      `adapt-agents-md`
Pitfalls         A file that is long enough and free of stub markers can still fail A14's real test
                 (non-inferable content) — `AGT-01`'s own rubric is a floor, not the content judgment;
                 `AGT-11` is where specificity is actually scored. A repository that only has a user-level
                 harness config naming `AGENTS.md` (no file on disk at all) still fails this check: `IDX-01`
                 is about index registration, not instruction content, and the two must not be conflated.

## AGT-02 — Component coverage by instruction files

Why it matters   Monorepos have different rules per component; a single root file forces one component's
                  conventions onto another
                  ([Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `AGT-02`. A single-root repository (no declared components beyond the root) is `PASS` by
                 construction — there is nothing to cover. For a multi-component repository, each declared
                 component (depth-1, from the facts tool's `components` section) is covered when
                 `<component>/AGENTS.md` exists, directly or among the paths the variant table already
                 classified as instruction files. Distrust a `FAIL` when the facts tool's component list is
                 itself incomplete (a monorepo the detector did not recognise, Q-logged against `facts.py`
                 if so) — verify by listing the repository's top-level directories directly.
Method           automated
Look for         The facts tool's `components` section first; a direct directory listing of the repository
                 root as a cross-check when a component's boundary is not obvious from the facts alone.
Rubric           PASS: every declared component has its own `AGENTS.md` (ratio 1.0), or there are no
                 declared components beyond the root.
                 PARTIAL: some but not all declared components have one (ratio strictly between 0 and 1).
                 FAIL: no declared component has one (ratio 0, with at least one component to cover).
                 NOT_APPLICABLE: never for a multi-component repository; a single-root repository is scored
                 `PASS`, not `NOT_APPLICABLE`, so the ratio stays visible in the summary.
                 UNKNOWN when: the component list itself cannot be established (facts tool unavailable and
                 no agent-level directory survey was done either).
Evidence to cite A `file` evidence item for each component path checked, present or absent, with
                 `note` stating which; or an `index_query` item citing the facts tool's component listing.
Absence proof    A FAIL or PARTIAL lists a `glob` search entry for `<component>/AGENTS.md` for every
                 uncovered component, each with a `0` hit count.
Remediation      `adapt-agents-md`
Pitfalls         A component directory that has its own `CLAUDE.md` or another alias but no canonical
                 `AGENTS.md` still counts as covered here (the check follows the variant table's own
                 classification) — do not re-flag that path as a competing file; that is `AGT-08`'s job,
                 scoped to the canonical-vs-vendor question, not this one's coverage ratio.

## AGT-03 — Documentation contract named

Why it matters   Agents must know where permanent truth lives and what is off-limits, or they treat
                  scratch notes as architecture
                  ([greenfield-bootstrap/README.md § 5.2 Templates & Guides](../../../greenfield-bootstrap/README.md#52-templates--guides)).
Severity         DEGRADER
Engine           `AGT-03`. Reads the entry instruction file (canonical, else `CLAUDE.md`) for three
                 mentions: `docs/` (or the bare word "docs"), `STYLE_GUIDE.md`, and the scratch-workspace
                 name (`artefacts/` or `artifacts/`). Missing any is `PARTIAL`; missing all three with no
                 instruction file to read at all is the engine's `UNKNOWN` (it defers the absence finding
                 to `AGT-01`), not `FAIL`. Distrust a `PARTIAL` when the project uses a different canonical
                 scratch-directory name by deliberate, documented convention — verify the file actually
                 states an equivalent contract under its own name before counting it missing.
Method           automated
Look for         The instruction file's documentation section (A14's non-inferable test: does it name this
                 project's actual canonical docs home, not a generic "see our wiki").
Rubric           PASS: the file names `docs/` as the documentation home, `docs/STYLE_GUIDE.md` as the
                 authoring rules, and the scratch-workspace directory as off-limits scratch, each on its
                 own line.
                 PARTIAL: at least one but not all three is named.
                 FAIL: none of the three is named (and the file itself exists and is non-trivial — if not,
                 `AGT-01` already covers the absence).
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file exists to read (`AGT-01` is `FAIL` or `UNKNOWN` already).
Evidence to cite A `file` evidence item per element found, citing the instruction file and the matching
                 line number, with `note` naming which of the three it satisfies.
Absence proof    A FAIL or PARTIAL names, for each missing element, the line-search pattern tried (the
                 `grep` tool, the element's pattern, the instruction file as scope, `0` hits).
Remediation      `adapt-agents-md`
Pitfalls         A file that links to `docs/STYLE_GUIDE.md` only from a table of contents, with no sentence
                 stating it is canonical, still passes the engine's textual match — the agent should
                 independently judge whether the mention actually states the contract (A14) rather than
                 accept any appearance of the three strings as sufficient.

## AGT-04 — Definition of done stated

Why it matters   Docs must change in the same change set as the code they describe, or specs drift within
                  days
                  ([greenfield-bootstrap/README.md § 5.2 Templates & Guides](../../../greenfield-bootstrap/README.md#52-templates--guides)).
Severity         DEGRADER
Engine           `AGT-04`. Looks for a line containing "same changeset" or "same change set" with, within
                 three lines either side, one of the documentation triggers (public interface, observable
                 behaviour, architecture, ADR, documentation, docs). Both present and tied together is
                 `PASS`; the change-set phrase present but untied to any trigger, or absent entirely, is
                 `FAIL`. Distrust a `FAIL` when the file states the same rule in different words with no
                 literal "change set" phrase — verify by reading the paragraph around any documentation
                 rule directly.
Method           automated
Look for         The instruction file's documentation or definition-of-done section; read the surrounding
                 paragraph even when the exact phrase is not matched, since the engine's pattern is textual.
Rubric           PASS: a sentence ties a stated documentation trigger (public interface, observable
                 behaviour, architecture, an ADR, or documentation itself) to updating docs in the same
                 change set.
                 PARTIAL: not used by this check (the engine's own outcome is binary; an agent who finds the
                 rule stated in different words but unambiguously present overrides to PASS with a reason,
                 rather than inventing a PARTIAL the catalogue does not define for this check).
                 FAIL: no such sentence exists, or the change-set phrase is present without naming a
                 documentation trigger.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file exists to read.
Evidence to cite A `file` evidence item citing the instruction file and the line with the change-set
                 phrase (when found), or the line of an agent-found equivalent sentence when overriding.
Absence proof    A FAIL records a `grep` search for the change-set pattern and, separately, for each
                 documentation-trigger word, each with its hit count, scoped to the instruction file.
Remediation      `adapt-agents-md`
Pitfalls         The engine's pattern is textual and narrow by design (DP's own calibration note on similar
                 checks): a well-written rule using synonyms the pattern misses is a real PASS that the
                 agent must catch by reading, not a tooling gap to shrug off as UNKNOWN.

## AGT-05 — Seven verbs named

Why it matters   The agent needs the sanctioned verification path stated, or it invents one (`npx vitest`
                  where the project uses something else), diverging from what CI actually runs
                  ([greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs)).
Severity         DEGRADER
Engine           `AGT-05`. Shares its verb resolver with `CMD-01`, so the two checks never disagree:
                 `PASS` only when the instruction file names every framework verb as a whole token (not
                 `format` inside `format:check`) **and** every named verb resolves on a runner manifest.
                 Names complete but resolution incomplete, or the reverse, is `PARTIAL`. With no runner
                 manifest at all, a complete name list is `PARTIAL` (resolution evidence is unavailable, not
                 negative) and an incomplete one is the engine's `UNKNOWN`, deferring to `CMD-01`'s
                 missing-runner finding. Distrust a result when the repository defines verbs through a
                 runner this engine does not yet resolve (check `04-command-surface.md`'s own Engine notes
                 for the runner's coverage) before accepting a `PARTIAL` as the file's fault.
Method           automated
Look for         The instruction file's command-surface section; `04-command-surface.md`'s own evidence for
                 whether each named verb actually resolves, since this check and `CMD-01` must agree.
Rubric           PASS: all seven verbs (`format`, `format:check`, `lint`, `typecheck`, `test`, `check`,
                 `security`) are named in the instruction file and each resolves on a runner.
                 PARTIAL: verbs are named but at least one does not resolve, or vice versa, or all are named
                 with no runner manifest present to resolve against.
                 FAIL: verbs are both incompletely named and incompletely resolved, with a runner manifest
                 present.
                 NOT_APPLICABLE: never — every repository has a command surface, even an empty one.
                 UNKNOWN when: no runner manifest exists and the name list is also incomplete (`CMD-01` owns
                 the missing-runner finding in that case).
Evidence to cite A `file` evidence item citing the instruction file's command-surface table or list, and a
                 `command` evidence item for each verb's resolution (shared with `CMD-01`'s own evidence
                 where the two checks cite the same resolution).
Absence proof    A FAIL or PARTIAL names each missing or unresolved verb explicitly in the finding
                 statement; a verb named but unresolved records the runner command that was tried and its
                 exit code as a `command` evidence item.
Remediation      `adapt-agents-md` (for naming); `define-command-surface` (for resolution, S5.2.1) when the
                 gap is in the runner, not the instruction file.
Pitfalls         A verb named with a different spelling than the catalogue's (`typecheck` written as
                 `type-check`) is a real miss, not a false negative to excuse — the spec fixes the spelling
                 per runner ([`spec/command-surface.md`](../../../spec/command-surface.md)), and the
                 instruction file must use it.

## AGT-06 — Architectural boundaries declared

Why it matters   Boundary rules must be stated, not inferred, or edits cross module lines nothing ever
                  wrote down
                  ([greenfield-bootstrap/README.md § 6.1 AGENTS.md](../../../greenfield-bootstrap/README.md#61-agentsmd)).
Severity         DEGRADER
Engine           `AGT-06`. Scans the instruction file for lines carrying a boundary-context word (`must`,
                 `never`, `only`, `boundary`, `module`, `owns`, `import`, `depend`, `layer`, `allow`, `deny`,
                 `exclude`, `separate`, `isolate`, ...) alongside a path token that resolves to a real file
                 or directory prefix in the repository. Two or more such confirmed boundary rules is `PASS`;
                 one is `PARTIAL`; none is `FAIL`. Distrust a `FAIL` when the boundary is stated with a path
                 pattern the engine's token matcher does not parse (a glob, a backtick-free bare word) —
                 verify by reading the architecture section directly for rules the pattern missed.
Method           automated
Look for         The instruction file's architectural-boundaries section; confirm each cited path actually
                 exists in the repository (a rule naming a renamed or deleted directory is not a real
                 boundary rule, whatever the engine's textual match says).
Rubric           PASS: at least two boundary rules each name a path that exists in the repository.
                 PARTIAL: exactly one such rule exists.
                 FAIL: no boundary rule names an existing path.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file exists to read.
Evidence to cite A `file` evidence item per confirmed boundary rule, citing the instruction file, the line
                 number, and the matched path in `note`.
Absence proof    A FAIL or PARTIAL records, for the gap, that the boundary-context words were searched
                 (`grep`, the context pattern, the instruction file as scope) with the hit count of lines
                 that matched the context but named no real path.
Remediation      `adapt-agents-md`
Pitfalls         A path token that is real but incidental (mentioned in a sentence with boundary vocabulary
                 by coincidence, not as a stated rule) inflates the engine's count — the agent confirms each
                 match is actually a rule before accepting a borderline `PASS` or `PARTIAL` on its face.

## AGT-07 — Do-not-do / deny rules present

Why it matters   Explicit prohibitions work; implicit ones do not — an agent that is never told "never
                  weaken a test" will weaken one
                  ([Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `AGT-07`. Finds the prohibitions section by its heading (one of `never`/`do not`/`don't`/
                 `must not`/`prohibit`/`forbidden`/`off-limits`, or `❌`; the same heading-detection logic
                 `CON-01` and `CON-02` share, so this family and `CON` cannot drift on what counts as a
                 heading). No such section at all is `FAIL`. Inside the section, each line carrying a
                 prohibition word is checked against four concerns — tests, generated files (including
                 `artefacts/`/`artifacts/` and build output), the default branch, secrets — and the first
                 line to match each concern is recorded; covering all four is `PASS`, some is `PARTIAL`,
                 none is `FAIL`. Distrust a `FAIL` on heading detection when the project uses a heading the
                 pattern does not word-match (a bare "Rules" heading whose first line is a prohibition) —
                 verify by reading for a list of explicit prohibitions regardless of its heading text.
Method           automated
Look for         The prohibitions section itself; for each of the four concerns, whether the stated rule
                 is specific to this project (A14) rather than a generic restatement ("don't break things").
Rubric           PASS: a prohibitions section exists and covers all four concerns (tests, generated files,
                 the default branch, secrets) with an explicit rule for each.
                 PARTIAL: a prohibitions section exists but covers only some of the four.
                 FAIL: no prohibitions section exists, or one exists but covers none of the four.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file exists to read.
Evidence to cite A `file` evidence item per covered concern, citing the instruction file, the matching
                 line, and the concern it satisfies in `note`.
Absence proof    A FAIL or PARTIAL names each uncovered concern and records a `grep` search for that
                 concern's pattern scoped to the prohibitions section (or the whole file, when no section
                 heading was found), with its hit count.
Remediation      `add-deny-rules` (D4: this playbook writes only the prohibitions section, nothing else in
                 `AGENTS.md`)
Pitfalls         A prohibition stated outside a dedicated heading (scattered through prose) is real
                 governance but the engine's section-finder will not see it — read the whole file once
                 before accepting a `FAIL` that rests only on heading absence.

## AGT-08 — No competing instruction files, and the reach matrix is stated

Why it matters   `AGENTS.md`, `CLAUDE.md` and `.cursorrules` disagreeing is obeyed as ambiguity, not
                  flagged as a defect — inconsistent behaviour across harnesses, with no way to trace why
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         DEGRADER
Engine           `AGT-08`. Classifies every instruction-shaped path the variant table knows: vendor-only
                 files with no canonical counterpart are competitors (`FAIL`); a pair where one file
                 shadows another for the same harness (only one is ever loaded) is a shadowed pair
                 (`PARTIAL` per pair); and, when a canonical file or a competitor exists but some known
                 harness's own instruction path is never reached by anything present, that is a reach gap
                 (`COSMETIC`, `PARTIAL`). No findings at all is `PASS`. Distrust a competitor finding when
                 the vendor file is a deliberate, documented one-line pointer at the canonical file (A14
                 accepts a pointer; it is only a true competitor when it carries independent rules) —
                 verify by reading the vendor file's content, not just its presence.
Method           automated
Look for         Every instruction-shaped path present (the variant table's classification); for each
                 vendor-only file found, whether it is a pointer or an independent rule set.
Rubric           PASS: no vendor-only competitor exists, no shadowed pair exists, and either every known
                 harness is reached or the file states which harnesses it does not reach.
                 PARTIAL: a shadowed pair exists, or a reach gap exists while a canonical file or a
                 competitor is present, with no vendor-only competitor.
                 FAIL: at least one vendor-only file carries independent rules with no canonical file
                 reconciling it.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction-shaped path of any kind exists (`AGT-01` already owns that
                 absence).
Evidence to cite A `file` evidence item per competitor, shadowed pair (both paths) or reach-gap tool name.
Absence proof    A `FAIL` for "no canonical file reconciling it" records that `AGENTS.md` was searched for
                 (`glob`, `AGENTS.md`, repository root, `0` hits).
Remediation      `adapt-agents-md`
Pitfalls         A vendor file that merely restates the canonical file's rules (not a pointer, but an exact
                 copy) is still a competitor in spirit — restated rules drift, per the project's own style
                 guide — even though the engine's classifier may not distinguish a stale copy from a
                 current one; the agent reads the vendor file's content against the canonical one's current
                 text before accepting a `PASS` here.

## AGT-09 — Branch and release boundary declared

Why it matters   Agents must know whether they may tag, release or push, or one triggers a release it had
                  no authority to cut
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         DEGRADER
Engine           `AGT-09`. Looks for one line naming the branch model (`branch`/`branches`/`branching`/
                 `main`/`dev`/`trunk`) and one naming the release boundary (`tag`/`release`/`publish`/
                 `deploy`/`push`); both present is `PASS`, one is `PARTIAL`, neither is `FAIL`. Distrust a
                 `PARTIAL` or `FAIL` when the project states the rule as a flat prohibition elsewhere
                 (`AGT-07`'s own default-branch concern, "never push to main") that this check's narrower
                 word list does not independently recognise as the release half — verify by reading
                 whether the two facts (which branches exist, what an agent may not do with them) are both
                 actually stated anywhere in the file, even split across sections.
Method           automated
Look for         The instruction file's git-conventions section; cross-reference `AGT-07`'s own evidence
                 for the default-branch prohibition, since the two checks can both be satisfied by the
                 same sentence read two ways.
Rubric           PASS: the file states which branches exist and whether an agent may tag, release, publish,
                 deploy or push.
                 PARTIAL: only one of the two halves is stated.
                 FAIL: neither half is stated.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file exists to read.
Evidence to cite A `file` evidence item for each half found, citing the instruction file and the matching
                 line.
Absence proof    A FAIL or PARTIAL records a `grep` search for the missing half's pattern, scoped to the
                 instruction file, with its hit count.
Remediation      `adapt-agents-md`
Pitfalls         "We only have `main`" is a complete branch-model statement for a trunk-based project —
                 do not demand a multi-branch model where the project deliberately has none; the rubric
                 asks only that the fact be stated, not that it be elaborate.

## AGT-10 — Instruction indirection resolved

Why it matters   A rule the agent is told to "read elsewhere first" is only as reliable as the harness's
                  own willingness to follow that pointer — an unconfigured deferral is a rule that may
                  never load
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         DEGRADER
Engine           `AGT-10`. Reads harness configuration this project can parse without a third-party parser
                 (`.aider.conf.yml`'s `read:`, `.codex/config.toml`'s instruction-file keys,
                 `.gemini/settings.json`'s `contextFileName`, `opencode.json`'s `instructions`) for pointers
                 at files that do not exist (`FAIL`, one finding per broken pointer); separately, scans the
                 entry file for a deferral phrase ("read X first", "before you start, see Y") naming a real
                 file that no harness configuration already names (`FAIL`: loading depends on the agent
                 choosing to follow the pointer, not on configuration). No broken pointer and no
                 unconfigured deferral is `PASS`. Distrust a `FAIL` on deferral when the harness in use
                 reads the entry file in full regardless of pointers (so the deferral is redundant, not
                 risky) — verify which harness the user actually runs before treating every deferral
                 phrase as a gap.
Method           automated
Look for         Harness configuration files for named instruction targets; the entry file's own text for
                 deferral phrasing naming another file.
Rubric           PASS: no configured pointer names a missing file, and no deferral phrase in the entry file
                 names a file left unconfigured.
                 PARTIAL: not used by this check (the engine's outcome is binary per gap; an agent
                 confirming a harness reads the full file regardless overrides a `FAIL` to `PASS` with a
                 reason, rather than inventing a `PARTIAL`).
                 FAIL: a configured pointer names a file that does not exist, or the entry file defers to a
                 file no configuration names.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file exists to read and no harness configuration exists
                 either.
Evidence to cite A `file` evidence item citing the configuration file and the missing target (for a broken
                 pointer), or the entry file and the deferral line plus the file it names (for an
                 unconfigured deferral).
Absence proof    A PASS on the deferral half, when no deferral phrase is found at all, needs no search
                 recorded (there is no absence being claimed); a FAIL always cites the specific line, so no
                 separate absence proof applies to this check beyond the evidence itself.
Remediation      `adapt-agents-md`
Pitfalls         The deferral pattern is deliberately narrow (calibrated against two real repositories) so
                 that ordinary citations — "see `package.json` for versions" — are not flagged as risky
                 indirection; do not widen the agent's own reading of "defers to" beyond genuine
                 "read this before you act" phrasing, or every well-cross-referenced file starts failing.

## AGT-11 — Instructions are specific and not inferable

Why it matters   This is where A14 (above) is judged directly: a file full of generic, inferable advice
                  costs inference time for no benefit, which is R-16's own finding
                  ([Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           none — no deterministic rule can tell a derivable instruction from a specific one; this is
                 the one check in the family with `method: agent` and no `engine_id`. Status in the
                 catalogue is `planned` until this rubric exists; this leaf makes it exist.
Method           agent
Look for         Read the canonical instruction file (and every per-component one `AGT-02` found) end to
                 end. Classify each non-heading, non-blank, non-table-separator line (the same rule-line
                 definition `AGT-01`'s triviality check uses) into one of two buckets:
                 - **Specific:** the line states a fact an agent could not derive from reading the code —
                   a verified command, a boundary rule naming a real path, a prohibition, or a convention
                   that differs from the ecosystem's own default (the four categories A14 names).
                 - **Generic:** the line restates something either inferable from the code itself (a
                   standard test-running instruction with no project-specific gate) or a general software
                   engineering maxim with no project-specific content ("write clear code", "keep functions
                   small").
                 For every line classified specific, confirm it against the repository directly: a cited
                 command resolves, a cited path exists, a cited convention is observably true of the code.
Rubric           PASS: at least 80% of rule lines are specific (by the count above) and every specific line
                 checked resolves against the repository; no overview section exceeds roughly a fifth of
                 the file (A14: the overview is optional and must not dominate).
                 PARTIAL: between 50% and 80% of rule lines are specific, or one or more specific lines
                 fail to resolve against the repository.
                 FAIL: fewer than 50% of rule lines are specific, or the file reads as a largely unedited
                 copy of the framework's own template with no project-specific substitutions.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file exists to read (`AGT-01` already owns that absence).
Evidence to cite An `index_query` or `file` evidence item for each line sampled, with `note` stating the
                 bucket (specific/generic) and, for a specific line, the confirmation performed (command
                 resolved, path exists, convention observed) or its failure.
Absence proof    A FAIL or PARTIAL cites the count of rule lines classified generic as a `grep`-style tally
                 (tool `grep`, pattern "rule line", scope the instruction file, hits = the generic count),
                 so the ratio in the verdict is traceable to a number, not an impression.
Remediation      `adapt-agents-md`
Pitfalls         Counting lines is a proxy, not the goal (DP §5.2's own warning about the rubric being the
                 lever for consistency): a short file that is entirely specific must not be penalised for
                 having "too few" lines to sample confidently, and a long file padded with specific-sounding
                 but unverifiable claims (a boundary rule naming a path that was since deleted) must not
                 pass just because its language matches the specific bucket's shape. Always verify, never
                 just classify.
