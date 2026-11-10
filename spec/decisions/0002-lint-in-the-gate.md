# 0002. Lint is gated through `format:check`

## Context

[REQ-SH-022](../readiness-requirements.md#req-sh-022--check-composes-the-read-only-verbs) says `check` runs
`format:check`, `typecheck` and `test`. The [command surface](../command-surface.md) describes `format:check` as
"formatting and lint rules" and lists `lint` as not part of `check`. The framework's own `Makefile` runs the
formatter's check and the linter in its `format-check`. Without a rule, the two pages can be read to mean that lint
is gated, or that it is not.

## Decision

1. **`check` keeps its three members:** `format:check`, `typecheck` and `test`, in that order. `lint` does not join
   it.
2. **`format:check` MUST include the repository's lint rules.** A repository that has a separate `lint` verb runs the
   same rules inside `format:check`, so one gate covers both.
3. **Playbooks that add a lint or ratchet command put it in `format:check`**, not in a new member of `check`.

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| `check` = `format:check` + `lint` + `typecheck` + `test` | Changes the requirement, the verb table, the `CMD-02` check and every existing target's `check`. `lint` and `format:check` overlap in most runners. |
| `check` MUST gate lint by either route (`format:check` includes it, or `check` also runs `lint`) | Closes the case where a separate `lint` is not gated, but `CMD-02` would have to recognise two shapes. |

## Consequences

### Positive

* A target that follows the command surface needs no change; the framework's own `Makefile` conforms.
* One sentence in the requirement states the rule.

### Negative / Trade-offs

* A repository with a `lint` verb outside `format:check` is under-gated. `CMD-02` cannot read inside the target's
  recipe, so it does not see this.
