# Playbook: `establish-docs-contract`

> Theme T6 (documentation contract and navigation). Follows the anatomy in [`README.md`](README.md). Written in
> IR09.1; applied and corrected on a Gradle/Quarkus repository (IR09.2) and a multi-app Node repository (IR09.3).

## Goal

An agent finds permanent knowledge in one place: `docs/` has an index, a short style guide that the instruction
file names, a decision log with a template and an index, and a short architecture page with a diagram that was
checked. Scratch work stays out of version control. Structural traps (very large files, binaries) are listed,
not moved.

## Checks resolved

| Check | Rubric | What this playbook does for it |
|---|---|---|
| DOC-01 | [03-documentation-contract.md](../../audit/checks/03-documentation-contract.md#doc-01--docs-exists) | Confirms `docs/` holds Markdown, adds `docs/README.md` as the index; never creates a second docs home |
| DOC-02 | [03-documentation-contract.md](../../audit/checks/03-documentation-contract.md#doc-02--docsstyle_guidemd-exists) | Adds a one-page `docs/STYLE_GUIDE.md` and one line in the instruction file that names it |
| DOC-03 | [03-documentation-contract.md](../../audit/checks/03-documentation-contract.md#doc-03--artefacts-exists-and-is-ignored) | Verifies the scratch directory rule; adds the ignore rule only if a scratch directory exists |
| DOC-04 | [03-documentation-contract.md](../../audit/checks/03-documentation-contract.md#doc-04--adr-directory-and-index) | Adds `docs/adr/` with a template, an index and two or three first records marked `proposed` |
| NAV-01 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-01--declared-component-boundaries) | Verification only: lists the declared components in the architecture page |
| NAV-02 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-02--obvious-entry-points) | Verification only: names the entry points in the architecture page |
| NAV-03 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-03--structural-red-flags) | Census of oversized files, catch-all directories, binaries and minified assets; document, never move |
| NAV-04 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-04--architecture-orientation-artifact-informational-unscored) | Writes `docs/architecture/overview.md` from the code index, with one validated Mermaid diagram |
| NAV-05 | [11-navigation.md](../../audit/checks/11-navigation.md#nav-05--public-symbol-documentation-coverage-informational-unscored) | Verification only: records the ratio; no code is edited |

DOC-03, NAV-01 and NAV-05 had no confirmed finding in the two repositories this playbook was first applied to.
They stay here so a repository that has one has a procedure, and so the re-audit reads them.

## Preconditions

- The state file exists and Stage 1 triage is done ([`SKILL.md`](../SKILL.md#stage-1-triage)). Read it first and
  respect every `skipped` item and preference. Never re-propose a rejected or skipped finding (for example a
  rejected NAV-02).
- Preferences this playbook reads, when present: `format.mass_reformat` (a `no` means every docs check is a
  baseline or ratchet, never a reformat), `layout.command_runner`, `ci.edits_authorised` (needed to add the docs
  CI job), `agents_md.pointer_section` (where the one instruction-file line goes), `extra.*`.
- **Run the drift check first** ([`check_drift.py`](../../docs/reference/tools-cli.md)). A finding that says
  "no `docs/` directory" can be stale: an earlier theme or an audit-report commit may have created `docs/`. The
  engine passes DOC-01 on any Markdown file under `docs/`, so the report folders alone make it pass. Mark such a
  finding `done` with the drift as the reason, and add the index to the folder that exists. Never create a
  second `docs/`. The same goes for any number a phase text or finding statement quotes (sizes, counts, "340 MB
  in the tree"): re-measure on the current default branch before acting.
- No earlier theme is needed. If the command-surface theme named a docs verb, reuse it in the lint step.
- **Public/private boundary.** If the target is open source, everything written here comes from that repository's
  own code and files. Never copy content, paths, names or values from a private sibling repository or a private
  workspace into it. A private model may be mentioned by description only (no path, no hostname).

## Inputs to ask

1. **Docs tooling.** Detect first: an existing Markdown linter config (`.markdownlint*`, `.remarkrc*`), a docs
   job in CI, a link checker. Use what exists. If none, offer this set (the framework's default, STATE D6) and
   the owner decides. Currency checked 2026-10-30 (npm registry, GitHub releases API); re-check when applied.

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
2. **Style guide source.** Default: adapt the framework's
   [`brownfield-recipes/docs/STYLE_GUIDE.md`](../../docs/STYLE_GUIDE.md) (Diátaxis) to one page. The alternative
   (the owner's own house rules) is allowed only when those rules are not private to a different repository.
3. **First ADRs.** Ask which two or three existing decisions to record. If the owner has no preference, pick them
   from the code and the existing docs (a schema-migration tool, a search or storage engine, an authentication
   or tenant-selection mechanism, a branch model) and say why you picked them. Mark each `proposed`.
4. **Architecture overview scope.** Default: modules or apps, entry points, data stores, one authentication or
   request flow, from the code index of this repository only.
5. **Instruction-file line.** One line naming `docs/STYLE_GUIDE.md`, `docs/adr/` and `docs/architecture/`,
   placed beside the existing pointer line (section per `agents_md.pointer_section`). The AGENTS.md theme (T7)
   reorganises the file later; tell it in the status that the line exists.
6. **NAV-03 findings.** The owner chooses per path: document (default), or skip as by-design. Moving or
   untracking a file is a separate owner decision and, for generated output, belongs to the
   [`untrack-generated`](untrack-generated.md) playbook.

## Steps

### Generic

1. **Baseline.** Run the drift check. List the Markdown files under `docs/`, in the root and in sub-folders. Count
   Markdown lint violations with the pinned linter on every tracked Markdown file (report only, nothing is
   fixed). Record the count, but it is a draft: `progress.py render` adds a generated state view that is itself
   Markdown with a few violations, and so do the new pages, so **measure the final baseline after the last render**
   (with the new pages staged, since the report lists tracked files) and set it then.
   The census numbers in the finding text are another thing to re-measure: a stale NAV-03 count usually comes from
   untracked data on disk, so count with `git ls-files`.
2. **Docs index (DOC-01).** If `docs/README.md` (or `index.md`) does not exist, write it: one paragraph on what
   `docs/` holds, a list of the pages with one line each, and the places to look for decisions
   (`docs/adr/`) and the map (`docs/architecture/`). A frozen report folder from the first audit is listed in
   one line as "frozen first-audit report, not current"; it is not moved, edited or restructured. Use flat
   `docs/` plus `docs/architecture/` and `docs/adr/`; do not impose a Diátaxis folder tree on a handful of
   files.
3. **Style guide (DOC-02).** Write `docs/STYLE_GUIDE.md`, one page: where permanent knowledge lives and where
   scratch lives, heading and table rules, line length (match the lint config), Mermaid in fenced blocks and
   validated before saving, relative links, "no values from env files, credentials or keystores", "cite code by
   path", "decisions go in `docs/adr/`". Link to the lint config instead of restating its rules. Add the
   instruction-file line (Inputs 5). The check reads the literal string `STYLE_GUIDE.md`.
4. **ADRs (DOC-04).** Create `docs/adr/` with `README.md` (the index: a table of number, title, status, one
   line each, linking every file by its path), `0000-template.md` (adapted from the greenfield
   [`adr-template.md`](../../../greenfield-bootstrap/templates/docs/templates/adr-template.md): Status, Date,
   Context, Decision, Alternatives considered, Consequences) and the first records as `0001-short-title.md`.
   Rules:
   - Status is `proposed` until the owner accepts; the owner changes it. This differs from the greenfield
     template (which forbids merging `Proposed`): a retrospective record whose rationale the agent inferred
     must say so on its face.
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
6. **NAV-03 census.** Count, from the tracked file list (`git ls-files`), the four categories the check counts:
   files over 512 KB, catch-all directories (`utils`, `misc`, `common`, `helpers` and similar with many files),
   binary files, minified assets. The engine's counts can include on-disk or generated files that git does not
   track, so re-measure by tracked paths and use the tracked list as the census. Write the paths in a "Repository
   notes" section of the architecture page, each tagged: generated, by design (a lock file, public images), or
   needs a decision. Do not move, untrack, resize or delete anything. Untracked runtime data directories are a
   separate, owner-recorded item (an `extra.*` preference) and are mentioned, not changed.
7. **Scratch (DOC-03).** If an `artefacts/` (or `artifacts/`) directory exists, confirm it is ignored and that
   `git ls-files artefacts` prints nothing. Add the ignore rule and `git rm --cached` only what is tracked
   there, and only after the owner confirms those files are scratch. If no scratch directory exists, the check
   passes and nothing is created.
8. **Docs lint (needs `ci.edits_authorised`).**
   1. Write the lint config. Tune the rules to how the repository is already written (line length, allowed
      inline HTML, repeated sub-headings). `markdownlint-cli2` has no per-path rule overrides (an `overrides`
      key is silently ignored): where a folder needs different rules, use a nested config file in that folder.
      Template folders that must start with a non-heading line (rule MD041) are the usual case.
   2. Add the lint as a **ratchet**: the gating command lints a path list that only grows (the new docs plus any
      file that is already clean); a second command reports on every Markdown file and never fails. Record the
      baseline count from step 1 (final value after the last render, see step 1). `progress.py` has no field for
      lint debt on the docs items, so it lives in three places: the script's `BASELINE` constant, a `docs.lint_ratchet`
      preference, and the status file. Put the `partial` note on the nearest finding (NAV-03) or say so in the PR;
      a note can only be added when the item moves to a status, so set it in the same call that sets `partial`.
   3. Add a separate CI job, path-filtered to changed Markdown, that runs the linter and renders every Mermaid
      block with `mmdc` (`--no-sandbox` in CI, cache the npm and Puppeteer directories keyed by the pinned
      versions). Pin both versions exactly; never use an unpinned `npx`. If the repository already has Node,
      reuse the pinned `setup-node` step it uses elsewhere (same SHA and major version); otherwise leave setup out
      until a verified SHA exists. In a private repository, check out with `fetch-depth: 0` and diff the two
      commits locally: a `git fetch` fails there because `persist-credentials: false` leaves no token. Run the
      workflow linter on the changed workflow before pushing: a new job can turn the merge gate red through it.
      Check the repository's merge-gate job: a
      new job that must be green needs adding to it, which is the owner's call.
   4. If `lychee` was chosen: relative links only, report-only at first.
9. **Verify and commit.** Lint every new and changed Markdown file, validate every Mermaid block, run the
   repository's gate. Commit per logical change (docs, then lint config, then CI), each revertible alone.

### Gradle and Quarkus

Profile: [`stacks/java.md`](../../stacks/java.md#boundaries). Components: `settings.gradle` includes and the
module list for NAV-01; entry points: the `@QuarkusMain`, REST resource classes (`@Path`), the application
properties and the migration folder. Candidates for first ADRs: the schema-migration tool and where migrations
live, the search integration and its index, the tenant or authentication selection. The docs job is a separate
Node job; the Gradle build, wrapper and dependency set do not change.

### Node (npm, NestJS, React)

Profile: [`stacks/typescript-node.md`](../../stacks/typescript-node.md#boundaries). Components: workspace or
per-app `package.json` files and compose service names; entry points: `main.ts`, the `start` script, the
compose file. In a per-app layout (`layout.command_runner`), put the lint config and the script at the root and
run the docs job once from there. For infrastructure folders, read the routing from the files that are actually
active (a gateway may enable its upstream rules per environment); say in the page what you could not verify.
The repository already has Node, so the job can reuse its pinned Node version.

## Re-recording preferences

An earlier owner-answers commit on a side branch (the docs preferences from the brief pass) conflicts with the state
JSON as soon as the default branch has moved. Do not cherry-pick it; re-record the preferences with `progress.py
pref set --by owner` quoting the owner's words. Close earlier themes the state still shows `pr_open` although their
PRs are merged (`progress.py theme Tn --status merged --pr <n> --merged-sha <sha>`). `theme T6 --status pr_open`
needs `--pr`, so open the PR before the final state commit. `git add` named paths, never `commit -a`.

## Continue on error

- Markdown lint violations on existing files: counted at baseline, recorded as debt on the item (`partial`),
  held by the ratchet so the count cannot rise. Never mass-fix, reformat or suppress a rule to make the count
  fall unless the owner chooses that.
- Dead links (if `lychee` runs): counted, report-only.
- NAV-03 census paths: recorded in the architecture page and the state note; the check keeps reading `PARTIAL`
  because the engine counts, it does not judge. Mark the item `partial` with that reason, or `skipped` if the
  owner calls it by design.
- A proposed ADR the owner has not accepted: stays `proposed`, listed in the status file as waiting for the
  owner.
- A docs job the merge gate cannot yet require: left advisory, noted for the CI theme.

## Verification

| Check | Command or file | Expected |
|---|---|---|
| DOC-01 | `git ls-files 'docs/*.md' 'docs/**/*.md'` | At least one file; `docs/README.md` links every page; no second docs home |
| DOC-02 | `test -f docs/STYLE_GUIDE.md` and `grep -n STYLE_GUIDE.md <instruction file>` | File exists; the instruction file names it |
| DOC-03 | `git ls-files artefacts artifacts` and `git check-ignore -v artefacts/x` | No scratch directory, or nothing tracked and the rule matches |
| DOC-04 | List `docs/adr/`; read `docs/adr/README.md` | At least one numbered file; the index links every numbered file by path, the template included |
| NAV-01 | Read the components table in the overview | Every declared component listed with its manifest path |
| NAV-02 | Read the entry-points list | Each entry point is a real path (check with `test -f`) |
| NAV-03 | The "Repository notes" section | Every counted path is listed with a tag; nothing moved (`git status` shows only docs and config) |
| NAV-04 | `docs/architecture/overview.md` exists | Present, with a diagram that rendered |
| NAV-05 | The ratio the re-audit prints | Recorded; no source edited |
| Lint | The repository's docs lint command and the CI job | Zero violations in the ratchet path list; baseline total not higher than recorded |

## Rollback

`git revert` the commits: docs, lint config and CI job each revert alone. Nothing was moved, untracked or
deleted by this playbook except, with owner consent, the scratch files in step 7 (`git revert` returns them to the
index).

## Do-not-do

- Do not mass-reformat or mass-fix existing Markdown, and do not turn off a lint rule to make a count fall.
- Do not create a second `docs/` or restructure the existing report folders.
- Do not copy content, paths, names or values from a private repository or workspace into an open-source
  repository's docs or ADRs, or from any target repository into the framework.
- Do not invent the reason behind a decision. Inferred means "proposed" and says it is inferred.
- Do not move, resize, delete or untrack files for NAV-03.
- Do not put values from env files, credentials, realm exports or keystores in any page.
- Do not install a docs tool the owner has not approved, and do not use an unpinned `npx` in CI.
- Do not accept an ADR on the owner's behalf.

## State updates

Through [`progress.py`](../../docs/reference/tools-cli.md#progresspy), on the theme branch, `--phase` the
current step:

```bash
python3 brownfield-recipes/tools/progress.py set-status F-nnn in_progress --target <repo> --phase <phase>
python3 brownfield-recipes/tools/progress.py set-status F-nnn done --target <repo> --phase <phase> \
  --commit <sha> --verification-command "test -f docs/STYLE_GUIDE.md" \
  --verification-result "present; named in the instruction file"
python3 brownfield-recipes/tools/progress.py set-status F-nnn partial --target <repo> --phase <phase> \
  --debt "what=markdown lint violations,count=<n>,baseline=<file>" --note "<mechanism>"
python3 brownfield-recipes/tools/progress.py pref set docs.lint_tools <markdownlint-cli2+mmdc|none> \
  --target <repo> --phase <phase> --reason "<the owner's words>" --by owner
python3 brownfield-recipes/tools/progress.py theme T6 --status branch_open \
  --branch agentic-readiness/<phase>-docs --target <repo> --phase <phase> --render
```

Only the owner skips an item. A stale finding resolved by drift is `done` with the reason, not `skipped`.
