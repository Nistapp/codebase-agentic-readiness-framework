# Risks and Mitigations

> [!NOTE]
> This section captures known risks when adopting agentic workflows in codebases. It will be expanded as the tooling matures and real-world patterns emerge.

## Risk Matrix

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| R1 | `Minor`: **Stale documentation** — Generated docs drift from the code they describe. | Agents operate on outdated context, producing incorrect changes. (This is minor in our context as `agentic-tdd` also has a documentation agent to ensure up-to-date-ness.) | Re-running documentation tools as part of CI can be a good practice.|
| R2 | **Hallucinated docstrings** — Agent-generated documentation contains unsupported claims about business logic or security. | False assumptions propagate into downstream agent decisions. | Conservative generation rules: avoid business/security claims without evidence. Human review of initial generation. |
| R3 | **Over-reliance on characterization tests** — Teams treat behavioral baselines as proof of correctness. | Existing bugs become enshrined as "expected behavior." | Characterization tests should be explicitly labeled as *behavioral baselines, not correctness proofs*. Pair with intentional specification. |
| R4 | **Agents weakening tests** — An agent modifies or removes tests to make its code changes pass. | Silent regression; the safety net is removed. | Independent verification: tests and security checks run in a separate, agent-inaccessible pipeline. Constraint Engineering deny lists for test directories. |
| R5 | **Constraint erosion** — Allow/deny lists become overly permissive over time as teams take shortcuts. | Agent blast radius expands silently; spaghettification returns. | Periodic audit of constraint configurations. Treat constraint files as reviewed infrastructure, not developer convenience. |
| R6 | **Context pack incompleteness** — The context pack misses a critical dependency or side effect. | Agent produces code that compiles but breaks an undiscovered integration. | Use `codebase-memory-mcp` comprehensively. Run impact analysis before plan approval. Add missing relationships when discovered. |
| R7 | **Tool immaturity** — Several tools in the ecosystem are planned or aspirational, not yet available. | Teams may adopt the methodology expecting tooling that does not yet exist. | [tool maturity status](Tool-Ecosystem.md). The methodology is valuable even with manual execution of some phases. |
| R8 | **False confidence** — Teams assume agent-produced code is correct because it passed quality gates. | Subtle logic errors or security issues may slip through automated checks. | Human review remains necessary for high-risk changes. Quality gates increase probability but do not guarantee correctness. |

## General Principle

> [!IMPORTANT]
> These tools improve the **probability** of accurate work but do not **guarantee** correctness. Human review remains necessary for high-risk changes.

---

← [Home](../README.md) · [Legacy Phased Approach](../brownfield-legacy/Phased-Approach.md) · [Tool Ecosystem](Tool-Ecosystem.md)
