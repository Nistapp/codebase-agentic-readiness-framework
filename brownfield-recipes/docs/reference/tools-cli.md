# Tools CLI Reference

> **Audience:** Everyone
> **Source of truth:** each tool's `--describe` output; generated `tools/CATALOGUE.md`
> **Status:** Planned (placeholder).

> [!NOTE]
> Planned. No tool exists yet. Filled in by roadmap step S2.1–S2.8.

---

## Summary

| Item | Description |
|---|---|
| `engine.py` | Runs the deterministic engine from any directory (S2.1) |
| `validate_report.py` | Validates a report against schema and semantic rules (S2.2) |
| `report.py` | Builds and updates the audit report; the only writer (S2.3) |
| `render_report.py` | Renders a report to Markdown (S2.4) |
| `facts.py` | Emits stack and inventory facts, no verdicts (S2.7) |
| `recipe_lint.py` | Checks recipes for broken references and budgets (S2.8) |
| `progress.py` | Manages implementation progress (S5.1) |
| `check_drift.py` | Lists findings affected by changes since the audit (S5.1) |
