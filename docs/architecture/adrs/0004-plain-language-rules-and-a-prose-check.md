# 0004. Plain-Language Rules in One File, Checked by a Standard-Library Prose Check

* **Status:** Accepted
* **Date:** 2026-11-08
* **Last reviewed:** 2026-11-09
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
4. Does the check block a change, or only advise?

---

## Decision

**Rules.** [`docs/COMMUNICATION_RULES.md`](../../COMMUNICATION_RULES.md) holds all the rules for writing for people:

* the reader persona: a new engineer who knows Git, Python and Markdown, but not this repository or its terms;
* nine plain-language rules taken from the STE100 writing rules, without its approved word list;
* the diagram rules;
* the layouts for status reports, done reports and decision requests.

[`AGENTS.md`](../../../AGENTS.md) carries a six-line summary, because every harness loads it. The style guide
([`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md)) adds only the rules for doc pages and links to the rest.

**Check.** [`dev/prose_check.py`](../../../dev/prose_check.py) is a standard-library script with three rules. Each
issue has a severity:

| Rule | Reports | Severity |
|---|---|---|
| `PL001` | A sentence of more than 25 words | Notice |
| `PL001` | A sentence of more than 40 words, or more than 20 in a numbered step | Warning |
| `PL002` | A vague or padded word, such as `simply` or `in order to` | Warning |
| `PL003` | An explanation page or a tutorial without a Mermaid diagram | Warning |

**Advisory, never blocking.** The rules are guidelines. The check exits 0 whatever it finds. No gate, path list or
baseline count holds it. A writer fixes a warning in the change that touches the text and treats a notice as a hint.

* `make docs-prose [FILES=...]` prints the issues. `PROSE_ARGS=--min-severity=warning` hides the notices.
* The CI `docs` job runs it with `--format github` on the changed Markdown. The issues show as annotations on the
  pull request, and the job does not fail on them.

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
| textlint, with `textlint-rule-terminology` (reviewed 2026-11-09) | Pinnable through `dev/tools/package.json`, and its rules can be warnings. Not needed yet: revisit when passive voice or glossary terms need a check. |
| proselint, write-good, alex, LanguageTool (reviewed 2026-11-09) | proselint is opinionated and hard to configure. write-good and alex are narrow. LanguageTool needs Java. |
| Rules without a check | Rules without a check drift. Chat cannot be checked, but docs can. |
| A blocking check: a zero-issue path list (`PROSE_PATHS`) and a ratchet count in `.quality-baseline.json` (shipped 2026-11-08, reversed 2026-11-09) | Too strict for guidelines. On 2026-11-09, 1,574 of 1,624 issues were `PL001`, and a long sentence is often the clearest one. Blocking on it slowed work without a matching gain. |

---

## Consequences

### Positive

* Every harness that reads `AGENTS.md` gets the core rules, and the full rules are one link away.
* Writers see the issues on their own lines, in the terminal or on the pull request, without being blocked.
* Severities point attention at the issues that matter most: vague words, long steps and missing diagrams.
* No new pinned tool, and no network.

### Negative / Trade-offs

* The sentence splitter is a heuristic. It can miss a split, for example after a code span that ends with a full
  stop. Rewording the sentence fixes it.
* Nothing stops the count from rising. The full tree had 1,624 issues on 2026-11-09. Review, not a gate, keeps new
  text readable.
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
