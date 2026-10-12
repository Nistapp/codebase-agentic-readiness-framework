# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Describe a repository with counts and names and no verdicts, in a file the audit reads before it assesses.

IN DEVELOPMENT, until S2.7.5.3. One command::

    facts.py <target> --out FILE [--repo-label LABEL] [--exclude GLOB]... [--max-files N]

The tool writes one new file, ``facts.json``, whose format is ``schema/facts.schema.json``. This version writes
``facts_version``, ``label`` and ``git``; the inventory, the detections, the instruction files, the components and the
size class arrive in the steps after this one. ``--exclude`` and ``--max-files`` are accepted and checked now, spelled as
``engine.py`` spells them, because they shape the inventory section; until it is written they change nothing in the file.

The file holds no time, no absolute path and no machine name, so one repository state gives one file. The envelope on
stdout names the file, its size and the format's version. The tool never writes inside the target: the file must be
new, in a folder that exists and is outside the target, and nothing already there is replaced.

``git`` comes from the engine's own target module (``audit.target``). That module asks git with ``--no-optional-locks``,
so that ``git status`` does not refresh the index and write a file inside the target's ``.git``.

Failure behaviour: a target that does not exist, is not a directory or is a filesystem root, an output that is not
allowed, a bad option or a bad label is exit 1. A document that does not fit its schema, or is over ``MAX_FACTS_BYTES``,
is exit 3, because it can only be a bug in this tool; nothing is written then.
"""

from __future__ import annotations

import importlib
import json
import sys
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence

import _common
import _jsonschema_subset as subset
import engine as engine_launcher

INFO = _common.ToolInfo(
    name="facts",
    summary=(
        "Describe a repository with counts and names and no verdicts, as facts.json. "
        "In development: so far it writes facts_version, label and git."
    ),
    synopsis=("facts.py <target> --out FILE [--repo-label LABEL] [--exclude GLOB]... [--max-files N]",),
    writes="One new file, the one --out names, which must be outside the target and must not exist. It is never replaced.",
)

RECIPES = Path(__file__).resolve().parent.parent
FACTS_SCHEMA = RECIPES / "schema" / "facts.schema.json"
FACTS_VERSION = "0.1"
# Under 30 KB whether a kilobyte is 1,000 or 1,024 bytes.
MAX_FACTS_BYTES = 30_000
MAX_SCHEMA_ERRORS = 20


def engine_module(name: str) -> ModuleType:
    """An engine module, imported through the launcher, which puts the engine's folder on `sys.path` and checks it."""
    engine_launcher.load_engine()
    return importlib.import_module(name)


def git_state(target: Path) -> dict[str, Any]:
    """`sha` and `dirty`, from the engine's target guard, which also refuses a filesystem root."""
    guard = engine_module("audit.target").resolve_target
    refusal = engine_module("audit.cli").AuditUsageError
    try:
        found = guard(target)
    except refusal as exc:
        raise _common.UsageError(str(exc)) from None
    return {"sha": found.git_sha, "dirty": found.git_dirty}


def build_document(*, label: str, git: dict[str, Any]) -> dict[str, Any]:
    """The facts, in the schema's key order. Each later section is added here as its step lands."""
    return {"facts_version": FACTS_VERSION, "label": label, "git": git}


@cache
def facts_validator() -> subset.SubsetValidator:
    return subset.SubsetValidator(json.loads(FACTS_SCHEMA.read_text(encoding="utf-8")))


def check_document(document: dict[str, Any]) -> None:
    """Refuse a document that does not fit `facts.schema.json`. That is a bug in this tool, so it is exit 3."""
    problems = [str(found) for found in facts_validator().validate(document, limit=MAX_SCHEMA_ERRORS)]
    if problems:
        raise _common.ToolError("the facts do not fit facts.schema.json, which is a bug in the tool", errors=problems)


def encode_facts(document: dict[str, Any], *, limit: int = MAX_FACTS_BYTES) -> str:
    """The document as text, or `OutputTooLarge` when it does not fit. Key order is the order given."""
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    size = len(text.encode("utf-8"))
    if size > limit:
        raise _common.OutputTooLarge(
            f"the facts are {size} bytes and the limit is {limit}; the tool must bound its lists"
        )
    return text


def output_file(path: str, *, target: Path) -> Path:
    """The file `--out` names. Its folder must exist and be outside the target; the file itself is made later, and new."""
    out = Path(path).expanduser()
    if not out.parent.is_dir():
        raise _common.UsageError(f"the folder for --out does not exist: {out.parent}")
    folder = out.parent.resolve()
    if _common.is_within(target, folder):
        raise _common.PathNotAllowed(f"refusing to write inside the target: {folder}")
    return folder / out.name


def build_parser() -> _common.ToolParser:
    parser = _common.ToolParser(
        prog="facts.py",
        description=INFO.summary,
        epilog="IN DEVELOPMENT until S2.7.5.3: the file holds only facts_version, label and git so far.",
    )
    parser.add_argument("target", help="the repository to describe")
    parser.add_argument("--out", required=True, metavar="FILE", help="the file to create; it must not exist")
    parser.add_argument("--repo-label", help="the label in the file (default: derived from the target's name)")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="a path glob to leave out of the inventory, as engine.py's does (no effect until the inventory is written)",
    )
    parser.add_argument(
        "--max-files", type=int, help="stop the inventory walk after this many files (no effect until it is written)"
    )
    return parser


def handler(argv: Sequence[str]) -> _common.Result:
    args = build_parser().parse_args(list(argv))
    if args.max_files is not None and args.max_files < 1:
        raise _common.UsageError(f"--max-files must be at least 1, not {args.max_files}")
    target = _common.resolve_target(args.target)
    label = _common.repo_label(target, args.repo_label)
    git = git_state(target)
    out = output_file(args.out, target=target)
    document = build_document(label=label, git=git)
    check_document(document)
    text = encode_facts(document)
    try:
        written = _common.create_file(out, text)
    except OSError as exc:
        raise _common.UsageError(f"cannot write {out}: {exc.strerror or exc}") from None
    size = len(text.encode("utf-8"))
    return _common.Result(
        data={"file": str(written), "bytes": size, "facts_version": FACTS_VERSION},
        summary=f"facts: wrote {written.name} ({size} bytes)",
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
