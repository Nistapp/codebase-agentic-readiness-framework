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
KEYS = [
    "ecosystems",
    "source_only",
    "package_managers",
    "ci_providers",
    "test_frameworks",
    "hook_managers",
    "notes",
]
EMPTY: dict[str, list[str]] = {key: [] for key in KEYS}
NO_MANIFEST = "no recognised build manifest \u2014 stack-dependent checks report UNKNOWN"
PYTHON_FROM_SOURCE = "python recognised from its source files: no manifest names it"

# fixture -> the fields that are not empty
FIXTURE_STACKS: dict[str, dict[str, list[str]]] = {
    "exec-01-python-source-only": {
        "ecosystems": ["python"],
        "source_only": ["python"],
        "notes": [PYTHON_FROM_SOURCE],
    },
    "exec-02-nested-lockfile": {"ecosystems": ["node"], "package_managers": ["npm"]},
    "cmd-ok-npm": {"ecosystems": ["node"]},
    "cmd-ok-gradle": {"ecosystems": ["jvm"]},
    "cmd-ok-maven": {"ecosystems": ["jvm"], "package_managers": ["maven"]},
}

# field, name, a file that the engine's tables know the name by. A name with two spellings has two rows.
DETECTIONS: list[tuple[str, str, str]] = [
    ("ci_providers", "azure", "azure-pipelines.yml"),
    ("ci_providers", "buildkite", ".buildkite/pipeline.yml"),
    ("ci_providers", "circleci", ".circleci/config.yml"),
    ("ci_providers", "github", ".github/workflows/ci.yml"),
    ("ci_providers", "github", ".github/workflows/ci.yaml"),
    ("ci_providers", "gitlab", ".gitlab-ci.yml"),
    ("ci_providers", "jenkins", "Jenkinsfile"),
    ("test_frameworks", "cargo-test", "tests/it.rs"),
    ("test_frameworks", "go-test", "app_test.go"),
    ("test_frameworks", "jest", "jest.config.js"),
    ("test_frameworks", "jest", "jest.config.ts"),
    ("test_frameworks", "jest", "jest.config.mjs"),
    ("test_frameworks", "junit", "src/test/java/AppTest.java"),
    ("test_frameworks", "pytest", "pytest.ini"),
    ("test_frameworks", "pytest", "conftest.py"),
    ("test_frameworks", "tox", "tox.ini"),
    ("test_frameworks", "vitest", "vitest.config.js"),
    ("test_frameworks", "vitest", "vitest.config.mts"),
    ("test_frameworks", "vitest", "vitest.config.ts"),
    ("hook_managers", "gradle-hooks", ".githooks/pre-commit"),
    ("hook_managers", "husky", ".husky/pre-commit"),
    ("hook_managers", "lefthook", "lefthook.yaml"),
    ("hook_managers", "lefthook", "lefthook.yml"),
    ("hook_managers", "pre-commit", ".pre-commit-config.yaml"),
]

# fixture -> the field and the name it has, besides being a Node project
DETECTION_FIXTURES: dict[str, tuple[str, str]] = {
    "ci-01-no-pr-trigger": ("ci_providers", "github"),
    "ci-02-parity-break": ("ci_providers", "github"),
    "ci-03-ci-only-step": ("ci_providers", "github"),
    "ci-ok-gh": ("ci_providers", "github"),
    "base-01-no-baseline": ("test_frameworks", "vitest"),
    "base-02-no-count": ("test_frameworks", "vitest"),
    "base-03-no-ratchet": ("test_frameworks", "vitest"),
    "base-04-no-coverage-floor": ("test_frameworks", "vitest"),
    "base-ok": ("test_frameworks", "vitest"),
    "tool-01-no-formatter": ("hook_managers", "husky"),
    "tool-02-no-linter": ("hook_managers", "husky"),
    "tool-03-nonstrict-ts": ("hook_managers", "husky"),
    "tool-04-no-audit-verb": ("hook_managers", "husky"),
    "tool-05-unwired-hooks": ("hook_managers", "husky"),
    "tool-06-no-commit-rule": ("hook_managers", "pre-commit"),
    "tool-ok-node": ("hook_managers", "pre-commit"),
}

# Files that look like configuration of a CI provider, a test framework or a hook manager, and are not what the
# engine's tables name.
NEAR_MISSES = [
    ".buildkite/pipeline.yaml",
    ".circleci/config.yaml",
    ".githooks",
    ".github/workflows/ci.json",
    ".husky",
    "Jenkinsfile.bak",
    "jest.config.json",
    "lefthook.json",
    "my-pytest.ini",
    "tests/it.txt",
    "tox.ini.bak",
    "vitest.config.cjs",
]


class StackCase(RepoCase):
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
            "ci_providers": sorted(found.ci_providers),
            "test_frameworks": sorted(found.test_frameworks),
            "hook_managers": sorted(found.hook_managers),
            "notes": sorted(found.notes),
        }

    def assert_stack(self, target: Path, **not_empty: list[str]) -> None:
        """The section is these fields, as written out here, and every other field is empty; and it is the engine's."""
        self.assertLessEqual(set(not_empty), set(KEYS))
        written = self.written_stack(target)
        self.assertEqual(list(written), KEYS)
        self.assertEqual(written, {**EMPTY, **not_empty})
        self.assertEqual(written, self.engine_says(target))


class StackTests(StackCase):
    def test_each_field_is_the_engines_for_the_same_inventory_on_five_fixtures(self) -> None:
        for name, not_empty in FIXTURE_STACKS.items():
            with self.subTest(fixture=name):
                self.assert_stack(FIXTURES / name, **not_empty)

    def test_python_with_no_manifest_is_source_only_and_says_so(self) -> None:
        self.fill({"src/app.py": "print(1)\n"})
        self.assert_stack(self.repo, ecosystems=["python"], source_only=["python"], notes=[PYTHON_FROM_SOURCE])

    def test_a_manifest_that_names_python_leaves_source_only_empty(self) -> None:
        self.fill({"src/app.py": "print(1)\n", "pyproject.toml": "[project]\n", "requirements.txt": "x\n"})
        self.assert_stack(self.repo, ecosystems=["python"], package_managers=["pip"])

    def test_python_tests_alone_are_not_python_source(self) -> None:
        self.fill({"tests/test_app.py": "x\n"})
        self.assert_stack(self.repo, notes=[NO_MANIFEST])

    def test_a_repository_with_no_manifest_gives_empty_lists_and_the_engines_note(self) -> None:
        self.assert_stack(self.repo, notes=[NO_MANIFEST])

    def test_a_repository_of_only_unknown_files_gives_the_same(self) -> None:
        unknown = self.root / "unknown"
        _git.make_repo(unknown, files=("data.xyz", "notes.foo"))
        self.assert_stack(unknown, notes=[NO_MANIFEST])

    def test_an_empty_directory_is_not_an_error(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        self.assert_stack(empty, notes=[NO_MANIFEST])

    def test_names_are_sorted_whatever_order_the_engine_finds_them_in(self) -> None:
        manifests = ["package.json", "pom.xml", "go.mod", "Cargo.toml", "composer.json"]
        locks = ["yarn.lock", "pnpm-lock.yaml", "go.sum", "Cargo.lock", "composer.lock", "poetry.lock", "bun.lockb"]
        self.fill(dict.fromkeys([*manifests, *locks], "x\n"))
        self.assert_stack(
            self.repo,
            ecosystems=["go", "jvm", "node", "php", "rust"],
            package_managers=["bun", "cargo", "composer", "gomod", "maven", "pnpm", "poetry", "yarn"],
        )

    def test_every_list_is_sorted_and_the_notes_are_carried_as_the_engine_wrote_them(self) -> None:
        found = types.SimpleNamespace(
            ecosystems=["node", "go"],
            source_only=["python", "go"],
            package_managers=["yarn", "bun"],
            ci_providers=["jenkins", "azure"],
            test_frameworks=["vitest", "jest"],
            hook_managers=["lefthook", "husky"],
            notes=["b \u2014 x", "a x"],
        )
        with mock.patch.object(facts.engine_module("audit.stack"), "detect_stack", return_value=found) as detect:
            section = facts.stack_section("the inventory")
        detect.assert_called_once_with("the inventory")
        self.assertEqual(list(section), KEYS)
        self.assertEqual(section["ecosystems"], ["go", "node"])
        self.assertEqual(section["source_only"], ["go", "python"])
        self.assertEqual(section["package_managers"], ["bun", "yarn"])
        self.assertEqual(section["ci_providers"], ["azure", "jenkins"])
        self.assertEqual(section["test_frameworks"], ["jest", "vitest"])
        self.assertEqual(section["hook_managers"], ["husky", "lefthook"])
        self.assertEqual(section["notes"], ["a x", "b \u2014 x"])

    def test_a_walk_that_was_cut_short_gives_the_stack_of_the_files_it_saw(self) -> None:
        self.fill({"package.json": "{}\n"})
        self.assertEqual(self.written_stack(self.repo)["ecosystems"], ["node"])
        cut = self.written_stack(self.repo, "--max-files", "1")
        self.assertEqual(cut, {**EMPTY, "notes": [NO_MANIFEST]})
        self.assertEqual(cut, self.engine_says(self.repo, max_files=1))

    def test_an_excluded_manifest_is_not_a_manifest(self) -> None:
        self.fill({"package.json": "{}\n"})
        excluded = self.written_stack(self.repo, "--exclude", "package.json")
        self.assertEqual(excluded, {**EMPTY, "notes": [NO_MANIFEST]})
        self.assertEqual(excluded, self.engine_says(self.repo, excludes=("package.json",)))

    def test_the_inventory_is_walked_once_and_feeds_both_sections(self) -> None:
        scan = facts.engine_module("audit.scan")
        with mock.patch.object(scan, "build_inventory", wraps=scan.build_inventory) as walk:
            self.run_ok("--max-files", "5")
        self.assertEqual(walk.call_count, 1)


class DetectionTests(StackCase):
    """CI providers, test frameworks and hook managers: names the engine's tables give to files, and no verdict."""

    DETECTION_FIELDS = ("ci_providers", "test_frameworks", "hook_managers")

    def test_each_name_in_the_engines_tables_is_listed_for_a_file_it_is_known_by(self) -> None:
        for number, (field, name, path) in enumerate(DETECTIONS):
            with self.subTest(field=field, name=name, path=path):
                target = self.root / f"detection-{number}"
                _git.make_repo(target, files=("package.json", path))
                written = self.written_stack(target)
                self.assertEqual(
                    {key: written[key] for key in self.DETECTION_FIELDS},
                    {key: [name] if key == field else [] for key in self.DETECTION_FIELDS},
                )
                self.assertEqual(written, self.engine_says(target))

    def test_the_tables_have_seventeen_names_and_the_cases_name_each_of_them(self) -> None:
        stack = facts.engine_module("audit.stack")
        tables = {
            "ci_providers": stack.CI_PROVIDERS,
            "test_frameworks": stack.TEST_FRAMEWORKS,
            "hook_managers": stack.HOOK_MANAGERS,
        }
        self.assertEqual(sum(len(table) for table in tables.values()), 17)
        for field, table in tables.items():
            self.assertEqual(sorted({name for kind, name, _ in DETECTIONS if kind == field}), sorted(table))

    def test_each_list_equals_the_engines_on_sixteen_fixtures_and_at_least_three_for_each(self) -> None:
        for name, (field, found) in DETECTION_FIXTURES.items():
            with self.subTest(fixture=name):
                self.assert_stack(FIXTURES / name, ecosystems=["node"], **{field: [found]})
        counts = {field: 0 for field in self.DETECTION_FIELDS}
        for field, _ in DETECTION_FIXTURES.values():
            counts[field] += 1
        self.assertEqual(counts, {"ci_providers": 4, "test_frameworks": 5, "hook_managers": 7})

    def test_every_name_at_once_is_listed_and_each_list_is_sorted(self) -> None:
        paths = {path for _, name, path in DETECTIONS if path not in ("conftest.py",)}
        self.fill(dict.fromkeys(["package.json", *paths], "x\n"))
        self.assert_stack(
            self.repo,
            ecosystems=["node"],
            ci_providers=["azure", "buildkite", "circleci", "github", "gitlab", "jenkins"],
            test_frameworks=["cargo-test", "go-test", "jest", "junit", "pytest", "tox", "vitest"],
            hook_managers=["gradle-hooks", "husky", "lefthook", "pre-commit"],
        )

    def test_a_repository_with_none_of_them_gives_three_empty_lists(self) -> None:
        written = self.written_stack(self.repo)
        self.assertEqual(
            {key: written[key] for key in self.DETECTION_FIELDS}, {key: [] for key in self.DETECTION_FIELDS}
        )
        self.assertEqual(written, self.engine_says(self.repo))

    def test_files_that_only_look_like_configuration_are_not_names(self) -> None:
        self.fill(dict.fromkeys(["package.json", *NEAR_MISSES], "x\n"))
        self.assert_stack(self.repo, ecosystems=["node"])

    def test_a_pattern_with_a_folder_matches_at_the_root_only_and_a_plain_name_at_any_depth(self) -> None:
        """The engine's way, which the file inherits: a nested `.husky`, workflow or `src/test/java` is not named."""
        self.fill(
            dict.fromkeys(
                [
                    "package.json",
                    "pkg/.husky/pre-commit",
                    "svc/src/test/java/A.java",
                    "web/.github/workflows/ci.yml",
                    "api/tests/it.rs",
                    "pkg/vitest.config.ts",
                    "pkg/.pre-commit-config.yaml",
                    "pkg/Jenkinsfile",
                ],
                "x\n",
            )
        )
        self.assert_stack(
            self.repo,
            ecosystems=["node"],
            ci_providers=["jenkins"],
            test_frameworks=["vitest"],
            hook_managers=["pre-commit"],
        )

    def test_a_workflow_that_the_walk_leaves_out_is_not_a_ci_provider(self) -> None:
        self.fill({".github/workflows/ci.yml": "x\n", "package.json": "{}\n"})
        self.assertEqual(self.written_stack(self.repo)["ci_providers"], ["github"])
        excluded = self.written_stack(self.repo, "--exclude", ".github/*")
        self.assertEqual(excluded["ci_providers"], [])
        self.assertEqual(excluded, self.engine_says(self.repo, excludes=(".github/*",)))


if __name__ == "__main__":
    import unittest

    unittest.main()
