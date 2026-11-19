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
are recorded. Git commands and reads outside the target (``$HOME``) are not paths of the target. The stack and the
components are detected before the checks run, so their reads belong to no check.

An ask is covered when a declared place matches it at its scope. ``has`` looks at any depth, so a ``root`` place
does not cover it. A ``match`` pattern is covered by a place with the same path, the same path under ``**/``, or the
place ``**``.
"""

from __future__ import annotations

import fnmatch
import posixpath
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Iterator
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
from audit.rules import reads  # noqa: E402
from audit.rules.checks import con  # noqa: E402
from audit.rules.registry import REGISTRY, applicable_checks  # noqa: E402
from audit.scan import CONTENT_READ_LIMIT, Inventory, build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402
from audit.target import resolve_target  # noqa: E402
from test_positive_fixture import TEMPLATES, locate_scaffolder  # noqa: E402

Ask = tuple[str, str]

_REPOSITORY_LEVEL = ("", ".github/", ".gitlab/", "docs/")

#: Checks that ask for paths the target's own text names: a path token on an instruction line, a code span of a
#: prohibitions section, a file an agent config points to. Such an ask is allowed when the path is written in a
#: file the same run read; that file itself must be declared.
NAMED_BY_TEXT: dict[str, str] = {
    "AGT-06": "each path token of a boundary line is looked up with Inventory.has",
    "AGT-10": "each file a harness config names must exist",
    "CON-01": "each code span of the prohibitions section is looked up in the scan and on disk",
}

#: Checks that compare base names in lower case, which the map's scopes do not express: the map has no case rule
#: for reads. Their asks are compared as asked and in lower case.
CASE_FOLDED: dict[str, str] = {
    "AGT-12": "a communication file name is matched with no regard to case",
    "AGT-13": "conventions files match the globs by lower-case base name",
}


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


def _covered(check: str, ask: Ask) -> bool:
    asks = [ask, (ask[0], ask[1].lower())] if check in CASE_FOLDED else [ask]
    return any(place_covers(place, one) for one in asks for place in reads.READS[check].where)


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


def undeclared(check: str, root: Path, asks: set[Ask]) -> set[Ask]:
    """The asks of one run that no declared place covers."""
    missing = {ask for ask in asks if not _covered(check, ask)}
    if check in NAMED_BY_TEXT:
        missing = {ask for ask in missing if not _named(root, asks, ask[1])}
    return missing


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
    """What every implemented check asked for on every fixture, and what no declaration covers."""

    def __init__(self) -> None:
        self.asks: dict[str, set[Ask]] = {spec.id: set() for spec in REGISTRY if spec.impl is not None}
        self.runs: dict[str, int] = dict.fromkeys(self.asks, 0)
        self.undeclared: dict[str, set[tuple[str, str, str]]] = {check: set() for check in self.asks}
        con.set_emit_target(None)
        for path in _fixtures():
            self._record(path)
        with tempfile.TemporaryDirectory() as tmp:
            self._record(_scaffold(Path(tmp) / "scaffold"))

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
                spec.run(target=target, inventory=recording, stack=stack, components=components, session=session)
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

    def test_a_held_place_follows_its_constant(self) -> None:
        from audit.rules.checks import tst

        reference = "audit.rules.checks.tst:_FASTPATH_DOCS"
        declared = [place.path for place in reads.READS["TST-04"].where if place.constant == reference]
        self.assertEqual(declared, list(tst._FASTPATH_DOCS))
        self.assertIn(reference, reads.READS["TST-04"].constants)

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

    def test_a_folder_at_the_root_covers_the_files_under_it(self) -> None:
        self.assertTrue(place_covers(reads.Place("artefacts", reads.ROOT), ("stat", "artefacts/notes.md")))

    def test_a_named_path_is_allowed_only_when_a_read_file_holds_it(self) -> None:
        root = support.fixture("con-01-names-existing-paths")
        texts = {("read", "AGENTS.md")}
        self.assertFalse(_named(root, texts, "no/such/token/anywhere-in-the-file"))


if __name__ == "__main__":
    unittest.main()
