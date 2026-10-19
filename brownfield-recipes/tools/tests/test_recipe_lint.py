# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The recipe linter: each of its eight rules (links, SKILL.md frontmatter, size, tool, check, requirement,
playbook references and the tool catalogue) has a fixture that passes it and one that breaks it, and the tool
honours the contract (envelope, exit codes, nothing written unless `--write-catalogue` is given).

A fixture is a small repository tree built in a temporary folder, with its own `brownfield-recipes/` so the tool
sees a real target. The project's own documentation is linted too, as the standing proof that the rule set the
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

    def write_catalogue(self, checks: list[dict[str, Any]]) -> Path:
        return self.write(
            "brownfield-recipes/catalogue.json",
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

    def write_tool(self, name: str, source: str) -> Path:
        return self.repo.write(f"brownfield-recipes/tools/{name}.py", source)


# --- The markdown sweep ----------------------------------------------------------------------------------


class FindMarkdownTests(FixtureTests):
    def test_a_file_under_dist_is_never_swept(self) -> None:
        self.repo.write("brownfield-recipes/docs/reference/kept.md", "# Kept\n")
        self.repo.write(
            "brownfield-recipes/dist/skills/agentic-readiness-audit/SKILL.md",
            "---\nname: audit\ndescription: x\n---\n\n[broken](../does-not-exist.md)\n",
        )
        files = rl.find_markdown(self.repo.root)
        relative = {path.relative_to(self.repo.root).as_posix() for path in files}
        self.assertIn("brownfield-recipes/docs/reference/kept.md", relative)
        self.assertFalse(any(path.startswith("brownfield-recipes/dist/") for path in relative))

    def test_a_broken_link_under_dist_does_not_fail_the_lint(self) -> None:
        self.repo.write(
            "brownfield-recipes/dist/skills/agentic-readiness-audit/SKILL.md",
            "---\nname: audit\ndescription: x\n---\n\n[broken](../does-not-exist.md)\n",
        )
        outcome = self.lint()
        self.assertEqual(outcome.errors, [])


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
        self.repo.write("brownfield-recipes/docs/source.md", "Run `brownfield-recipes/tools/thing.py`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_missing_tool_is_reported(self) -> None:
        self.repo.write("brownfield-recipes/docs/source.md", "Run `brownfield-recipes/tools/gone.py`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])

    def test_a_tool_that_exits_nonzero_on_describe_is_reported(self) -> None:
        self.write_tool("thing", BROKEN_EXIT_TOOL)
        self.repo.write("brownfield-recipes/docs/source.md", "Run `brownfield-recipes/tools/thing.py`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("exited 3: boom", errors[0])

    def test_a_tool_that_prints_invalid_json_is_reported(self) -> None:
        self.write_tool("thing", INVALID_JSON_TOOL)
        self.repo.write("brownfield-recipes/docs/source.md", "Run `brownfield-recipes/tools/thing.py`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("no valid JSON envelope", errors[0])

    def test_a_tool_that_says_ok_false_on_describe_is_reported(self) -> None:
        self.write_tool("thing", NOT_OK_TOOL)
        self.repo.write("brownfield-recipes/docs/source.md", "Run `brownfield-recipes/tools/thing.py`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("printed ok: False", errors[0])

    def test_a_tool_that_does_not_finish_in_time_is_reported(self) -> None:
        self.write_tool("thing", SLOW_TOOL)
        self.repo.write("brownfield-recipes/docs/source.md", "Run `brownfield-recipes/tools/thing.py`.\n")
        errors = self.lint(describe_timeout=0.2).errors
        self.assertEqual(len(errors), 1)
        self.assertIn("did not finish within 0.2s", errors[0])

    def test_a_reference_inside_a_fenced_synopsis_is_still_checked(self) -> None:
        self.repo.write(
            "brownfield-recipes/docs/source.md",
            "```text\npython3 brownfield-recipes/tools/gone.py <target>\n```\n",
        )
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])

    def test_a_tbd_line_is_skipped(self) -> None:
        self.repo.write(
            "brownfield-recipes/docs/source.md",
            "- TBD: `python3 brownfield-recipes/tools/gone.py show` does the thing.\n",
        )
        self.assertEqual(self.lint().errors, [])

    def test_a_bare_tools_reference_with_no_prefix_is_never_checked(self) -> None:
        self.repo.write("brownfield-recipes/docs/source.md", "Run `tools/gone.py`, someone else's tool.\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_tool_cited_twice_is_described_only_once(self) -> None:
        tool = self.write_tool("thing", COUNTING_TOOL)
        self.repo.write(
            "brownfield-recipes/docs/a.md",
            "Run `brownfield-recipes/tools/thing.py`.\n",
        )
        self.repo.write(
            "brownfield-recipes/docs/b.md",
            "Run `brownfield-recipes/tools/thing.py`.\n",
        )
        self.assertEqual(self.lint().errors, [])
        self.assertEqual((tool.parent / "calls.txt").read_text(encoding="utf-8"), "1")


# --- The check, requirement and playbook reference rules -----------------------------------------------------


def a_check(check_id: str, playbooks: Sequence[str] = ()) -> dict[str, Any]:
    return {"id": check_id, "playbooks": list(playbooks)}


class CatalogueReferenceTests(FixtureTests):
    def test_a_known_check_id_passes(self) -> None:
        self.repo.write_catalogue([a_check("CMD-01")])
        self.repo.write("brownfield-recipes/docs/source.md", "See `CMD-01`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_an_unknown_check_id_is_reported(self) -> None:
        self.repo.write_catalogue([a_check("CMD-01")])
        self.repo.write("brownfield-recipes/docs/source.md", "See `CMD-99`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("the check 'CMD-99' is not in catalogue.json", errors[0])

    def test_a_check_id_inside_a_fenced_json_example_is_still_checked(self) -> None:
        self.repo.write_catalogue([a_check("SEC-02")])
        self.repo.write("brownfield-recipes/docs/source.md", '```json\n{"check": "SEC-99"}\n```\n')
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("'SEC-99'", errors[0])

    def test_a_requirement_id_like_fragment_of_another_check_family_is_not_a_false_positive(self) -> None:
        # REQ-SH-022 must not look like a check in family "SH".
        self.repo.write_catalogue([a_check("CMD-01")])
        self.repo.write_requirements(["REQ-SH-022"])
        self.repo.write("brownfield-recipes/docs/source.md", "See `REQ-SH-022`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_known_requirement_id_passes(self) -> None:
        self.repo.write_requirements(["REQ-SH-022"])
        self.repo.write("brownfield-recipes/docs/source.md", "See `REQ-SH-022`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_an_unknown_requirement_id_is_reported(self) -> None:
        self.repo.write_requirements(["REQ-SH-022"])
        self.repo.write("brownfield-recipes/docs/source.md", "See `REQ-SH-999`.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("the requirement 'REQ-SH-999' is not in spec/readiness-requirements.md", errors[0])

    def test_a_known_playbook_cited_in_prose_passes(self) -> None:
        self.repo.write_catalogue([a_check("CON-04", playbooks=["add-deny-rules"])])
        self.repo.write("brownfield-recipes/docs/source.md", "Playbook `add-deny-rules` fixes it.\n")
        self.assertEqual(self.lint().errors, [])

    def test_a_known_playbook_cited_in_json_passes(self) -> None:
        self.repo.write_catalogue([a_check("CON-04", playbooks=["add-deny-rules"])])
        self.repo.write(
            "brownfield-recipes/docs/source.md",
            '```json\n{"remediation": {"playbook": "add-deny-rules"}}\n```\n',
        )
        self.assertEqual(self.lint().errors, [])

    def test_an_unknown_playbook_is_reported(self) -> None:
        self.repo.write_catalogue([a_check("CON-04", playbooks=["add-deny-rules"])])
        self.repo.write("brownfield-recipes/docs/source.md", "Playbook `bogus-playbook` fixes it.\n")
        errors = self.lint().errors
        self.assertEqual(len(errors), 1)
        self.assertIn("the catalogue names no playbook 'bogus-playbook'", errors[0])

    def test_a_playbook_with_no_file_yet_still_passes(self) -> None:
        # schema/SCHEMA.md rule 2: the catalogue, not the implement/playbooks/ folder, is what "exists" means.
        self.repo.write_catalogue([a_check("CON-04", playbooks=["add-deny-rules"])])
        self.assertFalse((self.repo.root / "brownfield-recipes" / "implement").exists())
        self.repo.write("brownfield-recipes/docs/source.md", "Playbook `add-deny-rules` fixes it.\n")
        self.assertEqual(self.lint().errors, [])

    def test_no_catalogue_or_requirements_file_skips_these_checks_without_crashing(self) -> None:
        self.repo.write("brownfield-recipes/docs/source.md", "See `CMD-99` and `REQ-SH-999`.\n")
        self.assertEqual(self.lint().errors, [])

    def test_deterministic_audit_is_never_checked_against_the_catalogue(self) -> None:
        self.repo.write_catalogue([a_check("CMD-01")])
        self.repo.write("brownfield-recipes/deterministic-audit/docs/source.md", "See `CMD-99`, the engine's own.\n")
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
        (self.root / "brownfield-recipes" / "tools").mkdir(parents=True)

    def write_tool(self, name: str, source: str) -> Path:
        path = self.root / "brownfield-recipes" / "tools" / f"{name}.py"
        path.write_text(source, encoding="utf-8")
        return path

    def catalogue_path(self) -> Path:
        return self.root / "brownfield-recipes" / "tools" / "CATALOGUE.md"

    def test_write_catalogue_generates_one_section_per_tool_sorted_by_name(self) -> None:
        self.write_tool("zeta", tool_script("zeta"))
        self.write_tool("alpha", tool_script("alpha"))
        code, envelope, _ = call([str(self.root), "--write-catalogue"])
        self.assertEqual(code, 0)
        self.assertIs(envelope["ok"], True)
        self.assertEqual(envelope["data"]["tools"], 2)
        text = self.catalogue_path().read_text(encoding="utf-8")
        self.assertLess(text.index("## alpha.py"), text.index("## zeta.py"))

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
        shutil.rmtree(self.root / "brownfield-recipes" / "tools")
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
