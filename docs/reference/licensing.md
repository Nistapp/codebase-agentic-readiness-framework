# Licensing

> **Audience:** Everyone
> **Source of truth:** this page, for which licence covers which path. The licence texts are `LICENSE`,
> `LICENSE-CODE` and `LICENSE-TEMPLATES`.
> **Status:** Live.

---

| What | Licence |
|---|---|
| Scripts and code: `audit/tools/`, `implement/tools/`, the playbook templates in `implement/playbooks/templates/` (a copy in a target takes the target's licence, see [below](#what-an-implement-run-puts-into-your-repository)), the engine code in `audit/engine/` (the `audit/` package, its tests and `build.py`), the dev-only checks and build tools in `dev/`, the greenfield scaffolder `greenfield/bootstrap/bootstrap.py`, and their tests | AGPL-3.0-or-later |
| Documentation: this `docs/` tree, the engine's docs (`audit/engine/docs/`, its README and `AGENTS.md`), recipes, check files, playbooks, stack profiles, the check catalogue (`catalogue.json`), the scaffolder's `README.md` and `DESIGN.md` in `greenfield/bootstrap/` | GFDL 1.3 |
| Templates: `greenfield/templates/`. A copy needs no notice, and takes the licence of the repository it lands in | MIT-0 |
| JSON Schemas (`audit/schema/`) and their documentation | GFDL 1.3 |
| Example reports and other outputs published in this repository, including `audit/engine/examples/` | GFDL 1.3 |

The licence texts are root files: `LICENSE` holds the GFDL 1.3 text, `LICENSE-CODE` holds the AGPL text and
`LICENSE-TEMPLATES` holds the MIT-0 text. Each skill
bundle that `dev/build_skills.py` builds carries a `LICENSE` file with the AGPL text.

SPDX identifiers: `AGPL-3.0-or-later` for code, `MIT-0` for templates, and `GFDL-1.3-only` for documentation,
schemas and published outputs.

> [!NOTE]
> The AGPL covers the tools, not the repositories they analyse. Reports that you produce on your own repositories are yours; the tools place no licence on them. Outputs this project publishes as examples are GFDL 1.3.

## What an implement run puts into your repository

Text and code that the implement step generates, or copies into a target repository, take the target repository's
own licence. This holds even when the text or code is copied word for word from this project. The project's
copyright holder licenses that text and code so that the target may relicense its copy under the target's own
licence. A private or enterprise repository is a target like any other.

The grant covers the copy in the target. The file in this repository keeps the licence in the table above, and the
tools that make the copy stay AGPL-3.0-or-later.

How the grant fits each source:

| Source | Licence here | The copy in a target |
|---|---|---|
| Text an implement run generates for the target (pages, instruction-file sections, configuration) | None: it is written for the target | The target's licence. |
| `greenfield/templates/`, copied or adapted by a playbook or by the scaffolder | MIT-0 (`LICENSE-TEMPLATES`) | The target's licence. MIT-0 already allows this, with no notice. A new project picks its own licence. |
| Code templates in `implement/playbooks/templates/` | AGPL-3.0-or-later, with a copyright line | The target's licence. The copyright holder permits the relicensing of the copy. The copy's SPDX line names the target's licence in place of this repository's. The copyright line stays. |

The implement recipe reads the target's licence from its root licence file. It asks the owner when the file is
absent or names no clear licence. The steps are in the
[`establish-docs-contract`](../../implement/playbooks/establish-docs-contract.md) playbook. The decision is
[ADR 0008](../../implement/docs/architecture/adrs/0008-copies-in-a-target-take-the-targets-licence.md).

A playbook still takes the text it copies from `greenfield/templates/` and the code it copies from
`implement/playbooks/templates/`. Those two folders are written to be copied, and the templates are MIT-0 so that
a copy carries no copyleft and no notice duty. A copy you make by hand from another
path, outside an implement run, keeps the licence in the table above.

This page states the project's policy. It is not legal advice: have your counsel review it where your licence or
your use needs certainty.
