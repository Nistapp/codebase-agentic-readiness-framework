# Making a Legacy Codebase Agentic-Ready (Brownfield Track)

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

## The 4-Phase Migration Structure

The Brownfield track is organized into two distinct parts:
1. **Part I: Agentic-Readiness Foundation (Phases 1–4)** — The mandatory, sequential roadmap to make an existing repo safe, discoverable, and deterministic.
2. **Part II: Post-Readiness Roadmap & Execution (Phases 5–7)** — High-value workflows (refactoring, human-facing docs, spec-driven feature development) accelerated *by* agents once readiness is achieved.

👉 **[Read the Full Phased Approach Guide](Phased-Approach.md)**

---

## Track Navigation

| Page | Description |
|------|-------------|
| **[Phased Approach](Phased-Approach.md)** | Detailed breakdown of all 7 phases with deliverables and maturity badges |
| **[Core Overview](../shared/Overview.md)** | Constraint Engineering, assumptions, and foundational principles |
| **[Tool Ecosystem](../shared/Tool-Ecosystem.md)** | Accelerators, tooling maturity status, and conventions |
| **[Risks & Mitigations](../shared/Risks-and-Mitigations.md)** | Known risks when introducing agents into legacy systems |
| **[Glossary](../shared/Glossary.md)** | Definitions of key terms |

---

← [Home (Dual-Track Router)](../README.md) · [New Project Initialization Recipe →](../greenfield-bootstrap/README.md)
