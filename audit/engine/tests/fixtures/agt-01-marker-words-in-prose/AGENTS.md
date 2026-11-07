# AGENTS.md

This file tells an agent how to work in this repository. It is finished, and it uses the words that mark an
unfinished file in ordinary sentences.

## Rules

- Never commit placeholder values for a credential, a URL or a version number.
- Leave no TODO in a commit: open an issue and cite its number in the code instead.
- A line that says TBD in a pull request description means the author has not decided, so ask them.
- Test data may hold a placeholder string, but never one that looks like a real secret. When in doubt, wrap
  the text and leave no
TODO markers or TBD notes behind in the fixtures.

## Commands

Run `make check` before proposing a change. It is the only gate.
