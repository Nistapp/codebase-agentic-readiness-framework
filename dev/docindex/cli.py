# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The document index's command line. The project entry point, ``dev/doc_index.py``, calls :func:`main`.

The subcommands::

    build [--at REF]      write the index of the working tree (or of the tree at REF) to stdout, as JSON
    diff <git-ref> [--at NEW] [--format text|json]
                          report what changed in the index from <git-ref> to NEW (:mod:`docindex.diff`)
    sweep [--at REF] [--format text|json] [--triggers group1|all]
                          list the normative items of the sweep scope (:mod:`docindex.sweep`)
    sweep --diff OLD [--at NEW] [--paths a,b,...] [--format text|json] [--triggers group1|all]
                          list the normative items at OLD that vanished by NEW (:mod:`docindex.sweep_diff`)
    sweep --recall COMMITS_JSON [--format text|json] [--triggers group1|all]
                          measure the removed lines of commits that lie in no normative item (:mod:`docindex.recall`)
    query <address> [--at REF] | query --report [--at REF]
                          show one node and its edges, or the reports (run by the entry point, not here)
    verify-quotes <folder> [--at REF]
                          check every quote the reports in <folder> cite (:mod:`docindex.quotes`)
    manifest [--out FILE] build the skill bundles into a temporary folder and write their manifest
                          (:mod:`docindex.manifest`)
    manifest-diff OLD.json NEW.json [--format text|json]
                          list the bundle files added, removed and changed from one manifest to another
    evidence run --out DIR [--target repo|fixtures]
                          run the audit engine into the fresh folder DIR and write a run record
                          (:mod:`docindex.evidence`)
    evidence compare OLD_DIR NEW_DIR [--format text|json]
                          list the checks whose verdict, or whose evidence under the same verdict, changed

``build`` writes the index of :mod:`docindex.extract` (file and section nodes, ``contains`` edges) to stdout, as
the deterministic JSON of :mod:`docindex.model`, and a summary of the counts (files, and the Markdown files and
sections per zone) to stderr. ``sweep`` reads the tracked files of the working tree, or with ``--at`` the
files at a git ref (``git show``, never a checkout); the scope is resolved in that tree, so a scope file that did not
exist there is skipped. In text mode it writes one block per item to stdout and the item count of each file to
stderr; in JSON mode the counts are in the JSON.

``sweep --diff OLD`` sweeps the scope at OLD and at NEW (``--at``, else the working tree) and compares them. With
``--paths``, a comma-separated list of files or folders, both sides sweep the files at or under those paths in place
of the scope, so a path that exists at one side only still works. ``sweep --recall`` reads a JSON list of commits
(``hash``, ``parent``, ``files``) from the path given, relative to the current folder. ``--diff`` and ``--recall``
exclude each other; ``--paths`` needs ``--diff``, and ``--recall`` takes no ``--at``.

``diff`` builds the index (:mod:`docindex.extract`) at <git-ref> and at NEW (``--at``, else the working tree), both
read with ``git show`` or from disk, never by a checkout, and writes the report of :mod:`docindex.diff` to stdout:
the sections added, removed, moved, renamed and edited, the edges lost and gained, and the IDs that lost their
definition or every mention. It is a report, so it exits 0 whatever it finds.

``query`` is routed by the entry point, ``dev/doc_index.py``, to :func:`docindex.ids.query_main`, which needs the
entry point's full config; called here, it says so on stderr and exits 1.

A git failure (a ref that names no commit, a folder that is not a repository) or an unreadable commits file exits 1.
A usage error that argparse finds (a missing or unknown argument) exits 2. Output goes to stdout; diagnostics go to
stderr.

``verify-quotes`` has its own exit codes: 0 when every quote and citation passes, 2 when one fails, and 1 on a usage
error (argparse's included, a folder that holds no ``quotes.json``, or with ``--at`` a ref that names no commit). The
folder is relative to the current folder; the quoted paths are relative to the repository root. It writes each
failure (id, path, reason) to stderr and a one-line count to stdout.

``manifest`` makes a fresh temporary folder, has the entry point's ``build_bundles`` build every bundle into it
(never into the project's own build folder), and writes the manifest of :func:`docindex.manifest.manifest` to
``--out`` (relative to the current folder) or to stdout; the folder is deleted afterwards. A failed build exits 1.
``manifest-diff`` reads two manifests (paths relative to the current folder) and writes the report of
:func:`docindex.manifest.compare`; it is a report, so it exits 0 whatever it finds, and 1 when a manifest cannot be
read.

``evidence run`` needs the entry point's :class:`docindex.evidence.Project` (the engine folder, the repository and the
targets). DIR is relative to the current folder; it must not exist or must be empty, and must lie outside the
repository. The targets (``repo`` by default) are prepared in a temporary folder that is deleted afterwards. It exits
0 when every report is written, 2 when the run is refused (DIR not fresh or inside the repository, a report missing
or older than the run's start), and 1 when a command fails. ``evidence compare`` reads two run folders and writes the
report of :func:`docindex.evidence.compare`; it is a report, so it exits 0 whatever it finds, and 1 when a run folder
cannot be read or the two runs have different targets.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, NoReturn, Sequence

from . import diff as index_diff
from . import evidence, extract, manifest, quotes, recall, sweep, sweep_diff
from .gitread import GitError, RefTree, Tree, WorkTree
from .model import to_json

PROG = "doc_index.py"
VERIFY_QUOTES = "verify-quotes"


class _ExitOneParser(argparse.ArgumentParser):
    """A parser whose usage error exits 1, not argparse's 2: the quote verifier keeps 2 for a failed quote."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _add_verify_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("folder", metavar="FOLDER", help="the report folder: Markdown reports and quotes.json")
    parser.add_argument("--at", metavar="GIT_REF", help="read the quoted files at this git ref, not the working tree")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROG, description="Build, compare, sweep and query the document index.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    build = commands.add_parser("build", help="write the index of the working tree to stdout as JSON")
    build.add_argument("--at", metavar="GIT_REF", help="index the files at this git ref, not the working tree")
    diff = commands.add_parser("diff", help="report what changed in the index from a git ref to the working tree")
    diff.add_argument("ref", metavar="GIT_REF", help="the old side: the git ref to compare with")
    diff.add_argument("--at", metavar="GIT_REF", help="the new side: this git ref, not the working tree")
    diff.add_argument("--format", choices=("text", "json"), default="text", help="the output form (text)")
    sweep_parser = commands.add_parser("sweep", help="list the normative items of the sweep scope")
    sweep_parser.add_argument("--at", metavar="GIT_REF", help="sweep the files at this git ref, not the working tree")
    modes = sweep_parser.add_mutually_exclusive_group()
    modes.add_argument("--diff", metavar="GIT_REF", help="list the items at this git ref that vanished by --at")
    modes.add_argument(
        "--recall", metavar="COMMITS_JSON", help="measure the removed lines of these commits that no item holds"
    )
    sweep_parser.add_argument(
        "--paths", metavar="PATHS", help="with --diff: sweep these comma-separated paths on both sides, not the scope"
    )
    sweep_parser.add_argument("--format", choices=("text", "json"), default="text", help="the output form (text)")
    sweep_parser.add_argument(
        "--triggers", choices=sweep.SELECTIONS, default="all", help="the trigger groups to use (all)"
    )
    query = commands.add_parser("query", help="show one node and its edges")
    query.add_argument("address", metavar="ADDRESS", help="a file path, a section address or an ID")
    verify = commands.add_parser(VERIFY_QUOTES, help="check every quote the reports of a folder cite")
    _add_verify_arguments(verify)
    manifest_parser = commands.add_parser("manifest", help="build the skill bundles and write their manifest")
    manifest_parser.add_argument("--out", metavar="FILE", help="write the manifest to this file, not stdout")
    manifest_diff = commands.add_parser("manifest-diff", help="list the bundle files changed between two manifests")
    manifest_diff.add_argument("old", metavar="OLD_JSON", help="the old manifest")
    manifest_diff.add_argument("new", metavar="NEW_JSON", help="the new manifest")
    manifest_diff.add_argument("--format", choices=("text", "json"), default="text", help="the output form (text)")
    evidence_parser = commands.add_parser("evidence", help="run the audit engine, or compare two runs' evidence")
    evidence_commands = evidence_parser.add_subparsers(dest="evidence_command", required=True, metavar="ACTION")
    evidence_run = evidence_commands.add_parser("run", help="run the audit engine into a fresh folder")
    evidence_run.add_argument("--out", metavar="DIR", required=True, help="the new or empty output folder")
    evidence_run.add_argument(
        "--target", choices=evidence.TARGET_KINDS, default="repo", help="this repository or the engine fixtures (repo)"
    )
    evidence_compare = evidence_commands.add_parser("compare", help="compare the verdicts and evidence of two runs")
    evidence_compare.add_argument("old", metavar="OLD_DIR", help="the earlier run folder")
    evidence_compare.add_argument("new", metavar="NEW_DIR", help="the later run folder")
    evidence_compare.add_argument("--format", choices=("text", "json"), default="text", help="the output form (text)")
    return parser


def _manifest(args: argparse.Namespace, build_bundles: Callable[[Path], None] | None) -> int:
    if build_bundles is None:
        print(f"{PROG} manifest: no bundle build given; run it through dev/doc_index.py", file=sys.stderr)
        return 1
    try:
        with tempfile.TemporaryDirectory(prefix="doc-index-manifest-") as folder:
            build_bundles(Path(folder))
            text = manifest.to_json(manifest.manifest(Path(folder)))
    except (manifest.BuildError, manifest.ManifestError) as exc:
        print(f"{PROG} manifest: {exc}", file=sys.stderr)
        return 1
    if args.out is None:
        sys.stdout.write(text)
        return 0
    try:
        Path(args.out).write_text(text, encoding="utf-8")
    except OSError as exc:
        print(f"{PROG} manifest: cannot write {args.out}: {exc}", file=sys.stderr)
        return 1
    return 0


def _read_manifest(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise manifest.ManifestError(f"cannot read {path}: {exc}") from exc


def _manifest_diff(args: argparse.Namespace) -> int:
    try:
        changes = manifest.compare(_read_manifest(args.old), _read_manifest(args.new))
    except manifest.ManifestError as exc:
        print(f"{PROG} manifest-diff: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(manifest.diff_to_json(changes) if args.format == "json" else manifest.to_text(changes))
    return 0


def _evidence_run(args: argparse.Namespace, project: evidence.Project | None) -> int:
    prog = f"{PROG} evidence run"
    if project is None:
        print(f"{prog}: no engine project given; run it through dev/doc_index.py", file=sys.stderr)
        return 1
    try:
        with tempfile.TemporaryDirectory(prefix="doc-index-evidence-") as work:
            record = evidence.run(Path(args.out), args.target, project, Path(work))
    except evidence.RefusedError as exc:
        print(f"{prog}: refused: {exc}", file=sys.stderr)
        return 2
    except evidence.EvidenceError as exc:
        print(f"{prog}: {exc}", file=sys.stderr)
        return 1
    count = len(record["reports"])
    print(f"{prog}: {count} report(s) and {evidence.RUN_RECORD} written to {args.out}", file=sys.stderr)
    return 0


def _evidence_compare(args: argparse.Namespace) -> int:
    try:
        old, new, comparison = evidence.compare(Path(args.old), Path(args.new))
    except evidence.EvidenceError as exc:
        print(f"{PROG} evidence compare: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        sys.stdout.write(evidence.diff_to_json(old, new, comparison))
    else:
        sys.stdout.write(evidence.to_text(old, new, comparison))
    return 0


def _verify_quotes(argv: Sequence[str], root: Path) -> int:
    parser = _ExitOneParser(
        prog=f"{PROG} {VERIFY_QUOTES}", description="Check every quote the reports of a folder cite."
    )
    _add_verify_arguments(parser)
    args = parser.parse_args(list(argv))
    try:
        read = quotes.ref_reader(root, args.at) if args.at is not None else quotes.working_tree_reader(root)
        result = quotes.verify(Path(args.folder), read)
    except (quotes.UsageError, GitError) as exc:
        print(f"{PROG} {VERIFY_QUOTES}: {exc}", file=sys.stderr)
        return 1
    for failure in result.failures:
        print(failure.line(), file=sys.stderr)
    print(result.summary())
    return 0 if result.passed else 2


def _build(args: argparse.Namespace, config: Mapping[str, Any], root: Path) -> int:
    try:
        tree: Tree = RefTree(root, args.at) if args.at is not None else WorkTree(root)
        result = extract.extract(tree, config)
    except GitError as exc:
        print(f"{PROG} build: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(to_json(result.index))
    sys.stderr.write(extract.summary_text(result.summary, prog=f"{PROG} build"))
    return 0


def _index_diff(args: argparse.Namespace, config: Mapping[str, Any], root: Path) -> int:
    try:
        old_tree = RefTree(root, args.ref)
        new_tree: Tree = RefTree(root, args.at) if args.at is not None else WorkTree(root)
        old = extract.extract(old_tree, config).index
        new = extract.extract(new_tree, config).index
    except GitError as exc:
        print(f"{PROG} diff: {exc}", file=sys.stderr)
        return 1
    report = index_diff.compare(
        old, new, old_body=index_diff.body_hashes(old_tree), new_body=index_diff.body_hashes(new_tree)
    )
    if args.format == "json":
        sys.stdout.write(index_diff.to_json(report, old=args.ref, new=args.at))
    else:
        sys.stdout.write(index_diff.to_text(report, old=args.ref, new=args.at))
    return 0


def _report(args: argparse.Namespace, triggers: Sequence[str], tree: Tree, paths: Sequence[str]) -> int:
    report = sweep.sweep(tree, paths, triggers)
    if args.format == "json":
        sys.stdout.write(sweep.to_json(report, selection=args.triggers, at=args.at))
    else:
        sys.stdout.write(sweep.to_text(report))
        sys.stderr.write(sweep.summary(report))
    return 0


def _split_paths(value: str) -> list[str]:
    return sorted({path.strip() for path in value.split(",") if path.strip()})


def _diff(
    args: argparse.Namespace,
    config: Mapping[str, Any],
    root: Path,
    bundle_sources: Callable[[], Sequence[str]] | None,
    triggers: Sequence[str],
) -> int:
    old_tree = RefTree(root, args.diff)
    new_tree: Tree = RefTree(root, args.at) if args.at is not None else WorkTree(root)
    listed = _split_paths(args.paths) if args.paths is not None else None
    if listed is not None:
        old_paths = sweep_diff.restrict(old_tree.files(), listed)
        new_paths = sweep_diff.restrict(new_tree.files(), listed)
    else:
        sources = bundle_sources() if bundle_sources else ()
        old_paths = sweep.scope(old_tree.files(), config, sources)
        new_paths = sweep.scope(new_tree.files(), config, sources)
    old = sweep.sweep(old_tree, old_paths, triggers)
    new = sweep.sweep(new_tree, new_paths, triggers)
    report = sweep_diff.compare(old.items, new.items)
    if args.format == "json":
        sys.stdout.write(sweep_diff.to_json(report, old=args.diff, new=args.at, selection=args.triggers, paths=listed))
    else:
        sys.stdout.write(sweep_diff.to_text(report, old=args.diff, new=args.at))
    return 0


def _recall(args: argparse.Namespace, root: Path, triggers: Sequence[str]) -> int:
    try:
        commits = recall.load_commits(json.loads(Path(args.recall).read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"{PROG} sweep: cannot read the commits file {args.recall}: {exc}", file=sys.stderr)
        return 1
    results = recall.measure(root, commits, triggers)
    if args.format == "json":
        sys.stdout.write(recall.to_json(results, selection=args.triggers))
    else:
        sys.stdout.write(recall.to_text(results, selection=args.triggers))
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
        if args.recall is not None:
            return _recall(args, root, triggers)
        if args.diff is not None:
            return _diff(args, config, root, bundle_sources, triggers)
        tree: Tree = RefTree(root, args.at) if args.at is not None else WorkTree(root)
        paths = sweep.scope(tree.files(), config, bundle_sources() if bundle_sources else ())
        return _report(args, triggers, tree, paths)
    except GitError as exc:
        print(f"{PROG} sweep: {exc}", file=sys.stderr)
        return 1


def main(
    argv: Sequence[str] | None = None,
    config: Mapping[str, Any] | None = None,
    *,
    root: Path | None = None,
    bundle_sources: Callable[[], Sequence[str]] | None = None,
    build_bundles: Callable[[Path], None] | None = None,
    evidence_project: evidence.Project | None = None,
) -> int:
    """Run one subcommand and return its exit code.

    ``config`` is the project config the entry point loaded. ``root`` is the repository root (the current folder
    when ``None``). ``bundle_sources`` returns the project's bundle sources, the files and folders the sweep scope
    starts from; ``build_bundles`` builds every bundle into the folder it is given, one subfolder each, and raises
    :class:`docindex.manifest.BuildError` when the build fails. ``evidence_project`` names the audit engine and the
    targets of ``evidence run``. The entry point supplies all three, so that this package imports no other ``dev/``
    module.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == [VERIFY_QUOTES]:
        return _verify_quotes(arguments[1:], root or Path.cwd())
    parser = build_parser()
    args = parser.parse_args(arguments)
    if args.command == "build":
        return _build(args, config or {}, root or Path.cwd())
    if args.command == "sweep":
        if args.paths is not None and args.diff is None:
            parser.error("sweep: --paths needs --diff")
        if args.paths is not None and not _split_paths(args.paths):
            parser.error("sweep: --paths needs at least one path")
        if args.recall is not None and args.at is not None:
            parser.error("sweep: --recall takes no --at")
        return _sweep(args, config or {}, root or Path.cwd(), bundle_sources)
    if args.command == "diff":
        return _index_diff(args, config or {}, root or Path.cwd())
    if args.command == "manifest":
        return _manifest(args, build_bundles)
    if args.command == "manifest-diff":
        return _manifest_diff(args)
    if args.command == "evidence":
        if args.evidence_command == "run":
            return _evidence_run(args, evidence_project)
        return _evidence_compare(args)
    print(f"{PROG} {args.command}: not implemented here; run it through dev/doc_index.py", file=sys.stderr)
    return 1
