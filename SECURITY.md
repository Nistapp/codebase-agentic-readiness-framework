# Security policy

## Reporting a vulnerability

Please do not report a security problem in a public issue or pull request.

Report it privately through GitHub's private vulnerability reporting: open the repository's **Security** tab and choose
**Report a vulnerability**. Include what you found, the commit or release it affects, and the steps to reproduce it.

If you cannot use GitHub, email <udan-security@nistapp.com>.

## What to expect

We aim to acknowledge a report within 5 working days, and to keep you informed until it is fixed or closed.
Please give us a reasonable time to fix a problem before you disclose it publicly.

## Scope

This policy covers what this repository ships and runs:

- the audit engine and the recipe tools (Python), including the release asset `audit.pyz`;
- the two skill bundles on the release page, and the recipes (`SKILL.md`, checks, playbooks) that tell a coding agent
  what to read, run and change in a user's repository;
- the build, CI and release workflows in `.github/`.

Examples of what we want to hear about: a tool that writes outside the places its documentation names, a recipe step
that leads an agent to expose a secret or run a command the user did not approve, or a release asset that does not
match its `SHA256SUMS` or fails `gh attestation verify`. Problems in the framework documents themselves (wrong or
unsafe advice) are welcome as reports too.
