# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Every engine check asks the target only for what ``audit/rules/reads.py`` declares.

Each implemented check runs on every fixture under ``tests/fixtures/``, in process, with a recording inventory and
recording ``pathlib`` reads. The recorder keeps each path a check asks for inside the target:

- ``has``: a name looked for at any depth (``Inventory.has``);
- ``read``: one file's text (``Inventory.read``, ``Path.read_text``, ``read_bytes`` or ``open``);
- ``stat``: a path tested on disk (``Path.exists``, ``is_file`` or ``is_dir``);
- ``match``: a pattern or a suffix tried on every name (``Inventory.match``, ``Inventory.with_suffix``).

A check that walks ``Inventory.files`` or ``Inventory.paths`` for names asks for no path; the files it then reads
are recorded. A second run of each check hands it every ``FileEntry.rel``, and every path git tracks, as a tracking
string, the name probe. It records a fifth kind of ask:

- ``name``: a name a check compares a scanned path with in its own code (``==``, ``!=``, ``startswith``,
  ``endswith``, ``in``, ``fnmatch``), and whether the path was lower-cased first.

The name probe is report-only for now: the test prints the ``name`` asks that no declared place covers and the
declared places that no ask of any kind reaches, and fails on neither. A place with ``via`` is read upstream, by
the scan's file kinds or by component detection, so no ask needs to reach it; the report counts it apart. A further test proves that the probe changes
no check's result. Git commands and reads outside the target (``$HOME``) are not paths of the target. The stack and the
components are detected before the checks run, so their reads belong to no check.

An ask is covered when a declared place matches it at its scope. ``has`` looks at any depth, so a ``root`` place
does not cover it. A ``match`` pattern is covered by a place with the same path, the same path under ``**/``, or the
place ``**``.
"""

from __future__ import annotations

import fnmatch
import os
import posixpath
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import fields, replace
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.components import detect_components  # noqa: E402
from audit.probes import ProbeSession  # noqa: E402
from audit import scan  # noqa: E402
from audit.rules import checks, reads, variants  # noqa: E402
from audit.rules.checks import _common, agt, con, sec  # noqa: E402
from audit.rules.registry import REGISTRY, applicable_checks  # noqa: E402
from audit.scan import CONTENT_READ_LIMIT, Inventory, build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402
from audit.target import resolve_target  # noqa: E402
from test_positive_fixture import TEMPLATES, locate_scaffolder  # noqa: E402

Ask = tuple[str, str]
#: A ``name`` ask: the operation (``eq``, ``start``, ``end``, ``sub`` or ``glob``), the operand, and whether the
#: scanned path was case-folded before the comparison.
NameAsk = tuple[str, str, bool]

_REPOSITORY_LEVEL = ("", ".github/", ".gitlab/", "docs/")


class _RecordingInventory(Inventory):
    """An inventory that writes each path a check asks for into ``asks``."""

    asks: set[Ask]

    def has(self, rel: str) -> bool:
        self.asks.add(("has", rel.strip("/")))
        return super().has(rel)

    def match(self, *patterns: str) -> list[str]:
        self.asks.update(("match", pattern) for pattern in patterns)
        return super().match(*patterns)

    def with_suffix(self, *suffixes: str) -> list[str]:
        self.asks.update(("match", "*" + suffix) for suffix in suffixes)
        return super().with_suffix(*suffixes)

    def read(self, rel: str, limit: int = CONTENT_READ_LIMIT) -> str | None:
        self.asks.add(("read", rel))
        return super().read(rel, limit)


def _recording(inventory: Inventory) -> _RecordingInventory:
    copy = _RecordingInventory(**{f.name: getattr(inventory, f.name) for f in fields(Inventory)})
    copy.asks = set()
    return copy


@contextmanager
def _recording_disk(root: Path, asks: set[Ask]) -> Iterator[None]:
    """Record the ``pathlib`` reads and tests of paths under ``root`` while the block runs."""
    prefix = str(root) + "/"
    saved: dict[str, Callable[..., Any]] = {}

    def wrap(name: str, kind: str) -> None:
        original = getattr(Path, name)
        saved[name] = original

        def recorded(self: Path, *args: Any, **kwargs: Any) -> Any:
            text = str(self)
            if text.startswith(prefix):
                asks.add((kind, text[len(prefix) :]))
            return original(self, *args, **kwargs)

        setattr(Path, name, recorded)

    for name in ("read_text", "read_bytes", "open"):
        wrap(name, "read")
    for name in ("exists", "is_file", "is_dir"):
        wrap(name, "stat")
    try:
        yield
    finally:
        for name, original in saved.items():
            setattr(Path, name, original)


def _glob_match(path: str, pattern: str) -> bool:
    """A glob from the root, where ``**/`` also matches no folder (the map's ``glob`` scope)."""
    if pattern == "**" or fnmatch.fnmatchcase(path, pattern):
        return True
    return "**/" in pattern and fnmatch.fnmatchcase(path, pattern.replace("**/", "", 1))


def place_covers(place: reads.Place, ask: Ask) -> bool:
    """Whether one declared place covers one ask."""
    kind, path = ask
    if kind == "match":
        # Inventory.match tries the pattern on the path and on the base name, so "**/" + pattern is the same ask.
        return place.path in (path, "**/" + path, "**")
    if kind == "has":
        # Inventory.has finds the name at any depth, so the place must cover it below a folder too.
        return place_covers(place, ("read", path)) and place_covers(place, ("read", "any/" + path))
    base = posixpath.basename(path)
    if place.scope == reads.ROOT:
        return path == place.path or path.startswith(place.path + "/")
    if place.scope == reads.ANY_DEPTH:
        if "/" in place.path:
            return path == place.path or path.endswith("/" + place.path)
        return fnmatch.fnmatchcase(base, place.path)
    if place.scope == reads.REPOSITORY_LEVEL:
        return any(path == folder + base for folder in _REPOSITORY_LEVEL) and fnmatch.fnmatchcase(base, place.path)
    return _glob_match(path, place.path)


def _folded_covers(place: reads.Place, ask: Ask) -> bool:
    """Whether a ``fold`` place covers the ask in lower case; an ``exact`` place never does."""
    lowered = replace(place, path=place.path.lower())
    return place.case == reads.FOLD and place_covers(lowered, (ask[0], ask[1].lower()))


def _covered(check: str, ask: Ask) -> bool:
    return any(place_covers(place, ask) or _folded_covers(place, ask) for place in reads.READS[check].where)


def _named(root: Path, asks: set[Ask], path: str) -> bool:
    for kind, rel in asks:
        if kind != "read":
            continue
        try:
            if path in (root / rel).read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    return False


def _text_core(operand: str) -> str:
    """The path a check took from the target's text, less the "*/" or "/*" it added to match below or above it."""
    core = operand.removeprefix("*/")
    for tail in ("/*", "/"):
        core = core.removesuffix(tail)
    return core


def undeclared(check: str, root: Path, asks: set[Ask]) -> set[Ask]:
    """The asks of one run that no declared place covers.

    A declaration with ``named_by_text`` also allows a path that is written in a file the same run read; that file
    itself must be declared.
    """
    missing = {ask for ask in asks if not _covered(check, ask)}
    if reads.READS[check].named_by_text:
        missing = {ask for ask in missing if not _named(root, asks, ask[1])}
    return missing


# The name probe. It leans on CPython details: a set or dict lookup calls ``__eq__`` only on a hash hit, so a name
# held in a set is seen only when a fixture has the file, so the probe swaps the check modules' held sets and
# dicts of names for recording copies (``_held_containers``). ``strip``, ``lstrip`` and ``rstrip`` keep a name tracked.
# Regular expressions and ``Path`` objects built from a name return plain strings, which the probe no longer tracks.

_CHECKS_DIR = os.path.dirname(os.path.abspath(checks.__file__)) + os.sep
_SCAN_FILE = os.path.abspath(scan.__file__)
_THIS_FILE = os.path.abspath(__file__)

#: Operands shorter than this are not recorded. A one- or two-character operand ("/", ".", "..", "-") fits nearly
#: every path, so it says nothing about which place a check reads, and as an uncovered ask it would only be noise.
_SHORTEST_OPERAND = 3

#: Where the name asks of the running check go, with the check's id; empty outside the probe's block.
_NAME_SINK: list[set[NameAsk]] = []
_NAME_CHECK: list[str | None] = []

#: Functions whose comparisons are never reads, as (check, or None for every check; function; reason). The probe
#: records nothing that a frame of one of them asks.
_NOT_READS_IN: tuple[tuple[str | None, Callable[..., Any], str], ...] = (
    (None, agt.is_non_instruction, "an exclusion: a path its globs match is left out of the instruction files"),
    (
        None,
        variants.classify_present,
        "it sorts the instruction files a check already chose by its declared places, and picks no new path",
    ),
    (
        None,
        variants.mis_cased_canonical_candidates,
        "it sorts the instruction files a check already chose by its declared places, and picks no new path",
    ),
    (
        "AGT-02",
        agt.instruction_paths,
        "AGT-02 keeps only the paths that end in <component>/AGENTS.md, so the other instruction names it "
        "compares on the way decide nothing",
    ),
)

#: Names a check compares only to leave a path out, as (check, operation, names, reason). Such an ask reads nothing.
_NOT_READ_NAMES: tuple[tuple[str, str, frozenset[str], str], ...] = (
    (
        "SEC-01",
        "eq",
        frozenset(sec._ENV_TEMPLATE_BASENAMES),
        "a committed template (.env.example, env.example) is left out of the tracked .env files",
    ),
    ("AGT-13", "eq", frozenset({agt._DOCS_STYLE_GUIDE}), "the docs style guide never counts as a conventions file"),
    ("TOOL-07", "start", frozenset({".git/"}), "a hook file under .git/ is left out: git's own hooks are not shared"),
)


def _not_a_read(check: str, ask: NameAsk) -> bool:
    return any(check == c and ask[0] == op and ask[1] in names for c, op, names, _why in _NOT_READ_NAMES)


def _in_a_non_read(code: Any) -> bool:
    check = _NAME_CHECK[-1] if _NAME_CHECK else None
    return any(code is function.__code__ and owner in (None, check) for owner, function, _why in _NOT_READS_IN)


def _asked_by_a_check(frame: Any) -> bool:
    """Whether the comparison was made by check code, walking out from the caller's frame.

    ``Inventory`` methods are recorded already as ``has``, ``match`` or ``read``, and the recorder's own frames ask
    nothing, so either ends the walk. Library frames (``fnmatch``, ``audit/stack.py``) are passed through. A
    function of ``_NOT_READS_IN`` anywhere on the way out means no read, so the walk goes on past the first check
    frame (a generator expression inside such a function is a frame of its own).
    """
    asked = False
    while frame is not None:
        if _in_a_non_read(frame.f_code):
            return False
        name = frame.f_code.co_filename
        if name in (_SCAN_FILE, _THIS_FILE):
            return asked
        asked = asked or name.startswith(_CHECKS_DIR)
        frame = frame.f_back
    return asked


def _record_name(op: str, operands: object, name: _TrackedName, frame: Any) -> None:
    if not _NAME_SINK or not _asked_by_a_check(frame):
        return
    for operand in operands if isinstance(operands, tuple) else (operands,):
        # A tracked operand is another scanned path, not a name the check holds.
        if not isinstance(operand, str) or isinstance(operand, _TrackedName) or len(operand) < _SHORTEST_OPERAND:
            continue
        # One folder segment of a path, a base name above all, never holds a slash, so it never equals a name
        # that does: AGT-01 looks each base name up in a set that also holds .github/copilot-instructions.md.
        if op == "eq" and name.segment and "/" in operand:
            continue
        _NAME_SINK[-1].add((op, str(operand), name.folded))


class _TrackedName(str):
    """A ``FileEntry.rel`` that records what check code compares it with. It compares and hashes as ``str``.

    ``folded`` is set once the name is lower-cased; ``segment`` once it is one part of a path split on ``/``, so it
    can hold no slash on any target.
    """

    folded: bool
    segment: bool

    def __new__(cls, value: str, folded: bool = False, segment: bool = False) -> _TrackedName:
        made = super().__new__(cls, value)
        made.folded = folded
        made.segment = segment
        return made

    def _like(self, value: str, folded: bool | None = None, segment: bool | None = None) -> _TrackedName:
        return _TrackedName(
            value, self.folded if folded is None else folded, self.segment if segment is None else segment
        )

    def __eq__(self, other: object) -> bool:
        _record_name("eq", other, self, sys._getframe(1))
        return str.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        _record_name("eq", other, self, sys._getframe(1))
        return str.__ne__(self, other)

    __hash__ = str.__hash__

    def startswith(self, prefix: Any, *args: Any) -> bool:
        _record_name("start", prefix, self, sys._getframe(1))
        return str.startswith(self, prefix, *args)

    def endswith(self, suffix: Any, *args: Any) -> bool:
        _record_name("end", suffix, self, sys._getframe(1))
        return str.endswith(self, suffix, *args)

    def __contains__(self, part: object) -> bool:
        _record_name("sub", part, self, sys._getframe(1))
        return str.__contains__(self, part)  # type: ignore[operator]

    def lower(self) -> _TrackedName:
        return self._like(str.lower(self), folded=True)

    def casefold(self) -> _TrackedName:
        return self._like(str.casefold(self), folded=True)

    def strip(self, chars: str | None = None) -> _TrackedName:
        return self._like(str.strip(self, chars))

    def lstrip(self, chars: str | None = None) -> _TrackedName:
        return self._like(str.lstrip(self, chars))

    def rstrip(self, chars: str | None = None) -> _TrackedName:
        return self._like(str.rstrip(self, chars))

    def split(self, sep: str | None = None, maxsplit: int = -1) -> list[str]:
        parts = str.split(self, sep, maxsplit)
        # On "/", every part but the last is one segment; the last is one too unless the limit left slashes in it.
        whole = maxsplit < 0 or len(parts) <= maxsplit
        return [
            self._like(part, segment=self.segment or (sep == "/" and (whole or i < len(parts) - 1)))
            for i, part in enumerate(parts)
        ]

    def rsplit(self, sep: str | None = None, maxsplit: int = -1) -> list[str]:
        parts = str.rsplit(self, sep, maxsplit)
        # On "/", every part but the first is one segment, and the last always is: rsplit("/", 1)[-1] is a base name.
        whole = maxsplit < 0 or len(parts) <= maxsplit
        return [
            self._like(part, segment=self.segment or (sep == "/" and (whole or i > 0 or i == len(parts) - 1)))
            for i, part in enumerate(parts)
        ]

    def partition(self, separator: str) -> tuple[str, str, str]:
        head, middle, tail = str.partition(self, separator)
        return self._like(head, segment=self.segment or separator == "/"), middle, self._like(tail)

    def rpartition(self, separator: str) -> tuple[str, str, str]:
        head, middle, tail = str.rpartition(self, separator)
        return self._like(head), middle, self._like(tail, segment=self.segment or separator == "/")

    def __getitem__(self, key: Any) -> _TrackedName:
        return self._like(str.__getitem__(self, key))


def _record_members(members: Iterable[str], key: object, frame: Any) -> None:
    """A tracked name looked up in a held set or dict asks for every member: it would match any of them."""
    if isinstance(key, _TrackedName):
        _record_name("eq", tuple(members), key, frame)


class _RecordingFrozenset(frozenset[str]):
    """A check's frozenset of names that records a lookup of a tracked name, hit or miss."""

    def __contains__(self, key: object) -> bool:
        _record_members(self, key, sys._getframe(1))
        return frozenset.__contains__(self, key)

    def __repr__(self) -> str:
        return repr(frozenset(self))


class _RecordingSet(set[str]):
    """A check's set of names that records a lookup of a tracked name, hit or miss."""

    def __contains__(self, key: object) -> bool:
        _record_members(self, key, sys._getframe(1))
        return set.__contains__(self, key)

    def __repr__(self) -> str:
        return repr(set(self))


class _RecordingDict(dict[str, Any]):
    """A check's dict keyed by names that records a lookup of a tracked name, hit or miss."""

    def __contains__(self, key: object) -> bool:
        _record_members(self, key, sys._getframe(1))
        return dict.__contains__(self, key)

    def __getitem__(self, key: str) -> Any:
        _record_members(self, key, sys._getframe(1))
        return dict.__getitem__(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        _record_members(self, key, sys._getframe(1))
        return dict.get(self, key, default)


_RECORDING_TYPES: dict[type, type] = {frozenset: _RecordingFrozenset, set: _RecordingSet, dict: _RecordingDict}

#: The held containers of names in the check modules and their recording copies, built once.
_HELD: list[tuple[Any, str, Any, Any]] = []


def _held_containers() -> list[tuple[Any, str, Any, Any]]:
    """Every module-level set, frozenset or dict of the check modules whose members are all strings.

    A set or dict lookup calls ``__eq__`` only on a hash hit, so without a recording copy a name held there is seen
    only when a fixture has the file. A container two modules share gets one copy.
    """
    if not _HELD:
        copies: dict[int, Any] = {}
        for module_name, module in sorted(sys.modules.items()):
            if not module_name.startswith(checks.__name__ + ".") or module is None:
                continue
            for name, value in sorted(vars(module).items()):
                recording = _RECORDING_TYPES.get(type(value))
                if name.startswith("__") or recording is None or not value:
                    continue
                if not all(isinstance(member, str) for member in value):
                    continue
                copy = copies.setdefault(id(value), recording(value))
                _HELD.append((module, name, value, copy))
    return _HELD


@contextmanager
def _recording_names(sink: set[NameAsk], check: str | None = None) -> Iterator[None]:
    """Record the ``name`` asks of tracked paths while the block runs, ``fnmatch`` and ``basename`` included.

    The paths git tracks are tracked names too: a check that reads the tracked set (``tracked_in_scope``) compares
    those, not ``FileEntry.rel``. The check modules' held sets and dicts of names are swapped for recording copies.
    """
    saved_fnmatch, saved_fnmatchcase = fnmatch.fnmatch, fnmatch.fnmatchcase
    saved_basename, saved_os_basename = posixpath.basename, os.path.basename
    saved_tracked_files = _common.tracked_files

    def tracked_files(target: Path) -> set[str] | None:
        tracked = saved_tracked_files(target)
        return None if tracked is None else {_TrackedName(rel) for rel in tracked}

    def globbed(original: Callable[[Any, str], bool]) -> Callable[[Any, str], bool]:
        def recorded(name: Any, pattern: str) -> bool:
            if isinstance(name, _TrackedName):
                _record_name("glob", pattern, name, sys._getframe(1))
            return original(name, pattern)

        return recorded

    def basename(path: Any) -> Any:
        base = saved_basename(path)
        return path._like(base, segment=True) if isinstance(path, _TrackedName) else base

    fnmatch.fnmatch, fnmatch.fnmatchcase = globbed(saved_fnmatch), globbed(saved_fnmatchcase)
    posixpath.basename = basename
    os.path.basename = basename
    _common.tracked_files = tracked_files
    for module, name, _value, copy in _held_containers():
        setattr(module, name, copy)
    _NAME_SINK.append(sink)
    _NAME_CHECK.append(check)
    try:
        yield
    finally:
        _NAME_SINK.pop()
        _NAME_CHECK.pop()
        fnmatch.fnmatch, fnmatch.fnmatchcase = saved_fnmatch, saved_fnmatchcase
        posixpath.basename, os.path.basename = saved_basename, saved_os_basename
        _common.tracked_files = saved_tracked_files
        for module, name, value, _copy in _held_containers():
            setattr(module, name, value)


def _probing(inventory: Inventory) -> _RecordingInventory:
    copy = _recording(inventory)
    copy.files = [replace(entry, rel=_TrackedName(entry.rel)) for entry in inventory.files]
    return copy


def name_hits(place: reads.Place, ask: NameAsk) -> bool:
    """Whether one ``name`` ask and one declared place meet, the rule both report directions use (a heuristic)."""
    op, operand, folded = ask
    path = place.path.lower() if folded else place.path
    base = posixpath.basename(path)
    if path == "**":
        # The whole tree holds every name, whatever a check compares a path with.
        return True
    if op == "eq":
        # A whole path, a base name, a path a glob place fits, or the folder a place sits under. A repository-level
        # place also sits under each of the folders that scope names, and a base name found at any depth meets
        # itself below a folder ("artefacts/.gitignore" meets ".gitignore").
        return (
            operand in (path, base, path.rstrip("/"))
            or fnmatch.fnmatchcase(operand, path)
            or path.startswith(operand + "/")
            or (place.scope == reads.REPOSITORY_LEVEL and operand + "/" in _REPOSITORY_LEVEL)
            or (
                place.scope == reads.ANY_DEPTH
                and "/" not in path
                and fnmatch.fnmatchcase(operand.rsplit("/")[-1], path)
            )
        )
    if op == "end":
        # A suffix meets a place only as a file type (".md"), a whole base name or a path tail. A place found at any
        # depth also stands for itself below a folder, so "/Makefile" meets it. A base name that ends in a wildcard
        # takes any file type, and a path tail meets a glob it fits.
        tails = (path,) if place.scope == reads.ROOT else (path, "any/" + path)
        if operand.startswith(".") and "/" not in operand and base.endswith("*"):
            return True
        if place.scope == reads.GLOB and "/" in operand and _glob_match(operand, path):
            return True
        return any(tail.endswith(operand) for tail in tails) and (
            operand.startswith(("/", ".")) or operand == base or "/" in operand
        )
    if op == "start":
        # A prefix meets a place that starts with it, or a glob whose fixed start, from the root or after "**/",
        # starts with the prefix or is one of its folders ("docs/explanation/" meets "docs/**/*.md").
        if path.startswith(operand) or operand.rstrip("/") == path.rstrip("/"):
            return True
        return place.scope == reads.GLOB and any(
            fixed and (operand.startswith(fixed) or fixed.startswith(operand))
            for fixed in (_fixed_start(path), _fixed_start(path.removeprefix("**/")))
        )
    if op == "sub":
        return operand in path
    # A glob operand meets a place it fits, as a name or as a narrower glob ("conventions*" meets "*convention*").
    return (
        fnmatch.fnmatchcase(path, operand)
        or fnmatch.fnmatchcase(base, operand)
        or operand == path
        or fnmatch.fnmatchcase(operand, path)
        or ("/" not in path and fnmatch.fnmatchcase(operand, base))
    )


def _fixed_start(pattern: str) -> str:
    """The part of a glob before its first wildcard."""
    cut = min((pattern.index(mark) for mark in "*?[" if mark in pattern), default=len(pattern))
    return pattern[:cut]


def _seen(check: str, place: reads.Place, asks: set[Ask], names: set[NameAsk]) -> bool:
    """Whether any recorded ask reaches a declared place: a covered ask, a pattern its name fits, or a name ask."""
    for kind, path in asks:
        if place_covers(place, (kind, path)):
            return True
        # A name looked for at any depth is looked for at the root too, so it reaches a root place of that name.
        if kind == "has" and place.scope == reads.ROOT and place.path == path:
            return True
        if kind == "match" and (
            fnmatch.fnmatchcase(posixpath.basename(place.path), path) or fnmatch.fnmatchcase(place.path, path)
        ):
            return True
        if _folded_covers(place, (kind, path)):
            return True
    return any(name_hits(place, ask) for ask in names)


def _places_by_reach(recording: Recorded) -> dict[str, dict[str, list[reads.Place]]]:
    """The declared places that no recorded ask reaches, by check: ``upstream`` when ``via`` accounts for them."""
    found: dict[str, dict[str, list[reads.Place]]] = {"unseen": {}, "upstream": {}}
    for check, declared in reads.READS.items():
        for place in declared.where:
            if not _seen(check, place, recording.asks[check], recording.names[check]):
                found["upstream" if place.via else "unseen"].setdefault(check, []).append(place)
    return found


def unseen_places(recording: Recorded) -> dict[str, list[reads.Place]]:
    """The declared places that no recorded ask of any kind reaches and no upstream step reads, by check."""
    return _places_by_reach(recording)["unseen"]


def uncovered_names(recording: Recorded) -> dict[str, set[NameAsk]]:
    """The ``name`` asks that no declared place of their check meets, by check."""
    uncovered: dict[str, set[NameAsk]] = {}
    for check, names in recording.names.items():
        missing = {ask for ask in names if not any(name_hits(place, ask) for place in reads.READS[check].where)}
        if missing:
            uncovered[check] = missing
    return uncovered


def _tally(found: dict[str, Any]) -> str:
    counts = sorted((-len(items), check) for check, items in found.items())
    return ", ".join(f"{check} {-count}" for count, check in counts) or "none"


def name_probe_summary(recording: Recorded, detail: bool = False) -> str:
    """The report the probe prints: totals and a count per check, or every item with ``detail``."""
    reach = _places_by_reach(recording)
    unseen = reach["unseen"]
    uncovered = uncovered_names(recording)
    places = sum(len(declared.where) for declared in reads.READS.values())
    unseen_count = sum(map(len, unseen.values()))
    upstream_count = sum(map(len, reach["upstream"].values()))
    lines = [
        f"name probe (report-only): {sum(map(len, recording.names.values()))} name asks, "
        f"{sum(map(len, uncovered.values()))} not covered by a declaration, in {len(uncovered)} checks",
        f"name probe: {places} declared places, {places - unseen_count - upstream_count} seen, "
        f"{upstream_count} read upstream (via), {unseen_count} unseen, in {len(unseen)} checks",
        f"  unseen places: {_tally(unseen)}",
        f"  uncovered name asks: {_tally(uncovered)}",
    ]
    if detail:
        for check, missing_places in sorted(unseen.items()):
            lines.extend(f"  unseen {check} {place.scope} {place.path}" for place in missing_places)
        for check, missing_asks in sorted(uncovered.items()):
            lines.extend(
                f"  uncovered {check} {op} {operand!r} folded={folded}" for op, operand, folded in sorted(missing_asks)
            )
    return "\n".join(lines)


def _fixtures() -> list[Path]:
    return sorted(path for path in support.FIXTURES_DIR.iterdir() if path.is_dir())


def _scaffold(target: Path) -> Path:
    """A greenfield scaffold, the positive fixture: a whole project, so the checks find more of what they look for."""
    target.mkdir()
    proc = subprocess.run(
        [sys.executable, str(locate_scaffolder()), str(target), "--no-git", "--templates", str(TEMPLATES)],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"scaffolder failed:\n{proc.stderr}")
    return target


class Recorded:
    """What every implemented check asked for on every fixture, and what no declaration covers.

    Each check runs twice: once as recorded, then again under the name probe. ``changed`` lists the runs whose
    result or recorded asks differ between the two, which the probe must never cause.
    """

    def __init__(self) -> None:
        self.asks: dict[str, set[Ask]] = {spec.id: set() for spec in REGISTRY if spec.impl is not None}
        self.runs: dict[str, int] = dict.fromkeys(self.asks, 0)
        self.undeclared: dict[str, set[tuple[str, str, str]]] = {check: set() for check in self.asks}
        self.names: dict[str, set[NameAsk]] = {check: set() for check in self.asks}
        self.changed: list[tuple[str, str]] = []
        with tempfile.TemporaryDirectory() as tmp:
            # CON-04 walks the scan only when it may write its draft: beside a report outside every target, as
            # --emit-baseline --force does, and the same file each run so both runs of a check give one result.
            con.set_emit_target(Path(tmp) / "out" / "report.json", force=True)
            try:
                for path in _fixtures():
                    self._record(path)
                self._record(_scaffold(Path(tmp) / "scaffold"))
            finally:
                con.set_emit_target(None)

    def _record(self, path: Path) -> None:
        target = resolve_target(path)
        inventory = build_inventory(target.path)
        stack = detect_stack(inventory)
        components = detect_components(inventory)
        session = ProbeSession(cwd=target.path, user_config=False)
        for spec in applicable_checks(stack):
            if spec.impl is None:
                continue
            recording = _recording(inventory)
            with _recording_disk(target.path, recording.asks):
                result = spec.run(
                    target=target, inventory=recording, stack=stack, components=components, session=session
                )
            probed = _probing(inventory)
            names: set[NameAsk] = set()
            with _recording_disk(target.path, probed.asks), _recording_names(names, spec.id):
                probed_result = spec.run(
                    target=target, inventory=probed, stack=stack, components=components, session=session
                )
            if repr(probed_result) != repr(result) or probed.asks != recording.asks:
                self.changed.append((path.name, spec.id))
            names = {ask for ask in names if not _not_a_read(spec.id, ask)}
            if reads.READS[spec.id].named_by_text:
                names = {ask for ask in names if not _named(target.path, probed.asks, _text_core(ask[1]))}
            self.names[spec.id] |= names
            self.asks[spec.id] |= recording.asks
            self.runs[spec.id] += 1
            missing = undeclared(spec.id, target.path, recording.asks)
            self.undeclared[spec.id] |= {(path.name, kind, rel) for kind, rel in missing}


_RECORDED: list[Recorded] = []


def recorded() -> Recorded:
    """One recording for the whole module: every check on every fixture takes a few seconds."""
    if not _RECORDED:
        _RECORDED.append(Recorded())
    return _RECORDED[0]


class DeclarationTest(unittest.TestCase):
    def test_every_implemented_check_declares_its_reads_in_registry_order(self) -> None:
        implemented = [spec.id for spec in REGISTRY if spec.impl is not None]
        self.assertEqual(list(reads.READS), implemented)

    def test_the_declarations_use_the_map_vocabulary(self) -> None:
        for check, declared in reads.READS.items():
            self.assertIn(declared.what.kind, reads.KINDS, check)
            self.assertIn(declared.binding, reads.BINDINGS, check)
            self.assertEqual(declared.window is not None, declared.binding == "window", check)
            self.assertTrue(declared.where, check)
            for place in declared.where:
                self.assertIn(place.scope, reads.SCOPES, check)
                self.assertIn(place.via, (None, *reads.VIAS), check)
                self.assertIn(place.case, reads.CASES, check)

    def test_a_held_place_follows_its_constant(self) -> None:
        from audit.rules.checks import tst

        reference = "audit.rules.checks.tst:_FASTPATH_DOCS"
        declared = [place.path for place in reads.READS["TST-04"].where if place.constant == reference]
        self.assertEqual(declared, list(tst._FASTPATH_DOCS))
        self.assertIn(reference, reads.READS["TST-04"].constants)

    def test_the_case_folded_and_text_named_checks_are_declared(self) -> None:
        folded = sorted({check for check, d in reads.READS.items() if any(p.case == reads.FOLD for p in d.where)})
        named = sorted(check for check, declared in reads.READS.items() if declared.named_by_text)
        self.assertEqual(folded, ["AGT-12", "AGT-13"])
        self.assertEqual(named, ["AGT-06", "AGT-10", "CON-01"])

    def test_constants_are_named_only_when_they_hold_every_place(self) -> None:
        self.assertIn("audit.rules.checks._common:RUNNER_PRECEDENCE", reads.READS["CMD-01"].constants)
        self.assertTrue(any(place.constant for place in reads.READS["TST-01"].where))
        self.assertEqual(reads.READS["TST-01"].constants, ())


class RecordingTest(unittest.TestCase):
    def test_every_implemented_check_ran_on_a_fixture(self) -> None:
        runs = recorded().runs
        self.assertEqual(list(runs), list(reads.READS))
        self.assertEqual([check for check, count in runs.items() if not count], [])

    def test_every_check_asks_only_for_what_it_declares(self) -> None:
        found = {check: sorted(asks) for check, asks in recorded().undeclared.items() if asks}
        self.assertEqual(found, {})

    def test_a_place_removed_from_a_declaration_fails(self) -> None:
        asks = recorded().asks["TST-04"]
        declared = reads.READS["TST-04"]
        thinner = replace(declared, where=tuple(place for place in declared.where if place.path != "AGENTS.md"))
        with mock.patch.dict(reads.READS, {"TST-04": thinner}):
            self.assertIn(("has", "AGENTS.md"), undeclared("TST-04", support.FIXTURES_DIR, asks))

    def test_the_recorder_sees_inventory_and_disk_asks(self) -> None:
        asks = recorded().asks
        self.assertIn(("has", "AGENTS.md"), asks["TST-04"])
        self.assertIn(("read", "AGENTS.md"), asks["AGT-01"])
        self.assertIn(("stat", "docs"), asks["DOC-01"])
        self.assertIn(("match", "*_test.go"), asks["TST-01"])


class NameProbeTest(unittest.TestCase):
    def test_the_name_probe_changes_no_check_result(self) -> None:
        recording = recorded()
        self.assertGreater(sum(recording.runs.values()), 1000)
        self.assertEqual(recording.changed, [])

    def test_the_probe_sees_a_name_compared_in_check_code(self) -> None:
        self.assertTrue(any(op == "eq" for op, _operand, _folded in recorded().names["AGT-01"]))

    def test_the_probe_ignores_test_frames(self) -> None:
        sink: set[NameAsk] = set()
        name = _TrackedName("docs/AGENTS.md")
        with _recording_names(sink):
            self.assertTrue(name.endswith(".md"))
            self.assertTrue(fnmatch.fnmatchcase(name, "*.md"))
        self.assertEqual(sink, set())

    def test_lower_marks_a_tracked_name_case_folded(self) -> None:
        name = _TrackedName("README.md")
        self.assertTrue(name.lower().folded)
        self.assertFalse(name[:6].folded)
        self.assertEqual(name.lower(), "readme.md")

    def test_strip_keeps_a_name_tracked(self) -> None:
        name = _TrackedName("/CODEOWNERS/").lower()
        for stripped in (name.strip("/"), name.lstrip("/"), name.rstrip("/")):
            self.assertIsInstance(stripped, _TrackedName)
            self.assertTrue(stripped.folded)
        self.assertEqual(name.strip("/"), "codeowners")

    def test_the_probe_sees_a_name_compared_after_strip(self) -> None:
        self.assertIn(("eq", "CODEOWNERS", False), recorded().names["HYG-02"])

    def test_the_probe_tracks_the_paths_git_tracks(self) -> None:
        names = recorded().names["SEC-01"]
        self.assertIn(("eq", ".env", False), names)
        self.assertIn(("start", ".env.", False), names)

    def test_the_probe_sees_a_name_held_in_a_set_with_no_fixture_file(self) -> None:
        # No fixture has a GNUmakefile; EXEC-08 looks each base name up in a frozenset that holds it.
        self.assertIn(("eq", "GNUmakefile", False), recorded().names["EXEC-08"])

    def test_a_held_container_is_swapped_only_inside_the_probe(self) -> None:
        from audit.rules.checks import execution

        self.assertIs(type(execution._INLINE_SURFACE_NAMES), frozenset)
        with _recording_names(set()):
            self.assertIsInstance(execution._INLINE_SURFACE_NAMES, _RecordingFrozenset)
        self.assertIs(type(execution._INLINE_SURFACE_NAMES), frozenset)

    def test_a_recording_container_looks_like_its_original(self) -> None:
        self.assertEqual(repr(_RecordingFrozenset({"a"})), repr(frozenset({"a"})))
        self.assertEqual(repr(_RecordingSet({"a"})), repr({"a"}))
        held = _RecordingDict({"a": 1})
        self.assertEqual((repr(held), held.get("b", 2), held["a"], "a" in held), ("{'a': 1}", 2, 1, True))

    def test_a_name_ask_meets_a_place_by_its_operation(self) -> None:
        place = reads.Place("docs/README.md", reads.ROOT)
        self.assertTrue(name_hits(place, ("eq", "README.md", False)))
        self.assertTrue(name_hits(place, ("end", ".md", False)))
        self.assertFalse(name_hits(place, ("end", "ME.md", False)))
        self.assertTrue(name_hits(place, ("start", "docs/", False)))
        self.assertTrue(name_hits(place, ("eq", "readme.md", True)))
        self.assertFalse(name_hits(place, ("eq", "readme.md", False)))
        self.assertTrue(name_hits(reads.Place("**/*.tf", reads.GLOB), ("glob", "*.tf", False)))
        self.assertTrue(name_hits(reads.Place("Makefile", reads.ANY_DEPTH), ("end", "/Makefile", False)))
        self.assertFalse(name_hits(reads.Place("Makefile", reads.ROOT), ("end", "/Makefile", False)))
        self.assertTrue(name_hits(reads.Place(".roo/rules/**", reads.GLOB), ("eq", ".roo/rules", False)))
        self.assertTrue(name_hits(reads.Place("CODEOWNERS", reads.REPOSITORY_LEVEL), ("eq", ".gitlab", False)))
        self.assertFalse(name_hits(reads.Place("CODEOWNERS", reads.ROOT), ("eq", ".gitlab", False)))

    def test_a_name_ask_meets_a_wider_place(self) -> None:
        self.assertTrue(name_hits(reads.Place("**", reads.GLOB), ("end", ".py", False)))
        self.assertTrue(name_hits(reads.Place("CONTRIBUTING*", reads.REPOSITORY_LEVEL), ("end", ".md", True)))
        self.assertFalse(name_hits(reads.Place("CONTRIBUTING.md", reads.ROOT), ("end", ".rst", True)))
        self.assertTrue(name_hits(reads.Place("**/AGENTS.md", reads.GLOB), ("end", "packages/b/AGENTS.md", False)))
        self.assertTrue(name_hits(reads.Place("docs/**/*.md", reads.GLOB), ("start", "docs/tutorials/", False)))
        self.assertTrue(name_hits(reads.Place("**/requirements*.txt", reads.GLOB), ("start", "requirements", False)))
        self.assertFalse(name_hits(reads.Place("**/*.tf", reads.GLOB), ("start", "docs/", False)))
        self.assertTrue(name_hits(reads.Place(".gitignore", reads.ANY_DEPTH), ("eq", "artefacts/.gitignore", False)))
        self.assertFalse(name_hits(reads.Place(".gitignore", reads.ROOT), ("eq", "artefacts/.gitignore", False)))
        self.assertTrue(name_hits(reads.Place("*convention*", reads.GLOB), ("glob", "conventions*", False)))
        self.assertFalse(
            name_hits(reads.Place(".claude/rules/**/*.md", reads.GLOB), ("glob", ".github/agents/*.md", False))
        )

    def test_a_segment_asks_for_no_name_with_a_slash(self) -> None:
        sink: set[NameAsk] = set()
        path = _TrackedName("docs/AGENTS.md")
        base = path.rsplit("/", 1)[-1]
        self.assertTrue(base.segment and path.split("/")[0].segment and not path.split("/", 1)[-1].segment)
        self.assertTrue(_TrackedName("AGENTS.md").rsplit("/", 1)[-1].segment)
        sink_frame = sys._getframe(0)
        with mock.patch(__name__ + "._asked_by_a_check", return_value=True), _recording_names(sink):
            _record_name("eq", (".github/copilot-instructions.md", "AGENTS.md"), base, sink_frame)
            _record_name("eq", ".github/copilot-instructions.md", path, sink_frame)
        self.assertEqual(sink, {("eq", "AGENTS.md", False), ("eq", ".github/copilot-instructions.md", False)})

    def test_a_function_that_reads_nothing_records_nothing(self) -> None:
        with _recording_names(set(), "AGT-02"):
            self.assertTrue(_in_a_non_read(agt.is_non_instruction.__code__))
            self.assertTrue(_in_a_non_read(agt.instruction_paths.__code__))
        with _recording_names(set(), "AGT-01"):
            self.assertTrue(_in_a_non_read(variants.classify_present.__code__))
            self.assertFalse(_in_a_non_read(agt.instruction_paths.__code__))
        names = recorded().names
        self.assertFalse(any(operand == ".opencode/**" for _op, operand, _folded in names["AGT-01"]))
        self.assertTrue(any(op == "glob" for op, _operand, _folded in names["AGT-01"]))
        self.assertFalse(any(op == "glob" and operand.startswith(".codex/") for op, operand, _f in names["AGT-02"]))

    def test_a_name_compared_only_to_leave_a_path_out_is_dropped(self) -> None:
        self.assertTrue(_not_a_read("SEC-01", ("eq", "env.example", False)))
        self.assertFalse(_not_a_read("SEC-01", ("eq", ".env", False)))
        self.assertFalse(_not_a_read("SEC-02", ("eq", "env.example", False)))
        self.assertNotIn(("eq", "env.example", False), recorded().names["SEC-01"])

    def test_a_name_taken_from_the_targets_text_is_dropped(self) -> None:
        self.assertEqual(
            [_text_core(op) for op in ("*/docs", "docs/*", "src/cli/", "tests")], ["docs", "docs", "src/cli", "tests"]
        )
        self.assertFalse(any(operand.startswith("src/") for _op, operand, _f in recorded().names["AGT-06"]))

    def test_a_name_looked_for_at_any_depth_reaches_its_root_place(self) -> None:
        place = reads.Place("lefthook.yaml", reads.ROOT)
        self.assertFalse(place_covers(place, ("has", "lefthook.yaml")))
        self.assertTrue(_seen("TOOL-07", place, {("has", "lefthook.yaml")}, set()))
        self.assertFalse(_seen("TOOL-07", place, {("has", "lefthook.yml")}, set()))

    def test_con04_walks_the_scan_while_recorded(self) -> None:
        self.assertIsNone(con._EMIT_TARGET)
        self.assertTrue(recorded().names["CON-04"])

    def test_a_place_read_upstream_is_not_unseen(self) -> None:
        recording = recorded()
        nav01 = reads.READS["NAV-01"]
        self.assertTrue(all(place.via == reads.COMPONENTS for place in nav01.where))
        self.assertNotIn("NAV-01", unseen_places(recording))
        plain = replace(nav01, where=tuple(replace(place, via=None) for place in nav01.where))
        with mock.patch.dict(reads.READS, {"NAV-01": plain}):
            self.assertIn("NAV-01", unseen_places(recording))

    def test_the_name_probe_reports_and_fails_on_nothing(self) -> None:
        # Report-only (RF4.9.1): no declaration is held to the name asks yet. AUDIT_NAME_PROBE=detail prints every
        # unseen place and every uncovered ask.
        summary = name_probe_summary(recorded(), detail=os.environ.get("AUDIT_NAME_PROBE") == "detail")
        sys.stderr.write("\n" + summary + "\n")
        self.assertIn("declared places", summary)


class CoverRuleTest(unittest.TestCase):
    def test_a_root_place_does_not_cover_an_any_depth_lookup(self) -> None:
        self.assertFalse(place_covers(reads.Place("Makefile", reads.ROOT), ("has", "Makefile")))
        self.assertTrue(place_covers(reads.Place("Makefile", reads.ANY_DEPTH), ("has", "Makefile")))

    def test_a_glob_with_a_double_star_also_matches_no_folder(self) -> None:
        self.assertTrue(place_covers(reads.Place("**/AGENTS.md", reads.GLOB), ("read", "AGENTS.md")))
        self.assertTrue(place_covers(reads.Place("**/AGENTS.md", reads.GLOB), ("read", "a/b/AGENTS.md")))
        self.assertFalse(place_covers(reads.Place("docs/*.md", reads.GLOB), ("read", "README.md")))

    def test_repository_level_means_the_root_github_gitlab_or_docs(self) -> None:
        place = reads.Place("SECURITY.md", reads.REPOSITORY_LEVEL)
        self.assertTrue(place_covers(place, ("read", ".github/SECURITY.md")))
        self.assertFalse(place_covers(place, ("read", "src/SECURITY.md")))

    def test_a_pattern_is_covered_by_the_same_pattern_or_everything(self) -> None:
        self.assertTrue(place_covers(reads.Place("**/*.tf", reads.GLOB), ("match", "*.tf")))
        self.assertTrue(place_covers(reads.Place("**", reads.GLOB), ("match", "*.tf")))
        self.assertFalse(place_covers(reads.Place("main.tf", reads.ROOT), ("match", "*.tf")))

    def test_only_a_folded_place_covers_a_name_in_another_case(self) -> None:
        ask = ("read", "docs/Communication.md")
        self.assertTrue(_folded_covers(reads.Place("**/*communicat*.md", reads.GLOB, case=reads.FOLD), ask))
        self.assertFalse(_folded_covers(reads.Place("**/*communicat*.md", reads.GLOB), ask))
        self.assertFalse(place_covers(reads.Place("**/*communicat*.md", reads.GLOB), ask))

    def test_a_folder_at_the_root_covers_the_files_under_it(self) -> None:
        self.assertTrue(place_covers(reads.Place("artefacts", reads.ROOT), ("stat", "artefacts/notes.md")))

    def test_a_named_path_is_allowed_only_when_a_read_file_holds_it(self) -> None:
        root = support.fixture("con-01-names-existing-paths")
        texts = {("read", "AGENTS.md")}
        self.assertFalse(_named(root, texts, "no/such/token/anywhere-in-the-file"))


if __name__ == "__main__":
    unittest.main()
