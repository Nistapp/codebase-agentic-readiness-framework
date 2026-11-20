# 0005. A Lost Pass Stops the Theme Until the Owner Decides

## Context

A theme of the implement recipe changes files to close its own findings. The same change can break an engine check
the theme does not own: a deleted `.mcp.json` turns "`IDX-01` codebase-memory-mcp registered" from `PASS` to `FAIL`.
The theme's own checks are compared with the audit report, but that report is older than the theme. It was taken at
another commit, often on another path, and earlier themes have changed the tree since. So it cannot tell what this
theme broke.

[`theme-checks.md`](../../../theme-checks.md#keep-passing-checks-passing) runs the engine on the theme worktree
twice. The base report comes before the first change (Stage 3, step 3), the close report at theme close (Stage 4,
step 1).
[`tools/check_regressions.py`](../../../tools/check_regressions.py) compares the two. A full engine run takes a few
seconds, so the close run costs little more than Stage 4 already paid.

## Decision

1. **Classes.** The tool compares the two reports check by check, by id. A check in `not_applicable` has the
   verdict `NOT_APPLICABLE`; a check in neither list is missing.
   - **Lost pass:** `PASS` at base, anything else at close (`PARTIAL`, `FAIL`, `UNKNOWN`, `NOT_APPLICABLE` or
     missing).
   - **Regressed:** `PARTIAL` at base, `FAIL` at close.
   - **Other moves:** improved (up along `FAIL < PARTIAL < PASS`), changed, added and removed.
   - **Evidence change:** the verdict holds, but the `summary`, a `data` key or a finding differs.
2. **A lost pass or a regression stops the theme.** The tool sets `data.status` to `lost` and exits 0. The agent
   stops and sends the owner a decision request with three answers:
   - (a) fix it in the theme, then take the close report and compare again;
   - (b) accept it with the owner's reason, recorded on the item with `progress.py set-status ... --note`;
   - (c) stop the theme here.

   There is no default; the agent waits.
3. **Other moves and evidence changes are reported, never a stop.** With `--changed-from <worktree>`, each listed
   check carries the places of its read declaration (the engine's `audit.rules.reads`) that a changed path meets.
4. **An unattributed change is flagged, not fixed.** A listed check that no changed path explains gets
   `unattributed: true`. It may be a gap in the engine's read declarations, which belongs to the framework. The run
   changes nothing in the target for it.
5. **The tool refuses a pair it cannot lay on the theme (exit 2).** The reports differ in ruleset hash, target,
   phase, user-config reading, probes on or off, or the probe verbs allowed. Or the close report is not newer than
   the base report. The agent says the lost-pass check did not run, and names the reasons.
6. **Every engine check counts, not only the theme's.** The read declarations explain a change; they never choose
   which checks are compared.

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| Compare only the theme's checks with the audit report | The audit report is older than the theme, and checks outside the theme go unseen. |
| A recipe step only: the agent compares the two reports itself | The agent would compare every engine check by hand, and no test could hold the comparison. |
| Compare only the checks whose declared reads a changed path meets | Some checks read every path, others read through an upstream step, and a missing declaration would hide a real break. |
| Stop only on a lost `PASS`, not on `PARTIAL` to `FAIL` | A worse non-pass is a break too. |
| Stop on an evidence change that a check outside the theme reads | A new docs page moves the evidence of "`DOC-05` Docs are readable" with no harm, so the theme would stop for nothing. |

## Consequences

### Positive

- A theme cannot quietly break a passing check: the owner decides each lost pass, and an accepted one carries a
  reason on the item.
- The comparison is deterministic: the same two reports give the same answer, and tests hold it.
- Unattributed changes feed back into the engine's read declarations.

### Negative / Trade-offs

- One more engine run per theme, and one more decision request when a pass is lost.
- A theme with no base report, or a refused pair, gets no lost-pass check. The agent says so.
- The two agent checks in the catalogue have no engine verdict, so this check does not cover them.
- Nothing stops an agent that reads `lost` and goes on; the rule lives in the recipe.
