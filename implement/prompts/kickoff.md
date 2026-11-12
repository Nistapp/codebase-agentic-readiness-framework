# Kickoff prompt

Give an agent this text, with the three fill-ins replaced: the repository's path, the final report's path (in
the audit's output folder, which becomes the run's workspace), and the integration branch (for example `dev`).
Use the same text to resume a run; the state file beside the report tells the agent where it stopped.

```text
Run the implement recipe (the agentic-readiness-implement skill, or implement/SKILL.md in a
framework checkout) on <path to the repository>, for the final audit report <path to the final report JSON>,
with <integration branch> as the integration branch. Follow it stage by stage.
If the report's folder already holds a state file, run progress.py show on it first and resume from where it
leaves off instead of starting over. If the repository still keeps a state in docs/agentic-readiness/, adopt it
into the report's folder first. Never copy the report or the state into the repository.
Do one theme per session: stop at the end of each theme, and at every question only I can answer.
Ask me the triage questions one theme at a time, relay my answers into the state exactly as I give them, and
stop rather than guess at any of them. Never install a tool I did not choose: when a step needs a missing
tool, offer me the options and wait for my pick, which may be none. Check each tool's version against the
repository's pin; warn and record a small gap, ask me about a large one, and accept my choice.
Commit each logical change as soon as it passes, so every commit can be rolled back alone.
Run the repository's tests before each commit and show me each result against the baseline run.
Push a branch and open a pull request only if the state records ci.pr_by_agent=yes. Never merge.
```
