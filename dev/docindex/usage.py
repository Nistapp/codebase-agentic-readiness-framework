# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The argument parser of every ``doc_index.py`` command: a usage error exits 1, not argparse's 2.

Exit 2 is kept for a failed check (a quote that fails, an ``evidence run`` that is refused), as the house tool
contract keeps it for a failed validation (``audit/tools/README.md``). ``--help`` still exits 0. This module imports
nothing outside the standard library.
"""

from __future__ import annotations

import argparse
import sys
from typing import NoReturn

__all__ = ["USAGE_EXIT", "UsageParser"]

#: The exit code of a usage error.
USAGE_EXIT = 1


class UsageParser(argparse.ArgumentParser):
    """A parser whose usage error prints the usage and the message to stderr and exits :data:`USAGE_EXIT`.

    Its subparsers are of the same class, as ``add_subparsers`` makes them by default.
    """

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(USAGE_EXIT, f"{self.prog}: error: {message}\n")
