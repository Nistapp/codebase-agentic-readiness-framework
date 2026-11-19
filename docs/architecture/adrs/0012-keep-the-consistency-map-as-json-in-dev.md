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

This ADR fixes the map's format and the gate's rules. The schema, the reads, the names, the moves, the kept pairs,
the boundaries and the gate in both modes exist, with their tests.

## Decision

1. The consistency map is JSON in two files. Each stays under the 512 KiB size that `NAV-03` flags.
   `dev/consistency-map.json` holds every part but `names`.
   `dev/consistency-map-names.json` holds `map_format` and `names`. The script joins them into one map. It
   refuses `names` in both files, a missing names file, or two `map_format` values.
   [`dev/consistency-map.schema.json`](../../../dev/consistency-map.schema.json) is the JSON Schema of the joined
   map. A standard-library script in `dev/` checks it.
2. The map has five parts:
   1. `reads`: one entry per check in [`audit/catalogue.json`](../../../audit/catalogue.json). It says where and
      what the check reads. It also says how close the parts must be: one line, a window, a paragraph, a section
      or the file.
   2. `moves`: one entry per playbook Commits row and per greenfield template. It says what the row or template
      does to such text: `write`, `move`, `rewrite`, `create`, `untrack` or `none`. Its `touches` list names the
      checks whose reads it can change, as a reviewer judged them.
   3. `keeps`: one entry for each check a move touches. It cites the sentence that keeps the read true, by index
      section address and verbatim quote. Or it is `accepted`, with the maintainer's reason.
   4. `names`: the file and folder names the engine gives a meaning to.
   5. `boundaries`: the implement run's promises that no check reads. Each has an id and one home quote. It says
      what enforces it: a tool refusal, a test, an assertion of the paid implement eval, or prose. An enforcer
      is named by its file and its function.
3. The engine declares the reads of each engine check beside the registry, in
   [`audit/rules/reads.py`](../../../audit/engine/audit/rules/reads.py):
   1. A declaration takes its paths from the engine constants the check uses, where they exist.
      A place read upstream, by the scan's file kinds or component detection, names that step in `via`.
      A place matched in lower case says `case: fold`.
      A read that also follows paths named in the target's text gives the reason in `named_by_text`.
      A place that no fixture can make the check ask for gives the reason in `unexercised`.
   2. [`dev/consistency_map_reads.py`](../../../dev/consistency_map_reads.py) generates the map's `reads` part from
      it. A `dev/` test fails when the two differ.
   3. The two agent checks have no code, so their entries are written in the map.
   4. A read names its `constants` only when they hold its whole file list, less the places read upstream.
   5. An engine test runs every check on every fixture and on a greenfield scaffold. It records each path a check
      asks for, and fails on a path the declaration does not cover. It also records `name` asks: the names a
      check compares a scanned path with in its own code. It fails on a `name` ask that no place covers. It also
      fails on a place that no ask reaches, unless the place has `via` or `unexercised`.
   6. The declaration is not in the ruleset hash and is in no report.
4. A keeps quote is checked as the quote verifier checks it: verbatim, with whitespace collapsed. Its section
   must still mention the check ID.
5. The gate fails in five cases:
   1. A move names a check in `touches`, and no keeps entry covers the pair.
   2. A keeps quote is gone, or its section no longer mentions the check.
   3. A catalogue check has no reads entry, or a Commits row has no moves entry.
   4. A created file matches the names list and its moves entry has no `intent`.
   5. A boundary's home quote is gone from its section, or the file or function that enforces it no longer exists.
6. The gate also infers touches from the paths and the content kinds. It reports the inferred pairs that no move
   declares as unreviewed advice, and never fails on them.
7. Evidence that changes under an unchanged verdict is reported to the reviewer. It does not fail the gate.
8. The gate has two modes. Static mode checks the map against the working tree. Change mode runs against a base
   ref (`--base`, default `origin/dev`) and adds:
   1. For review only: each changed section in a file a reads entry names. The index diff lists it as moved,
      renamed, edited or removed. A template counts at the path the scaffolder writes it to.
   2. A failure for a kept section that no longer mentions the check ID. It counts only when the base side
      mentioned it, and even when the quote still exists elsewhere.
   3. A failure for a reads file renamed to a path outside its entry's scope.
   4. The evidence comparison. Each side is copied into a one-commit repository and audited by the same engine, the
      working tree's. A check whose verdict or evidence changed is reported when its reads overlap the change.
9. [`dev/consistency_map.py`](../../../dev/consistency_map.py) is the gate. `make consistency-map` runs it
   report-only: it exits 0 whatever it finds. It joins `make check` once no pair is unkept and every gap is kept or
   accepted.

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| RDF with SHACL shapes | Needs dev-only packages (`rdflib`, `pyshacl`) and is a steep step for contributors |
| CUE over the JSON | Adds a Go tool and a new language for three joins a short script does |
| Datalog facts | Needs a dev-only engine and has few readers; it stays open if the queries outgrow a script |
| LikeC4, Alloy or TLA+ models | They model architecture or states, not the text a check reads |
| The reads written by hand in the map, or as a field of each registry entry | By hand, the map drifts from the code: the recording test found 24 entries whose scope or file list the code did not match. As a field, the registry's 76 entries grow by about 1,000 places; a module keyed by check ID leaves the registry, the ruleset hash and every report unchanged |
| The reads in `audit/catalogue.json` | The catalogue ships to readers and holds no code constant, so it drifts like a separate file |
| Files and phrases only, no boundaries | The run's own promises stay unmapped, and a playbook step can contradict a hard rule unseen |
| Fail the gate on any changed evidence | Rationale not recorded; owner to fill in |
| One map file, or one written with less indentation | The one file passed 512 KiB, which `NAV-03` flags in this repository's own audit. Less indentation buys about 80 KB and changes every line; the names list, at 224 KB, is the largest part and changes least |
| Infer the touches from paths and content kinds alone | On this repository the rule listed 1,772 pairs, and it found 28 of the 67 gaps a review named. A gate that noisy is not read |

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
