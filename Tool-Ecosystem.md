# Tool Ecosystem

[[_TOC_]]

## Methodology vs. Tooling

> [!IMPORTANT]
> The methodology described in this wiki stands on its own. A team can follow the [phased approach](Phased-Approach.md) manually without any of the tools listed below. The tools **accelerate adoption** but are not prerequisites.

The agentic-ready approach has two distinct layers:

```mermaid
graph TB
    subgraph "Methodology (tool-agnostic)"
        subgraph "Part I: Readiness Foundation (Required)"
            M1["Phase 1: Bootstrap"]
            M2["Phase 2: Source-Level Docs"]
            M3["Phase 3: Agent-Oriented Docs"]
            M4["Phase 4: Contracts & Baselines"]
        end
        subgraph "Part II: Post-Readiness Roadmap (Agent-Driven)"
            M5["Phase 5: Refactoring (Optional)"]
            M6["Phase 6: Human Docs"]
            M7["Phase 7: Spec-Driven Dev"]
        end
    end

    subgraph "Tooling (accelerators)"
        T1["codebase-memory-mcp"]
        T2["agentic-tdd"]
        T3["agentic-docstrings"]
        T4["agentic-agentDocs"]
        T5["agentic-contracts"]
        T6["agentic-characterize"]
        T7["agentic-repoDocs"]
    end

    T1 -.-> M1
    T1 -.-> M2
    T1 -.-> M3
    T1 -.-> M4
    T1 -.-> M5
    T1 -.-> M6
    T1 -.-> M7
    T2 -.-> M5
    T2 -.-> M7
    T3 -.-> M2
    T4 -.-> M3
    T5 -.-> M4
    T6 -.-> M4
    T7 -.-> M6
```

A well-prepared codebase should give exceptional results with **any** coding agent — Claude Code, Cursor, OpenCode, Goose — and of course with `agentic-tdd` too.

---

## Tool Maturity

| Tool | Status | Phase | Description |
|------|--------|-------|-------------|
| `codebase-memory-mcp` | ✅ Available | 1–7 | Core intelligence layer. Indexes symbols, relationships, dependencies, tests, contracts. Queried by all phases. |
| `agentic-tdd` | ✅ Available | 5 | Supports controlled, test-driven feature development and refactoring with AI agents. |
| `agentic-docstrings` | 📋 Planned | 2 | Will generate and maintain source-level documentation (docstrings, parameter descriptions, side effects). |
| `agentic-agentDocs` | 📋 Planned | 3 | Will create structured, agent-oriented documentation and task-specific context packs. Currently in conceptualisation. |
| `agentic-contracts` | 💡 Aspirational | 4 | Will generate and validate API contracts, event schemas, and consumer-provider relationships. |
| `agentic-characterize` | 💡 Aspirational | 4 | Will produce characterization tests and golden-master baselines for existing behavior. |
| `agentic-repoDocs` | 💡 Aspirational | 6 | Will create human-facing repository documentation following the Diátaxis model. The manually created docs  `agentic-tdd` can be found [`here`](https://github.com/Nistapp/agentic-tdd/tree/main/docs). `agentic-repoDocs` will automate this process in the future.|

### Maturity Legend

| Badge | Meaning |
|-------|---------|
| ✅ Available | Existing, usable today |
| 📋 Planned | Actively planned for near-term development |
| 💡 Aspirational | Conceptual; development has not started |

### Tool Maturity Map

```mermaid
graph TB
    subgraph "✅ Available"
        T1["codebase-memory-mcp\n(Phase 1–7)"]
        T2["agentic-tdd\n(Phase 5)"]
    end
    subgraph "📋 Final stages of design"
        T3["agentic-docstrings\n(Phase 2)"]
    end
    subgraph "💡 Aspirational"
        T4["agentic-agentDocs\n(Phase 3)"]
        T5["agentic-contracts\n(Phase 4)"]
        T6["agentic-characterize\n(Phase 4)"]
        T7["agentic-repoDocs\n(Phase 6)"]
    end

    style T1 fill:#2d6a4f,stroke:#1b4332,color:#fff
    style T2 fill:#2d6a4f,stroke:#1b4332,color:#fff
    style T3 fill:#e9c46a,stroke:#f4a261,color:#000
    style T4 fill:#264653,stroke:#2a9d8f,color:#fff
    style T5 fill:#264653,stroke:#2a9d8f,color:#fff
    style T6 fill:#264653,stroke:#2a9d8f,color:#fff
    style T7 fill:#264653,stroke:#2a9d8f,color:#fff
```

---

## Shared Conventions

All tools will be published as independent open-source npm packages, each focused on a single responsibility. They will share common conventions for:

- **Configuration** — consistent config file formats and defaults.
- **Reporting** — structured output with provenance metadata.
- **Verification** — each tool validates its own output before committing.
- **Integration** — all tools query and update `codebase-memory-mcp`.

---

← [Home](README.md) · [Phased Approach](Phased-Approach.md) · [Risks and Mitigations](Risks-and-Mitigations.md)
