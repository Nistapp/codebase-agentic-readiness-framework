# Navigation (`NAV`)

> Follows the anatomy in [`README.md`](README.md). Five checks: `NAV-01`–`NAV-03` are scored,
> `method: automated`; `NAV-04` and `NAV-05` are informational (`catalogue.json`: `scored: false`,
> no `req_ids`) — reported like every other check but earning no credit. See
> [Why These Checks §12](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#12-navigation-nav)
> for the consequence behind this family: an agent that cannot see component boundaries, entry points or
> structural traps either guesses at blast radius or is drawn to the worst places in the codebase. Every
> check reads the engine's `NAV` pack (`deterministic-audit/audit/rules/checks/nav.py`), whose module
> docstring names each check's deliberate limits (`NAV-02` reads a fixed, documented entry-point signal
> set per ecosystem rather than resolving one semantically; `NAV-05`'s "public" is a best-effort static
> approximation — module-level names not starting with `_` for Python, exported declarations for
> TypeScript/JavaScript — that never executes or reflects).

---

## NAV-01 — Declared component boundaries

Why it matters   Constraint Engineering needs a bounded component to scope work to; without one, blast
                  radius cannot be scoped or reviewed
                  ([shared/Overview.md § Applicability](../../../shared/Overview.md#applicability)).
Severity         DEGRADER
Engine           `NAV-01`. Reads `components.declared` (built by the engine's own component detector,
                 depth 1) for any member besides the root. At least one non-root component declared by a
                 build manifest (npm workspaces, `pnpm-workspace.yaml`, Maven modules, Gradle includes,
                 and the like) is `PASS`. None declared, but `components.candidates` names an
                 undeclared multi-app layout, is `PARTIAL` — the layout exists, nothing declares it. A
                 single-root repository that still declares a manifest is `PASS` too: the boundary
                 exists, it is just the root. No manifest at all, with the stack unrecognised, is
                 `UNKNOWN`, never `FAIL` — an unrecognised ecosystem is not proof that boundaries are
                 absent. Distrust a `PARTIAL`/`UNKNOWN` when the workspace convention used is one the
                 engine's component detector does not yet recognise — verify by reading the manifest
                 directly before treating the boundary as undeclared.
Method           automated
Look for         `components.declared` for any non-root member; failing that, `components.candidates`
                 for an undeclared layout; failing that, whether the declared root itself names a
                 manifest at all.
Rubric           PASS: at least one non-root component is declared by a build manifest, or the
                 repository is single-root and the root itself declares a manifest.
                 PARTIAL: one or more candidate components are detected (a layout that looks like
                 separate apps) but none is declared in any build manifest.
                 FAIL: not used by this check — an unrecognised stack with nothing declared is `UNKNOWN`,
                 never a defect to score.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no build manifest declares a component and the stack is not recognised at
                 all.
Evidence to cite A `file` evidence item per declared component (up to 6 named in the summary) for PASS;
                 a `file` evidence item per candidate component (up to 12) for PARTIAL.
Absence proof    A PARTIAL names every candidate component the engine's own layout heuristic found, so
                 "nothing declares them" is a checked list, not an assumption; the UNKNOWN case records
                 that no manifest exists at all as its own stated reason.
Remediation      playbook `establish-docs-contract` (`catalogue.json` lists it for `NAV-01`); point
                 at the workspace mechanism appropriate to the detected ecosystem inline.
Pitfalls         A single-package repository with a root manifest is a legitimate `PASS`, not a weaker
                 result than a declared multi-component layout — "the boundary is just the root" is the
                 engine's own documented reading, not a gap to flag.

## NAV-02 — Obvious entry points

Why it matters   Agents must find where execution begins before they can reason about what is live versus
                  dead code
                  ([greenfield-bootstrap/README.md § 1.9 Core DI interface file + public entry point](../../../greenfield-bootstrap/README.md#19-core-di-interface-file--public-entry-point)).
Severity         DEGRADER
Engine           `NAV-02`. For each detected ecosystem, checks a fixed, documented set of entry-point
                 signals: npm `main`/`bin`/`exports` plus a conventional index/server/main/app file for
                 node; `__main__.py`, `main.py`/`app.py`/`manage.py`, an
                 `if __name__ == "__main__"` guard, or a `console_scripts`/`[project.scripts]` entry
                 point for python; `public static void main`/`fun main`/`@SpringBootApplication` for jvm;
                 `func main` for go; `src/main.rs` or a `[[bin]]` section for rust; and fixed conventional
                 names for dotnet/ruby/php. No recognised ecosystem at all ⇒ `UNKNOWN` — there is no
                 language convention to check against. Distrust a `FAIL` when the entry point is named
                 something this fixed signal set does not recognise (a non-conventional script name, a
                 framework-specific bootstrap file) — verify by reading the project's own run
                 configuration or CI deploy step for how it actually starts.
Method           automated
Look for         The fixed per-ecosystem signal set named above, for every detected ecosystem.
Rubric           PASS: at least one entry-point signal is found for the detected ecosystem(s).
                 PARTIAL: not used by this check — the engine's own outcome is binary.
                 FAIL: a recognised ecosystem has no entry-point signal from the fixed set.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no ecosystem is recognised at all.
Evidence to cite A `file`/`command` evidence item per entry-point signal found (up to 6 named in the
                 summary) for PASS.
Absence proof    A FAIL names the detected ecosystem(s) explicitly and states that the engine's full
                 signal set for each was checked and matched nothing, so the absence is scoped to a named
                 search, not a general impression.
Remediation      playbook `establish-docs-contract` (`catalogue.json` lists it for `NAV-02`); name
                 the entry point in the manifest or the conventional filename for the detected ecosystem.
Pitfalls         A library package with genuinely no runnable entry point (no `main`, no CLI, no server)
                 still reads `FAIL` here — the engine does not distinguish "library, no entry point
                 expected" from "application missing one"; verify the project's own nature before writing
                 remediation that does not apply to a library.

## NAV-03 — Structural red flags

Why it matters   Oversized files, catch-all directories, checked-in binaries and minified assets are
                  exactly where agents are drawn when they explore, and exactly where they should not be
                  working
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         COSMETIC
Engine           `NAV-03`. A census, never a verdict on a heuristic: counts files over 512 KB
                 (`LARGE_FILE_BYTES`), directories with more than 50 immediate files (`CATCH_ALL_FILES`),
                 files the scan classifies `Kind.BINARY`, and generated files whose name contains
                 `.min.`. Both thresholds are documented constants in `nav.py`, not tuned per repository.
                 **The engine never returns `FAIL`** — an all-zero census is `PASS`, and any nonzero count
                 is `PARTIAL`, however large. This check runs regardless of detected ecosystem — there is
                 no `UNKNOWN` path. Distrust a `PARTIAL` whose flagged paths are intentional and
                 documented (a committed test fixture that must be exactly this large, a vendored binary
                 asset with no alternative) — verify by reading what the flagged path actually is before
                 recommending its removal.
Method           automated
Look for         Every file's size against the 512 KB threshold; every directory's immediate file count
                 against the 50-file threshold; every file's scan classification (`Kind.BINARY`); every
                 generated file's name for `.min.`.
Rubric           PASS: no oversized file, no catch-all directory, no checked-in binary, and no minified
                 asset is found.
                 PARTIAL: at least one of the four categories has a nonzero count.
                 FAIL: not used by this check — the engine's own outcome is never a hard failure,
                 whatever the counts.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — the census runs unconditionally.
Evidence to cite A `file` evidence item per flagged path (up to 12, across all four categories combined)
                 for PARTIAL; for PASS, the zero counts for all four categories.
Absence proof    A PARTIAL states each category's own count explicitly (`oversized(>512 KB): N`,
                 `catch-all dirs(>50 files): N`, and so on) before listing the paths, so the total is
                 checkable category by category, not just as one combined number.
Remediation      playbook `establish-docs-contract` (`catalogue.json` lists it for `NAV-03`); each
                 category has its own fix (split, reorganise, untrack, generate in the build), so name
                 which category the finding actually flags before recommending one.
Pitfalls         A `PARTIAL` here is never escalated to a blocking read — the catalogue's own severity
                 (`COSMETIC`) and the engine's "never FAIL" design both say this is a census for
                 awareness, not a gate; do not override it to a harsher verdict on the theory that a large
                 count "should" fail.

## NAV-04 — Architecture orientation artifact *(informational, unscored)*

Why it matters   A short map lets an agent orient before it explores instead of discovering structure by
                  trial and error
                  ([Phased-Approach.md § Key Deliverables](../../../brownfield-legacy/Phased-Approach.md#key-deliverables)).
Severity         COSMETIC
Engine           `NAV-04`. Not a scored check (`catalogue.json`: `scored: false`, no `req_ids` — this
                 check has no framework requirement behind it, unlike `NAV-01`–`NAV-03`). Unlike
                 `CON-04`, which never records a real defect, `NAV-04` does produce a genuine `FAIL`:
                 looks for any file under `docs/architecture/`, an ADR directory
                 (`docs/architecture/adrs/` or `docs/adr/`), or a diagram file (`.mmd`, `.puml`,
                 `.drawio`, `.excalidraw`, `.svg`, `.png`, matched by suffix anywhere in the tree). Any one
                 present is `PASS`; none at all is `FAIL`. There is no `UNKNOWN` path — the presence scan
                 runs unconditionally. Because it is unscored, a `FAIL` here never lowers the repository's
                 score, however it is written up.
Method           automated
Look for         Any file under `docs/architecture/`; an ADR directory at either conventional path; any
                 file whose suffix names a diagram format, anywhere in the tree.
Rubric           PASS: a `docs/architecture/` file, an ADR directory, or a diagram file exists (any one).
                 PARTIAL: not used by this check — presence is binary.
                 FAIL: none of the three exists.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — the presence scan runs unconditionally.
Evidence to cite A `file` evidence item per artifact kind found (up to all three) for PASS; nothing more
                 specific to cite for FAIL beyond the absence proof.
Absence proof    A FAIL states plainly that none of `docs/architecture/`, an ADR directory at either
                 conventional path, or any diagram-suffixed file was found anywhere in the tree.
Remediation      playbook `establish-docs-contract` (`catalogue.json` lists it for `NAV-04`); note
                 that any one of a short architecture page, an ADR directory or a diagram resolves it.
Pitfalls         Being unscored does not mean the finding is optional to report — an agent still writes
                 up a `NAV-04` `FAIL` like any other, it simply carries no score weight; do not drop it
                 from the report on the theory that "unscored" means "not worth mentioning".

## NAV-05 — Public-symbol documentation coverage *(informational, unscored)*

Why it matters   Phase 2 territory, reported here only as a signal: without any documentation coverage
                  signal an agent must read whole function bodies just to learn their signatures
                  ([Phased-Approach.md § Key Deliverables](../../../brownfield-legacy/Phased-Approach.md#key-deliverables)).
Severity         COSMETIC
Engine           `NAV-05`. Not a scored check (`catalogue.json`: `scored: false`, no `req_ids`). Picks one
                 language to census — python if the stack recognises python and python files exist, else
                 typescript/javascript under the same condition, else whichever of the two has more files
                 present — then counts "public" symbols for that language only (python: module-level
                 `def`/`class` not starting with `_`; typescript/javascript: `export`-prefixed
                 declarations) against how many are immediately preceded (python: followed) by a
                 docstring or `/** */` block comment. No recognised source language at all, or the chosen
                 language finds zero public symbols, is `UNKNOWN` — "public" cannot be defined, or there
                 is nothing to measure. A repository with both python and typescript files censuses only
                 the one language chosen; the other's documentation coverage is not reported by this run
                 at all. Distrust a result when the repository is predominantly a third language this
                 check cannot census (jvm, go, rust) — it is silently `UNKNOWN` by construction, not a
                 defect in the census itself.
Method           automated
Look for         The engine's own `Ratio` payload (`numerator`, `denominator`, `method`) attached to the
                 `NAV-05` outcome, naming which language and definition of "public" was used; read it
                 directly rather than re-counting symbols independently.
Rubric           PASS: every public symbol found (in the one censused language) is documented.
                 PARTIAL: at least one public symbol found is undocumented.
                 FAIL: not used by this check — the engine's own outcome has no failure branch.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised source language is found at all, or the censused language
                 has zero public symbols to measure.
Evidence to cite An `index_query` or `file` evidence item citing the engine's `Ratio` payload verbatim
                 (numerator, denominator, method) as the basis for the verdict.
Absence proof    Not applicable — this check never records a FAIL, so no absence search applies; an
                 UNKNOWN states the specific reason (no recognised language, or zero public symbols)
                 directly.
Remediation      playbook `establish-docs-contract` (`catalogue.json` lists it for `NAV-05`); point at
                 the specific undocumented symbols the `Ratio` payload's own breakdown would need to name
                 if the recipe later adds that detail.
Pitfalls         A multi-language repository's reported ratio covers only the one language the engine
                 chose to census (see Engine above) — a high ratio here is not evidence that every
                 language in the repository is well documented, only that the chosen one is.
