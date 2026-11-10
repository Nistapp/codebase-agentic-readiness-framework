# 0003. The Implement Recipe Pushes and Opens a Pull Request Only When the Owner Opted In

## Context

Three pages describe the end of a theme: [`implement/SKILL.md`](../../../SKILL.md), the
[purpose and non-goals page](../../../../docs/explanation/user-overview/01-purpose-and-non-goals.md) and the
[trust and safety page](../../../../docs/explanation/user-overview/03-trust-and-safety.md). Without one rule, they
can disagree on whether the recipe pushes the theme branch and opens a pull request.

The repositories the recipe runs on let a session push the phase branch and open the pull request; the
orchestrator or the owner merges. A recipe that
never pushes would break the one-pull-request-per-theme flow those runs depend on.

## Decision

1. **Default: stop at a local branch.** At the end of a theme (Stage 4) and of triage (Stage 1 step 9) the recipe
   commits on the theme branch and stops. The operator reviews and pushes.
2. **Opt-in: push and open a pull request.** When the owner recorded the preference `ci.pr_by_agent` with the value
   `yes`, the recipe pushes the theme branch and opens one pull request into the integration branch, then stops.
   Triage asks for it and records it with `progress.py pref set ci.pr_by_agent yes --by owner`. An absent key, or any
   other value, means the default. The recipe never infers `yes`.
3. **Never, under either path:** merge, push to the default branch, force-push, push tags, publish a release.
4. **Credentials.** Under the opt-in the agent needs a `gh` login that can push a branch and open a pull request on
   the target, and nothing more. It does not need, and must not use, merge, tag or force-push rights.

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| Always push and open a pull request | The agent would act with a push credential in repositories whose owner never said so, and the non-goals page would be false. |
| Never push | Every playbook ending and the Stage 1 and Stage 4 steps would change, and each theme would need a manual push by a person. |
| Opt-in, with a question when the key is absent | The recipe is built not to stop for questions in the middle of a theme; triage is the one place that asks. |

## Consequences

### Positive

* One rule, stated once here and linked from the three pages.
* The safe behaviour is the default; the choice is recorded in the state file every later session reads.

### Negative / Trade-offs

* Two end-of-theme paths to describe and test.
* Triage gains one question. Until a repository answers it, the recipe stops at a local branch.
