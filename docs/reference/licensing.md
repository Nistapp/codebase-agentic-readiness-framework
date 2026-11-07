# Licensing

> **Audience:** Everyone
> **Source of truth:** KC's decisions of 2026-10-09; the `LICENSE` files in this repository.
> **Status:** Live.

---

| What | Licence |
|---|---|
| Scripts and code: `audit/tools/`, `implement/tools/`, the engine code in `audit/engine/` (the `audit/` package, its tests and `build.py`), the dev-only checks and build tools in `dev/`, and their tests | AGPL-3.0-or-later |
| Documentation: this `docs/` tree, the engine's docs (`audit/engine/docs/`, its README and `AGENTS.md`), recipes, check files, playbooks, stack profiles, the check catalogue (`catalogue.json`) | GFDL 1.3 |
| JSON Schemas (`audit/schema/`) and their documentation | GFDL 1.3 |
| Example reports and other outputs published in this repository, including `audit/engine/examples/` | GFDL 1.3 |

The licence texts are root files: `LICENSE` holds the GFDL 1.3 text and `LICENSE-CODE` holds the AGPL text. Each skill
bundle that `dev/build_skills.py` builds carries a `LICENSE` file with the AGPL text.

SPDX identifiers: `AGPL-3.0-or-later` for code and `GFDL-1.3-only` for documentation, schemas and published outputs.

> [!NOTE]
> The AGPL covers the tools, not the repositories they analyse. Reports that you produce on your own repositories are yours; the tools place no licence on them. Outputs this project publishes as examples are GFDL 1.3.
