# Audit

The audit recipe checks an existing repository for agentic readiness against Phase 1 of the framework. A deterministic
engine does the counting: it reads the repository, never writes to it, and never calls an LLM. The agent does the
judgment: it verifies each blocker independently, cites evidence, and stops to ask rather than guess. The owner
confirms the findings before the report is final. To close the findings afterwards, use the
[implement recipe](../implement/README.md).

## Start an audit

1. Open Claude Code at the root of this repository. You need Python 3.11+ and read access to the target.
2. Say: "Audit `<repo-path>` and write the output to `<output-path>`".
3. Answer Stage 0's questions (including provider-exposure consent) and approve Stage 1's plan.

The skill is [`SKILL.md`](SKILL.md) (`agentic-readiness-audit`). Another agent with shell access (opencode, Codex,
Cursor) can run it from [`prompts/kickoff.md`](prompts/kickoff.md). Full walkthrough:
[Run an audit](../docs/how-to/run-an-audit.md). To run the engine alone, without the agent:
[Run an audit with the engine](engine/docs/how-to/run-an-audit.md).

### As an installed skill

To install the skill in another project, build the bundles with `python3 dev/build_skills.py` and copy
`dev/dist/skills/agentic-readiness-audit/` to `.claude/skills/agentic-readiness-audit/` in that project. The bundle
holds the recipe, the checks, the stack profiles and the tools; it needs no checkout of this repository. A tagged
release carries `audit.pyz`, the skill bundles as a zip and their SHA-256 sums; see
[`RELEASE_PROCESS.md`](../RELEASE_PROCESS.md).

## What is here

| Path | Contents |
| --- | --- |
| [`SKILL.md`](SKILL.md) | The recipe: hard rules and Stages 0 to 5 |
| [`prompts/`](prompts/kickoff.md) | The kickoff prompt for any agent, and [how the agents talk to the user](prompts/talking-to-the-user.md), which both recipes share |
| [`checks/`](checks/README.md) | The check files, thirteen families |
| [`catalogue.json`](catalogue.json) | The check catalogue the tools read |
| [`stacks/`](stacks/README.md) | Stack profiles: `typescript-node`, `java`, `python` |
| [`schema/`](schema/SCHEMA.md) | The report, intake, facts, catalogue and eval-expected schemas, with examples |
| [`tools/`](tools/README.md) | The tool contract and the tools |
| [`engine/`](engine/README.md) | The deterministic engine, with its own docs tree |
| [`docs/architecture/adrs/`](docs/architecture/adrs/0001-tools-import-engine.md) | This recipe's decisions |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed in the recipe |

## Tools

Each tool is standard-library Python and runs from a fresh clone: `python3 audit/tools/<tool>.py <arguments>`.

| Tool | Does |
| --- | --- |
| `engine.py` | Runs the engine from any directory and names the report after the target |
| `facts.py` | Describes the target with counts and names, no verdicts |
| `report.py` | Builds the report; the only writer of the draft |
| `render_report.py` | Renders the report JSON as Markdown |
| `validate_report.py` | Validates a report against its schema |

The full synopsis of each tool, and of `dev/recipe_lint.py` and `dev/build_skills.py`, is in the
[Tools CLI reference](../docs/reference/tools-cli.md). The generated list is [`tools/CATALOGUE.md`](tools/CATALOGUE.md).

## How this differs from prior art

Readiness checkers exist already: Factory's Agent Readiness (nine pillars, five levels, an 80% rule to unlock the next
level) and ambient-code's AgentReady (25 attributes, tiers). This project differs in five ways:

- an open, normative spec, not a vendor rubric;
- findings cited to evidence and confirmed by a person, not asserted;
- a deterministic engine does the scanning, and the agent's judgment sits on top;
- a brownfield ratchet: audit first, then fix only what the audit found;
- harness neutrality: plain `SKILL.md` plus command-line tools, for any agent with shell access.

## Documentation

Start at the root router, [`docs/README.md`](../docs/README.md). The engine's own router is
[`engine/docs/architecture/README.md`](engine/docs/architecture/README.md). A real run is in the
[worked example](schema/examples/server-worked-example/README.md). Licensing:
[`docs/reference/licensing.md`](../docs/reference/licensing.md).
