# Documentation Style Guide

> **Scope:** Governs all documentation under `brownfield-recipes/docs/`, and the engine docs under `brownfield-recipes/deterministic-audit/docs/` once the engine is migrated. Applies to human writers and AI documentation agents.
> **Standard:** [Diátaxis](https://diataxis.fr/) plus constraint-driven agent invariants.
> **Origin:** Adapted from the engine's style guide, which follows the greenfield template [`STYLE_GUIDE.md`](../../greenfield-bootstrap/templates/docs/STYLE_GUIDE.md). This file adds a Reference quadrant.
> **Enforcement:** The repository-root `AGENTS.md` (planned) MUST require compliance with this file. Link to these rules; never restate them elsewhere, because restated rules drift.

---

## 1. The 5 Core Invariants

1. **Single Source of Truth:** `docs/` is the sole canonical home for permanent knowledge about the recipes and their tools. `artefacts/` is transient scratch and is off-limits to automatic agent reading or indexing.
2. **Zero Specification Drift:** Code, recipes, schemas and docs MUST stay synchronized. Every behavioural change requires a matching doc update **in the same change set**.
3. **Empirical Grounding:** Never document planned features as existing facts. Every page that describes behaviour that does not exist yet MUST carry a `> [!NOTE] Planned.` line naming what is missing and the roadmap step that delivers it.
4. **Symbol Anchoring:** Reference code with explicit file paths. Once a file exists, link to its line anchors, for example `[report.py#L1-L40](../tools/report.py#L1-L40)`. While a file is planned, name it as a code span instead of linking to it.
5. **Living ADRs (Current-State Only):** An ADR MUST describe only the shipped, current design. When a decision changes, revise the ADR in place; when it becomes irrelevant, delete it. Git is the archive.

---

## 2. Writing Tones & Audiences

| Track | Audience | Focus | Tone |
|---|---|---|---|
| **Tutorials** | Newcomers | One guided, end-to-end success on a sample repo | Encouraging, step by step |
| **How-To** | Operators, engineers | One task, executable steps, verification | Direct, imperative |
| **Reference** | Everyone | Exact facts: tool CLIs, schemas, mappings, harness specifics | Dry, complete, scannable |
| **User Overview** (explanation) | CTOs, leads, adopters | Value, method, guarantees, limits | Executive, clear, concise |
| **Contributor Deep Dive** (explanation) | Engineers, maintainers | Mechanics, contracts, invariants, failure modes | Tactical, precise |
| **Agent Directives** | AI coding agents | Constraints, rules, mandatory steps | RFC 2119 (MUST, MUST NOT) |

Rules:
- User-overview pages MUST NOT descend into implementation internals; link to the contributor page instead.
- Contributor pages MUST ground every claim in a source file, schema field or check ID.
- How-to pages and tutorials MUST state prerequisites and an explicit verification step.
- Recipe files (`SKILL.md`, check files, playbooks) are Agent Directives. They live beside the recipes, not in `docs/`.

---

## 3. Formatting Standards

- **Headers:** ATX style (`#`, `##`, `###`), at most 4 levels.
- **Diagrams:** Mermaid. No external images when Mermaid can express it.
- **Alerts:** GitHub alerts (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`).
- **Tables:** GFM tables.
- **Blank lines:** one before and after headers, code blocks, tables and alerts.
- **Check references:** cite checks by catalogue ID (`EXEC-02`), never by prose description.
- **Requirement references:** cite requirements by ID (`REQ-BF-012`) once `spec/readiness-requirements.md` exists.

---

## 4. Document Types & Locations

Paths are relative to `brownfield-recipes/docs/`.

| Content type | Diátaxis quadrant | Location | Naming |
|---|---|---|---|
| This style guide | — | `STYLE_GUIDE.md` | `STYLE_GUIDE.md` |
| Doc router and ADR index | — | `architecture/README.md` | `README.md` |
| Glossary | Reference | `architecture/glossary.md` | `glossary.md` |
| Evaluator-facing explanations | Explanation | `architecture/user-overview/` | `NN-topic.md` |
| Engineer-facing explanations | Explanation | `architecture/contributor-deep-dive/` | `NN-topic.md` |
| Architectural Decision Records | Explanation | `architecture/adrs/` | `NNNN-short-title.md` |
| How-to guides | How-to | `how-to/` | `<task>.md` |
| Tutorials | Tutorial | `tutorials/` | `<topic>.md` |
| Reference pages | Reference | `reference/` | `<topic>.md` |
| Document templates | — | `templates/` | `<type>-template.md` |

New documents MUST start from the matching template in `templates/`.

---

## 5. Agent-Specific Writing Rules

### 5.1 Verification first

1. **Query-first:** where `codebase-memory-mcp` is available, use it to verify symbols and file locations before reading whole files.
2. Check existing pages in `docs/`; update rather than duplicate.
3. Check `architecture/adrs/` for the highest sequence number ever used before creating an ADR.

### 5.2 Doc Maintenance Trigger (definition of done)

When a change alters a tool's interface, a schema, a recipe stage, a check's semantics or the architecture:

1. Update every affected page and its source anchors.
2. Replace the `Planned` note on any page whose content now exists.
3. Update the ADR index in `architecture/README.md` when an ADR is added, revised or deleted.
4. Do all of the above **in the same change set** as the change.

### 5.3 Accuracy & status tagging

- Never state planned capabilities as working.
- Tag planned content: `> [!NOTE] Planned.` plus the roadmap step.
- Never document a check as implemented while it exists only in the catalogue.

---

## 6. ADR Lifecycle

ADRs live in `architecture/adrs/` and start from `templates/adr-template.md`.

1. **Create:** assign highest-ever sequence number + 1. Numbers of deleted ADRs are retired.
2. **Index:** add a row to `architecture/README.md` in the same change set.
3. **Revise in place:** overwrite the body, keep the number, and fold the reversal into *Alternatives Considered*.
4. **Delete when irrelevant**, and update every inbound reference in the same change set.

> [!IMPORTANT]
> There is no `Deprecated`, `Superseded` or `Rejected` status. A merged ADR is `Accepted`. `Proposed` is allowed in flight but MUST NOT be merged.

---

## 7. Content Boundaries

| Forbidden in `docs/` | Proper location |
|---|---|
| Agent plans, research drafts, scratch notes | `artefacts/` |
| Audit reports and run logs from real targets | The output directory chosen at run time |
| Recipe instructions, check rubrics, playbooks | `audit/`, `implement/`, `stacks/` (agent directives) |
| Executable rules and thresholds | Source code and `catalogue.json` |
| Secrets, tokens, environment values | `.env` (never committed) |
| Copied excerpts of framework pages | A relative link to the framework page and section |

> [!IMPORTANT]
> The framework (`brownfield-legacy/`, `shared/`, `spec/`) is the source of truth for *what* readiness means. These docs MUST link to it and MUST NOT restate it.
