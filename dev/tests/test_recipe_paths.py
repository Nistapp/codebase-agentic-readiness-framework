# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The recipe path check: which pages it reads, which words count as a path, where a path resolves, and the
contract (envelope, exit codes, nothing written).

The proof runs on this repository's own tree: a temporary page that names the engine's NAV module as the file it
was fails, and the same page naming the package it is now passes. The other fixtures are small git work trees
built in a temporary folder (``git init``, no commit: the check also reads untracked files that are not ignored).
Standard library only.
"""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, Sequence

import _dev_paths  # noqa: F401
import _common
import recipe_paths as rp

REPO_ROOT = Path(__file__).resolve().parents[2]


def call(argv: Sequence[str]) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    code = _common.run_tool(rp.INFO, rp.handler, list(argv), stdout=out, stderr=err)
    return code, json.loads(out.getvalue())


class RepositoryProofTests(unittest.TestCase):
    """A page outside the tree, checked against the tree git lists in this repository."""

    tree: rp.Tree

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = rp.Tree.from_paths(rp.git_listed(REPO_ROOT))

    def errors_for(self, text: str, kind: str = "repository") -> list[str]:
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / "page.md"
            page.write_text(text, encoding="utf-8")
            out = rp.Outcome()
            rp.check_page("page.md", kind, page.read_text(encoding="utf-8").splitlines(), self.tree, out)
        return [f"{stale.line}: {stale.resolved}" for stale in out.stale]

    def test_the_old_nav_module_fails_and_its_package_passes(self) -> None:
        self.assertEqual(
            self.errors_for("The checks live in `audit/engine/audit/rules/checks/nav.py`.\n"),
            ["1: audit/engine/audit/rules/checks/nav.py"],
        )
        self.assertEqual(self.errors_for("The checks live in `audit/engine/audit/rules/checks/nav/`.\n"), [])

    def test_the_engine_relative_form_resolves_under_the_engine(self) -> None:
        self.assertEqual(
            self.errors_for("See `audit/rules/checks/nav.py` and `audit/rules/checks/nav/`.\n", kind="recipe"),
            ["1: audit/engine/audit/rules/checks/nav.py"],
        )
        self.assertEqual(self.errors_for("`audit/stack.py` and `audit/report/model.py`\n"), [])

    def test_this_repository_is_clean(self) -> None:
        code, envelope = call([str(REPO_ROOT)])
        self.assertEqual(code, 0, envelope["data"].get("errors"))
        self.assertGreater(envelope["data"]["paths"], 0)


class FixtureTree:
    """A temporary git work tree, built file by file."""

    def __init__(self, root: Path) -> None:
        self.root = root
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        self.write("audit/tools/real.py", "")
        self.write("audit/engine/audit/rules/spec.py", "")
        self.write("audit/engine/docs/page.md", "# Page\n")
        self.write("docs/real.md", "# Real\n")
        self.write("dev/tool.py", "")

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


class FixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tree = FixtureTree(Path(temp.name).resolve())

    def run_check(self) -> tuple[int, dict[str, Any]]:
        return call([str(self.tree.root)])

    def errors(self) -> list[str]:
        code, envelope = self.run_check()
        self.assertIn(code, (0, 2), envelope)
        errors: list[str] = envelope["data"].get("errors", [])
        return errors

    def test_a_clean_tree_exits_0_and_counts_its_paths(self) -> None:
        self.tree.write("AGENTS.md", "Run `audit/tools/real.py` and read `docs/real.md`.\n")
        code, envelope = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["pages"], 1)
        self.assertEqual(envelope["data"]["paths"], 2)

    def test_a_stale_path_exits_2_with_page_line_and_resolved_path(self) -> None:
        self.tree.write("AGENTS.md", "# Title\n\nRun `audit/tools/gone.py --describe`.\n")
        code, envelope = self.run_check()
        self.assertEqual(code, 2)
        self.assertEqual(
            envelope["data"]["errors"],
            ["AGENTS.md:3: `audit/tools/gone.py` names audit/tools/gone.py, which does not exist"],
        )

    def test_a_recipe_page_checks_only_the_framework_folders(self) -> None:
        self.tree.write("implement/playbooks/x.md", "Write `docs/missing.md`; run `dev/missing.py`.\n")
        self.tree.write("audit/checks/01-x.md", "Reads `.github/missing.yml` and `implement/tools/gone.py`.\n")
        self.assertEqual(
            [error.split(": ")[0] for error in self.errors()],
            ["audit/checks/01-x.md:1", "implement/playbooks/x.md:1"],
        )

    def test_a_repository_page_checks_every_top_level_folder(self) -> None:
        self.tree.write("implement/AGENTS.md", "See `docs/missing.md`.\n")
        self.assertEqual(len(self.errors()), 1)

    def test_pages_outside_the_scope_are_not_read(self) -> None:
        for page in (
            "docs/how-to/x.md",
            "CHANGELOG.md",
            "README.md",
            "audit/engine/tests/fixtures/repo/AGENTS.md",
            "greenfield/templates/AGENTS.md",
            "audit/checks/notes.txt",
        ):
            self.tree.write(page, "See `docs/missing.md` and `audit/tools/gone.py`.\n")
        code, envelope = self.run_check()
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["pages"], 0)

    def test_words_that_are_no_path_are_ignored(self) -> None:
        self.tree.write(
            "AGENTS.md",
            "`audit/checks/*.md` `audit/<name>.py` `audit/tools/{a,b}.py` `docs/.../x.md` `$HOME/dev/x`\n"
            "`docs/adrs/NNNN-title.md` `audit/checks/NN-x.md` `scripts/tools/x.py` `tests/x.py` `/dev/null`\n"
            "`audit` `docs/` `fix/report-score` `make -C audit/engine`\n",
        )
        self.assertEqual(self.errors(), [])

    def test_fenced_blocks_are_not_read(self) -> None:
        self.tree.write("AGENTS.md", "```bash\n`audit/tools/gone.py`\n```\n~~~\n`dev/gone.py`\n~~~\n")
        self.assertEqual(self.errors(), [])

    def test_quotes_punctuation_anchors_and_line_suffixes_are_dropped(self) -> None:
        self.tree.write(
            "AGENTS.md",
            '`"audit/tools/real.py",` `(docs/real.md)` `docs/real.md#real` `dev/tool.py:12` `dev/tool.py:L3-L9`\n'
            "``audit/tools/real.py`` `audit/tools/`\n",
        )
        self.assertEqual(self.errors(), [])

    def test_a_page_under_the_engine_resolves_from_the_engine_folder(self) -> None:
        self.tree.write("audit/engine/AGENTS.md", "Read `docs/page.md` and `docs/real.md`, not `docs/gone.md`.\n")
        self.assertEqual(
            self.errors(),
            ["audit/engine/AGENTS.md:1: `docs/gone.md` names docs/gone.md, which does not exist"],
        )

    def test_the_engine_package_form_resolves_under_the_engine(self) -> None:
        self.tree.write("AGENTS.md", "`audit/rules/spec.py` passes; `audit/rules/gone.py` fails.\n")
        self.assertEqual(
            self.errors(),
            [
                "AGENTS.md:1: `audit/rules/gone.py` names audit/engine/audit/rules/gone.py, which does not exist",
            ],
        )

    def test_a_missing_path_git_ignores_is_no_failure(self) -> None:
        self.tree.write(".gitignore", "/dev/dist/\n")
        self.tree.write("AGENTS.md", "The bundles land in `dev/dist/skills/`; `dev/distro/` is stale.\n")
        self.assertEqual(self.errors(), ["AGENTS.md:1: `dev/distro/` names dev/distro/, which does not exist"])

    def test_an_untracked_file_counts_and_a_deleted_one_does_not(self) -> None:
        self.tree.write("AGENTS.md", "`dev/tool.py` and `dev/new.py`\n")
        subprocess.run(["git", "-C", str(self.tree.root), "add", "-A"], check=True)
        (self.tree.root / "dev" / "tool.py").unlink()
        self.tree.write("dev/new.py", "")
        self.assertEqual(self.errors(), ["AGENTS.md:1: `dev/tool.py` names dev/tool.py, which does not exist"])


class ContractTests(unittest.TestCase):
    def test_a_folder_that_is_no_git_work_tree_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            code, envelope = call([folder])
        self.assertEqual(code, 1)
        self.assertFalse(envelope["ok"])
        self.assertIn("not a git work tree", envelope["data"]["error"])

    def test_describe_prints_the_manifest(self) -> None:
        code, envelope = call(["--describe"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["name"], "recipe_paths")
        self.assertFalse(envelope["data"]["writes_inside_target"])

    def test_nothing_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            tree = FixtureTree(Path(folder).resolve())
            tree.write("AGENTS.md", "`dev/gone.py`\n")
            before = sorted(path.relative_to(tree.root) for path in tree.root.rglob("*") if ".git" not in path.parts)
            call([str(tree.root)])
            after = sorted(path.relative_to(tree.root) for path in tree.root.rglob("*") if ".git" not in path.parts)
        self.assertEqual(before, after)

    def test_no_ignored_paths_means_no_git_call(self) -> None:
        self.assertEqual(rp.git_ignored(REPO_ROOT, []), frozenset())


if __name__ == "__main__":
    unittest.main()
