# Documentation Style Guide

> **Scope:** Governs all documentation under `docs/`. Applies to both human writers and AI documentation agents.
> **Standard:** [Diátaxis Framework](https://diataxis.fr/) + Constraint-Driven Agent Invariants.
> **Enforcement:** [`AGENTS.md`](../AGENTS.md) §5.3 and §8 require compliance with this file. Link to these rules; never restate them elsewhere — restated rules drift.

---

## 1. The 5 Core Invariants

1. **Single Source of Truth:** `docs/` is the sole canonical home for permanent knowledge. `artefacts/` is transient scratch and is off-limits to automatic agent reading or indexing.
2. **Zero Specification Drift:** Code and architecture specs MUST remain synchronized. Every behavioral change requires a matching spec update **in the same change set**.
3. **Empirical Grounding:** Never document aspirational features as existing facts. All claims must be verifiable against source code or tests; planned work MUST carry an explicit notice banner.
4. **Symbol Anchoring:** Reference code symbols using fully-qualified names and explicit file paths with markdown links to source line anchors (e.g. `[orchestrator.ts#L37-L61](../src/core/orchestrator.ts#L37-L61)`).
5. **Current-State ADRs:** An ADR states only the current decision; git is the archive. The rules are in
   [`ADR_POLICY.md`](ADR_POLICY.md).

---

## 2. Writing Tones & Audiences

| Track | Audience | Focus | Tone |
|---|---|---|---|
| **User Overview** | Evaluators, Architects, CTOs | Value, capabilities, security, guarantees | Executive, clear, concise |
| **Contributor Deep Dive** | Engineers, Maintainers | Mechanics, data flow, invariants, failure modes | Tactical, technical, precise |
| **Agent Directives** | AI Coding Agents | Constraints, rules, mandatory steps | RFC 2119 (MUST, MUST NOT, REQUIRED) |

Rules:
- User-overview pages MUST NOT descend into implementation internals — link to the matching
  contributor page instead.
- Contributor pages MUST ground every claim in a source file or symbol.

---

## 3. Formatting Standards

- **Headers:** ATX style (`#`, `##`, `###`), maximum 4 levels deep.
- **Diagrams:** Use Mermaid; see §9. Do not embed external images when a Mermaid representation is possible.
- **Alerts:** Use GitHub-flavored Markdown alerts (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`).
- **Tables:** Use standard GFM tables with aligned headers for scannability.
- **Blank lines:** one blank line before and after headers, code blocks, tables, and alert blocks.

---

## 4. Document Types & Locations

| Content Type | Location | Naming |
|---|---|---|
| This style guide | `docs/STYLE_GUIDE.md` | `STYLE_GUIDE.md` |
| Architecture overview / explanations | `docs/architecture/` | `<topic>.md` |
| Architectural Decision Records | `docs/architecture/adrs/` | `NNNN-short-title.md` |
| ADR policy | `docs/ADR_POLICY.md` | `ADR_POLICY.md` |
| ADR index & doc router | `docs/architecture/README.md` | `README.md` |
| Domain glossary | `docs/architecture/glossary.md` | `glossary.md` |
| How-to guides | `docs/how-to/` | `<task>.md` |
| Tutorials | `docs/tutorials/` | `<topic>.md` |
| Reference (generated) | `docs/api/` | TypeDoc output — never hand-edited |
| Document templates | `docs/templates/` | `<type>-template.md` |

New documents MUST start from the matching template in `docs/templates/`.

---

## 5. Agent-Specific Writing Rules

### 5.1 Verification first

1. **Query-first:** consult `codebase-memory-mcp` (`search_graph`, `get_code_snippet`, `get_architecture`) to verify symbols and file locations against the current codebase before grepping or reading whole files.
2. Check existing pages in `docs/` — update rather than duplicate.
3. Before you add, change or delete an ADR, read [`ADR_POLICY.md`](ADR_POLICY.md).

### 5.2 Doc Maintenance Trigger (definition of done)

When a change alters a public interface, observable behaviour, architecture, or an ADR:

1. Run `detect_changes` on `codebase-memory-mcp`.
2. Update every affected documentation page and its source line anchors.
3. Update the ADR index in `docs/architecture/README.md` whenever an ADR is added, revised, or deleted.
4. Do all of the above **in the same change set** as the code change.

Pure internal refactors with no observable or documentation impact do not require doc edits.

### 5.3 Accuracy & status tagging

- Never state aspirational or planned capabilities as working code.
- Tag planned features explicitly: `> [!NOTE] Planned.`

---

## 6. ADRs

ADRs live in `docs/architecture/adrs/` and start from `docs/templates/adr-template.md`. How to add, change or
delete one: [`ADR_POLICY.md`](ADR_POLICY.md).

---

## 7. Content Boundaries (What Does NOT Belong in Docs)

| ❌ Forbidden in `docs/` | ✅ Proper location |
|---|---|
| In-progress agent plans, research drafts, scratch notes | `artefacts/` |
| Per-run execution logs and debug output | `.agentic-tdd/logs/` or the tool's own log directory |
| Hand-edited API signatures | `docs/api/` (generated) |
| Secrets, tokens, and environment values | `.env` (never committed) |

`artefacts/` is never an architectural source of truth and is excluded from the
`codebase-memory` index; see [`AGENTS.md` §4](../AGENTS.md).

---

## 8. Plain Language

Write for the reader that [`AGENTS.md`](../AGENTS.md) §8.1 names. These rules come from ASD-STE100 (Simplified
Technical English), without its fixed word list: technical names are fine. The audit check `DOC-05` measures
rules 2 and 6 over every page under `docs/`.

1. **Bottom line first.** Put the answer, the result or the decision in the first two lines.
2. **Short sentences.** At most 20 words in a step of a procedure. At most 25 words in other text.
3. **One instruction per sentence.** Write steps in the imperative: "Run the tests", not "You should run them".
4. **Active voice.** Say who does what: "The service reads the file", not "The file is read".
5. **One word, one meaning.** Use the same term every time. Do not change words for variety.
6. **No vague or padded words.** Do not write `simply`, `just`, `obviously`, `clearly`, `basically`, `easily`,
   `utilize`, `leverage`, `in order to`, `and/or` or `etc.`. Name the real items instead of `etc.`.

Example (the "before" text breaks rules 2, 4 and 6 on purpose, so the check skips it):

<!-- prose-check off -->

> Before: In order to ensure that the build is green, it is recommended that the tests are run by the
> contributor prior to the proposal of a change.
>
> After: Run the tests before you propose a change.

<!-- prose-check on -->

---

## 9. Diagrams

A diagram often explains a flow faster than text. Every page under `docs/explanation/` and `docs/tutorials/`
(an index page excepted) has at least one Mermaid diagram. Pick the type by what you show:

| You show | Mermaid type |
|---|---|
| Steps and choices in a process | `flowchart` |
| Who calls whom, in order | `sequenceDiagram` |
| The states of one thing and how it moves between them | `stateDiagram-v2` |
| Data shapes and how they relate | `classDiagram` or `erDiagram` |

- Keep a diagram to about 12 nodes. Split a larger one.
- Write one sentence before the diagram that says what it shows.
- Validate every block before you commit it: render it with the Mermaid CLI, or a Mermaid validator.
