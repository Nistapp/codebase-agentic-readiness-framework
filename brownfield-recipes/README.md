# Brownfield Recipes

Recipes that a coding agent runs against an existing repository: first to audit it for agentic readiness,
then (v0.2.0) to implement the confirmed findings. A deterministic engine does the counting — it reads the
repository, never writes to it, and never calls an LLM — while the agent does the judgment: verifying
every blocker independently, citing evidence, and stopping to ask rather than guessing. See
[`README.md`](../README.md) at the repository root for the framework these recipes check against.

## Quick start

Either path runs the same audit recipe, [`audit/SKILL.md`](audit/SKILL.md); the clone path is quicker to
try, the skill bundle is self-contained once installed.

### From a clone

1. Make sure a coding agent with shell access (Claude Code, opencode, Codex, Cursor) and Python 3.11+ are
   available, and that you have read access to the target repository.
2. Paste [`audit/prompts/kickoff.md`](audit/prompts/kickoff.md) into the agent, naming the target
   repository's path.
3. Answer Stage 0's questions (including provider-exposure consent) and approve Stage 1's plan when asked.

Full walkthrough: [`docs/how-to/run-an-audit.md`](docs/how-to/run-an-audit.md).

### As an installed skill

1. Build the bundles: `python3 brownfield-recipes/tools/build_skills.py` (or `make validate-skills` to also
   check them against the Agent Skills specification's reference validator).
2. Copy `brownfield-recipes/dist/skills/agentic-readiness-audit/` to `.claude/skills/agentic-readiness-audit/`
   under the project you want to audit — this path is a supported, documented skill location for both
   Claude Code and opencode. To implement a report as well, copy `agentic-readiness-implement/` beside it, from
   the same build: it runs the audit skill's engine.
3. Invoke the installed `agentic-readiness-audit` skill, naming the target repository's path. The bundle
   carries the recipe, the check files and stack profiles, and the tools it calls; no checkout of this
   repository is needed at run time. The `agentic-readiness-implement` skill starts from
   `references/prompts/kickoff.md` inside it.

Tool reference: [`docs/reference/tools-cli.md`](docs/reference/tools-cli.md#build_skillspy).

A tagged release carries the built `audit.pyz`, the skill bundle as a zip and their SHA-256 sums, so a one-off user
need not clone and build; the workflow is described in [`RELEASE_PROCESS.md`](../RELEASE_PROCESS.md) and has not
run yet.

## How this differs from prior art

Readiness checkers exist already — Factory's Agent Readiness (nine pillars, five levels, an 80% rule to
unlock the next level) and ambient-code's AgentReady (25 attributes, tiers). This project differs in five
ways: an open, normative spec rather than a vendor rubric; findings that are cited to evidence and confirmed
by a person rather than asserted; a deterministic engine that does the scanning, with the agent's judgment
layered on top rather than an LLM doing both; a brownfield ratchet — ship the audit first, then only the
fixes the audit actually found, rather than a greenfield template; and harness neutrality, since the recipe
is plain `SKILL.md` plus command-line tools, runnable by any agent with shell access.

## Layout

| Folder | Contents | Status |
|---|---|---|
| [`audit/`](audit/SKILL.md) | The audit recipe and its check files | Live |
| [`implement/`](implement/SKILL.md) | The implementation recipe, its playbooks and the state contract | Live (v0.2.0): Stages 0-5, the state contract, the thirteen playbooks and the skill bundle |
| [`schema/`](schema/SCHEMA.md) | The report, intake, facts, catalogue and eval-expected schemas, with examples | Live |
| [`stacks/`](stacks/README.md) | Stack profiles (`typescript-node`, `java`, `python`) | Live |
| [`tools/`](tools/README.md) | The tool contract, shared helpers and the tools themselves — engine launcher, facts, report builder, renderer, validator, recipe linter, skill bundler | Live |
| [`deterministic-audit/`](deterministic-audit/README.md) | The deterministic engine, migrated with its history | Live |
| [`docs/`](docs/architecture/README.md) | Documentation, Diátaxis layout | Live — see the doc router; the only pages marked `Planned` are the deferred second-harness items |

Licensing: [docs/reference/licensing.md](docs/reference/licensing.md).
