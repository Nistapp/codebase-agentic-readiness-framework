# 0012. Keep the Consistency Map as a JSON File in `dev/`, Checked by a Standard-Library Script

## Context

The audit engine reads text in a target repository. It may need a phrase on one line, a fenced command in the
root `AGENTS.md`, or a file with a given name. The implement playbooks and the greenfield templates write, move and
renumber that same text. A tidy edit can change what a check reads while every verdict stays the same. Nothing
records which step touches which read, or which sentence keeps the read true.

A fix needs a declaration that a script can join. It holds what each check reads, what each step does, and the
rule that keeps the two in step. It must run offline, in `make` and in CI, with nothing installed. A contributor
must be able to review it in a diff. The document index
([ADR 0011](0011-index-the-documents-with-a-standard-library-tool.md)) already gives section addresses, and its
quote verifier already checks quotes verbatim.

This ADR fixes the map's format and the gate's rules. The schema exists. The map file, its tests and the gate
script are not written yet.

## Decision

1. The consistency map is one JSON file, `dev/consistency-map.json`.
   [`dev/consistency-map.schema.json`](../../../dev/consistency-map.schema.json) is its JSON Schema. A
   standard-library script in `dev/` checks it.
2. The map has five parts:
   1. `reads`: one entry per check in [`audit/catalogue.json`](../../../audit/catalogue.json). It says where and
      what the check reads. It also says how close the parts must be: one line, a window, a paragraph, a section
      or the file.
   2. `moves`: one entry per playbook Commits row and per greenfield template. It says what the row or template
      does to such text: `write`, `move`, `rewrite`, `create` or `none`.
   3. `keeps`: one entry for each move that touches a read. It cites the sentence that keeps the read true, by
      index section address and verbatim quote. Or it is `accepted`, with the maintainer's reason.
   4. `names`: the file and folder names the engine gives a meaning to.
   5. `boundaries`: the implement run's promises that no check reads. Each has one home quote. It says what
      enforces it: a tool refusal, a test, or only the prose.
3. The reads live in the map, not in the engine. A read can name the engine constants that hold its file list
   (`constants`). A `dev/` test compares the two, so a changed constant fails the test.
4. A keeps quote is checked as the quote verifier checks it: verbatim, with whitespace collapsed. Its section
   must still mention the check ID.
5. The gate fails in four cases:
   1. A move touches a read, and no keeps entry covers the pair.
   2. A keeps quote is gone, or its section no longer mentions the check.
   3. A catalogue check has no reads entry, or a Commits row has no moves entry.
   4. A created file matches the names list and its moves entry has no `intent`.
6. Evidence that changes under an unchanged verdict is reported to the reviewer. It does not fail the gate.
7. The gate runs first as its own report-only `make` target. It joins `make check` once every check has a reads
   entry and every Commits row a moves entry.

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| RDF with SHACL shapes | Needs dev-only packages (`rdflib`, `pyshacl`) and is a steep step for contributors |
| CUE over the JSON | Adds a Go tool and a new language for three joins a short script does |
| Datalog facts | Needs a dev-only engine and has few readers; it stays open if the queries outgrow a script |
| LikeC4, Alloy or TLA+ models | They model architecture or states, not the text a check reads |
| The reads beside each check in the engine registry | An engine change for 76 checks under the engine's strictest rules; the `constants` field and its test catch drift without it |
| The reads in `audit/catalogue.json` | The catalogue ships to readers and holds no code constant, so it drifts like a separate file |
| Files and phrases only, no boundaries | The run's own promises stay unmapped, and a playbook step can contradict a hard rule unseen |
| Fail the gate on any changed evidence | Rationale not recorded; owner to fill in |

## Consequences

### Positive

- A playbook or template change that moves text a check reads must name the rule that keeps it, or say why the
  loss is accepted.
- The map is plain JSON: reviewable in a diff, and read by the standard library.
- The implement run's boundaries get one home each, and the map says which are prose only.

### Negative / Trade-offs

- The map is kept by hand beside the code, and its reads can drift from a check's phrases until a test covers them.
- A script checks that a rule is stated, not that an agent follows it.
- About 200 moves entries (153 Commits rows and 45 templates) must be written before the gate can join `make check`.
