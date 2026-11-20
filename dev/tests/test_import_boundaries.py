# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The import rules of `AGENTS.md` ("Boundaries" and "Code conventions"), checked on every tracked Python file.

The rules:

* ``stdlib-only``: the engine (``audit/engine/``), the audit tools (``audit/tools/``), the implement folder
  (``implement/``) and the greenfield scaffolder (``greenfield/bootstrap/``) import the standard library and
  first-party modules only, never a third-party package;
* ``engine-layering``: the engine imports nothing from the audit tools, the implement folder or ``dev/``;
* ``audit-layering``: nothing under ``audit/`` imports from ``implement/``;
* ``dev-only``: nothing outside ``dev/`` imports a ``dev/`` module.

The modules here are flat: a test or a tool puts its folder on ``sys.path`` and imports ``_common`` or ``progress``
by name. So each top-level module name is looked up in an index of the folders that are put on ``sys.path`` (the
``IMPORT_ROOTS``), and a name found there is first-party and belongs to that folder's zone. A name the index does not
hold is standard library when it is in ``sys.stdlib_module_names``, and third-party otherwise. A relative import
stays in its own package, so it is first-party in the importer's zone. Every ``import`` statement counts, wherever it
sits: no module in these zones uses ``if TYPE_CHECKING:``, so no block is exempt. A dynamic
``importlib.import_module("name")`` is not a statement and is not read.

Fixture trees (any ``fixtures/`` or ``testdata/`` folder) are data that the engine audits, not code of this
repository, so they are skipped. The synthetic tests at the end check the classifier, one rule at a time.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]

#: The zones, by path prefix, first match wins: (zone, prefix, standard library only).
ZONES: tuple[tuple[str, str, bool], ...] = (
    ("engine", "audit/engine/", True),
    ("audit-tools", "audit/tools/", True),
    ("implement", "implement/", True),
    ("greenfield", "greenfield/bootstrap/", True),
    ("dev", "dev/", False),
)

#: The folders that a tool, a test or a launcher puts on ``sys.path``; the modules in them are first-party.
IMPORT_ROOTS: tuple[str, ...] = (
    "audit/engine",
    "audit/engine/tests",
    "audit/tools",
    "audit/tools/tests",
    "implement/tools",
    "implement/tools/tests",
    "implement/playbooks/templates",
    "greenfield/bootstrap",
    "greenfield/bootstrap/tests",
    "dev",
    "dev/eval",
    "dev/tests",
)

#: The zones each importer zone must not import, with the rule that forbids it.
FORBIDDEN: Mapping[str, Mapping[str, str]] = {
    "engine": {"audit-tools": "engine-layering", "implement": "engine-layering", "dev": "engine-layering"},
    "audit-tools": {"implement": "audit-layering", "dev": "dev-only"},
    "implement": {"dev": "dev-only"},
    "greenfield": {"dev": "dev-only"},
    "": {"dev": "dev-only"},
}

DATA_DIRS = frozenset({"fixtures", "testdata"})
STDLIB = frozenset(sys.stdlib_module_names)


@dataclass(frozen=True)
class Import:
    line: int
    module: str
    level: int


def zone_of(path: str) -> str:
    """The zone of a repository-relative POSIX path, or ``""`` when it is in none."""
    for zone, prefix, _ in ZONES:
        if path.startswith(prefix):
            return zone
    return ""


def stdlib_only(zone: str) -> bool:
    return any(name == zone and only for name, _, only in ZONES)


def imports_of(source: str) -> list[Import]:
    """Every import statement in a module, in line order; ``from x import y`` yields ``x``."""
    found: list[Import] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend(Import(node.lineno, alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append(Import(node.lineno, node.module or "", node.level))
    return sorted(found, key=lambda item: (item.line, item.module))


def module_index(paths: Iterable[str]) -> dict[str, set[str]]:
    """Each first-party top-level module name, with the zones of the import roots that hold it."""
    roots = {PurePosixPath(root) for root in IMPORT_ROOTS}
    index: dict[str, set[str]] = {}
    for path in paths:
        pure = PurePosixPath(path)
        if pure.parent in roots and pure.suffix == ".py":
            name, zone = pure.stem, zone_of(path)
        elif pure.name == "__init__.py" and pure.parent.parent in roots:
            name, zone = pure.parent.name, zone_of(path)
        else:
            continue
        index.setdefault(name, set()).add(zone)
    return index


def classify(item: Import, importer_zone: str, index: Mapping[str, set[str]]) -> tuple[str, str]:
    """``("first-party", zone)``, ``("stdlib", "")`` or ``("third-party", "")`` for one import.

    A relative import stays in the importer's package. A name in the importer's own zone wins over another zone's
    module of the same name, as the importer's own folder comes first on ``sys.path``.
    """
    if item.level:
        return "first-party", importer_zone
    top = item.module.partition(".")[0]
    zones = index.get(top, set())
    if importer_zone in zones:
        return "first-party", importer_zone
    if zones:
        return "first-party", sorted(zones)[0]
    if top in STDLIB:
        return "stdlib", ""
    return "third-party", ""


def violations(path: str, source: str, index: Mapping[str, set[str]]) -> list[str]:
    """One message per import that breaks a rule: ``path:line: rule: what``."""
    importer = zone_of(path)
    problems: list[str] = []
    for item in imports_of(source):
        kind, zone = classify(item, importer, index)
        name = "." * item.level + item.module
        if kind == "third-party" and stdlib_only(importer):
            problems.append(f"{path}:{item.line}: stdlib-only: {importer} imports the third-party module {name!r}")
        rule = FORBIDDEN.get(importer, {}).get(zone) if kind == "first-party" else None
        if rule:
            problems.append(
                f"{path}:{item.line}: {rule}: {importer or 'a file outside every zone'} imports {name!r}, "
                f"a module of {zone}"
            )
    return problems


def tracked_python_files() -> list[str]:
    """Every tracked ``.py`` file of the repository, without the fixture and test-data trees."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", "--", "*.py"], check=True, capture_output=True, text=True
    ).stdout
    return sorted(
        path for path in out.split("\0") if path and not DATA_DIRS.intersection(PurePosixPath(path).parts[:-1])
    )


class RepositoryImportsTest(unittest.TestCase):
    paths: list[str]
    index: dict[str, set[str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.paths = tracked_python_files()
        cls.index = module_index(cls.paths)

    def test_every_zone_has_files_and_the_index_holds_their_modules(self) -> None:
        for zone, prefix, _ in ZONES:
            with self.subTest(zone=zone):
                self.assertTrue(any(path.startswith(prefix) for path in self.paths), prefix)
        for name, zone in (
            ("audit", "engine"),
            ("_common", "audit-tools"),
            ("progress", "implement"),
            ("bootstrap", "greenfield"),
            ("docindex", "dev"),
        ):
            with self.subTest(module=name):
                self.assertIn(zone, self.index.get(name, set()))

    def test_no_import_breaks_a_boundary(self) -> None:
        problems: list[str] = []
        for path in self.paths:
            problems.extend(violations(path, (REPO / path).read_text(encoding="utf-8"), self.index))
        self.assertEqual(problems, [], "\n" + "\n".join(problems))


INDEX: dict[str, set[str]] = {
    "audit": {"engine"},
    "_common": {"audit-tools"},
    "progress": {"implement"},
    "bootstrap": {"greenfield"},
    "recipe_lint": {"dev"},
}


class ClassifierTest(unittest.TestCase):
    def test_imports_of_reads_every_form_with_its_line(self) -> None:
        source = "import os, json.decoder\nfrom . import sibling\ndef f():\n    from pathlib import Path\n"
        self.assertEqual(
            imports_of(source),
            [Import(1, "json.decoder", 0), Import(1, "os", 0), Import(2, "", 1), Import(4, "pathlib", 0)],
        )

    def test_classify_sorts_stdlib_first_party_relative_and_third_party(self) -> None:
        self.assertEqual(classify(Import(1, "os.path", 0), "engine", INDEX), ("stdlib", ""))
        self.assertEqual(classify(Import(1, "audit.rules", 0), "audit-tools", INDEX), ("first-party", "engine"))
        self.assertEqual(classify(Import(1, "anything", 2), "implement", INDEX), ("first-party", "implement"))
        self.assertEqual(classify(Import(1, "yaml", 0), "engine", INDEX), ("third-party", ""))

    def test_the_importers_own_zone_wins_a_shared_name(self) -> None:
        shared = {"helpers": {"engine", "audit-tools"}}
        self.assertEqual(classify(Import(1, "helpers", 0), "audit-tools", shared), ("first-party", "audit-tools"))

    def test_module_index_reads_modules_and_packages_in_import_roots_only(self) -> None:
        index = module_index(
            [
                "audit/tools/_common.py",
                "audit/engine/audit/__init__.py",
                "audit/engine/audit/rules/checks/x.py",
                "dev/docindex/__init__.py",
            ]
        )
        self.assertEqual(index, {"_common": {"audit-tools"}, "audit": {"engine"}, "docindex": {"dev"}})

    def test_stdlib_only_rejects_a_third_party_import_in_each_shipped_zone(self) -> None:
        for path in (
            "audit/engine/audit/x.py",
            "audit/tools/x.py",
            "implement/tools/x.py",
            "greenfield/bootstrap/x.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    violations(path, "import json\nimport yaml\n", INDEX),
                    [f"{path}:2: stdlib-only: {zone_of(path)} imports the third-party module 'yaml'"],
                )

    def test_stdlib_only_allows_a_third_party_import_in_dev(self) -> None:
        self.assertEqual(violations("dev/x.py", "import yaml\nfrom jsonschema import validate\n", INDEX), [])

    def test_engine_layering_rejects_the_audit_tools_and_implement(self) -> None:
        self.assertEqual(
            violations("audit/engine/audit/x.py", "import _common\nfrom progress import main\n", INDEX),
            [
                "audit/engine/audit/x.py:1: engine-layering: engine imports '_common', a module of audit-tools",
                "audit/engine/audit/x.py:2: engine-layering: engine imports 'progress', a module of implement",
            ],
        )

    def test_engine_layering_allows_the_engine_itself(self) -> None:
        self.assertEqual(violations("audit/engine/tests/t.py", "from audit import cli\nfrom . import x\n", INDEX), [])

    def test_audit_layering_rejects_implement(self) -> None:
        self.assertEqual(
            violations("audit/tools/tests/t.py", "import progress\n", INDEX),
            ["audit/tools/tests/t.py:1: audit-layering: audit-tools imports 'progress', a module of implement"],
        )

    def test_audit_layering_allows_implement_to_import_the_audit_tools(self) -> None:
        self.assertEqual(violations("implement/tools/t.py", "import _common\nimport audit\n", INDEX), [])

    def test_dev_only_rejects_dev_outside_dev(self) -> None:
        for path in ("audit/tools/x.py", "implement/tools/x.py", "greenfield/bootstrap/x.py", "x.py"):
            with self.subTest(path=path):
                self.assertEqual(len(violations(path, "import recipe_lint\n", INDEX)), 1)
                self.assertIn(":1: ", violations(path, "import recipe_lint\n", INDEX)[0])
        self.assertIn("engine-layering", violations("audit/engine/x.py", "import recipe_lint\n", INDEX)[0])

    def test_dev_only_allows_dev_to_import_dev_and_every_zone(self) -> None:
        self.assertEqual(violations("dev/tests/t.py", "import recipe_lint, _common, progress, audit\n", INDEX), [])

    def test_fixture_trees_are_not_scanned(self) -> None:
        self.assertFalse(any(DATA_DIRS.intersection(PurePosixPath(path).parts) for path in tracked_python_files()))


if __name__ == "__main__":
    unittest.main()
