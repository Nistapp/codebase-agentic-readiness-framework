# Documentation Style Guide

> **Scope:** Governs all documentation under `docs/`. Applies to both human writers and AI documentation agents.
> **Standard:** [Diátaxis Framework](https://diataxis.fr/) + Constraint-Driven Agent Invariants.

---

## 1. The 5 Core Invariants

1. **Single Source of Truth:** `docs/` is the sole canonical home for permanent knowledge. Agent scratchpads in `artefacts/` are transient.
2. **Zero Specification Drift:** Code and architecture specs MUST remain synchronized. Every behavioral change requires a matching spec update. (TODO: This is still aspirational. We will fix this in future versions of agentic-tdd)
3. **Empirical Grounding:** Never document aspirational features as existing facts. All claims must be verifiable against source code or tests.
4. **Symbol Anchoring:** Reference code symbols using fully-qualified names and explicit file paths with markdown links.
5. **Permanent ADR History:** Never delete or silently rewrite an accepted ADR. Use tombstone stubs when an ADR is superseded.

---

## 2. Writing Tones & Audiences

| Track | Audience | Focus | Tone |
|---|---|---|---|
| **User Overview** | Evaluators, Architects, CTOs | Value, capabilities, security, guarantees | Executive, clear, concise |
| **Contributor Deep Dive** | Engineers, Maintainers | Mechanics, data flow, invariants, failure modes | Tactical, technical, precise |
| **Agent Directives** | AI Coding Agents | Constraints, rules, mandatory steps | RFC 2119 (MUST, MUST NOT, REQUIRED) |

---

## 3. Formatting Standards

- **Headers:** ATX style (`#`, `##`, `###`), maximum 4 levels deep.
- **Diagrams:** Use Mermaid (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`). Keep nodes clean and descriptive.
- **Alerts:** Use GitHub-flavored Markdown alerts (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`).
- **Tables:** Use standard GFM tables with aligned headers for scannability.

---

## 4. ADR Lifecycle

1. **Create:** Assign the next 4-digit sequence number (`docs/architecture/adrs/000X-short-title.md`).
2. **Record:** Use `docs/templates/adr-template.md`.
3. **Index:** Add the ADR to the index table in `docs/architecture/README.md`.
4. **Supersede:** If obsolete, update status to `Superseded by [ADR-YYYY]` and replace the body with the tombstone stub. (TODO: We should refine this since we are working in Git and this is confusing to the agent.)
