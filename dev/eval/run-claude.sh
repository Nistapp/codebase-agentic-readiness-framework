#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna
#
# Run a recipe headlessly with Claude Code, unattended, and record what it cost (DP §11, review R-07).
#
#   run-claude.sh [--recipe audit|implement] [--answers <file>] [--model <model>] [--max-budget-usd <n>]
#                 <target> <out-dir> [<repo-label>]
#
# --recipe audit (the default) runs the audit recipe. <target> is the repository to audit, as an absolute path.
# <out-dir> is where the recipe's own report files land (outside the target, per the tool contract); it must
# already exist. <repo-label> defaults to <target>'s directory name. An intake file,
# <out-dir>/audit-intake.<repo-label>.json, must already exist with "eval_mode": true and a fixed
# "confirmation_policy" ("accept-all" or "defer-all"): Stage 0 of the recipe then never has to ask a question,
# which is what makes the run unattended rather than scripted past a real refusal (review R-07).
#
# --recipe implement runs the implement recipe on one eval scenario that `implement_eval.py materialise` laid out
# (IR13). <target> is then that scenario's root, and this script refuses to run unless the root is contained: it
# sits under ${TMPDIR:-/tmp}, holds eval-baseline.json, its repo/ has exactly one remote, origin, which is the
# local bare repository <root>/origin.git (so a push reaches nothing outside the root), and <root>/bin/gh is the
# logging shim (it records every call in <root>/gh-calls.log and exits 1, so no pull request is opened and any merge
# attempt is on record). <root>/bin goes first on PATH. The prompt is the implement kickoff with its fill-ins set
# (the repository, the report the baseline names, dev as the integration branch), followed by the canned owner
# answers from --answers, which is required. The agent works from <root>/framework, the copy of the recipe
# materialise made, with no MCP servers, no user-level settings and no saved session. The transcript is
# --output-format stream-json --verbose, so every tool call the agent made is on record for the assertions.
#
# This script runs with --dangerously-skip-permissions, because an unattended run cannot answer a permission
# prompt either. That is an eval-harness choice, not a recommendation for a real run: a real audit still reaches
# target commands only through the engine's own Tier-C probe runner (review R-08), and the operator still decides
# whether to run it inside a disposable worktree or container. KC approved this script and its use of that flag
# explicitly (S4.1.3), and approved the implement mode with the containment above, keeping the flag (IR13, Q2).
#
# Writes, in <out-dir>:
#   <repo-label>.harness-run.<stamp>.json         harness, recipe, model, started_at, duration_s, cost/tokens
#                                                  (best-effort, whatever the harness reports), and the exit code.
#   <repo-label>.harness-transcript.<stamp>.jsonl  the harness's raw output: one JSON line (audit) or the
#                                                  stream-json events (implement), unparsed.
#   <repo-label>.harness-stderr.<stamp>.log        the harness's stderr.
#
# Needs: claude (Claude Code) on PATH, already logged in; git and python3. Nothing is installed. No network call
# of this script's own; whatever the recipe itself does is the recipe's affair.

set -euo pipefail

usage() {
  echo "usage: run-claude.sh [--recipe audit|implement] [--answers <file>] [--model <model>] [--max-budget-usd <n>] <target> <out-dir> [<repo-label>]" >&2
  exit 1
}

RECIPE=audit
ANSWERS=""
MODEL=""
BUDGET=""
POSITIONAL=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --recipe) [ "$#" -ge 2 ] || usage; RECIPE="$2"; shift 2 ;;
    --answers) [ "$#" -ge 2 ] || usage; ANSWERS="$2"; shift 2 ;;
    --model) [ "$#" -ge 2 ] || usage; MODEL="$2"; shift 2 ;;
    --max-budget-usd) [ "$#" -ge 2 ] || usage; BUDGET="$2"; shift 2 ;;
    --*) usage ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done
[ "${#POSITIONAL[@]}" -ge 2 ] || usage
case "$RECIPE" in audit|implement) ;; *) usage ;; esac

TARGET=$(cd "${POSITIONAL[0]}" && pwd -P)
OUT_DIR=$(cd "${POSITIONAL[1]}" && pwd -P)
REPO_LABEL="${POSITIONAL[2]:-$(basename "$TARGET")}"

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FRAMEWORK=$(cd "$HERE/../.." && pwd)

EXTRA=()
[ -n "$MODEL" ] && EXTRA+=(--model "$MODEL")
[ -n "$BUDGET" ] && EXTRA+=(--max-budget-usd "$BUDGET")

fail() {
  echo "run-claude.sh: $1" >&2
  exit 1
}

if [ "$RECIPE" = audit ]; then
  [ -z "$ANSWERS" ] || fail "--answers is for --recipe implement"
  KICKOFF="$FRAMEWORK/audit/prompts/kickoff.md"
  [ -f "$KICKOFF" ] || fail "cannot find the kickoff prompt at $KICKOFF"
  INTAKE="$OUT_DIR/audit-intake.$REPO_LABEL.json"
  [ -f "$INTAKE" ] || fail "no intake file at $INTAKE; write one with eval_mode: true before running headless"
  PROMPT=$(sed "s#<path to the repository>#$TARGET#" "$KICKOFF")
  PROMPT="$PROMPT
Use the intake file at $INTAKE. Write every output file into $OUT_DIR."
  WORKDIR="$PWD"
  CLAUDE_ARGS=(--add-dir "$TARGET" --add-dir "$OUT_DIR" --output-format json)
else
  ROOT="$TARGET"
  TMP_BASE=$(cd "${TMPDIR:-/tmp}" && pwd -P)
  case "$ROOT/" in "$TMP_BASE"/*) ;; *) fail "an implement eval root must sit under $TMP_BASE, not $ROOT" ;; esac
  if [ -z "$ANSWERS" ] || [ ! -f "$ANSWERS" ]; then fail "--recipe implement needs --answers <file>"; fi
  [ -f "$ROOT/eval-baseline.json" ] || fail "$ROOT holds no eval-baseline.json; lay it out with implement_eval.py materialise"
  [ "$(git -C "$ROOT/origin.git" rev-parse --is-bare-repository 2>/dev/null)" = true ] || fail "$ROOT/origin.git is not a bare repository"
  [ "$(git -C "$ROOT/repo" remote)" = origin ] || fail "$ROOT/repo must have exactly one remote, origin"
  ORIGIN_URL=$(cd "$(git -C "$ROOT/repo" remote get-url origin)" 2>/dev/null && pwd -P || true)
  [ "$ORIGIN_URL" = "$ROOT/origin.git" ] || fail "origin of $ROOT/repo is not $ROOT/origin.git"
  if [ ! -x "$ROOT/bin/gh" ] || ! grep -q "gh-calls.log" "$ROOT/bin/gh"; then fail "$ROOT/bin/gh is not the logging shim"; fi
  KICKOFF="$ROOT/framework/implement/prompts/kickoff.md"
  [ -f "$KICKOFF" ] || fail "cannot find the implement kickoff at $KICKOFF"
  PROMPT=$(python3 - "$KICKOFF" "$ROOT" "$ANSWERS" <<'PY'
import json
import re
import sys
from pathlib import Path

kickoff, root, answers = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
block = re.search(r"```text\n(.*?)```", kickoff.read_text(encoding="utf-8"), re.DOTALL)
if block is None:
    sys.exit("run-claude.sh: the implement kickoff holds no text block")
report = json.loads((root / "eval-baseline.json").read_text(encoding="utf-8"))["report"]
text = (
    block.group(1)
    .replace("<path to the repository>", str(root / "repo"))
    .replace("<path to the report JSON inside it>", str(root / "repo" / report))
    .replace("<integration branch>", "dev")
)
print(text.rstrip())
print()
print(f"The framework checkout is {root / 'framework'}; run the tools from there.")
print()
print(answers.read_text(encoding="utf-8").rstrip())
PY
)
  export PATH="$ROOT/bin:$PATH"
  WORKDIR="$ROOT/framework"
  CLAUDE_ARGS=(--add-dir "$ROOT" --output-format stream-json --verbose --strict-mcp-config --setting-sources project
    --no-session-persistence)
fi

STAMP=$(python3 -c "import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))")
TRANSCRIPT="$OUT_DIR/$REPO_LABEL.harness-transcript.$STAMP.jsonl"
SUMMARY="$OUT_DIR/$REPO_LABEL.harness-run.$STAMP.json"

STARTED_AT=$(python3 -c "import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat())")
START_S=$(date +%s)
EXIT_CODE=0
(cd "$WORKDIR" && claude -p "$PROMPT" "${CLAUDE_ARGS[@]}" ${EXTRA[@]+"${EXTRA[@]}"} --dangerously-skip-permissions) \
  >"$TRANSCRIPT" 2>"$OUT_DIR/$REPO_LABEL.harness-stderr.$STAMP.log" || EXIT_CODE=$?
END_S=$(date +%s)
DURATION_S=$((END_S - START_S))

python3 - "$TRANSCRIPT" "$SUMMARY" "$REPO_LABEL" "$STARTED_AT" "$DURATION_S" "$EXIT_CODE" "$RECIPE" <<'PY'
import json
import sys

transcript_path, summary_path, repo_label, started_at, duration_s, exit_code, recipe = sys.argv[1:8]

harness_data = {}
try:
    with open(transcript_path, encoding="utf-8") as handle:
        lines = [line for line in handle.read().splitlines() if line.strip()]
    # One JSON line for --output-format json; for stream-json the last "result" event carries the totals.
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type", "result") == "result":
            harness_data = event
            break
except OSError:
    harness_data = {}

summary = {
    "repo_label": repo_label,
    "harness": "claude-code",
    "recipe": recipe,
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
