# Owner answers (canned)

Nobody can answer during this run: these are the owner's answers, given up front. Use them exactly as written,
relay them into the state as the recipe says, and where a question is not covered here, stop and say so in your
final message instead of guessing.

- Create every worktree under `{root}/worktrees/`.
- This session has no code-graph tool: say that you read files directly.

- Session phase id: `t6`. Triage is merged into `dev` (the state is there).
- Theme for this session: T6 (documentation contract). `{id:DOC-05}` (DOC-05) is the item.
- T6 change list: approved as long as it stays inside the playbook.
- Docs tooling: none. No Markdown linter, no Mermaid CLI, no link checker, and no install.
- Prose check: copy the template under the MIT licence (`docs.prose_check=template`,
  `docs.prose_check_licence=MIT`). There is no CI: wire the ratchet runs as Makefile targets instead.
- Existing pages are not rewritten (`format.mass_reformat` is `no`; no `extra.prose-rewrite`).
- The docs language is English (`docs.language` is `en`).
- `ci.pr_by_agent` is `no`: stop at the local theme branch.
- Stop when Stage 4 ends.
