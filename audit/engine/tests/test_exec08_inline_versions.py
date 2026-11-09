# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC-08`: a tool version written into a command is invisible to Dependabot and Renovate.

Any literal version no manifest holds is `FAIL`; every literal also held by a manifest is `PARTIAL`, because the
inline copy drifts; none is `PASS`. A version read from a variable is not a literal.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

from audit.rules.checks.execution import check_exec08 as CHECK  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

CHECK_ID = "EXEC-08"

MAKE_HEAD = "check:\n"


def make(*recipe: str) -> str:
    return MAKE_HEAD + "".join(f"\t{line}\n" for line in recipe)


class Exec08Tests(unittest.TestCase):
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

    def tools(self, check: dict) -> list[str]:
        return sorted(e["note"] for f in check["findings"] for e in f["evidence"])

    def test_python_launchers_with_literal_versions_fail(self):
        check = self.check(
            {
                "Makefile": make(
                    "uvx ruff@0.5.0 check .",
                    "uvx --from detect-secrets==1.5.0 detect-secrets scan",
                    "uv run --with jsonschema==4.0.0 python x.py",
                    "pip install black==24.1.0 isort==5.13.2",
                    "pipx run mypy==1.10.0 .",
                )
            }
        )
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(
            self.tools(check),
            ["black 24.1.0", "detect-secrets 1.5.0", "isort 5.13.2", "jsonschema 4.0.0", "mypy 1.10.0", "ruff 0.5.0"],
        )

    def test_go_rust_and_scoped_node_launchers_are_read(self):
        check = self.check(
            {
                "Makefile": make(
                    "go install golang.org/x/tools/cmd/goimports@v0.20.0",
                    "cargo install cargo-deny --version 0.14.0",
                    "npx -y @biomejs/biome@1.8.0 check .",
                )
            }
        )
        self.assertEqual(
            self.tools(check), ["@biomejs/biome 1.8.0", "cargo-deny 0.14.0", "golang.org/x/tools/cmd/goimports v0.20.0"]
        )

    def test_a_version_read_from_a_variable_comments_and_versionless_commands_pass(self):
        check = self.check(
            {
                "Makefile": make("uvx ruff@$(call pin,ruff) check .", "uvx mypy .", "go install x/y@latest"),
                "lefthook.yml": "# npx eslint@9.0.0 is not run here\npre-commit:\n  commands:\n    lint:\n      run: make check\n",
            }
        )
        self.assertEqual(check["verdict"], "PASS")

    def test_workflow_run_steps_and_installer_inputs_are_read(self):
        workflow = (
            "on: [pull_request]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
            '      - uses: astral-sh/setup-uv@v6\n        with:\n          version: "0.5.1"\n'
            "      - run: pip install pre-commit==3.7.0\n"
        )
        check = self.check({".github/workflows/ci.yml": workflow})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(self.tools(check), ["pre-commit 3.7.0", "uv 0.5.1"])
        lines = sorted((e["line"], e["note"]) for e in check["findings"][0]["evidence"])
        self.assertEqual(lines, [(8, "uv 0.5.1"), (9, "pre-commit 3.7.0")])

    def test_every_literal_held_by_a_manifest_is_partial(self):
        check = self.check(
            {
                "Makefile": make("uvx ruff@0.5.0 check .", "go run golang.org/x/vuln/cmd/govulncheck@v1.1.0 ./..."),
                "tools/pyproject.toml": '[dependency-groups]\ntools = ["Ruff==0.5.0"]\n',
                "tools/go.mod": "module tools\n\ngo 1.24\n\nrequire golang.org/x/vuln v1.1.0\n",
            }
        )
        self.assertEqual(check["verdict"], "PARTIAL")

    def test_a_different_manifest_version_does_not_hold_it(self):
        check = self.check(
            {
                "Makefile": make("uvx ruff@0.5.0 check ."),
                "pyproject.toml": '[project]\ndependencies = ["ruff==0.6.0"]\n',
            }
        )
        self.assertEqual(check["verdict"], "FAIL")

    def test_a_file_a_renovate_custom_manager_reads_is_visible(self):
        renovate = '{"customManagers": [{"customType": "regex", "managerFilePatterns": ["/(^|/)Makefile$/"]}]}'
        check = self.check({"Makefile": make("uvx ruff@0.5.0 check ."), "renovate.json": renovate})
        self.assertEqual(check["verdict"], "PASS")

    def test_no_command_surface_is_unknown(self):
        check = self.check({"src/app.py": "print('x')\n"})
        self.assertEqual(check["verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
