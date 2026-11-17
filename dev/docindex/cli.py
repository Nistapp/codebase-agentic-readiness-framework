# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The document index's command line. The project entry point, ``dev/doc_index.py``, calls :func:`main`.

Four subcommands::

    build                 write the index of the working tree to stdout, as JSON
    diff <git-ref>        compare the index at <git-ref> with the index of the working tree
    sweep                 list the normative items of the sweep scope
    query <address>       show one node and its edges

Only ``build`` works yet, and it writes an empty index. The others print ``not implemented yet`` on stderr and exit
1. A usage error exits 2 (argparse). Output goes to stdout; diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Mapping, Sequence

from .model import Index, to_json

PROG = "doc_index.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROG, description="Build, compare, sweep and query the document index.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    commands.add_parser("build", help="write the index of the working tree to stdout as JSON")
    diff = commands.add_parser("diff", help="compare the index at a git ref with the working tree")
    diff.add_argument("ref", metavar="GIT_REF", help="the git ref to compare with")
    commands.add_parser("sweep", help="list the normative items of the sweep scope")
    query = commands.add_parser("query", help="show one node and its edges")
    query.add_argument("address", metavar="ADDRESS", help="a file path, a section address or an ID")
    return parser


def _build(config: Mapping[str, Any]) -> int:
    sys.stdout.write(to_json(Index()))
    return 0


def main(argv: Sequence[str] | None = None, config: Mapping[str, Any] | None = None) -> int:
    """Run one subcommand and return its exit code. ``config`` is the project config the entry point loaded."""
    args = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.command == "build":
        return _build(config or {})
    print(f"{PROG} {args.command}: not implemented yet", file=sys.stderr)
    return 1
