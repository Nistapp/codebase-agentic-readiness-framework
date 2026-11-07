# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Real git repositories for tests: a clean environment, so that the machine's own git settings cannot change a result.

A test imports this module for the repositories it needs a target to be. Nothing here touches the network or the
user's git configuration.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Sequence


def git_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    return environment


def run_git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, env=git_environment())
    return done.stdout.strip()


def make_repo(root: Path, files: Sequence[str] = ("README.md",), *, commit: bool = True, branch: str = "main") -> None:
    """Turn `root` into a git repository holding `files`, on `branch`, with one commit unless `commit` is false.

    `git commit`'s own auto-gc check (`maybe_auto_gc`) can fork a background `git gc`/`git maintenance`
    process that keeps rewriting `.git/objects/` after this function returns — observed on macOS CI,
    where it raced a later snapshot's read of an object file's size, and separately created and removed
    a `maintenance.lock` mid-walk. Both are this repository's own commit triggering it, not an external
    scheduler, so disabling it locally before the first commit is the actual fix, not a tolerance for it.
    """
    root.mkdir(parents=True, exist_ok=True)
    for name in files:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("x\n", encoding="utf-8")
    run_git(root, "init", "-q", "-b", branch)
    run_git(root, "config", "gc.auto", "0")
    run_git(root, "config", "maintenance.auto", "false")
    if commit:
        run_git(root, "add", "-A")
        run_git(root, "commit", "-q", "-m", "x")
