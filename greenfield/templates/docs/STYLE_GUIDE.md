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
- **Diagrams:** Use Mermaid (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`). Do not embed external images when a Mermaid representation is possible.
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
