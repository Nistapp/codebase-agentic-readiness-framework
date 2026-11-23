# 0006. A Weakened Gate or an Unapproved Dependency Stops the Theme Until the Owner Decides

## Context

Two hard rules of the [implement recipe](../../../SKILL.md#hard-rules) protect the target's own checks and its
supply chain. "Never weaken a gate": no test deleted, skipped or weakened, no floor lowered, no rule turned off,
unless the owner chose it. "Never install a dependency the owner did not approve." Only the paid implement eval
scored them (its assertions A15 and A18), and only on canned scenarios. On a real run nothing looked.

Much of a break shows in the theme's diff: a deleted test file, a new skip marker, a lower `fail_under`, a new name in
`package.json`. A tool can read that diff with read-only git at theme close, beside the lost-pass check of
[ADR 0005](0005-a-lost-pass-stops-the-theme.md).

## Decision

1. **A close-time diff check.** [`tools/check_gates.py`](../../../tools/check_gates.py) reads
   `git diff <base>..<theme>` in the theme worktree and the two sides of each changed file. It writes nothing. Stage 4,
   step 1 runs it after the lost-pass comparison
   ([theme-checks.md](../../../theme-checks.md#keep-every-gate-and-approve-every-dependency)).
2. **Skip markers come from the engine.** The test-file rule and the marker table are the engine's `TST-03` census
   (`audit.rules.checks.tst`), loaded through `engine.py`. They are never copied, so the two cannot drift.
3. **A finding is exit 2, and the theme stops.** `data.errors` has one line per finding. The agent asks the owner:
   fix it, record the choice, or stop the theme. There is no default.
4. **The owner's choice is a preference in the state.** `dependencies.approved` lists the dependency names the owner
   approved. `gates.accepted` lists the path globs whose gate findings the owner chose. Both are ordinary
   preferences, set with `progress.py pref set ... --by owner`, so the state schema does not change. An accepted
   gate finding is listed in `data.accepted`; it never approves a dependency.
5. **The tool names what it cannot see** (the Tools CLI reference and `theme-checks.md` list it). A clean result is
   no proof; the rules still bind the agent there.

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| Keep the two rules eval-only | The eval runs only on canned scenarios, so a real run has no check at all. |
| Exit 0 with a status field, as `check_regressions.py` does | A finding here is the rule broken, not a move to judge; exit 2 makes the stop hard to miss. |
| Copy the skip markers into the tool | The copy would drift from the engine's `TST-03` census. |
| A new state field for approvals | A preference already records an owner choice with a reason, a date and who decided; a field would change the schema for the same data. |
| Refuse at commit time with a hook in the target | A hook writes inside the target, which [ADR 0004](0004-implement-state-lives-in-the-audit-workspace.md) forbids. |

## Consequences

### Positive

- The commonest ways to weaken a gate or add a dependency stop the theme on every run, not only in the eval.
- An owner's choice is recorded once, with a reason, and the tool honours it.

### Negative / Trade-offs

- The tool reads text patterns. A weakened assertion, a rule turned off in a config file and a one-off install pass
  unseen.
- A playbook move that adds a dependency now needs the owner's approval recorded before the theme closes.
- Nothing stops an agent that reads exit 2 and goes on; the rule lives in the recipe.
