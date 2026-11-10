# Licensing

> **Audience:** Everyone
> **Source of truth:** KC's decisions of 2026-10-09; the `LICENSE` files in this repository.
> **Status:** Live.

---

| What | Licence |
|---|---|
| Scripts and code: `audit/tools/`, `implement/tools/`, the playbook templates in `implement/playbooks/templates/` (a copy in a target carries `MIT`, `Apache-2.0` or `BSD-3-Clause`, as its owner picks, and keeps the copyright line), the engine code in `audit/engine/` (the `audit/` package, its tests and `build.py`), the dev-only checks and build tools in `dev/`, and their tests | AGPL-3.0-or-later |
| Documentation: this `docs/` tree, the engine's docs (`audit/engine/docs/`, its README and `AGENTS.md`), recipes, check files, playbooks, stack profiles, the check catalogue (`catalogue.json`) | GFDL 1.3 |
| Templates: `greenfield/templates/`, and the text an implement playbook copies or adapts from them into a target repository. A copy needs no notice | MIT-0 |
| JSON Schemas (`audit/schema/`) and their documentation | GFDL 1.3 |
| Example reports and other outputs published in this repository, including `audit/engine/examples/` | GFDL 1.3 |

The licence texts are root files: `LICENSE` holds the GFDL 1.3 text, `LICENSE-CODE` holds the AGPL text and
`LICENSE-TEMPLATES` holds the MIT-0 text. Each skill
bundle that `dev/build_skills.py` builds carries a `LICENSE` file with the AGPL text.

SPDX identifiers: `AGPL-3.0-or-later` for code, `MIT-0` for templates, and `GFDL-1.3-only` for documentation,
schemas and published outputs.

The templates are MIT-0 so that text copied into a repository, private and enterprise ones included, carries no
copyleft and no notice duty. The repository then owns its copy. For the same reason a playbook copies or adapts
text only from `greenfield/templates/`, never from this repository's `docs/`.

> [!NOTE]
> The AGPL covers the tools, not the repositories they analyse. Reports that you produce on your own repositories are yours; the tools place no licence on them. Outputs this project publishes as examples are GFDL 1.3.
