#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna
#
# Run the audit recipe headlessly with Claude Code, unattended, and record what it cost (DP §11, review R-07).
#
#   run-claude.sh <target> <out-dir> [<repo-label>]
#
# <target> is the repository to audit, as an absolute path. <out-dir> is where the recipe's own report
# files land (outside the target, per the tool contract); it must already exist. <repo-label> defaults to
# <target>'s directory name.
#
# An intake file, <out-dir>/audit-intake.<repo-label>.json, must already exist with "eval_mode": true and a
# fixed "confirmation_policy" ("accept-all" or "defer-all") — Stage 0 of the recipe then never has to ask a
# question, which is what makes the run unattended rather than scripted past a real refusal (review R-07).
#
# This script runs with --dangerously-skip-permissions, because an unattended run cannot answer a permission
# prompt either. That is an eval-harness choice, not a recommendation for a real audit: a real run still
# reaches target commands only through the engine's own Tier-C probe runner (review R-08), and the operator
# still decides whether to run this inside a disposable worktree or container. KC approved this script and
# its use of that flag explicitly (S4.1.3).
#
# Writes, in <out-dir>:
#   <repo-label>.harness-run.<stamp>.json      harness, model, started_at, duration_s, cost/tokens
#                                               (best-effort, whatever the harness's own --output-format
#                                               json reports), and the exit code.
#   <repo-label>.harness-transcript.<stamp>.jsonl   the harness's raw --output-format json line, unparsed.
#
# Needs: claude (Claude Code) on PATH, already logged in. python3 for the timestamp and JSON. Nothing is
# installed. No network call of this script's own; whatever the recipe itself does is the recipe's affair.

set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: run-claude.sh <target> <out-dir> [<repo-label>]" >&2
  exit 1
fi

TARGET=$(cd "$1" && pwd)
OUT_DIR=$(cd "$2" && pwd)
REPO_LABEL="${3:-$(basename "$TARGET")}"

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FRAMEWORK=$(cd "$HERE/../../.." && pwd)
KICKOFF="$FRAMEWORK/brownfield-recipes/audit/prompts/kickoff.md"

if [ ! -f "$KICKOFF" ]; then
  echo "run-claude.sh: cannot find the kickoff prompt at $KICKOFF" >&2
  exit 1
fi

INTAKE="$OUT_DIR/audit-intake.$REPO_LABEL.json"
if [ ! -f "$INTAKE" ]; then
  echo "run-claude.sh: no intake file at $INTAKE; write one with eval_mode: true before running headless" >&2
  exit 1
fi

PROMPT=$(sed "s#<path to the repository>#$TARGET#" "$KICKOFF")
PROMPT="$PROMPT
Use the intake file at $INTAKE. Write every output file into $OUT_DIR."

STAMP=$(python3 -c "import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))")
TRANSCRIPT="$OUT_DIR/$REPO_LABEL.harness-transcript.$STAMP.jsonl"
SUMMARY="$OUT_DIR/$REPO_LABEL.harness-run.$STAMP.json"

STARTED_AT=$(python3 -c "import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat())")
START_S=$(date +%s)
EXIT_CODE=0
claude -p "$PROMPT" \
  --add-dir "$TARGET" --add-dir "$OUT_DIR" \
  --output-format json \
  --dangerously-skip-permissions \
  >"$TRANSCRIPT" 2>"$OUT_DIR/$REPO_LABEL.harness-stderr.$STAMP.log" || EXIT_CODE=$?
END_S=$(date +%s)
DURATION_S=$((END_S - START_S))

python3 - "$TRANSCRIPT" "$SUMMARY" "$REPO_LABEL" "$STARTED_AT" "$DURATION_S" "$EXIT_CODE" <<'PY'
import json
import sys

transcript_path, summary_path, repo_label, started_at, duration_s, exit_code = sys.argv[1:7]

harness_data = {}
try:
    with open(transcript_path, encoding="utf-8") as handle:
        text = handle.read().strip()
    if text:
        harness_data = json.loads(text)
except (OSError, ValueError):
    harness_data = {}

summary = {
    "repo_label": repo_label,
    "harness": "claude-code",
    "model": harness_data.get("model"),
    "started_at": started_at,
    "duration_s": int(duration_s),
    "exit_code": int(exit_code),
    "cost_usd": harness_data.get("total_cost_usd", harness_data.get("cost_usd")),
    "num_turns": harness_data.get("num_turns"),
    "usage": harness_data.get("usage"),
}
with open(summary_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)
    handle.write("\n")
print(f"run-claude: {repo_label} in {duration_s}s, exit {exit_code}, summary at {summary_path}")
PY

exit "$EXIT_CODE"
