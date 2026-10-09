# 1. Tool Contract

> **Audience:** Engineers, maintainers
> **Goal:** Define the contract every deterministic tool follows.
> **Status:** Planned (placeholder).

> [!NOTE]
> Planned. `tools/_common.py` does not exist yet. Filled in by roadmap step S2.1.

---

## 1. Envelope and exit codes

- TBD: stdout JSON envelope; exit 0, 1, 2, 3.

## 2. Self-description

- TBD: `--describe` manifest and the generated `tools/CATALOGUE.md`.

## 3. Safety properties

- TBD: no network, no writes inside the target, bounded output, path-escape refusal.

## 4. Engine launcher

- TBD: `tools/engine.py` and the import-path ADR.
