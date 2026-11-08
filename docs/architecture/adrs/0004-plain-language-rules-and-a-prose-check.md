# 0004. Plain-Language Rules in One File, Checked by a Standard-Library Prose Check

* **Status:** Accepted
* **Date:** 2026-11-08
* **Last reviewed:** 2026-11-08
* **Deciders:** [@nistapp]

---

## Context

The owner found AI output and some docs dense and hard to follow. In chat, the owner asked agents for four things:

* STE100 (Simplified Technical English);
* explanations aimed at an intern;
* Mermaid diagrams;
* options with a recommendation before a decision.

Each session had to ask again, and no rule said how a doc page should read.

Measured on 2026-11-08: 11 of 71 doc pages had a Mermaid diagram. Four pages averaged 30 to 39 words per sentence.
STE100 sets 20 words for a procedure step and 25 for other text.

Three questions needed an answer:

1. Where do the rules live, so that every harness reads them?
2. How much of STE100 do we adopt?
3. Does a tool check the rules, and which tool?

---

## Decision

**Rules.** [`COMMUNICATION_RULES.md`](../../../COMMUNICATION_RULES.md) at the root holds all the rules for writing for people:

* the reader persona: a new engineer who knows Git, Python and Markdown, but not this repository or its terms;
* nine plain-language rules taken from the STE100 writing rules, without its approved word list;
* the diagram rules;
* the layouts for status reports, done reports and decision requests.

[`AGENTS.md`](../../../AGENTS.md) carries a six-line summary, because every harness loads it. The style guide
([`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md)) adds only the rules for doc pages and links to the rest.

**Check.** [`dev/prose_check.py`](../../../dev/prose_check.py) is a standard-library script with three rules:

* `PL001`: a sentence of more than 25 words, or more than 20 in a numbered step;
* `PL002`: a vague or padded word, such as `simply` or `in order to`;
* `PL003`: an explanation page or a tutorial without a Mermaid diagram.

`make docs-lint` runs it two ways:

* on the `PROSE_PATHS` list in the `Makefile`, which must have zero issues;
* on all tracked Markdown, whose count may not rise above the `prose` entry of `.quality-baseline.json`.

Both are ratchets. A page joins `PROSE_PATHS` once it is clean.

**Scope.** The rules apply to this repository: agent messages and docs. How the audit and implement recipes talk to
their users, and whether target repositories get a matching requirement, is listed for v0.3.4.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| The full STE100 standard, with its approved word list | Made for maintenance manuals. The word list blocks the technical terms this repository needs. |
| Rules only in `AGENTS.md` | Every line costs context in every session, and `AGENTS.md` is already long. |
| Rules only in `COMMUNICATION_RULES.md` | Agents often skip a linked file. The short summary in `AGENTS.md` keeps the core in view. |
| Vale with a custom STE style (the v0.3.3 A4 pilot) | A Go binary: not on PyPI or npm, so it cannot be pinned the ADR 0003 way. Our three rules need about 200 lines of Python. |
| Rules without a check | Rules without a check drift. Chat cannot be checked, but docs can. |

---

## Consequences

### Positive

* Every harness that reads `AGENTS.md` gets the core rules, and the full rules are one link away.
* New and edited pages in `PROSE_PATHS` stay readable; the full-tree count can only go down.
* No new pinned tool, and no network.

### Negative / Trade-offs

* The sentence splitter is a heuristic. It can miss a split, for example after a code span that ends with a full
  stop. Rewording the sentence fixes it.
* The full-tree count starts high (about 1,680 issues on 2026-11-08). Most pages join the list only when someone edits
  them.
* The check cannot see passive voice, one meaning per word or the bottom-line-first rule. People and agents apply
  those.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or
  `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into
  *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference
  plus the index table in `docs/architecture/adrs/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/0004-plain-language-rules-and-a-prose-check.md`.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
