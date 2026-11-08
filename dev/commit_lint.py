# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Check that commit subjects follow Conventional Commits: ``type(scope)!: subject``.

    commit_lint.py --range <base>..<head>   every non-merge commit in the range (CI, ``make commit-lint``)
    commit_lint.py --message-file <file>    the first line of one message (the lefthook ``commit-msg`` hook)

Exit 0 when every subject passes, 1 when one fails (each failure is printed), 2 on a usage or git error. The rule
lives here only: ``lefthook.yml`` and ``.github/workflows/ci.yml`` call this script. The ``Roadmap-Step:`` trailer
is checked in review, not here. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

TYPES = ("feat", "fix", "docs", "test", "chore", "ci", "refactor", "perf", "build", "style", "revert")
SUBJECT = re.compile(r"^(?:" + "|".join(TYPES) + r")(?:\([a-z0-9._-]+\))?!?: \S.*$")


def valid(subject: str) -> bool:
    """True when ``subject`` is a Conventional Commits subject with one of :data:`TYPES`."""
    return SUBJECT.match(subject) is not None


def subjects_in_range(revision_range: str) -> list[tuple[str, str]]:
    """``(short sha, subject)`` for each non-merge commit in ``revision_range``, oldest first."""
    result = subprocess.run(
        ["git", "log", "--no-merges", "--reverse", "--format=%h%x00%s", revision_range],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git log failed for {revision_range}")
    pairs = []
    for line in result.stdout.splitlines():
        sha, _, subject = line.partition("\x00")
        pairs.append((sha, subject))
    return pairs


def first_line(path: Path) -> str:
    """The subject of a commit message file: its first line that is not a git comment."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            return line.rstrip()
    return ""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--range", dest="revision_range", help="a git revision range, for example origin/dev..HEAD")
    group.add_argument("--message-file", type=Path, help="a commit message file, as git passes to commit-msg")
    args = parser.parse_args(argv)

    try:
        if args.revision_range:
            pairs = subjects_in_range(args.revision_range)
        else:
            pairs = [("message", first_line(args.message_file))]
    except (RuntimeError, OSError) as exc:
        print(f"commit_lint: {exc}", file=sys.stderr)
        return 2

    bad = [(sha, subject) for sha, subject in pairs if not valid(subject)]
    for sha, subject in bad:
        print(f"commit_lint: {sha}: not a Conventional Commits subject: {subject!r}", file=sys.stderr)
    if bad:
        print(f"commit_lint: use type(scope): subject, with a type from: {', '.join(TYPES)}", file=sys.stderr)
        return 1
    print(f"commit_lint: {len(pairs)} subject(s) checked, all follow Conventional Commits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
