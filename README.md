# Codebase Agentic Readiness Framework

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Nistapp/codebase-agentic-readiness-framework/badge)](https://scorecard.dev/viewer/?uri=github.com/Nistapp/codebase-agentic-readiness-framework)

> *"The more you sweat in peace, the less you bleed in war."* Preparing a codebase for AI coding agents is the sweat;
> agents changing it from user prompts is the war.

This framework 'prepares' a codebase or repo to enable higher quality of work from AI coding agents and to prevent
spaghettification of code. [What is an agentic-ready codebase?](docs/framework/overview.md)

This gives you two skills that act on it:

- The **audit** skill measures an existing repository and writes an evidence-cited readiness report.
- The **implement** skill then fixes the confirmed findings, one theme at a time, on a branch per theme.

## Quick start

You need [Claude Code](https://claude.com/claude-code), `git` and Python 3.11 or newer.

(Disclaimer: This has been built as a generic skill to be used in any agentic harness -
[opencode](https://github.com/anomalyco/opencode), [hermes-agent](https://github.com/nousresearch/hermes-agent) etc
but we have not yet tested in other harnesses. Please exercise caution when using in other harnesses and provide
bug-reports, suggestions and improvements in
[github discussions](https://github.com/Nistapp/codebase-agentic-readiness-framework/discussions).)

1. Clone the latest release (the `main` branch) and start Claude Code in it:

   ```bash
   git clone --branch main https://github.com/Nistapp/codebase-agentic-readiness-framework.git
   cd codebase-agentic-readiness-framework
   claude
   ```

2. Say: **"Audit /path/to/your/repo and write the output to /path/to/output"**.
3. You will find a folder `/path/to/output/` with the readiness report `<repo-name>.audit-report.<timestamp>.json`
   and a markdown summary `<repo-name>.audit-report.<timestamp>.md`. Review them but do not edit them.
4. You have full control on what/how to implement during the 'implementation' phase. You can prescribe, customise,
   skip or accept the defaults provided by the tool. When you are ready to implement, open claude (fresh session is
   recommended for clean context) in the same directory as this skill and say: **"Start implementing the fixes on
   /path/to/your/repo based on /path/to/output/\<repo-name\>.audit-report.\<timestamp\>.json"**. First, the skill
   asks you to copy the report (`.json` and `.md`) into your repository under `docs/agentic-readiness-report/` and
   commit it. It does not copy the report itself.

What happens: the skill asks a few questions, shows you a plan, and asks before each step that changes something.
The audit never writes inside your repository. The implement skill commits on local branches. It never merges, and
it pushes a branch only if you opt in.

## Other ways to use it

| You want to | Read |
| --- | --- |
| Install the skills from the release zips, with no clone | [Install the skills](docs/how-to/install-the-skills.md) |
| See a real run: one repository audited, fixed and audited again | [Worked example](audit/schema/examples/server-worked-example/README.md) |
| Start a new repository that is agent-ready from the first commit | [Greenfield](greenfield/README.md) |
| See every check an audit runs, and what an implement run changes | [Audit master list](docs/reference/audit-master.md), [Implement master list](docs/reference/implement-master.md) |
| Read the method: the seven phases and the requirements | [Phased approach](docs/framework/phased-approach.md), [`spec/`](spec/README.md) |
| Find any other page | [Documentation index](docs/README.md) |

## Platforms

- **Linux:** tested.
- **macOS:** the tools are tested in CI. The Claude Code path above is not yet checked by hand. macOS ships an older
  Python; install Python 3.11 or newer, for example with Homebrew.
- **Windows:** not tested. WSL may work.

## Contributing

Start at [`CONTRIBUTING.md`](CONTRIBUTING.md): the repository map, the gates (`make check`, `make security`) and the
commit rules. Agents read [`AGENTS.md`](AGENTS.md). To give your coding agent the code index here, see
[Set up the agent tools](docs/how-to/set-up-agent-tools.md).

`dev` is the default branch and holds the work in progress; `main` holds the latest release. Start your branch from
`dev` and open your pull request into `dev`. Nobody commits to `dev` or `main` directly, and only `dev` is promoted
to `main`. Step by step: [Contribute a change](docs/how-to/contribute-a-change.md). How a release is made:
[`RELEASE_PROCESS.md`](RELEASE_PROCESS.md). Report a security problem privately: see
[`SECURITY.md`](SECURITY.md). Changes are listed in [`CHANGELOG.md`](CHANGELOG.md).

## Licence

Documentation, schemas and published outputs: GFDL-1.3 ([`LICENSE`](LICENSE)). Code: AGPL-3.0-or-later
([`LICENSE-CODE`](LICENSE-CODE)). Details: [licensing](docs/reference/licensing.md).
