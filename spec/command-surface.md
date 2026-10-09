# Command surface

Normative. This page fixes the verbs a repository exposes to agents, humans and CI, and how each runner spells them. The requirements in [readiness-requirements.md](readiness-requirements.md) link here instead of restating the table. The keywords **MUST**, **SHOULD** and **MAY** are used as in [spec/README.md](README.md#requirement-language).

## The verbs

A verb is the name of one command. The verbs are the contract; the runner that carries them is a local choice. Every verb exits non-zero on failure.

| Verb | What it does | Writes to the working tree | Part of `check` |
|---|---|---|---|
| `format` | Rewrites formatting in place. | Yes | No |
| `format:check` | Read-only verification of formatting and lint rules. Exits non-zero on drift. | No | Yes, first |
| `lint` | Read-only lint. | No | No |
| `typecheck` | Strict type check of source and tests. Zero errors. | No | Yes, second |
| `test` | The full test suite. Every test passes. | No | Yes, third |
| `check` | The single pre-PR and CI gate. Runs `format:check`, `typecheck` and `test`, in that order. | No | — |
| `security` | Dependency vulnerability gate. | No | No |

The surface is these seven commands. Older framework text calls the set "the six verbs", counting `format` and `format:check` as one concern with a write form and a read-only form. Both forms are required.

## Spelling per runner

The rules:

1. A repository defines the verbs on one **authoritative runner**. A second runner MAY exist only to delegate to the first (for example `make check` that runs `npm run check`).
2. On every runner except Maven, a verb is spelled as its own name. Only `format:check` has other spellings, because the colon is not a legal or portable name character on every runner.
3. Each runner below lists the accepted spellings of `format:check`. The first is preferred and is what new repositories and playbooks write.
4. A repository MUST write down, in its instruction file, the command that runs each verb.

| Runner | Where the verbs are defined | `format:check` spelling | Invocation |
|---|---|---|---|
| npm scripts (npm, pnpm, yarn, bun) | `scripts` in `package.json` | `format:check` | `npm run <verb>` (`npm test` for `test`); `pnpm run <verb>`; `yarn <verb>`; `bun run <verb>` |
| Make | Targets in `Makefile` | `format\:check`, or the alias `format-check` | `make <verb>`: `make format:check` or `make format-check` |
| Taskfile | `tasks:` in `Taskfile.yml` or `Taskfile.yaml` | `format:check` | `task <verb>` |
| pyproject task runners (poethepoet, taskipy) | `[tool.poe.tasks]` or `[tool.taskipy.tasks]` in `pyproject.toml` | `format-check` | `poe <verb>`; `task <verb>` |
| Gradle | Tasks registered in `build.gradle` or `build.gradle.kts` | `formatCheck` | `./gradlew <verb>` |
| Maven | Lifecycle phases and plugin goals; Maven has no named tasks | See the Maven table | `./mvnw <phase or goal>` |

Notes on the table:

- **Make.** A Makefile MUST define at least one of the two spellings and SHOULD define both, so that `make format:check` and `make format-check` both run. An unescaped `format:check:` target is not valid Make: GNU Make 4.4.1 refuses the file with `target pattern contains no '%'`.
- **Taskfile.** Task's own style guide separates namespace and task name with a colon, so `format:check` is idiomatic ([style guide](https://taskfile.dev/docs/styleguide)).
- **pyproject task runners.** Neither tool documents a colon as a character of a task name; poethepoet's documentation shows hyphenated names. The hyphen is used for that reason.
- **Gradle.** A colon separates project and task names in a Gradle task path (`:subproject:task`), so it is not used inside a task name. `test` and `check` are Gradle's own lifecycle tasks; `check` MUST be wired to depend on the formatting check. Every other verb is an aggregate task the build registers under that name.
- **Gradle and Maven** are invoked through the committed wrapper, `./gradlew` or `./mvnw`, never through a system-wide installation.

### Maven

Maven names phases and plugin goals, not tasks. The defaults below use the Spotless, Checkstyle and OWASP dependency-check plugins; the plugin is a local choice, but the repository MUST state in its instruction file the invocation it uses for each verb.

| Verb | Default invocation |
|---|---|
| `format` | `./mvnw spotless:apply` |
| `format:check` | `./mvnw spotless:check` |
| `lint` | `./mvnw checkstyle:check` |
| `typecheck` | `./mvnw compile test-compile` |
| `test` | `./mvnw test` |
| `check` | `./mvnw verify`, with the format check bound to a phase that runs no later than `verify` |
| `security` | `./mvnw org.owasp:dependency-check-maven:check` |

### A runner this table does not cover

Just, mise, Rake, Cargo aliases, hatch, pdm, `uv run` scripts and shell scripts are not listed. A repository on such a runner MUST still expose all seven verbs under one idiomatic spelling per verb. An audit proposes the spelling that follows the nearest row above, asks the repository owner to confirm it, and records it in the report. The audit never invents a verb the repository does not define.

## Last checked

The colon rules for Make, Taskfile, Gradle, poethepoet and taskipy were read against the runners' current documentation on 2026-10-09. The documentation of poethepoet and taskipy says nothing about colons in task names, and Gradle's says only that a colon separates path segments; the spellings above are the ones that avoid the question. The Make rule was also run: this repository's `Makefile` defines both `format\:check` and `format-check`, `make format:check` and `make format-check` both succeed with GNU Make 4.4.1, and CI runs `make check` on Linux and macOS, so the file with the escaped target parses on both.
