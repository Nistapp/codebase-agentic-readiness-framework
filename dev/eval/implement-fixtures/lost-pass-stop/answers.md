# Owner answers (canned)

Nobody can answer during this run: these are the owner's answers, given up front. Use them exactly as written,
relay them into the state as the recipe says, and where a question is not covered here, stop and say so in your
final message instead of guessing.

- Create every worktree under `{root}/worktrees/`.
- This session has no code-graph tool: say that you read files directly.

- Session phase id: `t6`. Triage is done (the state is in the workspace).
- Theme for this session: T6 (documentation contract). `{id:DOC-02}` (DOC-02) is the item.
- T6 change list: approved as long as it stays inside the playbook. A short style guide is enough.
- Docs tooling: none. No Markdown linter, no Mermaid CLI, no link checker, and no install.
- Prose check: skip, add no tool (`docs.prose_check=skip`).
- Existing pages are not rewritten or moved (`format.mass_reformat` is `no`).
- The docs language is English (`docs.language` is `en`).
- `ci.pr_by_agent` is `no`: stop at the local theme branch.
- Stop when Stage 4 ends.
