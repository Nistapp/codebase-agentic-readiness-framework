# [Component / Stage Name]

> **Audience:** Engineers & Architects
> **Related ADRs:** [ADR-NNNN](../architecture/adrs/NNNN-title.md)
> **Status:** Planned — not yet implemented.

---

## 1. Responsibilities & Boundaries

- **Primary Goal:** [Summary of what this component solves]
- **In-Scope:** [Explicit responsibilities]
- **Out-of-Scope:** [What this stage does not do — especially writes it must never perform]

---

## 2. Component Diagram

```mermaid
flowchart TD
    Client["Client / Entrypoint"] --> Stage["Audit Stage"]
    Stage --> Report["Report Writer"]
```

---

## 3. Interfaces & Contracts

| Interface | File | Description |
|---|---|---|
| `<interface>` | `<path>` | <description> |

---

## 4. Invariants & Failure Modes

- Invariant 1: ...
- Failure Mode: ...
