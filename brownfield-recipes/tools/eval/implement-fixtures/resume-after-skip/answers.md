# Owner answers (canned)

Nobody can answer during this run: these are the owner's answers, given up front. Use them exactly as written,
relay them into the state as the recipe says, and where a question is not covered here, stop and say so in your
final message instead of guessing.

- Create every worktree under `{root}/worktrees/`.
- This session has no code-graph tool: say that you read files directly.

- Session phase id: `t6`. Triage is merged into `dev` (the state is there).
- Theme for this session: T6 (docs). The diagram allows it before T1.
- T6 change list: approved as long as it stays inside the playbook. `DOC-01`: create `docs/README.md` as the
  documentation index (what the project is, where code and tests live, which commands exist). No new tool and no
  install. The repository has no Markdown linter: say so, do not add one.
- Values only the owner has: skip (option 3), and record the skip as the recipe says.
- Stop when Stage 4 ends: the theme branch stays local (`ci.pr_by_agent` is `no`).
