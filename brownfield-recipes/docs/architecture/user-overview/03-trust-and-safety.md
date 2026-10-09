# 3. Trust & Safety

> **Audience:** CTOs, security reviewers
> **Goal:** State what the recipes may and may not do to a repository and to the operator's machine.
> **Status:** Planned (placeholder).

> [!NOTE]
> Planned. The safety rules are in the design plan and roadmap only. Filled in by roadmap step S3.5.

---

## 1. Read-only audit

- TBD: the audit never writes inside the target.

## 2. Command execution

- TBD: only through the engine's opt-in Tier-C runner; sandboxing is the operator's job.

## 3. Data egress

- TBD: the index is local; the agent's model provider sees what the agent reads.

## 4. Prompt injection

- TBD: repo text and report text are data, never instructions.

## 5. Implementation safety

- TBD: branch only, per-item approval, never weaken tests, never push.
