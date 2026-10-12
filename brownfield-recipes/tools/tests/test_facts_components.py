# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The facts tool's `components` section is the engine's own `detect_components` for the inventory the file describes.

Each test runs the tool on a small repository made in a temporary directory, or calls `facts.components_section`
directly with a model built from the engine's own `Component` and `ComponentModel`, and compares the section with
values written out by hand. Standard library only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest import mock

import _paths  # noqa: F401
import facts
from test_facts import RepoCase

KEYS = ["declared", "candidates", "notes"]
ENTRY_KEYS = ["name", "path", "declared_by", "manifest"]
NO_COMPONENTS = "single-root repository: no component declarations found"


class ComponentCase(RepoCase):
    def written_components(self, target: Path, *extra: str) -> dict[str, Any]:
        out = self.folder / f"{target.name}.json"
        out.unlink(missing_ok=True)
        self.run_ok(*extra, target=target, out=out)
        document: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
        components: dict[str, Any] = document["components"]
        return components

    def document(self, target: Path, *extra: str) -> dict[str, Any]:
        out = self.folder / f"{target.name}.json"
        out.unlink(missing_ok=True)
        self.run_ok(*extra, target=target, out=out)
        document: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
        return document

    def engine_says(self, target: Path) -> dict[str, Any]:
        """The engine's own model for the same inventory, shaped as the tool shapes it, with no cap applied."""
        scan = facts.engine_module("audit.scan")
        components = facts.engine_module("audit.components")
        inventory = scan.build_inventory(target)
        model = components.detect_components(inventory)
        members = sorted((member for member in model.components if not member.is_root), key=lambda m: m.path)
        return {
            "declared": [
                {"name": m.name, "path": m.path, "declared_by": m.declared_by, "manifest": m.manifest} for m in members
            ],
            "candidates": sorted(model.candidates),
            "notes": sorted(model.notes),
        }

    def assert_components(self, target: Path, **expected: Any) -> None:
        written = self.written_components(target)
        self.assertEqual(list(written), KEYS)
        self.assertEqual(written, {"declared": [], "candidates": [], "notes": [], **expected})
        self.assertEqual(written, self.engine_says(target))


class AcceptanceTests(ComponentCase):
    def test_declared_members_of_an_npm_workspace(self) -> None:
        self.fill(
            {
                "package.json": '{"name": "root", "workspaces": ["packages/*"]}\n',
                "packages/api/package.json": '{"name": "api"}\n',
                "packages/web/package.json": '{"name": "web"}\n',
            }
        )
        self.assert_components(
            self.repo,
            declared=[
                {
                    "name": "api",
                    "path": "packages/api",
                    "declared_by": "package.json:workspaces",
                    "manifest": "packages/api/package.json",
                },
                {
                    "name": "web",
                    "path": "packages/web",
                    "declared_by": "package.json:workspaces",
                    "manifest": "packages/web/package.json",
                },
            ],
        )

    def test_a_repository_with_candidates_only(self) -> None:
        self.fill({"apps/worker/package.json": '{"name": "worker"}\n'})
        self.assert_components(self.repo, candidates=["apps/worker"])

    def test_a_single_package_repository_has_no_declared_members_and_no_candidates(self) -> None:
        self.fill({"package.json": '{"name": "root"}\n'})
        self.assert_components(self.repo, notes=[NO_COMPONENTS])

    def test_a_repository_with_nothing_at_all(self) -> None:
        self.assert_components(self.repo, notes=[NO_COMPONENTS])

    def test_a_manifest_without_a_component_declaration_leaves_it_out(self) -> None:
        self.fill({"package.json": '{"name": "root", "workspaces": ["packages/*"]}\n'})
        self.assert_components(self.repo, notes=[NO_COMPONENTS])

    def test_the_implicit_root_is_never_listed(self) -> None:
        self.fill({"package.json": '{"name": "root"}\n'})
        self.run_ok()
        text = self.out.read_text(encoding="utf-8")
        self.assertNotIn("(root)", text)
        self.assertNotIn('"implicit"', text)


class SortAndShapeTests(ComponentCase):
    def test_declared_members_are_sorted_by_path_whatever_order_the_engine_finds_them_in(self) -> None:
        self.fill(
            {
                "package.json": '{"name": "root", "workspaces": ["packages/*"]}\n',
                "packages/zeta/package.json": "{}\n",
                "packages/alpha/package.json": "{}\n",
            }
        )
        written = self.written_components(self.repo)
        self.assertEqual([entry["path"] for entry in written["declared"]], ["packages/alpha", "packages/zeta"])

    def test_candidates_are_sorted(self) -> None:
        self.fill(
            {
                "apps/zeta/package.json": "{}\n",
                "apps/alpha/package.json": "{}\n",
            }
        )
        written = self.written_components(self.repo)
        self.assertEqual(written["candidates"], ["apps/alpha", "apps/zeta"])

    def test_a_component_without_its_own_manifest_is_null(self) -> None:
        self.fill(
            {
                "package.json": '{"name": "root", "workspaces": ["packages/*"]}\n',
                "packages/bare/README.md": "x\n",
            }
        )
        written = self.written_components(self.repo)
        self.assertEqual(
            written["declared"],
            [{"name": "bare", "path": "packages/bare", "declared_by": "package.json:workspaces", "manifest": None}],
        )

    def test_no_entry_is_a_verdict(self) -> None:
        self.fill(
            {
                "package.json": '{"name": "root", "workspaces": ["packages/*"]}\n',
                "packages/api/package.json": "{}\n",
            }
        )
        written = self.written_components(self.repo)
        self.assertEqual([list(entry) for entry in written["declared"]], [ENTRY_KEYS])
        text = (self.folder / f"{self.repo.name}.json").read_text(encoding="utf-8")
        for word in ("good", "complete", "well-formed", "verdict"):
            self.assertNotIn(word, text)


class EngineReuseTests(ComponentCase):
    def test_the_section_is_built_from_a_model_crafted_with_the_engines_own_dataclasses(self) -> None:
        """`components_section` carries exactly what `detect_components` gives it: no search of its own."""
        module = facts.engine_module("audit.components")
        model = module.ComponentModel(
            components=[
                module.Component(name="(root)", path=".", declared_by="implicit", manifest=None),
                module.Component(
                    name="zeta",
                    path="packages/zeta",
                    declared_by="pkg:workspaces",
                    manifest="packages/zeta/package.json",
                ),
                module.Component(name="alpha", path="packages/alpha", declared_by="pkg:workspaces", manifest=None),
            ],
            candidates=["services/worker", "apps/beta"],
            notes=["z note", "a note"],
        )
        with mock.patch.object(module, "detect_components", return_value=model) as detect:
            section, declared_omitted, candidate_omitted = facts.components_section("the inventory")
        detect.assert_called_once_with("the inventory")
        self.assertEqual(list(section), KEYS)
        self.assertEqual(
            section["declared"],
            [
                {"name": "alpha", "path": "packages/alpha", "declared_by": "pkg:workspaces", "manifest": None},
                {
                    "name": "zeta",
                    "path": "packages/zeta",
                    "declared_by": "pkg:workspaces",
                    "manifest": "packages/zeta/package.json",
                },
            ],
        )
        self.assertEqual(section["candidates"], ["apps/beta", "services/worker"])
        self.assertEqual(section["notes"], ["a note", "z note"])
        self.assertEqual((declared_omitted, candidate_omitted), (0, 0))


class FitTests(ComponentCase):
    def section_of(
        self, *, components: list[Any], candidates: list[str] | None = None
    ) -> tuple[dict[str, Any], int, int]:
        module = facts.engine_module("audit.components")
        model = module.ComponentModel(components=components, candidates=candidates or [], notes=[])
        with mock.patch.object(module, "detect_components", return_value=model):
            return facts.components_section("the inventory")

    def member(self, **overrides: Any) -> Any:
        module = facts.engine_module("audit.components")
        fields: dict[str, Any] = {
            "name": "api",
            "path": "packages/api",
            "declared_by": "pkg:workspaces",
            "manifest": None,
        }
        fields.update(overrides)
        return module.Component(**fields)

    def test_a_name_that_does_not_fit_is_left_out_and_counted(self) -> None:
        section, omitted, _ = self.section_of(components=[self.member(name="a\nb")])
        self.assertEqual((section["declared"], omitted), ([], 1))

    def test_a_path_that_does_not_fit_is_left_out_and_counted(self) -> None:
        section, omitted, _ = self.section_of(components=[self.member(path="C:/packages/api")])
        self.assertEqual((section["declared"], omitted), ([], 1))

    def test_a_declared_by_that_does_not_fit_is_left_out_and_counted(self) -> None:
        section, omitted, _ = self.section_of(components=[self.member(declared_by="\u00e9")])
        self.assertEqual((section["declared"], omitted), ([], 1))

    def test_a_manifest_that_does_not_fit_is_left_out_and_counted(self) -> None:
        section, omitted, _ = self.section_of(components=[self.member(manifest="/etc/package.json")])
        self.assertEqual((section["declared"], omitted), ([], 1))

    def test_a_null_manifest_always_fits(self) -> None:
        section, omitted, _ = self.section_of(components=[self.member(manifest=None)])
        self.assertEqual((len(section["declared"]), omitted), (1, 0))

    def test_a_candidate_that_does_not_fit_is_left_out_and_counted(self) -> None:
        section, _, omitted = self.section_of(components=[], candidates=["C:/apps/worker"])
        self.assertEqual((section["candidates"], omitted), ([], 1))


class CutTests(ComponentCase):
    def test_sixteen_declared_members_are_all_listed(self) -> None:
        workspace: dict[str, str | bytes] = {"package.json": '{"name": "root", "workspaces": ["packages/*"]}\n'}
        workspace.update({f"packages/p{n:02d}/package.json": "{}\n" for n in range(1, 17)})
        self.fill(workspace)
        written = self.written_components(self.repo)
        self.assertEqual(len(written["declared"]), 16)
        document = self.document(self.repo)
        self.assertEqual(document["caps"]["declared_components"], {"limit": 16, "omitted": 0})

    def test_the_seventeenth_declared_member_is_left_out_and_counted(self) -> None:
        workspace: dict[str, str | bytes] = {"package.json": '{"name": "root", "workspaces": ["packages/*"]}\n'}
        workspace.update({f"packages/p{n:02d}/package.json": "{}\n" for n in range(1, 18)})
        self.fill(workspace)
        written = self.written_components(self.repo)
        self.assertEqual([entry["path"] for entry in written["declared"]], [f"packages/p{n:02d}" for n in range(1, 17)])
        document = self.document(self.repo)
        self.assertEqual(document["caps"]["declared_components"], {"limit": 16, "omitted": 1})

    def test_twenty_candidates_are_all_listed(self) -> None:
        self.fill({f"apps/c{n:02d}/package.json": "{}\n" for n in range(1, 21)})
        written = self.written_components(self.repo)
        self.assertEqual(len(written["candidates"]), 20)
        document = self.document(self.repo)
        self.assertEqual(document["caps"]["candidate_components"], {"limit": 20, "omitted": 0})

    def test_the_twenty_first_candidate_is_left_out_and_counted(self) -> None:
        self.fill({f"apps/c{n:02d}/package.json": "{}\n" for n in range(1, 22)})
        written = self.written_components(self.repo)
        self.assertEqual(written["candidates"], [f"apps/c{n:02d}" for n in range(1, 21)])
        document = self.document(self.repo)
        self.assertEqual(document["caps"]["candidate_components"], {"limit": 20, "omitted": 1})

    def test_a_walk_that_was_cut_short_or_excluded_gives_the_components_it_saw(self) -> None:
        self.fill(
            {
                "package.json": '{"name": "root", "workspaces": ["packages/*"]}\n',
                "packages/api/package.json": "{}\n",
            }
        )
        written = self.written_components(self.repo)
        self.assertEqual([entry["path"] for entry in written["declared"]], ["packages/api"])
        excluded = self.written_components(self.repo, "--exclude", "package.json")
        self.assertEqual(excluded["declared"], [])
        self.assertEqual(excluded["candidates"], ["packages/api"])
        self.assertEqual(excluded["notes"], [])


if __name__ == "__main__":
    import unittest

    unittest.main()
