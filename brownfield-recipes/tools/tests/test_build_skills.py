# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The skill bundler: the bundle has its three parts (`SKILL.md`, `references/`, `scripts/`), the frontmatter
name is rewritten for the bundle, and two builds from the same source tree agree file for file.

Builds for real, into a temporary directory — there is no fixture to fake this against, since the whole
point is copying this repository's own files; a build that can run only against a double would not prove the
real one works. One pass runs `build.py` for real too (network-free, stdlib-only), so this test is slower
than most in this suite but still seconds, not minutes.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence

import _paths
import _common
import build_skills as bs

TOOLS = _paths.TOOLS


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
            self.assertTrue((bundle_dir / "scripts" / "deterministic-audit" / "audit" / "__main__.py").is_file())
            self.assertTrue((bundle_dir / "scripts" / "audit.pyz").is_file())

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


if __name__ == "__main__":
    unittest.main()
