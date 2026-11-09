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
- **Not done:** 5 checks are `UNKNOWN`: `IDX-01`, `IDX-02`, ...; the scan cannot read them.
- **Blocked:** nothing. (Or: what stops you, and what you need.)
- **Next:** Stage 3. The draft is `/full/path/to/<label>.audit-report.draft.json`.
```

## Done report and pull request description

The last message of a run is a done report. So is the description of a theme's pull request, and of the triage
pull request. Use these three headings, exactly, as Markdown headings:

```markdown
## What changed

- F-001 `CMD-01`: added the `check` verb (`a1b2c3d`). Done.
- F-004 `TST-02`: added a ratchet; 12 failing tests counted as debt (`d4e5f6a`). Partial.

## How it was checked

- `make check`: passed.
- Engine re-check: `CMD-01` PASS, `TST-02` PARTIAL (the debt above).

## What was not done

- Skipped by the owner: F-007 `CI-01` ("CI comes next quarter").
- Failed or blocked: none.
- Engine limits: `CMD-02` stays `UNKNOWN` on Gradle; verified by hand.
- Checks that pass with no item: `CMD-03`.
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
| a. Native runner | One runner; the engine reads it | `CMD-02` stays `UNKNOWN` | 1 file | Easy: one revert |
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
**F-003, blocker 1 of 5: `CMD-01`.** The command surface has no `check` verb.

- **Evidence:** `Makefile` has no `check` target (*checked*: the engine read it).
- **My verification:** I read `Makefile` and `package.json`; neither defines `check` (*checked*).
- **Options:** a. confirmed; b. rejected (a false positive); c. deferred (real, left open on purpose);
  d. edited (the wording or the evidence needs a fix first).
- **Recommendation:** a, because both files lack the verb.
- **Default:** none. A blocker needs your answer.
```

Other findings, one numbered table per batch:

```markdown
**Batch 2 of 4: documentation (`DOC-`), 3 findings.**

| # | Finding | Check | Severity | Statement | Recommendation |
|---|---|---|---|---|---|
| 1 | F-010 | `DOC-02` | COSMETIC | No style guide | a. confirmed |

Options per row: a. confirmed; b. rejected; c. deferred; d. edited. Reply "all a", or "all a except 2c".
**Default:** none; the batch waits for your reply.
```

## Triage (implement Stage 1)

One numbered table per theme. Keep is the default, because a kept finding stays `queued` and nothing changes.
You never skip or defer on your own.

```markdown
**Triage: T1 Command surface (theme 1 of 8), 4 findings.**

| # | Finding | Check | Severity | Statement | Playbook |
|---|---|---|---|---|---|
| 1 | F-001 | `CMD-01` | BLOCKER | No `check` verb | `define-command-surface` |

Options per row: a. keep; b. skip (final: never offered again); c. defer (kept for later). Give a reason for b
or c. Reply "all a", or "all a except 3b: we use Bazel".
**Default:** a (keep).
```
