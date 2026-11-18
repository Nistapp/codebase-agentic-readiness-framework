# Code Conventions

This file holds the code rules for **[Project Name]** that no tool enforces and that a reader cannot infer from
the code. It is for people and AI agents. Change a rule here, in one place; other files link to it.

The tools enforce the rest. Read their configs, and never copy their settings here:\
a. [`biome.json`](biome.json) sets formatting, import order and the lint rules, including no `any`.\
b. [`tsconfig.json`](tsconfig.json) sets `strict` mode and the module system.\
c. [`.editorconfig`](.editorconfig) sets line endings and indentation for every editor.

---

## 1. Naming

| Thing | Style | Example |
|---|---|---|
| Source files | `kebab-case.ts` | `file-system.ts` |
| Test files | The source name plus `.test.ts` | `file-system.test.ts` |
| Types and classes | `PascalCase` | `RunResult` |
| Interfaces | `PascalCase` with an `I` prefix | `IFileSystem` |
| Test doubles | The interface name without `I`, plus `Stub` or `Mock` | `FileSystemStub` |
| Functions and variables | `camelCase` | `readConfig` |
| Module-level constants | `UPPER_SNAKE_CASE` | `USAGE` |

1.1 Name a function for what it returns or does: `readConfig`, not `handleConfig`.

1.2 Use the terms in [`docs/architecture/glossary.md`](docs/architecture/glossary.md) for names in the domain.

---

## 2. Layering

2.1 The layers, and what each may import, are in [`AGENTS.md`](AGENTS.md) §2. Every agent reads them there.

2.2 Where new code goes:\
a. Domain logic goes in `src/core/`. It takes its dependencies as interfaces.\
b. A new dependency on the outside world gets an interface in `src/core/interfaces.ts` first.\
c. Argument parsing and output to the terminal go in `src/cli/`.\
d. A symbol that package users may rely on is exported from `src/core/index.ts`. Everything else stays internal.

---

## 3. Errors and logging

3.1 Throw an `Error` subclass with a message that names the input and what was wrong. Never throw a string.

3.2 Never swallow an error. Catch it only to add context, to recover, or to turn it into an exit code.

3.3 `src/cli/` turns an error into a message on standard error and a non-zero exit code. Core code never calls
`process.exit`.

3.4 Log through the injected `ILogger` from `src/core/interfaces.ts`. Core code never writes to the console.

3.5 Put values in the context object, not in the message: `logger.info('Config read', { path })`.

3.6 Never log a secret, a token or a full environment.

---

## 4. Testing

4.1 Vitest runs `src/**/*.test.ts` and `test/**/*.test.ts` ([`vitest.config.ts`](vitest.config.ts)). Put a unit
test in `test/`, in the folder that mirrors its source.

4.2 A unit test builds its subject with stubs for each interface. Name the stubs as in section 1.

4.3 Name a test for the behaviour it checks: `it('returns an empty list when the folder is empty')`.

4.4 The test prohibitions (no real I/O, a positive and a negative test per public method, no skipped test) are in
[`AGENTS.md`](AGENTS.md) §6.

---

## 5. Changing these conventions

5.1 Propose a change in a pull request that edits this file. Say why in the description.

5.2 When a tool can enforce a rule, move the rule into the tool's config and delete it here.
