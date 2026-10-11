# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Every runner manifest in a fixture parses with a real parser.

``test_make_fixtures.py`` holds the Makefiles to GNU Make. The other runners cannot be run here (no JVM, no
Gradle), but their manifests can be read by the standard library: ``pom.xml`` as XML, ``pyproject.toml`` as TOML and
``package.json`` as JSON. A fixture whose manifest does not parse is not a repository the runner would accept, so
the verb it earns or loses would not mean what the fixture says.
"""

from __future__ import annotations

import json
import sys
import tomllib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402


def manifests(name: str) -> list[Path]:
    return sorted(support.FIXTURES_DIR.glob(f"*/{name}"))


class ManifestFixtureTests(unittest.TestCase):
    def test_the_manifests_this_covers_include_the_jvm_and_pyproject_fixtures(self):
        self.assertTrue({"cmd-ok-maven", "cmd-01-maven-no-formatter"} <= {p.parent.name for p in manifests("pom.xml")})
        self.assertIn("cmd-ok-pyproject-poe", {p.parent.name for p in manifests("pyproject.toml")})
        self.assertIn("cmd-ok-npm", {p.parent.name for p in manifests("package.json")})

    def test_every_pom_is_well_formed_xml(self):
        for path in manifests("pom.xml"):
            with self.subTest(fixture=path.parent.name):
                self.assertEqual(ET.parse(path).getroot().tag, "{http://maven.apache.org/POM/4.0.0}project")

    def test_every_pyproject_is_toml(self):
        for path in manifests("pyproject.toml"):
            with self.subTest(fixture=path.parent.name):
                tomllib.loads(path.read_text(encoding="utf-8"))

    def test_every_package_json_is_json(self):
        for path in manifests("package.json"):
            with self.subTest(fixture=path.parent.name):
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
