# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`TOOL-04` follows a root-Makefile verb the way Make runs it.

Before v0.3.3 C13 the check read only the verb's own recipe text. `OSV := osv-scanner` with `$(OSV) scan`, or a
`security: deps-audit` prerequisite whose recipe runs the scanner, read `PARTIAL`. The check now expands simple
variables and reads each prerequisite target and each `make <target>` or `$(MAKE) <target>` line in turn.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks.tool import _expand_make, _makefile_variables  # noqa: E402
from audit.rules.checks.tool import check_tool04 as CHECK  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "TOOL-04"
PYPROJECT = '[project]\nname = "x"\nversion = "0.1.0"\n'
#: CI runs the verb, so the verdict turns on the local half, the Makefile walk under test (C6: local and CI ⇒ PASS).
WORKFLOW = (
    "on: [pull_request]\njobs:\n  security:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make security\n"
)


class Tool04MakefileFollowTests(unittest.TestCase):
    def check(self, makefile: str, extra: dict[str, str] | None = None) -> dict:
        """Run the check in-process (so coverage traces it) on a repository with this root ``Makefile``."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in {
                "pyproject.toml": PYPROJECT,
                "Makefile": makefile,
                ".github/workflows/ci.yml": WORKFLOW,
                **(extra or {}),
            }.items():
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

    def test_a_variable_that_names_the_scanner_passes(self):
        check = self.check("OSV := go tool osv-scanner\n\nsecurity:\n\t$(OSV) scan --recursive .\n")
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("runs `go tool osv-scanner scan --recursive .`", check["summary"])

    def test_brace_references_and_nested_variables_expand(self):
        check = self.check("TOOL = pip-audit\nAUDIT ?= ${TOOL} --strict\n\nsecurity:\n\t$(AUDIT)\n")
        self.assertEqual(check["verdict"], "PASS")

    def test_a_prerequisite_that_runs_the_audit_passes(self):
        makefile = "security: secrets deps-audit\n\nsecrets:\n\tdetect-secrets scan\n\ndeps-audit:\n\tnpm audit\n"
        check = self.check(makefile, {"package.json": '{"name": "x"}'})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("(target deps-audit)", check["summary"])

    def test_a_make_call_in_the_recipe_is_followed(self):
        makefile = "security:\n\t$(MAKE) deps\n\ndeps:\n\tmake vuln\n\nvuln:\n\tgovulncheck ./...\n"
        check = self.check(makefile)
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("(target vuln)", check["summary"])

    def test_a_chain_with_no_audit_stays_partial(self):
        check = self.check("SCAN := detect-secrets scan\n\nsecurity: secrets\n\nsecrets:\n\t$(SCAN)\n")
        self.assertEqual(check["verdict"], "PARTIAL")

    def test_a_cycle_ends(self):
        check = self.check("security: a\n\na:\n\t$(MAKE) b\n\nb:\n\t$(MAKE) a\n")
        self.assertEqual(check["verdict"], "PARTIAL")

    def test_a_call_into_another_makefile_is_not_followed(self):
        makefile = "security:\n\t$(MAKE) -C tools deps\n\ndeps:\n\tpip-audit\n"
        self.assertEqual(self.check(makefile)["verdict"], "PARTIAL")

    def test_an_unknown_variable_is_kept(self):
        self.assertEqual(_expand_make("$(NOPE) x", {}), "$(NOPE) x")
        self.assertEqual(_expand_make("$(call pin,ruff)", {"call": "x"}), "$(call pin,ruff)")

    def test_assignment_forms(self):
        variables = _makefile_variables(
            "A = one\nA ?= two\nB := x\nB += y\nexport C ::= z\n\ttarget-line = no\nD = long \\\n  value\n"
        )
        self.assertEqual(variables, {"A": "one", "B": "x y", "C": "z", "D": "long value"})


if __name__ == "__main__":
    unittest.main()
