# How the Checks Map to the Framework

> **Audience:** Everyone
> **Source of truth:** [`catalogue.json`](../../catalogue.json) and [`spec/readiness-requirements.md`](../../../spec/readiness-requirements.md)
> **Status:** Live. The table below is generated from `catalogue.json`'s `req_ids` and each requirement's
> own `Source` field in [`readiness-requirements.md`](../../../spec/readiness-requirements.md); see
> [`spec/traceability.md`](../../../spec/traceability.md) for the check-to-requirement half on its own, and
> this page's note below for what keeps it true.

---

## Summary

| Item | Description |
|---|---|
| `check ID` | Catalogue entry, e.g. `CMD-02` |
| `requirement ID` | Spec entry, e.g. `REQ-SH-022` |
| `framework anchor` | The heading a requirement's `Source` field links, in the framework's documents |

---

## Following a check to the framework

A check reaches the framework through a requirement. Three steps, shown for `CMD-02`.

1. **Find the check in the catalogue.** In [`catalogue.json`](../../catalogue.json), the entry `CMD-02` ("`check` composes the read-only verbs", a BLOCKER) has `req_ids` of `["REQ-SH-022"]`.
2. **Read the requirement.** [REQ-SH-022](../../../spec/readiness-requirements.md#req-sh-022--check-composes-the-read-only-verbs) says "The `check` verb MUST run `format:check`, `typecheck` and `test`." Its `Checks` field names `CMD-02` back.
3. **Follow its `Source`.** The field links [greenfield-bootstrap/README.md § 1.4, The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs), the framework heading the rule comes from.

To go the other way, start from a framework heading, find the requirements whose `Source` links it, and read their `Checks` fields.

## Every check, generated

All 71 catalogue checks, each with its requirement(s) and the framework heading(s) the requirement's
`Source` field links. Generated 2026-10-19 from `catalogue.json`'s `req_ids` and
`readiness-requirements.md`'s `Source` fields — the same two steps as the worked example above, run once
per check rather than by hand. 14 checks are informational or an emitter and trace to no requirement
(`none`); `AGT-11` and `CI-04` carry a requirement but have no rubric yet (`spec/traceability.md#checks-that-do-not-yet-verify-their-requirement`
has the detail).

| Check | Title | Severity | Scored | Requirement(s) | Framework anchor(s) |
|---|---|---|---|---|---|
| `AGT-01` | Instruction file present, canonical, and non-trivial | BLOCKER | yes | [REQ-SH-005](../../../spec/readiness-requirements.md#req-sh-005--canonical-instruction-file) | [greenfield-bootstrap/README.md § 6.1 AGENTS.md](../../../greenfield-bootstrap/README.md#61-agentsmd) |
| `AGT-02` | Component coverage by instruction files | DEGRADER | yes | [REQ-SH-006](../../../spec/readiness-requirements.md#req-sh-006--component-instruction-files) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `AGT-03` | Documentation contract named | DEGRADER | yes | [REQ-SH-007](../../../spec/readiness-requirements.md#req-sh-007--documentation-contract-named) | [greenfield-bootstrap/README.md § 5.2 Templates & Guides](../../../greenfield-bootstrap/README.md#52-templates--guides) |
| `AGT-04` | Definition of done stated | DEGRADER | yes | [REQ-SH-008](../../../spec/readiness-requirements.md#req-sh-008--definition-of-done-stated) | [greenfield-bootstrap/README.md § 5.2 Templates & Guides](../../../greenfield-bootstrap/README.md#52-templates--guides) |
| `AGT-05` | Seven verbs named | DEGRADER | yes | [REQ-SH-009](../../../spec/readiness-requirements.md#req-sh-009--verbs-named) | [greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs) |
| `AGT-06` | Architectural boundaries declared | DEGRADER | yes | [REQ-SH-010](../../../spec/readiness-requirements.md#req-sh-010--architectural-boundaries-declared) | [greenfield-bootstrap/README.md § 6.1 AGENTS.md](../../../greenfield-bootstrap/README.md#61-agentsmd) |
| `AGT-07` | Do-not-do / deny rules present | DEGRADER | yes | [REQ-SH-011](../../../spec/readiness-requirements.md#req-sh-011--prohibitions-declared) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `AGT-08` | No competing instruction files, and the reach matrix is stated | DEGRADER | yes | [REQ-SH-012](../../../spec/readiness-requirements.md#req-sh-012--no-competing-instruction-files) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `AGT-09` | Branch and release boundary declared | DEGRADER | yes | [REQ-SH-013](../../../spec/readiness-requirements.md#req-sh-013--branch-and-release-boundary-declared) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `AGT-10` | Instruction indirection resolved | DEGRADER | yes | [REQ-SH-014](../../../spec/readiness-requirements.md#req-sh-014--instruction-indirection-resolved) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `AGT-11` | Instructions are specific and not inferable | DEGRADER | yes | [REQ-SH-015](../../../spec/readiness-requirements.md#req-sh-015--instructions-are-specific-and-not-inferable) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `BASE-01` | Baseline artifact exists | DEGRADER | yes | [REQ-BF-001](../../../spec/readiness-requirements.md#req-bf-001--quality-baseline) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `BASE-02` | Current violation counts measured | DEGRADER | yes | [REQ-BF-002](../../../spec/readiness-requirements.md#req-bf-002--violation-count-recorded) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `BASE-03` | No-new-violations mechanism | DEGRADER | yes | [REQ-BF-003](../../../spec/readiness-requirements.md#req-bf-003--no-new-violations) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `BASE-04` | Coverage floor configured | DEGRADER | yes | [REQ-SH-036](../../../spec/readiness-requirements.md#req-sh-036--coverage-floor) | [greenfield-bootstrap/README.md § 4.1 Workflows](../../../greenfield-bootstrap/README.md#41-workflows) |
| `CI-01` | Pipeline present, triggered on PRs | BLOCKER | yes | [REQ-SH-033](../../../spec/readiness-requirements.md#req-sh-033--pipeline-on-pull-requests) | [greenfield-bootstrap/README.md § 4.1 Workflows](../../../greenfield-bootstrap/README.md#41-workflows) |
| `CI-02` | Local↔CI parity | BLOCKER | yes | [REQ-SH-034](../../../spec/readiness-requirements.md#req-sh-034--ci-runs-the-verbs) | [greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs) |
| `CI-03` | CI-only steps flagged | DEGRADER | yes | [REQ-SH-034](../../../spec/readiness-requirements.md#req-sh-034--ci-runs-the-verbs) | [greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs) |
| `CI-04` | CI enforces the same gate as the local check | DEGRADER | yes | [REQ-SH-035](../../../spec/readiness-requirements.md#req-sh-035--ci-enforces-the-gate) | [greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs) |
| `CMD-01` | Seven verbs resolvable on one runner | BLOCKER | yes | [REQ-SH-021](../../../spec/readiness-requirements.md#req-sh-021--verbs-defined-on-one-runner) | [greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs) |
| `CMD-02` | check composes the read-only verbs | BLOCKER | yes | [REQ-SH-022](../../../spec/readiness-requirements.md#req-sh-022--check-composes-the-read-only-verbs) | [greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs) |
| `CMD-03` | No divergent second definition | DEGRADER | yes | [REQ-SH-023](../../../spec/readiness-requirements.md#req-sh-023--no-second-definition-of-the-gate) | [greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs) |
| `CMD-04` | Write verbs separated from read-only verbs | DEGRADER | yes | [REQ-SH-024](../../../spec/readiness-requirements.md#req-sh-024--read-only-verbs-do-not-write) | [greenfield-bootstrap/README.md § 1.4 The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs) |
| `CON-01` | Allow/deny artifact present | BLOCKER | yes | [REQ-SH-037](../../../spec/readiness-requirements.md#req-sh-037--allow-and-deny-lists) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `CON-02` | Test directories protected | BLOCKER | yes | [REQ-SH-038](../../../spec/readiness-requirements.md#req-sh-038--test-directories-denied) | [Overview.md § Principles](../../../shared/Overview.md#principles) |
| `CON-03` | artefacts/ excluded from index and agent reads | DEGRADER | yes | [REQ-SH-018](../../../spec/readiness-requirements.md#req-sh-018--scratch-and-tool-state-directories-ignored) | [greenfield-bootstrap/README.md § 6.2 Agent Scratchpad](../../../greenfield-bootstrap/README.md#62-agent-scratchpad--artefacts) |
| `CON-04` | Draft allow/deny emitted | COSMETIC | no | none | none |
| `DOC-01` | docs/ exists | DEGRADER | yes | [REQ-SH-016](../../../spec/readiness-requirements.md#req-sh-016--documentation-directory) | [greenfield-bootstrap/README.md § 5.1 Diátaxis Framework](../../../greenfield-bootstrap/README.md#51-diátaxis-framework) |
| `DOC-02` | docs/STYLE_GUIDE.md exists | DEGRADER | yes | [REQ-SH-017](../../../spec/readiness-requirements.md#req-sh-017--style-guide) | [greenfield-bootstrap/README.md § 5.2 Templates & Guides](../../../greenfield-bootstrap/README.md#52-templates--guides) |
| `DOC-03` | artefacts/ exists and is ignored | DEGRADER | yes | [REQ-SH-018](../../../spec/readiness-requirements.md#req-sh-018--scratch-and-tool-state-directories-ignored) | [greenfield-bootstrap/README.md § 6.2 Agent Scratchpad](../../../greenfield-bootstrap/README.md#62-agent-scratchpad--artefacts) |
| `DOC-04` | ADR directory and index | COSMETIC | yes | [REQ-SH-019](../../../spec/readiness-requirements.md#req-sh-019--adr-directory-and-index) | [greenfield-bootstrap/README.md § 5.2 Templates & Guides](../../../greenfield-bootstrap/README.md#52-templates--guides) |
| `EXEC-01` | Toolchain pinned / wrapper committed | BLOCKER | yes | [REQ-SH-039](../../../spec/readiness-requirements.md#req-sh-039--toolchain-pinned) | [greenfield-bootstrap/README.md § File Tree — What Gets Created](../../../greenfield-bootstrap/README.md#file-tree--what-gets-created) |
| `EXEC-02` | Lockfile committed and consistent | BLOCKER | yes | [REQ-SH-040](../../../spec/readiness-requirements.md#req-sh-040--lockfile-tracked-and-consistent) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `EXEC-03` | Non-interactive setup path | BLOCKER | yes | [REQ-SH-041](../../../spec/readiness-requirements.md#req-sh-041--non-interactive-setup) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `EXEC-04` | Env-var inventory complete | BLOCKER | yes | [REQ-SH-042](../../../spec/readiness-requirements.md#req-sh-042--environment-variables-inventoried) | [greenfield-bootstrap/README.md § File Tree — What Gets Created](../../../greenfield-bootstrap/README.md#file-tree--what-gets-created) |
| `EXEC-05` | No generated artifacts committed in-tree | DEGRADER | yes | [REQ-SH-043](../../../spec/readiness-requirements.md#req-sh-043--generated-files-marked-or-untracked) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `EXEC-06` | Documented commands resolve | DEGRADER | yes | [REQ-SH-025](../../../spec/readiness-requirements.md#req-sh-025--documented-commands-resolve) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `EXEC-07` | No competing configs for one concern | DEGRADER | yes | [REQ-SH-044](../../../spec/readiness-requirements.md#req-sh-044--one-configuration-per-concern) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `HYG-01` | README present and non-placeholder | COSMETIC | no | none | none |
| `HYG-02` | CODEOWNERS present | COSMETIC | no | none | none |
| `HYG-03` | Pull-request template present | COSMETIC | no | none | none |
| `HYG-04` | Issue templates present | COSMETIC | no | none | none |
| `HYG-05` | CONTRIBUTING present | COSMETIC | no | none | none |
| `HYG-06` | SECURITY present | COSMETIC | no | none | none |
| `HYG-07` | CHANGELOG present and recent | COSMETIC | no | none | none |
| `HYG-08` | Release process documented | COSMETIC | no | none | none |
| `HYG-09` | Dependency update automation configured | COSMETIC | no | none | none |
| `HYG-10` | License present | COSMETIC | no | none | none |
| `HYG-11` | Branch protection declared as code | COSMETIC | no | none | none |
| `IDX-01` | codebase-memory-mcp registered for this repository | BLOCKER | yes | [REQ-SH-001](../../../spec/readiness-requirements.md#req-sh-001--index-server-registered) | [greenfield-bootstrap/README.md § 6.4 Codebase-Memory-MCP Registration](../../../greenfield-bootstrap/README.md#64-codebase-memory-mcp-registration) |
| `IDX-02` | An index exists for this checkout | BLOCKER | yes | [REQ-SH-002](../../../spec/readiness-requirements.md#req-sh-002--index-exists) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `IDX-03` | Index freshness | DEGRADER | yes | [REQ-SH-003](../../../spec/readiness-requirements.md#req-sh-003--index-current) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `NAV-01` | Declared component boundaries | DEGRADER | yes | [REQ-SH-051](../../../spec/readiness-requirements.md#req-sh-051--components-declared) | [Overview.md § Applicability](../../../shared/Overview.md#applicability) |
| `NAV-02` | Obvious entry points | DEGRADER | yes | [REQ-SH-052](../../../spec/readiness-requirements.md#req-sh-052--entry-points-declared) | [greenfield-bootstrap/README.md § 1.9 Core DI interface file + public entry point](../../../greenfield-bootstrap/README.md#19-core-di-interface-file--public-entry-point) |
| `NAV-03` | Structural red flags | COSMETIC | yes | [REQ-SH-053](../../../spec/readiness-requirements.md#req-sh-053--no-structural-red-flags) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `NAV-04` | Architecture orientation artifact | COSMETIC | no | none | none |
| `NAV-05` | Public-symbol documentation coverage | COSMETIC | no | none | none |
| `SEC-01` | .env untracked and ignored | BLOCKER | yes | [REQ-SH-054](../../../spec/readiness-requirements.md#req-sh-054--no-tracked-environment-file) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `SEC-02` | No key-shaped strings in tracked files | BLOCKER | yes | [REQ-SH-055](../../../spec/readiness-requirements.md#req-sh-055--no-credential-shaped-strings) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `SEC-03` | Ignore patterns cover secret shapes | DEGRADER | yes | [REQ-SH-056](../../../spec/readiness-requirements.md#req-sh-056--ignore-rules-cover-secret-shapes) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `TOOL-01` | Formatter configured | DEGRADER | yes | [REQ-SH-027](../../../spec/readiness-requirements.md#req-sh-027--formatter) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `TOOL-02` | Linter configured | DEGRADER | yes | [REQ-SH-028](../../../spec/readiness-requirements.md#req-sh-028--linter) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `TOOL-03` | Type checker configured | DEGRADER | yes | [REQ-SH-029](../../../spec/readiness-requirements.md#req-sh-029--strict-type-checking) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `TOOL-04` | Dependency / security scan verb | DEGRADER | yes | [REQ-SH-030](../../../spec/readiness-requirements.md#req-sh-030--dependency-vulnerability-scan) | [Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities) |
| `TOOL-05` | Local hook chain active | DEGRADER | yes | [REQ-SH-031](../../../spec/readiness-requirements.md#req-sh-031--local-hook-chain) | [greenfield-bootstrap/README.md § 2.3 Git Hooks](../../../greenfield-bootstrap/README.md#23-git-hooks--husky--lint-staged--commitlint) |
| `TOOL-06` | Commit convention enforced | COSMETIC | yes | [REQ-SH-032](../../../spec/readiness-requirements.md#req-sh-032--commit-convention-enforced) | [greenfield-bootstrap/README.md § 2.3 Git Hooks](../../../greenfield-bootstrap/README.md#23-git-hooks--husky--lint-staged--commitlint) |
| `TST-01` | Test verb exists, suite non-empty | BLOCKER | yes | [REQ-SH-045](../../../spec/readiness-requirements.md#req-sh-045--test-verb-and-suite) | [greenfield-bootstrap/README.md § 3.2 Testing Policies](../../../greenfield-bootstrap/README.md#32-testing-policies-enforced-via-agentsmd) |
| `TST-02` | Suite status known | DEGRADER | yes | [REQ-SH-046](../../../spec/readiness-requirements.md#req-sh-046--suite-passes) | [greenfield-bootstrap/README.md § 3.2 Testing Policies](../../../greenfield-bootstrap/README.md#32-testing-policies-enforced-via-agentsmd) |
| `TST-03` | Skip / xfail census | DEGRADER | yes | [REQ-SH-047](../../../spec/readiness-requirements.md#req-sh-047--no-skipped-tests) | [greenfield-bootstrap/README.md § 3.2 Testing Policies](../../../greenfield-bootstrap/README.md#32-testing-policies-enforced-via-agentsmd) |
| `TST-04` | Fast path documented | DEGRADER | yes | [REQ-SH-048](../../../spec/readiness-requirements.md#req-sh-048--fast-path-documented) | [Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-) |
| `TST-05` | Coverage configuration present | COSMETIC | yes | [REQ-SH-049](../../../spec/readiness-requirements.md#req-sh-049--coverage-reporting) | [greenfield-bootstrap/README.md § 3.1 vitest.config.ts](../../../greenfield-bootstrap/README.md#31-vitestconfigts--with-coverage) |

71 checks total.

## Where the relation is held

| File | Holds | Kept true by |
|---|---|---|
| [`catalogue.json`](../../catalogue.json) | Each check's `req_ids` | [`test_catalogue.py`](../../tools/tests/test_catalogue.py) |
| [`readiness-requirements.md`](../../../spec/readiness-requirements.md) | Each requirement's `Checks` and `Source` | The same test, for `Checks` |
| [`traceability.md`](../../../spec/traceability.md) | The check-to-requirement table, for reading | The same test |
| This page's "Every check, generated" table | The check-to-framework-anchor table above, for reading | Nothing yet — generated by hand from the two files above on 2026-10-19; re-generate it after a catalogue or requirements change, the same gap `traceability.md` itself names for its own table |

A requirement can be derived, meaning the framework does not say it in so many words. [`traceability.md`](../../../spec/traceability.md#derived-requirements) lists those.
