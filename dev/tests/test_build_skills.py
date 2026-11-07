# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The skill bundler: each bundle has its three parts (`SKILL.md`, `references/`, `scripts/`) and a `LICENSE`,
the frontmatter name is rewritten for the bundle, and two builds from the same source tree agree file for file.
The implement bundle also keeps no framework tool path and no link that leaves it, and its tools run against the
audit bundle installed beside it.

Builds for real, into a temporary directory — there is no fixture to fake this against, since the whole
point is copying this repository's own files; a build that can run only against a double would not prove the
real one works. One pass runs `build.py` for real too (network-free, stdlib-only), so this test is slower
than most in this suite but still seconds, not minutes.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence

import _dev_paths  # noqa: F401
import _common
import build_skills as bs
import recipe_lint

EXAMPLE_REPORT = bs.AUDIT_SCHEMA / "examples" / "example-service.audit-report.20261010T094207Z.json"
#: Where a tool command in a source page starts; none of them may be left in a bundle.
SOURCE_TOOL_PREFIXES = ("python3 audit/tools/", "python3 implement/tools/", "python3 audit/tools/")
LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"^\s*(```+|~~~+)")


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(bs.INFO, bs.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


class BuildSkillsTests(unittest.TestCase):
    def test_describe(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["name"], "build_skills")

    def test_bundle_has_its_three_parts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = bs.build_bundle(Path(tmp))
            self.assertEqual(bundle_dir.name, bs.BUNDLE_NAME)
            self.assertTrue((bundle_dir / "SKILL.md").is_file())

            checks = {p.name for p in (bundle_dir / "references" / "checks").glob("*.md")}
            self.assertIn("README.md", checks)
            self.assertIn("01-discovery-and-index.md", checks)

            stacks = {p.name for p in (bundle_dir / "references" / "stacks").glob("*.md")}
            self.assertEqual(stacks, {"README.md", "java.md", "python.md", "typescript-node.md"})

            ref_schema = {p.name for p in (bundle_dir / "references" / "schema").iterdir()}
            self.assertEqual(ref_schema, set(bs.SCHEMA_FILES))

            for name in bs.TOOL_FILES:
                self.assertTrue((bundle_dir / "scripts" / "tools" / name).is_file(), name)
            script_schema = {p.name for p in (bundle_dir / "scripts" / "schema").iterdir()}
            self.assertEqual(script_schema, set(bs.SCHEMA_FILES))
            self.assertTrue((bundle_dir / "scripts" / "catalogue.json").is_file())
            self.assertTrue((bundle_dir / "scripts" / "engine" / "audit" / "__main__.py").is_file())
            self.assertFalse((bundle_dir / "scripts" / "deterministic-audit").exists())
            self.assertTrue((bundle_dir / "scripts" / "audit.pyz").is_file())

    def test_bundle_carries_the_code_licence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = bs.build_bundle(Path(tmp))
            self.assertEqual((bundle_dir / "LICENSE").read_bytes(), bs.LICENSE_CODE.read_bytes())

    def test_bundled_engine_launcher_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = bs.build_bundle(Path(tmp))
            done = run_bundle_tool(bundle_dir / "scripts" / "tools" / "engine.py", "--describe")
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_skill_md_frontmatter_is_rewritten_for_the_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = bs.build_bundle(Path(tmp))
            text = (bundle_dir / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"\nname: {bs.BUNDLE_NAME}\n", text)
            self.assertNotIn("\nname: audit\n", text)

    def test_handler_reports_the_bundle_path_and_file_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, envelope, err = call(["--out-dir", tmp])
            self.assertEqual(code, 0)
            self.assertTrue(envelope["ok"])
            bundle = Path(envelope["data"]["bundle"])
            self.assertEqual(bundle, Path(tmp).resolve() / bs.BUNDLE_NAME)
            on_disk = sum(1 for p in bundle.rglob("*") if p.is_file())
            self.assertEqual(envelope["data"]["files"], on_disk)
            self.assertIn("build_skills: wrote", err)

    def test_two_builds_from_the_same_source_agree_file_for_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = bs.build_bundle(Path(tmp) / "first")
            second = bs.build_bundle(Path(tmp) / "second")
            first_files = sorted(p.relative_to(first).as_posix() for p in first.rglob("*") if p.is_file())
            second_files = sorted(p.relative_to(second).as_posix() for p in second.rglob("*") if p.is_file())
            self.assertEqual(first_files, second_files)
            for relative in first_files:
                self.assertEqual(
                    (first / relative).read_bytes(),
                    (second / relative).read_bytes(),
                    relative,
                )

    def test_rebuilding_into_the_same_out_dir_replaces_the_bundle_whole(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            bundle_dir = bs.build_bundle(out_dir)
            stray = bundle_dir / "scripts" / "tools" / "leftover-from-a-prior-build.py"
            stray.write_text("# stale\n", encoding="utf-8")
            bs.build_bundle(out_dir)
            self.assertFalse(stray.exists())


def links_outside_fences(text: str) -> list[str]:
    targets: list[str] = []
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            targets.extend(match.group(1) for match in LINK.finditer(line))
    return targets


class ImplementBundleTests(unittest.TestCase):
    _tmp: "tempfile.TemporaryDirectory[str]"
    out_dir: Path
    bundle: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out_dir = Path(cls._tmp.name)
        cls.bundle = bs.build_implement_bundle(cls.out_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def markdown_files(self) -> list[Path]:
        return sorted(self.bundle.rglob("*.md"))

    def test_bundle_has_its_three_parts(self) -> None:
        self.assertEqual(self.bundle.name, bs.IMPLEMENT_BUNDLE_NAME)
        for relative in (
            "SKILL.md",
            "references/state.md",
            "references/prompts/kickoff.md",
            "references/playbooks/README.md",
            "references/playbooks/define-command-surface.md",
            "references/checks/04-command-surface.md",
            "references/stacks/java.md",
            "references/adrs/0003-push-and-pr-policy.md",
            "references/spec/command-surface.md",
            "references/spec/decisions/0002-lint-in-the-gate.md",
            "references/schema/SCHEMA.md",
            "references/schema/readiness-state.schema.json",
            "references/tools-cli.md",
            "scripts/catalogue.json",
            "scripts/tools/engine.py",
            "scripts/tools/_audit_tools_path.py",
            "LICENSE",
        ):
            self.assertTrue((self.bundle / relative).is_file(), relative)
        for name in bs.IMPLEMENT_TOOL_FILES:
            self.assertTrue((self.bundle / "scripts" / "tools" / name).is_file(), name)
        script_schema = {p.name for p in (self.bundle / "scripts" / "schema").iterdir()}
        self.assertEqual(script_schema, set(bs.IMPLEMENT_SCHEMA_FILES))
        source_playbooks = {p.name for p in (bs.IMPLEMENT / "playbooks").glob("*.md")}
        bundle_playbooks = {p.name for p in (self.bundle / "references" / "playbooks").glob("*.md")}
        self.assertEqual(bundle_playbooks, source_playbooks)

    def test_bundle_carries_the_code_licence(self) -> None:
        self.assertEqual((self.bundle / "LICENSE").read_bytes(), bs.LICENSE_CODE.read_bytes())

    def test_no_engine_copy_in_the_bundle(self) -> None:
        self.assertFalse((self.bundle / "scripts" / "engine").exists())
        self.assertFalse((self.bundle / "scripts" / "deterministic-audit").exists())
        self.assertFalse((self.bundle / "scripts" / "audit.pyz").exists())
        self.assertEqual((self.bundle / "scripts" / "tools" / "engine.py").read_text(encoding="utf-8"), bs.ENGINE_SHIM)

    def test_skill_md_frontmatter_is_rewritten_for_the_bundle(self) -> None:
        text = (self.bundle / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"\nname: {bs.IMPLEMENT_BUNDLE_NAME}\n", text)
        self.assertNotIn("\nname: implement\n", text)

    def test_no_framework_tool_command_is_left(self) -> None:
        for file in self.markdown_files():
            text = file.read_text(encoding="utf-8")
            for prefix in SOURCE_TOOL_PREFIXES:
                self.assertNotIn(prefix, text, file.relative_to(self.bundle))
        skill = (self.bundle / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/tools/progress.py", skill)
        self.assertIn(f"python3 ../{bs.BUNDLE_NAME}/scripts/tools/engine.py", skill)

    def test_every_link_resolves_inside_the_bundle(self) -> None:
        root = self.bundle.resolve()
        for file in self.markdown_files():
            text = file.read_text(encoding="utf-8")
            for target in links_outside_fences(text):
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                where = f"{file.relative_to(self.bundle)} -> {target}"
                path_part, _, fragment = target.partition("#")
                resolved = (file.parent / path_part).resolve() if path_part else file.resolve()
                self.assertTrue(resolved == root or root in resolved.parents, f"leaves the bundle: {where}")
                self.assertTrue(resolved.exists(), f"does not resolve: {where}")
                if fragment and resolved.suffix == ".md":
                    lines = resolved.read_text(encoding="utf-8").splitlines()
                    self.assertIn(fragment, recipe_lint.heading_slugs(resolved, lines), f"no such heading: {where}")

    def test_tools_cli_reference_keeps_only_the_carried_tools(self) -> None:
        text = (self.bundle / "references" / "tools-cli.md").read_text(encoding="utf-8")
        headings = [line[3:] for line in text.splitlines() if line.startswith("## ")]
        self.assertEqual(headings, list(bs.TOOLS_CLI_SECTIONS))

    def test_extract_sections_refuses_a_missing_section(self) -> None:
        with self.assertRaises(_common.ToolError):
            bs.extract_sections("# T\n\n## a\n\ntext\n", ("a", "b"))

    def test_two_builds_agree_file_for_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            second = bs.build_implement_bundle(Path(tmp))
            first_files = sorted(p.relative_to(self.bundle).as_posix() for p in self.bundle.rglob("*") if p.is_file())
            second_files = sorted(p.relative_to(second).as_posix() for p in second.rglob("*") if p.is_file())
            self.assertEqual(first_files, second_files)
            for relative in first_files:
                self.assertEqual((self.bundle / relative).read_bytes(), (second / relative).read_bytes(), relative)

    def test_rebuilding_replaces_the_bundle_whole(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = bs.build_implement_bundle(Path(tmp))
            stray = bundle_dir / "references" / "leftover-from-a-prior-build.md"
            stray.write_text("stale\n", encoding="utf-8")
            bs.build_implement_bundle(Path(tmp))
            self.assertFalse(stray.exists())


def run_bundle_tool(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, str(script), *args], capture_output=True, text=True, check=False, env=env, timeout=120
    )


class ImplementBundleRunsTests(unittest.TestCase):
    """The bundled tools run on their own, with the engine from the audit bundle installed beside them."""

    def test_validate_report_runs_with_the_audit_bundle_beside_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bs.build_bundle(Path(tmp))
            implement = bs.build_implement_bundle(Path(tmp))
            done = run_bundle_tool(implement / "scripts" / "tools" / "validate_report.py", str(EXAMPLE_REPORT))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue(json.loads(done.stdout)["data"]["valid"])

    def test_without_the_audit_bundle_the_error_names_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            implement = bs.build_implement_bundle(Path(tmp))
            done = run_bundle_tool(implement / "scripts" / "tools" / "validate_report.py", str(EXAMPLE_REPORT))
            self.assertEqual(done.returncode, 1)
            self.assertIn(bs.BUNDLE_NAME, done.stderr)
            described = run_bundle_tool(implement / "scripts" / "tools" / "progress.py", "--describe")
            self.assertEqual(described.returncode, 0, described.stderr)

    def test_handler_builds_both_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, envelope, _ = call(["--out-dir", tmp])
            self.assertEqual(code, 0)
            names = [bundle["name"] for bundle in envelope["data"]["bundles"]]
            self.assertEqual(names, [bs.BUNDLE_NAME, bs.IMPLEMENT_BUNDLE_NAME])
            for bundle in envelope["data"]["bundles"]:
                on_disk = sum(1 for p in Path(bundle["bundle"]).rglob("*") if p.is_file())
                self.assertEqual(bundle["files"], on_disk)


if __name__ == "__main__":
    unittest.main()
