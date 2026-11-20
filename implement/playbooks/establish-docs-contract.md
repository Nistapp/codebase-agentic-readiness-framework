# Playbook: `establish-docs-contract`

> Theme T6 (documentation contract and navigation). Follows the anatomy in [`README.md`](README.md). Written in
> IR09.1; applied and corrected on a Gradle/Quarkus repository (IR09.2) and a multi-app Node repository (IR09.3).

## Goal

An agent finds permanent knowledge in one place: `docs/` has an index, a short style guide that the instruction
file names, a decision log with a policy, a template and an index, and a short architecture page with a diagram that was
checked. Scratch work stays out of version control. Structural traps (very large files, binaries) are listed,
not moved.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| DOC-01 | [03-documentation-contract.md](../../audit/checks/03-documentation-contract.md#doc-01--docs-exists) | Confirms `docs/` holds Markdown, adds `docs/README.md` as the index; never creates a second docs home. A dense README section that the owner agrees to move gets a `docs/` page and an index row (Steps 10) |
| DOC-02 | [03-documentation-contract.md](../../audit/checks/03-documentation-contract.md#doc-02--docsstyle_guidemd-exists) | Adds a one-page `docs/STYLE_GUIDE.md` with the form rules and one line in the instruction file that names it. An existing guide gets the form rules only by the owner's choice (Steps 9) |
| DOC-03 | [03-documentation-contract.md](../../audit/checks/03-documentation-contract.md#doc-03--artefacts-exists-and-is-ignored) | Verifies the scratch directory rule; adds the ignore rule only if a scratch directory exists |
| DOC-04 | [03-documentation-contract.md](../../audit/checks/03-documentation-contract.md#doc-04--adr-directory-and-index) | Adds `docs/architecture/adrs/` with an ADR policy page, a template, an index and two or three first records for the owner to review |
| DOC-05 | [03-documentation-contract.md](../../audit/checks/03-documentation-contract.md#doc-05--docs-are-readable) | Adds a "Plain language" and a "Diagrams" section to the style guide (Steps 3); the pages this theme writes pass the rules. Existing pages are not rewritten. A prose check with a ratchet only when the owner picks one of three permissive licences for it (Inputs 6, Steps 8). Trigger: a confirmed finding, or `extra.doc-05` (Preconditions) |
| NAV-01 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-01--declared-component-boundaries) | Verification only: lists the declared components in the architecture page |
| NAV-02 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-02--obvious-entry-points) | Verification only: names the entry points in the architecture page |
| NAV-03 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-03--structural-red-flags) | Census of oversized files, catch-all directories, binaries and minified assets; document, never move |
| NAV-04 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-04--architecture-orientation-artifact-informational-unscored) | Writes `docs/architecture/overview.md` from the code index, with one validated Mermaid diagram |
| NAV-05 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-05--public-symbol-documentation-coverage-informational-unscored) | Verification only: records the ratio; no code is edited |

DOC-03, NAV-01 and NAV-05 had no confirmed finding in the two repositories this playbook was first applied to.
They stay here so a repository that has one has a procedure, and so the re-audit reads them.

## Preconditions

- The shared procedure in `SKILL.md` applies: [Stage 3](../SKILL.md#stage-3-apply) (state read first, drift first,
  worktree, one item at a time) and [Stage 4](../SKILL.md#stage-4-close-the-theme) (engine re-check, gate, ending).
- Preferences this playbook reads, when present: `format.mass_reformat` (a `no` means every docs check is a
  baseline or ratchet, never a reformat; for prose, `yes` changes nothing, see Do-not-do), `extra.prose-rewrite`
  (the pages the owner named for a prose rewrite), `layout.command_runner`, `ci.edits_authorised` (needed to add the
  docs CI job), `agents_md.pointer_section` (where the one instruction-file line goes), `docs.prose_check` and
  `docs.prose_check_licence` (Inputs 6), `docs.style_guide_update` (`ask`, `yes` or `no`; default `ask`; Inputs 8),
  `docs.split_readme` (`ask`, `yes` or `no`; default `ask`; Inputs 9),
  `docs.language` (the language of the docs; see [`adapt-agents-md`](adapt-agents-md.md#inputs-to-ask), Inputs 7),
  `extra.*`.
- The `DOC-05` steps run on a confirmed `DOC-05` finding. They also run when the owner asked for them by name in
  Stage 1 (`extra.doc-05`); that change has no finding for the re-audit to confirm, so say so in the pull request,
  under "What changed".
- **Drift** ([Stage 3](../SKILL.md#stage-3-apply), step 2): a finding that says "no `docs/` directory" can be stale: an
  earlier theme or an audit-report commit may have created `docs/`. The engine passes DOC-01 on any Markdown file under
  `docs/`, so the report folders alone make it pass. Add the index to the folder that exists; never create a second
  `docs/`. Re-measure every size or count a finding quotes ("340 MB in the tree").
- No earlier theme is needed. If the command-surface theme named a docs verb, reuse it in the lint step.
- **Private sources** (the hard rule in `SKILL.md`): a private model may be mentioned by description only, with
  no path and no hostname.

## Inputs to ask

1. **Docs tooling.** Detect first: an existing Markdown linter config (`.markdownlint*`, `.remarkrc*`), a docs
   job in CI, a link checker. Use what exists. If none, offer this set (the framework's recommendation) and
   the owner decides, none included. A one-off pick from an earlier theme (`docs.lint_tools`, scope one-off)
   is offered first here; adopting it is still the owner's choice. Currency checked 2026-10-30 (npm registry,
   GitHub releases API); re-check when applied.

   | Tool | Version, date | Weekly downloads | Pros | Cons |
   |---|---|---|---|---|
   | `markdownlint-cli2` | 0.24.0, 2026-10-21 | about 2.4 million | The standard rule set (MD numbers); config file; works as a ratchet by path list; no browser | Needs Node 22 or newer; no per-path rule overrides (see Steps) |
   | `@mermaid-js/mermaid-cli` (`mmdc`) | 12.0.0, 2026-09-24 | about 0.8 million | Renders every Mermaid block with the real library, so a syntax error fails the job | Pulls a Chrome build through Puppeteer (large, needs `--no-sandbox` in CI); Node 22 or newer |
   | `lychee` (optional) | v0.24.2, 2026-05-01 | not measured (binary) | Finds dead relative and external links | One more tool and more CI time; network flakiness on external links, so use relative links only |

   Recommend `markdownlint-cli2` and `mmdc` in a **separate** CI job, path-filtered to changed Markdown, so the
   main build and a JVM or other non-Node stack gain no Node step. `lychee` is offered, never assumed; record
   the answer as a preference.

   > [!NOTE]
   > Why Node on a non-Node repository: markdownlint's rules and the Mermaid library exist only as JavaScript.
   > A JVM route can format Markdown but not apply those rules or validate a diagram, so it replaces the check
   > rather than implementing it. See the owner-facing comparison in the track research note
   > (`node-vs-java-docs-lint`, not part of the recipe). An owner who asks "why not Java" gets this answer; the
   > docs job stays separate from the build, so the build toolchain is unchanged.
2. **Style guide source.** Default: adapt the greenfield
   [`docs/STYLE_GUIDE.md`](../../greenfield/templates/docs/STYLE_GUIDE.md) (Diátaxis) to one page. The alternative
   (the owner's own house rules) is allowed only when those rules are not private to a different repository.
   Either way, the guide gains the "Plain language" and "Diagrams" sections (Steps 3) when DOC-05 is in the theme.
   A new guide also carries the form rules and the README landing-page rule (Steps 3). A guide that already exists
   gets them only by the owner's answer to Inputs 8.
3. **First ADRs.** Ask which two or three existing decisions to record. With no owner preference, pick them
   from the code and the existing docs, and say why you picked them. Good candidates: a schema-migration tool, a
   search or storage engine, an authentication or tenant-selection mechanism, a branch model.
4. **Architecture overview scope.** Default: modules or apps, entry points, data stores, one authentication or
   request flow, from the code index of this repository only.
5. **Instruction-file line.** One line names `docs/STYLE_GUIDE.md`, `docs/architecture/adrs/`, the ADR policy
   page and `docs/architecture/`. It goes in the section `agents_md.pointer_section` names. Without that
   preference, ask the owner where it goes and record the answer with `pref set agents_md.pointer_section`.
   The AGENTS.md theme (T7) reorganises the file later; tell it in the status that the line exists.
   Write the line as a plain list of pages, with no rule word such as must, never or only. With one, "`AGT-06`
   Architectural boundaries declared" reads it as a boundary rule. Never write "read ... first" on it either:
   "`AGT-10` Instruction indirection resolved" reads that as a deferral. Keep the line out of the prohibitions
   section, whose code spans "`CON-01` Allow/deny artifact present" reads.
6. **Prose check (DOC-05).** The framework has a stdlib Python template that checks the style guide's rules and can
   fail above a count: [`templates/docs_prose_check.py`](templates/docs_prose_check.py). It is code under the
   framework's own licence, and a copy never carries that licence. So flag the option, and offer two answers as a
   [decision request](../../audit/prompts/talking-to-the-user.md#decision-requests):
   - a. **Skip (default).** Add no tool. The `DOC-05` counts are recorded as debt (`docs.prose_check=skip`).
   - b. **Copy it under a licence the owner picks from this list:** `MIT`, `Apache-2.0` or `BSD-3-Clause`. These
     are the licences the template's copyright holder grants for a copy. Offer no other licence, and never the
     framework's own. When the owner wants another licence, record skip (a). Record `docs.prose_check=template` and
     `docs.prose_check_licence=<id>`. The copy needs Python 3.11 or newer where it runs, and
     `ci.edits_authorised` for the runner command and the CI step.
7. **NAV-03 findings.** The owner chooses per path: document (default), or skip as by-design. Moving or
   untracking a file is a separate owner decision and, for generated output, belongs to the
   [`untrack-generated`](untrack-generated.md) playbook.
8. **Form rules for an existing style guide** (`docs.style_guide_update`). Ask only when `docs/STYLE_GUIDE.md` already
   exists. One question, as a [decision request](../../audit/prompts/talking-to-the-user.md#decision-requests): append
   one section with the form rules to the owner's guide? a. `ask` (default): show the section in Steps 9, then record
   the owner's answer as `yes` or `no`; b. `yes`: append it in one commit; c. `no`: record the answer and change
   nothing. Record the answer with `pref set docs.style_guide_update`.
9. **Split a dense README** (`docs.split_readme`). Ask only when the root `README.md` has a dense section (Steps 10).
   One question, as a [decision request](../../audit/prompts/talking-to-the-user.md#decision-requests): move the dense
   sections of the README into `docs/` pages, one section per commit? a. `ask` (default): list the dense sections in
   Steps 10, then record the owner's answer as `yes` or `no`; b. `yes`: split, one section per commit; c. `no`: record
   the answer and change nothing. Record the answer with `pref set docs.split_readme`.

## Steps

### Generic

1. **Baseline.** List the Markdown files under `docs/`, in the root and in sub-folders. Count
   Markdown lint violations with the pinned linter on every tracked Markdown file (report only, nothing is
   fixed). Record the count, but it is a draft: the new pages add a few violations. So **measure the final baseline
   after the last new page**, and set it then. Stage the new pages first, since the report lists tracked files.
   The census numbers in the finding text are another thing to re-measure: a stale NAV-03 count usually comes from
   untracked data on disk, so count with `git ls-files`.
2. **Docs index (DOC-01).** If `docs/README.md` (or `index.md`) does not exist, write it: one paragraph on what
   `docs/` holds, a list of the pages with one line each, and the places to look for decisions
   (`docs/architecture/adrs/`) and the map (`docs/architecture/`). A frozen report folder from the first audit is
   listed in one line as "frozen first-audit report, not current"; it is not moved, edited or restructured. Use
   flat `docs/` plus `docs/architecture/` and `docs/architecture/adrs/`; do not impose a Diátaxis folder tree on a
   handful of files.
3. **Style guide (DOC-02).** Write `docs/STYLE_GUIDE.md`, one page: where permanent knowledge lives and where
   scratch lives, heading and table rules, line length (match the lint config), Mermaid in fenced blocks and
   validated before saving, relative links, "no values from env files, credentials or keystores", "cite code by
   path", "decisions go in `docs/architecture/adrs/`". Link to the lint config instead of restating its rules. Add
   the instruction-file line (Inputs 5) once the pages it names exist; [Commits](#commits) row 8 orders it. The
   check reads the literal string `STYLE_GUIDE.md`.

   **Plain language and diagrams (DOC-05).** Add two sections to the style guide. The template is the greenfield
   style guide: [§ 8 Plain Language](../../greenfield/templates/docs/STYLE_GUIDE.md#8-plain-language) and
   [§ 9 Diagrams](../../greenfield/templates/docs/STYLE_GUIDE.md#9-diagrams). They hold rules 1 to 6 of the
   framework's [communication rules](../../docs/COMMUNICATION_RULES.md#2-plain-language-rules) and the diagram rule,
   with the limits `DOC-05` measures (25 words, 20 in a step, the same vague words). Rules:
   - A style guide that already exists keeps its text. Add only the missing sections or rules, in the file's own
     heading style. A limit of its own (for example 30 words) stays; tell the owner how it differs from the check.
   - Keep the "before" example inside `<!-- prose-check off -->` and `<!-- prose-check on -->`, or the check counts
     it.
   - With a non-English `docs.language`, the owner supplies the rules in that language. `DOC-05` then reads
     `UNKNOWN`; record the item `partial` with
     `--debt "what=style rules the check cannot read (<language>),count=1"`.
   - Every page this theme writes follows the rules: the index, the style guide, the ADR policy page, the ADRs and
     the architecture page. Re-run the engine before the theme closes: `DOC-05` cites no line on those pages.

   **Form rules and the README landing page (a new style guide).** A guide that this step writes also carries two more
   greenfield sections:
   [§ 3.1 Form follows content](../../greenfield/templates/docs/STYLE_GUIDE.md#31-form-follows-content) and
   [§ 4.1 A README is a landing page](../../greenfield/templates/docs/STYLE_GUIDE.md#41-a-readme-is-a-landing-page).
   Adapt them to the target's heading style and docs layout. Keep the rule that the setup command and the
   single-test command stay in a root file, because `EXEC-03` and `TST-04` read them there. A guide that already
   exists gets these sections only through step 9.
4. **ADRs (DOC-04).** Create `docs/architecture/adrs/` with four parts:
   - `README.md`, the index: a table of number, title and a one-line summary, linking every file by its path.
   - `0000-template.md`, copied from the greenfield
     [`adr-template.md`](../../greenfield/templates/docs/templates/adr-template.md):
     Context, Decision, Alternatives Considered, Consequences. It has no status, date or decider fields.
   - An ADR policy page, adapted from the greenfield [`ADR_POLICY.md`](../../greenfield/templates/docs/ADR_POLICY.md).
     Keep its rules; replace its folder list and links with the target's. Name the page to fit the target's
     file names: `docs/ADR_POLICY.md` beside `docs/STYLE_GUIDE.md` by default, or `docs/adr-policy.md` where
     the docs use lower-case names. The instruction-file line names it (Inputs 5).
   - The first records, as `0001-short-title.md`.

   Rules:
   - Git is the archive: no record carries a status, a date or an approval line. The owner accepts the records
     by merging the branch, and edits or deletes one before that. The pull request body (or the status note,
     when no pull request is opened) lists each record under "What was not done", as waiting for the owner's
     review.
   - The engine matches the numbered-file pattern (three or four digits, hyphen, slug, `.md`). The template file
     `0000-template.md` counts as a numbered entry, so list it in the index too.
   - Context and Decision come from the code and the existing docs, with file paths. State plainly what is
     inferred. If the reason for a decision is not in the repository, write "Rationale not recorded; owner to
     fill in" and do not invent one.
5. **Architecture overview (NAV-01, NAV-02, NAV-04).** Re-index the repository with the code index. Write
   `docs/architecture/overview.md` from `get_architecture` and targeted `search_graph` / `trace_path` calls: the
   components and where each is declared, the entry points, the data stores, and one request or authentication
   flow. Add one Mermaid diagram, checked with the `mermaid-validator` MCP before saving. Cite files by path.
   Add `docs/architecture/README.md` only if the folder holds more than one page. For a component whose source
   is private, describe the dependency in one sentence with no path.
6. **NAV-03 census.** Count, from the tracked file list (`git ls-files`), the four categories the check counts: files
   over 512 KB, catch-all directories (`utils`, `misc`, `common`, `helpers` and similar with many files), binary files,
   minified assets. A lockfile is not a large file: the engine leaves it out. The engine's counts can include on-disk or
   generated files that git does not track, so re-measure by tracked paths and use the tracked list as the census. Write
   the paths in a "Repository notes" section of the architecture page, each tagged: generated, by design (a lock file,
   public images), or needs a decision. Do not move, untrack, resize or delete anything. Untracked runtime data
   directories are a separate, owner-recorded item (an `extra.*` preference) and are mentioned, not changed.
7. **Scratch (DOC-03).** If an `artefacts/` (or `artifacts/`) directory exists, confirm it is ignored and that
   `git ls-files artefacts` prints nothing. Add the ignore rule and `git rm --cached` only what is tracked
   there, and only after the owner confirms those files are scratch. "`CON-03` artefacts/ excluded from index and
   agent reads" reads the same rule and the tracked files under it. If no scratch directory exists, the check
   passes and nothing is created.
8. **Docs lint (needs `ci.edits_authorised`).**
   1. Write the lint config. Tune the rules to how the repository is already written (line length, allowed
      inline HTML, repeated sub-headings). `markdownlint-cli2` has no per-path rule overrides (an `overrides`
      key is silently ignored): where a folder needs different rules, use a nested config file in that folder.
      Template folders that must start with a non-heading line (rule MD041) are the usual case.
   2. Add the lint as a **ratchet**: the gating command lints a path list that only grows (the new docs plus any
      file that is already clean); a second command reports on every Markdown file and never fails. Neither
      command carries `--fix`: "`CMD-04` Write verbs separated from read-only verbs" fails on a writer under a
      read-only verb. Record the
      baseline count from step 1 (final value after the last render, see step 1) on the docs item it belongs to
      (`set-status F-nnn partial --debt "what=markdown lint violations,count=N,baseline=<lint script>"`), and keep
      the script's `BASELINE` constant and a `docs.lint_ratchet` preference equal to it. When no docs item is open,
      record the count in the `docs.lint_ratchet` preference and in the pull request, under "How it was checked".
   3. Add a separate CI job, path-filtered to changed Markdown, that runs the linter and renders every Mermaid
      block with `mmdc` (`--no-sandbox` in CI, cache the npm and Puppeteer directories keyed by the pinned
      versions). Pin both versions exactly; never use an unpinned `npx`. Put each pin in a manifest, such as the
      `devDependencies` of a root or tools `package.json`. The runner commands and the job (item 5 too) run each
      tool by name, never as `name@version`. So "`EXEC-08` Tool versions visible to
      dependency automation" finds every version in a manifest. If the repository already has Node,
      reuse the pinned `setup-node` step it uses elsewhere (same SHA and major version); otherwise leave setup out
      until a verified SHA exists. In a private repository, check out with `fetch-depth: 0` and diff the two
      commits locally: a `git fetch` fails there because `persist-credentials: false` leaves no token. Run the
      workflow linter on the changed workflow before pushing: a new job can turn the merge gate red through it.
      Check the repository's merge-gate job: a
      new job that must be green needs adding to it, which is the owner's call.
   4. If `lychee` was chosen: relative links only, report-only at first.
   5. **Prose check (only with `docs.prose_check=template`).** Copy the template to the place and name the
      repository uses for its scripts (D18), for example `scripts/docs_prose_check.py`. Replace its SPDX line with
      the licence the owner picked (`docs.prose_check_licence`). Keep the copyright line: the template's author keeps
      the copyright, and the owner gets the licence. Remove nothing else. Where the repository keeps a list of
      third-party code (a `THIRD_PARTY_NOTICES` file or similar), add the copy to it.
      Wire it as a ratchet, as for the lint. Both runs count warnings only (`--min-severity warning`): a sentence
      over 40 words, a step over 20, a vague word, a page without its diagram. A sentence of 26 to 40 words stays a
      notice, shown but not counted: a long sentence is often the clearest one (the framework's own
      [ADR 0004](../../docs/architecture/adrs/0004-plain-language-rules-and-a-prose-check.md) reversed a ratchet that
      counted them).

      - a runner command (`docs-prose` or the runner's own spelling) runs the copy with
        `--min-severity warning --max-issues 0` on the pages held clean: the pages this theme wrote, and any page
        that is already clean;
      - a second run on every Markdown page under `docs/` uses `--max-issues <baseline>`. Measure the baseline after
        the last render, with the new pages staged, as for the lint count;
      - if the explanation pages live elsewhere (for example `docs/architecture/`), pass `--diagram-dir` once per
        folder;
      - both runs go in the docs CI job from item 3. Use `--format github` there, so issues show on the pull request.
        A third run with no limit and no `--min-severity` shows the notices too, as advice;
      - keep both `--max-issues` numbers out of the root runner files (`package.json`, `Makefile`, `pyproject.toml`,
        `Taskfile.yml`). Put them in a small script
        that the runner command calls, beside the copy. "`BASE-02` Current violation counts measured" reads a
        `max-issues` number in those files as a code-quality budget. "`BASE-03` No-new-violations mechanism" then
        builds on that budget, so both could pass for the docs alone.

      Record the baseline (warnings) as debt on the `DOC-05` item, and in the `docs.prose_ratchet` preference.
9. **Style guide that already exists (`docs.style_guide_update`).** Run this step only when `docs/STYLE_GUIDE.md`
   existed before this theme, so step 3 did not write it. Make its commit right after step 3, before the lint
   baseline of step 1 is final: the new lines count there. Read the preference (Inputs 8):
   - `ask` (default): show the owner the section described below, then record the answer as `yes` or `no`.
   - `yes`: append the section in one commit (Commits row 4).
   - `no`: record the preference and change nothing. Do not ask again in this run.

   The section holds the form rules and the README landing-page rule. Adapt it from the greenfield
   [§ 3.1 Form follows content](../../greenfield/templates/docs/STYLE_GUIDE.md#31-form-follows-content) and
   [§ 4.1 A README is a landing page](../../greenfield/templates/docs/STYLE_GUIDE.md#41-a-readme-is-a-landing-page).
   Rules:
   - Append the section at the end of the file, in the file's own heading style and numbering. Never rewrite, reorder
     or renumber the owner's text.
   - Leave out a rule the guide already has. A limit of the owner's own stays; tell the owner how it differs.
   - Keep the rule that the setup command and the single-test command stay in a root file (`EXEC-03`
     non-interactive setup path, `TST-04` fast path documented).
   - The new lines follow the plain language rules of step 3, because `DOC-05` reads this page.
10. **Split a dense README (`docs.split_readme`).** This step is opt-in (Inputs 9). It moves text out of the root
    `README.md` and changes no fact. Make its commits before the lint config of step 8, so the baselines of step 1
    count the new pages. Read the preference first:
    - `ask` (default): list the dense sections, then record the owner's answer as `yes` or `no`.
    - `yes`: split, one section per commit (Commits row 11).
    - `no`: record the preference and change nothing. Do not ask again in this run.

    A section is dense when it has a paragraph of more than three sentences, or a table cell of more than one
    sentence. Leave the README's landing-page parts in place: what the project is, the setup command, how to start it,
    and links into `docs/`.
    1. **Pick the page type.** Move one section, by its content:
       - Deployment and operations go to a how-to page, from the greenfield
         [`how-to-template.md`](../../greenfield/templates/docs/templates/how-to-template.md).
       - Settings go to a reference page, from the greenfield
         [`reference-template.md`](../../greenfield/templates/docs/templates/reference-template.md).
       - Design and behaviour go to an explanation page, from the greenfield
         [`architecture-doc-template.md`](../../greenfield/templates/docs/templates/architecture-doc-template.md).

       Place the page in the target's own docs layout and name it as the target names its pages (D18). Do not impose
       a folder tree. A page named like a conventions file, or `docs/CONTRIBUTING.md`, is also read by "`AGT-13`
       Coding conventions written"; step 5 catches a changed verdict.
    2. **Audit before.** On a clean tree, run the engine and keep the report path:
       `python3 audit/tools/engine.py <worktree> --out-dir <dir outside the target> --no-user-config`. Use the same
       command for every run in this step. The after report of one section is the before report of the next.
    3. **Move the section.** Copy the text into the new page, in the page's own form. Leave a link table where the
       section was, with one row for each topic that moved: the topic and a relative link to the new page. Add the page
       to `docs/README.md` in the same commit.
    4. **Audit after, then compare.** Commit the section and run the same engine command again. Then run
       `python3 implement/tools/compare_reports.py <before report> <after report>`. Read the "Checks that moved"
       table. Expected: `None.`
    5. **Stop on a changed verdict.** Any row in that table stops the step. Revert the commit, or fix it in a new
       commit and audit again, before the next section. A verdict can stay while its evidence changes. So also
       compare the `summary` of three checks in the two JSON reports. They read README prose: "`HYG-01` README
       present and non-placeholder", "`BASE-03` No-new-violations mechanism" and "`BASE-04` Coverage floor
       configured". A changed summary stops the step too.
    6. **Check the commands by hand.** The comparison cannot catch one loss. `EXEC-06` documented commands resolve reads
       fenced commands in `README.md`, `AGENTS.md` and `CLAUDE.md` only. A command that moves to `docs/` leaves that
       scope. The `EXEC-06` verdict does not change, so the before-and-after audit shows nothing. Before each commit,
       list the fenced commands in the section. Check by hand that the first word of each still resolves. It is a
       verb, a script that exists, or a tool on the path. Tell the owner which commands now sit outside the check, in the
       pull request under "What changed".

    Rules:
    - Keep the setup command and the single-test command in a root file: `README.md`, `AGENTS.md` or `CONTRIBUTING.md`.
      `EXEC-03` non-interactive setup path reads fenced commands in `README.md`, `AGENTS.md`, `CLAUDE.md` and
      `CONTRIBUTING.md`. `TST-04` fast path documented reads the single-test command in the same four files. Neither
      reads `docs/`. Prefer `README.md` or `AGENTS.md`: "`EXEC-06` Documented commands resolve" reads fenced commands
      there, but not in `CONTRIBUTING.md`.
    - A fact in the section stays as written. If the section has a gap or a doubt, ask the owner. Rewording is not
      moving.
    - The new page follows the style guide: form follows content, and the plain language rules of step 3.

### Gradle and Quarkus

Profile: [`stacks/java.md`](../../audit/stacks/java.md#boundaries). Components: `settings.gradle` includes and the
module list for NAV-01; entry points: the `@QuarkusMain`, REST resource classes (`@Path`), the application
properties and the migration folder. Candidates for first ADRs: the schema-migration tool and where migrations
live, the search integration and its index, the tenant or authentication selection. The docs job is a separate
Node job; the Gradle build, wrapper and dependency set do not change.

### Node (npm, NestJS, React)

Profile: [`stacks/typescript-node.md`](../../audit/stacks/typescript-node.md#boundaries). Components: workspace or
per-app `package.json` files and compose service names; entry points: `main.ts`, the `start` script, the
compose file. In a per-app layout (`layout.command_runner`), put the lint config and the script at the root and
run the docs job once from there. For infrastructure folders, read the routing from the files that are actually
active (a gateway may enable its upstream rules per environment); say in the page what you could not verify.
The repository already has Node, so the job can reuse its pinned Node version.

## Commits

Docs first, then the lint config, then the wiring. The instruction-file line waits until the pages it names exist.

| # | Commit | Checks | Kind |
|---|---|---|---|
| 1 | Docs index, `docs/README.md` (only when missing) | `DOC-01` | hand |
| 2 | Style guide, `docs/STYLE_GUIDE.md` | `DOC-02` | hand |
| 3 | Plain language and Diagrams sections in the style guide (only for DOC-05) | `DOC-05` | hand |
| 4 | Form rules section appended to an existing style guide (only with `docs.style_guide_update=yes`) | `DOC-02` | hand |
| 5 | Decision log: `docs/architecture/adrs/` index, template, ADR policy page, first records | `DOC-04` | hand |
| 6 | Architecture overview with its diagram | `NAV-01`, `NAV-02`, `NAV-04` | hand |
| 7 | Repository notes section: the NAV-03 census | `NAV-03` | hand |
| 8 | Instruction-file line naming the docs pages | `DOC-02`, `DOC-04` | hand |
| 9 | Ignore rule for the scratch directory (only when one exists and lacks it) | `DOC-03` | config |
| 10 | Untrack the scratch files, `git rm --cached` (only those the owner confirms) | `DOC-03` | bulk |
| 11 | One dense README section moved to a `docs/` page, with a link table left behind (one commit per section; only with `docs.split_readme=yes`) | `DOC-01` | hand |
| 12 | Markdown lint config | - | config |
| 13 | Lint ratchet: the gating and report commands, with the baseline | - | wiring |
| 14 | Docs CI job: lint and Mermaid render | - | wiring |
| 15 | Link check in the docs CI job (only when the owner chose `lychee`) | - | wiring |
| 16 | Prose check copy with the owner's licence line (only with `docs.prose_check=template`) | `DOC-05` | bulk |
| 17 | Third-party notice entry for the copy (only where the repository keeps such a list) | `DOC-05` | hand |
| 18 | Prose ratchet: the runner command and the full-tree run (same condition as 16) | `DOC-05` | wiring |
| 19 | Prose runs in the docs CI job (same condition as 16) | `DOC-05` | wiring |

Two rows come before the step that would place them. Row 4 follows row 3, because step 9 runs right after step 3.
Row 11 follows the docs pages and the index, so each moved section joins `docs/README.md`. It comes before row 12,
so the lint and prose baselines (rows 13 and 18) count the new pages.

## Continue on error

- Markdown lint violations on existing files: counted at baseline, recorded as debt on the item (`partial`),
  held by the ratchet so the count cannot rise. Never mass-fix, reformat or suppress a rule to make the count
  fall unless the owner chooses that.
- Dead links (if `lychee` runs): counted, report-only.
- No Python 3.11 where the prose check must run: tell the owner, and fall back to `docs.prose_check=skip`.
- DOC-05 counts on pages the theme did not write: the long sentences, vague words and pages without a diagram
  stay. Record one debt entry per measure on the item (`partial`). The note names the worst pages, at most five,
  worst first, from the engine's cited lines. The owner decides on a rewrite (`extra.prose-rewrite`).
- A page the theme edits anyway (for example the docs index) joins the clean path list only when it passes the
  rules. Until then it stays in the debt count.
- NAV-03 census paths: recorded in the architecture page and the state note; the check keeps reading `PARTIAL`
  because the engine counts, it does not judge. Mark the item `partial` with
  `--debt "what=NAV-03 census paths,count=N"` and that reason in the note, or `skipped` if the owner calls it by
  design.
- An ADR the owner has not reviewed: listed in the pull request under "What was not done", or in the status note,
  as waiting for the owner. The owner edits, deletes or merges it.
- A docs job the merge gate cannot yet require: left advisory, noted for the CI theme.
- A changed verdict after a README section moved: the step stops at that section. Revert the commit, or fix it in a
  new commit and audit again. Sections already moved stay; the rest stay in the README. Say so in the pull request,
  under "What was not done".
- A dense section with a gap, a doubt or a fact that looks wrong: the section stays in the README, and the question
  goes to the owner. Move the next section.
- A section that holds the setup command or the single-test command: leave those commands in the root file. Move only
  the rest, or leave the section, and tell the owner why.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| DOC-01 | `git ls-files 'docs/*.md' 'docs/**/*.md'` | At least one file; `docs/README.md` links every page; no second docs home |
| DOC-02 | `test -f docs/STYLE_GUIDE.md` and `grep -n STYLE_GUIDE.md <instruction file>` | File exists; the instruction file names it |
| DOC-02 form rules | `grep -n -i 'form follows content\|landing page' docs/STYLE_GUIDE.md`; for an existing guide, `git diff --numstat <base> -- docs/STYLE_GUIDE.md` | New guide, or `yes`: both rules present, and an existing guide shows 0 deleted lines. `no`: 0 deleted lines, no added line holds either rule, and the preference recorded. Row 3 may still add lines to an existing guide |
| README split | After each section commit: `python3 implement/tools/compare_reports.py <before report> <after report>`; `git show --stat` | Only with `docs.split_readme=yes`. "Checks that moved" says `None.`. The commit adds one page and its `docs/README.md` row, and leaves a link table in the README. `EXEC-03` and `TST-04` still find their commands in a root file. `no`: no diff, and the preference recorded |
| DOC-05 | `grep -n -i 'plain language\|diagram' docs/STYLE_GUIDE.md`; the engine's DOC-05 | Both sections present; no cited line on a page this theme wrote; `PASS`, or `partial` with the counts as debt |
| DOC-03 | `git ls-files artefacts artifacts` and `git check-ignore -v artefacts/x` | No scratch directory, or nothing tracked and the rule matches |
| DOC-04 | List `docs/architecture/adrs/`; read `docs/architecture/adrs/README.md`; `grep -n -i 'adr' <instruction file>` | At least one numbered file; the index links every numbered file by path, the template included; the ADR policy page exists and the instruction file names it |
| NAV-01 | Read the components table in the overview | Every declared component listed with its manifest path |
| NAV-02 | Read the entry-points list | Each entry point is a real path (check with `test -f`) |
| NAV-03 | The "Repository notes" section | Every counted path is listed with a tag; nothing moved (`git status` shows only docs and config) |
| NAV-04 | `docs/architecture/overview.md` exists | Present, with a diagram that rendered |
| NAV-05 | The ratio the re-audit prints | Recorded; no source edited |
| Prose check | The runner's `docs-prose` command, then `head -2 <copy>` | Only with `docs.prose_check=template`: exit 0; the full-tree limit equals `docs.prose_ratchet`; the SPDX line is the owner's licence |
| Lint | The repository's docs lint command and the CI job | Zero violations in the ratchet path list; baseline total not higher than recorded |

## Rollback

`git revert` the commits, newest first. Revert the prose CI runs and the prose ratchet before the prose check copy.
Revert the docs CI job and the lint ratchet before the lint config. The instruction-file line goes with any docs
commit whose page it names. The appended section of row 4 reverts alone. Each README section of row 11 reverts alone:
the revert restores the section and removes the page and its index row. With the ratchets in place, measure the lint
and prose baselines again after that revert. The other commits revert alone. This
playbook moves, untracks and deletes nothing, except the README sections of step 10 and the scratch files in step 7,
both with owner consent. `git revert` returns them.

## Do-not-do

- Do not mass-reformat or mass-fix existing Markdown, and do not turn off a lint rule to make a count fall.
- Do not create a second `docs/` or restructure the existing report folders.
- Do not copy content, paths, names or values from a private repository or workspace into an open-source
  repository's docs or ADRs, or from any target repository into the framework.
- Do not invent the reason behind a decision. Say what is inferred, or write "Rationale not recorded; owner to
  fill in".
- Do not move, resize, delete or untrack files for NAV-03.
- Do not put values from env files, credentials, realm exports or keystores in any page. Such a value also fails
  "`SEC-02` No key-shaped strings in tracked files".
- Do not install a docs tool the owner has not approved, and do not use an unpinned `npx` in CI.
- Do not rewrite existing prose to lower the DOC-05 counts, even with `format.mass_reformat=yes`. Rewording can
  change meaning, unlike a reformat. A rewrite needs the owner to name the pages (`extra.prose-rewrite`), with one
  commit per page.
- Do not copy the prose check template unless the owner picked `MIT`, `Apache-2.0` or `BSD-3-Clause` for the copy.
  Never copy it under another licence, the framework's own included, and never remove or replace its copyright
  line.
- Do not add a status, date or approval line to an ADR. The owner's merge is the acceptance.
- Do not rewrite, reorder or renumber the text of an existing style guide. Append the form rules as one section, and
  only with `docs.style_guide_update=yes`. With `no`, do not touch the file.
- Do not move the setup command or the single-test command out of the root files `README.md`, `AGENTS.md` or
  `CONTRIBUTING.md`. `EXEC-03` non-interactive setup path and `TST-04` fast path documented read only `README.md`,
  `AGENTS.md`, `CLAUDE.md` and `CONTRIBUTING.md`, never `docs/`. `TST-04` reads the single-test command, not the setup
  command.
- Do not change a fact while moving a README section. Ask the owner about a gap.
- Do not split a README the owner answered `no` to (`docs.split_readme=no`), and do not move two sections in one
  commit.

## State updates

Beyond the shared lines in [Stage 3](../SKILL.md#stage-3-apply) (`in_progress`, the theme rows) and
[Stage 4](../SKILL.md#stage-4-close-the-theme) (the ending):

```bash
python3 implement/tools/progress.py set-status F-nnn done --workspace <workspace> --phase <phase> \
  --commit <sha> --verification-command "test -f docs/STYLE_GUIDE.md" \
  --verification-result "present; named in the instruction file"
python3 implement/tools/progress.py set-status F-nnn partial --workspace <workspace> --phase <phase> \
  --debt "what=markdown lint violations,count=<n>,baseline=<file>" --note "<mechanism>"
python3 implement/tools/progress.py set-status F-nnn partial --workspace <workspace> --phase <phase> \
  --commit <sha> --debt "what=long sentences in docs,count=<n>" --debt "what=vague words in docs,count=<n>" \
  --debt "what=docs pages without a diagram,count=<n>" \
  --note "style guide sections added; worst pages: docs/a.md (12), docs/b.md (9)"
python3 implement/tools/progress.py pref set docs.prose_check <skip|template> \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set docs.prose_check_licence <SPDX id> \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set docs.style_guide_update <ask|yes|no> \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set docs.split_readme <ask|yes|no> \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
python3 implement/tools/progress.py pref set docs.lint_tools <markdownlint-cli2+mmdc|none> \
  --workspace <workspace> --phase <phase> --reason "<the owner's words>" --by owner
```
