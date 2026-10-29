# Harness Notes

> **Audience:** Everyone
> **Source of truth:** tested behaviour of each harness, with dates. See
> [`tools-cli.md#build_skillspy`](tools-cli.md#build_skillspy) for the bundle these harnesses install, and
> [`run-the-evals.md`](../how-to/run-the-evals.md) for the eval harness that drives a harness headlessly.
> **Status:** Live for Claude Code and opencode, the two harnesses actually run (S4.1.3, S4.5.3). Codex and
> Cursor are untested; their row states only what applies on paper, not a verified result.

---

## Summary

| Harness | What was tested | Headless mode | Notes |
|---|---|---|---|
| Claude Code | Skill install and run, headless `run-claude.sh` driver | `--dangerously-skip-permissions` (`D56`) | No friction found; see below |
| opencode | Skill install and run (DeepSeek flash) | `opencode run` | One real quirk found; see below |
| Codex | Not tested | — | `codex exec` is the documented headless entry point; unverified here |
| Cursor | Not tested | — | Unverified here |

## Claude Code

Tested twice: the eval harness's `run-claude.sh` driver against the `cmd-02-weak-check` fixture (S4.1.3,
headless, `--dangerously-skip-permissions`, 131s, $0.92, 30 turns), and the installed skill bundle
(S4.5.3, a fresh subagent, interactive): the `Skill` tool found and loaded `agentic-readiness-audit` on its
own the moment the bundle landed at `.claude/skills/agentic-readiness-audit/`, with no restart needed.
Both runs matched: 71 checks (eval harness) or 69 checks (skill-bundle run, a smaller fixture-only scope),
`CMD-02` correctly `FAIL`/`BLOCKER` either way. No friction in either run — every tool call exited 0, and
multi-step instructions (the kickoff prompt's own Stage 0–5 sequence) were followed without needing to be
collapsed into one shell call.

**Install path:** `.claude/skills/agentic-readiness-audit/` at the project root, built by
`tools/build_skills.py` (confirmed against Claude Code's own docs, `code.claude.com/docs/en/skills`, not
assumed).

## opencode

Tested once (S4.5.3), with DeepSeek flash as the model: `deepseek/deepseek-flash` only appears in
`opencode models` once `DEEPSEEK_API_KEY` is set in the environment (read from this repo's own `.env` by
sourcing it, never by catting or echoing a value, per the root `AGENTS.md`'s `.env` rule). The same install
path serves opencode too — `opencode.ai/docs/skills` names
`.claude/skills/<name>/SKILL.md` as its own "Project, Claude-compatible" location, confirmed directly, not
assumed, so no separate copy was needed.

**Found, not fixed — a model/harness quirk, not a recipe defect:** a multi-step natural-language
instruction (six numbered steps in one turn) hung with no tool call or text at all for 540s, then was
killed. A retry split into two separate `opencode run` calls got further, but the second call silently
re-ran only the already-done steps instead of the new ones — each `opencode run` is a fresh, memoryless
session, so it had no record of what the first call had already done. The fix that worked: give the model
one `&&`/`;`-chained shell one-liner as the literal instruction, rather than a multi-step natural-language
list, so it only has to construct and run a single tool call. With that, the run matched the Claude Code
run exactly (`69 checks`, `35 findings`, `CMD-02` `FAIL`/`BLOCKER`).

**If you are driving opencode headlessly:** prefer one chained shell command per `opencode run` over a
numbered multi-step prompt, and expect to re-supply already-completed context on every call — opencode
carries no memory between invocations of `opencode run`.

## Codex and Cursor

Neither has been run against this project's recipe or skill bundle. `run-codex.sh` was drafted for the
eval harness but dropped (`D57`): `codex` was not installed in the environment that built the eval harness,
so its flags could not be verified. Codex's skills support and `codex exec` entry point, and Cursor's
skills/rules support, are both named in Anthropic's and the respective vendors' own public documentation,
but nothing here has confirmed them against this bundle. Treat this row as a gap, not a negative result.
