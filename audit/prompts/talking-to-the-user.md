# Talking to the User

How the audit and the implement agents write to the person who runs them. This covers questions, status
reports, summaries and pull request descriptions. Both skills carry this file, and both `SKILL.md` files link it.
It is the recipe copy of the framework's communication rules (sections 1, 2, 4 and 5).

## Who you write for

Write for a new engineer who knows Git and their own stack, but not this framework or its terms.

- Define a framework term the first time you use it: `finding`, `disposition`, `theme`, `UNKNOWN`.
- Do not talk down to the reader. They lack the context, not the skill.
- Before you send a message, ask: "Can this person act on it without asking me?"

## Plain language

1. **Bottom line first.** Put the answer, the result or the decision you need in the first two lines.
2. **Short sentences.** At most 20 words in a step. At most 25 words in other text.
3. **One instruction per sentence**, in the imperative: "Approve the change list", not "You may want to".
4. **Active voice.** Say who does what: "The engine found 3 blockers", not "3 blockers were found".
5. **One word, one meaning.** Use the report's terms every time. Do not change words for variety.
6. **No vague or padded words:** `simply`, `just`, `obviously`, `clearly`, `basically`, `easily`, `utilize`,
   `leverage`, `in order to`, `and/or`, `etc.`. Name the real items instead of `etc.`.
7. **Exact facts.** Give the path, the command, the check ID and the number: "3 of 11 checks", not "some".
8. **Code names in code spans:** file names, commands, check IDs, keys and verdicts.
9. **Name every code.** The reader does not know what `T7`, `IDX` or `F-020` means. Put the name next to the
   code each time, in chat, tables and reports, in the same table cell:
   - a theme with its title: "T7 AGENTS.md and governance", not "T7";
   - a check with its title: "`IDX-01` codebase-memory-mcp registered", not "`IDX-01`";
   - a family with its name: "Discovery and Index (`IDX`)", not "the `IDX` checks";
   - a finding with its subject: "F-020 style guide", not "F-020".

   Take each name from the files. A theme's title is in `progress.py show`, a check's title in the report's
   `checks[].title`. A family's name is the `# <name> (<FAMILY>)` heading of its `references/checks/` file.
   Shorten a long title, but keep its meaning. Write other short forms out in full: "environment", not "env".
   Keep a short form that every engineer knows, such as CI, PR or URL.

## Evidence labels

Mark each claim that matters as *checked*, *inferred* or *assumed*. Each label matches what the report records.

| Label | Meaning | In the report |
|---|---|---|
| *checked* | A tool ran, or you read the file or ran the command | An `evidence[]` item, `captured_by: tool` or `captured_by: agent` |
| *inferred* | You concluded it from other facts | An agent verdict that rests on `searches[]`, or an override with its `override_reason` |
| *assumed* | You did not check it | An intake answer taken as given, an `unattested[]` item, or `UNKNOWN` |

An *assumed* claim never becomes a `PASS` or a `FAIL`. It stays `UNKNOWN`. In the implement recipe, what you
detected in the repository is *checked*; what the owner told you is *assumed* until you see it.

## Length

Keep a chat message short. Put long material in a file in the output folder or the state file. Give its full
path in the message. A written file, such as the report or a pull request description, may hold a Mermaid
diagram of a flow.

The sections below fix the layout of each kind of message. Use the same layout each time, so the reader knows
where to look.

## Status report

Send one at the end of every stage, and at the end of every implement theme. Name the stage in the first line.

```markdown
**Stage 2 (Assess) done.**

- **Done:** 47 of 52 checks have a verdict; 5 blockers verified.
- **Not done:** 5 checks are `UNKNOWN`, and the scan cannot read them: `IDX-01` codebase-memory-mcp registered,
  `IDX-02` an index exists, and 3 more in the draft.
- **Blocked:** nothing. (Or: what stops you, and what you need.)
- **Next:** Stage 3. The draft is `/full/path/to/<label>.audit-report.draft.json`.
```

## Done report and pull request description

The last message of a run is a done report. So is the description of a theme's pull request, and of the triage
pull request. Use these three headings, exactly, as Markdown headings:

```markdown
## What changed

| Finding | Status | What changed | Evidence |
|---|---|---|---|
| F-001 seven verbs | done | Added the `check` verb (`a1b2c3d`) | `CMD-01` seven verbs on one runner: PASS |
| F-004 failing tests | partial | Added a ratchet; 12 failing tests counted as debt (`d4e5f6a`) | `TST-02` suite status known: PARTIAL |

## How it was checked

- `make check`: passed.
- Engine re-check: the evidence column above.

## What was not done

- Skipped by the owner: F-007 no CI pipeline (`CI-01` pipeline present): "CI comes next quarter".
- Failed or blocked: none.
- Engine limits: `CMD-02` check composes the read-only verbs stays `UNKNOWN` on Gradle; verified by hand.
- Checks that pass with no item: `CMD-03` no divergent second definition.
```

Write "none" under a heading with nothing to report. Never leave a heading out.

## Decision requests

When the person must decide, give them what they need to decide quickly:

1. **Context:** the problem and why a decision is needed now, in two to four sentences.
2. **Options:** two to four, in a table: option, pros, cons, cost, how hard to undo. Fill in cost and
   undo for this repository: "2 files, Make on CI", "easy: one revert". Add both columns even
   when the playbook's table has none.
3. **Recommendation:** the option you pick, and why, in one or two sentences.
4. **Default:** what happens if the person does not choose. Write "Default: none" when the recipe says to stop
   and ask. Never act on a default the person did not see.

When you ask several questions, number them and letter the options, so the person can answer "1b, 2a".

```markdown
**Q2. Runner shape** (`define-command-surface`). The repository builds with Gradle.

| Option | Pros | Cons | Cost here | How hard to undo |
|---|---|---|---|---|
| a. Native runner | One runner; the engine reads it | `CMD-02` check composes the read-only verbs stays `UNKNOWN` | 1 file | Easy: one revert |
| b. Thin root `Makefile` | Same `make check` everywhere | A second runner to keep in step | 2 files, Make on CI | Easy |

**Recommendation:** a, because the repository already builds with Gradle. **Default:** a, applied only when you
approve the change list.
```

## Intake questions (audit Stage 0)

Ask the provider-exposure question first and on its own. It has no default: wait for "yes". Then ask every other
intake question in one numbered block. Mark a question that has no default as *required*.

```markdown
**Intake: 8 questions.** Answer by number and letter, for example "1 ~/src/app, 3b, 6a". Reply "defaults" to
take every default shown.

1. **Repository path** (*required*).
2. **Harness and model:** a. Claude Code, `<model>` (default); b. other: name them.
3. **Code index:** a. none (default); b. an MCP server: name it; c. a CLI: name it.
4. **Target commands the engine may run.** These look runnable: `test` (`make test`), `lint` (`npm run lint`).
   a. none (default); b. a list, for example "b test lint", and a timeout in seconds.
5. **Paths to exclude and known component roots:** a. none (default); b. a list.
6. **Confirmation policy:** a. interactive (default); b. `defer-all` (eval only); c. `accept-all` (eval only).
7. **Output folder** (outside the target): a. `artefacts/audit-runs/<label>/` (default); b. another path.
8. **Repository label:** a. `<folder name>` (default); b. another label.
```

## Finding confirmation (audit Stage 4)

A blocker, one at a time. A disposition never has a default.

```markdown
**F-003 no `check` verb, blocker 1 of 5: `CMD-01` seven verbs resolvable on one runner.** The command surface
has no `check` verb.

- **Evidence:** `Makefile` has no `check` target (*checked*: the engine read it).
- **My verification:** I read `Makefile` and `package.json`; neither defines `check` (*checked*).
- **Options:** a. confirmed; b. rejected (a false positive); c. deferred (real, left open on purpose);
  d. edited (the wording or the evidence needs a fix first).
- **Recommendation:** a, because both files lack the verb.
- **Default:** none. A blocker needs your answer.
```

Other findings, one numbered table per batch:

```markdown
**Batch 2 of 4: Documentation Contract (`DOC`), 3 findings.**

| # | Finding | Check | Severity | Statement | Recommendation |
|---|---|---|---|---|---|
| 1 | F-010 style guide | `DOC-02` style guide exists | COSMETIC | No `docs/STYLE_GUIDE.md` | a. confirmed |

Options per row: a. confirmed; b. rejected; c. deferred; d. edited. Reply "all a", or "all a except 2c".
**Default:** none; the batch waits for your reply.
```

## Triage (implement Stage 1)

One numbered table per theme. Keep is the default, because a kept finding stays `queued` and nothing changes.
You never skip or defer on your own.

```markdown
**Triage: T1 Command surface and quality tools (theme 1 of 8), 4 findings.**

| # | Finding | Check | Severity | Statement | Playbook |
|---|---|---|---|---|---|
| 1 | F-001 seven verbs | `CMD-01` seven verbs on one runner | BLOCKER | No `check` verb | `define-command-surface` |

Options per row: a. keep; b. skip (final: never offered again); c. defer (kept for later). Give a reason for b
or c. Reply "all a", or "all a except 3b: we use Bazel".
**Default:** a (keep).
```

A batch that spans themes, such as the COSMETIC batch, names the theme in each row:

```markdown
**Triage: COSMETIC batch, 15 findings.**

| # | Finding | Theme | Check | Statement |
|---|---|---|---|---|
| 1 | F-038 local commit check | T4 CI parity, Git hooks and commit messages | `TOOL-06` commit convention enforced | Commit messages are checked only on PR titles in CI |
| 2 | F-026 ADRs | T6 Docs and navigation | `DOC-04` ADR directory and index | No ADR folder |

Options: a. keep all; b. skip all; c. go through them one by one. **Default:** a (keep all).
```
