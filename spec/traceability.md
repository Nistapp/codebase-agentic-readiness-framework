# Traceability

Maps the checks of the audit engine to the [requirements](readiness-requirements.md) they verify, and the requirements back to the checks. The `Checks` field of a requirement is authoritative. This page is its inverse, built from those fields on 2026-10-09; no test keeps the two in step yet.

Check IDs and severities are those printed by `python3 -m audit --list-checks`.

## Checks to requirements

69 checks. 54 scored checks and the blocked `CON-01` trace to at least one requirement. The other 14 are informational or an emitter and trace to none.

| Check | Title | Severity | Scored | Requirements |
|---|---|---|---|---|
| `IDX-01` | codebase-memory-mcp registered for this repository | BLOCKER | yes | [REQ-SH-001](readiness-requirements.md#req-sh-001--index-server-registered) |
| `IDX-02` | An index exists for this checkout | BLOCKER | yes | [REQ-SH-002](readiness-requirements.md#req-sh-002--index-exists) |
| `IDX-03` | Index freshness | DEGRADER | yes | [REQ-SH-003](readiness-requirements.md#req-sh-003--index-current) |
| `AGT-01` | Instruction file present, canonical, and non-trivial | BLOCKER | yes | [REQ-SH-005](readiness-requirements.md#req-sh-005--canonical-instruction-file) |
| `AGT-02` | Component coverage by instruction files | DEGRADER | yes | [REQ-SH-006](readiness-requirements.md#req-sh-006--component-instruction-files) |
| `AGT-03` | Documentation contract named | DEGRADER | yes | [REQ-SH-007](readiness-requirements.md#req-sh-007--documentation-contract-named) |
| `AGT-04` | Definition of done stated | DEGRADER | yes | [REQ-SH-008](readiness-requirements.md#req-sh-008--definition-of-done-stated) |
| `AGT-05` | Six verbs named | DEGRADER | yes | [REQ-SH-009](readiness-requirements.md#req-sh-009--verbs-named) |
| `AGT-06` | Architectural boundaries declared | DEGRADER | yes | [REQ-SH-010](readiness-requirements.md#req-sh-010--architectural-boundaries-declared) |
| `AGT-07` | Do-not-do / deny rules present | DEGRADER | yes | [REQ-SH-011](readiness-requirements.md#req-sh-011--prohibitions-declared) |
| `AGT-08` | No competing instruction files, and the reach matrix is stated | DEGRADER | yes | [REQ-SH-012](readiness-requirements.md#req-sh-012--no-competing-instruction-files) |
| `AGT-09` | Branch and release boundary declared | DEGRADER | yes | [REQ-SH-013](readiness-requirements.md#req-sh-013--branch-and-release-boundary-declared) |
| `AGT-10` | Instruction indirection resolved | DEGRADER | yes | [REQ-SH-014](readiness-requirements.md#req-sh-014--instruction-indirection-resolved) |
| `DOC-01` | docs/ exists | DEGRADER | yes | [REQ-SH-016](readiness-requirements.md#req-sh-016--documentation-directory) |
| `DOC-02` | docs/STYLE_GUIDE.md exists | DEGRADER | yes | [REQ-SH-017](readiness-requirements.md#req-sh-017--style-guide) |
| `DOC-03` | artefacts/ exists and is ignored | DEGRADER | yes | [REQ-SH-018](readiness-requirements.md#req-sh-018--scratch-and-tool-state-directories-ignored) |
| `DOC-04` | ADR directory and index | COSMETIC | yes | [REQ-SH-019](readiness-requirements.md#req-sh-019--adr-directory-and-index) |
| `CMD-01` | Six verbs resolvable on one runner | BLOCKER | yes | [REQ-SH-021](readiness-requirements.md#req-sh-021--verbs-defined-on-one-runner) |
| `CMD-02` | check composes the read-only verbs | BLOCKER | yes | [REQ-SH-022](readiness-requirements.md#req-sh-022--check-composes-the-read-only-verbs) |
| `CMD-03` | No divergent second definition | DEGRADER | yes | [REQ-SH-023](readiness-requirements.md#req-sh-023--no-second-definition-of-the-gate) |
| `CMD-04` | Write verbs separated from read-only verbs | DEGRADER | yes | [REQ-SH-024](readiness-requirements.md#req-sh-024--read-only-verbs-do-not-write) |
| `TOOL-01` | Formatter configured | DEGRADER | yes | [REQ-SH-027](readiness-requirements.md#req-sh-027--formatter) |
| `TOOL-02` | Linter configured | DEGRADER | yes | [REQ-SH-028](readiness-requirements.md#req-sh-028--linter) |
| `TOOL-03` | Type checker configured | DEGRADER | yes | [REQ-SH-029](readiness-requirements.md#req-sh-029--strict-type-checking) |
| `TOOL-04` | Dependency / security scan verb | DEGRADER | yes | [REQ-SH-030](readiness-requirements.md#req-sh-030--dependency-vulnerability-scan) |
| `TOOL-05` | Local hook chain active | DEGRADER | yes | [REQ-SH-031](readiness-requirements.md#req-sh-031--local-hook-chain) |
| `TOOL-06` | Commit convention enforced | COSMETIC | yes | [REQ-SH-032](readiness-requirements.md#req-sh-032--commit-convention-enforced) |
| `CI-01` | Pipeline present, triggered on PRs | BLOCKER | yes | [REQ-SH-033](readiness-requirements.md#req-sh-033--pipeline-on-pull-requests) |
| `CI-02` | Local↔CI parity | BLOCKER | yes | [REQ-SH-034](readiness-requirements.md#req-sh-034--ci-runs-the-verbs) |
| `CI-03` | CI-only steps flagged | DEGRADER | yes | [REQ-SH-034](readiness-requirements.md#req-sh-034--ci-runs-the-verbs) |
| `BASE-01` | Baseline artifact exists | DEGRADER | yes | [REQ-BF-001](readiness-requirements.md#req-bf-001--quality-baseline) |
| `BASE-02` | Current violation counts measured | DEGRADER | yes | [REQ-BF-002](readiness-requirements.md#req-bf-002--violation-count-recorded) |
| `BASE-03` | No-new-violations mechanism | DEGRADER | yes | [REQ-BF-003](readiness-requirements.md#req-bf-003--no-new-violations) |
| `BASE-04` | Coverage floor configured | DEGRADER | yes | [REQ-SH-036](readiness-requirements.md#req-sh-036--coverage-floor) |
| `CON-01` | Allow/deny artifact present | BLOCKER | no (blocked) | [REQ-SH-037](readiness-requirements.md#req-sh-037--allow-and-deny-lists) |
| `CON-02` | Test directories protected | BLOCKER | yes | [REQ-SH-038](readiness-requirements.md#req-sh-038--test-directories-denied) |
| `CON-03` | artefacts/ excluded from index and agent reads | DEGRADER | yes | [REQ-SH-018](readiness-requirements.md#req-sh-018--scratch-and-tool-state-directories-ignored) |
| `CON-04` | Draft allow/deny emitted | COSMETIC | no (emitter) | none: an emitter, not a check |
| `EXEC-01` | Toolchain pinned / wrapper committed | BLOCKER | yes | [REQ-SH-039](readiness-requirements.md#req-sh-039--toolchain-pinned) |
| `EXEC-02` | Lockfile committed and consistent | BLOCKER | yes | [REQ-SH-040](readiness-requirements.md#req-sh-040--lockfile-tracked-and-consistent) |
| `EXEC-03` | Non-interactive setup path | BLOCKER | yes | [REQ-SH-041](readiness-requirements.md#req-sh-041--non-interactive-setup) |
| `EXEC-04` | Env-var inventory complete | BLOCKER | yes | [REQ-SH-042](readiness-requirements.md#req-sh-042--environment-variables-inventoried) |
| `EXEC-05` | No generated artifacts committed in-tree | DEGRADER | yes | [REQ-SH-043](readiness-requirements.md#req-sh-043--generated-files-marked-or-untracked) |
| `EXEC-06` | Documented commands resolve | DEGRADER | yes | [REQ-SH-025](readiness-requirements.md#req-sh-025--documented-commands-resolve) |
| `EXEC-07` | No competing configs for one concern | DEGRADER | yes | [REQ-SH-044](readiness-requirements.md#req-sh-044--one-configuration-per-concern) |
| `TST-01` | Test verb exists, suite non-empty | BLOCKER | yes | [REQ-SH-045](readiness-requirements.md#req-sh-045--test-verb-and-suite) |
| `TST-02` | Suite status known | DEGRADER | yes | [REQ-SH-046](readiness-requirements.md#req-sh-046--suite-passes) |
| `TST-03` | Skip / xfail census | DEGRADER | yes | [REQ-SH-047](readiness-requirements.md#req-sh-047--no-skipped-tests) |
| `TST-04` | Fast path documented | DEGRADER | yes | [REQ-SH-048](readiness-requirements.md#req-sh-048--fast-path-documented) |
| `TST-05` | Coverage configuration present | COSMETIC | yes | [REQ-SH-049](readiness-requirements.md#req-sh-049--coverage-reporting) |
| `NAV-01` | Declared component boundaries | DEGRADER | yes | [REQ-SH-051](readiness-requirements.md#req-sh-051--components-declared) |
| `NAV-02` | Obvious entry points | DEGRADER | yes | [REQ-SH-052](readiness-requirements.md#req-sh-052--entry-points-declared) |
| `NAV-03` | Structural red flags | COSMETIC | yes | [REQ-SH-053](readiness-requirements.md#req-sh-053--no-structural-red-flags) |
| `NAV-04` | Architecture orientation artifact | COSMETIC | no (informational) | none: informational, reported and never scored |
| `NAV-05` | Public-symbol documentation coverage | COSMETIC | no (informational) | none: informational, reported and never scored |
| `SEC-01` | .env untracked and ignored | BLOCKER | yes | [REQ-SH-054](readiness-requirements.md#req-sh-054--no-tracked-environment-file) |
| `SEC-02` | No key-shaped strings in tracked files | BLOCKER | yes | [REQ-SH-055](readiness-requirements.md#req-sh-055--no-credential-shaped-strings) |
| `SEC-03` | Ignore patterns cover secret shapes | DEGRADER | yes | [REQ-SH-056](readiness-requirements.md#req-sh-056--ignore-rules-cover-secret-shapes) |
| `HYG-01` | README present and non-placeholder | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-02` | CODEOWNERS present | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-03` | Pull-request template present | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-04` | Issue templates present | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-05` | CONTRIBUTING present | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-06` | SECURITY present | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-07` | CHANGELOG present and recent | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-08` | Release process documented | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-09` | Dependency update automation configured | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-10` | License present | COSMETIC | no (informational) | none: informational, reported and never scored |
| `HYG-11` | Branch protection declared as code | COSMETIC | no (informational) | none: informational, reported and never scored |

## Requirements without a check

7 of the 60 requirements have no check. The five attested ones are the engine's unattested list: the report shows them as unattested and they earn no credit.

| Requirement | Title | Verification | Why |
|---|---|---|---|
| [REQ-SH-004](readiness-requirements.md#req-sh-004--agents-explore-through-the-index) | Agents explore through the index | attested | attested; the engine's unattested item `index-in-use` |
| [REQ-SH-015](readiness-requirements.md#req-sh-015--instructions-are-specific-and-not-inferable) | Instructions are specific and not inferable | agent | agent-verified; no check yet |
| [REQ-SH-020](readiness-requirements.md#req-sh-020--documentation-is-accurate) | Documentation is accurate | attested | attested; the engine's unattested item `doc-accuracy` |
| [REQ-SH-026](readiness-requirements.md#req-sh-026--the-gate-is-honoured) | The gate is honoured | attested | attested; the engine's unattested item `gate-honoured` |
| [REQ-SH-035](readiness-requirements.md#req-sh-035--ci-enforces-the-gate) | CI enforces the gate | agent | agent-verified; no check yet |
| [REQ-BF-004](readiness-requirements.md#req-bf-004--baseline-is-adequate) | Baseline is adequate | attested | attested; the engine's unattested item `baseline-adequacy` |
| [REQ-SH-050](readiness-requirements.md#req-sh-050--the-suite-is-trustworthy) | The suite is trustworthy | attested | attested; the engine's unattested item `suite-trustworthiness` |

## Derived requirements

20 of the 60 requirements go beyond what the framework documents say. They follow from the Phase 1 objective, "Make the repository executable, discoverable, and safe for agent interaction", or they come from the audit engine's rule packs. Each is still tied to the nearest framework heading. These are the requirements to review first.

| Requirement | Title | What the framework does not say |
|---|---|---|
| [REQ-SH-003](readiness-requirements.md#req-sh-003--index-current) | Index current | The framework says to index the code, not that the index matches the checked-out revision. |
| [REQ-SH-012](readiness-requirements.md#req-sh-012--no-competing-instruction-files) | No competing instruction files | The framework says to create `AGENTS.md`, not how to treat other harnesses' instruction files. |
| [REQ-SH-013](readiness-requirements.md#req-sh-013--branch-and-release-boundary-declared) | Branch and release boundary declared | The framework does not ask the instruction file to state the branch and release boundary. |
| [REQ-SH-014](readiness-requirements.md#req-sh-014--instruction-indirection-resolved) | Instruction indirection resolved | The framework does not discuss an entry file that defers to another file. |
| [REQ-SH-015](readiness-requirements.md#req-sh-015--instructions-are-specific-and-not-inferable) | Instructions are specific and not inferable | The framework says what the instruction file covers, not that its content must be specific and not inferable. |
| [REQ-SH-025](readiness-requirements.md#req-sh-025--documented-commands-resolve) | Documented commands resolve | Follows from 'run a known verification command', which the framework names as the result of Phase 1. |
| [REQ-SH-026](readiness-requirements.md#req-sh-026--the-gate-is-honoured) | The gate is honoured | The framework says a gate with no local equivalent cannot be honoured; whether the team honours it is not stated. |
| [REQ-SH-035](readiness-requirements.md#req-sh-035--ci-enforces-the-gate) | CI enforces the gate | The framework says CI runs the same scripts, not that CI must fail the run when one fails. |
| [REQ-BF-004](readiness-requirements.md#req-bf-004--baseline-is-adequate) | Baseline is adequate | The framework asks for baselines, not for the owner to declare them adequate. |
| [REQ-SH-038](readiness-requirements.md#req-sh-038--test-directories-denied) | Test directories denied | The framework says agents must not weaken tests only in its Phase 5 row. |
| [REQ-SH-040](readiness-requirements.md#req-sh-040--lockfile-tracked-and-consistent) | Lockfile tracked and consistent | Follows from 'executable'; the framework names no lockfile rule. |
| [REQ-SH-041](readiness-requirements.md#req-sh-041--non-interactive-setup) | Non-interactive setup | Follows from 'executable'; the framework names no setup path. |
| [REQ-SH-043](readiness-requirements.md#req-sh-043--generated-files-marked-or-untracked) | Generated files marked or untracked | Follows from 'executable'; the framework names no rule for generated files. |
| [REQ-SH-044](readiness-requirements.md#req-sh-044--one-configuration-per-concern) | One configuration per concern | Follows from 'executable'; the framework names no rule on competing configurations. |
| [REQ-SH-048](readiness-requirements.md#req-sh-048--fast-path-documented) | Fast path documented | Follows from 'run a known verification command'; the framework names no fast path. |
| [REQ-SH-050](readiness-requirements.md#req-sh-050--the-suite-is-trustworthy) | The suite is trustworthy | The framework's assumptions say tests protect behaviour, not that the owner declares the suite trustworthy. |
| [REQ-SH-053](readiness-requirements.md#req-sh-053--no-structural-red-flags) | No structural red flags | Follows from 'discoverable'; the framework names no structural red flags. |
| [REQ-SH-054](readiness-requirements.md#req-sh-054--no-tracked-environment-file) | No tracked environment file | The greenfield file tree shows a committed `.env.example`; the framework has no rule that a `.env` file stays untracked. |
| [REQ-SH-055](readiness-requirements.md#req-sh-055--no-credential-shaped-strings) | No credential-shaped strings | The framework asks for basic security scanning, not specifically for a scan for credential-shaped strings. |
| [REQ-SH-056](readiness-requirements.md#req-sh-056--ignore-rules-cover-secret-shapes) | Ignore rules cover secret shapes | Follows from 'safe for agent interaction'; the framework names no rule on ignore patterns for secrets. |

## Runners the engine reads

The spelling table in [command-surface.md](command-surface.md) covers every runner manifest the engine reads for verbs.

| Manifest the engine reads | Row in the spelling table |
|---|---|
| `package.json` (`scripts`) | npm scripts |
| `Makefile` | Make |
| `Taskfile.yml`, `Taskfile.yaml` | Taskfile |
| `pyproject.toml` (`[tool.<runner>.tasks]`) | pyproject task runners |
| `build.gradle`, `build.gradle.kts` | Gradle |
| `pom.xml` | Maven |
| `gradlew`, `mvnw` | the wrappers of Gradle and Maven, named in the same rows |
