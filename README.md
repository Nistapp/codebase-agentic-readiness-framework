# Making a Legacy Codebase Agentic-Ready

> *"The more you sweat in peace, the less you bleed in war."*
> In our context, **sweating in peace** is preparing the codebase for agentic participation. **The war** is when agents are implementing features from user prompts — and an unprepared codebase bleeds rework, hallucinations, and broken builds.

## TL;DR

Legacy codebases contain valuable business logic but lack the structure AI coding agents need to work safely. This guide presents a **phased, incremental approach** to making any codebase agentic-ready — without requiring a full rewrite. The methodology is **tool-agnostic**: a well-prepared codebase yields better results with *any* coding agent (Claude Code, Cursor, OpenCode, Goose, `agentic-tdd`, and others).

The ultimate goal: follow **SDD/BDD + TDD with confidence** to deploy agent-assisted code in production.

---

## Business Case

> [!IMPORTANT]
> The following outcomes are directional expectations based on early experience with `agentic-tdd` in well-structured projects. Formal benchmarks are pending.

| Outcome | Mechanism |
|---------|-----------|
| **Reduced agent rework cycles** | Focused context packs prevent agents from reasoning over irrelevant code. Fewer discarded responses and retry loops. |
| **Lower defect escape rate** | Automated quality gates, contracts, and characterization tests catch unintended behavioral changes before merge. |
| **Faster developer onboarding** | Generated source-level and repository documentation reduces reliance on tribal knowledge. |
| **Agent-agnostic investment** | The preparation benefits *all* coding agents and human developers equally — no vendor lock-in. |
| **Controlled blast radius** | Constraint Engineering enforces explicit boundaries on what agents can and cannot touch, reducing spaghetti edits across unrelated components. |
| **Production confidence** | The phased approach builds toward SDD/BDD + TDD workflows that meet the bar for production deployment. |

While `agentic-tdd` has been fairly performant in well-structured projects, it needs help in legacy/brownfield codebases that have drifted from best practices. We saw an opportunity to **increase accuracy and reduce spaghettification** by preparing the codebase for agentic participation.

---

## Documentation Navigation

| Page | Description |
|------|-------------|
| **[Overview](Overview.md)** | Core concepts, Constraint Engineering, assumptions, and applicability |
| **[Phased Approach](Phased-Approach.md)** | All 7 phases with deliverables, diagrams, and maturity badges |
| **[Tool Ecosystem](Tool-Ecosystem.md)** | Tools, maturity status, and methodology vs. tooling separation |
| **[Risks and Mitigations](Risks-and-Mitigations.md)** | Known risks when adopting agentic workflows |
| **[Glossary](Glossary.md)** | Definitions of key terms used throughout this guide |
| **[References](References.md)** | Related reading, frameworks, and external resources |

---

## Quick Context

- **Applicability**: Monoliths and monorepos. Microservices are not explicitly excluded but have not been validated yet.
- **Core intelligence layer**: [`codebase-memory-mcp`](https://github.com/nicobailon/codebase-memory-mcp) — used by every phase to identify symbols, dependencies, callers, callees, tests, contracts, and related documentation.
- **Methodology**: The approach is independent of any specific agent or tool. The tooling ecosystem accelerates adoption but is not a prerequisite.

---

## License

This documentation is licensed under the [GNU Free Documentation License, Version 1.3](LICENSE).
