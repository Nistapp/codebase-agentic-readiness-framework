# Owner answers (canned)

Nobody can answer during this run: these are the owner's answers, given up front. Use them exactly as written,
relay them into the state as the recipe says, and where a question is not covered here, stop and say so in your
final message instead of guessing.

- Create every worktree under `{root}/worktrees/`.
- This session has no code-graph tool: say that you read files directly.

- Session phase id: `t1`. Triage is merged into `dev` (the state is there).
- Theme for this session: T1 (command surface).
- T1 change list: approved as long as it stays inside the playbook. `{id:TOOL-02}` (TOOL-02): the linter is the
  repository's own style check (`tools/style_check.py`, run by `make lint`); keep it, no new tool and no install.
- Adoption mode for a tool that fails on today's code: ratchet, as the playbook recommends. There is no CI, so where
  the playbook says "report-only full run in CI", keep a full run as its own Makefile target instead.
- Existing code is not fixed or reformatted in this theme (`format.mass_reformat` is `no`).
- Values only the owner has: skip (option 3), and record the skip as the recipe says.
- `ci.pr_by_agent` is `yes`: push the theme branch and open the pull request as Stage 4 says. If opening the pull
  request fails, say so and stop there.
- Stop when Stage 4 ends.
