# 0008. Stamp One Release Version in Every Report and State, and Read Only the Current Schemas

## Context

A report from release 0.3.0 and a report from release 0.3.3 can differ: other checks, other wording, other fields.
Without a release stamp, no file says which release made it. A user who installs a release bundle has no git
checkout, so the report's commit is `null` too. The implement recipe then cannot tell if a report is too old for it,
and a resumed run cannot tell if the framework changed between sessions.

release-please manages one package, `.`, and the audit and implement recipes ship together in one release
([ADR 0005](0005-release-please-cuts-releases.md)).

The framework has no outside user yet, so there is no old report or state that a tool must keep reading.

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

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| A version per component: one for the audit recipe, one for the implement recipe | Two release-please packages, two tags and a compatibility table between them. The recipes ship together. |
| One shared constant that both tools import, such as the engine's `__version__` | The implement bundle loads the engine from the audit skill beside it. A mixed install would stamp the audit skill's version as the implement recipe's. |
| A `provenance.framework_release` field beside `recipe.version` | Two fields that hold the same value. |
| Keep report schema `0.1` and add optional fields | An older validator fails on the unknown field with an unclear error. A schema version bump gives every reader a clear signal. |
| Keep reading the older schemas | There is no outside user whose files need it. Each kept version is code and tests for a case that cannot happen yet. |
| A four-case rule, with a warning inside a minor line and an owner override flag | Written for customers who do not exist yet. It adds tests for cases that cannot happen. |
| A `framework_history[]` list in the state | It repeats what the log holds. |
| Write the end of the policy in this ADR only | Easy to forget at 1.0.0. The test makes the release fail until someone decides. |

## Consequences

### Positive

* Every report and state says which release, which commit and which kind of install made it.
* A too-old or too-new file stops with a message that says what to do, on a new run and on a resume.
* The tools carry no code for older schemas.

### Negative / Trade-offs

* A change to only one recipe still bumps the release version that both recipes carry.
* A report or state from another release is unreadable by the current tools. Run a new audit.
* Between two releases, every checkout carries the last released version. Only the commit tells two such reports
  apart, and a bundle has no commit.
* The "first outside user" trigger has no check. Someone has to notice it.
