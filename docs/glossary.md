# Glossary

Canonical definitions of terms used by the brownfield recipes. Terms from the readiness framework are cited, not
redefined; see [`docs/framework/glossary.md`](framework/glossary.md).

> **Status:** Live. Every term below names a thing that exists today. The implementation recipe and its
> playbooks (v0.2.0) are live.

---

| Term | Definition |
|---|---|
| Recipe | A Markdown instruction document (`SKILL.md`) that a coding agent executes. |
| Audit recipe | The read-only recipe that produces the audit report. |
| Implementation recipe | `implement/SKILL.md`: the recipe that closes confirmed findings one theme at a time, a branch per theme. v0.2.0: Stages 0 to 5. |
| Engine | The deterministic, standard-library Python audit in `audit/engine/`. |
| Tool | A deterministic script in `tools/` that follows the tool contract. |
| Envelope | The one JSON object a tool prints on stdout: `tool`, `version`, `ok`, `data`, `warnings`, `truncated`. |
| Check | A catalogue entry with an ID such as `CMD-01`, judged by a rubric. |
| Finding | A non-passing check result with a statement, evidence and remediation. |
| Disposition | A finding's state: `pending` until set, then the user's decision — `confirmed`, `rejected`, `deferred` or `edited`. |
| Playbook | A remediation procedure the implementation recipe follows for one finding class, in `implement/playbooks/`. All thirteen are written. A check's catalogue entry names its playbook. |
| Stack profile | A file that maps the checks and playbooks to one toolchain. |
| Evidence | A cited file, command or index query that supports a verdict. |
| `captured_by` | Whether evidence was captured by a tool or reported by the agent. |
| Eval mode | A run with fixed answers and confirmation policy, used for evaluation only. |
| Finding key | A finding's stable identifier: the check ID, then an optional scope after a colon. A re-audit matches findings by it. |
| Intake file | The JSON file that answers the audit's Stage 0 questions, so that a run needs no interview. |
| Override | A report verdict that differs from the engine's, recorded with a reason and agent-captured counter-evidence. |
| Framework release | The release version of the framework, such as `0.3.2`, from `.release-please-manifest.json`. Every report and state records the release that made it. See [Versions](reference/versions.md). |
| Catalogue | `catalogue.json`: every check in one ID namespace, with its method, requirements and playbooks. |
| Agent-only check | A check no deterministic rule can settle, judged by a model with cited evidence, such as `AGT-11`. It has no engine ID. |
| Draft | `<label>.audit-draft.<stamp>.json`: the report while it is being built. Only `report.py` writes it, and it becomes a final report when nothing is pending. |
| Fragment | The JSON object an agent hands `report.py` for one check, finding or list of decisions. It holds only what the agent decides; the tool computes the rest. |
| Builder | `report.py`: the only writer of the draft. Every change it makes is validated and written atomically. |
| Renderer | `render_report.py`: turns a valid report into Markdown. A pure function of the JSON, so one report gives one text. |
| Golden file | The Markdown that sits beside an example report and that the renderer's tests compare its output with. |
| Engine report | `<label>.engine-report.<stamp>.json`: the JSON that `engine.py` writes, in the engine's schema v2. The adapter reads it and never changes it. |
| Engine adapter | `report.py import-engine`, which applies `_engine_adapter.py`: brings the engine's checks, findings, stack, probes and unattested items into a draft. It runs once for a draft, and only for the draft's own repository. |
| Golden pair | A raw engine report in `schema/examples/realistic/` and the draft that the adapter must make from it, byte for byte. |
| Facts file | `facts.json`: the file `facts.py` writes before the audit's assessment stage. Counts and names only — inventory, stack, instruction files, components and a size class — with no verdict. |
