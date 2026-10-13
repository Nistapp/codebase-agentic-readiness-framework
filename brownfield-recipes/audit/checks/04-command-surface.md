# Command Surface (`CMD`)

> Follows the anatomy in [`README.md`](README.md). Four checks, all `method: automated`. See
> [Why These Checks §5](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#5-command-surface-cmd)
> for the consequence behind this family: one command surface, three consumers (human, agent, CI); this
> is the core of Phase 1 and the most common brownfield failure. Every verb and spelling cited below is
> fixed in [`spec/command-surface.md`](../../../spec/command-surface.md); this file never restates that
> table, only how each check reads against it.

---

## CMD-01 — Seven verbs, resolvable on one runner

Why it matters   The verbs are the contract; without them resolving an agent has no shared vocabulary
                  for "how do I verify this" and invents its own command
                  ([greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs)).
Severity         BLOCKER
Engine           `CMD-01`. Reads every runner manifest `_common` understands in full
                 (`resolve_all_verbs`), so a verb split across, or duplicated on, more than one runner is
                 visible. All seven verbs resolving on exactly one runner is `PASS`. Any verb missing from
                 every runner is `FAIL`. Verbs resolving but spread across more than one runner is
                 `PARTIAL` (the stray second definition itself is `CMD-03`'s territory, not this check's).
                 A `Makefile` GNU Make refuses to parse (an unescaped `format:check:` target, a static
                 pattern rule with no `%`) is not a runner at all: `FAIL` as `CMD-01:Makefile` when no
                 other runner carries the verbs, otherwise at least `PARTIAL`, and `CMD-02`–`CMD-04` report
                 `UNKNOWN` rather than compound the same defect. No recognised runner manifest at all
                 (`package.json`, `Makefile`, `Taskfile`, `pyproject.toml`, Gradle, Maven) is the engine's
                 own `UNKNOWN`: an ecosystem this engine does not yet resolve is not proof the verbs are
                 missing. Distrust a `FAIL` or `UNKNOWN` when the project uses a runner outside that set
                 (Just, mise, Rake, Cargo aliases, `uv run` scripts) — `spec/command-surface.md`'s own
                 "a runner this table does not cover" rule asks the audit to propose the nearest spelling
                 and confirm it with the owner rather than accept the engine's `UNKNOWN` as the last word.
Method           automated
Look for         The runner manifest itself (`package.json` scripts, `Makefile` targets, `Taskfile.yml`,
                 `pyproject.toml`'s task-runner tables, Gradle/Maven build files); for an unrecognised
                 runner, the project's own README or instruction file for how each verb is actually run.
Rubric           PASS: all seven verbs (`format`, `format:check`, `lint`, `typecheck`, `test`, `check`,
                 `security`) resolve, each on the same one runner.
                 PARTIAL: all seven resolve, but across more than one runner, or a `Makefile` that fails
                 to parse coexists with another runner that does carry the verbs.
                 FAIL: at least one verb resolves on no runner at all, or the only runner present is a
                 `Makefile` GNU Make refuses to parse.
                 NOT_APPLICABLE: never — every repository has some command surface, even an empty one.
                 UNKNOWN when: no runner manifest this engine's resolver understands exists at all.
Evidence to cite A `file` evidence item per runner manifest read, with `note` listing which verbs it
                 resolved; a `command` evidence item for a Makefile's own `make -n` or parse attempt when
                 citing a parse failure.
Absence proof    A FAIL for a missing verb names it explicitly in the finding statement; an UNKNOWN for "no
                 recognised runner" records a `glob` search for each manifest filename class checked, with
                 a `0` hit count.
Remediation      `define-command-surface`
Pitfalls         A Gradle or Maven build that resolves `check` as a lifecycle task is a real `PASS` for
                 this check even though `CMD-02` cannot see inside it (that gap is `CMD-02`'s own
                 `UNKNOWN`, not a reason to downgrade `CMD-01`). A verb hidden inside a quoted string, or
                 behind a shell variable, is invisible to the engine's textual reader — read the actual
                 script body before accepting a `FAIL` on a runner that might define the verb in a form
                 the engine cannot parse.

## CMD-02 — `check` composes the read-only verbs

Why it matters   A single pre-merge gate must exist and be the same one everywhere, or different people
                  gate on different subsets of the verbs
                  ([greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs)).
Severity         BLOCKER
Engine           `CMD-02`. Resolves `check` on its one runner (the same resolver `CMD-01` uses) and reads
                 its body for three concerns — a format-check, a typecheck, a test run — satisfied either
                 by invoking another resolved verb by name (indirection: `npm run format:check`) or by a
                 documented tool equivalent (`ruff check`, `tsc`, `pytest`, and others the engine's own
                 pattern list names). In a `Makefile`, `check`'s prerequisites are its body, and a
                 prerequisite that is not itself a verb is followed into its own recipe, once. All three
                 concerns present is `PASS`; some is `PARTIAL`; none is `FAIL`. A Gradle or Maven `check`
                 that is a lifecycle task is `UNKNOWN` — its dependency graph is the build's own, not a
                 command the engine reads (S2.6's own finding on this repository's dogfooding run). No
                 runner at all, or the Makefile `CMD-01` already flagged as unparseable, is also `UNKNOWN`.
                 Distrust a `FAIL` or `PARTIAL` when `check`'s tool choice is one the engine's documented-
                 equivalent list does not yet name — verify by reading the command for a tool this project
                 actually uses for the missing concern before accepting the gap as real.
Method           automated
Look for         The `check` verb's own command body (not just its name); for a `Makefile`, the recipe of
                 every prerequisite target `check` lists that is not itself a named verb.
Rubric           PASS: `check`'s body invokes, directly or by a resolved verb, all three of a format-check,
                 a typecheck and a test run.
                 PARTIAL: it invokes one or two of the three.
                 FAIL: a `check` verb is defined but invokes none of the three.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no runner exists to read, the only runner is a `Makefile` `CMD-01` already
                 reports as unparseable, or `check` is a Gradle/Maven lifecycle task whose composition is
                 set by the build graph rather than a readable command.
Evidence to cite A `command` evidence item citing the runner and `check`'s resolved command text, with
                 `note` listing the concerns it was found to compose.
Absence proof    A FAIL or PARTIAL names each missing concern (`format-check`, `typecheck`, `test`)
                 explicitly in the finding statement, citing the `check` command body that was read as the
                 evidence that the concern is absent from it.
Remediation      `define-command-surface`
Pitfalls         A `check` that composes `lint` instead of `format:check` is not the same gate the
                 framework defines: `lint` is read-only but is not one of the three composed concerns
                 (`format:check`, `typecheck`, `test`) — `spec/command-surface.md` names `lint` as a
                 standalone verb, not part of `check`'s own composition, and the engine's `_CONCERN_OF_VERB`
                 table reflects that; do not credit a `lint`-only `check` with the `format-check` concern.

## CMD-03 — No divergent second definition

Why it matters   A runner other than the authoritative one must delegate, not compose its own gate, or
                  nobody can tell which definition is the real one when they disagree
                  ([greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs)).
Severity         DEGRADER
Engine           `CMD-03`. When more than one runner defines a `check` target, the primary is the
                 highest-precedence runner present (`RUNNER_PRECEDENCE`); every other runner's `check` is
                 checked for a delegation to the primary (a known delegation pattern per runner —
                 `npm run check`, `make check`/`$(MAKE) check`, `task check`, `./gradlew check`, and the
                 rest — or, more generally, any segment that invokes `check` on a runner other than the
                 one that currently owns it). A second runner that delegates is `PASS`; one that composes
                 its own gate independently is `FAIL`. Zero or one runner defining `check` at all is
                 `PASS` by construction (nothing to diverge). No runner at all is the engine's own
                 `UNKNOWN`. Distrust a `FAIL` when the "divergent" runner's own `check` is itself a thin
                 wrapper the engine's delegation patterns do not recognise (a custom shell script that
                 calls out to the primary runner in a form outside the known patterns) — verify by reading
                 that runner's `check` command directly.
Method           automated
Look for         Every runner manifest present, specifically whether each defines its own `check`; for any
                 that do, whether the secondary's `check` command actually invokes the primary's.
Rubric           PASS: at most one runner defines `check`, or every runner but the primary delegates to it.
                 PARTIAL: not used by this check (the engine's outcome is binary: a delegation either holds
                 or it does not, for each secondary runner found).
                 FAIL: at least one runner other than the primary defines `check` independently, without
                 delegating to it.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no runner defines `check` at all because no runner manifest exists to read
                 (distinct from "zero or one defines it", which is a real PASS).
Evidence to cite A `file` evidence item per divergent runner, citing its manifest and the `check` command
                 text that does not delegate.
Absence proof    A FAIL names the divergent runner(s) explicitly and cites each one's actual `check`
                 command as the evidence that no delegation pattern matched.
Remediation      `define-command-surface`
Pitfalls         The primary runner is decided by `RUNNER_PRECEDENCE`, not by which one was added first or
                 is used more often — if the project's own convention disagrees with the engine's
                 precedence order, say so explicitly in the finding rather than silently treating the
                 engine's choice of primary as the project's intent.

## CMD-04 — Write verbs separated from read-only verbs

Why it matters   A gate that mutates the working tree while "verifying" it cannot be trusted to report on
                  the code that was actually committed
                  ([greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs)).
Severity         DEGRADER
Engine           `CMD-04`. For every read-only verb (every framework verb except the write verbs `format`,
                 `install`, `build`, `clean`), reads its resolved command for an invocation of a write verb
                 — either by name through another runner (`npm run format`) or by a direct writer pattern
                 (`prettier --write`, `eslint --fix`, bare `cargo fmt` without `--check`, `rm -rf`, and the
                 rest the engine's own pattern tables name). None found is `PASS`; any found is `FAIL`. No
                 runner at all is the engine's own `UNKNOWN`. Distrust a `FAIL` when the matched pattern is
                 inside a comment or a string the command merely echoes rather than executes — verify by
                 reading the actual command, not just the matched substring, before accepting the finding.
Method           automated
Look for         Each read-only verb's resolved command text; whether any segment of it, followed through
                 one level of runner indirection, invokes a tool in its mutating form.
Rubric           PASS: no read-only verb's command invokes a write verb, directly or by indirection.
                 PARTIAL: not used by this check (the engine's outcome is binary per offending verb; one or
                 more offenders is already `FAIL`, not a softer partial state).
                 FAIL: at least one read-only verb's command invokes a write verb.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no runner exists to read.
Evidence to cite A `command` evidence item per offending read-only verb, citing the runner and the exact
                 command text that matched a write pattern, with `note` naming the write verb it
                 represents.
Absence proof    A FAIL names each offending read-only verb and the write verb it invokes explicitly in
                 the finding statement; the cited command text is itself the proof, so no separate absence
                 search applies.
Remediation      `define-command-surface`
Pitfalls         The engine's writer patterns are deliberately narrow (the check form of a tool,
                 `prettier --check`, must never be mistaken for its write form, `prettier --write`) — a
                 tool invoked with neither flag, in a form the pattern tables do not recognise either way,
                 is a real gap in coverage, not a false negative to excuse; read the command directly
                 before trusting a `PASS` on an unfamiliar tool invocation.
