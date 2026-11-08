# Harness Notes

> **Audience:** Everyone
> **Source of truth:** the tested behaviour of each harness, with dates. Related pages:
>
> - [`tools-cli.md#build_skillspy`](tools-cli.md#build_skillspy): the bundle that these harnesses install;
> - [`run-the-evals.md`](../how-to/run-the-evals.md): the eval harness that drives a harness without a person.
>
> **Status:** Live for Claude Code and opencode, the two harnesses that were run (S4.1.3, S4.5.3). Codex and Cursor
> are untested. Their row says only what applies on paper. It is not a verified result.

A **harness** is the program that runs an AI coding agent, for example Claude Code or opencode. This page records how
each harness behaved with the audit skill bundle.

---

## Summary

| Harness | What was tested | Headless mode | Notes |
|---|---|---|---|
| Claude Code | Skill install and run, headless `run-claude.sh` driver | `--dangerously-skip-permissions` (`D56`) | No friction found; see below |
| opencode | Skill install and run (DeepSeek flash) | `opencode run` | One real quirk found; see below |
| Codex | Not tested | — | `codex exec` is the documented headless entry point; unverified here |
| Cursor | Not tested | — | Unverified here |

## Claude Code

Claude Code was tested twice.

| Run | How | Result |
|---|---|---|
| Eval harness (S4.1.3) | `run-claude.sh` on the `cmd-02-weak-check` fixture; headless, `--dangerously-skip-permissions` | 71 checks; `CMD-02` `FAIL`/`BLOCKER`; 131 s, $0.92, 30 turns |
| Installed skill bundle (S4.5.3) | A fresh subagent, interactive | 69 checks (a smaller, fixture-only scope); `CMD-02` `FAIL`/`BLOCKER` |

In the second run, the `Skill` tool found and loaded `agentic-readiness-audit` as soon as the bundle was in
`.claude/skills/agentic-readiness-audit/`. No restart was needed.

Neither run had friction:

- every tool call exited 0;
- the agent followed multi-step instructions (the Stage 0 to 5 sequence of the kickoff prompt) without needing them
  as one shell call.

**Install path:** `.claude/skills/agentic-readiness-audit/` at the project root.

- `dev/build_skills.py` builds it. The path was checked against Claude Code's own docs
  (`code.claude.com/docs/en/skills`).
- The implement skill installs beside it, at `.claude/skills/agentic-readiness-implement/`. It needs the audit skill
  there, because its `engine.py` loads the audit skill's engine. This was not yet run as an installed skill.

## opencode

opencode was tested once (S4.5.3), with DeepSeek flash as the model.

- `deepseek/deepseek-flash` appears in `opencode models` only when `DEEPSEEK_API_KEY` is set in the environment.
  The run set it by sourcing this repository's `.env`, never by printing a value (the `.env` rule of the root
  `AGENTS.md`).
- opencode uses the same install path. `opencode.ai/docs/skills` names `.claude/skills/<name>/SKILL.md` as its
  "Project, Claude-compatible" location. This was checked directly, so no second copy was needed.

**Found, not fixed: a quirk of the model or the harness, not a recipe defect.**

1. A prompt with six numbered steps in one turn hung for 540 s, with no tool call and no text. It was then killed.
2. A retry split the prompt into two `opencode run` calls. The second call ran the finished steps again, not the new
   ones. Each `opencode run` is a fresh session with no memory, so it did not know what the first call did.
3. The fix: give the model one shell command, chained with `&&` or `;`, as the instruction. The model then has to
   build and run one tool call only.

With the fix, the run matched the Claude Code run exactly: 69 checks, 35 findings, `CMD-02` `FAIL`/`BLOCKER`.

> [!TIP]
> To drive opencode headless, give each `opencode run` one chained shell command, not a numbered list of steps.
> The harness keeps no memory between `opencode run` calls, so give the full context on every call.

## Codex and Cursor

Neither harness has run this project's recipe or skill bundle.

- `run-codex.sh` was drafted for the eval harness, then dropped (`D57`). `codex` was not installed in the environment
  that built the eval harness, so its flags could not be checked.
- Public docs from Anthropic and from each vendor describe Codex's skills support, its `codex exec` entry point, and
  Cursor's skills and rules support. Nothing here has checked them against this bundle.

Treat this row as a gap, not as a negative result.
