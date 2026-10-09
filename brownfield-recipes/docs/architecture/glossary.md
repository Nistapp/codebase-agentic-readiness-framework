# Glossary

Canonical definitions of terms used by the brownfield recipes. Terms from the readiness framework are cited, not redefined; see [`shared/Glossary.md`](../../../shared/Glossary.md).

> [!NOTE]
> Planned. Definitions are provisional until the step that introduces each term ships.

---

| Term | Definition |
|---|---|
| Recipe | A Markdown instruction document (`SKILL.md`) that a coding agent executes. |
| Audit recipe | The read-only recipe that produces the audit report. |
| Implementation recipe | The recipe that applies confirmed findings on a branch. |
| Engine | The deterministic, standard-library Python audit in `deterministic-audit/`. |
| Tool | A deterministic script in `tools/` that follows the tool contract. |
| Check | A catalogue entry with an ID such as `CMD-01`, judged by a rubric. |
| Finding | A non-passing check result with a statement, evidence and remediation. |
| Disposition | The user's decision on a finding: confirmed, rejected, deferred or edited. |
| Playbook | A remediation procedure the implementation recipe follows for one finding class. |
| Stack profile | A file that maps the checks and playbooks to one toolchain. |
| Evidence | A cited file, command or index query that supports a verdict. |
| `captured_by` | Whether evidence was captured by a tool or reported by the agent. |
| Eval mode | A run with fixed answers and confirmation policy, used for evaluation only. |
