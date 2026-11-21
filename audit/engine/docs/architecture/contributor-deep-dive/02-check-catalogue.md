# Check Catalogue

> **Audience:** Engineers & Maintainers
> **Related ADRs:** [ADR-0003](../adrs/0003-component-depth-declared-depth-1.md) · [ADR-0004](../adrs/0004-no-llm-in-v1.md)
> **Status:** Live for the `IDX`, `AGT`, `EXEC`, `CMD`, `DOC`, `NAV`, `SEC`, `TOOL`, `CI`, `TST`, `BASE`, `CON` and `HYG` packs (the `CON-04` emitter included); every catalogued check is implemented. This page is the design of record; `audit/rules/registry.py` is its executable form, and `python3 -m audit --list-checks` prints the current truth.

> [!NOTE]
> The recipes' [`catalogue.json`](../../../../catalogue.json) is seeded from this registry through `--list-checks --format json`
> and adds the checks only an agent can judge. A test keeps it identical to this registry on every field they share.

> [!IMPORTANT]
> **The executable rules live in code, not here.** This catalogue holds the id, tier, phase anchor, severity and
> evidence rule for every check — the rationale for each family is in
> [Why These Checks](../user-overview/03-why-these-checks.md). Any change to a check's semantics updates this page
> and its rule pack in the same change set.

---

## 1. Summary

| Group | Checks | Tier A | Tier B | Tier C |
|---|---|---|---|---|
| `IDX` Discovery & index | 3 | 2 | — | 1 |
| `AGT` Agent governance | 12 | 2 | 10 | — |
| `DOC` Documentation contract | 5 | 3 | 2 | — |
| `CMD` Command surface | 4 | — | 4 | — |
| `TOOL` Tooling | 7 | 3 | 4 | — |
| `CI` CI | 4 | — | 4 | — |
| `BASE` Baselines & ratchet | 4 | 2 | 2 | — |
| `CON` Constraints | 4 | — | 3 | — |
| `EXEC` Execution determinism | 8 | 2 | 6 | — |
| `TST` Tests | 5 | 2 | 2 | 1 |
| `NAV` Navigation | 3 | 1 | 2 | — |
| `SEC` Security hygiene | 3 | — | 3 | — |
| **Total catalogued** | **62** | **17** | **42** | **2** |

Plus **14 informational checks** (`NAV-04`, `NAV-05`, `HYG-01`–`HYG-11`, `HYG-13`), reported and never scored.
`HYG-12` is reserved for a planned release-provenance check; ruleset `2026-11-17.3` added `HYG-13`.

Of the 62, `CON-04` is an emitter rather than a check, leaving **61 scoreable checks** in v1. (`CON-01` carried weight 0
until ruleset `2026-10-11.1`, because the engine did not read the artifact that the spec defines; it reads the
prohibitions section now.)

> [!NOTE]
> The tier columns sum to 61, not 62: `CON-04` is an emitter with no tier. The variant research added `AGT-10`;
> v0.3.3 added `CI-05`, `EXEC-08` and `TOOL-07`; v0.3.4 added `AGT-12` and `DOC-05`; ruleset `2026-11-17.2` added
> `AGT-13`.
> Earlier revisions of this table carried per-group tier splits that disagreed with their own rows — `--list-checks`
> is the executable truth, and a mismatch between it and this page is a defect in this page.

---

## 2. `IDX` — Discovery & Index

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `IDX-01` | `codebase-memory-mcp` registered for this repository | A | BLOCKER | A project- or user-level MCP config names the server and the target path | Implemented |
| `IDX-02` | An index exists for this checkout | A | BLOCKER | The index store contains a project whose root path resolves to the target | Implemented |
| `IDX-03` | Index freshness | C | DEGRADER | Indexed git SHA equals target `HEAD`; probe only | Implemented |

---

## 3. `AGT` — Agent Governance

Component-scoped: `AGT-02` reports a ratio over declared components; the remaining checks evaluate the root file
and are reported per component when a component-level file exists.

One data structure in code drives the pack: `audit/rules/variants.py`. It records every instruction-file variant per
harness, with the documentation URL it came from and a `last_verified` date. It also records the config-indirection
keys, the shadow pairs, and the globs that only *look* like instructions. A harness whose own path loads only through
its config (`paths_need_config`, Aider's `CONVENTIONS.md`) reaches that path only when the config file exists. A
filename-only check is wrong in both directions: it calls a `CLAUDE.md` repository ungoverned, and an
`AGENTS.override.md` repository governed. The table rots by design (Windsurf → Devin Desktop; Antigravity CLI replacing
Gemini CLI). So every report carries a `ruleset_hash` over the table and the catalogue. Rot then shows up in provenance,
so no one has to infer it from a suspicious verdict.

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `AGT-01` | Instruction file present, canonical, and non-trivial | A | BLOCKER | A canonical instruction file is present, over the minimum size, not a stub (a template phrase such as "coming soon", or `TODO`, `TBD` or `placeholder` as a marker: opening a line, or in brackets; the word inside a sentence is not one), not mis-cased, and not shadowed by an override in the same directory | Implemented |
| `AGT-02` | Component coverage | A | DEGRADER | `components with AGENTS.md / declared components`, as a `PARTIAL` ratio | Implemented |
| `AGT-03` | Documentation contract named | B | DEGRADER | Names `docs/`, names `docs/STYLE_GUIDE.md` as canonical, names `artefacts/` as off-limits | Implemented |
| `AGT-04` | Definition of done stated | B | DEGRADER | A doc-trigger sentence exists and names the same change set | Implemented |
| `AGT-05` | Seven verbs named | B | DEGRADER | The command block lists `format`, `format:check`, `lint`, `typecheck`, `test`, `check`, `security` and they resolve in `CMD-01` | Implemented |
| `AGT-06` | Architectural boundaries declared | B | DEGRADER | At least two named boundary rules referencing real paths | Implemented |
| `AGT-07` | Do-not-do / deny rules present | B | DEGRADER | A prohibitions section exists (a heading with `Do Not Do`, `Never`, `Prohibited`, `Forbidden`, `Deny` or the like; a heading inside a code fence is not one) and the file, anywhere in it, covers tests, generated files, default branch, secrets. `prohibitions_section` in `audit/rules/checks/_common.py` finds the section for this check, `CON-01` and `CON-02`, so that they cannot disagree on where it is | Implemented |
| `AGT-08` | No competing instruction files; reach stated | B | DEGRADER | No variant file competes with the canonical one; shadow pairs reconciled; the harnesses that reach nothing are stated | Implemented |
| `AGT-09` | Branch and release boundary declared | B | DEGRADER | States which branches exist and whether an agent may tag or release, and names every branch the declared branch rules protect by name | Implemented |
| `AGT-10` | Instruction indirection resolved | B | DEGRADER | A file the entry file defers to ("first read …") is named in a harness config (`.aider.conf.yml` `read:`, `opencode.json` `instructions`, `.codex/config.toml` `model_instructions_file`, `.gemini/settings.json` `context.fileName`) or inlined | Implemented |
| `AGT-12` | Communication rules stated | B | COSMETIC | A section of the instruction file headed for writing to people, or a linked file whose name says `communicat`, names the reader, how to report and how to ask for a decision; a named file that does not exist, or a missing element, is `PARTIAL` | Implemented |
| `AGT-13` | Coding conventions written | B | COSMETIC | A conventions file (`CONVENTIONS*`, `*convention*`, `CODE_STYLE*`, `CODING_STANDARDS*`, `*coding-guidelines*`, at the root or under `docs/` or `.github/`) or a conventions section of `AGENTS.md` or `CONTRIBUTING.md` covers naming, layering, error handling and logging, and testing, and links the formatter or linter config; a missing item or a `TBD` or `TODO` is `PARTIAL`; `docs/STYLE_GUIDE.md` never counts | Implemented |

---

## 4. `DOC` — Documentation Contract

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `DOC-01` | `docs/` exists | A | DEGRADER | Directory present with at least one markdown file | Implemented |
| `DOC-02` | `docs/STYLE_GUIDE.md` exists | A | DEGRADER | File present; `AGT-03` must reference it | Implemented |
| `DOC-03` | `artefacts/` exists and is ignored | B | DEGRADER | Directory present and matched by an ignore rule; contents not tracked | Implemented |
| `DOC-04` | ADR directory and index | A | COSMETIC | An ADR directory exists with an index listing its files | Implemented |
| `DOC-05` | Docs are readable | B | COSMETIC | The prose under `docs/`: at most 10% of sentences over 25 words (20 in a numbered step), at most 1 vague word per 1,000 words, and a Mermaid block on each explanation or tutorial page ⇒ `PASS`; over 25% long ⇒ `FAIL`; else `PARTIAL`; under 10 sentences, or under 20% common English function words ⇒ `UNKNOWN` | Implemented |

---

## 5. `CMD` — Command Surface

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `CMD-01` | Seven verbs resolvable on one runner | B | BLOCKER | Each verb maps to a script in exactly one runner (package scripts, `Taskfile`, `Makefile`, `pyproject`, gradle, maven), under a spelling the spec accepts for that runner; a `Makefile` that GNU Make refuses is a finding, not a runner ([how runners are read](01-scan-engine-and-tiering.md#41-reading-the-verb-runners)) | Implemented |
| `CMD-02` | `check` composes the read-only verbs | B | BLOCKER | The `check` definition invokes format-check, typecheck and test (or documented equivalents), by command or, in a `Makefile`, by prerequisite, following a target or package script that is no verb once; a Gradle `check` is read from its plugins and `dependsOn` wiring, `UNKNOWN` when an unknown plugin, script, subproject or task could add a missing concern; `UNKNOWN` for a Maven lifecycle `check`, whose plugin bindings the build sets | Implemented |
| `CMD-03` | No divergent second definition | B | DEGRADER | A second runner may delegate; it must not define its own composition of the gate | Implemented |
| `CMD-04` | Write verbs separated from read-only verbs | B | DEGRADER | A write verb is never invoked by a verification verb | Implemented |

---

## 6. `TOOL` — Tooling

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `TOOL-01` | Formatter configured | B | DEGRADER | A formatter config file and a resolvable write verb | Implemented |
| `TOOL-02` | Linter configured | B | DEGRADER | A linter config file and a resolvable read-only verb | Implemented |
| `TOOL-03` | Type checker configured | A | DEGRADER | Language-appropriate strict configuration (`tsconfig`, `mypy`/`pyright`, `global.json` nullable settings, etc.) | Implemented |
| `TOOL-04` | Dependency / security scan verb | A | DEGRADER | A resolvable verb performing a dependency-audit check, and a CI step that runs one | Implemented |
| `TOOL-05` | Local hook chain active | B | DEGRADER | Hook manager configured and wired (`core.hooksPath`, `.pre-commit-config.yaml`, `lefthook.yml`) | Implemented |
| `TOOL-06` | Commit convention enforced | A | COSMETIC | A commit-message rule runs in a local `commit-msg` stage and in CI | Implemented |
| `TOOL-07` | Local guard against commits to a protected branch | B | COSMETIC | A wired `pre-commit` or `commit-msg` hook refuses a commit on each branch the declared rules protect | Implemented |

---

## 7. `CI` — Continuous Integration

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `CI-01` | Pipeline present, triggered on PRs | B | BLOCKER | A workflow file exists and declares a pull-request trigger | Implemented |
| `CI-02` | Local↔CI parity | B | BLOCKER | Set comparison of CI-invoked commands against the resolved verb set from `CMD-01` | Implemented |
| `CI-03` | CI-only steps flagged | B | DEGRADER | CI steps with no local equivalent are listed as findings | Implemented |
| `CI-05` | Workflow files are linted | B | DEGRADER | A linter that knows the CI provider is named on the local surface (`PASS`) or only in CI (`PARTIAL`) | Implemented |

---

## 8. `BASE` — Baselines & Ratchet

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `BASE-01` | Baseline artifact exists | A | DEGRADER | A committed baseline or suppression file, or an equivalent documented mechanism | Implemented |
| `BASE-02` | Current violation counts measured | B | DEGRADER | The audit counts violations with the repository's own configured tooling where possible, and records the method used | Implemented |
| `BASE-03` | No-new-violations mechanism | B | DEGRADER | A committed ratchet — violation budget, suppression count, or comparison step | Implemented |
| `BASE-04` | Coverage floor configured | A | DEGRADER | A coverage threshold exists in test-runner configuration, any `package.json`, or a JaCoCo floor in a Gradle or Maven build | Implemented |

---

## 9. `CON` — Constraints

The framework requires initial Constraint Engineering allow/deny lists as a Phase-1 deliverable. The artifact is the
prohibitions section of the instruction file ([decision 0001](../../../../../spec/decisions/0001-constraint-artifact.md)),
and `CON-01` and `CON-02` read it through one helper (`prohibitions_section`, `audit/rules/checks/_common.py`). A path or
pattern is *named* when it stands in a code span of the section. The audit also *emits* a draft list derived from the scan
(`CON-04`), as a starting point for what to write there.

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `CON-01` | Allow/deny artifact present | B | BLOCKER | The prohibitions section of the instruction file names at least one path or pattern, in a code span, that matches a file or directory of the repository. `PARTIAL` when it names paths and none matches; `FAIL` when it names none; `UNKNOWN` with no instruction file or no section. A code span that is a command, a flag or a bare word that is not a path is not a path | Implemented |
| `CON-02` | Test directories protected | B | BLOCKER | The prohibitions section of the instruction file names every test directory, or a pattern that covers it, in a code span ([decision 0001](../../../../../spec/decisions/0001-constraint-artifact.md)). A test directory is one named `test`, `tests` or `__tests__`; `spec` and `specs` hold feature specifications. `PARTIAL` names some, `FAIL` none; `UNKNOWN` with no instruction file, no section or no test directory. Constraint files, ignore rules and CI text are not read | Implemented |
| `CON-03` | `artefacts/` excluded from index and agent reads | B | DEGRADER | Ignore rules cover `artefacts/`, `artifacts/`, and the tool's own state directory | Implemented |
| `CON-04` | Draft allow/deny emitted | Emitter | — | Writes `do-not-do.draft.md` from the scan, with `--emit-baseline`: a Markdown list to paste under the prohibitions heading, one entry for each of secrets, migrations, generated code, test dirs, IaC and production manifests, paths in code spans | Implemented (not scored) |

---

## 10. `EXEC` — Execution Determinism

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `EXEC-01` | Toolchain pinned / wrapper committed | A | BLOCKER | `.nvmrc`/`engines`, `.tool-versions`, `requires-python`, `global.json`, `gradlew`, `mvnw` — at least one appropriate to the detected stack | Implemented |
| `EXEC-02` | Lockfile committed and consistent | B | BLOCKER | Every lockfile tracked (at any depth, by its path), and each one's declared dependencies agree with the manifest in its own folder | Implemented |
| `EXEC-03` | Non-interactive setup path | A | BLOCKER | A devcontainer, compose file, Dockerfile (a variant such as `Dockerfile.jvm` too, at any depth), or setup target/script exists and is documented | Implemented |
| `EXEC-04` | Env-var inventory complete | B | BLOCKER | Set difference of env keys referenced in source against keys in the committed example files that cover each reading file (an example file covers its folder and below) | Implemented |
| `EXEC-05` | No generated artifacts committed in-tree | B | DEGRADER | Generated or vendored paths are either untracked or carry a generated-file header | Implemented |
| `EXEC-06` | Documented commands resolve | B | DEGRADER | Every fenced command in README and `AGENTS.md` resolves to a real script, verb, or file | Implemented |
| `EXEC-07` | No competing configs for one concern | B | DEGRADER | At most one authoritative config per concern (lint, format, test, types per language, security); a pyright config that mirrors the mypy gate is not a competitor | Implemented |
| `EXEC-08` | Tool versions visible to dependency automation | B | DEGRADER | No literal tool version in a command, workflow or hook (`FAIL`), or only copies of a manifest pin (`PARTIAL`) | Implemented |

---

## 11. `TST` — Tests

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `TST-01` | Test verb exists, suite non-empty | A | BLOCKER | A resolvable test verb and at least one test file matching the framework's conventions | Implemented |
| `TST-02` | Suite status known | C | DEGRADER | The test verb is run and its exit code recorded; probe only | Implemented |
| `TST-03` | Skip / xfail census | B | DEGRADER | Count of skip, ignore, and expected-failure markers, per test framework | Implemented |
| `TST-04` | Fast path documented | B | DEGRADER | A documented single-test or subset invocation exists | Implemented |
| `TST-05` | Coverage configuration present | A | COSMETIC | Coverage reporting configured in the test runner | Implemented |

---

## 12. `NAV` — Navigation

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `NAV-01` | Declared component boundaries | A | DEGRADER | At least one component declared in a build manifest | Implemented |
| `NAV-02` | Obvious entry points | B | DEGRADER | An entry point is declared (`bin`, `main`, `__main__`, `Application`, `func main`) | Implemented |
| `NAV-03` | Structural red flags | B | COSMETIC | Counts of oversized files, catch-all directories, checked-in binaries, minified assets | Implemented |
| `NAV-04` | Architecture orientation artifact | A | *informational* | `docs/architecture/`, an ADR directory, or a diagram exists | Implemented |
| `NAV-05` | Public-symbol documentation coverage | B | *informational* | Fraction of public symbols carrying a doc comment or docstring | Implemented |

---

## 13. `SEC` — Security Hygiene

| ID | Check | Tier | Sev | Evidence rule | Status |
|---|---|---|---|---|---|
| `SEC-01` | `.env` untracked and ignored | B | BLOCKER | No tracked `.env`, and ignore rules cover `.env` shapes | Implemented |
| `SEC-02` | No key-shaped strings in tracked files | B | BLOCKER | Pattern scan of tracked text files for credential shapes; matches reported by path and line only. A keyword such as `token` counts only when it is assigned a literal, not a name, an expression or a reference to the environment or a secret store. A literal or `Bearer` token that names itself a sentinel, and a badge URL, do not count; a properties or env-style file counts a short value | Implemented |
| `SEC-03` | Ignore patterns cover secret shapes | B | DEGRADER | Ignore rules include key, certificate, and credential extensions | Implemented |

---

## 14. Informational Checks (Reported, Never Scored)

| ID | Check | Tier | Evidence rule | Status |
|---|---|---|---|---|
| `HYG-01` | README | A | Present, non-placeholder | Implemented |
| `HYG-02` | CODEOWNERS | A | Present; paths noted for consistency against the draft deny list | Implemented |
| `HYG-03` | Pull-request template | A | Present | Implemented |
| `HYG-04` | Issue templates | A | At least one present | Implemented |
| `HYG-05` | CONTRIBUTING | A | Present | Implemented |
| `HYG-06` | SECURITY | A | Present | Implemented |
| `HYG-07` | CHANGELOG | A | Present and dated recently | Implemented |
| `HYG-08` | Release process documented | A | A release document exists | Implemented |
| `HYG-09` | Dependency update automation | A | Dependabot or Renovate configured, an entry for each detected ecosystem, and no `target-branch` beside `ignore` or `groups` | Implemented |
| `HYG-10` | License | A | A license file exists | Implemented |
| `HYG-11` | Branch protection | B | Protection declared by configuration-as-code where the provider allows (ruleset files, the Settings app, Terraform), plus a source-branch check for a two-branch model | Implemented |
| `HYG-13` | Contributing rules written | B | The `CONTRIBUTING*` documents `HYG-05` finds point to the setup command (a link to `README.md` or `AGENTS.md`, or a named setup command), name the gate command with a paragraph saying CI runs the same, and name branches, commits and pull requests; one or two of the three is `PARTIAL`, none `FAIL`, no document `UNKNOWN` | Implemented |

---

## 15. Adding a Check

The diagram shows the steps below in order. A check that misses one does not merge.

```mermaid
flowchart LR
    A["Next id in its group"] --> B["Tier, anchor, severity, falsifiable evidence rule"]
    B --> C["Failure mode in Why These Checks"]
    C --> D["summary and a typed data payload"]
    D --> E["A fixture that fails only this check"]
    E --> R["Its reads declared in audit/rules/reads.py"]
    R --> F["Summary table row and framework anchor"]
    F --> G["Merge"]
```

1. Assign the next id in the appropriate group.
2. State tier, phase anchor, severity, and a **falsifiable** evidence rule. Any reviewer who applies that rule to
   a fixture reaches the same verdict.
3. Add the failure mode to [Why These Checks](../user-overview/03-why-these-checks.md). No failure mode, no check.
4. Emit a short human `summary`. Where the check has table-shaped facts, also emit a typed `data` payload from
   `audit/rules/payloads.py` (ADR-0007). The renderer builds check tables from the payload `kind`, never
   from prose. Editorial wording belongs in `audit/report/presentation.py`, not in the check.
5. Add a broken fixture that fails exactly this check and nothing else. Add its row to the fixture matrix table
   of the check's family, `tests/packs/<family>/matrix.py`. A fixture that belongs to no one family goes in
   `tests/packs/cross_family/matrix.py`.
6. Declare what the check reads in `audit/rules/reads.py`: the places, the text and the binding. Take the paths
   from the check's own constant with `_held` where one exists. Give a place `via` when the scan's file kinds or
   component detection read it before the check runs. Give it `case=FOLD` when the check lower-cases the name. Set
   `named_by_text` when the check looks up paths that the target's text names. Mark a place `unexercised`, with the
   reason, when no fixture can make the check ask for it. Prefer a small fixture that does. Add a place to
   `MONOTONE` only when the code shows that added text can only raise the verdict there.
   `tests/test_reads_monotone.py` adds text to it in every fixture and fails when a verdict falls. `tests/test_check_reads.py`
   fails on a path the check asks for and the declaration does not cover. A pattern passed to `Inventory.match`
   counts as every path it finds there. The engine and a `glob` place both match folder by folder
   (`audit/globs.py`), so the engine's `.husky/**` is not declared as `.husky/*`. It also fails on an uncovered
   `name` ask: a name a check
   compares paths with in its own code. And it fails on a declared place that no ask reaches, unless the place has
   `via` or `unexercised`. Then run `python3 dev/consistency_map_reads.py --write` from the repository root. It
   rewrites the consistency map's reads (ADR 0012 in the root `docs/architecture/adrs/`).
7. Add the row to the summary table and to the pack's framework anchor before merging.

---

## Related Pages

- Previous: [Scan Engine & Tiering](01-scan-engine-and-tiering.md)
- Rationale: [Why These Checks](../user-overview/03-why-these-checks.md) · [The Readiness Model](../user-overview/02-the-readiness-model.md)
