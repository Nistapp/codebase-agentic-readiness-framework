# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC-01` reads the toolchain pin in a nested manifest, as it reads pin files at any depth.

A repository whose only Go module is `tools/osv/go.mod` pins Go with that file's `go` directive. Before v0.3.3 C13
the check found the nested `go.mod` (the stack was detected) but read only a root `go.mod`, so it failed a pinned
module. The same held for a nested `requires-python` and a nested `engines.node`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

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
        return {"verdict": outcome.verdict.value, "summary": outcome.summary}

    def test_nested_go_directive_pins_go(self):
        check = self.check({"tools/osv/go.mod": "module example.com/osv\n\ngo 1.24\n"})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("tools/osv/go.mod (go directive)", check["summary"])

    def test_nested_go_mod_without_a_directive_fails(self):
        check = self.check({"tools/lint/go.mod": "module example.com/lint\n"})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("unpinned: go", check["summary"])

    def test_one_pinned_module_is_enough(self):
        check = self.check(
            {
                "tools/a/go.mod": "module example.com/a\n",
                "tools/b/go.mod": "module example.com/b\n\ngo 1.24\n",
            }
        )
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("tools/b/go.mod", check["summary"])

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
        check = self.check({"package.json": json.dumps({"name": "root"}), "apps/web/package.json": manifest})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("apps/web/package.json (engines.node)", check["summary"])

    def test_nested_manifest_without_a_pin_still_fails(self):
        check = self.check({"apps/web/package.json": json.dumps({"name": "web"})})
        self.assertEqual(check["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
