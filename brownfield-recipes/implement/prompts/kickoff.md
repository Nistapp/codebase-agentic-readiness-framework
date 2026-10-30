# Kickoff prompt

Give an agent this text, with the two paths filled in.

```text
Run the implement recipe on <path to the repository> for the final audit report <path to the report JSON>,
following brownfield-recipes/implement/SKILL.md stage by stage.
If docs/agentic-readiness/ in the repository already holds a state file, run progress.py show on it first and
resume from where it leaves off instead of starting over.
Ask me the triage questions one theme at a time, relay my answers into the state exactly as I give them, and
stop rather than guess at any of them. Never merge.
```
