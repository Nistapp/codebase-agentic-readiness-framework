# 0006. Private Check Helpers and the Ignore Engine

## Context

ADR-0005 fixes the package layout: one module per pipeline stage under `audit/`, one module per check
family under `audit/rules/checks/`. That works for behaviour that belongs to a single stage or a
single pack. Two cross-cutting concerns do not fit it:

1. **Tracked-file and ignore certainty.** The walk, `SEC-01`, `SEC-03`, `DOC-03`, `EXEC-05` and `CON-03` ask
   which files git tracks. They also ask whether an ignore rule covers a path.
2. **Verb resolution and documented commands.** `CMD-01`, `EXEC-06`, `CI-02`, `AGT-05`,
   `TOOL-01/02/04` and `TST-01/04` all ask "what verbs exist, what does each run, and which commands
   does the documentation show?". Answering that per pack guarantees several divergent answers.

Duplicating either concern across packs is the classic path to disagreement: two checks reading the
same manifest by two slightly different rules will one day disagree in the same report.

## Decision

**Two internal helper modules, no new pipeline stage and no new rule pack.**

1. **`audit/ignore.py`** owns the git-aware tracked-file accessor and the documented-subset ignore
   matcher. `tracked_files()` returns `None` — never an empty set — when the target is not a
   repository or git fails, so callers degrade to `UNKNOWN` rather than infer. One scoped matcher
   answers "is this path ignored?" for the walk and for `DOC-03`, `CON-03`, `SEC-01` and `SEC-03`
   ([ADR-0009](0009-nested-ignore-files-and-negation.md)). Its semantics are a **documented subset**
   (`UNKNOWN`, never `PASS`, when certainty is unavailable).
2. **`audit/rules/checks/_common.py`** is a **private** module holding the shared verb resolver
   (`resolve_verbs`) and fenced-command extractor (`extract_fenced_commands`). It is deliberately
   **absent from `MODULE_NAMES`** in `audit/rules/checks/__init__.py`: the registry must not load it,
   because it defines no `IMPLEMENTATIONS` and is not a pack. Packs import it directly.
3. **These are internal helpers with no public contract and no rule-pack status.** They are not part
   of the CLI, the catalogue, or `ruleset_hash`, and nothing outside `audit/` may depend on them.
   They may be reshaped when real usage in units 03–13 shows which helpers are genuinely shared; a
   thin `_common.py` beats a speculative one.

## Alternatives Considered

| Alternative | Why it is rejected |
|---|---|
| Duplicate the logic in each pack | Guarantees drift: two checks reading one manifest under two subtly different rules will eventually disagree in one report. |
| Make ignore logic a new pipeline stage | It is not a stage — it is a query over traversal, which the walk and the checks both ask. |
| Fold the helpers into `audit/stack.py` or `audit/components.py` | Wrong responsibility: stack detection classifies ecosystems, it does not resolve the verbs or read ignore files. |
| Add `_common` to `MODULE_NAMES` so the registry loads it | The registry wires checks to implementations; a module with no `IMPLEMENTATIONS` has no place there, and listing it would imply rule-pack status it does not have. |
| Depend on a gitignore-parsing / YAML / TOML library | Violates the stdlib-only constraint that lets the audit run before the target's toolchain exists (ADR-0005). |
| Make the helpers a public, semver'd API | No external consumer exists; a public contract here would freeze crude, deliberately-partial parsers before they have been shaped by use. |

## Consequences

### Positive

* One answer to "what verbs exist?" and one to "does an ignore rule cover this path?", shared by the walk
  and every pack that asks, so the answers cannot diverge within a report.
* `tracked_files()` returning `None` makes "git could not answer" a representable state, which keeps
  the `UNKNOWN`-never-`PASS` invariant (ADR-0004 line of reasoning) enforceable at the call site.
* `MODULE_NAMES` keeps meaning "one entry per rule pack", and `--list-checks` is unaffected because
  the helper module adds no checks.

### Negative / Trade-offs

* Two helper modules exist that ADR-0005's stage/pack map does not name. They are infrastructure,
  not stages or packs, and this ADR is where that distinction is recorded.
* The Taskfile and pyproject readers are deliberately shallow (no YAML/TOML library). They are
  documented as crude and are expected to be refined as implementation units adopt them.
* Because there is no public contract, a helper signature may change without a deprecation path.
  That is intentional for internal code exercised only by this repository's own test suite.
