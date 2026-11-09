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

## Messages

Use the same layout each time, so the reader knows where to look.

**Status report** (at the end of a stage or a theme):

- **Done:** what is finished.
- **Not done:** what is left.
- **Blocked:** what stops you, and what you need.
- **Next:** what you do next.

**Done report** (at the end of a run, and in a pull request description):

- **What changed:** files, commits or report entries.
- **How it was checked:** the command and its result, for example "`make check`: passed".
- **What was not done:** skipped steps and known gaps. Say so plainly.

**Length:** keep a chat message short. Put long material in a file in the output folder or the state file.
Give its full path in the message. A written file, such as the report or a pull request description, may hold
a Mermaid diagram of a flow.

## Decision requests

When the person must decide, give them what they need to decide quickly:

1. **Context:** the problem and why a decision is needed now, in two to four sentences.
2. **Options:** two to four, in a table with pros and cons.
3. **Recommendation:** the option you pick, and why, in one or two sentences.
4. **Default:** what happens if the person does not choose. Never act on a default where the recipe says to
   stop and ask.

When you ask several questions, number them and letter the options, so the person can answer "1b, 2a".
