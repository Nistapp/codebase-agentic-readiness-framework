# Agentic readiness audit: example-service

> [!NOTE]
> This audit reports; it does not gate. A check that could not be settled is UNKNOWN: it earns no credit and is never shown as a pass.

## Provenance

| Field | Value |
|---|---|
| Target | `/work/example-service` |
| Commit | `deadbeefdead` on `main` — clean working tree |
| Status | final |
| Started | `2026-10-10T09:00:00+00:00` |
| Finalised | `2026-10-10T09:42:07+00:00` |
| Recipe | `brownfield-audit` 0.1.0, catalogue `0.2.0` |
| Engine | `python-agentic-audit` 0.1.0, ruleset `2026-09-28.13`, ruleset hash `a1b2a1b2a1b2a1b2`, scanned `2026-10-10T09:01:30+00:00` |
| Framework revision | `cafecafecafe` |
| Agent (self-reported) | `claude-code` with `claude-sonnet-5-5` |
| Probes | none: no command of the target was run |
| Report schema | `0.1` |

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

## Checks by verdict and severity

The first table counts every check in the report. The second counts the scored checks only.

| Verdict | Checks | Credit | Meaning |
|---|---:|---:|---|
| PASS | 3 | 1 | The requirement is met. |
| PARTIAL | 2 | 0.5 | Part of the requirement is met. |
| FAIL | 6 | 0 | The requirement is not met. |
| UNKNOWN | 1 | 0 | The evidence could not be gathered. It is never read as a pass. |
| NOT_APPLICABLE | 0 | outside the score | The check does not apply to this repository. |
| **Total** | **12** |  |  |

| Severity | Weight | Meaning | Scored checks | Not met |
|---|---:|---|---:|---:|
| BLOCKER | 3 | Agent work is impossible, unsafe or unverifiable. Fix before onboarding agents. | 6 | 4 |
| DEGRADER | 2 | Agent work is possible but unreliable or wasteful. | 6 | 5 |
| COSMETIC | 1 | Hygiene. Fix when convenient. | 0 | 0 |

## Command surface

The framework's seven verbs, resolved verb by verb on the target's runners — CMD-01's structured payload; CMD-02, AGT-05 and CI-02 read the same surface.

3 verbs of 7 verbs resolve. Missing: `format:check`, `typecheck`, `check`, `security`.

| Verb | Resolved | Runner | Command |
|---|:---:|---|---|
| `format` | yes | `package.json` | `prettier --write "src/**/*.ts"` |
| `format:check` | **no** | — | — |
| `lint` | yes | `package.json` | `eslint "src/**/*.ts"` |
| `typecheck` | **no** | — | — |
| `test` | yes | `package.json` | `jest` |
| `check` | **no** | — | — |
| `security` | **no** | — | — |

## Checks that need attention

Each row is a finding, or a check that has none. A check is listed when it is not met, was overridden, was judged by the agent, or raised a finding. Evidence is grouped by who captured it, and a quote or command output is under Evidence in full. The decision on a finding is one of these:

- **interactive**: Decided by the person, on this finding alone.
- **batch**: Decided by the person, as one of a group of findings that are not blockers.
- **policy**: Set by the confirmation policy, not by a person.

### Blocker checks

4 of the 6 scored BLOCKER checks are not met.

| Check | Verdict | What we found | Evidence | Fix | Decision |
|---|---|---|---|---|---|
| `CMD-01` Seven verbs resolvable on one runner<br>finding `F-001` | **FAIL** | An agent cannot run the standardized command surface literally because 4 of 7 framework verbs are not defined on any runner (format:check, typecheck, check, security). | **tool** `package.json` | Define every verb as a script so an agent never has to invent a command.<br>Playbook `define-command-surface` · Effort S · Touches `package.json` | **Confirmed** (interactive) |
| `CMD-02` check composes the read-only verbs<br>finding `F-002` | **FAIL** | An agent cannot run one command that proves a change is safe because the check verb is not defined on any runner. | **tool** `package.json` | Define check as the composition of the read-only verbs.<br>Playbook `define-command-surface` · Effort S · Depends on `F-001` · Touches `package.json` | **Confirmed** (interactive) |
| `EXEC-01` Toolchain pinned / wrapper committed<br>finding `F-003` | **FAIL** | An agent cannot reproduce the toolchain because node is not pinned by a version file, an engines constraint or a wrapper. | **tool** `package.json` | Pin Node 22 in .nvmrc.<br>Playbook `pin-execution-environment` · Effort S · Touches `.nvmrc` | **Edited** (interactive)<br>Note: The owner pins Node 22 in .nvmrc and leaves the engines field alone. |
| `SEC-02` No key-shaped strings in tracked files<br>finding `F-004` | **FAIL** | An agent cannot keep credentials out of the repository and its history because src/config/constants.ts contains 1 credential-shaped line(s). | **tool** `src/config/constants.ts:12` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential.<br>Playbook `env-inventory-and-secrets` · Effort M · Touches `src/config/constants.ts` | **Confirmed** (interactive) |
| `SEC-02` No key-shaped strings in tracked files<br>finding `F-005` | **FAIL** | An agent cannot keep credentials out of the repository and its history because src/services/\_\_tests\_\_/auth.test.ts contains 2 credential-shaped line(s). | **tool** `src/services/__tests__/auth.test.ts:37` (credential-shaped string)<br>`src/services/__tests__/auth.test.ts:58` (credential-shaped string) | Remove the value from the file and its history, load it from the environment, and rotate the credential. | **Rejected** (interactive)<br>Note: Placeholder values in a unit test, not credentials. |

### Degrader checks

5 of the 6 scored DEGRADER checks are not met.

| Check | Verdict | What we found | Evidence | Fix | Decision |
|---|---|---|---|---|---|
| `AGT-07` Do-not-do / deny rules present<br>finding `F-006` | **FAIL** | An agent cannot rely on an explicit do-not list because AGENTS.md has no prohibitions section. | **tool** `AGENTS.md` | Add an explicit prohibitions section covering tests, generated files, the default branch and secrets.<br>Playbook `add-deny-rules` · Effort S · Touches `AGENTS.md` | **Confirmed** (batch) |
| `AGT-08` No competing instruction files, and the reach matrix is stated<br>finding `F-010`, severity COSMETIC | **PARTIAL** | An agent cannot be reached by every agent harness because 8 of 28 known harnesses cannot read AGENTS.md. | — | State the harnesses that do not read AGENTS.md. | **Deferred** (batch)<br>Note: The team uses two of the harnesses it lacks files for; revisit when it adds a third. |
| `AGT-11` Instructions are specific and not inferable<br>finding `F-007` · agent, confidence medium | **PARTIAL** | An agent cannot learn the project's non-obvious rules from AGENTS.md because most of its lines restate what the manifests already show. | **agent** `AGENTS.md:14-16` (quote in Evidence in full)<br>`AGENTS.md:31-33` (quote in Evidence in full)<br>**searches** `grep` for `do not\|never\|must not` in `AGENTS.md`: 2 hits | Cut the lines an agent can infer from package.json and keep the branch, release and deploy rules.<br>Playbook `adapt-agents-md` · Effort S · Touches `AGENTS.md` | **Confirmed** (batch) |
| `TOOL-03` Type checker configured<br>finding `F-009` | **PASS**<br>engine: PARTIAL | An agent cannot trust the type checker to catch a whole class of defects because a type-check configuration exists but is not strict (tsconfig.json:strict).<br>**Overridden.** The engine's verdict was PARTIAL. Reason: tsconfig.json extends tsconfig.base.json, which sets strict: true; the engine reads only the leaf file. | **tool** `tsconfig.json` (strict)<br>**agent** `tsconfig.base.json:4` (quote in Evidence in full)<br>`tsconfig.json:2` (quote in Evidence in full) | Turn on strict mode. | **Rejected** (batch)<br>Note: Overridden to PASS: strict is set in the extended base config. |
| `CI-04` CI enforces the same gate as the local check<br>finding `F-008` · agent, confidence medium | **FAIL** | An agent cannot trust a green CI run to mean the local gate passed because we did not find any evidence that the workflow runs the check verb. | We did not find any evidence. | Make the workflow run the check verb once it exists.<br>Playbook `add-ci-parity` · Effort M · Depends on `F-002` · Touches `.github/workflows/ci.yml` | **Confirmed** (batch) |
| `TST-02` Suite status known | **UNKNOWN** | probe not run: probes disabled (pass --run-gates) | We did not find any evidence. | — | — |

### Cosmetic checks

There is no COSMETIC check in this report.

## Overrides of the engine's verdicts

Where this report's verdict differs from the engine's, the row of the check above shows both, and the agent's counter-evidence is in its Evidence column or under Evidence in full.

| Check | Engine's verdict | This report's verdict | Reason |
|---|---|---|---|
| `TOOL-03` | PARTIAL | PASS | tsconfig.json extends tsconfig.base.json, which sets strict: true; the engine reads only the leaf file. |

## Evidence in full

Quotes and command output that the tables above point to, each under the check that cites it.

### AGT-11: Instructions are specific and not inferable

- `AGENTS.md:14-16` · captured by agent
  ```text
  Run `npm test` to run the tests. Run `npm run lint` to lint the code.
  ```
- `AGENTS.md:31-33` · captured by agent
  ```text
  Never tag a release from a feature branch; releases are cut from `dev` by the release workflow.
  ```

### TOOL-03: Type checker configured

- `tsconfig.base.json:4` · captured by agent
  ```text
  "strict": true
  ```
- `tsconfig.json:2` · captured by agent
  ```text
  "extends": "./tsconfig.base.json"
  ```

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

## Run context

| Field | Value |
|---|---|
| Evaluation mode | no |
| Confirmation policy | `interactive` |
| Provider exposure acknowledged | yes: the model provider receives what the agent reads from the target |
| Code index | `mcp` `codebase-memory-mcp` |
| Excluded | `dist/` |
| Known components | none |
| Stack profile | `typescript-node`, shipped, confirmed by the user |

## Appendix — all checks

All 12 checks, grouped by family. The command surface above is one of the engine's structured payloads; the rest (credential-shaped lines, missing secret-shape ignore rules, and so on) are in the JSON report only, for now.

### IDX

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `IDX-01` | codebase-memory-mcp registered for this repository | BLOCKER | automated | yes | PASS | PASS | codebase-memory-mcp registered in: ~/.config/opencode/opencode.jsonc (user) |

### AGT

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `AGT-07` | Do-not-do / deny rules present | DEGRADER | automated | yes | FAIL | FAIL | no prohibitions section |
| `AGT-08` | No competing instruction files, and the reach matrix is stated | DEGRADER | automated | yes | PARTIAL | PARTIAL | 20/28 harnesses reached |
| `AGT-11` | Instructions are specific and not inferable | DEGRADER | agent | yes | PARTIAL | — | AGENTS.md states the non-obvious branch and release rules, but most other lines restate what package.json already shows. |

### CMD

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `CMD-01` | Seven verbs resolvable on one runner | BLOCKER | automated | yes | FAIL | FAIL | format -> package.json; format:check -> missing; lint -> package.json; typecheck -> missing; test -> package.json; check -> missing; security -> missing |
| `CMD-02` | check composes the read-only verbs | BLOCKER | automated | yes | FAIL | FAIL | the check verb is not defined on any runner |

### TOOL

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `TOOL-03` | Type checker configured | DEGRADER | automated | yes | PASS | PARTIAL | type checker configured and strict: tsconfig.base.json |

### CI

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `CI-01` | Pipeline present, triggered on PRs | BLOCKER | automated | yes | PASS | PASS | workflow file(s): .github/workflows/ci.yml, triggered on pull_request |
| `CI-04` | CI enforces the same gate as the local check | DEGRADER | agent | yes | FAIL | — | We did not find any evidence that the CI workflow runs the repository's check verb or fails the run when it fails. |

### EXEC

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `EXEC-01` | Toolchain pinned / wrapper committed | BLOCKER | automated | yes | FAIL | FAIL | unpinned: node |

### SEC

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `SEC-02` | No key-shaped strings in tracked files | BLOCKER | automated | yes | FAIL | FAIL | 3 credential-shaped line(s) across 2 file(s) in tracked text files |

### TST

| Check | Title | Severity | Method | Scored | Verdict | Engine | Summary |
|---|---|---|---|---|---|---|---|
| `TST-02` | Suite status known | DEGRADER | automated | yes | UNKNOWN | UNKNOWN | probe not run: probes disabled (pass --run-gates) |

---

Rendered from the JSON report by `render_report.py`. The JSON report is the record.
