# 0002. Lint is gated through `format:check`

* **Status:** Accepted
* **Date:** 2026-11-05
* **Last reviewed:** 2026-11-05
* **Deciders:** K. C. Ramakrishna (Q2, accepted 2026-11-05)

---

## Context

[REQ-SH-022](../readiness-requirements.md#req-sh-022--check-composes-the-read-only-verbs) said `check` runs
`format:check`, `typecheck` and `test`, and said nothing about lint. The [command surface](../command-surface.md)
already described `format:check` as "formatting and lint rules" and listed `lint` as not part of `check`. The
framework's own `Makefile` follows the second reading: its `format-check` runs the formatter's check and the linter.
The two pages could be read to mean that lint is gated, or that it is not.

## Decision

1. **`check` keeps its three members:** `format:check`, `typecheck` and `test`, in that order. `lint` does not join
   it.
2. **`format:check` MUST include the repository's lint rules.** A repository that has a separate `lint` verb runs the
   same rules inside `format:check`, so one gate covers both.
3. **Playbooks that add a lint or ratchet command put it in `format:check`**, not in a new member of `check`.

## Alternatives Considered

| Alternative | Why it was rejected |
|---|---|
| `check` = `format:check` + `lint` + `typecheck` + `test` | Changes the requirement, the verb table, the `CMD-02` check and every existing target's `check`. `lint` and `format:check` overlap in most runners. |
| `check` MUST gate lint by either route (`format:check` includes it, or `check` also runs `lint`) | Closes the case where a separate `lint` is not gated, but `CMD-02` would have to recognise two shapes. Left for later if that case matters. |

## Consequences

### Positive

* No change for a target that already follows the command surface; the framework's own `Makefile` already conforms.
* One sentence in the requirement states the rule.

### Negative / Trade-offs

* A repository with a `lint` verb outside `format:check` is under-gated. `CMD-02` cannot read inside the target's
  recipe, so it does not see this.
