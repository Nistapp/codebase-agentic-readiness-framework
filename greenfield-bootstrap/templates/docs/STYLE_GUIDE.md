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
5. **Living ADRs (Current-State Only):** An ADR MUST describe only the shipped, current codebase. When a decision changes, revise the ADR body **in place**; when an ADR becomes irrelevant, delete it. Git is the archive — never keep tombstone, superseded, or deprecated stubs.

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
3. Check `docs/architecture/adrs/` for the highest sequence number ever used before creating an ADR.

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

## 6. ADR Lifecycle

ADRs live in `docs/architecture/adrs/` and are created from `docs/templates/adr-template.md`.

```markdown
# NNNN. Short Title

* **Status:** Accepted
* **Date:** YYYY-MM-DD
* **Last reviewed:** YYYY-MM-DD
* **Deciders:** [@github-handle]

## Context
[Technical context, problem statement, alternatives considered.]

## Decision
[Chosen architecture, pattern, or dependency, with links to source interfaces.]

## Consequences
### Positive
* [Benefit]

### Negative / Trade-offs
* [Trade-off]
```

1. **Create:** assign `highest-ever sequence number + 1`. A number whose ADR was deleted is retired and MUST NOT be reused.
2. **Record:** use `docs/templates/adr-template.md`.
3. **Index:** add a row to the index table in `docs/architecture/README.md` in the same change set.
4. **Revise in place:** when a decision changes, overwrite the ADR body and keep its number. Fold the reversal into the ADR's own *Alternatives considered* table. Do NOT create a second "superseding" ADR and do NOT leave a tombstone stub. Use `git log --follow` to recover older wording.
5. **Delete when irrelevant:** when an ADR no longer describes anything in the current codebase, delete the file and update every inbound reference in the same change set. Feature-level deprecation belongs in the glossary or roadmap, never as a lingering ADR.

> [!IMPORTANT]
> There is no `Deprecated`, `Superseded`, or `Rejected` status. A merged ADR is always `Accepted` (`Proposed` is allowed in-flight but MUST NOT be merged). Stale instructions pollute agent context, so staleness is treated as a defect, not as history.

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
