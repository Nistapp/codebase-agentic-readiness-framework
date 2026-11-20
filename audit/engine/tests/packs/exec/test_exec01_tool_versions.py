# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC-01` reads a `.tool-versions` line for ruby, dotnet and jvm (ruleset 2026-11-20.4).

Before that revision a shared `.tool-versions` counted only for node, python, rust, go and php, although the check
page said a matching line pins every ecosystem. The asdf and mise plugin names are `ruby`, `java` for the JDK (jvm),
and `dotnet-core` (asdf) or `dotnet` (mise) for .NET.
"""

from __future__ import annotations

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

#: ecosystem -> a manifest that makes the stack detect it, and no pin file of its own
MANIFESTS = {
    "ruby": ("Gemfile", "gem 'rake'\n"),
    "dotnet": ("App.csproj", "<Project />\n"),
    "jvm": ("pom.xml", "<project />\n"),
}


class Exec01ToolVersionsTests(unittest.TestCase):
    def check(self, files: dict[str, str]) -> tuple[str, str]:
        """Run the check in-process (so coverage traces it) on a repository built from ``files``."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            inventory = build_inventory(root)
            outcome = CHECK(
                spec=REGISTRY_BY_ID["EXEC-01"],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        return outcome.verdict.value, outcome.summary

    def test_each_plugin_name_pins_its_ecosystem(self):
        cases = (
            ("ruby", "ruby 3.3.6\n"),
            ("dotnet", "dotnet 8.0.404\n"),
            ("dotnet", "dotnet-core 8.0.404\n"),
            ("jvm", "java temurin-21.0.5+11.0.LTS\n"),
            ("jvm", "java 21\n"),
        )
        for ecosystem, line in cases:
            with self.subTest(line=line):
                name, text = MANIFESTS[ecosystem]
                verdict = self.check({name: text, ".tool-versions": "nodejs 22.11.0\n" + line})
                self.assertEqual(verdict, ("PASS", f"pinned: {ecosystem} (.tool-versions)"))

    def test_a_line_for_another_tool_does_not_pin(self):
        cases = (("ruby", "rubocop 1.69.0\n"), ("dotnet", "dotnet-script 1.6.0\n"), ("jvm", "javascript 1\n"))
        for ecosystem, line in cases:
            with self.subTest(line=line):
                name, text = MANIFESTS[ecosystem]
                verdict = self.check({name: text, ".tool-versions": line})
                self.assertEqual(verdict, ("FAIL", f"unpinned: {ecosystem}"))

    def test_a_java_line_beside_a_wrapper_is_cited_with_it(self):
        verdict = self.check({"pom.xml": "<project />\n", ".tool-versions": "java 21.0.5\n", "mvnw": "#!/bin/sh\n"})
        self.assertEqual(verdict, ("PASS", "pinned: jvm (.tool-versions, mvnw)"))


if __name__ == "__main__":
    unittest.main()
