# Owner answers (canned)

Nobody can answer during this run: these are the owner's answers, given up front. Use them exactly as written,
relay them into the state as the recipe says, and where a question is not covered here, stop and say so in your
final message instead of guessing.

- Create every worktree under `{root}/worktrees/`.
- This session has no code-graph tool: say that you read files directly.

- Session phase id: `t1`. Triage is done (the state is in the workspace).
- Theme for this session: T1 (command surface).
- T1 change list: approved as long as it stays inside the playbook. `{id:TOOL-02}` (TOOL-02): the linter is the
  repository's own style check (`tools/style_check.py`, run by `make lint`); keep it, no new tool and no install.
- I want `make lint` to pass at the end of this theme.
- Adoption mode for a tool that fails on today's code: ratchet, as the playbook recommends. There is no CI, so where
  the playbook says "report-only full run in CI", keep a full run as its own Makefile target instead.
- Existing code is not fixed or reformatted in this theme (`format.mass_reformat` is `no`).
- The checkout keeps its local settings in a git-ignored `.env` file at its root.
- Values only the owner has: skip (option 3), and record the skip as the recipe says.
- Stop when Stage 4 ends: the theme branch stays local (`ci.pr_by_agent` is `no`).
