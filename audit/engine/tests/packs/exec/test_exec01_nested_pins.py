# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC-01` reads the toolchain pin in a nested manifest, as it reads pin files at any depth.

A repository whose only Go module is `tools/osv/go.mod` pins Go with that file's `go` directive. Before v0.3.3 C13
the check found the nested `go.mod` (the stack was detected) but read only a root `go.mod`, so it failed a pinned
module. The same held for a nested `requires-python` and a nested `engines.node`.

Since v0.3.5.1 item 4.5 (ruleset 2026-11-10.4) one pinned module no longer covers its siblings: a module manifest
that no pin reaches (its own manifest, or a pin in its folder or a parent folder) makes the check `PARTIAL`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks.execution import check_exec01 as CHECK  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "EXEC-01"


class Exec01NestedPinsTests(unittest.TestCase):
    def check(self, files: dict[str, str]) -> dict:
        """Run the check in-process (so coverage traces it) on a repository built from ``files``."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            inventory = build_inventory(root)
            outcome = CHECK(
                spec=REGISTRY_BY_ID[CHECK_ID],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        return {
            "verdict": outcome.verdict.value,
            "summary": outcome.summary,
            "findings": [finding.to_dict() for finding in outcome.findings],
        }

    def test_nested_go_directive_pins_go(self):
        check = self.check({"tools/osv/go.mod": "module example.com/osv\n\ngo 1.24\n"})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("tools/osv/go.mod (go directive)", check["summary"])

    def test_nested_go_mod_without_a_directive_fails(self):
        check = self.check({"tools/lint/go.mod": "module example.com/lint\n"})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("unpinned: go", check["summary"])

    def test_one_pinned_module_does_not_cover_an_unpinned_sibling(self):
        check = self.check(
            {
                "tools/a/go.mod": "module example.com/a\n",
                "tools/b/go.mod": "module example.com/b\n\ngo 1.24\n",
            }
        )
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("pinned: go (tools/b/go.mod (go directive))", check["summary"])
        self.assertIn("modules no pin reaches: go (tools/a/go.mod)", check["summary"])
        self.assertEqual([e["path"] for e in check["findings"][0]["evidence"]], ["tools/a/go.mod"])

    def test_a_parent_go_mod_does_not_pin_a_nested_module(self):
        check = self.check({"go.mod": "module example.com/root\n\ngo 1.23\n", "tools/a/go.mod": "module a\n"})
        self.assertEqual(check["verdict"], "PARTIAL")

    def test_every_module_pinned_passes(self):
        check = self.check(
            {
                "tools/a/go.mod": "module example.com/a\n\ngo 1.24\n",
                "tools/b/go.mod": "module example.com/b\n\ngo 1.24\n",
            }
        )
        self.assertEqual(check["verdict"], "PASS")

    def test_a_root_pin_file_reaches_every_module(self):
        files = {
            ".python-version": "3.12\n",
            "pyproject.toml": '[project]\nname = "root"\n',
            "tools/x/pyproject.toml": '[project]\nname = "x"\n',
        }
        self.assertEqual(self.check(files)["verdict"], "PASS")

    def test_a_pin_file_reaches_the_modules_below_it(self):
        files = {"apps/.nvmrc": "22\n", "apps/web/package.json": json.dumps({"name": "web"})}
        self.assertEqual(self.check(files)["verdict"], "PASS")

    def test_a_root_tool_versions_line_reaches_every_module(self):
        files = {".tool-versions": "nodejs 22.1.0\n", "apps/web/package.json": json.dumps({"name": "web"})}
        self.assertEqual(self.check(files)["verdict"], "PASS")

    def test_a_workspace_root_pin_reaches_its_members(self):
        root = json.dumps({"name": "root", "engines": {"node": ">=22"}, "workspaces": ["apps/*"]})
        files = {"package.json": root, "apps/web/package.json": json.dumps({"name": "web"})}
        self.assertEqual(self.check(files)["verdict"], "PASS")

    def test_a_pin_in_a_sibling_folder_does_not_reach(self):
        files = {
            "apps/api/.nvmrc": "22\n",
            "apps/api/package.json": json.dumps({"name": "api"}),
            "apps/web/package.json": json.dumps({"name": "web"}),
        }
        check = self.check(files)
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("node (apps/web/package.json)", check["summary"])

    def test_a_long_list_of_modules_is_cut_in_the_summary(self):
        files = {f"m{i}/go.mod": f"module m{i}\n" for i in range(7)}
        files["pinned/go.mod"] = "module p\n\ngo 1.24\n"
        check = self.check(files)
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("and 2 more", check["summary"])
        self.assertEqual(len(check["findings"][0]["evidence"]), 7)

    def test_a_fail_keeps_the_partial_findings_of_other_ecosystems(self):
        files = {
            "tools/a/go.mod": "module a\n",
            "tools/b/go.mod": "module b\n\ngo 1.24\n",
            "web/package.json": json.dumps({"name": "web"}),
        }
        check = self.check(files)
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(sorted(f["verdict"] for f in check["findings"]), ["FAIL", "PARTIAL"])

    def test_the_shallowest_pinning_manifest_is_the_evidence(self):
        check = self.check(
            {
                "go.mod": "module example.com/root\n\ngo 1.23\n",
                "tools/b/go.mod": "module example.com/b\n\ngo 1.24\n",
            }
        )
        self.assertIn("go (go.mod (go directive))", check["summary"])
        self.assertNotIn("tools/b/go.mod", check["summary"])

    def test_nested_requires_python_pins_python(self):
        check = self.check({"service/pyproject.toml": '[project]\nname = "svc"\nrequires-python = ">=3.11"\n'})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("service/pyproject.toml (requires-python)", check["summary"])

    def test_nested_engines_pins_node(self):
        manifest = json.dumps({"name": "web", "engines": {"node": ">=22"}})
        check = self.check({"apps/web/package.json": manifest})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("apps/web/package.json (engines.node)", check["summary"])

    def test_a_pinned_member_does_not_pin_an_unpinned_root(self):
        manifest = json.dumps({"name": "web", "engines": {"node": ">=22"}})
        check = self.check({"package.json": json.dumps({"name": "root"}), "apps/web/package.json": manifest})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("node (package.json)", check["summary"])

    def test_nested_manifest_without_a_pin_still_fails(self):
        check = self.check({"apps/web/package.json": json.dumps({"name": "web"})})
        self.assertEqual(check["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
