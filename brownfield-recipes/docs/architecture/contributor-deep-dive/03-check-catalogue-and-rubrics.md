# 3. Check Catalogue & Rubrics

> **Audience:** Engineers, maintainers
> **Goal:** Explain how checks are defined once in `catalogue.json`, what keeps it true, and how a check is judged.
> **Status:** Live for the catalogue, the anatomy, S3.1's four check families (`IDX`, `AGT`, `DOC`,
> `CMD`), S3.2's four (`TOOL`, `CI`, `BASE`, `CON`) and S3.3's first three (`EXEC`, `TST`, `NAV`); `S3.1`
> and `S3.2` are closed, `S3.3` is in progress. The remaining `S3.3` families are still being written.

> [!NOTE]
> Planned. `S3.1` is closed:
> [`01-discovery-and-index.md`](../../../audit/checks/01-discovery-and-index.md) (`IDX`),
> [`02-agent-governance.md`](../../../audit/checks/02-agent-governance.md) (`AGT`, including `AGT-11`,
> the first agent-only check whose rubric exists — its catalogue `status` is now `implemented`),
> [`03-documentation-contract.md`](../../../audit/checks/03-documentation-contract.md) (`DOC`) and
> [`04-command-surface.md`](../../../audit/checks/04-command-surface.md) (`CMD`).
> [`05-tooling.md`](../../../audit/checks/05-tooling.md) (`TOOL`),
> [`06-ci.md`](../../../audit/checks/06-ci.md) (`CI`, including `CI-04`, the second agent-only check whose
> rubric exists — its catalogue `status` is now `implemented`),
> [`07-baselines-and-ratchet.md`](../../../audit/checks/07-baselines-and-ratchet.md) (`BASE`) and
> [`08-constraints.md`](../../../audit/checks/08-constraints.md) (`CON`) are also written, closing `S3.2`
> (18 more checks: `TOOL` 6, `CI` 4, `BASE` 4, `CON` 4).
> [`09-execution-determinism.md`](../../../audit/checks/09-execution-determinism.md) (`EXEC`, 7 checks),
> [`10-tests.md`](../../../audit/checks/10-tests.md) (`TST`, 5 checks, including `TST-02`, the pack's one
> Tier-C probe) and [`11-navigation.md`](../../../audit/checks/11-navigation.md) (`NAV`, 5 checks,
> including `NAV-04` and `NAV-05`, informational and unscored) are `S3.3`'s first three families. The
> remaining families (`SEC`, `HYG`) are still being written. The catalogue itself,
> [`catalogue.json`](../../../catalogue.json), exists and is tested.

---

## 1. One ID namespace

[`catalogue.json`](../../../catalogue.json) lists every check the audit can report, engine checks and agent-only checks together. A check has one ID, in the form of a family prefix and a number, and that ID is the only name the report, the spec's `Checks` fields, the playbooks and the rubrics use. Nothing translates between an "engine ID" and a "recipe ID". The schema is [`catalogue.schema.json`](../../../schema/catalogue.schema.json), and the field list is there; this page does not repeat it.

Where the entries come from:

- **Engine checks** are seeded from the engine's own list, `python3 -m audit --list-checks --format json` ([`cli.py`](../../../deterministic-audit/audit/cli.py)). After seeding the file is edited by hand. The engine's ID is the check's ID, and `engine_id` repeats it.
- **Agent-only checks** are the ones no deterministic rule can settle. Today there are two: `AGT-11` (instructions are specific and not inferable, for [REQ-SH-015](../../../../spec/readiness-requirements.md#req-sh-015--instructions-are-specific-and-not-inferable)) and `CI-04` (CI enforces the same gate as the local check, for [REQ-SH-035](../../../../spec/readiness-requirements.md#req-sh-035--ci-enforces-the-gate)). They are numbered after the engine's highest number in their family, so an engine check added later cannot collide with one: the engine takes the next free number and the test fails if it takes an agent check's.
- **`status`** is the engine's own status for an engine check. An agent-only check is `planned` until its rubric exists. A check that is planned or blocked is reported `UNKNOWN`. `scored` is also the engine's: `CON-01` was `blocked` and unscored until catalogue 0.2.0, when the engine began to read the prohibitions section.

## 2. Methods

A check's `method` is one of the two that produce a verdict. The words are the spec's ([verification methods](../../../../spec/README.md#verification-methods)).

| Method | Decided by | In the catalogue | In a report |
|---|---|---|---|
| `automated` | The engine | Every engine check | `engine_verdict` equals `verdict` unless an agent overrides it with counter-evidence and a reason |
| `agent` | A model reading the repository | `AGT-11`, `CI-04` | A verdict with cited evidence, or a `FAIL` that says no evidence was found |

A requirement verified by a person (`human`) or by the owner's declaration (`attested`) has no check, so it has no row here. It appears in a report's `unattested[]`. The catalogue test requires that a check has the same method as every requirement it verifies, so the two vocabularies cannot drift.

## 3. Rubric anatomy

Every check file under [`audit/checks/`](../../../audit/checks/) follows one fixed shape, set out in that
folder's own [`README.md`](../../../audit/checks/README.md): `Why it matters`, `Severity`, `Engine`,
`Method`, `Look for`, `Rubric` (a verdict per outcome, including when it is `UNKNOWN`), `Evidence to cite`,
`Absence proof`, `Remediation` and `Pitfalls`. `Engine` and `Method` are additions beyond DP §5.2: they say
which engine check backs this one (or `none` for an agent-only check) and repeat the catalogue's `method`,
so the file is readable without a second lookup. A rubric names observable thresholds, never adjectives;
a `FAIL` that claims an absence must record the `searches[]` entries that looked for it. See
[`01-discovery-and-index.md`](../../../audit/checks/01-discovery-and-index.md) for the pattern applied to
`IDX-01`–`IDX-03`.

## 4. Traceability and versions

A check reaches the framework in three hops, and three files say it:

1. The catalogue's `req_ids` name the requirements the check verifies.
2. Each requirement's `Checks` field in [`readiness-requirements.md`](../../../../spec/readiness-requirements.md) names the checks back.
3. Each requirement's `Source` links the framework heading it comes from.

[`traceability.md`](../../../../spec/traceability.md) lists the same relation for people to read. A test, [`test_catalogue.py`](../../../tools/tests/test_catalogue.py), holds all of them to one another: the catalogue against the engine's JSON list, the requirements in both directions, the method against the requirement's, and the traceability table. [How the Checks Map to the Framework](../../reference/how-the-checks-map-to-the-framework.md) shows how to follow one check.

A report records `catalogue_version`, which is `MAJOR.MINOR.PATCH`. The rules for a bump are in the schema's description of the field. A `fingerprint` in the catalogue covers the fields that decide a verdict: ID, phase, severity, scored flag, method, requirement IDs and engine ID. The test fails when the fingerprint is stale, and its message names the steps. The fingerprint does not cover titles, playbooks or rubric wording, so a change to one of those, which is a PATCH at most, depends on the person making it.

---

## 5. Invariants & Failure Modes

- **Invariant: the engine is the authority on its own checks.** The catalogue cannot hold an engine check the engine lacks, cannot omit one it has, and cannot disagree with it on title, phase, severity, scored flag or status. The engine's order is kept.
- **Invariant: agreement is checked in both directions.** A requirement names a check only if the check names the requirement, and the other way round.
- **Invariant: every scored BLOCKER names a playbook.** The implementation recipe covers every blocker class of the audit.
- **Failure mode: a catalogued check with no rubric.** `AGT-11` and `CI-04` are in the catalogue and cannot be judged until the rubrics exist, so a report cannot contain a verdict for them yet.
- **Failure mode: a change the fingerprint misses.** A rewritten rubric changes what a verdict means and leaves the fingerprint alone. The rule is that such a change bumps the version, and nothing enforces it.
