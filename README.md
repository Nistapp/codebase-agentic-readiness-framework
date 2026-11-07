# Codebase Agentic Readiness Framework

> *"The more you sweat in peace, the less you bleed in war."* Preparing a codebase for AI coding agents is the sweat;
> agents changing it from user prompts is the war.

This framework says what makes a codebase safe for AI coding agents, and gives you two skills that act on it.
The **audit** skill measures an existing repository and writes an evidence-cited readiness report. The **implement**
skill then fixes the confirmed findings, one theme at a time, on a branch per theme.

## Quick start

You need [Claude Code](https://claude.com/claude-code), `git` and Python 3.11 or newer.

1. Clone this repository and start Claude Code in it:

   ```bash
   git clone https://github.com/Nistapp/codebase-agentic-readiness-framework.git
   cd codebase-agentic-readiness-framework
   claude
   ```

2. Say: **"Audit /path/to/your/repo and write the output to /path/to/output"**.
3. When the report is final, say: **"Start implementing the fixes on /path/to/your/repo based on
   /path/to/output/\<report\>.json"**.

What happens: the skill asks a few questions, shows you a plan, and asks before each step that changes something.
The audit never writes inside your repository. The implement skill commits on local branches. It never merges, and
it pushes a branch only if you opt in.

## Other ways to use it

| You want to | Read |
| --- | --- |
| Install the skills from the release zips, with no clone | [Install the skills](docs/how-to/install-the-skills.md) |
| See a real run: one repository audited, fixed and audited again | [Worked example](audit/schema/examples/server-worked-example/README.md) |
| Start a new repository that is agent-ready from the first commit | [Greenfield](greenfield/README.md) |
| Read the method: the seven phases and the requirements | [Phased approach](docs/framework/phased-approach.md), [`spec/`](spec/README.md) |
| Find any other page | [Documentation index](docs/README.md) |

## Platforms

- **Linux:** tested.
- **macOS:** the tools are tested in CI. The Claude Code path above is not yet checked by hand. macOS ships an older
  Python; install Python 3.11 or newer, for example with Homebrew.
- **Windows:** not tested. WSL may work.

## Contributing

Start at [`CONTRIBUTING.md`](CONTRIBUTING.md): the repository map, the gates (`make check`, `make security`) and the
commit rules. Agents read [`AGENTS.md`](AGENTS.md). Report a security problem privately: see
[`SECURITY.md`](SECURITY.md). Changes are listed in [`CHANGELOG.md`](CHANGELOG.md).

## Licence

Documentation, schemas and published outputs: GFDL-1.3 ([`LICENSE`](LICENSE)). Code: AGPL-3.0-or-later
([`LICENSE-CODE`](LICENSE-CODE)). Details: [licensing](docs/reference/licensing.md).
