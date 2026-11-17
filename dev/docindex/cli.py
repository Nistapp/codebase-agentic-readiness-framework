# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The document index's command line. The project entry point, ``dev/doc_index.py``, calls :func:`main`.

Four subcommands::

    build                 write the index of the working tree to stdout, as JSON
    diff <git-ref>        compare the index at <git-ref> with the index of the working tree
    sweep [--at REF] [--format text|json] [--triggers group1|all]
                          list the normative items of the sweep scope (:mod:`docindex.sweep`)
    query <address>       show one node and its edges

``build`` writes an empty index yet. ``sweep`` reads the tracked files of the working tree, or with ``--at`` the
files at a git ref (``git show``, never a checkout); the scope is resolved in that tree, so a scope file that did not
exist there is skipped. In text mode it writes one block per item to stdout and the item count of each file to
stderr; in JSON mode the counts are in the JSON. ``diff`` and ``query`` print ``not implemented yet`` on stderr and
exit 1. A git failure (a ref that names no commit, a folder that is not a repository) exits 1. A usage error exits 2
(argparse). Output goes to stdout; diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import sweep
from .gitread import GitError, RefTree, Tree, WorkTree
from .model import Index, to_json

PROG = "doc_index.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROG, description="Build, compare, sweep and query the document index.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    commands.add_parser("build", help="write the index of the working tree to stdout as JSON")
    diff = commands.add_parser("diff", help="compare the index at a git ref with the working tree")
    diff.add_argument("ref", metavar="GIT_REF", help="the git ref to compare with")
    sweep_parser = commands.add_parser("sweep", help="list the normative items of the sweep scope")
    sweep_parser.add_argument("--at", metavar="GIT_REF", help="sweep the files at this git ref, not the working tree")
    sweep_parser.add_argument("--format", choices=("text", "json"), default="text", help="the output form (text)")
    sweep_parser.add_argument(
        "--triggers", choices=sweep.SELECTIONS, default="all", help="the trigger groups to use (all)"
    )
    query = commands.add_parser("query", help="show one node and its edges")
    query.add_argument("address", metavar="ADDRESS", help="a file path, a section address or an ID")
    return parser


def _build(config: Mapping[str, Any]) -> int:
    sys.stdout.write(to_json(Index()))
    return 0


def _sweep(
    args: argparse.Namespace,
    config: Mapping[str, Any],
    root: Path,
    bundle_sources: Callable[[], Sequence[str]] | None,
) -> int:
    try:
        triggers = sweep.select_triggers(config, args.triggers)
    except ValueError as exc:
        print(f"{PROG} sweep: {exc}", file=sys.stderr)
        return 1
    try:
        tree: Tree = RefTree(root, args.at) if args.at is not None else WorkTree(root)
        paths = sweep.scope(tree.files(), config, bundle_sources() if bundle_sources else ())
    except GitError as exc:
        print(f"{PROG} sweep: {exc}", file=sys.stderr)
        return 1
    report = sweep.sweep(tree, paths, triggers)
    if args.format == "json":
        sys.stdout.write(sweep.to_json(report, selection=args.triggers, at=args.at))
    else:
        sys.stdout.write(sweep.to_text(report))
        sys.stderr.write(sweep.summary(report))
    return 0


def main(
    argv: Sequence[str] | None = None,
    config: Mapping[str, Any] | None = None,
    *,
    root: Path | None = None,
    bundle_sources: Callable[[], Sequence[str]] | None = None,
) -> int:
    """Run one subcommand and return its exit code.

    ``config`` is the project config the entry point loaded. ``root`` is the repository root (the current folder
    when ``None``). ``bundle_sources`` returns the project's bundle sources, the files and folders the sweep scope
    starts from; the entry point reads them, so that this package imports no other ``dev/`` module.
    """
    args = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.command == "build":
        return _build(config or {})
    if args.command == "sweep":
        return _sweep(args, config or {}, root or Path.cwd(), bundle_sources)
    print(f"{PROG} {args.command}: not implemented yet", file=sys.stderr)
    return 1
