# 0004. Plain-Language Rules in One File, Checked by a Standard-Library Prose Check

## Context

AI output and some docs are dense and hard to follow. The owner wants four things from agents:

* STE100 (Simplified Technical English);
* explanations aimed at an intern;
* Mermaid diagrams;
* options with a recommendation before a decision.

Without a written rule, each session must ask again, and nothing says how a doc page should read.

Few doc pages have a Mermaid diagram (11 of 71 in one count), and some average 30 to 39 words per sentence.
STE100 sets 20 words for a procedure step and 25 for other text.

Four questions need an answer:

1. Where do the rules live, so that every harness reads them?
2. How much of STE100 do we adopt?
3. Does a tool check the rules, and which tool?
4. Does the check block a change, or only advise?

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
* `make check` does not run it. A check that cannot fail adds only output to the
  gate, and the pull request annotations already show the issues on the changed lines.

**Scope.** The rules apply to this repository: agent messages and docs. The audit and implement recipes carry their
own copy, `audit/prompts/talking-to-the-user.md`, for how they talk to their users. The skill bundles do not ship
this repository's `docs/`.

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| The full STE100 standard, with its approved word list | Made for maintenance manuals. The word list blocks the technical terms this repository needs. |
| Rules only in `AGENTS.md` | Every line costs context in every session, and `AGENTS.md` is already long. |
| Rules only in `COMMUNICATION_RULES.md` | Agents often skip a linked file. The short summary in `AGENTS.md` keeps the core in view. |
| Vale with a custom STE style | A Go binary: not on PyPI or npm, so it cannot be pinned the ADR 0003 way. Our three rules need about 200 lines of Python. |
| textlint, with `textlint-rule-terminology` | Pinnable through `dev/tools/package.json`, and its rules can be warnings. Not needed yet: revisit when passive voice or glossary terms need a check. |
| proselint, write-good, alex, LanguageTool | proselint is opinionated and hard to configure. write-good and alex are narrow. LanguageTool needs Java. |
| Rules without a check | Rules without a check drift. Chat cannot be checked, but docs can. |
| Run the advisory check in `make check` too | It costs little (0.3 s over the whole tree), but it cannot fail, so the gate would only print about 1,750 issues that no one acts on there. The CI annotations put each issue on its own line in the pull request instead. |
| A blocking check: a zero-issue path list (`PROSE_PATHS`) and a ratchet count in `.quality-baseline.json` | Too strict for guidelines. In one count, 1,574 of 1,624 issues were `PL001`, and a long sentence is often the clearest one. Blocking on it slowed work without a matching gain. |

## Consequences

### Positive

* Every harness that reads `AGENTS.md` gets the core rules, and the full rules are one link away.
* Writers see the issues on their own lines, in the terminal or on the pull request, without being blocked.
* Severities point attention at the issues that matter most: vague words, long steps and missing diagrams.
* No new pinned tool, and no network.

### Negative / Trade-offs

* The sentence splitter is a heuristic. It can miss a split, for example after a code span that ends with a full
  stop. Rewording the sentence fixes it.
* Nothing stops the count from rising. Review, not a gate, keeps new text readable.
* The check cannot see passive voice, one meaning per word or the bottom-line-first rule. People and agents apply
  those.
