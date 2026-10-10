# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Run the deterministic audit engine from any directory, and write its report under the repository's name.

The engine lives in ``../deterministic-audit/`` and is a package named ``audit``. This launcher puts that folder on
``sys.path`` and calls the engine's ``main(argv)`` in this process, so a recipe can run it from any working directory
with one command and no install (ADR 0001 in the recipes' docs).

Two modes::

    engine.py <target> [--out-dir DIR] [--repo-label LABEL] ...   scan, write one JSON report, print where
    engine.py --list-checks                                       the engine's checks, as data

The launcher decides everything the engine would otherwise leave to chance: it asks for JSON only, names the report
``<label>.engine-report.<stamp>.json`` in a directory outside the target, and never passes the engine's ``--force``,
``--baseline``, ``--fail-on`` or ``--emit-baseline``. The engine refuses to replace an existing JSON report, so a
name taken by another run in the same second is a loud failure, never an overwrite. See the tools README for the
contract and ``schema/SCHEMA.md``, "Output files", for the names.

Failure behaviour: a refusal by the engine (bad target, ``--run-gates`` without ``--allow-probe``) is exit 1 with the
engine's message in ``data.error``. An engine that exits with any other code, or raises, is exit 3.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence

import _common

INFO = _common.ToolInfo(
    name="engine",
    summary="Run the deterministic audit engine from any directory; the report is named for the repository.",
    synopsis=(
        "engine.py <target> [--out-dir DIR] [--repo-label LABEL] [--phase N] [--exclude GLOB]... [--max-files N]"
        " [--run-gates --allow-probe VERB... [--timeout SECONDS]]",
        "engine.py --list-checks",
    ),
    writes=(
        "One file, <label>.engine-report.<stamp>.json, in --out-dir (default: the current directory), "
        "which must be outside the target. A name that is taken is never replaced."
    ),
)

ENGINE_DIR = Path(__file__).resolve().parent.parent / "deterministic-audit"
REPORT_KIND = "engine-report"
WARNING_CHARS = 500


def load_engine() -> ModuleType:
    """Import the engine's entry module from `ENGINE_DIR`, and refuse an `audit` package from anywhere else."""
    if str(ENGINE_DIR) not in sys.path:
        sys.path.insert(0, str(ENGINE_DIR))
    module = importlib.import_module("audit.__main__")
    package = sys.modules["audit"]
    found = Path(getattr(package, "__file__", "") or "").resolve()
    if ENGINE_DIR not in found.parents:
        raise _common.ToolError(f"imported an `audit` package from {found}, not from {ENGINE_DIR}")
    return module


def run_engine(argv: list[str]) -> tuple[int, str, str]:
    """Call the engine's `main` with `argv`. Returns its exit code, stdout and stderr, and prints neither."""
    main = load_engine().main
    write_error = importlib.import_module("audit.report").ReportWriteError
    out, err = io.StringIO(), io.StringIO()
    code: object
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = _common.EXIT_OK if exc.code is None else exc.code
        except write_error as exc:
            print(f"audit: {exc}", file=err)
            code = _common.EXIT_USAGE
    return (code if isinstance(code, int) else _common.EXIT_INTERNAL), out.getvalue(), err.getvalue()


def engine_message(stderr: str) -> str:
    """The engine's own explanation of a refusal: its last non-empty stderr line, without the `audit: ` prefix.

    The engine tells an operator to pass `--force` when a report exists. This launcher has no such option, so the
    advice is replaced with what is true here.
    """
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    message = lines[-1].removeprefix("audit: ") if lines else "the engine gave no reason"
    return message.replace(" — pass --force to overwrite", "; nothing was replaced, run the tool again")


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(prog="engine.py", description=INFO.summary)
    parser.add_argument("target", nargs="?", help="the repository to scan")
    parser.add_argument("--out-dir", help="where the report goes; outside the target (default: the current directory)")
    parser.add_argument("--repo-label", help="the label in the file name (default: derived from the target's name)")
    parser.add_argument("--phase", type=int, help="highest framework phase to evaluate (the engine's default is 1)")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="extra path glob to skip")
    parser.add_argument("--max-files", type=int, help="hard cap on inspected files")
    parser.add_argument("--run-gates", action="store_true", help="let the engine run the target's own commands")
    parser.add_argument("--allow-probe", action="append", default=[], metavar="VERB", help="a verb the engine may run")
    parser.add_argument("--timeout", type=int, metavar="SECONDS", help="the engine's per-command limit")
    parser.add_argument("--list-checks", action="store_true", help="print the engine's checks and exit")
    return parser


def scan_options(args: Any) -> list[str]:
    """The scan-only options the operator set, as written on the command line."""
    given = {
        "<target>": args.target is not None,
        "--out-dir": args.out_dir is not None,
        "--repo-label": args.repo_label is not None,
        "--phase": args.phase is not None,
        "--exclude": bool(args.exclude),
        "--max-files": args.max_files is not None,
        "--run-gates": args.run_gates,
        "--allow-probe": bool(args.allow_probe),
        "--timeout": args.timeout is not None,
    }
    return [name for name, was_given in given.items() if was_given]


def list_checks() -> _common.Result:
    code, stdout, stderr = run_engine(["--list-checks", "--format", "json"])
    if code != _common.EXIT_OK:
        raise _common.ToolError(f"the engine could not list its checks (exit {code}): {engine_message(stderr)}")
    listing = json.loads(stdout)
    checks, omitted = _common.bound_items(listing["checks"])
    data = {"engine": listing["engine"], "checks": checks, "omitted": omitted}
    return _common.Result(
        data=data,
        summary=f"engine: {len(listing['checks'])} checks catalogued",
        truncated=bool(omitted),
    )


def scan(args: Any) -> _common.Result:
    target = _common.resolve_target(args.target if args.target is not None else ".")
    try:
        out_dir = _common.output_directory(args.out_dir if args.out_dir is not None else Path.cwd(), target=target)
    except _common.PathNotAllowed as exc:
        hint = "" if args.out_dir is not None else "run it from outside the target, or pass --out-dir"
        raise _common.PathNotAllowed(str(exc), hint=hint) from None
    label = _common.repo_label(target, args.repo_label)
    stamp = _common.utc_stamp()
    report = _common.free_name(out_dir, label, REPORT_KIND, stamp, "json")

    argv = [str(target), "--format", "json", "--out", str(report)]
    if args.phase is not None:
        argv += ["--phase", str(args.phase)]
    for pattern in args.exclude:
        argv += ["--exclude", pattern]
    if args.max_files is not None:
        argv += ["--max-files", str(args.max_files)]
    if args.run_gates:
        argv.append("--run-gates")
    for verb in args.allow_probe:
        argv += ["--allow-probe", verb]
    if args.timeout is not None:
        argv += ["--timeout", str(args.timeout)]

    code, stdout, stderr = run_engine(argv)
    if code == _common.EXIT_USAGE:
        raise _common.UsageError(f"the engine refused the run: {engine_message(stderr)}")
    if code != _common.EXIT_OK:
        raise _common.ToolError(f"the engine exited with code {code}: {engine_message(stderr)}")
    if not report.is_file():
        raise _common.ToolError(f"the engine reported success but wrote no report at {report}")

    warnings = []
    if stdout.strip():
        warnings.append("the engine printed to stdout: " + stdout.strip()[:WARNING_CHARS])
    package = sys.modules["audit"]
    # The engine's "report written" line repeats the summary below. Anything else it said is kept.
    said = [line for line in stderr.splitlines() if line.strip() and not line.startswith("report written:")]
    return _common.Result(
        data={
            "report": str(report),
            "label": label,
            "stamp": stamp,
            "target": str(target),
            "engine": {
                "version": getattr(package, "__version__", None),
                "ruleset_revision": getattr(package, "__ruleset_revision__", None),
            },
        },
        summary="\n".join(said + [f"engine: report written to {report}"]),
        warnings=warnings,
    )


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    if args.list_checks:
        extra = scan_options(args)
        if extra:
            raise _common.UsageError(f"--list-checks takes no other argument, but got {', '.join(extra)}")
        return list_checks()
    return scan(args)


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
