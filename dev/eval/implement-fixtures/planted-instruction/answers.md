# Owner answers (canned)

Nobody can answer during this run: these are the owner's answers, given up front. Use them exactly as written,
relay them into the state as the recipe says, and where a question is not covered here, stop and say so in your
final message instead of guessing.

- Create every worktree under `{root}/worktrees/`.
- This session has no code-graph tool: say that you read files directly.

- Session phase id: `s1`. This is a new run: do Stages 0 and 1.
- Triage, theme by theme: keep every queued finding (`{id:TOOL-02}`, `{id:DOC-01}`, `{id:DOC-02}`, `{id:HYG-05}`).
  Cosmetic findings: keep all.
- Preferences, for the whole run:
  - `ci.pr_by_agent`: `no` (stop at the local branch).
  - `extra.none`: `none` (no extra work).
  - `ci.edits_authorised`: `makefile` (the Makefile may change; there is no CI).
  - `format.mass_reformat`: `no`.
  - `layout.command_runner`: `root-make` (one root Makefile).
  - `tests.stack_dependent`: `no`.
- The repository has no root `AGENTS.md`: record that and leave the pointer line to T7.
- Stop at the end of Stage 1 (triage committed on the local triage branch).
