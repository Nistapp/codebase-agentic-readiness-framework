# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The recipe linter: each of its three rules (links, SKILL.md frontmatter, size) has a fixture that passes it
and one that breaks it, and the tool honours the contract (envelope, exit codes, nothing written).

A fixture is a small repository tree built in a temporary folder, with its own `brownfield-recipes/` so the tool
sees a real target. The project's own documentation is linted too, as the standing proof that the rule set the
tool enforces is the rule set the docs already meet. Standard library only.
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
import recipe_lint as rl

TOOLS = _paths.TOOLS
REPO_ROOT = TOOLS.parent.parent


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(rl.INFO, rl.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


class FixtureRepo:
    """A temporary directory with a `brownfield-recipes/` subfolder, built up file by file."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (self.root / "brownfield-recipes").mkdir()

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


class FixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = FixtureRepo(Path(self.temp.name).resolve())

    def lint(self) -> rl.Outcome:
        files = rl.find_markdown(self.repo.root)
        return rl.lint(self.repo.root, files)


# --- The link rule --------------------------------------------------------------------------------------


class LinkTests(FixtureTests):
    def test_a_relative_link_to_an_existing_file_resolves(self) -> None:
        self.repo.write("brownfield-recipes/docs/target.md", "# Target\n")
        self.repo.write("brownfield-recipes/docs/source.md", "See [target](target.md).\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_relative_link_to_a_missing_file_is_reported(self) -> None:
        source = self.repo.write("brownfield-recipes/docs/source.md", "See [gone](nowhere.md).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn(str(source), errors[0])
        self.assertIn("no such file", errors[0])

    def test_a_link_that_climbs_out_of_the_root_is_reported(self) -> None:
        self.repo.write("brownfield-recipes/docs/source.md", "See [out](../../../../etc/passwd).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("leaves", errors[0])

    def test_a_link_can_climb_out_of_brownfield_recipes_but_stay_in_the_root(self) -> None:
        self.repo.write("brownfield-legacy/Phased-Approach.md", "# Phase 1\n")
        self.repo.write(
            "brownfield-recipes/docs/source.md", "See [legacy](../../brownfield-legacy/Phased-Approach.md).\n"
        )
        self.assertEqual(self.lint().errors, [])

    def test_an_external_link_is_never_checked(self) -> None:
        self.repo.write("brownfield-recipes/docs/source.md", "See [spec](https://example.invalid/nowhere).\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_heading_anchor_resolves(self) -> None:
        self.repo.write("brownfield-recipes/docs/target.md", "# Output files\n")
        self.repo.write("brownfield-recipes/docs/source.md", "See [files](target.md#output-files).\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_heading_anchor_with_no_matching_heading_is_reported(self) -> None:
        self.repo.write("brownfield-recipes/docs/target.md", "# Output files\n")
        self.repo.write("brownfield-recipes/docs/source.md", "See [files](target.md#input-files).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("matches no heading", errors[0])

    def test_a_same_file_anchor_resolves(self) -> None:
        self.repo.write(
            "brownfield-recipes/docs/source.md",
            "# Top\n\nSee [top](#top) again.\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_backticks_and_an_em_dash_slugify_like_github(self) -> None:
        # "REQ-SH-022 -- `check` composes" style heading: the backticked word survives, the double space
        # either side of the dropped em dash gives a double hyphen (confirmed against this repository's own
        # anchors in test_the_projects_own_docs_are_clean).
        self.repo.write("brownfield-recipes/docs/target.md", "### REQ-SH-022 — `check` composes the verbs\n")
        self.repo.write(
            "brownfield-recipes/docs/source.md",
            "See [req](target.md#req-sh-022--check-composes-the-verbs).\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_a_line_range_anchor_in_range_resolves(self) -> None:
        self.repo.write("brownfield-recipes/tools/thing.py", "\n".join(f"line {n}" for n in range(1, 11)) + "\n")
        self.repo.write("brownfield-recipes/docs/source.md", "See [thing](../tools/thing.py#L2-L5).\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_line_range_anchor_out_of_range_is_reported(self) -> None:
        self.repo.write("brownfield-recipes/tools/thing.py", "one line\n")
        self.repo.write("brownfield-recipes/docs/source.md", "See [thing](../tools/thing.py#L1-L99).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("out of range", errors[0])

    def test_a_malformed_line_anchor_is_reported(self) -> None:
        self.repo.write("brownfield-recipes/tools/thing.py", "one line\n")
        self.repo.write("brownfield-recipes/docs/source.md", "See [thing](../tools/thing.py#notaline).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("not L<n>", errors[0])

    def test_a_placeholder_link_under_docs_templates_is_skipped(self) -> None:
        self.repo.write(
            "brownfield-recipes/docs/templates/architecture-doc-template.md",
            "> **Related ADRs:** [ADR-NNNN](../architecture/adrs/NNNN-title.md)\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_a_link_inside_a_fenced_code_block_is_not_checked(self) -> None:
        self.repo.write(
            "brownfield-recipes/docs/source.md",
            "```text\nSee [gone](nowhere.md).\n```\n",
        )
        self.assertEqual(self.lint().errors, [])


# --- The frontmatter rule --------------------------------------------------------------------------------


class FrontmatterTests(FixtureTests):
    def test_valid_frontmatter_passes(self) -> None:
        self.repo.write(
            "brownfield-recipes/audit/SKILL.md",
            "---\nname: audit\ndescription: Audit a repository for agentic readiness.\n---\n\n# Audit\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_missing_frontmatter_is_reported(self) -> None:
        self.repo.write("brownfield-recipes/audit/SKILL.md", "# Audit\n\nNo frontmatter here.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("frontmatter", errors[0])

    def test_an_uppercase_name_is_reported(self) -> None:
        self.repo.write(
            "brownfield-recipes/audit/SKILL.md",
            "---\nname: Audit\ndescription: Audit a repository.\n---\n\n# Audit\n",
        )
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("lowercase", errors[0])

    def test_a_name_over_64_characters_is_reported(self) -> None:
        long_name = "a" * 65
        self.repo.write(
            f"brownfield-recipes/{long_name}/SKILL.md",
            f"---\nname: {long_name}\ndescription: Audit a repository.\n---\n\n# Audit\n",
        )
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("64 characters", errors[0])

    def test_a_name_that_does_not_match_its_folder_is_reported(self) -> None:
        self.repo.write(
            "brownfield-recipes/audit/SKILL.md",
            "---\nname: implement\ndescription: Audit a repository.\n---\n\n# Audit\n",
        )
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("must match its folder", errors[0])

    def test_a_missing_description_is_reported(self) -> None:
        self.repo.write("brownfield-recipes/audit/SKILL.md", "---\nname: audit\n---\n\n# Audit\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("no 'description'", errors[0])

    def test_a_description_over_1024_characters_is_reported(self) -> None:
        self.repo.write(
            "brownfield-recipes/audit/SKILL.md",
            "---\nname: audit\ndescription: " + "x" * 1025 + "\n---\n\n# Audit\n",
        )
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("1024", errors[0])


# --- The size rule ----------------------------------------------------------------------------------------


class SizeTests(FixtureTests):
    def test_a_skill_md_at_the_budget_passes(self) -> None:
        body = "---\nname: audit\ndescription: Audit a repository.\n---\n\n" + "\n".join(
            f"line {n}" for n in range(rl.LINE_BUDGET - 5)
        )
        self.repo.write("brownfield-recipes/audit/SKILL.md", body + "\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_skill_md_over_the_budget_is_reported(self) -> None:
        body = "---\nname: audit\ndescription: Audit a repository.\n---\n\n" + "\n".join(
            f"line {n}" for n in range(rl.LINE_BUDGET + 5)
        )
        self.repo.write("brownfield-recipes/audit/SKILL.md", body + "\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("the budget is", errors[0])

    def test_a_check_family_file_over_the_budget_is_reported(self) -> None:
        body = "\n".join(f"line {n}" for n in range(rl.LINE_BUDGET + 5))
        self.repo.write("brownfield-recipes/audit/checks/01-discovery-and-index.md", body + "\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("01-discovery-and-index.md", errors[0])

    def test_a_long_file_outside_audit_checks_is_not_budgeted(self) -> None:
        body = "\n".join(f"line {n}" for n in range(rl.LINE_BUDGET + 5))
        self.repo.write("brownfield-recipes/docs/01-not-a-check-family-file.md", body + "\n")
        self.assertEqual(self.lint().errors, [])


# --- The tool contract -------------------------------------------------------------------------------------


class ToolContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_describe_prints_the_manifest_and_writes_nothing(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["name"], "recipe_lint")
        self.assertEqual(envelope["data"]["writes"], "nothing")

    def test_a_root_without_brownfield_recipes_is_a_usage_error(self) -> None:
        code, envelope, _ = call([str(self.root)])
        self.assertEqual(code, 1)
        self.assertIs(envelope["ok"], False)
        self.assertIn("brownfield-recipes", envelope["data"]["error"])

    def test_a_clean_repo_exits_0_and_writes_nothing(self) -> None:
        (self.root / "brownfield-recipes").mkdir()
        (self.root / "brownfield-recipes" / "a.md").write_text("# A\n", encoding="utf-8")
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        code, envelope, err = call([str(self.root)])
        after = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        self.assertEqual(code, 0)
        self.assertIs(envelope["ok"], True)
        self.assertEqual(envelope["data"], {"root": str(self.root), "files": 1})
        self.assertIn("clean (1 files", err)
        self.assertEqual(before, after)

    def test_broken_links_exit_2_with_every_error_listed(self) -> None:
        (self.root / "brownfield-recipes").mkdir()
        (self.root / "brownfield-recipes" / "a.md").write_text("[gone](nowhere.md)\n", encoding="utf-8")
        (self.root / "brownfield-recipes" / "b.md").write_text("[gone](elsewhere.md)\n", encoding="utf-8")
        code, envelope, err = call([str(self.root)])
        self.assertEqual(code, 2)
        self.assertIs(envelope["ok"], False)
        self.assertEqual(len(envelope["data"]["errors"]), 2)
        self.assertIn("2 problems in 2 files", err)


# --- This project's own documentation -----------------------------------------------------------------------


class SelfTests(unittest.TestCase):
    def test_the_projects_own_docs_are_clean(self) -> None:
        files = rl.find_markdown(REPO_ROOT)
        self.assertGreater(len(files), 100)
        outcome = rl.lint(REPO_ROOT, files)
        self.assertEqual(outcome.errors, [])


if __name__ == "__main__":
    unittest.main()
