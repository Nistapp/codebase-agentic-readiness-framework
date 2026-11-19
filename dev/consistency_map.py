# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The consistency map's gate, in static mode: is every touched read kept? (ADR 0012).

``python3 dev/consistency_map.py`` reads the map (:func:`load_map`), the catalogue, the playbooks, the greenfield
templates and the engine's constants in the working tree, and reports eight kinds of problem:

- ``unkept``: a move declares that it touches a check (``touches``) and no keeps entry covers the pair;
- ``quote``: a kept quote is not in the section its address names;
- ``mention``: a kept quote's section no longer mentions the check ID;
- ``coverage``: a catalogue check has no reads entry, or a playbook Commits row has no moves entry;
- ``names``: a template's scaffolded path carries an engine name and its moves entry declares no intent;
- ``constants``: a reads or names entry disagrees with the engine constants it names;
- ``keeps``: a keeps entry names an unknown move or check, repeats a pair, or keeps a check its move does not
  declare in ``touches``;
- ``boundary``: a boundary's home quote is not in its section, its id repeats, or the file or symbol that enforces
  it no longer exists.

The touches are a reviewer's judgement, written in the map. The gate also infers touches from the paths and the
content kinds (``touch``), and counts the inferred pairs no move declares and no keep covers as ``unreviewed``. That
count is advice, never a problem: the inference is coarse, and a reviewer decides whether a pair is real.

The gate prints a report and exits 0. With ``--strict`` it exits 1 when it found a problem. ``--format json``
writes the report as JSON. ``make consistency-map`` runs it in report mode.

``--base [REF]`` adds change mode against ``REF`` (default ``origin/dev``): the sections a branch changed in the
files the checks read, the kept sections that lost their mention of a check, the files renamed out of a read's
scope, and the evidence comparison (:mod:`consistency_map_change`). ``--at REF`` takes the new side from a commit,
not the working tree; ``--no-evidence`` skips the engine runs. A ref that names no commit is a usage error (exit 2);
a failed engine run exits 1.

The map is two files, so that each stays under the 512 KiB size the audit's structural check flags:
``dev/consistency-map.json`` holds every part but ``names``, and ``dev/consistency-map-names.json`` holds
``map_format`` and ``names``. :func:`load_map` joins them into the one map the schema describes. A map file that
also holds ``names``, a missing names file, or a ``map_format`` that differs is a usage error (exit 2).
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import functools
import importlib
import json
import posixpath
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

DEV = Path(__file__).resolve().parent
REPO = DEV.parent
MAP_PATH = DEV / "consistency-map.json"
#: The suffix that turns the map file's name into its names file's name (``consistency-map-names.json``).
NAMES_SUFFIX = "-names"
ENGINE = REPO / "audit" / "engine"
BOOTSTRAP = REPO / "greenfield" / "bootstrap"
TEMPLATES = REPO / "greenfield" / "templates"
PLAYBOOKS = REPO / "implement" / "playbooks"
CATALOGUE = REPO / "audit" / "catalogue.json"
#: The base ref of change mode (`--base` with no value).
DEFAULT_BASE = "origin/dev"

if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from docindex.extract import _section_nodes  # noqa: E402  (dev/ must be on sys.path first)

KINDS = ("unkept", "quote", "mention", "coverage", "names", "constants", "keeps", "boundary")
#: The boundary enforcements that name a file and a symbol; ``prose`` names neither.
ENFORCERS = ("tool-refusal", "test", "eval")

Reader = Callable[[str], str]

_COMMITS_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
_REPOSITORY_LEVEL = ("", ".github", ".gitlab", "docs")
# Which move content can hold what a read looks for.
_CONTENT_FOR: dict[str, frozenset[str]] = {
    "phrase": frozenset({"prose", "rule-line", "heading", "table"}),
    "word-list": frozenset({"prose", "rule-line", "heading", "table"}),
    "fenced-command": frozenset({"fenced-command"}),
    "code-span": frozenset({"code-span", "rule-line"}),
    "key": frozenset({"key"}),
    "exists": frozenset({"file"}),
}


class MapError(Exception):
    """The map's two files do not join into one map."""


def names_path(map_path: Path) -> Path:
    """The names file beside a map file: ``consistency-map.json`` gives ``consistency-map-names.json``."""
    return map_path.with_name(map_path.stem + NAMES_SUFFIX + map_path.suffix)


def load_map(map_path: Path = MAP_PATH) -> dict[str, Any]:
    """The map file joined with its names file, as one map; raises :class:`MapError` when they do not join."""
    cmap = json.loads(map_path.read_text(encoding="utf-8"))
    if "names" in cmap:
        raise MapError(f"{map_path.name} holds names; they belong in {names_path(map_path).name}")
    try:
        names = json.loads(names_path(map_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MapError(f"{names_path(map_path).name} is missing beside {map_path.name}") from None
    if set(names) != {"map_format", "names"}:
        raise MapError(f"{names_path(map_path).name} must hold map_format and names only, not {sorted(names)}")
    if names["map_format"] != cmap.get("map_format"):
        raise MapError(
            f"{names_path(map_path).name} has map_format {names['map_format']!r}, "
            f"{map_path.name} has {cmap.get('map_format')!r}"
        )
    return {**cmap, "names": names["names"]}


def working_tree(path: str) -> str:
    """The text of a repository file in the working tree."""
    return (REPO / path).read_text(encoding="utf-8")


def _engine_module(name: str) -> Any:
    if str(ENGINE) not in sys.path:
        sys.path.insert(0, str(ENGINE))
    return importlib.import_module(name)


# --- Engine constants -----------------------------------------------------------------------------------------------


def constant_values(reference: str) -> tuple[set[str], list[str]]:
    """The strings a ``module:NAME`` constant holds, and the problems found while reading it."""
    module_name, _, attribute = reference.partition(":")
    module = _engine_module(module_name)
    if not hasattr(module, attribute):
        return set(), [f"{reference}: no such constant"]
    value = getattr(module, attribute)
    if not isinstance(value, (tuple, list, frozenset, set)) or not all(isinstance(item, str) for item in value):
        return set(), [f"{reference}: not a tuple, list or set of strings"]
    return set(value), []


def read_constant_problems(read: dict[str, Any]) -> list[str]:
    """Differences between a reads entry's paths and the union of the engine constants it names."""
    references = read.get("constants", [])
    if not references:
        return []
    held: set[str] = set()
    problems: list[str] = []
    for reference in references:
        values, found = constant_values(reference)
        held |= values
        problems += found
    declared = {where["path"] for where in read["where"]}
    check = read["check"]
    problems += [f"{check}: the engine reads {path!r}, the map does not list it" for path in sorted(held - declared)]
    problems += [f"{check}: the map lists {path!r}, the engine constants do not" for path in sorted(declared - held)]
    return problems


def names_constant_problems(names: Sequence[dict[str, Any]]) -> list[str]:
    """Patterns that are not in the constants their entry names, and constant values no entry covers."""
    problems: list[str] = []
    covered: dict[str, set[str]] = {}
    for name in names:
        references = name.get("constants", [])
        for reference in references:
            covered.setdefault(reference, set()).add(name["pattern"])
        if references:
            held: set[str] = set()
            for reference in references:
                values, found = constant_values(reference)
                held |= values
                problems += found
            if name["pattern"] not in held:
                problems.append(f"{name['pattern']!r} is not a value of {', '.join(references)}")
    for reference, patterns in sorted(covered.items()):
        values, _ = constant_values(reference)
        problems += [f"{reference}: {value!r} has no names entry" for value in sorted(values - patterns)]
    return problems


# --- Names and templates --------------------------------------------------------------------------------------------


def name_matches(name: dict[str, Any], path: str) -> bool:
    """Whether a repository-relative path matches a names entry, as the entry's ``match`` and ``ignore_case`` say."""
    pattern = str(name["pattern"])
    if name.get("ignore_case"):
        pattern, path = pattern.lower(), path.lower()
    match = name["match"]
    if match == "exact":
        return path == pattern
    if match == "base-name":
        return fnmatch.fnmatchcase(posixpath.basename(path), pattern)
    if match == "glob":
        return fnmatch.fnmatchcase(path, pattern)
    return pattern in path


def bootstrap_module() -> Any:
    """The greenfield scaffolder, ``greenfield/bootstrap/bootstrap.py``, imported once."""
    if str(BOOTSTRAP) not in sys.path:
        sys.path.insert(0, str(BOOTSTRAP))
    return importlib.import_module("bootstrap")


def scaffolded_paths() -> dict[str, str]:
    """Each template file (``greenfield/templates/...``) and the path the scaffolder writes it to."""
    bootstrap = bootstrap_module()
    paths: dict[str, str] = {}
    for file in sorted(TEMPLATES.rglob("*")):
        if file.is_file():
            rel = file.relative_to(TEMPLATES).as_posix()
            target = bootstrap.target_path_for(rel)
            if target is not None:
                paths[f"greenfield/templates/{rel}"] = target
    return paths


def undeclared_names(paths: dict[str, str], cmap: dict[str, Any]) -> list[str]:
    """Templates whose scaffolded path matches a names entry but have no ``create`` moves entry with an intent."""
    declared = {
        (move["origin"]["path"], tuple(move.get("to", [])))
        for move in cmap["moves"]
        if move["action"] == "create" and move.get("intent")
    }
    problems = []
    for origin, target in sorted(paths.items()):
        hits = sorted({check for name in cmap["names"] if name_matches(name, target) for check in name["checks"]})
        if hits and (origin, (target,)) not in declared:
            problems.append(f"{origin} -> {target} has a name read by {', '.join(hits)} and no declared intent")
    return problems


# --- Playbook rows, sections and quotes -----------------------------------------------------------------------------


def commits_rows(text: str) -> list[int]:
    """The numbers of the rows in a playbook's ``## Commits`` table."""
    rows: list[int] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Commits"
            continue
        match = _COMMITS_ROW.match(line) if inside else None
        if match:
            rows.append(int(match.group(1)))
    return rows


def normalised(text: str) -> str:
    """``text`` with each whitespace run collapsed to one space, as the quote verifier compares quotes."""
    return " ".join(text.split())


@functools.lru_cache(maxsize=64)
def _sections(path: str, text: str) -> tuple[frozenset[str], tuple[tuple[str, str], ...]]:
    """The section addresses of one file, and each line's text with the address of the section that holds it."""
    nodes, _, parsed = _section_nodes(path, text)
    lines = tuple((line.text, holder) for line, holder in zip(parsed.document.lines, parsed.holders, strict=True))
    return frozenset(node.address for node in nodes), lines


def section_text(path: str, address: str, text: str) -> str | None:
    """The lines of the section at ``address`` and its subsections, or ``None`` when the file has no such section."""
    addresses, lines = _sections(path, text)
    if address != path and address not in addresses:
        return None
    return "\n".join(
        line for line, holder in lines if address == path or holder == address or holder.startswith(address + "/")
    )


def quote_problem(home: dict[str, Any], read: Reader = working_tree) -> str | None:
    """Why a keeps home does not hold its quote, or ``None``."""
    path, address = home["path"], home["section"]
    if not (address == path or address.startswith(path + "#")):
        return f"{address} is not a section of {path}"
    body = section_text(path, address, read(path))
    if body is None:
        return f"{path} has no section {address}"
    if normalised(home["quote"]) not in normalised(body):
        return f"{address} does not hold the quote {home['quote']!r}"
    return None


def mention_problem(keep: dict[str, Any], read: Reader = working_tree) -> str | None:
    """Why a kept quote's section does not mention the check ID, or ``None`` (also ``None`` when it has no section)."""
    home = keep["home"]
    body = section_text(home["path"], home["section"], read(home["path"]))
    if body is None or re.search(rf"\b{re.escape(keep['check'])}\b", body):
        return None
    return f"{keep['move']} -> {keep['check']}: {home['section']} does not mention {keep['check']}"


# --- Touches --------------------------------------------------------------------------------------------------------


def _is_folder(path: str) -> bool:
    return path.endswith("/")


def place_overlaps(path: str, where: dict[str, Any]) -> bool:
    """Whether a move path (a file, a folder ending in ``/`` or a glob) can overlap a place a read covers.

    A folder overlaps a root, any-depth or repository-level place only when the place is the folder itself or sits
    under it (rule R1): a move of ``artefacts/`` reaches the root place ``artefacts``, not every name the scan reads.
    """
    target, scope = str(where["path"]), str(where["scope"])
    if _is_folder(path):
        folder = path.rstrip("/")
        if scope == "glob":
            return target.startswith(path) or fnmatch.fnmatchcase(path + "x", target)
        return target == folder or target.startswith(path)
    if scope == "root":
        return path == target or fnmatch.fnmatchcase(target, path) or fnmatch.fnmatchcase(path, target)
    if scope == "glob":
        return fnmatch.fnmatchcase(path, target) or fnmatch.fnmatchcase(target, path)
    base = posixpath.basename(path)
    named = fnmatch.fnmatchcase(base, target) or fnmatch.fnmatchcase(target, base)
    if scope == "repository-level":
        return named and posixpath.dirname(path) in _REPOSITORY_LEVEL
    return named


def _covers(paths: Sequence[str], read: dict[str, Any]) -> str | None:
    for path in paths:
        for where in read["where"]:
            if place_overlaps(path, where):
                return path
    return None


def touch(move: dict[str, Any], read: dict[str, Any]) -> str | None:
    """The move path through which ``move`` touches ``read``, or ``None``."""
    action = move["action"]
    if action == "none":
        return None
    hit = _covers(move.get("from", []), read)
    if action in ("move", "untrack") and hit:
        return hit
    kind = read["what"]["kind"]
    content = set(move.get("content", []))
    if action == "create":
        fits = kind == "exists" or not content or bool(content & _CONTENT_FOR[kind])
    else:
        fits = not content or bool(content & _CONTENT_FOR[kind])
    if not fits:
        return None
    return _covers(move.get("to", []), read) or (hit if action in ("write", "rewrite") else None)


def unkept_pairs(cmap: dict[str, Any]) -> list[tuple[str, str]]:
    """Each (move id, check) a move declares in ``touches`` that no keeps entry covers."""
    kept = {(keep["move"], keep["check"]) for keep in cmap["keeps"]}
    return [
        (move["id"], check)
        for move in cmap["moves"]
        for check in move.get("touches", [])
        if (move["id"], check) not in kept
    ]


def unreviewed_pairs(cmap: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Each (move id, check, path) the coarse rule infers that no move declares and no keep covers.

    Template moves are left out: a template is the read's own source, and its intent is checked by the names rule.
    """
    kept = {(keep["move"], keep["check"]) for keep in cmap["keeps"]}
    pairs = []
    for move in cmap["moves"]:
        if "row" not in move["origin"]:
            continue
        declared = set(move.get("touches", []))
        for read in cmap["reads"]:
            check = read["check"]
            if read["source"] != "engine" or check in declared or (move["id"], check) in kept:
                continue
            path = touch(move, read)
            if path is not None:
                pairs.append((move["id"], check, path))
    return pairs


# --- The report -----------------------------------------------------------------------------------------------------


def coverage_problems(cmap: dict[str, Any], catalogue_ids: Sequence[str], read: Reader = working_tree) -> list[str]:
    """Catalogue checks with no reads entry, and playbook Commits rows with no moves entry."""
    have = {entry["check"] for entry in cmap["reads"]}
    problems = [f"{check} has no reads entry" for check in catalogue_ids if check not in have]
    declared: dict[str, set[int]] = {}
    for move in cmap["moves"]:
        if "row" in move["origin"]:
            declared.setdefault(move["origin"]["path"], set()).add(move["origin"]["row"])
    for playbook in sorted(PLAYBOOKS.glob("*.md")):
        path = playbook.relative_to(REPO).as_posix()
        for row in commits_rows(read(path)):
            if row not in declared.get(path, set()):
                problems.append(f"{path} Commits row {row} has no moves entry")
    return problems


def keeps_problems(cmap: dict[str, Any], catalogue_ids: Sequence[str]) -> list[str]:
    """Keeps entries that name an unknown move or check, repeat a pair, or keep a check the move does not touch."""
    moves = {move["id"]: set(move.get("touches", [])) for move in cmap["moves"]}
    known = set(catalogue_ids)
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for keep in cmap["keeps"]:
        pair = (keep["move"], keep["check"])
        if keep["move"] not in moves:
            problems.append(f"{pair[0]} -> {pair[1]}: no such move")
        elif keep["check"] not in moves[keep["move"]]:
            problems.append(f"{pair[0]} -> {pair[1]}: the move does not declare this check in touches")
        if keep["check"] not in known:
            problems.append(f"{pair[0]} -> {pair[1]}: no such check")
        if pair in seen:
            problems.append(f"{pair[0]} -> {pair[1]}: kept twice")
        seen.add(pair)
    return problems


def defined_symbols(text: str) -> set[str]:
    """The functions and classes a Python file defines at the top level, and each ``Class.method``."""
    symbols: set[str] = set()
    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        if isinstance(node, ast.ClassDef):
            symbols |= {
                f"{node.name}.{child.name}"
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return symbols


def enforcement_problem(boundary: dict[str, Any], read: Reader = working_tree) -> str | None:
    """Why a boundary's enforcer is missing or misdeclared, or ``None``."""
    path, symbol = boundary.get("enforced_by"), boundary.get("symbol")
    if boundary["enforcement"] not in ENFORCERS:
        return "a prose boundary names no enforced_by or symbol" if path or symbol else None
    if not (path and symbol):
        return f"the {boundary['enforcement']} enforcement needs enforced_by and symbol"
    try:
        text = read(path)
    except FileNotFoundError:
        return f"{path} does not exist"
    if symbol not in defined_symbols(text):
        return f"{path} defines no {symbol}"
    return None


def boundary_problems(boundaries: Sequence[dict[str, Any]], read: Reader = working_tree) -> list[str]:
    """Boundaries whose id repeats, whose home quote is gone, or whose enforcer no longer exists."""
    problems: list[str] = []
    seen: set[str] = set()
    for boundary in boundaries:
        name = boundary["id"]
        if name in seen:
            problems.append(f"{name}: the id is used twice")
        seen.add(name)
        problems += [
            f"{name}: {problem}"
            for problem in (quote_problem(boundary["home"], read), enforcement_problem(boundary, read))
            if problem
        ]
    return problems


def report(cmap: dict[str, Any], catalogue_ids: Sequence[str], read: Reader = working_tree) -> dict[str, list[str]]:
    """Every problem the static gate finds, by kind."""
    kept = [keep for keep in cmap["keeps"] if keep["status"] == "kept"]
    quotes = [problem for keep in kept if (problem := quote_problem(keep["home"], read))]
    return {
        "unkept": [f"{move} -> {check}" for move, check in unkept_pairs(cmap)],
        "quote": quotes,
        "mention": [problem for keep in kept if (problem := mention_problem(keep, read))],
        "coverage": coverage_problems(cmap, catalogue_ids, read),
        "names": undeclared_names(scaffolded_paths(), cmap),
        "constants": [p for entry in cmap["reads"] for p in read_constant_problems(entry)]
        + names_constant_problems(cmap["names"]),
        "keeps": keeps_problems(cmap, catalogue_ids),
        "boundary": boundary_problems(cmap["boundaries"], read),
    }


def format_text(found: dict[str, list[str]], unreviewed: Sequence[str], verbose: bool = False) -> str:
    lines: list[str] = []
    for kind in KINDS:
        items = found[kind]
        lines.append(f"{kind}: {len(items)}")
        lines += [f"  {item}" for item in items]
    lines.append(f"unreviewed (advice, not a problem): {len(unreviewed)}")
    if verbose:
        lines += [f"  {item}" for item in unreviewed]
    total = sum(len(items) for items in found.values())
    lines.append(f"consistency map: {total} problem(s)")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="consistency_map.py", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--map",
        type=Path,
        default=MAP_PATH,
        help="the map file; its names file is beside it (default: dev/consistency-map.json)",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="exit 1 when the gate finds a problem")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="also list the unreviewed pairs in text mode, and the broad checks of each review line",
    )
    parser.add_argument(
        "--base",
        nargs="?",
        const=DEFAULT_BASE,
        metavar="GIT_REF",
        help="also run change mode against this git ref (default origin/dev)",
    )
    parser.add_argument(
        "--at", metavar="GIT_REF", help="with --base: the new side is this commit, not the working tree"
    )
    parser.add_argument("--no-evidence", action="store_true", help="with --base: skip the evidence comparison")
    args = parser.parse_args(argv)
    if args.base is None and (args.at is not None or args.no_evidence):
        parser.error("--at and --no-evidence need --base")
    try:
        cmap = load_map(args.map)
    except MapError as exc:
        parser.error(str(exc))
    catalogue_ids = [check["id"] for check in json.loads(CATALOGUE.read_text(encoding="utf-8"))["checks"]]
    found = report(cmap, catalogue_ids)
    unreviewed = [f"{move} -> {check} (through {path})" for move, check, path in unreviewed_pairs(cmap)]
    change = None
    if args.base is not None:
        import consistency_map_change as cmc
        from docindex.evidence import EvidenceError
        from docindex.gitread import GitError

        try:
            change = cmc.change_report(
                cmap,
                REPO,
                args.base,
                args.at,
                cmc.project_config(),
                engine_dir=None if args.no_evidence else ENGINE,
            )
        except GitError as exc:
            parser.error(str(exc))
        except EvidenceError as exc:
            print(f"consistency_map.py: the evidence comparison failed: {exc}", file=sys.stderr)
            return 1
    if args.format == "json":
        data: dict[str, Any] = {**found, "unreviewed": unreviewed}
        if change is not None:
            data["change"] = cmc.to_dict(change)
        sys.stdout.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(format_text(found, unreviewed, args.verbose))
        if change is not None:
            sys.stdout.write(cmc.format_text(change, args.verbose))
    problems = any(found.values()) or (change is not None and any(change.problems.values()))
    return 1 if args.strict and problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
