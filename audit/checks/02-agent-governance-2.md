# Agent Governance (`AGT`)

> Follows the anatomy in [`README.md`](README.md). This is the second file of the family: the first,
> [`02-agent-governance.md`](02-agent-governance.md), reached the 500-line budget
> ([§5 of the README](README.md#5-one-family-one-file)).

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
