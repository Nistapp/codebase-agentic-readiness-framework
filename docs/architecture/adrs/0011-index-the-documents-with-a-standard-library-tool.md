# 0011. Index the Documents With Our Own Standard-Library Tool in `dev/`

## Context

The audit and implement recipes are Markdown files that refer to each other. They use paths, heading anchors and
IDs: check IDs from [`audit/catalogue.json`](../../../audit/catalogue.json), requirement IDs from
[`spec/`](../../../spec/README.md), ADR numbers, playbook names and tool paths. A refactor of the recipes can drop a
rule or break a reference, and no test fails.

[`recipe_lint.py`](../../../dev/recipe_lint.py) checks links and anchors. It keeps no record of what each file
defines and what refers to it. So a reviewer cannot ask what a change removed, or which pages depend on a section.

A fix needs a repeatable picture of that graph that two commits can be compared on. It must run offline, in `make`
and in CI, with nothing installed.

## Decision

1. The document index is this repository's own tool, in [`dev/docindex/`](../../../dev/docindex/__init__.py), with
   the standard library only. [`dev/doc_index.py`](../../../dev/doc_index.py) is its entry point.
2. The package is a generic core. It imports nothing from `audit/`, `implement/` or another `dev/` module, and never
   `recipe_lint.py`. Only the entry point may import another `dev/` module, for example `dev/build_skills.py`.
3. Every project detail lives in [`dev/docindex.config.json`](../../../dev/docindex.config.json): the zones by path
   prefix, the ID patterns, the exclusions and the sweep scope.
4. The index is a graph of file, section and id nodes. Its edges are contains, links, mentions, runs and bundles,
   each with a confidence of exact or name-match. [`model.py`](../../../dev/docindex/model.py) defines it.
   [`index.schema.json`](../../../dev/docindex/index.schema.json) is the JSON Schema of its one serialised form.
5. The serialised form is deterministic: sorted keys, sorted nodes and edges, no timestamps, no absolute paths and
   no line numbers. Two builds of one tree are byte-identical, so two indexes compare with a plain diff.
6. The index is built on demand (`python3 dev/doc_index.py build`) and is not committed. No gate reads an index file.
7. Graphify, a third-party graph builder, is at most an optional local cross-check. No gate, test or committed file
   depends on it.
8. No obligation ledger, a hand-kept list of every normative rule, is kept. A refactoring experiment decided against
   it. Rationale not recorded in the repository; owner to fill in.

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| Graphify as the index | Its graph does not know this repository's IDs, zones or bundle scope, and a gate would depend on an outside tool and its output format |
| Extend `recipe_lint.py` into an index | The index is checked against `recipe_lint.py` in a parity test; one shared code path would hide the differences that test looks for |
| An obligation ledger kept by hand | Rationale not recorded; owner to fill in |
| Commit the index and check it in `make check` | Rationale not recorded; owner to fill in |

## Consequences

### Positive

- A change to a recipe can be compared with its parent: which sections, IDs and links it added, removed or changed.
- The tool runs anywhere Python runs, in CI and offline, with no install.
- Another repository can reuse the core with its own config.

### Negative / Trade-offs

- This repository maintains a Markdown parser of its own, with the edge cases that brings.
- A link or ID form that the config does not describe is not in the index until someone adds it.
- With no committed index, a reviewer builds one for each comparison.
