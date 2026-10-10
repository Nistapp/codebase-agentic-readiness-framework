# Agentic readiness audit: example-service

Repository `example-service` at commit `deadbeefdead` on branch `main` (clean working tree). Finalised `2026-10-10T09:42:07+00:00`.

## Readiness summary

- **Phase-1 score: 0.33**, over 12 scored checks
- **4 blockers remaining: 4 FAIL**
- **Unattested:** 5 requirements that no check settles, listed below

1 of the 12 scored checks is UNKNOWN. An UNKNOWN check earns no credit, so the score understates what is true of the repository and does not certify it. No agent finding is waiting for a person's decision.

The score is the weighted share of the scored checks that the repository meets. The weights are BLOCKER 3, DEGRADER 2, COSMETIC 1; PASS earns full credit, PARTIAL half, and FAIL and UNKNOWN none. The framework sets no pass mark, and a score says nothing about whether agents will write correct code.

### Unattested requirements

A person's review or the owner's declaration verifies these requirements, so no check gives them a verdict, and they are outside the score. One leaves this list only when a person records an outcome or the owner declares it.

| Requirement | Method | Property | Why |
|---|---|---|---|
| `REQ-SH-004` | attested | `index-in-use` | Whether the codebase index is actually used during agent work. |
| `REQ-BF-004` | attested | `baseline-adequacy` | Whether the committed baseline or budget is adequate. |
| `REQ-SH-050` | attested | `suite-trustworthiness` | Whether the passing test suite actually catches regressions. |
| `REQ-SH-020` | attested | `doc-accuracy` | Whether the documentation matches the code it describes. |
| `REQ-SH-026` | attested | `gate-honoured` | Whether the gate is actually run and honoured before merge. |

## Blockers remaining

| Check | Title | Verdict | Summary |
|---|---|---|---|
| `CMD-01` | Seven verbs resolvable on one runner | FAIL | format -> package.json; format:check -> missing; lint -> package.json; typecheck -> missing; test -> package.json; check -> missing; security -> missing |
| `CMD-02` | check composes the read-only verbs | FAIL | the check verb is not defined on any runner |
| `EXEC-01` | Toolchain pinned / wrapper committed | FAIL | unpinned: node |
| `SEC-02` | No key-shaped strings in tracked files | FAIL | 3 credential-shaped line(s) across 2 file(s) in tracked text files |

## Overrides of the engine's verdicts

Where this report's verdict differs from the engine's, the agent's counter-evidence is under the check, in the details below.

| Check | Engine's verdict | This report's verdict | Reason |
|---|---|---|---|
| `TOOL-03` | PARTIAL | PASS | tsconfig.json extends tsconfig.base.json, which sets strict: true; the engine reads only the leaf file. |

## Checks

12 checks: 3 PASS, 2 PARTIAL, 6 FAIL, 1 UNKNOWN.

- **PASS**: The requirement is met. Full credit.
- **PARTIAL**: Part of the requirement is met. Half credit.
- **FAIL**: The requirement is not met. No credit.
- **UNKNOWN**: The evidence could not be gathered. No credit, and never read as a pass.
- **NOT_APPLICABLE**: The check does not apply to this repository. It is outside the score.
- **BLOCKER**: Agent work is impossible, unsafe or unverifiable. Fix before onboarding agents.
- **DEGRADER**: Agent work is possible but unreliable or wasteful.
- **COSMETIC**: Hygiene. Fix when convenient.

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `IDX-01` | codebase-memory-mcp registered for this repository | BLOCKER | automated | yes | PASS | PASS | codebase-memory-mcp registered in: ~/.config/opencode/opencode.jsonc (user) |
| `AGT-07` | Do-not-do / deny rules present | DEGRADER | automated | yes | FAIL | FAIL | no prohibitions section |
| `AGT-08` | No competing instruction files, and the reach matrix is stated | DEGRADER | automated | yes | PARTIAL | PARTIAL | 20/28 harnesses reached |
| `AGT-11` | Instructions are specific and not inferable | DEGRADER | agent | yes | PARTIAL | — | AGENTS.md states the non-obvious branch and release rules, but most other lines restate what package.json already shows. |
| `CMD-01` | Seven verbs resolvable on one runner | BLOCKER | automated | yes | FAIL | FAIL | format -> package.json; format:check -> missing; lint -> package.json; typecheck -> missing; test -> package.json; check -> missing; security -> missing |
| `CMD-02` | check composes the read-only verbs | BLOCKER | automated | yes | FAIL | FAIL | the check verb is not defined on any runner |
| `TOOL-03` | Type checker configured | DEGRADER | automated | yes | PASS | PARTIAL | type checker configured and strict: tsconfig.base.json |
| `CI-01` | Pipeline present, triggered on PRs | BLOCKER | automated | yes | PASS | PASS | workflow file(s): .github/workflows/ci.yml, triggered on pull_request |
| `CI-04` | CI enforces the same gate as the local check | DEGRADER | agent | yes | FAIL | — | We did not find any evidence that the CI workflow runs the repository's check verb or fails the run when it fails. |
| `EXEC-01` | Toolchain pinned / wrapper committed | BLOCKER | automated | yes | FAIL | FAIL | unpinned: node |
| `SEC-02` | No key-shaped strings in tracked files | BLOCKER | automated | yes | FAIL | FAIL | 3 credential-shaped line(s) across 2 file(s) in tracked text files |
| `TST-02` | Suite status known | DEGRADER | automated | yes | UNKNOWN | UNKNOWN | probe not run: probes disabled (pass --run-gates) |

## Check details

Each check below is one that is not met, was overridden, was judged by the agent, or raised a finding, in order of severity. A check that passed and was settled by a tool has only its row in the table above; its evidence is in the JSON report.

### BLOCKER checks

#### CMD-01: Seven verbs resolvable on one runner

**FAIL** · BLOCKER · automated · scored

format -> package.json; format:check -> missing; lint -> package.json; typecheck -> missing; test -> package.json; check -> missing; security -> missing

**Evidence**

- `package.json` · captured by tool `python-agentic-audit` 0.1.0

The engine's payload for this check, of kind `verb_surface`, is in the JSON report.

**F-001** · BLOCKER · key `CMD-01`

An agent cannot run the standardized command surface literally because 4 of 7 framework verbs are not defined on any runner (format:check, typecheck, check, security).

**Fix.** Define every verb as a script so an agent never has to invent a command.

Playbook `define-command-surface` · Effort S · Touches `package.json`

**Confirmed.** Decided by the person, on this finding alone.

Evidence: the same as under the check.

#### CMD-02: check composes the read-only verbs

**FAIL** · BLOCKER · automated · scored

the check verb is not defined on any runner

**Evidence**

- `package.json` · captured by tool `python-agentic-audit` 0.1.0

**F-002** · BLOCKER · key `CMD-02`

An agent cannot run one command that proves a change is safe because the check verb is not defined on any runner.

**Fix.** Define check as the composition of the read-only verbs.

Playbook `define-command-surface` · Effort S · Depends on `F-001` · Touches `package.json`

**Confirmed.** Decided by the person, on this finding alone.

Evidence: the same as under the check.

#### EXEC-01: Toolchain pinned / wrapper committed

**FAIL** · BLOCKER · automated · scored

unpinned: node

**Evidence**

- `package.json` · captured by tool `python-agentic-audit` 0.1.0

**F-003** · BLOCKER · key `EXEC-01`

An agent cannot reproduce the toolchain because node is not pinned by a version file, an engines constraint or a wrapper.

**Fix.** Pin Node 22 in .nvmrc.

Playbook `pin-execution-environment` · Effort S · Touches `.nvmrc`

**Edited.** Decided by the person, on this finding alone. Note: The owner pins Node 22 in .nvmrc and leaves the engines field alone.

Evidence: the same as under the check.

#### SEC-02: No key-shaped strings in tracked files

**FAIL** · BLOCKER · automated · scored

3 credential-shaped line(s) across 2 file(s) in tracked text files

**Evidence**

- `src/config/constants.ts:12` — credential-shaped string · captured by tool `python-agentic-audit` 0.1.0
- `src/services/__tests__/auth.test.ts:37` — credential-shaped string · captured by tool `python-agentic-audit` 0.1.0
- `src/services/__tests__/auth.test.ts:58` — credential-shaped string · captured by tool `python-agentic-audit` 0.1.0

The engine's payload for this check, of kind `credential_matrix`, is in the JSON report.

**F-004** · BLOCKER · key `SEC-02:src/config/constants.ts`

An agent cannot keep credentials out of the repository and its history because src/config/constants.ts contains 1 credential-shaped line(s).

**Fix.** Remove the value from the file and its history, load it from the environment, and rotate the credential.

Playbook `env-inventory-and-secrets` · Effort M · Touches `src/config/constants.ts`

**Confirmed.** Decided by the person, on this finding alone.

Evidence for F-004:

- `src/config/constants.ts:12` — credential-shaped string · captured by tool `python-agentic-audit` 0.1.0

**F-005** · BLOCKER · key `SEC-02:src/services/__tests__/auth.test.ts`

An agent cannot keep credentials out of the repository and its history because src/services/\_\_tests\_\_/auth.test.ts contains 2 credential-shaped line(s).

**Fix.** Remove the value from the file and its history, load it from the environment, and rotate the credential.

**Rejected.** Decided by the person, on this finding alone. Note: Placeholder values in a unit test, not credentials.

Evidence for F-005:

- `src/services/__tests__/auth.test.ts:37` — credential-shaped string · captured by tool `python-agentic-audit` 0.1.0
- `src/services/__tests__/auth.test.ts:58` — credential-shaped string · captured by tool `python-agentic-audit` 0.1.0

### DEGRADER checks

#### AGT-07: Do-not-do / deny rules present

**FAIL** · DEGRADER · automated · scored

no prohibitions section

**Evidence**

- `AGENTS.md` · captured by tool `python-agentic-audit` 0.1.0

**F-006** · DEGRADER · key `AGT-07`

An agent cannot rely on an explicit do-not list because AGENTS.md has no prohibitions section.

**Fix.** Add an explicit prohibitions section covering tests, generated files, the default branch and secrets.

Playbook `add-deny-rules` · Effort S · Touches `AGENTS.md`

**Confirmed.** Decided by the person, as one of a group of findings that are not blockers.

Evidence: the same as under the check.

#### AGT-08: No competing instruction files, and the reach matrix is stated

**PARTIAL** · DEGRADER · automated · scored

20/28 harnesses reached

The engine's payload for this check, of kind `harness_matrix`, is in the JSON report.

**F-010** · COSMETIC · key `AGT-08` · on a DEGRADER check

An agent cannot be reached by every agent harness because 8 of 28 known harnesses cannot read AGENTS.md.

**Fix.** State the harnesses that do not read AGENTS.md.

**Deferred.** Decided by the person, as one of a group of findings that are not blockers. Note: The team uses two of the harnesses it lacks files for; revisit when it adds a third.

#### AGT-11: Instructions are specific and not inferable

**PARTIAL** · DEGRADER · agent · scored · confidence medium

AGENTS.md states the non-obvious branch and release rules, but most other lines restate what package.json already shows.

**Evidence**

- `AGENTS.md:14-16` · captured by agent
  ```text
  Run `npm test` to run the tests. Run `npm run lint` to lint the code.
  ```
- `AGENTS.md:31-33` · captured by agent
  ```text
  Never tag a release from a feature branch; releases are cut from `dev` by the release workflow.
  ```
- Index query `scripts defined in package.json` through `search_graph`: 7 scripts; 4 are named in AGENTS.md with no added context · captured by agent

**Searches**

- `grep` search for `do not|never|must not` in `AGENTS.md`: 2 hits

**F-007** · DEGRADER · key `AGT-11`

An agent cannot learn the project's non-obvious rules from AGENTS.md because most of its lines restate what the manifests already show.

**Fix.** Cut the lines an agent can infer from package.json and keep the branch, release and deploy rules.

Playbook `adapt-agents-md` · Effort S · Touches `AGENTS.md`

**Confirmed.** Decided by the person, as one of a group of findings that are not blockers.

Evidence for F-007:

- `AGENTS.md:14-16` · captured by agent
  ```text
  Run `npm test` to run the tests. Run `npm run lint` to lint the code.
  ```
- `AGENTS.md:31-33` · captured by agent
  ```text
  Never tag a release from a feature branch; releases are cut from `dev` by the release workflow.
  ```

Searches: the same as under the check.

#### TOOL-03: Type checker configured

**PASS** · DEGRADER · automated · scored · confidence high

type checker configured and strict: tsconfig.base.json

**Overridden.** The engine's verdict was **PARTIAL**. This report says **PASS**. Reason: tsconfig.json extends tsconfig.base.json, which sets strict: true; the engine reads only the leaf file.

**Evidence**

- `tsconfig.base.json:4` · captured by agent
  ```text
  "strict": true
  ```
- `tsconfig.json:2` · captured by agent
  ```text
  "extends": "./tsconfig.base.json"
  ```

**F-009** · DEGRADER · key `TOOL-03`

An agent cannot trust the type checker to catch a whole class of defects because a type-check configuration exists but is not strict (tsconfig.json:strict).

**Fix.** Turn on strict mode.

**Rejected.** Decided by the person, as one of a group of findings that are not blockers. Note: Overridden to PASS: strict is set in the extended base config.

Evidence for F-009:

- `tsconfig.json` — strict is not set · captured by tool `python-agentic-audit` 0.1.0

#### CI-04: CI enforces the same gate as the local check

**FAIL** · DEGRADER · agent · scored · confidence medium

We did not find any evidence that the CI workflow runs the repository's check verb or fails the run when it fails.

**Evidence.** We did not find any evidence.

**F-008** · DEGRADER · key `CI-04`

An agent cannot trust a green CI run to mean the local gate passed because we did not find any evidence that the workflow runs the check verb.

**Fix.** Make the workflow run the check verb once it exists.

Playbook `add-ci-parity` · Effort M · Depends on `F-002` · Touches `.github/workflows/ci.yml`

**Confirmed.** Decided by the person, as one of a group of findings that are not blockers.

#### TST-02: Suite status known

**UNKNOWN** · DEGRADER · automated · scored

probe not run: probes disabled (pass --run-gates)

**Evidence.** We did not find any evidence.

## Coverage

**Examined:** `.`

| Skipped | Why |
|---|---|
| `dist/` | excluded at intake |

**Files:** 84 files inspected, 0 skipped; the scan was not cut short.

## Stack and components

| Stack | Detected |
|---|---|
| Ecosystems | `node` |
| Package managers | `npm` |
| CI providers | `github-actions` |
| Test frameworks | `jest` |
| Hook managers | — |

| Component | Path | Declared | Declared by | Manifest | AGENTS.md |
|---|---|---|---|---|---|
| (root) | `.` | yes | implicit | `package.json` | present |

## Provenance

| Field | Value |
|---|---|
| Report status | final |
| Schema version | `0.1` |
| Repository label | `example-service` |
| Path | `/work/example-service` |
| Commit | `deadbeefdeadbeefdeadbeefdeadbeefdeadbeef` |
| Branch | `main` |
| Started | `2026-10-10T09:00:00+00:00` |
| Finalised | `2026-10-10T09:42:07+00:00` |
| Recipe | `brownfield-audit` 0.1.0 |
| Catalogue version | `0.1.0` |
| Framework revision | `cafecafecafe` |
| Engine | `python-agentic-audit` 0.1.0, ruleset `2026-09-28.13`, ruleset hash `a1b2a1b2a1b2a1b2`, scanned `2026-10-10T09:01:30+00:00` |
| Agent (self-reported) | `claude-code` with `claude-sonnet-5-5` |

## Run context

| Field | Value |
|---|---|
| Evaluation mode | no |
| Confirmation policy | `interactive` |
| Provider exposure acknowledged | yes: the model provider receives what the agent reads from the target |
| Code index | `mcp` `codebase-memory-mcp` |
| Probes | none: no command of the target was run |
| Excluded | `dist/` |
| Known components | none |
| Stack profile | `typescript-node`, shipped, confirmed by the user |

---

Rendered from the JSON report by `render_report.py`. The JSON report is the record.
