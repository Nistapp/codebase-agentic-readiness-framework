# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The recipe linter: each of its eight rules (links, SKILL.md frontmatter, size, tool, check, requirement,
playbook references and the tool catalogue) has a fixture that passes it and one that breaks it, and the tool
honours the contract (envelope, exit codes, nothing written unless `--write-catalogue` is given).

A fixture is a small repository tree built in a temporary folder, with its own `audit/` (the folder that marks a
framework repository) so the tool sees a real target; recipe Markdown goes under `audit/`, `implement/` or
`docs/`, tools under `audit/tools/` or `implement/tools/`. The project's own documentation is linted too, as the standing proof that the rule set the
tool enforces is the rule set the docs already meet. Standard library only.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence

import _dev_paths  # noqa: F401
import _common
import recipe_lint as rl

REPO_ROOT = Path(__file__).resolve().parents[2]


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(rl.INFO, rl.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue()), err.getvalue()


class FixtureRepo:
    """A temporary directory with an `audit/` subfolder, built up file by file."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (self.root / "audit").mkdir()

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_catalogue(self, checks: list[dict[str, Any]]) -> Path:
        return self.write(
            "audit/catalogue.json",
            json.dumps({"catalogue_version": "0.1.0", "fingerprint": "0" * 16, "checks": checks}),
        )

    def write_requirements(self, ids: list[str]) -> Path:
        body = "\n\n".join(f"### {req_id} — Some requirement\n\nBody.\n" for req_id in ids)
        return self.write("spec/readiness-requirements.md", body + "\n")


class FixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = FixtureRepo(Path(self.temp.name).resolve())

    def lint(self, *, describe_timeout: float = rl.DESCRIBE_TIMEOUT_S) -> rl.Outcome:
        files = rl.find_markdown(self.repo.root)
        return rl.lint(self.repo.root, files, describe_timeout=describe_timeout)

    def write_tool(self, name: str, source: str, folder: str = "audit/tools") -> Path:
        return self.repo.write(f"{folder}/{name}.py", source)


# --- The markdown sweep ----------------------------------------------------------------------------------


class FindMarkdownTests(FixtureTests):
    def test_a_file_under_dist_is_never_swept(self) -> None:
        self.repo.write("docs/reference/kept.md", "# Kept\n")
        self.repo.write(
            "audit/dist/skills/agentic-readiness-audit/SKILL.md",
            "---\nname: audit\ndescription: x\n---\n\n[broken](../does-not-exist.md)\n",
        )
        files = rl.find_markdown(self.repo.root)
        relative = {path.relative_to(self.repo.root).as_posix() for path in files}
        self.assertIn("docs/reference/kept.md", relative)
        self.assertFalse(any(path.startswith("audit/dist/") for path in relative))

    def test_a_broken_link_under_dist_does_not_fail_the_lint(self) -> None:
        self.repo.write(
            "audit/dist/skills/agentic-readiness-audit/SKILL.md",
            "---\nname: audit\ndescription: x\n---\n\n[broken](../does-not-exist.md)\n",
        )
        outcome = self.lint()
        self.assertEqual(outcome.errors, [])


class RootPageLinkTests(FixtureTests):
    def lint_root_pages(self) -> rl.Outcome:
        files = rl.find_markdown(self.repo.root)
        return rl.lint(self.repo.root, files, root_pages=rl.find_root_pages(self.repo.root))

    def test_the_root_pages_are_found(self) -> None:
        for relative in ("README.md", "spec/B.md", "greenfield/C.md", "other/D.md", "docs/framework/E.md"):
            self.repo.write(relative, "# T\n")
        found = {path.relative_to(self.repo.root).as_posix() for path in rl.find_root_pages(self.repo.root)}
        self.assertEqual(found, {"README.md", "spec/B.md", "greenfield/C.md"})

    def test_the_root_process_documents_are_root_pages(self) -> None:
        for relative in ("AGENTS.md", "CONTRIBUTING.md", "RELEASE_PROCESS.md", "SECURITY.md", "CHANGELOG.md"):
            self.repo.write(relative, "# T\n")
        found = {path.relative_to(self.repo.root).as_posix() for path in rl.find_root_pages(self.repo.root)}
        self.assertEqual(found, {"AGENTS.md", "CONTRIBUTING.md", "RELEASE_PROCESS.md", "SECURITY.md"})

    def test_a_broken_link_in_a_root_process_document_is_reported(self) -> None:
        self.repo.write("RELEASE_PROCESS.md", "# R\n\n[gone](docs/missing.md)\n")
        errors = self.lint_root_pages().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("RELEASE_PROCESS.md:3", errors[0])

    def test_the_framework_pages_under_docs_framework_are_recipe_markdown(self) -> None:
        self.repo.write("docs/framework/glossary.md", "# G\n\n[gone](missing.md)\n")
        files = {path.relative_to(self.repo.root).as_posix() for path in rl.find_markdown(self.repo.root)}
        self.assertIn("docs/framework/glossary.md", files)
        errors = self.lint_root_pages().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("docs/framework/glossary.md:3", errors[0])

    def test_a_broken_link_in_a_root_page_is_reported(self) -> None:
        self.repo.write("greenfield/Glossary.md", "# G\n\n[gone](Missing.md)\n")
        errors = self.lint_root_pages().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("greenfield/Glossary.md:3", errors[0])

    def test_a_good_link_and_anchor_in_a_root_page_pass(self) -> None:
        self.repo.write("README.md", "# R\n\n[g](spec/Glossary.md#terms)\n")
        self.repo.write("spec/Glossary.md", "# G\n\n## Terms\n")
        self.assertEqual(self.lint_root_pages().errors, [])

    def test_the_template_placeholders_are_skipped(self) -> None:
        self.repo.write("greenfield/templates/docs/STYLE_GUIDE.md", "# S\n\n[x](../src/core/a.ts#L1)\n")
        self.assertEqual(self.lint_root_pages().errors, [])

    def test_root_pages_get_no_other_check(self) -> None:
        self.repo.write("spec/Long.md", "# L\n" + "line\n" * 600)
        self.assertEqual(self.lint_root_pages().errors, [])


# --- The link rule --------------------------------------------------------------------------------------


class LinkTests(FixtureTests):
    def test_a_relative_link_to_an_existing_file_resolves(self) -> None:
        self.repo.write("docs/target.md", "# Target\n")
        self.repo.write("docs/source.md", "See [target](target.md).\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_relative_link_to_a_missing_file_is_reported(self) -> None:
        source = self.repo.write("docs/source.md", "See [gone](nowhere.md).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn(str(source), errors[0])
        self.assertIn("no such file", errors[0])

    def test_a_link_that_climbs_out_of_the_root_is_reported(self) -> None:
        self.repo.write("docs/source.md", "See [out](../../../../etc/passwd).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("leaves", errors[0])

    def test_a_link_can_climb_out_of_the_recipe_folders_but_stay_in_the_root(self) -> None:
        self.repo.write("greenfield/README.md", "# Greenfield\n")
        self.repo.write("audit/checks/source.md", "See [greenfield](../../greenfield/README.md).\n")
        self.assertEqual(self.lint().errors, [])

    def test_an_external_link_is_never_checked(self) -> None:
        self.repo.write("docs/source.md", "See [spec](https://example.invalid/nowhere).\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_heading_anchor_resolves(self) -> None:
        self.repo.write("docs/target.md", "# Output files\n")
        self.repo.write("docs/source.md", "See [files](target.md#output-files).\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_heading_anchor_with_no_matching_heading_is_reported(self) -> None:
        self.repo.write("docs/target.md", "# Output files\n")
        self.repo.write("docs/source.md", "See [files](target.md#input-files).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("matches no heading", errors[0])

    def test_a_same_file_anchor_resolves(self) -> None:
        self.repo.write(
            "docs/source.md",
            "# Top\n\nSee [top](#top) again.\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_backticks_and_an_em_dash_slugify_like_github(self) -> None:
        # "REQ-SH-022 -- `check` composes" style heading: the backticked word survives, the double space
        # either side of the dropped em dash gives a double hyphen (confirmed against this repository's own
        # anchors in test_the_projects_own_docs_are_clean).
        self.repo.write("docs/target.md", "### REQ-SH-022 — `check` composes the verbs\n")
        self.repo.write(
            "docs/source.md",
            "See [req](target.md#req-sh-022--check-composes-the-verbs).\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_a_line_range_anchor_in_range_resolves(self) -> None:
        self.repo.write("audit/tools/thing.py", "\n".join(f"line {n}" for n in range(1, 11)) + "\n")
        self.repo.write("docs/source.md", "See [thing](../audit/tools/thing.py#L2-L5).\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_line_range_anchor_out_of_range_is_reported(self) -> None:
        self.repo.write("audit/tools/thing.py", "one line\n")
        self.repo.write("docs/source.md", "See [thing](../audit/tools/thing.py#L1-L99).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("out of range", errors[0])

    def test_a_malformed_line_anchor_is_reported(self) -> None:
        self.repo.write("audit/tools/thing.py", "one line\n")
        self.repo.write("docs/source.md", "See [thing](../audit/tools/thing.py#notaline).\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("not L<n>", errors[0])

    def test_a_placeholder_link_under_docs_templates_is_skipped(self) -> None:
        self.repo.write(
            "docs/templates/architecture-doc-template.md",
            "> **Related ADRs:** [ADR-NNNN](../architecture/adrs/NNNN-title.md)\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_a_link_inside_a_fenced_code_block_is_not_checked(self) -> None:
        self.repo.write(
            "docs/source.md",
            "```text\nSee [gone](nowhere.md).\n```\n",
        )
        self.assertEqual(self.lint().errors, [])


# --- The frontmatter rule --------------------------------------------------------------------------------


class FrontmatterTests(FixtureTests):
    def test_valid_frontmatter_passes(self) -> None:
        self.repo.write(
            "audit/SKILL.md",
            "---\nname: audit\ndescription: Audit a repository for agentic readiness.\n---\n\n# Audit\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_missing_frontmatter_is_reported(self) -> None:
        self.repo.write("audit/SKILL.md", "# Audit\n\nNo frontmatter here.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("frontmatter", errors[0])

    def test_an_uppercase_name_is_reported(self) -> None:
        self.repo.write(
            "audit/SKILL.md",
            "---\nname: Audit\ndescription: Audit a repository.\n---\n\n# Audit\n",
        )
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("lowercase", errors[0])

    def test_a_name_over_64_characters_is_reported(self) -> None:
        long_name = "a" * 65
        self.repo.write(
            f"audit/{long_name}/SKILL.md",
            f"---\nname: {long_name}\ndescription: Audit a repository.\n---\n\n# Audit\n",
        )
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("64 characters", errors[0])

    def test_a_name_that_does_not_match_its_folder_is_reported(self) -> None:
        self.repo.write(
            "audit/SKILL.md",
            "---\nname: implement\ndescription: Audit a repository.\n---\n\n# Audit\n",
        )
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("must match its folder", errors[0])

    def test_a_missing_description_is_reported(self) -> None:
        self.repo.write("audit/SKILL.md", "---\nname: audit\n---\n\n# Audit\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("no 'description'", errors[0])

    def test_a_description_over_1024_characters_is_reported(self) -> None:
        self.repo.write(
            "audit/SKILL.md",
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
        self.repo.write("audit/SKILL.md", body + "\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_skill_md_over_the_budget_is_reported(self) -> None:
        body = "---\nname: audit\ndescription: Audit a repository.\n---\n\n" + "\n".join(
            f"line {n}" for n in range(rl.LINE_BUDGET + 5)
        )
        self.repo.write("audit/SKILL.md", body + "\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("the budget is", errors[0])

    def test_a_check_family_file_over_the_budget_is_reported(self) -> None:
        body = "\n".join(f"line {n}" for n in range(rl.LINE_BUDGET + 5))
        self.repo.write("audit/checks/01-discovery-and-index.md", body + "\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("01-discovery-and-index.md", errors[0])

    def test_a_long_file_outside_audit_checks_is_not_budgeted(self) -> None:
        body = "\n".join(f"line {n}" for n in range(rl.LINE_BUDGET + 5))
        self.repo.write("docs/01-not-a-check-family-file.md", body + "\n")
        self.assertEqual(self.lint().errors, [])


# --- The tool-reference rule ---------------------------------------------------------------------------------

GOOD_TOOL = (
    "import json, sys\n"
    "print(json.dumps({'tool': 'thing', 'version': '0.1.0', 'ok': True, 'data': {}, "
    "'warnings': [], 'truncated': False}))\n"
)
BROKEN_EXIT_TOOL = "import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n"
INVALID_JSON_TOOL = "print('not json')\n"
NOT_OK_TOOL = (
    "import json\n"
    "print(json.dumps({'tool': 'thing', 'version': '0.1.0', 'ok': False, 'data': {}, "
    "'warnings': [], 'truncated': False}))\n"
)
SLOW_TOOL = "import time\ntime.sleep(5)\n"
COUNTING_TOOL = (
    "import json\n"
    "from pathlib import Path\n"
    "counter = Path(__file__).parent / 'calls.txt'\n"
    "counter.write_text(str(int(counter.read_text()) + 1) if counter.exists() else '1')\n"
    "print(json.dumps({'tool': 'thing', 'version': '0.1.0', 'ok': True, 'data': {}, "
    "'warnings': [], 'truncated': False}))\n"
)


class ToolReferenceTests(FixtureTests):
    def test_a_tool_that_exists_and_describes_itself_passes(self) -> None:
        self.write_tool("thing", GOOD_TOOL)
        self.repo.write("docs/source.md", "Run `audit/tools/thing.py`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_missing_tool_is_reported(self) -> None:
        self.repo.write("docs/source.md", "Run `audit/tools/gone.py`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])

    def test_a_tool_that_exits_nonzero_on_describe_is_reported(self) -> None:
        self.write_tool("thing", BROKEN_EXIT_TOOL)
        self.repo.write("docs/source.md", "Run `audit/tools/thing.py`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("exited 3: boom", errors[0])

    def test_a_tool_that_prints_invalid_json_is_reported(self) -> None:
        self.write_tool("thing", INVALID_JSON_TOOL)
        self.repo.write("docs/source.md", "Run `audit/tools/thing.py`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("no valid JSON envelope", errors[0])

    def test_a_tool_that_says_ok_false_on_describe_is_reported(self) -> None:
        self.write_tool("thing", NOT_OK_TOOL)
        self.repo.write("docs/source.md", "Run `audit/tools/thing.py`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("printed ok: False", errors[0])

    def test_a_tool_that_does_not_finish_in_time_is_reported(self) -> None:
        self.write_tool("thing", SLOW_TOOL)
        self.repo.write("docs/source.md", "Run `audit/tools/thing.py`.\n")
        errors = self.lint(describe_timeout=0.2).errors
        self.assertEqual(len(errors), 1)
        self.assertIn("did not finish within 0.2s", errors[0])

    def test_a_reference_inside_a_fenced_synopsis_is_still_checked(self) -> None:
        self.repo.write(
            "docs/source.md",
            "```text\npython3 audit/tools/gone.py <target>\n```\n",
        )
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])

    def test_a_tbd_line_is_skipped(self) -> None:
        self.repo.write(
            "docs/source.md",
            "- TBD: `python3 audit/tools/gone.py show` does the thing.\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_a_bare_tools_reference_with_no_prefix_is_never_checked(self) -> None:
        self.repo.write("docs/source.md", "Run `tools/gone.py`, someone else's tool.\n")
        self.assertEqual(self.lint().errors, [])

    def test_an_implement_tool_resolves_in_implement_tools(self) -> None:
        self.write_tool("thing", GOOD_TOOL, folder="implement/tools")
        self.repo.write(
            "implement/SKILL.md", "---\nname: implement\ndescription: x\n---\n\n`implement/tools/thing.py`\n"
        )
        self.assertEqual(self.lint().errors, [])

    def test_a_tool_cited_under_the_wrong_folder_is_reported(self) -> None:
        self.write_tool("thing", GOOD_TOOL, folder="implement/tools")
        self.repo.write("docs/source.md", "Run `audit/tools/thing.py`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("the tool audit/tools/thing.py does not exist", errors[0])

    def test_another_folders_tools_ending_in_audit_are_never_checked(self) -> None:
        self.repo.write(
            "docs/source.md",
            "Run `audit/engine/tools/build.py` or `deterministic-audit/tools/build.py`, the engine's own.\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_a_tool_cited_twice_is_described_only_once(self) -> None:
        tool = self.write_tool("thing", COUNTING_TOOL)
        self.repo.write(
            "docs/a.md",
            "Run `audit/tools/thing.py`.\n",
        )
        self.repo.write(
            "docs/b.md",
            "Run `audit/tools/thing.py`.\n",
        )
        self.assertEqual(self.lint().errors, [])
        self.assertEqual((tool.parent / "calls.txt").read_text(encoding="utf-8"), "1")


# --- The check, requirement and playbook reference rules -----------------------------------------------------


def a_check(check_id: str, playbooks: Sequence[str] = ()) -> dict[str, Any]:
    return {"id": check_id, "playbooks": list(playbooks)}


class CatalogueReferenceTests(FixtureTests):
    def test_a_known_check_id_passes(self) -> None:
        self.repo.write_catalogue([a_check("CMD-01")])
        self.repo.write("docs/source.md", "See `CMD-01`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_an_unknown_check_id_is_reported(self) -> None:
        self.repo.write_catalogue([a_check("CMD-01")])
        self.repo.write("docs/source.md", "See `CMD-99`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("the check 'CMD-99' is not in catalogue.json", errors[0])

    def test_a_check_id_inside_a_fenced_json_example_is_still_checked(self) -> None:
        self.repo.write_catalogue([a_check("SEC-02")])
        self.repo.write("docs/source.md", '```json\n{"check": "SEC-99"}\n```\n')
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("'SEC-99'", errors[0])

    def test_a_requirement_id_like_fragment_of_another_check_family_is_not_a_false_positive(self) -> None:
        # REQ-SH-022 must not look like a check in family "SH".
        self.repo.write_catalogue([a_check("CMD-01")])
        self.repo.write_requirements(["REQ-SH-022"])
        self.repo.write("docs/source.md", "See `REQ-SH-022`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_known_requirement_id_passes(self) -> None:
        self.repo.write_requirements(["REQ-SH-022"])
        self.repo.write("docs/source.md", "See `REQ-SH-022`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_an_unknown_requirement_id_is_reported(self) -> None:
        self.repo.write_requirements(["REQ-SH-022"])
        self.repo.write("docs/source.md", "See `REQ-SH-999`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("the requirement 'REQ-SH-999' is not in spec/readiness-requirements.md", errors[0])

    def test_a_known_playbook_cited_in_prose_passes(self) -> None:
        self.repo.write_catalogue([a_check("CON-04", playbooks=["add-deny-rules"])])
        self.repo.write("docs/source.md", "Playbook `add-deny-rules` fixes it.\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_known_playbook_cited_in_json_passes(self) -> None:
        self.repo.write_catalogue([a_check("CON-04", playbooks=["add-deny-rules"])])
        self.repo.write(
            "docs/source.md",
            '```json\n{"remediation": {"playbook": "add-deny-rules"}}\n```\n',
        )
        self.assertEqual(self.lint().errors, [])

    def test_an_unknown_playbook_is_reported(self) -> None:
        self.repo.write_catalogue([a_check("CON-04", playbooks=["add-deny-rules"])])
        self.repo.write("docs/source.md", "Playbook `bogus-playbook` fixes it.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("the catalogue names no playbook 'bogus-playbook'", errors[0])

    def test_a_playbook_with_no_file_yet_still_passes(self) -> None:
        # schema/SCHEMA.md rule 2: the catalogue, not the implement/playbooks/ folder, is what "exists" means.
        self.repo.write_catalogue([a_check("CON-04", playbooks=["add-deny-rules"])])
        self.assertFalse((self.repo.root / "implement" / "playbooks").exists())
        self.repo.write("docs/source.md", "Playbook `add-deny-rules` fixes it.\n")
        self.assertEqual(self.lint().errors, [])

    def test_no_catalogue_or_requirements_file_skips_these_checks_without_crashing(self) -> None:
        self.repo.write("docs/source.md", "See `CMD-99` and `REQ-SH-999`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_the_engine_is_never_checked_against_the_catalogue(self) -> None:
        self.repo.write_catalogue([a_check("CMD-01")])
        self.repo.write("audit/engine/docs/source.md", "See `CMD-99`, the engine's own.\n")
        self.assertEqual(self.lint().errors, [])


# --- The tool contract -------------------------------------------------------------------------------------


class ToolContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_describe_prints_the_manifest(self) -> None:
        code, envelope, _ = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["name"], "recipe_lint")
        self.assertIn("CATALOGUE.md", envelope["data"]["writes"])

    def test_a_root_without_audit_is_a_usage_error(self) -> None:
        (self.root / "docs").mkdir()
        (self.root / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
        code, envelope, _ = call([str(self.root)])
        self.assertEqual(code, 1)
        self.assertIs(envelope["ok"], False)
        self.assertIn("has no audit/ directory", envelope["data"]["error"])

    def test_a_clean_repo_exits_0_and_writes_nothing(self) -> None:
        (self.root / "audit").mkdir()
        (self.root / "audit" / "a.md").write_text("# A\n", encoding="utf-8")
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        code, envelope, err = call([str(self.root)])
        after = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        self.assertEqual(code, 0)
        self.assertIs(envelope["ok"], True)
        self.assertEqual(envelope["data"], {"root": str(self.root), "files": 1})
        self.assertIn("clean (1 files", err)
        self.assertEqual(before, after)

    def test_broken_links_exit_2_with_every_error_listed(self) -> None:
        (self.root / "audit").mkdir()
        (self.root / "implement").mkdir()
        (self.root / "audit" / "a.md").write_text("[gone](nowhere.md)\n", encoding="utf-8")
        (self.root / "implement" / "b.md").write_text("[gone](elsewhere.md)\n", encoding="utf-8")
        code, envelope, err = call([str(self.root)])
        self.assertEqual(code, 2)
        self.assertIs(envelope["ok"], False)
        self.assertEqual(len(envelope["data"]["errors"]), 2)
        self.assertIn("2 problems in 2 files", err)


# --- The tool catalogue ---------------------------------------------------------------------------------


def tool_script(name: str, *, synopsis: Sequence[str] = ("thing.py",), writes: str = "nothing") -> str:
    """Source for a fake tool whose `--describe` prints a full manifest, not just the bare envelope."""
    manifest = {
        "name": name,
        "version": "0.1.0",
        "summary": f"A test tool named {name}.",
        "synopsis": list(synopsis),
        "writes": writes,
        "network": False,
        "writes_inside_target": False,
        "exit_codes": {"0": "ok"},
    }
    envelope = {"tool": name, "version": "0.1.0", "ok": True, "data": manifest, "warnings": [], "truncated": False}
    return f"import json\nprint(json.dumps({envelope!r}))\n"


class CatalogueGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "audit" / "tools").mkdir(parents=True)

    def write_tool(self, name: str, source: str, folder: str = "audit/tools") -> Path:
        path = self.root / folder / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def catalogue_path(self) -> Path:
        return self.root / "audit" / "tools" / "CATALOGUE.md"

    def test_write_catalogue_generates_one_section_per_tool_sorted_by_name(self) -> None:
        self.write_tool("zeta", tool_script("zeta"))
        self.write_tool("alpha", tool_script("alpha"))
        code, envelope, _ = call([str(self.root), "--write-catalogue"])
        self.assertEqual(code, 0)
        self.assertIs(envelope["ok"], True)
        self.assertEqual(envelope["data"]["tools"], 2)
        text = self.catalogue_path().read_text(encoding="utf-8")
        self.assertLess(text.index("## alpha.py"), text.index("## zeta.py"))

    def test_write_catalogue_lists_the_audit_tools_then_the_implement_tools(self) -> None:
        self.write_tool("zeta", tool_script("zeta"))
        self.write_tool("alpha", tool_script("alpha"), folder="implement/tools")
        self.write_tool("beta", tool_script("beta"), folder="implement/tools")
        self.write_tool("_helper", "raise SystemExit(1)\n", folder="implement/tools")
        code, envelope, _ = call([str(self.root), "--write-catalogue"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["tools"], 3)
        text = self.catalogue_path().read_text(encoding="utf-8")
        self.assertLess(text.index("## zeta.py"), text.index("## alpha.py"))
        self.assertLess(text.index("## alpha.py"), text.index("## beta.py"))
        self.assertFalse((self.root / "implement" / "tools" / "CATALOGUE.md").exists())

    def test_a_new_implement_tool_makes_the_catalogue_stale(self) -> None:
        self.write_tool("thing", tool_script("thing"))
        call([str(self.root), "--write-catalogue"])
        self.write_tool("other", tool_script("other"), folder="implement/tools")
        code, envelope, _ = call([str(self.root)])
        self.assertEqual(code, 2)
        self.assertIn("CATALOGUE.md is stale", envelope["data"]["errors"][0])

    def test_write_catalogue_is_byte_stable_across_runs(self) -> None:
        self.write_tool("thing", tool_script("thing"))
        call([str(self.root), "--write-catalogue"])
        first = self.catalogue_path().read_text(encoding="utf-8")
        call([str(self.root), "--write-catalogue"])
        second = self.catalogue_path().read_text(encoding="utf-8")
        self.assertEqual(first, second)

    def test_write_catalogue_skips_a_leading_underscore_helper(self) -> None:
        self.write_tool("thing", tool_script("thing"))
        self.write_tool("_helper", "raise SystemExit(1)\n")
        code, envelope, _ = call([str(self.root), "--write-catalogue"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["tools"], 1)

    def test_write_catalogue_reports_a_tool_that_fails_describe(self) -> None:
        self.write_tool("thing", BROKEN_EXIT_TOOL)
        code, envelope, _ = call([str(self.root), "--write-catalogue"])
        self.assertEqual(code, 2)
        self.assertIs(envelope["ok"], False)
        self.assertIn("exited 3: boom", envelope["data"]["errors"][0])
        self.assertFalse(self.catalogue_path().exists())

    def test_a_missing_catalogue_fails_the_lint(self) -> None:
        self.write_tool("thing", tool_script("thing"))
        code, envelope, _ = call([str(self.root)])
        self.assertEqual(code, 2)
        self.assertIn("CATALOGUE.md is missing", envelope["data"]["errors"][0])

    def test_a_stale_catalogue_fails_the_lint(self) -> None:
        self.write_tool("thing", tool_script("thing"))
        call([str(self.root), "--write-catalogue"])
        self.write_tool("thing", tool_script("thing", writes="something else now"))
        code, envelope, _ = call([str(self.root)])
        self.assertEqual(code, 2)
        self.assertIn("CATALOGUE.md is stale", envelope["data"]["errors"][0])

    def test_a_fresh_catalogue_lints_clean(self) -> None:
        self.write_tool("thing", tool_script("thing"))
        call([str(self.root), "--write-catalogue"])
        code, envelope, _ = call([str(self.root)])
        self.assertEqual(code, 0)
        self.assertIs(envelope["ok"], True)

    def test_no_tools_directory_at_all_skips_the_catalogue_check(self) -> None:
        shutil.rmtree(self.root / "audit" / "tools")
        code, envelope, _ = call([str(self.root)])
        self.assertEqual(code, 0)
        self.assertIs(envelope["ok"], True)


# --- This project's own documentation -----------------------------------------------------------------------


class SelfTests(unittest.TestCase):
    def test_the_projects_own_docs_are_clean(self) -> None:
        files = rl.find_markdown(REPO_ROOT)
        self.assertGreater(len(files), 100)
        outcome = rl.lint(REPO_ROOT, files)
        self.assertEqual(outcome.errors, [])


if __name__ == "__main__":
    unittest.main()
