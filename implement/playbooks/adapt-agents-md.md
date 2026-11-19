# Playbook: `adapt-agents-md`

> Theme T7 (`AGENTS.md` and governance). Follows the anatomy in [`README.md`](README.md). Written in IR10.1;
> applied and corrected on a Gradle repository (IR10.2) and a multi-component Node repository (IR10.3). Its sibling
> [`add-deny-rules`](add-deny-rules.md) owns the prohibitions section; this playbook owns the rest of the file.

## Goal

The canonical instruction file states this repository's own facts, and only those: the seven verbs as the team runs
them, a single-test command, where documentation lives, when docs change with code, which paths are boundaries,
what an agent may do with branches and releases, which harnesses read the file, and nothing an agent could infer
from the code. Every line is true against the repository, and the file stays within the 400-line budget.

**The rule this playbook enforces: the playbook drafts, the owner edits.** `AGENTS.md` is the owner's voice. Each
finding gets the smallest diff that closes it, proposed and reviewed one at a time. An existing file is never
rewritten wholesale. When no instruction file exists, the playbook creates a bare skeleton first and fills it one
section, one commit at a time ([details](#no-instruction-file-yet)).

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| AGT-01 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-01--instruction-file-present-canonical-and-non-trivial) | Verification: a canonical root `AGENTS.md`, correctly cased, no stub markers, no override file. Creates the file from the greenfield skeleton when none exists |
| AGT-02 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-02--component-coverage-by-instruction-files) | Verification; a component `AGENTS.md` only when the owner asks (component scoping is planned for a later framework version) |
| AGT-03 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-03--documentation-contract-named) | One line each for `docs/`, `docs/STYLE_GUIDE.md` and the scratch directory |
| AGT-04 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-04--definition-of-done-stated) | One definition-of-done sentence tying documentation triggers to the same change set |
| AGT-05 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-05--seven-verbs-named) | The seven verbs named as whole tokens, in the runner's own spelling, annotated with inline comments |
| AGT-06 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-06--architectural-boundaries-declared) | Two or more boundary rules, each naming a path that exists |
| AGT-08 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-08--no-competing-instruction-files-and-the-reach-matrix-is-stated) | The "This file is read by ..." line; vendor pointer files kept and reconciled, never deleted unasked |
| AGT-09 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-09--branch-and-release-boundary-declared) | One release-boundary sentence built from the state and the repository |
| AGT-10 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-10--instruction-indirection-resolved) | A "read X first" deferral becomes an ordinary link, with the must-always rules moved into `AGENTS.md` |
| AGT-11 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-11--instructions-are-specific-and-not-inferable) | Generic text moves to `docs/`; contradicted rules become target state with the exception count; stale lines corrected |
| AGT-12 | [02-agent-governance.md](../../audit/checks/02-agent-governance.md#agt-12--communication-rules-stated) | A "How to write for people" section that names the reader, how to report and how to ask for a decision. Trigger: a confirmed finding, or `extra.agt-12` (Preconditions) |
| AGT-13 | [02-agent-governance-2.md](../../audit/checks/02-agent-governance-2.md#agt-13--coding-conventions-written) | Writes `CONVENTIONS.md` from the greenfield template when no conventions exist; at `PARTIAL`, suggests the missing items and adds the ones the owner accepts. Trigger: a confirmed finding |
| EXEC-06 | [09-execution-determinism.md](../../audit/checks/09-execution-determinism.md#exec-06--documented-commands-resolve) | Every fenced command in `AGENTS.md` resolves; the one command a finding names is fixed inline |
| TST-04 | [10-tests.md](../../audit/checks/10-tests.md#tst-04--fast-path-documented) | Verification only, when T5 wrote the fenced single-test line; written here when the item sits in T7 |

AGT-07 and the `CON` checks are [`add-deny-rules`](add-deny-rules.md)'s. The rubric that governs the whole family
(score non-inferable content, the overview is never scored, the 400-line budget) is the
[A14 rubric](../../audit/checks/02-agent-governance.md#the-a14-rubric-r-16-score-content-not-presence); read it once
before the first diff.

## Preconditions

- The shared procedure in `SKILL.md` applies: [Stage 3](../SKILL.md#stage-3-apply) (state read first, drift first,
  worktree, one item at a time) and [Stage 4](../SKILL.md#stage-4-close-the-theme) (engine re-check, gate, ending).
- A finding the owner rejected at triage (for example an AGT-08 finding on a `CLAUDE.md` import stub) is never
  re-proposed, not even as a side effect of another diff.
- **T1 to T6 done or `partial`.** This theme writes what the earlier themes made true: the verbs (T1), the pinned
  environment and the lock regeneration line (T2), the secrets rules (T3), the hooks and CI (T4), the baselines and
  the single-test line (T5), the docs home, style guide and decision log (T6). A fact an earlier theme has not made
  true is not written as if it were; it stays a finding for that theme.
- **Drift** ([Stage 3](../SKILL.md#stage-3-apply), step 2) matters most here: earlier themes edit `AGENTS.md` (T1 the
  verbs, T5 the fenced test line, T6 the docs line), so a T7 finding is often stale. Verbs a finding calls "not named"
  may now be named; a line it calls stale may already be fixed; a count such as "rule contradicted in five services" is
  re-measured.
- Preferences this playbook reads, when present:

| Key | Effect |
|---|---|
| `agents_md.pointer_section` | Where the docs line already sits; keep it there |
| `agents_md.stubs` | `keep` (default) or `delete-asked`: what happens to a vendor pointer file (Inputs 3) |
| `agents_md.deferral` | `inline` (default) or `harness-config`: how a deferral to a second rules file is resolved (Inputs 4) |
| `agents_md.generic_text` | `move-to-docs` (default) or `delete`, per section if the owner chose per section (Inputs 5) |
| `agents_md.contradicted_rules` | `target-state` (default) or `describe-code` (Inputs 5) |
| `extra.agt-12` | The owner asked by name for the "How to write for people" section with no `AGT-12` finding; the change then has no finding for the re-audit to confirm, so say so in the pull request, under "What changed" |
| `agents_md.reader` | The reader persona the owner confirmed for the AGT-12 section (Inputs 7) |
| `agents_md.comm_long_form` | `no` (default) or `yes`: also write a long-form communication rules file (Inputs 7) |
| `docs.language` | The language the docs are written in; `en` (default) or another (Inputs 7) |
| `agents_md.release_tags` | What an agent may do with tags and releases; feeds the AGT-09 sentence (Inputs 6) |
| `ci.pr_by_agent` | Whether the AGT-09 sentence allows pushing a branch and opening a pull request ([ADR 0003](../docs/architecture/adrs/0003-push-and-pr-policy.md)) |
| `docs.agents_line` | T6 already wrote the docs line; AGT-03 then only verifies it |
| `layout.command_runner` | `per-app`: verbs are listed per app, not at the root |
| `format.mass_reformat` | `no` (usual): never reflow or reformat the file to make it shorter |
| `agents_md.create` | `yes` or `no`: create `AGENTS.md` when no instruction file exists (Inputs 9). Asked in Stage 1, because earlier themes write to the file |
| `agents_md.numbering` | `keep` (default for an existing file): its numbering stays. `nested` (a created file, or an existing one by opt-in): Steps 13 and 15 |
| `agents_md.conventions` | `create` (default): write or complete the conventions. `skip`: leave them as they are (Inputs 11, Step 16) |

## Inputs to ask

No tool is installed by this playbook: the instruction file is plain Markdown and the checks are read by the audit
engine. The questions are about text. Ask them per finding, before the diff for that finding.

1. **Order of the diffs.** Default order, smallest risk first: AGT-05 and EXEC-06 (commands), TST-04 (verify),
   AGT-03, AGT-04, AGT-06, AGT-09, AGT-08, AGT-10, AGT-11, AGT-12, AGT-13. The owner may reorder or skip any; a skip
   goes through `progress.py skip` by the owner.
2. **Boundary rules (AGT-06).** Propose two or three rules from the code index (which directory may import which,
   which layer owns persistence, which folder is generated or vendored). The owner picks; never invent a boundary
   the code does not show. If the code index shows no boundary, ask the owner for one or record the item `partial`.
   With no code index, a `grep` over the import lines can stand in for it to check a layer rule (which directory
   imports which); say which one you used.
3. **Vendor pointer files (AGT-08, the "ask about stub files" rule).** Default `keep`:
   - A vendor file whose content is only an import or a pointer at `AGENTS.md` (`@AGENTS.md`, "See AGENTS.md")
     stays. It is what gives that harness its reach (Claude Code loads `CLAUDE.md`, not `AGENTS.md`). Add the reach
     line to `AGENTS.md` (Steps 7). Ask before deleting anything; deletion is the owner's choice
     (`agents_md.stubs=delete-asked`) and loses that harness's reach.
   - A vendor file that carries extra rules beside the pointer: offer to move those rules into `AGENTS.md` (move,
     not copy) and ask whether the vendor file then becomes the one-line pointer. Move a line that names
     `STYLE_GUIDE.md` as well: "`DOC-02` docs/STYLE_GUIDE.md exists" reads that name in `AGENTS.md`. A rule that only makes sense for
     that harness (a tool preference, a harness setting) may stay there; say so in the pull request, under
     "What changed".
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
     wrote is lost. Option `delete` is offered per section. A reader persona (who the docs and messages are
     written for, AGT-12) is a communication rule, not a role-play prompt: it stays.
   - A rule the code contradicts becomes **target state**: "New code must X. N existing files do not yet; find them
     with `<command>`." The count is measured, not copied from the finding. Option `describe-code` (reword the rule
     to describe the code as it is) is offered per rule. T7 never edits code to make a rule true.
   - A stale line (a path hint, a claim about ignored or tracked files that no longer holds) is corrected to match
     the repository. When the correct wording depends on an owner decision recorded elsewhere in the state (a file
     tracked on purpose), the line states that decision; it does not change the files.
6. **Release boundary (AGT-09).** Default: one sentence built from facts (Steps 6). The owner reviews the sentence;
   never ask the owner to write it from scratch.
7. **Communication rules (AGT-12).** Three questions, asked together in one numbered block with lettered options
   ([decision requests](../../audit/prompts/talking-to-the-user.md#decision-requests)):
   1. **The reader** (`agents_md.reader`). Draft the persona from the stack profile and the code, for example "a new
      engineer who knows Java and Gradle, but not this repository or its terms". a. the draft (default); b. the
      owner's edit. Never ask the owner to write it from nothing.
   2. **The docs language** (`docs.language`). a. English, `en` (default); b. another language: the owner supplies
      the rules in that language, and the item is `partial`, because the check reads English words.
   3. **The long form** (`agents_md.comm_long_form`): a separate rules file. It starts from the greenfield template
      [`COMMUNICATION_RULES.md`](../../greenfield/templates/docs/COMMUNICATION_RULES.md). a. no (default): the style
      guide holds the docs rules ([`establish-docs-contract`](establish-docs-contract.md)); b. yes.
8. **Owner-only values.** None is needed for this playbook. If a step seems to need one (a reviewer name, a
   contact), ask in the order `SKILL.md` Stage 2, step 6 gives (supply it, draft one for review, or skip).
9. **No instruction file yet** (`agents_md.create`). Asked in [Stage 1](../SKILL.md#stage-1-triage), step 5,
   when no instruction file of any kind exists and AGT-01 is a confirmed finding. One question: create `AGENTS.md`
   from the skeleton? a. yes (default); b. no: earlier themes write to `CONTRIBUTING.md`, and the owner skips the
   AGT-01 item. If a vendor file such as `CLAUDE.md` carries real rules, do not create a second file: handle it as
   Inputs 3 says.
10. **Renumbering an existing file** (`agents_md.numbering`). Ask only when the file exists and the owner raises
    numbering or asks for nested style. One question: a. `keep` (default): the file's numbering stays; b. `nested`:
    Step 15 renumbers it, one top-level section per commit, with an audit before and after each commit. Never renumber
    a file the owner did not opt in for.
11. **Coding conventions (AGT-13)** (`agents_md.conventions`). Ask when `AGT-13` is a confirmed finding. One question,
    with the options that fit the verdict:
    1. No conventions yet (`FAIL`). a. Write `CONVENTIONS.md` from the greenfield template, one section at a time
       (default); b. skip: record the item `skipped`.
    2. Conventions exist at `PARTIAL`. a. List the missing items as suggestions and add each one the owner accepts
       (default); b. leave the conventions as they are: the item is `partial`, with debt.

    The owner confirms every section before it is committed. A stub word (`TBD`, `TODO`) in the conventions goes to the
    owner as a question, never as a guess.

## Steps

### Generic

1. **Baseline.** Record: the line count of `AGENTS.md` (and of each per-component file), the
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
   `python3 -m unittest tests.test_module -k name`. The framework's own [`AGENTS.md`](../../AGENTS.md#commands)
   is the worked example.
4. **Documentation contract and boundaries (AGT-03, AGT-06).** Three facts, each on its own line: `docs/` is the
   documentation home, `docs/STYLE_GUIDE.md` holds the writing rules, the scratch directory (`artefacts/`) is scratch
   and off-limits as a source of truth. T6 usually wrote the first two in the section `agents_md.pointer_section`
   names (`docs.agents_line`). Keep them there and add only what is missing. If the repository has no scratch
   directory, the third line says where scratch goes, so the rule exists before the folder does. Then add the
   boundary rules the owner picked (Inputs 2), one line each, each naming a path that exists (`test -e <path>`), in
   the section where the file describes its structure.
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
   - every branch the declared branch rules protect by name. Read them where the repository keeps them. GitHub
     ruleset files: `.github/rulesets/*.json`, each `conditions.ref_name.include` entry, `refs/heads/` removed. The
     Settings app: the `branches:` list in `.github/settings.yml`. Terraform: a `github_repository_ruleset`,
     `github_branch_protection` or `gitlab_branch_protection` resource. Skip `~DEFAULT_BRANCH`, `~ALL` and glob
     patterns such as `release/*`; the default branch is already named above. Name each other branch as written
     (`staging`, not "the staging branch" alone), or AGT-09 stays `PARTIAL`. When the rules live only in the
     provider's settings, nothing is read; do not guess the list;
   - whether an agent may push a branch and open a pull request: only when the state records `ci.pr_by_agent=yes`
     ([ADR 0003](../docs/architecture/adrs/0003-push-and-pr-policy.md)); otherwise it stops at a local branch;
   - that an agent never merges, tags, publishes a release or pushes to the default branch;
   - when a release tool is tracked (`release-please-config.json`, `.releaserc*`, a release workflow), that the
     tool cuts releases.

   Example: "Branch from `dev` and open pull requests into `dev`; `main` receives releases only. An agent may push
   its branch and open a pull request; it never merges, tags, publishes a release or pushes to `main` or `dev`.
   Releases are cut by release-please." Re-check the sentence whenever `ci.pr_by_agent` or
   `agents_md.release_tags` changes. The prohibition half also lands in the prohibitions section through
   [`add-deny-rules`](add-deny-rules.md) (default branch); keep the two consistent, do not state the rule twice in
   different words. The sentence is the one line of its section that holds never, do not or must not (Step 14).
   Keep it the only one. Three such lines make the section a prohibitions section for "`AGT-07` Do-not-do / deny
   rules present". Then "`CON-01` Allow/deny artifact present" and "`CON-02` Test directories protected" read it too.
7. **Reach and vendor files (AGT-08).** Add one line near the top of `AGENTS.md`: `This file is read by <harnesses>.`
   Name only harnesses that really reach it: native `AGENTS.md` readers, plus each harness whose vendor file points
   at it (a `CLAUDE.md` that imports `@AGENTS.md` makes Claude Code a reader). The engine takes the line as given; the
   line must be true. Then handle each vendor file per Inputs 3. A shadowed pair or an override file is reported to
   the owner with the harness it affects; do not delete either side unasked.
8. **Deferral (AGT-10).** Find the "read X first" line. Per Inputs 4: list the must-always rules in X that
   `AGENTS.md` does not already state, propose moving them (a diff that adds them to `AGENTS.md` and, if the owner
   agrees, removes them from X, so the rule lives in one place), and turn the deferral into a reference link. Check
   the tree or layout description in X against the repository while there: a stale tree is reported, and fixed only
   if the owner asks (X is not this playbook's file). X may be the conventions file or `CONTRIBUTING.md`. Then run
   "`AGT-13` Coding conventions written" and "`HYG-13` Contributing rules written" after the move. If either verdict
   falls, put the rule back in X.
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
    (component scoping is planned for a later framework version). Name a component file `AGENTS.md`, never a vendor
    name such as `CLAUDE.md`. "`AGT-08` No competing instruction files, and the reach matrix is stated" counts only
    vendor-named files as competitors.
11. **Communication rules (AGT-12).** Add a section headed "How to write for people". Match the file's heading
    level and style (D18), and keep a word the check reads (`write for`, `communication`, `reporting`). Place it
    after the section `agents_md.pointer_section` names; without that preference, place it before the prohibitions
    section. Start from the template in the greenfield
    [`AGENTS.md` § 5](../../greenfield/templates/AGENTS.md#5-how-to-write-for-people). It holds a scope line (5.1,
    with the link to the long form) and six numbered rules (5.2 to 5.7):
    - the reader: the persona the owner confirmed (Inputs 7);
    - bottom line first;
    - plain language: short sentences (at most 25 words), active voice, one term per meaning;
    - form: choose the form from the content (numbered rules, tables, diagrams or alerts), and link the style
      guide's form rules;
    - reports: a status report (done, not done, blocked, next) and a done report (what changed, how it was checked,
      what was not done);
    - decisions: the context, two to four options with pros and cons, a recommendation and the default.

    An existing section that already covers one of the three (reader, reports, decisions) gets only the missing
    rules. With `agents_md.comm_long_form=yes`, start the long-form file from the greenfield template
    [`docs/COMMUNICATION_RULES.md`](../../greenfield/templates/docs/COMMUNICATION_RULES.md). Adapt it to the target.
    Put it under `docs/`, with a name and place that follow the repository's convention (D18). Set its reader to the
    persona the owner confirmed. Link it from the section, and keep `communicat` in the file name: AGT-12 reads a
    linked file whose name contains it. Then run the engine's AGT-12.
12. **Budget.** Count the lines. Over 400: link instead of inlining (move a long section to `docs/` with a link) and
    record the overage as debt. Never shorten by reflowing or deleting the owner's rules. Move only a section that
    no root-only check reads. These stay in the root `AGENTS.md`, because the checks read them there and nowhere else:
    - the commands: "`AGT-05` Seven verbs named", "`EXEC-03` Non-interactive setup path", "`EXEC-06` Documented
      commands resolve" and "`TST-04` Fast path documented";
    - the documentation contract and the boundaries: "`AGT-03` Documentation contract named", "`DOC-02`
      docs/STYLE_GUIDE.md exists" and "`AGT-06` Architectural boundaries declared";
    - the definition of done ("`AGT-04` Definition of done stated") and the release boundary ("`AGT-09` Branch and
      release boundary declared");
    - the "How to write for people" section ("`AGT-12` Communication rules stated");
    - the baseline and coverage lines: "`BASE-01` Baseline artifact exists", "`BASE-03` No-new-violations
      mechanism" and "`BASE-04` Coverage floor configured".
13. **Numbering.** Text this playbook writes into a target comes from `greenfield/templates/`. It follows the form
    rules of the greenfield [style guide](../../greenfield/templates/docs/STYLE_GUIDE.md#31-form-follows-content).
    Read those rules there and do not copy them here. Then read `agents_md.numbering`:
    - `keep` (default for an existing file): leave the file's own numbering as it is. Write each new line in the
      style of the section it joins.
    - `nested` (used for a file this playbook creates): number the sections, rules and sub-rules in the nested style
      the style guide names (`## 1.`, `1.1`, `1.1.1`).

    The fourth level follows decision 4.2. Lettered `a.` items end each line but the last with a trailing `\`.
    Each lettered item is a full sentence that ends in a full stop. A table suits items that share columns.
14. **Two parsing traps.** The engine reads `AGENTS.md` line by line, so a tidy edit can break a check that passed.
    - Keep a boundary path and its rule word on one line. `AGT-06` boundaries declared counts a line only when that
      one line holds a path that exists and a word such as must, never or only. A line break between them hides
      the rule.
    - Keep prohibition words out of sections that are not prohibitions. The engine reads any section with three or
      more lines that hold never, do not or must not as a prohibitions section, whatever its heading. `AGT-07`
      prohibitions cover the four areas, and the deny-list checks (`CON-01`, `CON-02`), then read that section too.
      State the rules of other sections in positive form.
15. **Opt-in restructure of an existing file (`agents_md.numbering=nested`).** Run this step only when the owner chose
    `nested` for a file that already exists (Inputs 10). A file this playbook creates is numbered as it is written, so
    it skips this step. Renumber one top-level section per commit, never the whole file at once.
    1. **Audit before.** On a clean tree, run the engine and keep the report path:
       `python3 audit/tools/engine.py <worktree> --out-dir <dir outside the target> --no-user-config`. Use the same
       command for every run in this step.
    2. **Renumber one section.** Number its heading, rules and sub-rules in the style of Step 13. Change only the
       number or marker that starts a line, and the trailing `\` of a lettered item. Never change a rule's words, never
       move text between sections, and never reflow a line.
    3. **Audit after, then compare.** Commit the section and run the same engine command again. Then run
       `python3 implement/tools/compare_reports.py <before report> <after report>`. That tool reads two engine reports
       and writes nothing. The engine's `--baseline` is not used: it flags only new findings, not a changed verdict.
       The tool exits 0 even when checks moved, so read the "Checks that moved" table. Expected: `None.`
    4. **Stop on a changed verdict.** Any row in that table (`improved`, `regressed`, `changed`, `added` or `removed`)
       stops the step. Revert the commit, or fix it in a new commit and audit again, before the next section. The
       after report is the before report of the next section.
    5. **Read the section as rendered.** Two traps pass the engine comparison, so look at the page before each commit:
       - A dropped trailing `\` joins two lettered lines. `make docs-lint` and the verdicts do not catch it.
       - A lettered line that ends in `;` makes one long sentence for `DOC-05` docs are readable. Each lettered
         item is a full sentence that ends in a full stop. If an item is not one, ask the owner: rewording a rule
         is not renumbering.

    The two traps of Step 14 still hold: the renumbering never splits a boundary path from its rule word, and never
    moves a prohibition word into another section. This step fits the Do-not-do line on reflowing: a line keeps its
    words, its breaks and its place, and only its number, marker or trailing `\` changes.
16. **Coding conventions (AGT-13).** Run the engine's `AGT-13` first and read which of the five items it names as
    missing: naming, layering, errors and logging, testing, and the link to the formatter or linter config. Then follow
    the owner's answer (Inputs 11). A conventions file or section holds only rules that a tool does not enforce and a
    reader cannot infer from the code.
    - **a. No conventions.** Write `CONVENTIONS.md` from the greenfield
      [`CONVENTIONS.md`](../../greenfield/templates/CONVENTIONS.md) template. Adapt it to the target's stack and to its
      own naming of files (D18): a repository that already calls its docs `CODE_STYLE.md` or keeps them under `docs/`
      gets that name and place, because the engine finds any of the names the check page lists. Keep the template's
      five sections. Replace `[Project Name]` and every example with the target's own. Text comes from
      `greenfield/templates/` only: write no rule from memory or from this playbook. Add one link line to `AGENTS.md`,
      in the section that names the documentation, and state no convention there a second time. Word it as a
      reference ("Coding conventions: `CONVENTIONS.md`"), never as "read `CONVENTIONS.md` first". The check
      "`AGT-10` Instruction indirection resolved" reads that second form as a deferral.
    - **b. Evidence for every rule.** Every rule written comes from the code. Find it with the code index
      (`search_graph` for the types, the layers and the error classes) and cross-check it with a `grep` or `rg`. With
      no code index, a `grep` stands in; say which one you used. Evidence by item:
      - naming: the file names and the type names in the source tree and the test tree;
      - layering: the import lines between directories, as in Inputs 2;
      - errors and logging: the error classes that exist and the logger the code calls;
      - testing: the test directories, the runner config and the test file names;
      - the config link: the formatter and linter config files that exist (`test -e <path>`). Link each one. Never copy
        its settings.

      The owner confirms each section before its commit. A rule with no evidence stays out, and the item is `partial`.
    - **c. Conventions at `PARTIAL`.** List the missing items as suggestions, each with the evidence behind it. Add only
      the items the owner accepts. Never invent the missing rule. A stub word (`TBD`, `TODO`) goes to the owner as a
      question: "this line says `TBD`; what is the rule?" Remove the word only when the owner answers or says to drop
      the line.
    - **d. Where it stays.** A conventions section in `AGENTS.md` or `CONTRIBUTING.md` stays where it is, unless the
      owner asks to move it. Complete it in place.
    - **Git rules.** Branch and commit rules belong in `CONTRIBUTING.md`, the home of branches, commits and pull
      requests. Link to it from the conventions and write none of them there. Moving the Git rules out of an existing
      conventions file is a separate diff, made only when the owner asks.

    Then run the engine's `AGT-13`. Run `AGT-08` too: it must not count the new file as a vendor instruction file.

### No instruction file yet

Use this branch only when the engine's AGT-01 finds no instruction file in any variant (`AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`, `.cursorrules` and the rest of the variant table) and `agents_md.create=yes` (Inputs 9). A stub that
holds the owner's text is an existing file: use the Generic steps. A vendor file with real rules is AGT-08's
(Inputs 3).

1. **Skeleton.** The first theme that writes to the instruction file makes this step, often T1
   ([Stage 3, step 11](../SKILL.md#stage-3-apply)). Create `AGENTS.md` at the repository root with the title and
   the six section headings of the [greenfield `AGENTS.md` template](../../greenfield/templates/AGENTS.md), and
   nothing else. Number the headings in nested style (`## 1.` to `## 6.`, Step 13): the file is created, so
   `agents_md.numbering` is `nested`. The template is a filled example for one Node project: none of its body
   text is written into the target. That theme then writes its own lines into the matching section. When T7
   starts, the file exists and steps 2 to 4 below fill the rest.
2. **Fill each section with the Generic step that owns it, one commit per section.** Every fact comes from the
   repository, never from the template. A line you cannot make true stays out, and no `<placeholder>` or `TODO`
   remains in the file.

   | Skeleton section | Generic step | Fact comes from |
   |---|---|---|
   | Reach line | Step 7 | The harnesses that load the file (a `CLAUDE.md` import counts) |
   | 1. Commands | Steps 2 and 3 | The runner and the stack profile; verbs T1 made true |
   | 2. Boundaries | Step 4 and Inputs 2 | The code index or the import lines; two or more rules, each naming a path that exists. Naming rules appear only when the owner states one a linter does not enforce |
   | 3. Documentation | Steps 4 and 5 | The docs home, style guide and decision log T6 made true |
   | 4. Branches and releases | Step 6 | The branches, rulesets and release tool the repository declares |
   | 5. How to write for people | Step 11 | The persona the owner confirms (Inputs 7) |
   | 6. Never | [`add-deny-rules`](add-deny-rules.md) | Not written here; it runs on the same branch |

   Section 6 stays empty until `add-deny-rules` fills it. Then "`AGT-07` Do-not-do / deny rules present",
   "`CON-01` Allow/deny artifact present" and "`CON-02` Test directories protected" read it.

3. **Review.** The owner reads each section as its diff arrives (Inputs 1 sets the order). The file is a draft until
   the owner has seen every section. Then run the engine's AGT-01, AGT-05 and AGT-12.
4. **Budget.** The skeleton is far below 400 lines. Step 12 applies if a filled file is not.

If a fact is missing (no boundary the code shows, no release tool), leave that line out and record the item
`partial` with a note, as the Generic steps say. Do not fill a gap with generic text.

### Gradle and Quarkus

Profile: [`stacks/java.md`](../../audit/stacks/java.md#command-surface-map). Verbs are Gradle task names
(`formatCheck` for `format:check`), always through the wrapper (`./gradlew`); annotate each with the framework verb.
The single-test form is `./gradlew test --tests '<fully.qualified.Class>'` (add `.<method>` for one method). Boundary candidates
come from the package layout: REST resources, services, repositories or entities, and the migration folder
(`src/main/resources/db/migration/`); a "never inject X in Y" rule is the usual contradicted rule, counted with a
code-index query on the injection points. JDK and wrapper preconditions sit next to the commands. The AGT-12 persona names
the language and the build tool: "a new engineer who knows Java, Quarkus and Gradle". For `AGT-13` (Step 16), naming
evidence comes from the package and class names (`*Resource`, `*Service`, `*Repository`) and the test class names;
layering evidence comes from the package layout and the injection points; the config links are `.editorconfig`,
`checkstyle*.xml` and the `spotless` block of `build.gradle`; testing evidence is `src/test/` and the JUnit setup.

### Node (npm, NestJS, React)

Profile: [`stacks/typescript-node.md`](../../audit/stacks/typescript-node.md#command-surface-map). In a per-app layout
(`layout.command_runner=per-app`) list the verbs under each app's heading with `npm --prefix <app> run <verb>` or a
`cd <app>` line, annotated. A verb an app does not have (no `typecheck` in a plain JavaScript app) is stated as such,
not invented. Jest single test: `npx jest -t '<name>'` from the app folder. Boundary candidates: the app folders
themselves (one app never imports another), `src/` versus `test/`, generated clients, and the infrastructure folder.
The AGT-12 persona names the languages and frameworks the apps use: "a new engineer who knows TypeScript, NestJS
and React". For `AGT-13` (Step 16), write one conventions file per repository, not one per app, and name the app a
rule covers when the apps differ. Naming evidence comes from the file names under each `src/` (`*.controller.ts`,
`*.module.ts`, `*.test.tsx`); layering evidence comes from the import lines between app folders and the NestJS module
layout; the config links are `.editorconfig`, `.prettierrc`, `eslint.config.*` and `biome.json`, with `tsconfig.json`
for strict mode; testing evidence is the Jest or Vitest config and the test folders.

## Commits

One commit per finding, so the owner can revert any one alone. A row that says "one per" repeats for each case. A
finding the owner skips makes no commit, and the owner's order (Inputs 1) replaces the order below.

| # | Commit | Checks | Kind |
|---|---|---|---|
| 1 | Skeleton: title and section headings (only when no instruction file existed; made by the first theme that writes to the file) | `AGT-01` | hand |
| 2 | The seven verbs in a fenced block, annotated | `AGT-05` | hand |
| 3 | Fix of the command a finding names (one per finding) | `EXEC-06` | hand |
| 4 | Precondition lines and lines T2 deferred, beside the commands (only when missing) | - | hand |
| 5 | Fenced single-test line (only when the item sits in T7) | `TST-04` | hand |
| 6 | Documentation contract lines (only the missing ones) | `AGT-03` | hand |
| 7 | Boundary rules the owner picked | `AGT-06` | hand |
| 8 | Definition-of-done sentence | `AGT-04` | hand |
| 9 | Release-boundary sentence | `AGT-09` | hand |
| 10 | Reach line | `AGT-08` | hand |
| 11 | Vendor file reconciled (one per file the owner agreed to change) | `AGT-08` | hand |
| 12 | Deferral resolved: must-always rules moved in, link line | `AGT-10` | hand |
| 13 | Generic text moved to a `docs/` page (one per section) | `AGT-11` | hand |
| 14 | Contradicted rule as target state (one per rule) | `AGT-11` | hand |
| 15 | Stale lines corrected | `AGT-11` | hand |
| 16 | Component `AGENTS.md` (only when the owner asks) | `AGT-02` | hand |
| 17 | "How to write for people" section | `AGT-12` | hand |
| 18 | Long-form communication rules file and its link (only with `agents_md.comm_long_form=yes`) | `AGT-12` | hand |
| 19 | Long section moved to `docs/` (only when over the 400-line budget) | - | hand |
| 20 | One top-level section renumbered in nested style (only with `agents_md.numbering=nested` on an existing file; one per section) | - | hand |
| 21 | `CONVENTIONS.md` written from the template, one section per commit (only when no conventions exist) | `AGT-13` | hand |
| 22 | Link line to the conventions in `AGENTS.md` (only when the file is new) | `AGT-13` | hand |
| 23 | Missing conventions items the owner accepted (only at `PARTIAL`; one per item) | `AGT-13` | hand |
| 24 | Stub word settled with the owner's answer (one per word) | `AGT-13` | hand |

## Continue on error

- **Over budget:** an `AGENTS.md` over 400 lines after the moves is `partial` with
  `--debt "what=AGENTS.md lines over the 400 budget,count=N"`. The next theme or the owner moves more text out.
- **Contradicted rules:** each rule kept as target state carries its exception count as debt
  (`what=files that break the <rule> rule,count=N`). The count may only go down; the item is `partial` until it is 0
  or the owner records the rule as describing the code.
- **Stale claims the owner has not settled** (a line whose correct wording needs an owner decision not in the state):
  the line is left as it is, flagged in the pull request under "What was not done", and the item is `partial`
  with a note.
- **Generic text the owner keeps:** the item is `partial` with the measured ratio as debt
  (`what=generic rule lines,count=N`), or `skipped` if the owner says so.
- A verb that does not resolve is not fixed here; record it and point at T1.
- **A changed verdict in the renumbering (Step 15):** the step stops at that section. The item is `partial` with a
  note that names the check and the section. Sections already renumbered stay; the rest keep their old numbering.
  Say so in the pull request, under "What was not done".
- **The owner declines conventions items (Step 16):** the item is `partial`, with each declined item as debt
  (`what=conventions items missing (<names>),count=N`). The count may only go down. A rule with no evidence in the code
  stays out and counts the same way.
- **A stub word the owner has not answered:** the line stays as it is, the item is `partial`, and the pull request says
  so under "What was not done".

## Verification

| Check | Command or file | Expected |
|---|---|---|
| AGT-01 | `ls AGENTS.md` and the engine's AGT-01 | Present, exact case; `PASS` |
| AGT-02 | The engine's AGT-02 | `PASS`, or the owner's recorded choice |
| AGT-03 | `grep -n 'docs/\|STYLE_GUIDE.md\|artefacts/' AGENTS.md` | Three lines, one fact each; `PASS` |
| AGT-04 | `grep -n -i 'same change set' AGENTS.md` | One sentence naming the triggers; `PASS` |
| AGT-05 | The fenced command block; the engine's AGT-05 and CMD-01 | All seven named and resolved; `PASS` |
| AGT-06 | Each boundary rule's path: `test -e <path>` | Two or more rules, every path exists; `PASS` |
| AGT-08 | `grep -n 'read by' AGENTS.md`; each vendor file's content | The reach line is true; every vendor file is a pointer or reconciled; `PASS` |
| AGT-09 | The release-boundary sentence | Branches named, each protected branch the declared rules name included; push and PR only as the state allows; never merge, tag or release; `PASS` |
| AGT-10 | `grep -n -i 'read .* first' AGENTS.md` | No unconfigured deferral; `PASS` |
| AGT-11 | The rule-line tally in the state note | At least 80% specific, every specific line verified; else `partial` with the count |
| AGT-12 | `grep -n -i -A6 'write for' AGENTS.md`; the engine's AGT-12 | The section names the confirmed persona, how to report and how to ask for a decision; `PASS` (`partial` for a non-English docs language) |
| AGT-13 | The engine's AGT-13; `grep -n -i 'TBD\|TODO' CONVENTIONS.md` | Naming, layering, errors and logging, testing and the config link are covered, with no stub word; `PASS`, or `partial` with the missing items named |
| EXEC-06 | The engine's EXEC-06 | Every fenced command resolves; `PASS` |
| TST-04 | `grep -n -A2 'single test' AGENTS.md` | A fenced single-test command for the runner; `PASS` |
| Budget | `wc -l AGENTS.md` | 400 or fewer, or the overage recorded as debt |
| Renumbering | After each section commit: `python3 implement/tools/compare_reports.py <before report> <after report>` | "Checks that moved" says `None.`: no changed verdict. `git show --word-diff` shows only numbers, markers and `\` |

## Rollback

`git revert` the commits, newest first: one per finding, each revertible alone. Some commits move a rule or a
text block: a reconciled vendor file, the deferral, generic text, a long section. The revert returns the text to its
old place. This playbook touches only `AGENTS.md`, the new `docs/` page, the long-form communication rules
file and `CONVENTIONS.md` (new, or completed in place). It also touches a vendor pointer file or the second rules
file, but only where the owner agreed. A renumbering commit (Step 15) reverts alone and restores that section's old
numbering. A conventions commit (Step 16) reverts alone too.

## Do-not-do

- Do not rewrite an existing `AGENTS.md` wholesale, reorder its sections, or reflow its lines. The opt-in
  renumbering (Step 15) keeps this true: it changes only the number, marker or trailing `\` of a line.
- Do not renumber an existing file the owner did not opt in for, renumber two top-level sections in one commit, or
  go on after a changed verdict.
- Do not copy the template's example text, a placeholder or a generic line into a created file, and do not create
  `AGENTS.md` beside a vendor file that holds real rules.
- Do not reword the rest of `AGENTS.md` to meet the plain-language rules. Only the new AGT-12 section follows
  them, and no prose debt is recorded for the file.
- Do not delete a vendor instruction file, or re-propose a finding the owner rejected, unasked.
- Do not edit the prohibitions section; that is [`add-deny-rules`](add-deny-rules.md). It is the section that
  "`AGT-07` Do-not-do / deny rules present", "`CON-01` Allow/deny artifact present" and "`CON-02` Test
  directories protected" read.
- Do not edit code to make a rule true, and do not drop a rule because the code breaks it.
- Do not create a harness configuration file to point at a second rules file.
- Do not write a fact an earlier theme has not made true (a verb that does not resolve, a docs page that does not
  exist), and do not name a harness in the reach line that does not load the file.
- Do not add generic prose, role-play persona text or an overview to fill a section. The reader persona of the
  AGT-12 section is not generic text.
- Do not write a conventions rule that the code does not show, fill a missing item with generic text, or invent the
  rule behind a `TBD` or `TODO` line. Do not write conventions text that does not come from `greenfield/templates/`.
- Do not move or rewrite a conventions section in `AGENTS.md` or `CONTRIBUTING.md` unasked, copy a Git rule into the
  conventions, or copy a formatter or linter setting into them.
- Do not copy content from a private repository or workspace into an open-source one, or from any target into the
  framework.

## State updates

Beyond the shared lines in [Stage 3](../SKILL.md#stage-3-apply) (`in_progress`, the theme rows) and
[Stage 4](../SKILL.md#stage-4-close-the-theme) (the ending):

```bash
python3 implement/tools/progress.py pref set agents_md.stubs keep \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set agents_md.generic_text move-to-docs \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py set-status F-nnn done --workspace <workspace> --phase <phase> \
  --commit <sha> --verification-command "grep -n -i 'same change set' AGENTS.md" \
  --verification-result "one sentence, triggers named"
python3 implement/tools/progress.py pref set agents_md.reader "a new engineer who knows Java and Gradle" \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py set-status F-nnn done --workspace <workspace> --phase <phase> \
  --commit <sha> --verification-command "grep -n -i -A6 'write for' AGENTS.md" \
  --verification-result "section names the reader, reports and decisions; AGT-12 PASS"
python3 implement/tools/progress.py set-status F-nnn partial --workspace <workspace> --phase <phase> \
  --commit <sha> --debt "what=files that break the <rule> rule,count=<N>" --note "rule kept as target state"
python3 implement/tools/progress.py pref set agents_md.conventions create \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py set-status F-nnn partial --workspace <workspace> --phase <phase> \
  --commit <sha> --debt "what=conventions items missing (testing),count=1" --note "owner declined the testing item"
```

T7 is one theme with two playbooks: run this one and [`add-deny-rules`](add-deny-rules.md) on the same branch, and
close the theme once ([Stage 4](../SKILL.md#stage-4-close-the-theme)).
