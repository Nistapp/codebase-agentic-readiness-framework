# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The facts tool's `instruction_files` section is the files the engine's `AGT-01` and `AGT-08` see, with no verdict.

The tests run the tool on fixtures and on small directories made in a temporary directory. They compare the section with
what `instruction_paths` gives the two checks, which they record by running the checks, and with values written out by
hand. Some tests pin what the engine does not see today, so that they fail on the day it does and the page that says so is
rewritten with them. Standard library only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest import mock

import _paths  # noqa: F401
import _common
import engine as launcher
import facts
from test_facts import RepoCase, call

FIXTURES = launcher.ENGINE_DIR / "tests" / "fixtures"
ENTRY_KEYS = ["path", "variant", "size_bytes"]

# fixture -> its files as `path`, `variant`, for the six AGT fixtures
AGT_FIXTURES: dict[str, list[tuple[str, str]]] = {
    "agt-01-marker-words-in-prose": [("AGENTS.md", "AGENTS.md")],
    "agt-01-mis-cased": [("agents.md", "agents.md")],
    "agt-01-missing": [],
    "agt-01-shadowed": [("AGENTS.md", "AGENTS.md"), ("AGENTS.override.md", "AGENTS.override.md")],
    "agt-01-stub": [("AGENTS.md", "AGENTS.md")],
    "agt-08-competitor": [("AGENTS.md", "AGENTS.md"), ("CLAUDE.md", "CLAUDE.md")],
}

# A file in a directory of its own -> the pattern of the variants table that names it.
FAMILIES: dict[str, str] = {
    "AGENTS.md": "AGENTS.md",
    "AGENT.md": "AGENT.md",
    ".rules": ".rules",
    "AGENTS.local.md": "AGENTS.local.md",
    "AGENTS.override.md": "AGENTS.override.md",
    "CLAUDE.md": "CLAUDE.md",
    "CLAUDE.local.md": "CLAUDE.local.md",
    ".claude/CLAUDE.md": "CLAUDE.md",
    ".junie/AGENTS.md": "AGENTS.md",
    "GEMINI.md": "GEMINI.md",
    ".cursorrules": ".cursorrules",
    ".windsurfrules": ".windsurfrules",
    ".clinerules": ".clinerules",
    ".roorules": ".roorules",
    ".roorules-code": ".roorules-*",
    ".augment-guidelines": ".augment-guidelines",
    ".goosehints": ".goosehints",
    ".voidrules": ".voidrules",
    "WARP.md": "WARP.md",
    "CRUSH.md": "CRUSH.md",
    "replit.md": "replit.md",
    "CONVENTIONS.md": "CONVENTIONS.md",
    "AmazonQ.md": "AmazonQ.md",
    "QWEN.md": "QWEN.md",
    "agents.md": "agents.md",
    ".cursor/rules/a/x.mdc": ".cursor/rules/**/*.mdc",
    ".claude/rules/a/x.md": ".claude/rules/**/*.md",
    ".github/instructions/a/x.instructions.md": ".github/instructions/**/*.instructions.md",
    ".devin/rules/a/x.md": ".devin/rules/**/*.md",
    ".windsurf/rules/a/x.md": ".windsurf/rules/**/*.md",
    ".continue/rules/a/x.md": ".continue/rules/**/*.md",
    ".amazonq/rules/a/x.md": ".amazonq/rules/**/*.md",
    ".kiro/steering/a/x.md": ".kiro/steering/**/*.md",
    ".trae/rules/a/x.md": ".trae/rules/**/*.md",
    ".augment/rules/a/x.md": ".augment/rules/**/*.md",
    ".junie/rules/x.md": ".junie/rules/*.md",
    ".clinerules/x": ".clinerules/**",
    ".cline/rules/x": ".cline/rules/**",
    ".roo/rules/x": ".roo/rules/**",
    ".roo/rules-code/x": ".roo/rules-*/**",
}

# The table's names with a folder and no star. A file of one of them is found by its own name when that is a name of
# the table too (the first three), and not found at all otherwise: the engine looks for such a name by its last part.
PLAIN_WITH_A_FOLDER = {
    ".claude/CLAUDE.md",
    ".claude/AGENTS.md",
    ".junie/AGENTS.md",
    ".devin/global_rules.md",
    ".gemini/styleguide.md",
    ".github/copilot-instructions.md",
    ".idx/airules.md",
    ".junie/guidelines.md",
    ".junie/playbook.md",
}

# What the engine does not see today, though its table names it (Q36): each file, alone in its directory.
NOT_SEEN = [
    ".devin/global_rules.md",
    ".gemini/styleguide.md",
    ".github/copilot-instructions.md",
    ".idx/airules.md",
    ".junie/guidelines.md",
    ".junie/playbook.md",
    ".amazonq/rules/x.md",
    ".augment/rules/x.md",
    ".claude/rules/x.md",
    ".continue/rules/x.md",
    ".cursor/rules/x.mdc",
    ".devin/rules/x.md",
    ".github/instructions/x.instructions.md",
    ".kiro/steering/x.md",
    ".trae/rules/x.md",
    ".windsurf/rules/x.md",
    "sub/.cursor/rules/a/x.mdc",
]


class InstructionCase(RepoCase):
    def setUp(self) -> None:
        super().setUp()
        self.cases = 0

    def directory(self, files: dict[str, str | bytes]) -> Path:
        """A new plain directory holding `files`."""
        self.cases += 1
        root = self.root / f"case-{self.cases}"
        root.mkdir()
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        return root

    def document(self, target: Path, *extra: str) -> dict[str, Any]:
        out = self.folder / f"{target.name}.json"
        out.unlink(missing_ok=True)
        self.run_ok(*extra, target=target, out=out)
        document: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
        return document

    def listed(self, target: Path, *extra: str) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = self.document(target, *extra)["instruction_files"]
        return files

    def engine_sees(self, target: Path) -> set[str]:
        scan = facts.engine_module("audit.scan")
        agt = facts.engine_module("audit.rules.checks.agt")
        return set(agt.instruction_paths(scan.build_inventory(target)))

    def seen_by(self, check: str, target: Path) -> set[str]:
        """The set that `check` (`AGT-01` or `AGT-08`) gets from `instruction_paths`, recorded while the check runs."""
        scan = facts.engine_module("audit.scan")
        agt = facts.engine_module("audit.rules.checks.agt")
        spec = facts.engine_module("audit.rules.registry").REGISTRY_BY_ID[check]
        real = agt.instruction_paths
        answers: list[set[str]] = []

        def record(inventory: Any) -> set[str]:
            found: set[str] = real(inventory)
            answers.append(set(found))
            return found

        with mock.patch.object(agt, "instruction_paths", record):
            getattr(agt, "check_" + check.replace("-", "").lower())(
                spec=spec,
                target=None,
                inventory=scan.build_inventory(target),
                stack=None,
                components=None,
                session=None,
            )
        self.assertEqual(len(answers), 1, check)
        return answers[0]


class AcceptanceTests(InstructionCase):
    def test_the_files_are_the_ones_agt_01_and_agt_08_see_on_the_six_agt_fixtures(self) -> None:
        for name, files in AGT_FIXTURES.items():
            with self.subTest(fixture=name):
                target = FIXTURES / name
                document = self.document(target)
                expected = [
                    {"path": path, "variant": variant, "size_bytes": (target / path).stat().st_size}
                    for path, variant in files
                ]
                self.assertEqual(document["instruction_files"], expected)
                self.assertEqual(document["caps"]["instruction_files"], {"limit": 25, "omitted": 0})
                paths = {entry["path"] for entry in expected}
                self.assertEqual(self.seen_by("AGT-01", target), paths)
                self.assertEqual(self.seen_by("AGT-08", target), paths)

    def test_every_fixture_gives_the_engines_own_set(self) -> None:
        names = sorted(path.name for path in FIXTURES.iterdir() if path.is_dir())
        with_files = 0
        for name in names:
            with self.subTest(fixture=name):
                found = [entry["path"] for entry in self.listed(FIXTURES / name)]
                self.assertEqual(found, sorted(self.engine_sees(FIXTURES / name)))
                with_files += bool(found)
        self.assertGreater(len(names), 80)
        self.assertGreater(with_files, 10)

    def test_no_field_is_a_verdict(self) -> None:
        target = self.directory({"AGENTS.md": "x\n", "AGENTS.override.md": "", "CLAUDE.md": "x\n"})
        document = self.document(target)
        self.assertEqual([list(entry) for entry in document["instruction_files"]], [ENTRY_KEYS] * 3)
        self.assertEqual(
            [(entry["path"], entry["variant"], entry["size_bytes"]) for entry in document["instruction_files"]],
            [
                ("AGENTS.md", "AGENTS.md", 2),
                ("AGENTS.override.md", "AGENTS.override.md", 0),
                ("CLAUDE.md", "CLAUDE.md", 2),
            ],
        )
        text = (self.folder / f"{target.name}.json").read_text(encoding="utf-8")
        for word in ("stub", "canonical", "shadow", "competitor", "verdict"):
            self.assertNotIn(word, text)

    def test_the_set_is_whatever_instruction_paths_says_and_the_tool_searches_for_nothing(self) -> None:
        target = self.directory({"AGENTS.md": "x\n", "CLAUDE.md": "x\n"})
        agt = facts.engine_module("audit.rules.checks.agt")
        with mock.patch.object(agt, "instruction_paths", return_value={"CLAUDE.md"}):
            self.assertEqual([entry["path"] for entry in self.listed(target)], ["CLAUDE.md"])


class FamilyTests(InstructionCase):
    def test_each_family_in_the_table_is_listed_with_the_pattern_that_names_it(self) -> None:
        for rel, pattern in FAMILIES.items():
            with self.subTest(file=rel):
                target = self.directory({rel: "x\n"})
                self.assertEqual(self.listed(target), [{"path": rel, "variant": pattern, "size_bytes": 2}])
                self.assertEqual(self.engine_sees(target), {rel})

    def test_the_cases_name_every_pattern_of_the_table_but_the_plain_names_with_a_folder(self) -> None:
        variants = facts.engine_module("audit.rules.variants")
        patterns = {pattern for harness in variants.HARNESSES for pattern in harness.paths}
        patterns |= set(variants.CANONICAL_PATHS) | set(variants.NON_CANONICAL_ALIASES) | set(variants.OVERRIDE_PATHS)
        self.assertEqual(
            {pattern for pattern in patterns if "*" not in pattern and "/" in pattern}, PLAIN_WITH_A_FOLDER
        )
        self.assertEqual(patterns - PLAIN_WITH_A_FOLDER, set(FAMILIES.values()))

    def test_a_nested_file_is_listed_by_its_name_and_the_list_is_sorted_by_code_point(self) -> None:
        names = ["docs/CLAUDE.md", "a/AGENTS.md", "Z/AGENTS.md", "AGENTS.md", "B/CLAUDE.md", "sub/.cursorrules"]
        target = self.directory(dict.fromkeys(names, "x\n"))
        self.assertEqual(
            [(entry["path"], entry["variant"]) for entry in self.listed(target)],
            [
                ("AGENTS.md", "AGENTS.md"),
                ("B/CLAUDE.md", "CLAUDE.md"),
                ("Z/AGENTS.md", "AGENTS.md"),
                ("a/AGENTS.md", "AGENTS.md"),
                ("docs/CLAUDE.md", "CLAUDE.md"),
                ("sub/.cursorrules", ".cursorrules"),
            ],
        )

    def test_a_name_is_listed_only_in_the_case_the_table_spells_it(self) -> None:
        for rel in ("Agents.md", "AGENTS.MD", "claude.md", "Claude.md", "gemini.md", "Warp.md"):
            with self.subTest(file=rel):
                self.assertEqual(self.listed(self.directory({rel: "x\n"})), [])
        self.assertEqual(self.listed(self.directory({"agents.md": "x\n"}))[0]["variant"], "agents.md")

    def test_skills_run_state_and_harness_config_are_not_instruction_files(self) -> None:
        not_instructions = [
            ".claude/skills/x/SKILL.md",
            ".codex/config.toml",
            ".opencode/AGENTS.md",
            ".github/prompts/a.prompt.md",
            ".github/agents/a.md",
            ".amazonq/rules/memory-bank/x.md",
            ".agents/skills/x/SKILL.md",
        ]
        target = self.directory(dict.fromkeys(["AGENTS.md", *not_instructions], "x\n"))
        self.assertEqual([entry["path"] for entry in self.listed(target)], ["AGENTS.md"])

    def test_a_repository_with_none_gives_an_empty_list_and_nothing_omitted(self) -> None:
        document = self.document(self.repo)
        self.assertEqual(document["instruction_files"], [])
        self.assertEqual(document["caps"]["instruction_files"], {"limit": 25, "omitted": 0})

    def test_the_size_is_the_files_size_in_bytes(self) -> None:
        target = self.directory({"AGENTS.md": "\u00e9\n", "CLAUDE.md": b"\x00" * 300})
        self.assertEqual([entry["size_bytes"] for entry in self.listed(target)], [3, 300])


class CutTests(InstructionCase):
    def agents_files(self, count: int, *extra: str) -> Path:
        return self.directory(
            {**{f"docs/{n:02d}/AGENTS.md": "x\n" for n in range(1, count + 1)}, **dict.fromkeys(extra, "x\n")}
        )

    def test_twenty_five_files_are_all_listed(self) -> None:
        document = self.document(self.agents_files(25))
        self.assertEqual(len(document["instruction_files"]), 25)
        self.assertEqual(document["caps"]["instruction_files"], {"limit": 25, "omitted": 0})

    def test_the_twenty_sixth_is_left_out_and_counted(self) -> None:
        document = self.document(self.agents_files(26))
        self.assertEqual(
            [entry["path"] for entry in document["instruction_files"]],
            [f"docs/{n:02d}/AGENTS.md" for n in range(1, 26)],
        )
        self.assertEqual(document["caps"]["instruction_files"], {"limit": 25, "omitted": 1})

    def test_a_path_that_does_not_fit_is_counted_and_does_not_use_up_a_place(self) -> None:
        target = self.agents_files(25, "C:/AGENTS.md")
        document = self.document(target)
        self.assertEqual(
            [entry["path"] for entry in document["instruction_files"]],
            [f"docs/{n:02d}/AGENTS.md" for n in range(1, 26)],
        )
        self.assertEqual(document["caps"]["instruction_files"], {"limit": 25, "omitted": 1})

    def test_what_the_schema_cannot_hold_in_a_path_is_left_out(self) -> None:
        fits = "d" * 118 + "/AGENTS.md"
        too_long = "d" * 119 + "/AGENTS.md"
        self.assertEqual((len(fits), len(too_long)), (128, 129))
        target = self.directory(dict.fromkeys([fits, too_long, "\u00e9/AGENTS.md", "C:/AGENTS.md", "AGENTS.md"], "x\n"))
        document = self.document(target)
        self.assertEqual([entry["path"] for entry in document["instruction_files"]], ["AGENTS.md", fits])
        self.assertEqual(document["caps"]["instruction_files"], {"limit": 25, "omitted": 3})

    def test_a_walk_that_was_cut_short_or_excluded_lists_the_files_it_saw(self) -> None:
        self.fill({"sub/AGENTS.md": "x\n"})
        self.assertEqual([entry["path"] for entry in self.listed(self.repo)], ["sub/AGENTS.md"])
        self.assertEqual(self.listed(self.repo, "--max-files", "1"), [])
        self.assertEqual(self.listed(self.repo, "--exclude", "sub/*"), [])


class EngineGapTests(InstructionCase):
    """What the engine does not see, though its variants table names it (Q36). The file inherits it, knowingly."""

    def test_files_the_engine_does_not_see_are_not_listed(self) -> None:
        for rel in NOT_SEEN:
            with self.subTest(file=rel):
                target = self.directory({rel: "x\n"})
                self.assertEqual(self.engine_sees(target), set())
                self.assertEqual(self.listed(target), [])

    def test_the_table_still_has_a_name_for_each_of_them(self) -> None:
        names = {
            ".devin/global_rules.md": ".devin/global_rules.md",
            ".github/copilot-instructions.md": ".github/copilot-instructions.md",
            ".idx/airules.md": ".idx/airules.md",
            ".junie/guidelines.md": ".junie/guidelines.md",
            ".cursor/rules/x.mdc": ".cursor/rules/**/*.mdc",
            ".claude/rules/x.md": ".claude/rules/**/*.md",
            ".github/instructions/x.instructions.md": ".github/instructions/**/*.instructions.md",
            ".kiro/steering/x.md": ".kiro/steering/**/*.md",
        }
        for rel, pattern in names.items():
            with self.subTest(file=rel):
                self.assertEqual(facts.variant_of(rel), pattern)

    def test_a_path_the_table_has_no_name_for_is_a_bug_and_exit_three(self) -> None:
        with self.assertRaises(_common.ToolError) as caught:
            facts.variant_of("notes/readme.txt")
        self.assertEqual(
            str(caught.exception),
            "the engine sees notes/readme.txt as an instruction file and its variants table has no name for it",
        )
        self.assertEqual(caught.exception.exit_code, 3)
        target = self.directory({"notes.txt": "x\n"})
        agt = facts.engine_module("audit.rules.checks.agt")
        with mock.patch.object(agt, "instruction_paths", return_value={"notes.txt"}):
            code, envelope, _ = call([str(target), "--out", str(self.out)])
        self.assertEqual(code, 3)
        self.assertEqual(
            envelope["data"],
            {"error": "the engine sees notes.txt as an instruction file and its variants table has no name for it"},
        )
        self.assertEqual(list(self.folder.iterdir()), [])


if __name__ == "__main__":
    import unittest

    unittest.main()
