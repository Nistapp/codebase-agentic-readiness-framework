# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Compare one tool's violation count with the committed quality baseline; fail when the count went up.

    quality_baseline.py check TOOL [--baseline FILE] -- COMMAND...

``TOOL`` is ``ruff``, ``mypy``, ``markdownlint`` or ``prose`` (``dev/prose_check.py``). The command after ``--`` is the tool's own read-only full-tree run;
its output is parsed into one number and compared with the entry for ``TOOL`` in ``.quality-baseline.json``:

* count above the baseline: exit 1, naming the tool and both numbers;
* count equal: exit 0;
* count below the baseline: exit 0, with a request to lower the baseline in the same change. The script never rewrites
  the file: a baseline only goes down, by a reviewed edit.

This is the framework's own copy of the compare step that the ``add-baselines-and-ratchet`` playbook describes
(BASE-03). Dev-only: CI runs it through the Makefile, nothing in ``tools/`` or the engine imports it. Standard library
only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_BASELINE = Path(".quality-baseline.json")
TOOLS = ("ruff", "mypy", "markdownlint", "prose")

_MARKDOWNLINT_SUMMARY = re.compile(r"^Summary:\s+(\d+)\s+issues?\b", re.MULTILINE)


def count_ruff(output: str) -> int:
    """Number of diagnostics in ``ruff check --output-format json``."""
    data = json.loads(output)
    if not isinstance(data, list):
        raise ValueError("ruff JSON output is not a list")
    return len(data)


def count_mypy(output: str) -> int:
    """Number of ``error:`` lines in mypy's output (notes are not violations)."""
    return sum(1 for line in output.splitlines() if ": error:" in line)


def count_markdownlint(output: str) -> int:
    """The ``Summary: N issues`` line of markdownlint-cli2; a clean run prints no summary issue count."""
    match = _MARKDOWNLINT_SUMMARY.search(output)
    if match:
        return int(match.group(1))
    if re.search(r"^Summary:\s+0\s+error", output, re.MULTILINE):
        return 0
    raise ValueError("no 'Summary: N issues' line in markdownlint output")


_PROSE_SUMMARY = re.compile(r"^Summary: (\d+) issues? in \d+ files?$", re.MULTILINE)


def count_prose(output: str) -> int:
    """The ``Summary: N issues in M files`` line of ``dev/prose_check.py``."""
    match = _PROSE_SUMMARY.search(output)
    if not match:
        raise ValueError("no 'Summary: N issues in M files' line in prose_check output")
    return int(match.group(1))


PARSERS = {"ruff": count_ruff, "mypy": count_mypy, "markdownlint": count_markdownlint, "prose": count_prose}


def load_baseline(path: Path, tool: str) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data["counts"][tool]
    count = entry["count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError(f"{path}: counts.{tool}.count must be a non-negative integer")
    return count


def compare(tool: str, current: int, baseline: int) -> tuple[int, str]:
    """Exit code and the message for one tool."""
    if current > baseline:
        return 1, (
            f"quality baseline: {tool} has {current} violations, the baseline allows {baseline}. "
            "A baseline only goes down: fix the new violations; raising it needs the owner."
        )
    if current < baseline:
        return 0, (
            f"quality baseline: {tool} is down to {current} (baseline {baseline}). "
            f"Lower counts.{tool}.count to {current} in the same change so the gain is kept."
        )
    return 0, f"quality baseline: {tool} holds at {current}."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="verb", required=True)
    check = sub.add_parser("check", help="run the tool and compare its count with the baseline")
    check.add_argument("tool", choices=TOOLS)
    check.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="counts file (default: %(default)s)")
    raw = sys.argv[1:] if argv is None else argv
    head, sep, command = (raw[: raw.index("--")], True, raw[raw.index("--") + 1 :]) if "--" in raw else (raw, False, [])
    args = parser.parse_args(head)
    if not sep or not command:
        print("quality baseline: no command given after --", file=sys.stderr)
        return 2
    try:
        baseline = load_baseline(args.baseline, args.tool)
    except (OSError, KeyError, ValueError) as exc:
        print(f"quality baseline: cannot read the {args.tool} entry of {args.baseline}: {exc}", file=sys.stderr)
        return 2
    try:
        run = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        print(f"quality baseline: cannot run {command[0]}: {exc}", file=sys.stderr)
        return 2
    try:
        # ruff's JSON and prose_check's summary are on stdout alone; mypy and markdownlint-cli2 split their report
        # across both streams.
        text = run.stdout if args.tool in ("ruff", "prose") else run.stdout + "\n" + run.stderr
        current = PARSERS[args.tool](text)
    except ValueError as exc:
        print(f"quality baseline: cannot read the {args.tool} output: {exc}", file=sys.stderr)
        return 2
    code, message = compare(args.tool, current, baseline)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
