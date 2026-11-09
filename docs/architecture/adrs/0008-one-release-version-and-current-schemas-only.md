# 0008. Stamp One Release Version in Every Report and State, and Read Only the Current Schemas

* **Status:** Accepted
* **Date:** 2026-11-09
* **Last reviewed:** 2026-11-09
* **Deciders:** [@nistapp]

---

## Context

A report from release 0.3.0 and a report from release 0.3.3 can differ: other checks, other wording, other fields.
Before this decision, no file said which release made it. The audit report carried `recipe.version: 0.1.0` and the
implement state `0.2.0-dev`, whatever the release. A user who installs a release bundle has no git checkout, so the
report's commit was `null` too. The implement recipe could not tell if a report was too old for it, and a resumed run
could not tell if the framework changed between sessions.

release-please manages one package, `.`, and the audit and implement recipes ship together in one release
([ADR 0005](0005-release-please-cuts-releases.md)).

The framework has no outside user yet. The public releases so far served to test the CI and release pipeline. So
there is no old report or state that a tool must keep reading.

---

## Decision

1. **One release version.** It is the version in
   [`.release-please-manifest.json`](../../../.release-please-manifest.json).
   release-please writes it into the engine's `__version__`. It also writes it into `FRAMEWORK_RELEASE` in
   [`report.py`](../../../audit/tools/report.py) and [`progress.py`](../../../implement/tools/progress.py).
   [`build_skills.py`](../../../dev/build_skills.py) writes it into each bundle's `SKILL.md` as `metadata.version`.
   [`test_release_config.py`](../../../dev/tests/test_release_config.py) fails when a stamp differs from the manifest.
2. **One shape for "which framework".** A report holds `provenance.framework` and a state holds `framework`, both as
   `{release, revision, install}`. `revision` is a 12-digit commit or `null`; `install` is `checkout`, `bundle` or
   `copy`. One function, `validate_report.framework_facts`, finds all three, because both skill bundles ship
   `validate_report.py`. A state also holds `last_framework`, set by every write, with a log entry when it changes.
3. **The read rule.** A tool reads only the report schema and the state schema of its own release. Another version
   stops it with a message that names both versions and the next step. A report from a newer release stops the
   implement tools. A report from an older release, or from the same release at another commit, gives a warning.
   [`check_drift.py`](../../../implement/tools/check_drift.py) applies the rule on every new run and every resume.
4. **No backward compatibility yet.** A schema change replaces the old version.
   No tool converts or reads an older report or state.
   The policy ends at the first outside user or at release `1.0.0`, whichever comes first.
   `test_release_config.py` fails when the manifest reaches `1.0.0`.
   So release 1.0.0 cannot ship until the owner decides which older schemas the tools read.

[`docs/reference/versions.md`](../../reference/versions.md) lists every number, where it is written and each message.

---

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| A version per component: one for the audit recipe, one for the implement recipe | Two release-please packages, two tags and a compatibility table between them. The recipes ship together. |
| One shared constant that both tools import, such as the engine's `__version__` | The implement bundle loads the engine from the audit skill beside it. A mixed install would stamp the audit skill's version as the implement recipe's. |
| A `provenance.framework_release` field beside `recipe.version` | Two fields that hold the same value. |
| Keep report schema `0.1` and add optional fields | An older validator fails on the unknown field with an unclear error. A schema version bump gives every reader a clear signal. |
| Keep reading the older schemas | There is no outside user whose files need it. Each kept version is code and tests for a case that cannot happen yet. |
| A four-case rule, with a warning inside a minor line and an owner override flag | Written for customers who do not exist yet. It adds tests for cases that cannot happen. |
| A `framework_history[]` list in the state | It repeats what the log holds. |
| Write the end of the policy in this ADR only | Easy to forget at 1.0.0. The test makes the release fail until someone decides. |

> A later reversal of this decision is folded into this table, so the rejected direction
> keeps its rationale inside the accepted record.

---

## Consequences

### Positive

* Every report and state says which release, which commit and which kind of install made it.
* A too-old or too-new file stops with a message that says what to do, on a new run and on a resume.
* The tools carry no code for older schemas.

### Negative / Trade-offs

* A change to only one recipe still bumps the release version that both recipes carry.
* Every report and state made before this decision is unreadable by the current tools. Run a new audit.
* Between two releases, every checkout carries the last released version. Only the commit tells two such reports
  apart, and a bundle has no commit.
* The "first outside user" trigger has no check. Someone has to notice it.

---

## Lifecycle — Living, Current-State ADRs

* **This ADR MUST describe only the shipped, current design.** There is no `Deprecated`, `Superseded`, or `Rejected` status.
* **Decision changed?** Overwrite the body, keep the file and its number, and fold the reversal into
  *Alternatives Considered*. Do NOT create a superseding ADR and do NOT leave a tombstone stub.
* **Decision no longer relevant?** Delete the file, retire its number forever, and update every inbound reference
  plus the index table in `docs/architecture/adrs/README.md` in the same change set.
* Archived wording: `git log --follow docs/architecture/adrs/0008-one-release-version-and-current-schemas-only.md`.

See [`docs/STYLE_GUIDE.md`](../../STYLE_GUIDE.md) § ADR Lifecycle for the canonical rules.
