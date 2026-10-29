# Check files

> **Audience:** Agents running the audit recipe, and the people who write or review these files.
> **Scope:** Governs every `NN-*.md` file in this folder. One file per check family (`catalogue.json`'s
> `family`), in catalogue order.

---

## 1. Anatomy

Every check in a family file follows this fixed shape, so an agent reads each the same way:

```
## <CHECK-ID> — <title>
Why it matters   (one sentence, links to the framework section this check anchors)
Severity         BLOCKER | DEGRADER | COSMETIC
Engine           the engine ID, what it reads, when its verdict can be wrong, how to verify it independently
                 — or "none" for an agent-only check
Method           automated | agent (catalogue.json's method for this check)
Look for         what evidence to gather, and where to look first (index query, then file search)
Rubric           PASS: ...   PARTIAL: ...   FAIL: ...   NOT_APPLICABLE: ...   UNKNOWN when: ...
Evidence to cite exactly what must appear in evidence[] (report.py add-check / add-finding)
Absence proof    the searches[] entries a FAIL must record
Remediation      playbook id(s), as catalogue.json names them for this check
Pitfalls         known false positives / false negatives
```

`<CHECK-ID>` and `<title>` are `catalogue.json`'s `id` and `title` for the check, unchanged. `Severity`,
`Method` and `Remediation`'s playbook ids also come from `catalogue.json`; a check file never invents a
value the catalogue does not already carry, so the recipe linter's check, requirement and playbook
references stay meaningful.

## 2. Two fields beyond DP §5.2

- **Engine.** Every engine check (`method: automated`) names its engine ID, what that check reads inside
  the target, the condition under which its verdict should be distrusted (stale index, a tool the engine
  cannot see, a convention it does not recognise), and the independent step that resolves the doubt. An
  agent-only check (`method: agent`, today `AGT-11` and `CI-04`) writes `none` here — there is no engine
  verdict to carry or dispute.
- **Method.** One word, `automated` or `agent`, repeating `catalogue.json`'s own field, so the rubric is
  readable without a second lookup.

## 3. Rubric thresholds are observable

A rubric names what is counted, measured or matched — a file that exists, a pattern that is present, a
number compared against a stated limit — never an adjective ("reasonable", "sufficient", "clear"). This is
the rubric's job as the lever for consistency across models (DP §5.2): two readings of the same repository
against the same rubric text should reach the same verdict.

## 4. A FAIL lists its absence searches

A verdict of FAIL that rests on "this does not exist" must record the searches that looked for it, as
`searches[]` entries (`report.py`'s `add-check`/`add-finding` contract): the tool (`glob`, `grep` or
`index`), the pattern, the scope searched and the hit count. A FAIL with no search recorded is not
distinguishable from a verdict reached by not looking, so the absence proof is not optional on that path.

## 5. One family, one file

Each file is this folder's single source for its family: `04-command-surface.md` holds every `CMD-*`
check, nothing is duplicated across two files, and a check that moves families is a rename of its section,
not a copy. The recipe linter's size rule (500 lines, shared with `SKILL.md`, D46) applies to each file, so
a family that outgrows the budget splits by check number into two files (S3.3.5 does this for `HYG`), each
still following this anatomy.

## 6. How a verdict is recorded

The anatomy's `Evidence to cite` and `Absence proof` fields describe what goes into the report, not how:
`report.py add-check` records an engine check's agreement or override (with `override_reason` when the
verdict differs from `engine_verdict`); `report.py add-finding` records the issue a FAIL or PARTIAL raises,
with its own `evidence[]` and `searches[]`. Both are schema-shaped (`schema/audit-report.schema.json`): an
`evidence` item's `kind` (`file`, `command` or `index_query`) decides which of its fields apply, and
`captured_by` says whether a tool or the agent recorded it.
