# Agent Governance (`AGT`)

> Follows the anatomy in [`README.md`](README.md). This is the second file of the family, with `AGT-12` and
> `AGT-13`: the first, [`02-agent-governance.md`](02-agent-governance.md), reached the 500-line budget
> ([§5 of the README](README.md#5-one-family-one-file)).

## AGT-12 — Communication rules stated

Why it matters   Agents report to people and ask them for decisions; without written rules each agent
                  picks its own layout and the reader digs for the bottom line
                  ([greenfield/README.md § 5.2 Templates & Guides](../../greenfield/README.md#52-templates--guides)).
Severity         COSMETIC
Engine           `AGT-12`. Reads the entry instruction file for a section headed `communication`, `how to
                 write`, `writing for people`, `reporting` or `talking to the user` (not in a fence), and
                 for a Markdown file it links or code-spans whose name contains `communicat`. The rules
                 must name the reader (`reader`, `audience`, `write for`, `new engineer`), how to report
                 (`report`, `status`, `summary`, `bottom line`) and how to ask for a decision (`decision`,
                 `recommend`, `trade-off`). Distrust a `FAIL` when the rules sit in a linked file with
                 another name: read the link.
Method           automated
Look for         The instruction file's headings, then each file its documentation section links.
Rubric           PASS: the rules exist and name the reader, how to report and how to ask for a decision.
                 PARTIAL: one or two of the three are missing, or a named rules file does not exist.
                 FAIL: no section and no named rules file.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no instruction file exists to read (`AGT-01` already owns that absence).
Evidence to cite A `file` item for each section (its heading line) and each named rules file, with `note`.
Absence proof    A FAIL records `grep` searches for the heading and the file-name patterns, scoped to the
                 instruction file; a PARTIAL, one per missing element, scoped to the rules.
Remediation      `adapt-agents-md`
Pitfalls         Presence, not quality: rules that name the three in passing still pass; judge generic
                 text under `AGT-11`. The rules are for English; a team writing in another language states
                 its own.

## AGT-13 — Coding conventions written

Why it matters   An agent cannot infer the naming, layering and error rules that no tool enforces; without
                 them it writes code its own way, and review catches it late
                 ([REQ-SH-062](../../spec/readiness-requirements.md#req-sh-062--coding-conventions-written)).
Severity         COSMETIC
Engine           `AGT-13`, implemented. Finds each conventions file and each conventions section, then reads
                 them together for the five items and for a stub word.
Method           automated
Look for         A file whose name matches `CONVENTIONS*`, `*convention*`, `CODE_STYLE*`, `CODING_STANDARDS*`
                 or `*coding-guidelines*`, in any case, at the root or anywhere under `docs/` or `.github/`.
                 It is prose: `.md`, `.markdown`, `.mdx`, `.txt`, `.rst`, `.adoc` or no extension. Then a
                 section of the root `AGENTS.md`, or of `CONTRIBUTING.md` at the root or in `.github/` or
                 `docs/`. A section opens at a heading of level 2 to 6, outside a fence, that says
                 `conventions`, `code style`, `coding standards` or `naming`. A heading that also says `git`,
                 `commit`, `branch`, `pull request`, `release`, `docs`, `documentation`, `writing` or `prose`
                 is about other work and does not count. The section runs to the next heading of its level or
                 a higher one, so its subsections belong to it. `docs/STYLE_GUIDE.md` never counts: it holds
                 the rules for documentation, not for code. Whether Aider reads `CONVENTIONS.md` does not matter.
Rubric           PASS: the conventions cover naming, layering, error handling and logging, and testing, and
                 link the formatter or linter config.
                 PARTIAL: conventions exist but lack one or more items, or hold a stub word.
                 FAIL: no conventions file and no conventions section.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never; no other check owns this absence.
Evidence to cite A `file` item for each conventions file (line 1) and each section (its heading line), and
                 one for each stub word, with `note`.
Absence proof    A FAIL records the `AGENTS.md` and `CONTRIBUTING.md` read with no conventions section; the
                 file-name patterns found no file. A PARTIAL names each missing item.
Remediation      `adapt-agents-md`
Pitfalls         Presence, not quality: a word in passing covers an item. The items are counted over all
                 sources together, and a stub word in any one gives `PARTIAL`. The words are English.

The engine reads each item from these words, case-insensitive. They cover the Java, Node and Python stack
profiles in [`audit/stacks/`](../stacks/README.md).

| Item | Words that show it |
|---|---|
| Naming | `naming`, `camelCase`, `PascalCase`, `snake_case`, `kebab-case`, `PEP 8` |
| Layering | `layer`, `layering`, `architecture`, `boundary`, `what goes where`, `package structure`, `project layout`, `may import`, `may call`, `controller`, `hexagonal`, `ports and adapters` |
| Error handling and logging | One error word (`error`, `exception`, `throw`, `raise`) and one logging word (`log`, `logging`, `logger`, `SLF4J`, `Log4j`, `Logback`, `winston`, `pino`) |
| Testing | `test`, `tests`, `testing`, `JUnit`, `pytest`, `unittest`, `Jest`, `Vitest`, `Mocha` |
| Formatter or linter config | `.editorconfig`, `.prettierrc`, `prettier.config.*`, `biome.json`, `eslint.config.*`, `.eslintrc`, `pyproject.toml`, `ruff.toml`, `setup.cfg`, `.flake8`, `.pylintrc`, `checkstyle*.xml`, `pmd*.xml`, `spotless` |

A stub word is `TBD` or `TODO` in upper case, as a whole word, outside a code span or a fenced block.
