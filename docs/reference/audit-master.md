# Audit master list

> **Audience:** CTOs, senior engineers and anyone who wants to know what an audit looks at.
> **Source of truth:** [`catalogue.json`](../../audit/catalogue.json) and the check files in
> [`audit/checks/`](../../audit/checks/README.md).
>
> **Generated** by [`dev/build_masters.py`](../../dev/build_masters.py) from the catalogue and the check files. Do not
> edit it by hand: change a source, then run `make update-masters`. `make check` fails when this page is stale.

---

The audit runs **75 checks** in 13 families (catalogue 0.6.0). 61 are scored; the rest are reported for the whole
picture and earn no credit. The engine decides 73 checks from the files alone; the agent judges 2. Each check below says
what passes and why it matters. To fix a finding, follow the playbook it names in the [implement master
list](implement-master.md).

| Severity | Meaning |
|---|---|
| `BLOCKER` | An agent cannot work safely until this is fixed |
| `DEGRADER` | An agent can work, but slower, with more mistakes or with less trust in its result |
| `COSMETIC` | Worth fixing; it does not change what an agent can do |

## At a glance

| Area | The question it answers | Families | Checks |
|---|---|---|---|
| [Agent context](#agent-context) | Can an agent find the code, the rules and the documents it needs before it edits anything? | [`IDX`](#discovery-and-index-idx), [`AGT`](#agent-governance-agt), [`DOC`](#documentation-contract-doc), [`NAV`](#navigation-nav) | 24 (3 BLOCKER, 16 DEGRADER, 5 COSMETIC) |
| [Command surface and quality gates](#command-surface-and-quality-gates) | Can an agent run one command that formats, lints, type-checks and tests, and trust its answer? | [`CMD`](#command-surface-cmd), [`TOOL`](#tooling-tool), [`TST`](#tests-tst), [`BASE`](#baselines-and-the-ratchet-base) | 20 (3 BLOCKER, 14 DEGRADER, 3 COSMETIC) |
| [Enforcement in CI](#enforcement-in-ci) | Does the pipeline run the same gate the agent runs locally, and does it block the merge? | [`CI`](#continuous-integration-ci) | 5 (2 BLOCKER, 3 DEGRADER) |
| [Reproducible execution](#reproducible-execution) | Does the same command give the same result on a fresh machine, without a human in the loop? | [`EXEC`](#execution-determinism-exec) | 8 (4 BLOCKER, 4 DEGRADER) |
| [Safety boundaries and secrets](#safety-boundaries-and-secrets) | Is it written down, and enforced, what an agent must never touch or reveal? | [`CON`](#constraints-con), [`SEC`](#security-hygiene-sec) | 7 (4 BLOCKER, 2 DEGRADER, 1 COSMETIC) |
| [Team hygiene (informational)](#team-hygiene-informational) | Is the repository run like a team project? Reported for the whole picture; never scored. | [`HYG`](#hygiene-hyg) | 11 (11 COSMETIC) |

## Agent context

Can an agent find the code, the rules and the documents it needs before it edits anything?

### Discovery and Index (IDX)

3 checks: 2 BLOCKER, 1 DEGRADER.

#### `IDX-01` codebase-memory-mcp registered for this repository

`BLOCKER` · scored · engine check · fixed by [`register-index`](implement-master.md#register-index)

- **Passes when:** a readable project- or user-level config names `codebase-memory-mcp`.
- **Why it matters:** Every later check and playbook assumes an agent can reach the index; without registration an agent
  has no way to discover that one should exist ([`docs/framework/phased-approach.md` § Phase 1: Agentic
  Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `IDX-02` An index exists for this checkout

`BLOCKER` · scored · engine check · fixed by [`register-index`](implement-master.md#register-index)

- **Passes when:** the index answers a structural query for this checkout, or the engine finds a store row whose root
  resolves to the target.
- **Why it matters:** An index of a different checkout is worse than none: it answers confidently with structure that no
  longer exists ([`docs/framework/phased-approach.md` § Activities](../framework/phased-approach.md#activities)).

#### `IDX-03` Index freshness

`DEGRADER` · scored · engine check · fixed by [`register-index`](implement-master.md#register-index)

- **Passes when:** the index's recorded revision matches `HEAD`, or a direct freshness query reports no drift.
- **Why it matters:** A stale graph is stale context: an agent edits based on symbols that have already moved or been
  deleted ([`docs/framework/phased-approach.md` § Activities](../framework/phased-approach.md#activities)).

### Agent Governance (AGT)

12 checks: 1 BLOCKER, 10 DEGRADER, 1 COSMETIC.

#### `AGT-01` Instruction file present, canonical, and non-trivial

`BLOCKER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** `AGENTS.md` exists at the repository root in canonical case, is not shadowed by a harness override in
  the same directory, is at least 400 characters, and contains no stub marker.
- **Why it matters:** `AGENTS.md` is the entry point every harness is guaranteed to read; without it an agent infers
  conventions from whatever code it happens to open first ([greenfield/README.md § 6.1
  AGENTS.md](../../greenfield/README.md#61-agentsmd)).

#### `AGT-02` Component coverage by instruction files

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** every declared component has its own `AGENTS.md` (ratio 1.0), or there are no declared components
  beyond the root.
- **Why it matters:** Monorepos have different rules per component; a single root file forces one component's
  conventions onto another ([Phased-Approach.md § Activities](../framework/phased-approach.md#activities)).

#### `AGT-03` Documentation contract named

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** the file names `docs/` as the documentation home, `docs/STYLE_GUIDE.md` as the authoring rules, and
  the scratch-workspace directory as off-limits scratch, each on its own line.
- **Why it matters:** Agents must know where permanent truth lives and what is off-limits, or they treat scratch notes
  as architecture ([greenfield/README.md § 5.2 Templates & Guides](../../greenfield/README.md#52-templates--guides)).

#### `AGT-04` Definition of done stated

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** a sentence ties a stated documentation trigger (public interface, observable behaviour, architecture,
  an ADR, or documentation itself) to updating docs in the same change set.
- **Why it matters:** Docs must change in the same change set as the code they describe, or specs drift within days
  ([greenfield/README.md § 5.2 Templates & Guides](../../greenfield/README.md#52-templates--guides)).

#### `AGT-05` Seven verbs named

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** all seven verbs (`format`, `format:check`, `lint`, `typecheck`, `test`, `check`, `security`) are
  named in the instruction file and each resolves on a runner.
- **Why it matters:** The agent needs the sanctioned verification path stated, or it invents one (`npx vitest` where the
  project uses something else), diverging from what CI actually runs ([greenfield/README.md § 1.4 The standardized
  command surface](../../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)).

#### `AGT-06` Architectural boundaries declared

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** at least two boundary rules each name a path that exists in the repository.
- **Why it matters:** Boundary rules must be stated, not inferred, or edits cross module lines nothing ever wrote down
  ([greenfield/README.md § 6.1 AGENTS.md](../../greenfield/README.md#61-agentsmd)).

#### `AGT-07` Do-not-do / deny rules present

`DEGRADER` · scored · engine check · fixed by [`add-deny-rules`](implement-master.md#add-deny-rules)

- **Passes when:** a prohibitions section exists and covers all four concerns (tests, generated files, the default
  branch, secrets) with an explicit rule for each.
- **Why it matters:** Explicit prohibitions work; implicit ones do not — an agent that is never told "never weaken a
  test" will weaken one ([Phased-Approach.md § Activities](../framework/phased-approach.md#activities)).

#### `AGT-08` No competing instruction files, and the reach matrix is stated

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** no vendor-only competitor exists, no shadowed pair exists, and either every known harness is reached
  or the file states which harnesses it does not reach.
- **Why it matters:** `AGENTS.md`, `CLAUDE.md` and `.cursorrules` disagreeing is obeyed as ambiguity, not flagged as a
  defect — inconsistent behaviour across harnesses, with no way to trace why ([Phased-Approach.md § Phase 1: Agentic
  Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `AGT-09` Branch and release boundary declared

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** the file states which branches exist and whether an agent may tag, release, publish, deploy or push,
  and names every branch the declared branch rules protect by name.
- **Why it matters:** Agents must know whether they may tag, release or push, or one triggers a release it had no
  authority to cut ([Phased-Approach.md § Phase 1: Agentic
  Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `AGT-10` Instruction indirection resolved

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** no configured pointer names a missing file, and no deferral phrase in the entry file names a file
  left unconfigured.
- **Why it matters:** A rule the agent is told to "read elsewhere first" is only as reliable as the harness's own
  willingness to follow that pointer — an unconfigured deferral is a rule that may never load ([Phased-Approach.md §
  Phase 1: Agentic Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `AGT-11` Instructions are specific and not inferable

`DEGRADER` · scored · agent judgement · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** at least 80% of rule lines are specific (by the count above) and every specific line checked resolves
  against the repository; no overview section exceeds roughly a fifth of the file (A14: the overview is optional and
  must not dominate).
- **Why it matters:** This is where A14 (above) is judged directly: a file full of generic, inferable advice costs
  inference time for no benefit, which is R-16's own finding ([Phased-Approach.md §
  Activities](../framework/phased-approach.md#activities)).

#### `AGT-12` Communication rules stated

`COSMETIC` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** the rules exist and name the reader, how to report and how to ask for a decision.
- **Why it matters:** Agents report to people and ask them for decisions; without written rules each agent picks its own
  layout and the reader digs for the bottom line ([greenfield/README.md § 5.2 Templates &
  Guides](../../greenfield/README.md#52-templates--guides)).

### Documentation Contract (DOC)

4 checks: 3 DEGRADER, 1 COSMETIC.

#### `DOC-01` docs/ exists

`DEGRADER` · scored · engine check · fixed by [`establish-docs-contract`](implement-master.md#establish-docs-contract)

- **Passes when:** at least one Markdown file exists anywhere under `docs/`.
- **Why it matters:** `docs/` is the declared home for permanent documentation; without it on day one, documentation has
  nowhere canonical to start ([greenfield/README.md § 5.1 Diátaxis
  Framework](../../greenfield/README.md#51-diátaxis-framework)).

#### `DOC-02` docs/STYLE_GUIDE.md exists

`DEGRADER` · scored · engine check · fixed by [`establish-docs-contract`](implement-master.md#establish-docs-contract)

- **Passes when:** `docs/STYLE_GUIDE.md` exists and the instruction file names it.
- **Why it matters:** Agents need authoring rules they can cite instead of restating per page, or rules get restated and
  drift ([greenfield/README.md § 5.2 Templates & Guides](../../greenfield/README.md#52-templates--guides)).

#### `DOC-03` artefacts/ exists and is ignored

`DEGRADER` · scored · engine check · fixed by [`establish-docs-contract`](implement-master.md#establish-docs-contract)

- **Passes when:** no scratch directory exists anywhere, or one exists, is matched by an ignore rule, and nothing under
  it is tracked.
- **Why it matters:** Transient scratch must be separable and off-limits, or an agent reads work-in-progress notes as
  the current, settled requirement ([greenfield/README.md § 6.2 Agent
  Scratchpad](../../greenfield/README.md#62-agent-scratchpad--artefacts)).

#### `DOC-04` ADR directory and index

`COSMETIC` · scored · engine check · fixed by [`establish-docs-contract`](implement-master.md#establish-docs-contract)

- **Passes when:** a numbered-ADR directory exists, holds at least one entry, and an index lists every entry.
- **Why it matters:** Architectural decisions need a location and a registry, or the rationale lives only in chat and
  pull requests, and agents re-litigate settled decisions ([greenfield/README.md § 5.2 Templates &
  Guides](../../greenfield/README.md#52-templates--guides)).

### Navigation (NAV)

5 checks: 2 DEGRADER, 3 COSMETIC.

#### `NAV-01` Declared component boundaries

`DEGRADER` · scored · engine check · fixed by [`establish-docs-contract`](implement-master.md#establish-docs-contract)

- **Passes when:** at least one non-root component is declared by a build manifest, or the repository is single-root and
  the root itself declares a manifest.
- **Why it matters:** Constraint Engineering needs a bounded component to scope work to; without one, blast radius
  cannot be scoped or reviewed ([docs/framework/overview.md § Applicability](../framework/overview.md#applicability)).

#### `NAV-02` Obvious entry points

`DEGRADER` · scored · engine check · fixed by [`establish-docs-contract`](implement-master.md#establish-docs-contract)

- **Passes when:** at least one entry-point signal is found for the detected ecosystem(s).
- **Why it matters:** Agents must find where execution begins before they can reason about what is live versus dead code
  ([greenfield/README.md § 1.9 Core DI interface file + public entry
  point](../../greenfield/README.md#19-core-di-interface-file--public-entry-point)).

#### `NAV-03` Structural red flags

`COSMETIC` · scored · engine check · fixed by [`establish-docs-contract`](implement-master.md#establish-docs-contract)

- **Passes when:** no oversized file, no catch-all directory, no checked-in binary, and no minified asset is found.
- **Why it matters:** Oversized files, catch-all directories, checked-in binaries and minified assets are exactly where
  agents are drawn when they explore, and exactly where they should not be working ([Phased-Approach.md § Phase 1:
  Agentic Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `NAV-04` Architecture orientation artifact

`COSMETIC` · not scored · engine check · fixed by
[`establish-docs-contract`](implement-master.md#establish-docs-contract)

- **Passes when:** a `docs/architecture/` file, an ADR directory, or a diagram file exists (any one).
- **Why it matters:** A short map lets an agent orient before it explores instead of discovering structure by trial and
  error ([Phased-Approach.md § Key Deliverables](../framework/phased-approach.md#key-deliverables)).

#### `NAV-05` Public-symbol documentation coverage

`COSMETIC` · not scored · engine check · fixed by
[`establish-docs-contract`](implement-master.md#establish-docs-contract)

- **Passes when:** every public symbol found (in the one censused language) is documented.
- **Why it matters:** Phase 2 territory, reported here only as a signal: without any documentation coverage signal an
  agent must read whole function bodies just to learn their signatures ([Phased-Approach.md § Key
  Deliverables](../framework/phased-approach.md#key-deliverables)).

## Command surface and quality gates

Can an agent run one command that formats, lints, type-checks and tests, and trust its answer?

### Command Surface (CMD)

4 checks: 2 BLOCKER, 2 DEGRADER.

#### `CMD-01` Seven verbs resolvable on one runner

`BLOCKER` · scored · engine check · fixed by [`define-command-surface`](implement-master.md#define-command-surface)

- **Passes when:** all seven verbs (`format`, `format:check`, `lint`, `typecheck`, `test`, `check`, `security`) resolve,
  each on the same one runner.
- **Why it matters:** The verbs are the contract; without them resolving an agent has no shared vocabulary for "how do I
  verify this" and invents its own command ([greenfield/README.md § 1.4 The standardized command
  surface](../../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)).

#### `CMD-02` check composes the read-only verbs

`BLOCKER` · scored · engine check · fixed by [`define-command-surface`](implement-master.md#define-command-surface)

- **Passes when:** `check`'s body invokes, directly or by a resolved verb, all three of a format-check, a typecheck and
  a test run.
- **Why it matters:** A single pre-merge gate must exist and be the same one everywhere, or different people gate on
  different subsets of the verbs ([greenfield/README.md § 1.4 The standardized command
  surface](../../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)).

#### `CMD-03` No divergent second definition

`DEGRADER` · scored · engine check · fixed by [`define-command-surface`](implement-master.md#define-command-surface)

- **Passes when:** at most one runner defines `check`, or every runner but the primary delegates to it.
- **Why it matters:** A runner other than the authoritative one must delegate, not compose its own gate, or nobody can
  tell which definition is the real one when they disagree ([greenfield/README.md § 1.4 The standardized command
  surface](../../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)).

#### `CMD-04` Write verbs separated from read-only verbs

`DEGRADER` · scored · engine check · fixed by [`define-command-surface`](implement-master.md#define-command-surface)

- **Passes when:** no read-only verb's command invokes a write verb, directly or by indirection.
- **Why it matters:** A gate that mutates the working tree while "verifying" it cannot be trusted to report on the code
  that was actually committed ([greenfield/README.md § 1.4 The standardized command
  surface](../../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)).

### Tooling (TOOL)

7 checks: 5 DEGRADER, 2 COSMETIC.

#### `TOOL-01` Formatter configured

`DEGRADER` · scored · engine check · fixed by [`configure-quality-tools`](implement-master.md#configure-quality-tools)

- **Passes when:** a formatter config file is present and a `format` verb resolves on some runner.
- **Why it matters:** Formatting must be free and non-negotiable, or every diff mixes style with substance and review
  spends attention on noise ([`docs/framework/phased-approach.md` §
  Activities](../framework/phased-approach.md#activities)).

#### `TOOL-02` Linter configured

`DEGRADER` · scored · engine check · fixed by [`configure-quality-tools`](implement-master.md#configure-quality-tools)

- **Passes when:** a linter config file is present and a `lint` verb resolves on some runner.
- **Why it matters:** A linter catches classes of defect before tests exist to catch them, including regressions an
  agent introduces that no test yet covers ([`docs/framework/phased-approach.md` §
  Activities](../framework/phased-approach.md#activities)).

#### `TOOL-03` Type checker configured

`DEGRADER` · scored · engine check · fixed by [`configure-quality-tools`](implement-master.md#configure-quality-tools)

- **Passes when:** at least one strict-mode signal is found (`tsconfig.json: strict`, mypy/pyright strict,
  `<Nullable>enable</Nullable>`, or a `typecheck` verb with `--strict`).
- **Why it matters:** A strict type checker is the cheapest correctness gate available; without it, interface drift
  between an agent's change and its callers is discovered at runtime instead of at review time
  ([`docs/framework/phased-approach.md` § Activities](../framework/phased-approach.md#activities)).

#### `TOOL-04` Dependency / security scan verb

`DEGRADER` · scored · engine check · fixed by [`configure-quality-tools`](implement-master.md#configure-quality-tools)

- **Passes when:** at least one resolved verb's command matches a known dependency-audit invocation.
- **Why it matters:** Third-party risk is real and agents add dependencies; without a scan, a vulnerability can enter
  through the very change an agent just made ([`docs/framework/phased-approach.md` §
  Activities](../framework/phased-approach.md#activities)).

#### `TOOL-05` Local hook chain active

`DEGRADER` · scored · engine check · fixed by
[`add-hooks-and-commit-rules`](implement-master.md#add-hooks-and-commit-rules)

- **Passes when:** a hook chain is wired (`.pre-commit-config.yaml`, `lefthook.yml`/`.yaml`, `core.hooksPath`, or a
  referenced `.husky/`).
- **Why it matters:** Enforcement must exist where an agent actually works, not only downstream in CI; a rule that lives
  only in CI is a rule an agent cannot honour before it commits ([greenfield/README.md § 2.3 Git
  Hooks](../../greenfield/README.md#23-git-hooks--husky--lint-staged--commitlint)).

#### `TOOL-06` Commit convention enforced

`COSMETIC` · scored · engine check · fixed by
[`add-hooks-and-commit-rules`](implement-master.md#add-hooks-and-commit-rules)

- **Passes when:** a local rule (commitlint config, `commit-msg` hook file or equivalent pre-commit/lefthook stage) and
  a CI step that checks commit messages or the pull-request title are both found.
- **Why it matters:** Release automation reads commit messages; without an enforced convention, version bumps and
  changelog generation silently stop working ([greenfield/README.md § 2.3 Git
  Hooks](../../greenfield/README.md#23-git-hooks--husky--lint-staged--commitlint)).

#### `TOOL-07` Local guard against commits to a protected branch

`COSMETIC` · scored · engine check · fixed by
[`add-hooks-and-commit-rules`](implement-master.md#add-hooks-and-commit-rules)

- **Passes when:** a guard in a wired hook chain names every branch the declared rules protect, or any guard is wired
  and no rules are declared.
- **Why it matters:** An agent commits on whatever branch is checked out. Without a local guard it learns that the
  branch is protected only when the push is refused, and then has to move its commits by hand ([greenfield/README.md §
  2.3 Git Hooks](../../greenfield/README.md#23-git-hooks--husky--lint-staged--commitlint)).

### Tests (TST)

5 checks: 1 BLOCKER, 3 DEGRADER, 1 COSMETIC.

#### `TST-01` Test verb exists, suite non-empty

`BLOCKER` · scored · engine check · fixed by [`define-command-surface`](implement-master.md#define-command-surface)

- **Passes when:** a `test` verb resolves and at least one test-source file exists.
- **Why it matters:** An agent cannot verify a change it cannot run; a resolvable `test` verb and a real suite are the
  floor every other test check stands on ([greenfield/README.md § 3.2 Testing
  Policies](../../greenfield/README.md#32-testing-policies-enforced-via-agentsmd)).

#### `TST-02` Suite status known

`DEGRADER` · scored · engine check · fixed by
[`add-baselines-and-ratchet`](implement-master.md#add-baselines-and-ratchet)

- **Passes when:** the test verb was run as a Tier-C probe and exited 0.
- **Why it matters:** Whether the suite is green *today* determines what an agent can safely attempt; without this an
  agent inherits a red baseline and cannot tell its own regressions from yours ([greenfield/README.md § 3.2 Testing
  Policies](../../greenfield/README.md#32-testing-policies-enforced-via-agentsmd)).

#### `TST-03` Skip / xfail census

`DEGRADER` · scored · engine check · fixed by
[`add-baselines-and-ratchet`](implement-master.md#add-baselines-and-ratchet)

- **Passes when:** the census total is zero.
- **Why it matters:** A suite weakened with skip and expected-failure markers to reach green is the fingerprint of a
  gate that no longer catches the regressions it was meant to ([greenfield/README.md § 3.2 Testing
  Policies](../../greenfield/README.md#32-testing-policies-enforced-via-agentsmd)).

#### `TST-04` Fast path documented

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md),
[`add-baselines-and-ratchet`](implement-master.md#add-baselines-and-ratchet)

- **Passes when:** at least one entry document shows a single-test/subset invocation.
- **Why it matters:** Agent iteration speed is the workflow; without a documented single-test invocation an agent waits
  out the whole suite per attempt, or stops running tests altogether ([Phased-Approach.md § Phase 1: Agentic
  Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `TST-05` Coverage configuration present

`COSMETIC` · scored · engine check · fixed by
[`add-baselines-and-ratchet`](implement-master.md#add-baselines-and-ratchet)

- **Passes when:** any one of the routes above finds coverage configured.
- **Why it matters:** A ratchet (`BASE-03`) needs a number to hold the line on, and coverage is the number for the test
  surface; with none configured there is no floor to hold ([greenfield/README.md § 3.1
  vitest.config.ts](../../greenfield/README.md#31-vitestconfigts--with-coverage)).

### Baselines and the Ratchet (BASE)

4 checks: 4 DEGRADER.

#### `BASE-01` Baseline artifact exists

`DEGRADER` · scored · engine check · fixed by
[`add-baselines-and-ratchet`](implement-master.md#add-baselines-and-ratchet)

- **Passes when:** a baseline/suppression artifact is committed, or an equivalent mechanism is documented in `AGENTS.md`
  or `CLAUDE.md`.
- **Why it matters:** Gates cannot be turned on over existing debt without mass failure; instrumentation that separates
  old debt from new debt must land first ([Phased-Approach.md §
  Activities](../framework/phased-approach.md#activities)).

#### `BASE-02` Current violation counts measured

`DEGRADER` · scored · engine check · fixed by
[`add-baselines-and-ratchet`](implement-master.md#add-baselines-and-ratchet)

- **Passes when:** an explicit numeric violation budget is committed somewhere the engine reads (`--max-warnings 12`,
  `max-issues: 5`, `violation_budget = 40`).
- **Why it matters:** The baseline must be a number, not an impression, or there is no way to tell whether debt is
  growing or shrinking ([Phased-Approach.md § Activities](../framework/phased-approach.md#activities)).

#### `BASE-03` No-new-violations mechanism

`DEGRADER` · scored · engine check · fixed by
[`add-baselines-and-ratchet`](implement-master.md#add-baselines-and-ratchet)

- **Passes when:** a numeric violation budget is committed, or a committed baseline artifact is referenced by name
  inside a CI workflow, or a comparison step is documented in one of the four entry documents.
- **Why it matters:** The policy must be executable, not aspirational, or every change quietly adds a little more debt
  on top of what was already frozen ([Phased-Approach.md § Activities](../framework/phased-approach.md#activities)).

#### `BASE-04` Coverage floor configured

`DEGRADER` · scored · engine check · fixed by
[`add-baselines-and-ratchet`](implement-master.md#add-baselines-and-ratchet)

- **Passes when:** a coverage threshold is configured in test-runner configuration.
- **Why it matters:** Coverage is the most common form of the ratchet, and without a configured floor it decays
  invisibly, one untested branch at a time ([greenfield/README.md § 4.1
  Workflows](../../greenfield/README.md#41-workflows)).

## Enforcement in CI

Does the pipeline run the same gate the agent runs locally, and does it block the merge?

### Continuous Integration (CI)

5 checks: 2 BLOCKER, 3 DEGRADER.

#### `CI-01` Pipeline present, triggered on PRs

`BLOCKER` · scored · engine check · fixed by [`add-ci-parity`](implement-master.md#add-ci-parity)

- **Passes when:** at least one workflow file exists and declares a pull-request trigger the engine's pattern
  recognises.
- **Why it matters:** Verification must be automatic and independent of the author, or "I ran the tests" before pushing
  is unverifiable by anyone else ([greenfield/README.md § 4.1 Workflows](../../greenfield/README.md#41-workflows)).

#### `CI-02` Local↔CI parity

`BLOCKER` · scored · engine check · fixed by [`add-ci-parity`](implement-master.md#add-ci-parity)

- **Passes when:** every framework verb a CI command invokes also resolves locally.
- **Why it matters:** The gate an agent *can* run locally must be the gate that *decides*, or an agent optimises against
  a weaker local gate and discovers the real gap only at review ([greenfield/README.md § 1.4 The standardized command
  surface](../../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)).

#### `CI-03` CI-only steps flagged

`DEGRADER` · scored · engine check · fixed by [`add-ci-parity`](implement-master.md#add-ci-parity)

- **Passes when:** no CI command names a runner target absent from every local runner manifest.
- **Why it matters:** A step with no local equivalent is a failure an agent cannot reproduce, so it cannot investigate
  or fix what CI is failing it on ([greenfield/README.md § 1.4 The standardized command
  surface](../../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)).

#### `CI-04` CI enforces the same gate as the local check

`DEGRADER` · scored · agent judgement · fixed by [`add-ci-parity`](implement-master.md#add-ci-parity)

- **Passes when:** every job running a verb (or `check`) gates on it — no `continue-on-error`, no swallowed exit code on
  the gating command — and the workflow is a required status check for merging (confirmed, not just assumed from the
  workflow file alone).
- **Why it matters:** A pipeline that runs the verbs but does not fail the build when one of them fails is theatre, not
  enforcement ([greenfield/README.md § 1.4 The standardized command
  surface](../../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)).

#### `CI-05` Workflow files are linted

`DEGRADER` · scored · engine check · fixed by [`add-ci-parity`](implement-master.md#add-ci-parity)

- **Passes when:** every provider with workflow files has a linter that runs locally.
- **Why it matters:** An agent cannot run a workflow on its machine. A linter that knows the CI provider is its only
  check before a push: without one, a broken expression, a wrong action input or a script-injection risk is found only
  after the push ([greenfield/README.md § 4.1 Workflows](../../greenfield/README.md#41-workflows)).

## Reproducible execution

Does the same command give the same result on a fresh machine, without a human in the loop?

### Execution determinism (EXEC)

8 checks: 4 BLOCKER, 4 DEGRADER.

#### `EXEC-01` Toolchain pinned / wrapper committed

`BLOCKER` · scored · engine check · fixed by
[`pin-execution-environment`](implement-master.md#pin-execution-environment)

- **Passes when:** every detected pinnable ecosystem has at least one of its own pin files, or a matching
  `.tool-versions` line, or (node/python/go) the manifest-level constraint.
- **Why it matters:** An agent's runtime must be the repository's, not whatever happens to be on the host — otherwise
  the gate passes locally and fails in CI, or an agent reproduces nothing ([greenfield/README.md § File Tree — What Gets
  Created](../../greenfield/README.md#file-tree--what-gets-created)).

#### `EXEC-02` Lockfile committed and consistent

`BLOCKER` · scored · engine check · fixed by
[`pin-execution-environment`](implement-master.md#pin-execution-environment)

- **Passes when:** every detected ecosystem's lockfile exists, is tracked, and (where parsing is attempted) agrees with
  the manifest.
- **Why it matters:** Every run must resolve identical dependencies; a lockfile that is missing, untracked, or stale
  turns "works on my machine" into a problem the agent inherits too ([Phased-Approach.md § Phase 1: Agentic
  Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `EXEC-03` Non-interactive setup path

`BLOCKER` · scored · engine check · fixed by [`define-command-surface`](implement-master.md#define-command-surface)

- **Passes when:** a documented non-interactive install command exists, or a setup artifact exists and is named by one
  of the four doc files.
- **Why it matters:** An agent cannot answer an interactive prompt or provision a database by guessing; with no
  non-interactive path it is blocked before it can run anything ([Phased-Approach.md § Phase 1: Agentic
  Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `EXEC-04` Env-var inventory complete

`BLOCKER` · scored · engine check · fixed by
[`env-inventory-and-secrets`](implement-master.md#env-inventory-and-secrets)

- **Passes when:** every referenced key not on the allow-list is declared in a committed example file (including the
  case of no references at all).
- **Why it matters:** A variable the code needs but nobody wrote down fails at runtime, mid-task, and the agent debugs
  an environment problem it has no way to see coming ([greenfield/README.md § File Tree — What Gets
  Created](../../greenfield/README.md#file-tree--what-gets-created)).

#### `EXEC-05` No generated artifacts committed in-tree

`DEGRADER` · scored · engine check · fixed by [`untrack-generated`](implement-master.md#untrack-generated)

- **Passes when:** no tracked path is classified `GENERATED`, or every tracked `GENERATED` path carries a generated-file
  header in its first 20 lines.
- **Why it matters:** An agent that edits a file the build regenerates loses its work silently, often not until the next
  CI run or review ([Phased-Approach.md § Phase 1: Agentic
  Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `EXEC-06` Documented commands resolve

`DEGRADER` · scored · engine check · fixed by [`adapt-agents-md`](implement-master.md#adapt-agents-md)

- **Passes when:** every documented command resolves, or no fenced shell command is documented at all.
- **Why it matters:** An agent runs the documented command literally; a command that does not resolve is the most
  expensive brownfield trap there is, discovered only after the agent has already acted on it ([Phased-Approach.md §
  Phase 1: Agentic Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `EXEC-07` No competing configs for one concern

`DEGRADER` · scored · engine check · fixed by [`untrack-generated`](implement-master.md#untrack-generated)

- **Passes when:** each of the five concerns has at most one matching root config (including zero).
- **Why it matters:** One concern, one authoritative answer; with two configs for the same concern an agent (or a human)
  picks whichever result turns up first, which is not the same thing as picking correctly ([Phased-Approach.md § Phase
  1: Agentic Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `EXEC-08` Tool versions visible to dependency automation

`DEGRADER` · scored · engine check · fixed by
[`pin-execution-environment`](implement-master.md#pin-execution-environment)

- **Passes when:** no literal tool version in any file read, or the file is matched by a Renovate `customManagers` (or
  `regexManagers`) file pattern.
- **Why it matters:** Dependabot and Renovate read manifests, not commands. A tool version typed into a `Makefile`, a
  workflow or a hook gets no security alert and no update, and an agent asked to upgrade the tool must find every copy
  by hand.

## Safety boundaries and secrets

Is it written down, and enforced, what an agent must never touch or reveal?

### Constraints (CON)

4 checks: 2 BLOCKER, 1 DEGRADER, 1 COSMETIC.

#### `CON-01` Allow/deny artifact present

`BLOCKER` · scored · engine check · fixed by [`add-deny-rules`](implement-master.md#add-deny-rules)

- **Passes when:** the prohibitions section names, in a code span, at least one path or pattern that matches a file or
  directory of the repository.
- **Why it matters:** An agent cannot respect a boundary that exists only in someone's head; the deny list must be a
  concrete, written artifact, not an unstated expectation ([Phased-Approach.md §
  Activities](../framework/phased-approach.md#activities)).

#### `CON-02` Test directories protected

`BLOCKER` · scored · engine check · fixed by [`add-deny-rules`](implement-master.md#add-deny-rules)

- **Passes when:** the prohibitions section names, in code spans, every test directory found.
- **Why it matters:** Tests are the safety net; an agent that may freely edit them is not actually gated by them, and
  can make a failure disappear instead of fixing it ([docs/framework/overview.md §
  Principles](../framework/overview.md#principles)).

#### `CON-03` artefacts/ excluded from index and agent reads

`DEGRADER` · scored · engine check · fixed by [`add-deny-rules`](implement-master.md#add-deny-rules)

- **Passes when:** no candidate root exists, or every root that exists is matched by an ignore rule and nothing under
  any of them is tracked.
- **Why it matters:** Scratch notes must not become context an agent treats as source of truth; a tracked or unignored
  scratch directory pollutes every session that follows ([greenfield/README.md § 6.2 Agent
  Scratchpad](../../greenfield/README.md#62-agent-scratchpad--artefacts)).

#### `CON-04` Draft allow/deny emitted

`COSMETIC` · not scored · engine check · no playbook (the audit emits it as an input)

- **Passes when:** the draft was written to `do-not-do.draft.md` beside the report.
- **Why it matters:** The scan knows what is dangerous in *this* repository; without it, every adoption starts from a
  generic template that fits nobody and an agent (or a human) has to rediscover the same paths by exploring
  ([Phased-Approach.md § Activities](../framework/phased-approach.md#activities)).

### Security hygiene (SEC)

3 checks: 2 BLOCKER, 1 DEGRADER.

#### `SEC-01` .env untracked and ignored

`BLOCKER` · scored · engine check · fixed by
[`env-inventory-and-secrets`](implement-master.md#env-inventory-and-secrets)

- **Passes when:** no `.env`/`.env.*` file is tracked, and ignore rules cover both shapes.
- **Why it matters:** An agent's context is transmitted and logged; a tracked `.env` file is a credential exposed
  through the tool added for safety, not despite it ([Phased-Approach.md § Phase 1: Agentic
  Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

#### `SEC-02` No key-shaped strings in tracked files

`BLOCKER` · scored · engine check · fixed by
[`env-inventory-and-secrets`](implement-master.md#env-inventory-and-secrets)

- **Passes when:** no tracked text file (or, with tracked state unavailable, no file in the whole inventory) contains a
  credential-shaped line outside the repository's own allowlist.
- **Why it matters:** A hardcoded credential is the same exposure as a tracked `.env` file, just inside source or
  configuration instead of a dedicated file ([Phased-Approach.md §
  Activities](../framework/phased-approach.md#activities)).

#### `SEC-03` Ignore patterns cover secret shapes

`DEGRADER` · scored · engine check · fixed by
[`env-inventory-and-secrets`](implement-master.md#env-inventory-and-secrets)

- **Passes when:** ignore rules cover every one of the eleven documented secret shapes.
- **Why it matters:** The guard must exist before the accident — ignore rules that do not cover a secret shape let a
  single careless commit become permanent history ([Phased-Approach.md § Phase 1: Agentic
  Bootstrap](../framework/phased-approach.md#phase-1-agentic-bootstrap-)).

## Team hygiene (informational)

Is the repository run like a team project? Reported for the whole picture; never scored.

### Hygiene (HYG)

11 checks: 11 COSMETIC.

#### `HYG-01` README present and non-placeholder

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** a root README exists, reads as text, has at least 200 characters of body, carries no placeholder
  marker, and is not a bare title.
- **Why it matters:** An agent (or a person) must be able to orient itself in this project in seconds, not by opening
  files at random.

#### `HYG-02` CODEOWNERS present

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** a `CODEOWNERS` file exists at one of the recognised locations.
- **Why it matters:** Review routing should be machine-readable, not tribal knowledge about who owns what.

#### `HYG-03` Pull-request template present

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** at least one `pull_request_template*` file exists.
- **Why it matters:** A reviewer needs the same information every time a change is filed, not whatever the author
  happened to think to write.

#### `HYG-04` Issue templates present

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** at least one file exists under `.github/ISSUE_TEMPLATE/`, or `.github/ISSUE_TEMPLATE.md` exists.
- **Why it matters:** A bug report or feature request filed in a structured way is faster to triage than free text.

#### `HYG-05` CONTRIBUTING present

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** at least one `CONTRIBUTING`-prefixed document exists at a repository-level location.
- **Why it matters:** A contributor should not have to reverse-engineer the setup, the gate and the review flow from
  reading commit history.

#### `HYG-06` SECURITY present

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** at least one `SECURITY`-prefixed document exists at a repository-level location.
- **Why it matters:** A vulnerability should have a documented, private way to be reported, not left to whatever channel
  the reporter happens to try first.

#### `HYG-07` CHANGELOG present and recent

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** a changelog document exists and its last commit is within 365 days of `HEAD`'s.
- **Why it matters:** A reader needs to see what changed between two versions without diffing the whole history
  themselves.

#### `HYG-08` Release process documented

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** at least one text/Markdown document whose name contains `release` exists.
- **Why it matters:** Whoever cuts the next release should be following a written process, not reconstructing it from
  whoever did it last time's memory.

#### `HYG-09` Dependency update automation configured

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** a configuration exists, every detected ecosystem has an entry, and no entry has the trap.
- **Why it matters:** Dependencies should be patched on a schedule, not discovered stale during an incident. A
  configuration that silently misses an ecosystem, or whose rules do not reach security updates, looks like a policy and
  is not one.

#### `HYG-10` License present

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** a root license file (one of the five recognised name prefixes) exists.
- **Why it matters:** Anyone using or contributing to the code needs to know the terms under which it may be used,
  without asking.

#### `HYG-11` Branch protection declared as code

`COSMETIC` · not scored · engine check · fixed by [`add-repo-hygiene`](implement-master.md#add-repo-hygiene)

- **Passes when:** rules are declared as code, and a two-branch model has a source-branch check.
- **Why it matters:** Protected-branch rules should be reviewed like any other change, not configured by hand in a
  settings page nobody diffs. In a two-branch model the release branch must also refuse pull requests from anything but
  the integration branch, and a ruleset cannot say that.

## Read more

- The full rubric of each check (PARTIAL, FAIL, evidence, pitfalls):
  [`audit/checks/`](../../audit/checks/README.md).
- Each check's requirement and framework section:
  [Checks to framework map](how-the-checks-map-to-the-framework.md).
- How an audit runs: [Run an audit](../how-to/run-an-audit.md).
