# Questions and answers

Short answers to the questions a leader, a security reviewer or a staff engineer asks first. Each answer links
one page with the detail.

## Why not wait for better models?

Stronger models need less help to finish a task, but they still spend tokens when they must guess. Published
studies show that several practices cut cost while task success stays equal. You also own the repository: you
prepare it once, and every later task gains, whichever agent you use.
[The evidence](evidence.md)

## We already have linters, CI and SonarQube. What is new?

Those tools check your code. The audit checks whether an agent can find and trust them. It looks for one set of
commands, CI that runs the same commands, tests the agent cannot weaken, and written rules for agents. The fix
step keeps the tools your repository already uses.
[How it works](how-it-works.md)

## Does our code leave our machines?

Not through the framework's tools: none of them opens a network connection. Your coding agent sends what it
reads to its model provider, as it does today. The audit says so, and it starts only after you acknowledge it.
If you agree, the agent also reads your branch rules from your Git host.
[Security and data](security-and-data.md)

## What about the AGPL?

The AGPL covers the tools, not the repositories they analyse. Reports on your repositories are yours. Text and
code that the fix step generates or copies into your repository take your repository's own licence. That holds
even for text or code copied word for word from this project. The documentation and the published examples are
GFDL-1.3. This answer is a summary, not legal advice.
[Licence in plain words](licence-in-plain-words.md)

## What does it change, and can we refuse?

The audit never writes inside your repository. You confirm or reject the findings, and the fix step acts only on
those you confirmed. Before anything changes, you approve one change list per area. The fix step commits on local
branches, never merges, and pushes only if you opt in.
[How it works](how-it-works.md)

## Does the audit run our code?

Not by default. The audit never writes to your repository, and it runs none of your commands unless you opt in.
If you opt in, it may run only your read-only commands. Those are the format check, lint, the type check, the
tests, the combined check and the security check. The audit engine refuses, in code, the command that rewrites
formatting.
[Security and data](security-and-data.md)

## What does it cost?

The framework is free and open source. You pay for your agent's usage and for your engineers' time. In the
project's own runs on the Sonnet 5.5 model, an audit of a real repository cost $1.24 to $3.02 of agent usage.
Your costs depend on the repository, and heavily on the model. The fix run's figures are on the same page.
[Cost and time](cost-and-time.md)

## Does it help teams on Copilot or Cursor?

Partly. A skill is a set of instructions that a coding agent follows. Running the audit and fix skills is tested
on Claude Code, with one run on opencode. Cursor, Codex, Gemini CLI and GitHub Copilot are not tested for running
them. The repository changes they make help any agent and any engineer. Those changes are ordinary files:
commands, tests, automatic checks in CI and a rules file.
[Harness notes](../reference/harness-notes.md)

## Which stacks and platforms?

The project has profiles for three toolchains: Java, Python, and TypeScript on Node. Linux is tested. On macOS,
the tools were tested in CI until November 2026, and the Claude Code path is not yet checked by hand. Continuous
macOS testing is planned ([issue #82](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/82)).
Windows is not tested; WSL may work.
[Stack profiles](../../audit/stacks/README.md)

## Does a higher score mean better agent work?

Nobody knows yet. The score counts the checks a repository passes, weighted by severity. No study has measured
whether a higher score leads to better agent work, for this framework or any other. Treat the score as an
ordered list of work.
[The evidence](evidence.md)

## Who maintains it, and what if it stops?

It is a small open-source project, and it publishes no release schedule. The tools are plain Markdown and
standard-library Python. Reports and fixes are ordinary files that you own. If the project stops, everything
already in your repository keeps working.
[Governance](../../GOVERNANCE.md)

## How much engineer time does it take?

Nobody has measured it yet. An engineer answers the agent's questions, decides the findings, approves each area's
change list and reviews each branch. The project has not yet published engineer hours per run. It gives typical
elapsed times, such as 10 to 30 minutes for an audit, and they are not engineer hours.
[Cost and time](cost-and-time.md)

## How often should we audit again?

There is no fixed schedule. The project improves the checks continuously, from community feedback, so a newer
release may find more. Run the latest release about once a quarter. Run it also after a major change to your
automatic checks or your rules for agents.
[How it works](how-it-works.md)

## How do we roll it out to many repositories?

One repository at a time. Each audit is a separate run with its own output folder. The project has not yet
published a rollout guide, so start with a pilot on one non-critical repository.
[Run a pilot](run-a-pilot.md)

## Can we run it on a monorepo?

Partly. The audit scores the components that a build manifest declares, one level deep. A check scoped to one
nested component is planned.
[Applicability](../framework/overview.md#applicability)

## Is anything installed into our repository or machine?

The audit installs nothing. It needs `git` and Python 3.11 or newer, and it writes only to an output folder
outside your repository. The fix step may propose a tool or a dependency for your repository. It adds one only
after you approve it, on a branch you review.
[Security and data](security-and-data.md)

One caveat concerns the install from the release zips. It unzips the skills, with the AGPL tools, into a folder
you choose. A folder inside a project puts those tools in that project, so keep it out of what you commit. The
[install guide](../how-to/install-the-skills.md) also gives a folder in your home folder, which is not yet tested.
A clone of the framework avoids the question.
