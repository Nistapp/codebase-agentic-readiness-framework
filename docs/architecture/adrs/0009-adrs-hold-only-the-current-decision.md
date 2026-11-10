# 0009. ADRs Hold Only the Current Decision; Stale and Unnecessary Ones Are Deleted

## Context

The usual ADR conventions were written for people. A record keeps a status (proposed, accepted, superseded,
deprecated), a date and its deciders. A changed decision gets a new record, and the old one stays as a tombstone
that points forward. For a person, that file history is the archive.

In this repository the main readers of an ADR are AI coding agents. An agent loads an ADR as an instruction. It
has no reliable sense of time, and it often reads one record without the record that supersedes it. A
superseded, deprecated or no-longer-needed ADR in an agent's context is therefore not history: the agent can
apply it as a current rule. Every stale line also costs context that a current rule could use.

Git already keeps every past version of every file, with its author and date. The file does not need to keep
them too.

## Decision

1. **An ADR states only the current decision.** It has no status, date, review stamp, decider list or change log.
   [`docs/ADR_POLICY.md`](../../ADR_POLICY.md) holds the rules.
2. **A changed decision is overwritten in place.** The old choice becomes one row of *Alternatives Considered*,
   with the reason it is rejected now. No second ADR supersedes the first.
3. **A stale or unnecessary ADR is deleted,** with its index row and every reference to it. Nothing refers to a
   deleted ADR again. Its number is retired.
4. **An ADR is written only when it earns its place.** It records a decision an agent would otherwise get
   wrong.
5. **The same rules reach other repositories.** The implement recipe writes ADRs into a target under them, and
   the greenfield templates ship them.

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| A status lifecycle with superseded records kept (Nygard, MADR) | Agents read a superseded record as a current instruction, and the tombstones fill their context. |
| Move stale ADRs to an archive folder | Search and code-index tools still find the folder, so agents still load the stale records. |
| Keep only `Status: Accepted` and a date | Every merged ADR is accepted, and git holds the date. The fields add noise and no meaning. |
| A history section inside each ADR | It puts past decisions back in the context the policy keeps clean. `git log --follow` gives the history. |

## Consequences

### Positive

- An agent that loads an ADR gets a rule that holds today.
- ADRs stay short, so an agent can load the ones it needs without spending context on history.
- A reader sees each rejected option and its current reason in one table.

### Negative / Trade-offs

- A person who wants the history of a decision runs `git log --follow` on the file.
- A link to a deleted ADR from outside the repository (an old pull request, an issue) stops resolving.
  The file stays in git history.
- Deleting a record takes judgement: the person who changes the code must decide that the ADR is stale.
