# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The facts tool's `stack` section is the engine's own `detect_stack` for the inventory the file describes.

Each test runs the tool on a fixture or on a small repository made in a temporary directory, and compares the section
with the engine's `Stack` for the same inventory, as sorted lists, and with exact values written out by hand. Standard
library only.
"""

from __future__ import annotations

import json
import types
from pathlib import Path
from typing import Any
from unittest import mock

import _paths  # noqa: F401
import _git
import engine as launcher
import facts
from test_facts import RepoCase, engine_default_cap

FIXTURES = launcher.ENGINE_DIR / "tests" / "fixtures"
KEYS = ["ecosystems", "source_only", "package_managers", "notes"]
NO_MANIFEST = "no recognised build manifest \u2014 stack-dependent checks report UNKNOWN"
PYTHON_FROM_SOURCE = "python recognised from its source files: no manifest names it"

# fixture -> ecosystems, source_only, package_managers, notes
FIXTURE_STACKS: dict[str, tuple[list[str], list[str], list[str], list[str]]] = {
    "exec-01-python-source-only": (["python"], ["python"], [], [PYTHON_FROM_SOURCE]),
    "exec-02-nested-lockfile": (["node"], [], ["npm"], []),
    "cmd-ok-npm": (["node"], [], [], []),
    "cmd-ok-gradle": (["jvm"], [], [], []),
    "cmd-ok-maven": (["jvm"], [], ["maven"], []),
}


class StackTests(RepoCase):
    def written_stack(self, target: Path, *extra: str) -> dict[str, Any]:
        out = self.folder / f"{target.name}.json"
        out.unlink(missing_ok=True)
        self.run_ok(*extra, target=target, out=out)
        document: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
        stack: dict[str, Any] = document["stack"]
        return stack

    def engine_says(
        self, target: Path, *, max_files: int | None = None, excludes: tuple[str, ...] = ()
    ) -> dict[str, Any]:
        """The engine's own `Stack` for the same inventory, as sorted lists."""
        scan = facts.engine_module("audit.scan")
        cap = engine_default_cap() if max_files is None else max_files
        inventory = scan.build_inventory(target, extra_excludes=excludes, max_files=cap)
        found = facts.engine_module("audit.stack").detect_stack(inventory)
        return {
            "ecosystems": sorted(found.ecosystems),
            "source_only": sorted(found.source_only),
            "package_managers": sorted(found.package_managers),
            "notes": sorted(found.notes),
        }

    def assert_stack(
        self, target: Path, expected: tuple[list[str], list[str], list[str], list[str]], *extra: str
    ) -> None:
        written = self.written_stack(target, *extra)
        self.assertEqual(list(written), KEYS)
        self.assertEqual(written, dict(zip(KEYS, expected)))
        self.assertEqual(written, self.engine_says(target))

    def test_each_field_is_the_engines_for_the_same_inventory_on_five_fixtures(self) -> None:
        for name, expected in FIXTURE_STACKS.items():
            with self.subTest(fixture=name):
                self.assert_stack(FIXTURES / name, expected)

    def test_python_with_no_manifest_is_source_only_and_says_so(self) -> None:
        self.fill({"src/app.py": "print(1)\n"})
        self.assert_stack(self.repo, (["python"], ["python"], [], [PYTHON_FROM_SOURCE]))

    def test_a_manifest_that_names_python_leaves_source_only_empty(self) -> None:
        self.fill({"src/app.py": "print(1)\n", "pyproject.toml": "[project]\n", "requirements.txt": "x\n"})
        self.assert_stack(self.repo, (["python"], [], ["pip"], []))

    def test_python_tests_alone_are_not_python_source(self) -> None:
        self.fill({"tests/test_app.py": "x\n"})
        self.assert_stack(self.repo, ([], [], [], [NO_MANIFEST]))

    def test_a_repository_with_no_manifest_gives_empty_lists_and_the_engines_note(self) -> None:
        self.assert_stack(self.repo, ([], [], [], [NO_MANIFEST]))

    def test_a_repository_of_only_unknown_files_gives_the_same(self) -> None:
        unknown = self.root / "unknown"
        _git.make_repo(unknown, files=("data.xyz", "notes.foo"))
        self.assert_stack(unknown, ([], [], [], [NO_MANIFEST]))

    def test_an_empty_directory_is_not_an_error(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        self.assert_stack(empty, ([], [], [], [NO_MANIFEST]))

    def test_names_are_sorted_whatever_order_the_engine_finds_them_in(self) -> None:
        manifests = ["package.json", "pom.xml", "go.mod", "Cargo.toml", "composer.json"]
        locks = ["yarn.lock", "pnpm-lock.yaml", "go.sum", "Cargo.lock", "composer.lock", "poetry.lock", "bun.lockb"]
        self.fill(dict.fromkeys([*manifests, *locks], "x\n"))
        self.assert_stack(
            self.repo,
            (
                ["go", "jvm", "node", "php", "rust"],
                [],
                ["bun", "cargo", "composer", "gomod", "maven", "pnpm", "poetry", "yarn"],
                [],
            ),
        )

    def test_every_list_is_sorted_and_the_notes_are_carried_as_the_engine_wrote_them(self) -> None:
        found = types.SimpleNamespace(
            ecosystems=["node", "go"],
            source_only=["python", "go"],
            package_managers=["yarn", "bun"],
            notes=["b \u2014 x", "a x"],
        )
        with mock.patch.object(facts.engine_module("audit.stack"), "detect_stack", return_value=found) as detect:
            section = facts.stack_section("the inventory")
        detect.assert_called_once_with("the inventory")
        self.assertEqual(list(section), KEYS)
        self.assertEqual(section["ecosystems"], ["go", "node"])
        self.assertEqual(section["source_only"], ["go", "python"])
        self.assertEqual(section["package_managers"], ["bun", "yarn"])
        self.assertEqual(section["notes"], ["a x", "b \u2014 x"])

    def test_a_walk_that_was_cut_short_gives_the_stack_of_the_files_it_saw(self) -> None:
        self.fill({"package.json": "{}\n"})
        self.assertEqual(self.written_stack(self.repo)["ecosystems"], ["node"])
        cut = self.written_stack(self.repo, "--max-files", "1")
        self.assertEqual(cut, dict(zip(KEYS, ([], [], [], [NO_MANIFEST]))))
        self.assertEqual(cut, self.engine_says(self.repo, max_files=1))

    def test_an_excluded_manifest_is_not_a_manifest(self) -> None:
        self.fill({"package.json": "{}\n"})
        excluded = self.written_stack(self.repo, "--exclude", "package.json")
        self.assertEqual(excluded, dict(zip(KEYS, ([], [], [], [NO_MANIFEST]))))
        self.assertEqual(excluded, self.engine_says(self.repo, excludes=("package.json",)))

    def test_the_inventory_is_walked_once_and_feeds_both_sections(self) -> None:
        scan = facts.engine_module("audit.scan")
        with mock.patch.object(scan, "build_inventory", wraps=scan.build_inventory) as walk:
            self.run_ok("--max-files", "5")
        self.assertEqual(walk.call_count, 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
