# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Puts the greenfield scaffolder on `sys.path` and runs it in-process, for the scaffolder's tests.

A test imports this module first. The unittest runner starts in this tests folder, which does not hold
``bootstrap.py``; ``greenfield/bootstrap/`` is not a package. The scaffolder runs in-process (``bootstrap.main``),
never as a subprocess, so coverage.py measures it.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
from pathlib import Path

BOOTSTRAP = Path(__file__).resolve().parents[1]
REPO = BOOTSTRAP.parents[1]
TEMPLATES = REPO / "greenfield" / "templates"

if str(BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP))

import bootstrap as bootstrap  # noqa: E402  (re-exported for the tests)

#: The identity flags every in-process run passes, so no test reads the developer's git config.
IDENTITY = ["--author", "Ada Lovelace", "--email", "ada@example.com", "--github-owner", "ada"]


def run_main(argv: list[str]) -> tuple[int, str, str]:
    """Run ``bootstrap.main(argv)``; return the exit code, stdout and stderr."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = bootstrap.main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue(), err.getvalue()


def copy_templates(dest: Path) -> Path:
    """A copy of this checkout's templates under ``dest``, for a test that edits the template tree."""
    copy = dest / "templates"
    shutil.copytree(TEMPLATES, copy)
    return copy
