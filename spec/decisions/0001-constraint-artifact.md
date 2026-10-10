# 0001. Use the prohibitions section as the deny list

* **Status:** Accepted
* **Date:** 2026-10-10
* **Last reviewed:** 2026-10-10
* **Deciders:** K. C. Ramakrishna (decided 2026-10-09; written down 2026-10-10)

---

## Context

Phase 1 of the framework asks a repository to "establish initial Constraint Engineering allow/deny lists" ([Phased-Approach.md](../../brownfield-legacy/Phased-Approach.md#activities)). Its Key Deliverables table gives the form as "Config files" and the consumer as agents. It names no file and no schema. Constraint Engineering itself is described in [Overview.md](../../shared/Overview.md#constraint-engineering).

The audit engine could not check what no document defined:

* `CON-01` ("Allow/deny artifact present") is blocked and carries weight 0.
* `CON-02` ("Test directories protected") accepts one of about twenty root-level file names, such as `.cursorignore`, `constraints.yaml` and `denylist.txt`. Without one it falls back to ignore rules and to CI text, and never passes.
* Two equally well-governed repositories got different verdicts depending on the file name they happened to choose.

An agent reads the instruction file at the start of every session. It reads no other file unless its harness is configured to. The framework's own template already has a "Do Not Do" section in that file ([greenfield `AGENTS.md`](../../greenfield-bootstrap/templates/AGENTS.md), section 10).

---

## Decision

1. **The deny list is the prohibitions section of the instruction file.** It is the section whose heading says what an agent must not do. "Do Not Do" is the template's heading; "Never", "Prohibited", "Forbidden" and "Deny" are accepted too. It is the only allow/deny artifact the spec requires or checks.
2. **There is no separate allow list.** What an agent may change is stated by the architectural boundaries ([REQ-SH-010](../readiness-requirements.md#req-sh-010--architectural-boundaries-declared)) and limited by the deny list.
3. **Harness-native enforcement is optional hardening.** Claude Code permission rules, opencode permissions, `.cursorignore` and the like are neither required nor checked, and an audit gives them no verdict. A report may mention them as a way to enforce the list.
4. **Scope.** This decides Phase 1. Where per-component constraints live in Phases 3 to 5 is not decided here.

Three requirements concern the deny list, and each answers one question:

| Requirement | Question | Check |
|---|---|---|
| [REQ-SH-011](../readiness-requirements.md#req-sh-011--prohibitions-declared) | Does the file have a prohibitions section, and do its prohibitions, anywhere in the file, cover tests, generated files, the default branch and secrets? | `AGT-07` |
| [REQ-SH-037](../readiness-requirements.md#req-sh-037--allow-and-deny-lists) | Is the section a concrete deny list, one that names paths, and not only prose? | `CON-01` |
| [REQ-SH-038](../readiness-requirements.md#req-sh-038--test-directories-denied) | Does it name every test directory? | `CON-02` |

An absence is reported once, by the check that owns it. With no instruction file, `AGT-01` reports it and the other three are `UNKNOWN`. With no prohibitions section, `AGT-07` reports it and `CON-01` and `CON-02` are `UNKNOWN`.

### What the two checks mean now

A prohibitions entry *names a path* when the path, or a pattern that covers it, appears in a code span in the entry.

| Verdict | `CON-01` | `CON-02` |
|---|---|---|
| `PASS` | At least one named path or pattern matches a file or directory of the repository. | The section names every test directory. |
| `PARTIAL` | The section names paths, but none matches anything in the repository. | It names some test directories, not all. |
| `FAIL` | The section names no path or pattern. | It names none of the test directories. |
| `UNKNOWN` | No instruction file, or no prohibitions section. | The same, or the repository has no test directory. |

`CON-02` stops counting constraint files, ignore rules and CI text as evidence. A repository that protects its tests only that way is reported as not naming them in its deny list. The change is deliberate: the other mechanisms are not the artifact.

### `CON-04`, the draft emitter

`CON-04` stays as a drafting aid. Its value is the deterministic scan: which secret, migration, generated, test, infrastructure and production paths exist. Its output changes: a Markdown section to paste under the instruction file's prohibitions heading, in place of `constraints.draft.yaml`, which nothing reads any more.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| A neutral machine-readable constraints file, with generators for each harness | No harness reads it, so it adds a file and a generator without adding enforcement. It can come later if enforcement is wanted, and the section can be its source. |
| Harness-native configuration as the policy | One configuration per harness, and a repository may serve several. The policy would sit in files an agent does not read as instructions. |
| Keep accepting any of the root-level file names | A verdict that depends on a naming choice, and no single place for the agent or the playbook to write to. |
| Retire `CON-04` | The scan that finds the candidates is deterministic and tested. A model should not rediscover the same paths by exploring the repository. |

---

## Consequences

### Positive

* One artifact that the agent already reads, and one verdict that does not depend on the harness.
* The `add-deny-rules` playbook has one file to write.
* A repository with several harnesses has one deny list, not one per harness.

### Negative / Trade-offs

* The section is prose, so the checks are heuristics: headings and code spans. A path written without backticks is not seen.
* The list is a statement, not a mechanism. An agent can ignore it, and optional native configuration is how a team enforces it.
* A repository governed through ignore files loses the credit it had under the old `CON-02`.
* The Key Deliverables table in [Phased-Approach.md](../../brownfield-legacy/Phased-Approach.md#key-deliverables) says "Config files". The spec reads that as the instruction file, and the table's wording is left to the framework's maintainer.

### Engine changes not yet made

The engine still behaves as described in the Context. These changes are planned, and this list is removed once they are done:

1. **`CON-02`: stop reading `spec` and `specs` as test directories.** The framework's own `specs/` holds feature specifications. On a freshly generated scaffold `CON-02` names `specs/` today. This must come before change 3, or the scaffold would fail a BLOCKER check.
2. **One helper that finds the prohibitions section**, used by `AGT-07`, `CON-01` and `CON-02`, so heading detection cannot drift between them. `AGT-07` keeps scanning the whole file for the four concerns.
3. **`CON-02`: read the section.** Remove the constraint-file names, the ignore-rule fallback and the CI-text fallback. One fixture per verdict.
4. **`CON-01`: implement and score it**, per the table above, with one fixture per verdict. The scored-check count and the score change, so the ruleset hash and the example reports change with them.
5. **`CON-04`: emit Markdown**, keep the six categories and the path matchers, and drop the YAML renderer.
6. **Documents:** the `CON` section of the engine's check catalogue, the pack's docstring, the registry text and the remediation how-to follow the code. The engine's changelog records the verdict changes.

---

## Lifecycle

A decision record describes the current decision only. When the decision changes, overwrite the body, keep the file and its number, and fold the reversal into *Alternatives Considered*. See [README.md](../README.md#decision-records).
