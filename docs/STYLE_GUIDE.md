# Documentation style guide

This page tells you how to write a documentation page in this repository. It applies to people and AI agents.

- **What it covers:** every page under `docs/`, the engine docs under `audit/engine/docs/`, the docs under
  `audit/docs/` and `implement/docs/`, and the root pages (`README.md`, `CONTRIBUTING.md`, `RELEASE_PROCESS.md`).
- **What it does not cover:** recipe files (`SKILL.md`, checks, playbooks, prompts). They are agent directives;
  see section 2.
- **Wording rules:** [`COMMUNICATION_RULES.md`](COMMUNICATION_RULES.md) sections 1 to 3 hold the reader ladder, the
  plain-language rules and the diagram rules. Section 2.1 adds rules for rung 0 and rung 1 pages. This page adds
  only the rules for documentation pages. It links to those rules and does not repeat them, because a copied rule
  drifts.
- **Structure:** [Diátaxis](https://diataxis.fr/). Each page is one of four kinds: tutorial, how-to guide,
  reference or explanation.

## 1. Five rules for every page

1. **One home for each fact.** `docs/` holds permanent knowledge about the recipes and their tools. `artefacts/`
   holds temporary notes. Agents do not read `artefacts/` unless a person gives them a path in it.
2. **Docs change with the code.** When a change alters behaviour, update the docs in the same change set.
3. **Describe only what exists.** Some pages describe a feature that is not built yet. Such a page carries the
   line `> [!NOTE] Planned.`, followed by what is missing and the roadmap step that delivers it.
4. **Point to the source.** Name the file. Once the file exists, link to it, with line anchors where they help.
   Example: `[report.py#L1-L40](../audit/tools/report.py#L1-L40)`. While a file is planned, write its name as a
   code span and do not link to it.
5. **An ADR describes the current design only.** The rules are in [`ADR_POLICY.md`](ADR_POLICY.md).

## 2. Kinds of page and their readers

| Kind | Reader | Rung | What it gives | Tone |
|---|---|---|---|---|
| Front page (the first screen of `README.md`) | A decision maker | 0 | The problem, what the reader gets, one fact that backs it | Plain, calm, no jargon |
| Tutorial | A newcomer | 1 | One guided success from start to end, on a sample repository | Encouraging, step by step |
| How-to guide | An engineer with a task | 1 | The steps for one task, and how to check the result | Direct, imperative |
| User overview (explanation) | A lead or an adopter | 1 | Value, method, guarantees and limits | Short and clear |
| Reference | Everyone | 2 | Exact facts: tool options, schemas, mappings, harness details | Dry, complete, easy to scan |
| Contributor deep dive (explanation) | A maintainer | 2 or 3 | How it works: contracts, rules, failure modes | Precise |
| Agent directive | An AI coding agent | 3 | Rules and required steps | RFC 2119 words (MUST, MUST NOT) |

The rungs are the reader ladder in [`COMMUNICATION_RULES.md`](COMMUNICATION_RULES.md) section 1.1.

Rules:

- A rung 0 or rung 1 page follows the extra rules in `COMMUNICATION_RULES.md` section 2.1.
- A user-overview page does not go into implementation detail. It links to the contributor page instead.
- A contributor page backs each claim with a source file, a schema field or a check ID.
- A how-to guide and a tutorial state the prerequisites and end with a step that checks the result.
- Agent directives (`SKILL.md`, check files, playbooks) live beside the recipes, not in `docs/`.

## 3. Plain language and diagrams on a page

The rules are in [`COMMUNICATION_RULES.md`](COMMUNICATION_RULES.md) sections 2 and 3. On a documentation page, also:

- **Start with what the page is for.** The first paragraph says what the reader gets and who it is for.
- **A diagram on every explanation page and tutorial.** `dev/prose_check.py` checks this (rule `PL003`).
- **A diagram in a how-to guide** when the task has more than about five steps, or a choice between paths.
- **Define a term on first use,** or link it to [`docs/glossary.md`](glossary.md).
- **Keep a page to one topic.** When a page grows past about 300 lines, split it.

`make docs-prose FILES=<file.md>` runs the prose check. It reports warnings and notices and never fails.
CI shows them as annotations on the pull request.

## 4. Format

- **Headings:** ATX style (`#`, `##`, `###`), at most four levels.
- **Diagrams:** Mermaid, not images, when Mermaid can draw it. Validate each block with
  `make docs-mermaid FILES=<file.md>`.
- **Alerts:** GitHub alerts (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`).
- **Tables:** GitHub tables.
- **Blank lines:** one before and one after each heading, code block, table and alert.
- **Line length:** at most 120 characters in prose (`.markdownlint-cli2.jsonc`).
- **Checks:** cite a check by its catalogue ID, for example `EXEC-02`, not by a description. A rung 0 or
  rung 1 page names the check in words and links the page that holds the ID.
- **Requirements:** cite a requirement by its ID, for example `REQ-SH-022`, from
  [`spec/readiness-requirements.md`](../spec/readiness-requirements.md).

## 5. Form follows content

Choose the form from the kind of content, not from habit. A reader scans a table or a diagram faster than a long
paragraph.

### 5.1 The form for each kind of content

| Content | Form | Example |
|---|---|---|
| Steps in a fixed order | Numbered steps, each with a check | Install the skills, cut a release |
| Rules people cite in review | Nested numbers: `## 2.`, `### 2.1`, `2.1.1`, then `a.` | `AGENTS.md`, a style guide |
| Rules that vary along one axis | A table | Tool to what it checks; path to its rules |
| A flow or a decision | A Mermaid diagram | Audit to implement; `dev` to `main` |
| A reason or an edge case | A `[!NOTE]` alert or a `<details>` block | Why a check is unscored |
| A warning that breaks things | A `[!IMPORTANT]` alert | "Never edit the master lists by hand" |
| A setting | A one-line table row, with a link to numbered details | A tool option |

5.1.1 A lettered item (`a.`) is one full sentence: a capital first, a full stop last. End every lettered line but
the last with a backslash (`\`), so each item renders on its own line. Use a table when the items share columns.

5.1.2 A table cell holds one line. Longer text goes into numbered details below the table.

5.1.3 A paragraph holds at most three sentences. More than that becomes numbered items or a table.

5.1.4 Some files keep their own shape: ADRs ([`ADR_POLICY.md`](ADR_POLICY.md)), glossaries, tutorials, the
changelog and the issue templates.

5.1.5 An existing page changes to this form only when it is touched for another reason.

### 5.2 A README is a landing page

5.2.1 A repository's root `README.md` holds four things: what the project is, the setup command, how to start it,
and links into `docs/`. A folder's `README.md` is an index page, like the router in [`README.md`](README.md).

5.2.2 The root README keeps the setup command. Two engine checks look for it in the root files, never in `docs/`:
`EXEC-03` non-interactive setup path and `TST-04` fast path documented. They read `README.md`, `AGENTS.md`,
`CLAUDE.md` and `CONTRIBUTING.md`.

5.2.3 Everything else moves to `docs/`, by kind of page (section 2):\
a. Deployment and operations go to a how-to guide.\
b. Settings go to a reference page.\
c. Design and behaviour go to an explanation page.

5.2.4 A section that moves leaves a link table behind in the README, so old readers still find it.

5.2.5 The first screen of the root README is a rung 0 page (section 2). The setup command (5.2.2) stays in the
README, in a "Try it" block below the first screen.

## 6. One home for each rule

Rule 1 in section 1 gives each fact one home. This section names the home of each rule that people and agents
read most. Every other file links to the home and does not restate the rule.

6.1 **The exception.** `AGENTS.md` is the one file an agent is sure to read. A harness may not follow its links
(`AGT-10` instruction indirection resolved). So `AGENTS.md` keeps what an agent needs in every session: the
commands, the boundaries and the never-rules. It links for the rest.

6.2 **The ownership map.**

| Topic | Home | Other files |
|---|---|---|
| Commands (setup, gate, one test) | `AGENTS.md`, "Commands"; the user's setup also in `README.md` | `CONTRIBUTING.md` explains them for people |
| Never-rules and boundaries | `AGENTS.md`, "Boundaries" and "Never", and each folder's `AGENTS.md` | No copies |
| Branches, commits, pull requests | `CONTRIBUTING.md` | `AGENTS.md` keeps what an agent may not do, and links |
| Promotion and releases | `RELEASE_PROCESS.md` | `CONTRIBUTING.md` and `AGENTS.md` link |
| Code conventions | Each folder's `AGENTS.md`; format and lint rules in `ruff.toml` | The root `AGENTS.md` links |
| Writing rules | This page (pages) and [`COMMUNICATION_RULES.md`](COMMUNICATION_RULES.md) (wording) | `AGENTS.md` keeps a summary |
| Definition of done | `AGENTS.md`, "Definition of done" | `CONTRIBUTING.md` links |
| Configuration and deployment | `docs/` pages (section 5.2) | `README.md` links |

6.3 **Why some homes are fixed.** Two checks read `AGENTS.md`:\
a. `AGT-04` definition of done stated needs the rule there, so it never moves out.\
b. `AGT-12` communication rules stated needs a section on writing for people, or a link to a rules file.

6.4 **Existing copies.** A page that still restates a rule from another home follows this map when it is next
touched (5.1.5).

## 7. Where each page goes

Paths are relative to `docs/`.

| Content | Kind | Location | File name |
|---|---|---|---|
| This style guide | — | `STYLE_GUIDE.md` | — |
| Documentation index (the router) | — | `README.md` | — |
| Architecture map and ADR index | — | `architecture/README.md`, `architecture/adrs/README.md` | `README.md` |
| Repository decisions (ADRs) | Explanation | `architecture/adrs/` | `NNNN-short-title.md` |
| Glossary | Reference | `glossary.md` | — |
| Pages for leads and adopters | Explanation | `explanation/user-overview/` | `NN-topic.md` |
| Pages for maintainers | Explanation | `explanation/contributor-deep-dive/` | `NN-topic.md` |
| How-to guides | How-to | `how-to/` | `<task>.md` |
| Tutorials | Tutorial | `tutorials/` | `<topic>.md` |
| Reference pages | Reference | `reference/` | `<topic>.md` |
| Page templates | — | `templates/` | `<kind>-template.md` |

- Start a new page from its template in `templates/`.
- Decisions about one component live beside that component, for example `audit/engine/docs/architecture/adrs/`.
  [ADR 0001](architecture/adrs/0001-decisions-live-beside-the-component.md) gives the rule.

## 8. What the tools check

| Tool | What it checks | Where it must be clean |
|---|---|---|
| `markdownlint-cli2` | Markdown format | `DOCS_LINT_PATHS` in the `Makefile` |
| `dev/prose_check.py` | Sentence length, vague words, diagrams on explanation pages | Nowhere: advisory warnings and notices |
| `dev/mermaid_check.py` | Each Mermaid block renders | The files you pass to `make docs-mermaid` |
| `dev/recipe_lint.py` | Links resolve inside the repository | Recipes, `docs/` and the root pages |
| `dev/recipe_paths.py` | A repository path in backticks still exists | The recipe pages and every `AGENTS.md` |
| `dev/adr_lint.py` | Every ADR follows [`ADR_POLICY.md`](ADR_POLICY.md) and is indexed; no page names a missing ADR | The ADR folders, their indexes and every Markdown page |

`DOCS_LINT_PATHS` is a ratchet: a page joins once it is clean, and the list only grows. Outside the list, the
total count of Markdown issues may not go up (`.quality-baseline.json`). When you edit a page outside the list, fix
its issues and add it to the list. The prose check has no list and no count. Fix its warnings on the lines you
edit.

## 9. Agents writing docs

1. Where `codebase-memory-mcp` is available, use it to check symbols and file paths before you read whole files.
2. Look for an existing page first. Update it; do not write a second page on the same topic.
3. Before you add, change or delete an ADR, read [`ADR_POLICY.md`](ADR_POLICY.md).

Some changes alter a tool's interface, a schema, a recipe stage, what a check means or the architecture. For such a
change, do all of this in the same change set:

1. Update every page it affects, and the source links on those pages.
2. Remove the `Planned` note from each page whose content now exists.
3. Update the ADR index when you add, change or delete an ADR.

## 10. ADR lifecycle

[`ADR_POLICY.md`](ADR_POLICY.md) holds every ADR rule: numbering, the index, changing and deleting. ADRs start from
[`templates/adr-template.md`](templates/adr-template.md).

## 11. What does not go in `docs/`

| Not in `docs/` | Where it goes |
|---|---|
| Agent plans, research drafts, scratch notes | `artefacts/` |
| Audit reports and run logs from real repositories | The output folder chosen when the audit runs |
| Recipe steps, check rubrics, playbooks | `audit/`, `implement/` (agent directives) |
| Rules and thresholds that code runs | Source code and `audit/catalogue.json` |
| Secrets, tokens, environment values | `.env`, never committed |
| Copies of framework text | A relative link to the framework page and section |

> [!IMPORTANT]
> The framework (`docs/framework/`, `greenfield/`, `spec/`) says *what* readiness means. Other pages link to it.
> They do not repeat it.
