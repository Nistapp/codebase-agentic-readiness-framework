# Glossary

| Term | Definition |
|------|------------|
| **Agentic-Ready** | A codebase state where AI coding agents can safely discover, modify, and verify code within well-defined boundaries. |
| **Constraint Engineering** | The practice of defining and enforcing explicit boundaries (allow/deny lists, mandatory analysis steps) to prevent agents from making uncontrolled or unintended changes. A proactive safety mechanism. |
| **Context Pack** | A task-specific bundle of information (symbols, callers, callees, tests, contracts, architecture decisions) assembled for an agent before it begins work. Replaces "dump the whole repo" approaches. |
| **Characterization Test** | A test that records what the system *currently does*, regardless of whether that behavior is correct or desirable. Used as a behavioral baseline to detect unintended changes. |
| **Golden-Master Test** | A form of characterization test that captures the full output of a system or component and compares future outputs against this "golden" reference. Also called an approval test. |
| **Context Engineering** | The discipline of selecting, structuring, and delivering the right information to an LLM at the right time to maximize accuracy and minimize wasted reasoning. |
| **Spaghettification** | When an agent makes entangled, cross-cutting changes across unrelated components — the agentic equivalent of spaghetti code. |
| **Context Bloat** | Providing an agent with excessive, unfocused context that exhausts its reasoning budget and degrades output quality. |
| **Specification Drift** | When implementation gradually diverges from the original specification because neither is updated to reflect changes in the other. |
| **Quality Gate** | An automated, deterministic check (lint, typecheck, test, security scan) that code must pass before proceeding. |
| **Impact Analysis** | The process of determining what components, symbols, tests, and contracts are affected by a proposed change — ideally performed *before* code generation begins. |
| **Allow/Deny List** | Explicit configuration that specifies which files, directories, methods, interfaces, or commands an agent is permitted or forbidden to touch. |
| **SDD** | Specification-Driven Development — writing and maintaining a specification as the source of truth that drives implementation. |
| **BDD** | Behavior-Driven Development — expressing requirements as executable scenarios (Given/When/Then) that serve as both documentation and tests. |
| **TDD** | Test-Driven Development — writing failing tests before implementation code, then making them pass. |
| **Diátaxis** | A documentation framework that organizes content into four categories: tutorials, how-to guides, reference, and explanation. |
| **Provenance** | Metadata that records how, when, and from what evidence a piece of generated documentation or code was produced. |
| **ADR** | Architecture Decision Record — a document capturing the context, decision, and consequences of a significant architectural choice. |
| **`codebase-memory-mcp`** | The core intelligence layer that indexes and queries source code symbols, relationships, dependencies, and documentation. Used by every phase of the agentic-ready process. |
| **`agentic-tdd`** | An available tool that supports controlled, test-driven feature development and refactoring with AI agents. |

---

← [Home](../README.md)
