# Playbook: `adapt-agents-md`

> Theme T7 (`AGENTS.md` and governance). Follows the anatomy in [`README.md`](README.md). Written in IR10.1; to be
> applied and corrected on a Gradle repository (IR10.2) and a multi-component Node repository (IR10.3). Its sibling
> [`add-deny-rules`](add-deny-rules.md) owns the prohibitions section; this playbook owns the rest of the file.

## Goal

The canonical instruction file states this repository's own facts, and only those: the seven verbs as the team runs
them, a single-test command, where documentation lives, when docs change with code, which paths are boundaries,
what an agent may do with branches and releases, which harnesses read the file, and nothing an agent could infer
from the code. Every line is true against the repository, and the file stays within the 400-line budget.

**The rule this playbook enforces: the playbook drafts, the owner edits.** `AGENTS.md` is the owner's voice. Each
finding gets the smallest diff that closes it, proposed and reviewed one at a time. The file is never rewritten
wholesale.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| AGT-01 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-01--instruction-file-present-canonical-and-non-trivial) | Verification: a canonical root `AGENTS.md`, correctly cased, no stub markers, no override file |
| AGT-02 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-02--component-coverage-by-instruction-files) | Verification; a component `AGENTS.md` only when the owner asks (component scoping is a v0.3 item) |
| AGT-03 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-03--documentation-contract-named) | One line each for `docs/`, `docs/STYLE_GUIDE.md` and the scratch directory |
| AGT-04 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-04--definition-of-done-stated) | One definition-of-done sentence tying documentation triggers to the same change set |
| AGT-05 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-05--seven-verbs-named) | The seven verbs named as whole tokens, in the runner's own spelling, annotated with inline comments |
| AGT-06 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-06--architectural-boundaries-declared) | Two or more boundary rules, each naming a path that exists |
| AGT-08 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-08--no-competing-instruction-files-and-the-reach-matrix-is-stated) | The "This file is read by ..." line; vendor pointer files kept and reconciled, never deleted unasked |
| AGT-09 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-09--branch-and-release-boundary-declared) | One release-boundary sentence built from the state and the repository |
| AGT-10 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-10--instruction-indirection-resolved) | A "read X first" deferral becomes an ordinary link, with the must-always rules moved into `AGENTS.md` |
| AGT-11 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-11--instructions-are-specific-and-not-inferable) | Generic text moves to `docs/`; contradicted rules become target state with the exception count; stale lines corrected |
| EXEC-06 | [09-execution-determinism.md](../../audit/checks/09-execution-determinism.md#exec-06--documented-commands-resolve) | Every fenced command in `AGENTS.md` resolves; the one command a finding names is fixed inline |
| TST-04 | [10-tests.md](../../audit/checks/10-tests.md#tst-04--fast-path-documented) | Verification only, when T5 wrote the fenced single-test line; written here when the item sits in T7 |

AGT-07 and the `CON` checks are [`add-deny-rules`](add-deny-rules.md)'s. The rubric that governs the whole family
(score non-inferable content, the overview is never scored, the 400-line budget) is the
[A14 rubric](../../audit/checks/02-agent-governance.md#the-a14-rubric-r-16-score-content-not-presence); read it once
before the first diff.

## Preconditions

- The state file exists and Stage 1 triage is done ([`SKILL.md`](../SKILL.md#stage-1-triage)). Read it first;
  respect every `skipped` item and preference. A finding the owner rejected at triage (for example an AGT-08 finding
  on a `CLAUDE.md` import stub) is never re-proposed, not even as a side effect of another diff.
- **T1 to T6 done or `partial`.** This theme writes what the earlier themes made true: the verbs (T1), the pinned
  environment and the lock regeneration line (T2), the secrets rules (T3), the hooks and CI (T4), the baselines and
  the single-test line (T5), the docs home, style guide and decision log (T6). A fact an earlier theme has not made
  true is not written as if it were; it stays a finding for that theme.
- **Run the drift check first** ([`check_drift.py`](../../docs/reference/tools-cli.md#check_driftpy)). Earlier themes
  edit `AGENTS.md` (T1 the verbs, T5 the fenced test line, T6 the docs line), so a T7 finding is often stale: verbs a
  finding calls "not named" may now be named; a line a finding calls stale may already be fixed. Re-measure every
  claim in the finding statement (line numbers, counts such as "rule contradicted in five services", "not named:
  ...") on the current integration branch. A finding resolved by drift is `done` with the drift as the reason.
- Preferences this playbook reads, when present:

| Key | Effect |
|---|---|
| `agents_md.pointer_section` | Where the readiness pointer and the docs line already sit; keep them there |
| `agents_md.stubs` | `keep` (default) or `delete-asked`: what happens to a vendor pointer file (Inputs 3) |
| `agents_md.deferral` | `inline` (default) or `harness-config`: how a deferral to a second rules file is resolved (Inputs 4) |
| `agents_md.generic_text` | `move-to-docs` (default) or `delete`, per section if the owner chose per section (Inputs 5) |
| `agents_md.contradicted_rules` | `target-state` (default) or `describe-code` (Inputs 5) |
| `agents_md.release_tags` | What an agent may do with tags and releases; feeds the AGT-09 sentence (Inputs 6) |
| `ci.pr_by_agent` | Whether the AGT-09 sentence allows pushing a branch and opening a pull request ([ADR 0003](../../docs/architecture/adrs/0003-push-and-pr-policy.md)); also the ending |
| `docs.agents_line` | T6 already wrote the docs line; AGT-03 then only verifies it |
| `layout.command_runner` | `per-app`: verbs are listed per app, not at the root |
| `format.mass_reformat` | `no` (usual): never reflow or reformat the file to make it shorter |

- **Public/private boundary.** Everything written into an open-source repository's `AGENTS.md` comes from that
  repository. Never copy content, paths, names or values from a private sibling repository or workspace into it.

## Inputs to ask

No tool is installed by this playbook: the instruction file is plain Markdown and the checks are read by the audit
engine. The questions are about text. Ask them per finding, before the diff for that finding.

1. **Order of the diffs.** Default order, smallest risk first: AGT-05 and EXEC-06 (commands), TST-04 (verify),
   AGT-03, AGT-04, AGT-06, AGT-09, AGT-08, AGT-10, AGT-11. The owner may reorder or skip any; a skip goes through
   `progress.py skip` by the owner.
2. **Boundary rules (AGT-06).** Propose two or three rules from the code index (which directory may import which,
   which layer owns persistence, which folder is generated or vendored). The owner picks; never invent a boundary
   the code does not show. If the code index shows no boundary, ask the owner for one or record the item `partial`.
3. **Vendor pointer files (AGT-08, the "ask about stub files" rule).** Default `keep`:
   - A vendor file whose content is only an import or a pointer at `AGENTS.md` (`@AGENTS.md`, "See AGENTS.md")
     stays. It is what gives that harness its reach (Claude Code loads `CLAUDE.md`, not `AGENTS.md`). Add the reach
     line to `AGENTS.md` (Steps 7). Ask before deleting anything; deletion is the owner's choice
     (`agents_md.stubs=delete-asked`) and loses that harness's reach.
   - A vendor file that carries extra rules beside the pointer: offer to move those rules into `AGENTS.md` (move,
     not copy) and ask whether the vendor file then becomes the one-line pointer. A rule that only makes sense for
     that harness (a tool preference, a harness setting) may stay there; say so in the PR.
   - A vendor file with independent rules and no pointer (a true competitor): reconcile its rules into `AGENTS.md`
     and offer the one-line pointer. Never delete it unasked.
4. **A second rules file the instruction file defers to (AGT-10).** Default `inline`: move the rules that must
   always apply (formatting, naming, branch and commit rules not already in `AGENTS.md`) into `AGENTS.md` within the
   budget, and turn the "read X first" line into an ordinary reference link ("Conventions for people: `X`"). The
   second file stays as human reference. Option `harness-config` (name the file in each harness's configuration) is
   offered **only** when the repository already has those harness files; never create a harness file for it.
   Merging the second file wholesale breaks the budget and is not offered.
5. **Generic and contradicted text (AGT-11).** Defaults:
   - Generic text (persona and role-play prompts, general maxims, restated tool defaults) moves to a page under
     `docs/` named in the repository's own convention, with a one-line link from `AGENTS.md`. Nothing the owner
     wrote is lost. Option `delete` is offered per section.
   - A rule the code contradicts becomes **target state**: "New code must X. N existing files do not yet; find them
     with `<command>`." The count is measured, not copied from the finding. Option `describe-code` (reword the rule
     to describe the code as it is) is offered per rule. T7 never edits code to make a rule true.
   - A stale line (a path hint, a claim about ignored or tracked files that no longer holds) is corrected to match
     the repository. When the correct wording depends on an owner decision recorded elsewhere in the state (a file
     tracked on purpose), the line states that decision; it does not change the files.
6. **Release boundary (AGT-09).** Default: one sentence built from facts (Steps 6). The owner reviews the sentence;
   never ask the owner to write it from scratch.
7. **Owner-only values.** None is needed for this playbook. If a step seems to need one (a reviewer name, a
   contact), it belongs to T8; follow the supply / generate-and-review / skip order there.

## Steps

### Generic

1. **Baseline.** Run the drift check. Record: the line count of `AGENTS.md` (and of each per-component file), the
   instruction-shaped files present (the engine's variant table, or list them: `AGENTS.md`, `CLAUDE.md`,
   `GEMINI.md`, `CONVENTIONS.md`, `.cursorrules`, `.cursor/rules/`, `.github/copilot-instructions.md`,
   `.windsurfrules` and similar), the harness configuration files present (`.claude/`, `opencode.json`, `.codex/`,
   `.gemini/`, `.aider.conf.yml`), and the rule lines (non-heading, non-blank, non-table-separator) for AGT-11.
   Re-index with the code index; Steps 4 and 9 need it.
2. **Commands (AGT-05, EXEC-06).** Name each of `format`, `format:check`, `lint`, `typecheck`, `test`, `check`,
   `security` as a whole token in a fenced block, in the runner's own spelling, with an inline `#` comment that names
   the framework verb when the spelling differs. The engine strips the comment before resolving the command
   (EXEC-06) and reads the verb name in it (AGT-05):

   ```bash
   ./gradlew formatCheck            # format:check, read-only
   npm --prefix app run typecheck   # typecheck
   ```

   A verb that does not resolve is T1's ([`define-command-surface`](define-command-surface.md)); do not document a
   verb the runner does not define. For an EXEC-06 finding, fix the one command it names, inline, and re-run the
   engine; do not rewrite the block. Commands that need a precondition (a JDK version, a running stack) say so in
   one line next to the command (`JAVA_HOME` must point at JDK 21); a line T2 deferred to T7 (the pinned runtime, the
   lock regeneration command) is added here if it is missing, verified if it is present.
3. **Single test (TST-04).** If T5 wrote the fenced single-test line, verify it is still fenced and still matches the
   runner. If the item sits in T7, add one: `./gradlew test --tests 'org.example.FooTest'`,
   `npx jest -t '<test name>'` (Jest needs `-t` or `--testNamePattern`; a path alone is not read as a single test),
   `python3 -m unittest tests.test_module -k name`. The framework's own [`AGENTS.md`](../../../AGENTS.md#commands)
   is the worked example.
4. **Documentation contract (AGT-03).** Three facts, each on its own line: `docs/` is the documentation home,
   `docs/STYLE_GUIDE.md` holds the writing rules, the scratch directory (`artefacts/`) is scratch and off-limits as
   a source of truth. T6 usually wrote the first two beside the readiness pointer (`docs.agents_line`); keep them
   there and add only what is missing. If the repository has no scratch directory, the third line says where
   scratch goes, so the rule exists before the folder does.
5. **Definition of done (AGT-04).** One sentence, in the definition-of-done section (create the section only if none
   exists), naming the triggers and the same change set. The framework's own wording is the example:
   "When a change alters a public interface, observable behaviour, the architecture or a decision, update the
   affected documentation and the decision records in the same change set." Name this repository's decision log
   path (`docs/adr/`) if T6 created one.
6. **Release boundary (AGT-09).** Build one sentence from facts, never from a template:
   - the branches that exist: the integration branch (from the state or the branch rule already in the file) and
     the default branch (`git symbolic-ref refs/remotes/origin/HEAD`);
     the branch that receives releases comes from the release workflow's trigger (`on.push.branches`), not from the
     default branch: the two can differ, and the old line "default remote branch is `main`" may be the stale one;
   - whether an agent may push a branch and open a pull request: only when the state records `ci.pr_by_agent=yes`
     ([ADR 0003](../../docs/architecture/adrs/0003-push-and-pr-policy.md)); otherwise it stops at a local branch;
   - that an agent never merges, tags, publishes a release or pushes to the default branch;
   - when a release tool is tracked (`release-please-config.json`, `.releaserc*`, a release workflow), that the
     tool cuts releases.

   Example: "Branch from `dev` and open pull requests into `dev`; `main` receives releases only. An agent may push
   its branch and open a pull request; it never merges, tags, publishes a release or pushes to `main` or `dev`.
   Releases are cut by release-please." Re-check the sentence whenever `ci.pr_by_agent` or
   `agents_md.release_tags` changes. The prohibition half also lands in the prohibitions section through
   [`add-deny-rules`](add-deny-rules.md) (default branch); keep the two consistent, do not state the rule twice in
   different words.
7. **Reach and vendor files (AGT-08).** Add one line near the top of `AGENTS.md`: `This file is read by <harnesses>.`
   Name only harnesses that really reach it: native `AGENTS.md` readers, plus each harness whose vendor file points
   at it (a `CLAUDE.md` that imports `@AGENTS.md` makes Claude Code a reader). The engine takes the line as given; the
   line must be true. Then handle each vendor file per Inputs 3. A shadowed pair or an override file is reported to
   the owner with the harness it affects; do not delete either side unasked.
8. **Deferral (AGT-10).** Find the "read X first" line. Per Inputs 4: list the must-always rules in X that
   `AGENTS.md` does not already state, propose moving them (a diff that adds them to `AGENTS.md` and, if the owner
   agrees, removes them from X, so the rule lives in one place), and turn the deferral into a reference link. Check
   the tree or layout description in X against the repository while there: a stale tree is reported, and fixed only
   if the owner asks (X is not this playbook's file).
9. **Specificity (AGT-11).** Classify every rule line as the check does (specific or generic), and verify every
   specific line against the repository: the command resolves, the path exists, the convention holds in the code.
   Then, per Inputs 5:
   - move each generic block to the `docs/` page and leave one link line;
   - reword each contradicted rule as target state with the measured exception count and the command that finds
     them (a code-index query or a `grep`); count with the code index (`search_graph`) and cross-check with `grep`;
   - correct each stale line.

   Recount the rule lines after the moves and record the ratio in the state note.
10. **Instruction file and components (AGT-01, AGT-02).** Verify: root `AGENTS.md`, exact case, no stub marker, no
    override file beside it. For a multi-component repository, a component `AGENTS.md` is written only when the owner
    asks and the component has rules the root file cannot state; otherwise record AGT-02 as the owner's choice
    (component scoping is a v0.3 item in the spec).
11. **Budget.** Count the lines. Over 400: link instead of inlining (move a long section to `docs/` with a link) and
    record the overage as debt. Never shorten by reflowing or deleting the owner's rules.
12. **Verify and commit.** Re-run the audit launcher on the branch for the touched checks (or the full engine run),
    lint the changed Markdown with the repository's docs lint, and run the repository's gate. Commit per finding
    (one logical change each) so the owner can revert any one alone.

### Gradle and Quarkus

Profile: [`stacks/java.md`](../../stacks/java.md#command-surface-map). Verbs are Gradle task names (`formatCheck` for
`format:check`), always through the wrapper (`./gradlew`); annotate each with the framework verb. The single-test
form is `./gradlew test --tests '<fully.qualified.Class>'` (add `.<method>` for one method). Boundary candidates
come from the package layout: REST resources, services, repositories or entities, and the migration folder
(`src/main/resources/db/migration/`); a "never inject X in Y" rule is the usual contradicted rule, counted with a
code-index query on the injection points. JDK and wrapper preconditions sit next to the commands.

### Node (npm, NestJS, React)

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#command-surface-map). In a per-app layout
(`layout.command_runner=per-app`) list the verbs under each app's heading with `npm --prefix <app> run <verb>` or a
`cd <app>` line, annotated. A verb an app does not have (no `typecheck` in a plain JavaScript app) is stated as such,
not invented. Jest single test: `npx jest -t '<name>'` from the app folder. Boundary candidates: the app folders
themselves (one app never imports another), `src/` versus `test/`, generated clients, and the infrastructure folder.

## Continue on error

- **Over budget:** an `AGENTS.md` over 400 lines after the moves is `partial` with
  `--debt "what=AGENTS.md lines over the 400 budget,count=N"`. The next theme or the owner moves more text out.
- **Contradicted rules:** each rule kept as target state carries its exception count as debt
  (`what=files that break the <rule> rule,count=N`). The count may only go down; the item is `partial` until it is 0
  or the owner records the rule as describing the code.
- **Stale claims the owner has not settled** (a line whose correct wording needs an owner decision not in the state):
  the line is left as it is, flagged in the PR description, and the item is `partial` with a note.
- **Generic text the owner keeps:** the item is `partial` with the measured ratio as debt
  (`what=generic rule lines,count=N`), or `skipped` if the owner says so.
- A verb that does not resolve is not fixed here; record it and point at T1.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| AGT-01 | `ls AGENTS.md` and the engine's AGT-01 | Present, exact case; `PASS` |
| AGT-02 | The engine's AGT-02 | `PASS`, or the owner's recorded choice for v0.3 |
| AGT-03 | `grep -n 'docs/\|STYLE_GUIDE.md\|artefacts/' AGENTS.md` | Three lines, one fact each; `PASS` |
| AGT-04 | `grep -n -i 'same change set' AGENTS.md` | One sentence naming the triggers; `PASS` |
| AGT-05 | The fenced command block; the engine's AGT-05 and CMD-01 | All seven named and resolved; `PASS` |
| AGT-06 | Each boundary rule's path: `test -e <path>` | Two or more rules, every path exists; `PASS` |
| AGT-08 | `grep -n 'read by' AGENTS.md`; each vendor file's content | The reach line is true; every vendor file is a pointer or reconciled; `PASS` |
| AGT-09 | The release-boundary sentence | Branches named; push and PR only as the state allows; never merge, tag or release; `PASS` |
| AGT-10 | `grep -n -i 'read .* first' AGENTS.md` | No unconfigured deferral; `PASS` |
| AGT-11 | The rule-line tally in the state note | At least 80% specific, every specific line verified; else `partial` with the count |
| EXEC-06 | The engine's EXEC-06 | Every fenced command resolves; `PASS` |
| TST-04 | `grep -n -A2 'single test' AGENTS.md` | A fenced single-test command for the runner; `PASS` |
| Budget | `wc -l AGENTS.md` | 400 or fewer, or the overage recorded as debt |

## Rollback

`git revert` the commits: one per finding, each revertible alone. Text moved to `docs/` comes back with the revert of
its commit; nothing outside `AGENTS.md`, the vendor pointer files the owner agreed to change, the second rules file
the owner agreed to trim, and the new `docs/` page is touched.

## Do-not-do

- Do not rewrite `AGENTS.md` wholesale, reorder its sections, or reflow its lines.
- Do not delete a vendor instruction file, or re-propose a finding the owner rejected, unasked.
- Do not edit the prohibitions section; that is [`add-deny-rules`](add-deny-rules.md).
- Do not edit code to make a rule true, and do not drop a rule because the code breaks it.
- Do not create a harness configuration file to point at a second rules file.
- Do not write a fact an earlier theme has not made true (a verb that does not resolve, a docs page that does not
  exist), and do not name a harness in the reach line that does not load the file.
- Do not add generic prose, persona text or an overview to fill a section.
- Do not copy content from a private repository or workspace into an open-source one, or from any target into the
  framework.

## State updates

Through [`progress.py`](../../docs/reference/tools-cli.md#progresspy), on the theme branch, `--phase` the current step:

```bash
python3 brownfield-recipes/tools/progress.py pref set agents_md.stubs keep \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py pref set agents_md.generic_text move-to-docs \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py set-status F-nnn in_progress --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "grep -n -i 'same change set' AGENTS.md" \
  --verification-result "one sentence, triggers named"
python3 brownfield-recipes/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --commit <sha> --debt "what=files that break the <rule> rule,count=<N>" --note "rule kept as target state"
python3 brownfield-recipes/tools/progress.py theme T7 --status branch_open \
  --branch agentic-readiness/<phase>-agents-md --target <repo> --phase <phase> --render
```

A finding resolved by drift is `done` with the drift as the reason. `partial` is reached through `in_progress`. T7 is
one theme with two playbooks: run this one and [`add-deny-rules`](add-deny-rules.md) on the same branch, and close
the theme once. The theme ends per [ADR 0003](../../docs/architecture/adrs/0003-push-and-pr-policy.md): commit on
the theme branch and stop, unless the owner recorded `ci.pr_by_agent=yes`; then push the branch and open one pull
request into the integration branch (`theme T7 --status pr_open --branch B --pr N` after it exists). Never merge.
Only the owner skips an item.
