# Readiness requirements: Phase 1

Normative. These are the requirements a repository meets to complete Phase 1 (Agentic Bootstrap) and the requirements common to new and existing repositories. Phases 2 to 4 are not written yet. The conventions (requirement language, IDs, fields and verification methods) are in [README.md](README.md#conventions).

## How to read this page

- **Area.** `REQ-SH` is a property any repository, new or existing, has to count as ready: the greenfield recipe produces it and the brownfield audit checks it. `REQ-BF` is a property that exists only because the repository already has history, such as an inherited violation baseline. The greenfield track starts without debt, so almost everything is shared.
- **Phase.** Every requirement here is phase 1 of the [framework phases](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-).
- **Keyword.** A requirement is a MUST unless its check is rated COSMETIC, which makes it a SHOULD. Severity is the catalogue's at the time of writing.
- **Source.** The framework text the requirement comes from. Where the framework does not say it in so many words and the requirement follows from the Phase 1 objective ("executable, discoverable, and safe for agent interaction"), the source is the nearest framework heading, usually the Phase 1 heading, and [traceability.md](traceability.md) lists the requirement as derived.
- **Checks.** Check IDs are those of the [check catalogue](../audit/catalogue.json): the audit engine's, as printed by `python3 -m audit --list-checks`, and the checks that only an agent runs. A test keeps the catalogue and these fields in step. [traceability.md](traceability.md) lists the requirements for each check.
- **Command surface.** The verbs and their spelling on each runner are in [command-surface.md](command-surface.md).
- **Prohibitions section.** The section of the instruction file whose heading says what an agent must not do: "Do Not Do", "Never", "Prohibited", "Forbidden" or "Deny". It is the repository's deny list, and nothing else is required to be ([decision 0001](decisions/0001-constraint-artifact.md)).
- **Naming a path.** An entry of the prohibitions section names a path when the path, or a pattern that covers it, appears in a code span of that entry.

## Discovery and index

### REQ-SH-001 — Index server registered
The repository MUST be registered with `codebase-memory-mcp` in a project-level or user-level MCP configuration.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 6.4 Codebase-Memory-MCP Registration](../greenfield/README.md#64-codebase-memory-mcp-registration)
- **Checks:** IDX-01

### REQ-SH-002 — Index exists
An index of the checked-out repository MUST exist in the `codebase-memory-mcp` index store.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** IDX-02

### REQ-SH-003 — Index current
The index of the repository MUST have been built from the revision that is checked out.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** IDX-03

### REQ-SH-004 — Agents explore through the index
Agents MUST explore the code through the index before they write code.

- **Phase:** 1
- **Verification:** attested
- **Source:** [Overview.md § Principles](../docs/framework/overview.md#principles)
- **Checks:** none (attested)

## Agent governance

### REQ-SH-005 — Canonical instruction file
The repository root MUST contain a canonical instruction file, `AGENTS.md`, that is not a stub, is spelled in the canonical case and is not shadowed by an override file in the same directory.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 6.1 AGENTS.md](../greenfield/README.md#61-agentsmd)
- **Checks:** AGT-01

### REQ-SH-006 — Component instruction files
Every declared component MUST have its own instruction file.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** AGT-02

### REQ-SH-007 — Documentation contract named
The instruction file MUST name `docs/` as the single source of truth for permanent documentation, `docs/STYLE_GUIDE.md` as its canonical authoring rules, and `artefacts/` as transient scratch that agents MUST NOT read unless a human passes an explicit path.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 5.2 Templates & Guides](../greenfield/README.md#52-templates--guides)
- **Checks:** AGT-03

### REQ-SH-008 — Definition of done stated
The instruction file MUST state that a change that alters a public interface, observable behaviour, architecture or an ADR updates the affected documentation in the same change set.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 5.2 Templates & Guides](../greenfield/README.md#52-templates--guides)
- **Checks:** AGT-04

### REQ-SH-009 — Verbs named
The instruction file MUST name every verb of the [command surface](command-surface.md) with the command that runs it, and each of those commands MUST resolve on the repository's runner.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 1.4 The standardized command surface](../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)
- **Checks:** AGT-05

### REQ-SH-010 — Architectural boundaries declared
The instruction file MUST declare at least two architectural boundary rules, each naming real paths of the repository.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 6.1 AGENTS.md](../greenfield/README.md#61-agentsmd)
- **Checks:** AGT-06

### REQ-SH-011 — Prohibitions declared
The instruction file MUST contain a prohibitions section, and the prohibitions in the file MUST cover tests, generated files, the default branch and secrets.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** AGT-07

### REQ-SH-012 — No competing instruction files
No instruction file for another agent harness MAY compete with the canonical file: every shadow pair MUST be reconciled, and the canonical file MUST state which harnesses it does not reach.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** AGT-08

### REQ-SH-013 — Branch and release boundary declared
The instruction file MUST state which branches exist and whether an agent may tag or release.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** AGT-09

### REQ-SH-014 — Instruction indirection resolved
When the entry instruction file defers to another file, that file MUST be named in the harness configuration or inlined into the entry file.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** AGT-10

### REQ-SH-015 — Instructions are specific and not inferable
The instruction file MUST consist of instructions that are specific to the repository and that an agent cannot infer by reading its code, and MUST NOT pad that content with generic or inferable material.

- **Phase:** 1
- **Verification:** agent
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** AGT-11

### REQ-SH-060 — Communication rules stated

The instruction file SHOULD state how agents write for people, in a section of its own or in a rules file it links:
who the reader is, how an agent reports its work, and how it asks a person for a decision.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 5.2 Templates & Guides](../greenfield/README.md#52-templates--guides)
- **Checks:** AGT-12

## Documentation contract

### REQ-SH-016 — Documentation directory
The repository MUST have a `docs/` directory that contains at least one Markdown file.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 5.1 Diátaxis Framework](../greenfield/README.md#51-diátaxis-framework)
- **Checks:** DOC-01

### REQ-SH-017 — Style guide
`docs/STYLE_GUIDE.md` MUST exist.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 5.2 Templates & Guides](../greenfield/README.md#52-templates--guides)
- **Checks:** DOC-02

### REQ-SH-018 — Scratch and tool-state directories ignored
When `artefacts/`, `artifacts/` or a directory where an agent tool keeps its own state exists, an ignore rule MUST match it and none of its contents MAY be tracked.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 6.2 Agent Scratchpad](../greenfield/README.md#62-agent-scratchpad--artefacts)
- **Checks:** DOC-03, CON-03

### REQ-SH-019 — ADR directory and index
The repository SHOULD have an ADR directory with numbered entries and an index that lists every entry.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 5.2 Templates & Guides](../greenfield/README.md#52-templates--guides)
- **Checks:** DOC-04

### REQ-SH-061 — Documentation is readable

The prose in `docs/` SHOULD follow plain-language rules: few sentences over 25 words (20 in a numbered step), no
vague or padded words, and a diagram on each explanation or tutorial page.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 5.2 Templates & Guides](../greenfield/README.md#52-templates--guides)
- **Checks:** DOC-05

### REQ-SH-020 — Documentation is accurate
The repository's owner MUST declare that the permanent documentation describes what the code does today.

- **Phase:** 1
- **Verification:** attested
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** none (attested)

## Command surface

### REQ-SH-021 — Verbs defined on one runner
The repository MUST define every verb of the [command surface](command-surface.md) on one authoritative runner, using the spelling that the command surface gives for that runner.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 1.4 The standardized command surface](../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)
- **Checks:** CMD-01

### REQ-SH-022 — `check` composes the read-only verbs
The `check` verb MUST run `format:check`, `typecheck` and `test`. The `format:check` verb MUST include the repository's lint rules, so a repository gates lint through `format:check`; see [decision 0002](decisions/0002-lint-in-the-gate.md).

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 1.4 The standardized command surface](../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)
- **Checks:** CMD-02

### REQ-SH-023 — No second definition of the gate
A runner other than the authoritative one MAY define `check` only as a delegation to the authoritative runner.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 1.4 The standardized command surface](../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)
- **Checks:** CMD-03

### REQ-SH-024 — Read-only verbs do not write
No read-only verb MAY invoke a write command: `format`, install, build or clean.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 1.4 The standardized command surface](../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)
- **Checks:** CMD-04

### REQ-SH-025 — Documented commands resolve
Every command in a fenced shell block of `README.md` or of the instruction file MUST resolve to a real script, verb, tool or path.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** EXEC-06

### REQ-SH-026 — The gate is honoured
The team MUST run `check` on every change and honour its result, including under deadline.

- **Phase:** 1
- **Verification:** attested
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** none (attested)

## Tooling

### REQ-SH-027 — Formatter
The repository MUST configure a formatter and expose it through the `format` verb.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** TOOL-01

### REQ-SH-028 — Linter
The repository MUST configure a linter and expose it through the `lint` verb.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** TOOL-02

### REQ-SH-029 — Strict type checking
Where the language has a type checker, the repository MUST configure it in strict mode.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** TOOL-03

### REQ-SH-030 — Dependency vulnerability scan
The `security` verb MUST run a dependency vulnerability scan.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** TOOL-04

### REQ-SH-031 — Local hook chain
The repository MUST wire a local Git hook chain, through a hook manager or `core.hooksPath`.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 2.3 Git Hooks](../greenfield/README.md#23-git-hooks--husky--lint-staged--commitlint)
- **Checks:** TOOL-05

### REQ-SH-032 — Commit convention enforced
The repository SHOULD enforce its commit-message convention with a `commit-msg` hook or an equivalent stage, and
SHOULD check the same rule in CI.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 2.3 Git Hooks](../greenfield/README.md#23-git-hooks--husky--lint-staged--commitlint)
- **Checks:** TOOL-06

### REQ-SH-059 — Local guard against commits to a protected branch

The repository SHOULD wire a local hook that refuses a commit on each branch its branch rules protect, so that an
agent learns it is on a protected branch before it commits, not when the push is refused.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 2.3 Git Hooks](../greenfield/README.md#23-git-hooks--husky--lint-staged--commitlint)
- **Checks:** TOOL-07

## Continuous integration

### REQ-SH-033 — Pipeline on pull requests
The repository MUST have a CI pipeline that runs on pull requests.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 4.1 Workflows](../greenfield/README.md#41-workflows)
- **Checks:** CI-01

### REQ-SH-034 — CI runs the verbs
Every verification command in the CI pipeline MUST be a verb of the [command surface](command-surface.md) run through the repository's runner, and no CI step MAY lack a local equivalent.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 1.4 The standardized command surface](../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)
- **Checks:** CI-02, CI-03

### REQ-SH-035 — CI enforces the gate
On every pull request the CI pipeline MUST run the verbs that make up `check` and MUST fail the run when one of them fails.

- **Phase:** 1
- **Verification:** agent
- **Source:** [greenfield/README.md § 1.4 The standardized command surface](../greenfield/README.md#14-the-standardized-command-surface--seven-verbs)
- **Checks:** CI-04

### REQ-SH-057 — Workflow files linted

The repository's CI workflow files MUST be checked by a linter that understands the CI provider. The linter MUST
be runnable locally, through the command surface or a hook, as well as in CI.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 4.1 Workflows](../greenfield/README.md#41-workflows)
- **Checks:** CI-05

## Baselines and the ratchet

### REQ-BF-001 — Quality baseline
The repository MUST commit a baseline of its existing violations, as a baseline or suppression file or as a documented equivalent mechanism.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** BASE-01

### REQ-BF-002 — Violation count recorded
The repository MUST commit the current violation count of its quality tools as an explicit numeric budget.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** BASE-02

### REQ-BF-003 — No new violations
The repository MUST enforce a "no new violations" policy through a committed ratchet, such as a numeric budget or a baseline that a CI step compares against, that stops the violation count from growing.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** BASE-03

### REQ-BF-004 — Baseline is adequate
The repository's owner MUST declare that the baseline matches the debt it describes and that the violations it accepts are an acceptable risk.

- **Phase:** 1
- **Verification:** attested
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** none (attested)

### REQ-SH-036 — Coverage floor
A coverage threshold MUST be configured in the test runner's configuration.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 4.1 Workflows](../greenfield/README.md#41-workflows)
- **Checks:** BASE-04

## Constraints

### REQ-SH-037 — Allow and deny lists
The prohibitions section of the instruction file MUST be the repository's deny list: at least one of its entries MUST name a path that matches a file or directory of the repository.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** CON-01

### REQ-SH-038 — Test directories denied
The prohibitions section of the instruction file MUST name every test directory.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Overview.md § Principles](../docs/framework/overview.md#principles)
- **Checks:** CON-02

## Execution determinism

### REQ-SH-039 — Toolchain pinned
The repository MUST pin its toolchain with a version file, an engines or `requires-python` constraint, or a committed wrapper that fits each detected ecosystem.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § File Tree — What Gets Created](../greenfield/README.md#file-tree--what-gets-created)
- **Checks:** EXEC-01

### REQ-SH-040 — Lockfile tracked and consistent
Each package manager's lockfile MUST be tracked and MUST agree with its manifest.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** EXEC-02

### REQ-SH-041 — Non-interactive setup
The repository MUST provide a documented setup path that runs without interaction: a devcontainer, a compose file, a Dockerfile, a setup target or script, or an install command.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** EXEC-03

### REQ-SH-042 — Environment variables inventoried
Every environment variable that the source references MUST appear in the committed example file.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § File Tree — What Gets Created](../greenfield/README.md#file-tree--what-gets-created)
- **Checks:** EXEC-04

### REQ-SH-043 — Generated files marked or untracked
Generated and vendored files MUST be untracked or carry a generated-file header.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** EXEC-05

### REQ-SH-044 — One configuration per concern
Each of lint, format, test, types and security MUST have at most one authoritative configuration at the repository root.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** EXEC-07

### REQ-SH-058 — Tool versions visible to dependency automation

A tool version that a command, a workflow or a hook runs MUST be held in a manifest that dependency automation
reads, or in a file a configured custom manager reads. It MUST NOT be written only as a literal in the command.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** EXEC-08

## Tests

### REQ-SH-045 — Test verb and suite
The repository MUST define the `test` verb and MUST contain at least one test file.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 3.2 Testing Policies](../greenfield/README.md#32-testing-policies-enforced-via-agentsmd)
- **Checks:** TST-01

### REQ-SH-046 — Suite passes
The `test` verb MUST exit with status 0 on the checked-out revision.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 3.2 Testing Policies](../greenfield/README.md#32-testing-policies-enforced-via-agentsmd)
- **Checks:** TST-02

### REQ-SH-047 — No skipped tests
The test suite MUST NOT contain skipped, ignored or expected-failure tests.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 3.2 Testing Policies](../greenfield/README.md#32-testing-policies-enforced-via-agentsmd)
- **Checks:** TST-03

### REQ-SH-048 — Fast path documented
The repository's entry documents MUST show how to run a single test or a subset of the suite.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** TST-04

### REQ-SH-049 — Coverage reporting
The repository SHOULD configure coverage reporting for the test runner.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 3.1 vitest.config.ts](../greenfield/README.md#31-vitestconfigts--with-coverage)
- **Checks:** TST-05

### REQ-SH-050 — The suite is trustworthy
The repository's owner MUST declare that a green suite means the protected behaviour holds: the suite asserts what it claims to.

- **Phase:** 1
- **Verification:** attested
- **Source:** [Overview.md § Assumptions](../docs/framework/overview.md#assumptions)
- **Checks:** none (attested)

## Navigation

### REQ-SH-051 — Components declared
The repository's components MUST be declared in build manifests.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Overview.md § Applicability](../docs/framework/overview.md#applicability)
- **Checks:** NAV-01

### REQ-SH-052 — Entry points declared
Each ecosystem in the repository MUST declare an entry point.

- **Phase:** 1
- **Verification:** automated
- **Source:** [greenfield/README.md § 1.9 Core DI interface file + public entry point](../greenfield/README.md#19-core-di-interface-file--public-entry-point)
- **Checks:** NAV-02

### REQ-SH-053 — No structural red flags
The repository SHOULD NOT contain oversized files, catch-all directories, checked-in binaries or minified assets.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** NAV-03

## Security hygiene

### REQ-SH-054 — No tracked environment file
No `.env` file MAY be tracked, and ignore rules MUST cover the `.env` file shapes. Committed templates such as `.env.example` are exempt.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** SEC-01

### REQ-SH-055 — No credential-shaped strings
Tracked text files MUST NOT contain strings shaped like credentials.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Activities](../docs/framework/phased-approach.md#activities)
- **Checks:** SEC-02

### REQ-SH-056 — Ignore rules cover secret shapes
Ignore rules MUST cover the key, certificate and credential file shapes.

- **Phase:** 1
- **Verification:** automated
- **Source:** [Phased-Approach.md § Phase 1: Agentic Bootstrap](../docs/framework/phased-approach.md#phase-1-agentic-bootstrap-)
- **Checks:** SEC-03
