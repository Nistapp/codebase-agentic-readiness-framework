# 0008. What Counts as the Repository

* **Status:** Accepted
* **Date:** 2026-11-05
* **Last reviewed:** 2026-11-05
* **Deciders:** [@nistapp]

---

## Context

Every check answers one of two questions about files: "which runner owns the verbs?" and "is file X present?".
Until this ADR the engine answered both from a flat list of every file the walk found, at any depth, with no
notion of which files are the project and which are data the project carries (templates it generates, fixtures
its tests read, examples its documentation shows).

The audit of this repository, the framework itself, showed the cost. A nested `greenfield-bootstrap/templates/
package.json` outranked the root `Makefile`, so `CMD-01` resolved all seven verbs against a template and
`CMD-03` reported a second gate. `CODEOWNERS`, `CONTRIBUTING`, `SECURITY`, a pull-request template, a release
document and a Dependabot file were all credited from `greenfield-bootstrap/templates/`, and `EXEC-02`, `EXEC-03`,
`BASE-01/02`, `TST-05` and `NAV-03` each read a fixture or a template as if it were the repository. The operator's
only remedy was `--exclude`, which the operator has to know to use, and which leaves no trace in the verdict.

Three separate defects had one cause:

1. **Precedence by kind, not by depth.** `RUNNER_PRECEDENCE` ranked `package.json` above `Makefile` whatever
   their paths, and `_manifest_path` picked the shallowest file of each kind independently, so a nested
   `package.json` outranked a root `Makefile`.
2. **Presence at any depth.** `Inventory.has`, `Inventory.match` and the hygiene readers (`HYG-02/03/05/06/08/09`)
   matched a name at any depth, although `HYG-02`'s own text says the file lives at the root, under `.github/` or
   under `docs/`.
3. **Carried data is indistinguishable from the project.** Nothing recorded that `tests/fixtures/`,
   `schema/examples/` or `templates/` hold files meant to be read, not run.

Component discovery is a different problem and stays out of scope (ADR-0003: components are declared, depth 1;
GitHub issue #20 covers nested components). This ADR decides which files are the repository at all; it does not
decide how a monorepo's components are scoped.

---

## Decision

**Three rules, applied once, in the inventory and the runner resolver, so that every check gets the same answer.**

1. **Runner precedence is depth first.** A runner is ranked by `(depth of its manifest, kind rank, path)`. A root
   manifest of any kind beats a nested one; among nested manifests the shallowest wins; a tie at equal depth is
   broken by `RUNNER_PRECEDENCE` (kind), then by path. The rank is one function in
   `audit/rules/checks/_common.py` (`runner_rank`) that the resolver (`resolve_all_verbs`), `runner_commands` and
   `CMD-03`'s choice of a primary runner all use. Precedence is applied per verb: a root `Makefile` that does not
   define `lint` does not hide a nested manifest that does.
2. **Carried data is set aside.** A file whose path has a directory component named `templates`, `template`,
   `examples`, `example`, `fixtures`, `samples`, `testdata` or `scaffold` (compared whole and case-insensitively; the
   target's own root name is never part of the comparison) is *carried data*. It is not a runner, not a source of
   hygiene, tooling, baseline or coverage evidence, not part of a directory census, and no check can read it. The
   list is one constant, `CARRIED_DATA_DIRS` in `audit/scan.py`. **Exception:** when no manifest remains outside
   the carried directories and a carried directory holds one, nothing is set aside, because that directory then
   holds the only manifest in the repository and is the project.
3. **The report says what it set aside.** `inventory.set_aside` in the report lists each outermost carried
   directory with its file count; `inventory.files_set_aside` totals them. The Markdown report shows both in
   "Scan coverage". A reader can therefore explain a verdict that surprises them, and see when a real directory
   was set aside by its name.

Set-aside is applied after the walk (the exception needs the whole tree). It reaches git-backed checks as well:
`tracked_in_scope` drops tracked paths under a set-aside directory, as it already drops `--exclude`d paths.

**Hygiene presence is bounded.** `HYG-02/03/05/06/08/09` count a file only at the repository root or under
`.github/`, `.gitlab/` or `docs/`, which is where `HYG-02`'s text already said the file lives. A hygiene file in
`packages/web/` is a component's file, not the repository's.

`--exclude` stays: it is the operator's tool for anything the list does not cover (`artefacts/**`, `dist/**`,
vendored trees). It is no longer needed for template, example or fixture directories.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| Each check filters out template-like paths itself | The pattern that caused the defect: thirty call sites, and one missed site reintroduces the bug. The engine's invariant (ADR-0006) is that a question asked by many packs has one answer. |
| Keep carried files in `Inventory.files` with a flag, and filter in the accessors | Direct iteration over `inventory.files` is used by more than a dozen checks; every one would need the filter, and a missed one is silent. Removing the files from `files` and recording them beside it fails closed. |
| Rely on `--exclude` | The operator must know the repository's layout and the flag. The verdict then carries no trace of what was left out. |
| Detect "a nested project" structurally (a directory with its own manifest and no parent link is not the project) | In a monorepo that directory is a component. The rule would set aside exactly the directories ADR-0003 and issue #20 want scoped, not hidden. |
| Consider only the repository root for every presence check | `docs/`, `.github/` and `.gitlab/` are conventional homes for repository-level files, and monorepo tooling lives in subdirectories. |
| Read `.gitattributes` (`linguist-vendored`, `export-ignore`) to find carried data | Needs git and an attribute almost no repository sets; the engine must work on a bare directory (ADR-0006: `None`, never an inference, when git cannot answer). |
| Let nested manifests outrank the root when they declare more verbs | Rewards the wrong file: the repository's gate is the one at its root, and a template generated into a new project will always declare more than the framework that generates it. |
| A flag to turn set-aside off | Cheap, but no repository has needed it yet. The report lists every set-aside directory, so a misfire is visible; the flag is added when one is seen. |

> A later reversal of this decision is folded into this table, so the rejected direction
> keeps its rationale inside the accepted record.

---

## Consequences

### Positive

* On the framework's own repository, `CMD-01` reads the root `Makefile`, `CMD-03` finds one gate, and no hygiene,
  tooling, baseline or coverage evidence comes from a template or a fixture. The fixtures `--exclude` is no longer
  needed for a correct verdict.
* `inventory.set_aside` makes a surprising verdict explainable without reading the engine.
* One rank function, one list and one filter: a check added later inherits all three.

### Negative / Trade-offs

* **A real directory with a carried name is set aside.** A Java package `com.acme.samples` or a Python package
  named `scaffold` disappears from every check. The report names it; there is no flag to bring it back yet (see
  Alternatives). The risk is judged smaller than the one it removes: the three names that matter most for
  repositories that carry data (`templates`, `fixtures`, `examples`) rarely name source packages.
* **Hazard checks lose the carried files too.** A real secret committed under `examples/` is not scanned by
  `SEC-02`. The alternative (hazards read carried data, credits do not) would make the engine flag every fixture
  that holds a fake credential on purpose, including its own. `inventory.set_aside` shows that the directory was
  not read.
* **Monorepo scoping is still open.** A nested `package.json` outside the list keeps its place: it is ranked below
  the root's manifests, and `CMD-03` still sees it as a second runner. Declaring components for `DOC-01/02`,
  `EXEC-04/07` and `NAV-01` is issue #20, deferred to v0.3 (open question Q3, default accepted).
* **Hygiene presence is stricter.** A repository that kept its only `CONTRIBUTING.md` in `packages/web/` now fails
  `HYG-05`. These checks are informational and never score.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference plus the index table in `docs/architecture/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/NNNN-title.md`.

See the [style guide](../../../../docs/STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
