# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Describe a repository with counts and names and no verdicts, in a file the audit reads before it assesses.

IN DEVELOPMENT, until S2.7.5.3. One command::

    facts.py <target> --out FILE [--repo-label LABEL] [--exclude GLOB]... [--max-files N]

The tool writes one new file, ``facts.json``, whose format is ``schema/facts.schema.json``. This version writes
``facts_version``, ``label``, ``git``, ``inventory``, ``stack``, ``instruction_files`` and ``components``, with
``caps`` for the lists that are cut; the size class arrives in the step after this one. ``--exclude`` and
``--max-files`` are spelled as ``engine.py`` spells them and shape the walk of ``audit.scan.build_inventory``, so the
facts describe the inventory the engine sees. The inventory holds counts and never a path. A walk that ``--max-files``
cut short says ``truncated`` in the file and gives a warning in the envelope; the engine records no skip reason for
that.

The instruction files are the ones that the engine's ``AGT-01`` and ``AGT-08`` see (``instruction_paths`` in
``audit.rules.checks.agt``), each with the pattern of the variants table that names it. The tool asks the engine and
adds no search of its own, so the list has the engine's gaps and follows the engine when they are closed.

The components are the engine's own ``audit.components.detect_components``: ``declared`` components that a build
manifest names, and ``candidates`` that look like a component but that no manifest declares. The implicit root
component is never listed. Nothing here says a component is complete or well-formed.

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

import fnmatch
import importlib
import inspect
import json
import re
import sys
from collections import Counter
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
        "In development: so far it writes facts_version, label, git, inventory, stack, instruction_files, "
        "components and caps."
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
# What the schema allows for a glob (`$defs/glob`, `$defs/cap_excludes`); tests hold both to the schema. `fullmatch`, so
# that a glob ending in a line break is out, as it is for the tools' validator.
GLOB_FITS = re.compile(r"[ -~]{1,100}")
EXCLUDES_LIMIT = 10
# What the schema allows for an instruction file's path (`$defs/relpath`, `$defs/cap_instruction_files`).
RELPATH_FITS = re.compile(r"(?![A-Za-z]:)(?!/)[ -~]{1,128}")
INSTRUCTION_FILES_LIMIT = 25
# What the schema allows for a component's name or the manifest key that declared it (`$defs/label_text`).
LABEL_FITS = re.compile(r"[ -~]{1,64}")
DECLARED_COMPONENTS_LIMIT = 16
CANDIDATE_COMPONENTS_LIMIT = 20


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


def default_max_files() -> int:
    """The walk's cap when `--max-files` is not given: the engine's own default, read from `build_inventory`."""
    parameter = inspect.signature(engine_module("audit.scan").build_inventory).parameters["max_files"]
    return int(parameter.default)


def walk_target(target: Path, *, excludes: Sequence[str], max_files: int) -> Any:
    """The engine's inventory of `target`. The walk never follows a link, never leaves the target and writes nothing."""
    build = engine_module("audit.scan").build_inventory
    return build(target, extra_excludes=tuple(excludes), max_files=max_files)


def listed_excludes(globs: Sequence[str]) -> tuple[list[str], int]:
    """The globs the file names, in the order given, and how many it leaves out.

    A glob that does not fit the schema is left out, and so is each glob after the first `EXCLUDES_LIMIT` that fit.
    The engine applied every glob all the same.
    """
    listed = [glob for glob in globs if GLOB_FITS.fullmatch(glob)][:EXCLUDES_LIMIT]
    return listed, len(globs) - len(listed)


def inventory_section(inventory: Any, *, max_files: int, excludes: Sequence[str]) -> dict[str, Any]:
    """Counts from the engine's `Inventory`, and never a path. `excludes` is what `listed_excludes` kept."""
    by_kind = {kind.value: 0 for kind in engine_module("audit.scan").Kind}
    for entry in inventory.files:
        by_kind[entry.kind.value] += 1
    reasons = Counter(reason for _, reason in inventory.skipped)
    return {
        "files": len(inventory.files),
        "bytes": sum(entry.size for entry in inventory.files),
        "by_kind": by_kind,
        "skipped": [{"reason": reason, "count": count} for reason, count in sorted(reasons.items())],
        "truncated": inventory.truncated,
        "max_files": max_files,
        "excludes": list(excludes),
    }


def stack_section(inventory: Any) -> dict[str, Any]:
    """The names `detect_stack` recognised in the inventory, sorted, and the engine's notes. No verdict, no error.

    A repository the engine does not recognise gives empty lists and the engine's note, which says so.
    """
    found = engine_module("audit.stack").detect_stack(inventory)
    return {
        "ecosystems": sorted(found.ecosystems),
        "source_only": sorted(found.source_only),
        "package_managers": sorted(found.package_managers),
        "ci_providers": sorted(found.ci_providers),
        "test_frameworks": sorted(found.test_frameworks),
        "hook_managers": sorted(found.hook_managers),
        "notes": sorted(found.notes),
    }


def variant_of(rel: str) -> str:
    """The pattern of the engine's variants table that names the instruction file `rel`.

    A plain name counts at any depth, as the engine counts it; a pattern with a folder in it is tried in the table's
    order, once as written and once without its `**/`, so that a file straight in the folder has a name too.
    """
    names = engine_module("audit.rules.checks.agt").INSTRUCTION_BASENAMES
    base = rel.rpartition("/")[2]
    if base in names:
        return str(base)
    for harness in engine_module("audit.rules.variants").HARNESSES:
        for pattern in harness.paths:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(rel, pattern.replace("**/", "")):
                return str(pattern)
    raise _common.ToolError(f"the engine sees {rel} as an instruction file and its variants table has no name for it")


def instruction_files_section(inventory: Any) -> tuple[list[dict[str, Any]], int]:
    """The files `AGT-01` and `AGT-08` see, sorted by path, and how many the file leaves out.

    A path that does not fit the schema is left out, and so is each file after the first `INSTRUCTION_FILES_LIMIT` that
    fit. Nothing here says whether a file is good, canonical or a stub: the entry has a path, a name and a size.
    """
    seen = sorted(engine_module("audit.rules.checks.agt").instruction_paths(inventory))
    sizes = {entry.rel: entry.size for entry in inventory.files}
    listed = [rel for rel in seen if RELPATH_FITS.fullmatch(rel)][:INSTRUCTION_FILES_LIMIT]
    entries = [{"path": rel, "variant": variant_of(rel), "size_bytes": sizes[rel]} for rel in listed]
    return entries, len(seen) - len(listed)


def components_section(inventory: Any) -> tuple[dict[str, Any], int, int]:
    """`declared`, `candidates` and `notes` from the engine's `detect_components`, sorted by path and capped.

    The implicit root component is never listed. A declared component whose name, path, declared-by or manifest does
    not fit the schema is left out, and so is a candidate whose path does not; so is each entry after the first cap
    that fits. Nothing here says whether a component is complete or well-formed.
    """
    model = engine_module("audit.components").detect_components(inventory)
    members = sorted((member for member in model.components if not member.is_root), key=lambda member: member.path)
    fit_members = [
        member
        for member in members
        if LABEL_FITS.fullmatch(member.name)
        and RELPATH_FITS.fullmatch(member.path)
        and LABEL_FITS.fullmatch(member.declared_by)
        and (member.manifest is None or RELPATH_FITS.fullmatch(member.manifest))
    ]
    listed_members = fit_members[:DECLARED_COMPONENTS_LIMIT]
    declared = [
        {"name": m.name, "path": m.path, "declared_by": m.declared_by, "manifest": m.manifest} for m in listed_members
    ]

    candidates = sorted(model.candidates)
    fit_candidates = [path for path in candidates if RELPATH_FITS.fullmatch(path)]
    listed_candidates = fit_candidates[:CANDIDATE_COMPONENTS_LIMIT]

    section = {"declared": declared, "candidates": listed_candidates, "notes": sorted(model.notes)}
    return section, len(members) - len(listed_members), len(candidates) - len(listed_candidates)


def build_document(*, label: str, git: dict[str, Any], inventory: Any, max_files: int) -> dict[str, Any]:
    """The facts, in the schema's key order. Each later section is added here as its step lands."""
    listed, omitted = listed_excludes(inventory.excludes)
    instruction_files, left_out = instruction_files_section(inventory)
    components, declared_omitted, candidate_omitted = components_section(inventory)
    return {
        "facts_version": FACTS_VERSION,
        "label": label,
        "git": git,
        "inventory": inventory_section(inventory, max_files=max_files, excludes=listed),
        "stack": stack_section(inventory),
        "instruction_files": instruction_files,
        "components": components,
        "caps": {
            "excludes": {"limit": EXCLUDES_LIMIT, "omitted": omitted},
            "instruction_files": {"limit": INSTRUCTION_FILES_LIMIT, "omitted": left_out},
            "declared_components": {"limit": DECLARED_COMPONENTS_LIMIT, "omitted": declared_omitted},
            "candidate_components": {"limit": CANDIDATE_COMPONENTS_LIMIT, "omitted": candidate_omitted},
        },
    }


def cut_warning(max_files: int) -> str:
    return f"the walk stopped at its cap of {max_files} files, so every count in the inventory is a lower bound"


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
        epilog=(
            "IN DEVELOPMENT until S2.7.5.3: so far the file holds facts_version, label, git, inventory, stack, "
            "instruction_files, components and caps."
        ),
    )
    parser.add_argument("target", help="the repository to describe")
    parser.add_argument("--out", required=True, metavar="FILE", help="the file to create; it must not exist")
    parser.add_argument("--repo-label", help="the label in the file (default: derived from the target's name)")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help=f"a path glob to leave out of the inventory, as engine.py's does; the file names up to {EXCLUDES_LIMIT}",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        help="stop the inventory walk after this many files (default: the engine's own cap); a walk that stops is truncated",
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
    cap = args.max_files if args.max_files is not None else default_max_files()
    inventory = walk_target(target, excludes=args.exclude, max_files=cap)
    document = build_document(label=label, git=git, inventory=inventory, max_files=cap)
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
        warnings=[cut_warning(cap)] if inventory.truncated else [],
    )


if __name__ == "__main__":
    raise SystemExit(_common.run_tool(INFO, handler, sys.argv[1:]))
