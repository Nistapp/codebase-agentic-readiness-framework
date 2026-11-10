# ADR policy

This page says how to write, change and delete an architecture decision record (ADR) in this repository. It is a
variant of the usual ADR conventions, tuned for AI agents rather than people. Agents load ADRs as instructions,
so a stale or historical ADR is a defect, not a record.

Every ADR folder follows it: the root `docs/architecture/adrs/`, `spec/decisions/`, `audit/docs/architecture/adrs/`,
`implement/docs/architecture/adrs/` and `audit/engine/docs/architecture/adrs/`. Where each decision goes is
[ADR 0001](architecture/adrs/0001-decisions-live-beside-the-component.md).

## Rules

1. **Git is the archive.** Do not manage an ADR lifecycle. An ADR has no status, date, review stamp, list of
   deciders or change log. `git log --follow <file>` gives its history.
2. **State the current decision only.** Write in the present tense. Do not write "previously", "in v1 we" or
   "was changed on". Leave out plan step IDs, question IDs and dated owner notes.
3. **Decision changed: overwrite the ADR in place.** Keep the file name and the number. Turn the old choice into
   one row of *Alternatives Considered*, with the reason it is rejected now. Never write a second ADR that
   supersedes the first.
4. **Decision superseded or no longer needed: delete the file.** In the same change, remove its index row and every
   link to it and mention of it. Never refer to a deleted ADR again, not even to say it was removed.
5. **Number a new ADR** as the highest number ever used in its folder, plus one. Find deleted numbers with
   `git log --diff-filter=D --name-only -- <folder>`. Never reuse a number, so an old commit message cannot point
   at a different decision.
6. **Write an ADR only when it earns its place.** Record a decision an agent would otherwise get wrong or reopen.
   Typical cases are a dependency, a boundary, a safety rule or a format contract. Put a one-line rule in
   `AGENTS.md` instead. Put a local detail in a code comment.
7. **Keep it small.** One decision per ADR, under about 100 lines. Link to the code, the spec and other pages; do
   not restate them.
8. **Index it.** The root index, [`architecture/adrs/README.md`](architecture/adrs/README.md), lists every ADR in
   every folder: number, title and a one-line summary. Add, change or remove the row in the same change as the ADR.
9. **Start from the template**, [`templates/adr-template.md`](templates/adr-template.md). Keep its four sections:
   Context, Decision, Alternatives Considered, Consequences.
10. **Never invent a rationale.** When the reason for a decision is not in the repository, write "Rationale not
    recorded; owner to fill in".
11. **Read only the ADRs you need.** Use the index summaries to pick the ADRs that govern the folder you change.

## Where else this applies

- The implement recipe writes ADRs into a target repository under the same rules. See the
  [`establish-docs-contract`](../implement/playbooks/establish-docs-contract.md) playbook.
- The greenfield templates ship a copy of this policy for new repositories:
  [`greenfield/templates/docs/ADR_POLICY.md`](../greenfield/templates/docs/ADR_POLICY.md).
