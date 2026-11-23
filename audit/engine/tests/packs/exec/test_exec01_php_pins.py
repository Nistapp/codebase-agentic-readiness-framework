# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC-01` reads the PHP toolchain pin (ruleset 2026-11-19.7).

Before that revision PHP had no entry in the pin table, so a PHP-only repository read `UNKNOWN` and a mixed
repository was judged on its other ecosystems alone. Four sources pin PHP now: a `.php-version` file, a `php` line in
`.tool-versions`, and in `composer.json` the key `config.platform.php`, then `require.php`. A `composer.json` is read
at any depth, shallowest first, as `package.json` is for `engines.node`.

Since ruleset 2026-11-20.3 each `composer.json` is also a module the pin must reach. A `.php-version` or a
`.tool-versions` `php` line in its folder or a parent folder reaches it; a parent `composer.json` does not, because
Composer installs each project on its own, as a parent `go.mod` does not reach a nested Go module. An unreached
module reads `PARTIAL`.
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


def _composer(**keys: object) -> str:
    return json.dumps({"name": "example/app", **keys})


class Exec01PhpPinTests(unittest.TestCase):
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

    def test_php_version_file_pins_php(self):
        check = self.check({"composer.json": _composer(), ".php-version": "8.3.14\n"})
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["summary"], "pinned: php (.php-version)")

    def test_a_tool_versions_php_line_pins_php(self):
        check = self.check({"composer.json": _composer(), ".tool-versions": "nodejs 22.11.0\nphp 8.3.14\n"})
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["summary"], "pinned: php (.tool-versions)")

    def test_a_tool_versions_file_without_a_php_line_does_not_pin_php(self):
        check = self.check({"composer.json": _composer(), ".tool-versions": "phpunit 11.0.0\n"})
        self.assertEqual(check["verdict"], "FAIL")

    def test_config_platform_php_pins_php(self):
        check = self.check({"composer.json": _composer(config={"platform": {"php": "8.3.14"}})})
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["summary"], "pinned: php (composer.json (config.platform.php))")

    def test_require_php_pins_php(self):
        check = self.check({"composer.json": _composer(require={"php": ">=8.2"})})
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["summary"], "pinned: php (composer.json (require.php))")

    def test_config_platform_php_is_cited_before_require_php(self):
        manifest = _composer(require={"php": ">=8.2"}, config={"platform": {"php": "8.3.14"}})
        check = self.check({"composer.json": manifest})
        self.assertEqual(check["summary"], "pinned: php (composer.json (config.platform.php))")

    def test_every_source_is_listed_when_several_pin(self):
        check = self.check(
            {
                "composer.json": _composer(require={"php": ">=8.2"}),
                ".php-version": "8.3\n",
                ".tool-versions": "php 8.3.14\n",
            }
        )
        self.assertEqual(check["summary"], "pinned: php (.php-version, .tool-versions, composer.json (require.php))")

    def test_the_shallowest_composer_json_that_pins_is_cited(self):
        check = self.check(
            {
                "composer.json": _composer(),
                "packages/a/composer.json": _composer(require={"php": "^8.1"}),
                "packages/a/b/composer.json": _composer(require={"php": "^8.3"}),
            }
        )
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertEqual(
            check["summary"],
            "pinned: php (packages/a/composer.json (require.php)); modules no pin reaches: php (composer.json)",
        )

    def test_a_composer_json_with_no_php_key_fails(self):
        check = self.check({"composer.json": _composer(require={"monolog/monolog": "^3.0"})})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(check["summary"], "unpinned: php")
        (finding,) = check["findings"]
        self.assertIn(".php-version", finding["remediation"])

    def test_an_empty_or_non_string_php_key_does_not_pin(self):
        for keys in ({"require": {"php": ""}}, {"require": {"php": 8}}, {"config": {"platform": {"php": "  "}}}):
            with self.subTest(keys=keys):
                self.assertEqual(self.check({"composer.json": _composer(**keys)})["verdict"], "FAIL")

    def test_a_composer_json_that_is_not_an_object_does_not_pin(self):
        for text in ("[1, 2]", "{not json", '{"config": [], "require": []}'):
            with self.subTest(text=text):
                self.assertEqual(self.check({"composer.json": text})["verdict"], "FAIL")

    def test_an_unpinned_php_project_fails_beside_a_pinned_node_project(self):
        check = self.check(
            {
                "composer.json": _composer(),
                "package.json": json.dumps({"name": "web", "engines": {"node": ">=22"}}),
            }
        )
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(check["summary"], "unpinned: php")

    def test_a_nested_composer_project_a_parent_composer_json_pins_is_not_reached(self):
        check = self.check(
            {"composer.json": _composer(require={"php": ">=8.2"}), "tools/lint/composer.json": _composer()}
        )
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertEqual(
            check["summary"],
            "pinned: php (composer.json (require.php)); modules no pin reaches: php (tools/lint/composer.json)",
        )
        (finding,) = check["findings"]
        self.assertEqual((finding["id"], finding["verdict"]), ("EXEC-01:php", "PARTIAL"))
        self.assertEqual([e["path"] for e in finding["evidence"]], ["tools/lint/composer.json"])
        self.assertIn(".php-version in its folder or a parent folder", finding["remediation"])

    def test_a_nested_composer_project_that_pins_php_itself_is_reached(self):
        check = self.check(
            {
                "composer.json": _composer(require={"php": ">=8.2"}),
                "tools/lint/composer.json": _composer(config={"platform": {"php": "8.3.14"}}),
            }
        )
        self.assertEqual(check["verdict"], "PASS")

    def test_a_php_version_file_in_a_parent_folder_reaches_every_composer_project(self):
        for pin in ({".php-version": "8.3.14\n"}, {".tool-versions": "php 8.3.14\n"}):
            with self.subTest(pin=pin):
                check = self.check({**pin, "composer.json": _composer(), "tools/lint/composer.json": _composer()})
                self.assertEqual(check["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
