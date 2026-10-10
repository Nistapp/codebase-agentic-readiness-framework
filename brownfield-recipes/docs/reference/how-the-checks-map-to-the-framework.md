# How the Checks Map to the Framework

> **Audience:** Everyone
> **Source of truth:** [`catalogue.json`](../../catalogue.json) and [`spec/readiness-requirements.md`](../../../spec/readiness-requirements.md)
> **Status:** Live for the method below. A generated table of every check is planned.

> [!NOTE]
> Planned. A table of all checks with their framework sections, generated from the catalogue at release, is filled in by roadmap step S4.6. Until then the relation is held in the files named below and by [`spec/traceability.md`](../../../spec/traceability.md).

---

## Summary

| Item | Description |
|---|---|
| `check ID` | Catalogue entry, e.g. `CMD-02` |
| `requirement ID` | Spec entry, e.g. `REQ-SH-022` |
| `framework anchor` | The heading a requirement's `Source` field links, in the framework's documents |

---

## Following a check to the framework

A check reaches the framework through a requirement. Three steps, shown for `CMD-02`.

1. **Find the check in the catalogue.** In [`catalogue.json`](../../catalogue.json), the entry `CMD-02` ("`check` composes the read-only verbs", a BLOCKER) has `req_ids` of `["REQ-SH-022"]`.
2. **Read the requirement.** [REQ-SH-022](../../../spec/readiness-requirements.md#req-sh-022--check-composes-the-read-only-verbs) says "The `check` verb MUST run `format:check`, `typecheck` and `test`." Its `Checks` field names `CMD-02` back.
3. **Follow its `Source`.** The field links [greenfield-bootstrap/README.md § 1.4, The standardized command surface](../../../greenfield-bootstrap/README.md#14-the-standardized-command-surface--seven-verbs), the framework heading the rule comes from.

To go the other way, start from a framework heading, find the requirements whose `Source` links it, and read their `Checks` fields.

## Where the relation is held

| File | Holds | Kept true by |
|---|---|---|
| [`catalogue.json`](../../catalogue.json) | Each check's `req_ids` | [`test_catalogue.py`](../../tools/tests/test_catalogue.py) |
| [`readiness-requirements.md`](../../../spec/readiness-requirements.md) | Each requirement's `Checks` and `Source` | The same test, for `Checks` |
| [`traceability.md`](../../../spec/traceability.md) | The check-to-requirement table, for reading | The same test |

A requirement can be derived, meaning the framework does not say it in so many words. [`traceability.md`](../../../spec/traceability.md#derived-requirements) lists those.
