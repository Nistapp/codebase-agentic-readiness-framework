# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""How the scaffolder maps template paths and fills in placeholders.

Covers `target_path_for` (file and folder renames), `build_plan` (the optional `cli/` and `infra/` groups),
`apply_substitutions` (longest token first, the date only where allowed), `build_substitutions` and the
conditional `bin` entry that `finalise_package_json` adds for `--cli`. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from _bootstrap_support import IDENTITY, TEMPLATES, bootstrap, run_main


def namespace(**overrides: object) -> argparse.Namespace:
    """The parsed arguments `build_substitutions` and `finalise_package_json` read, after `main` resolved them."""
    values: dict[str, object] = {
        "resolved_name": "@acme/my-pkg",
        "github_owner": "ada",
        "author": "Ada Lovelace",
        "email": "ada@example.com",
        "description": "A test package",
        "node_version": "24",
        "with_cli": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TargetPathTests(unittest.TestCase):
    def test_renamed_files(self) -> None:
        self.assertEqual(bootstrap.target_path_for("interfaces.ts"), "src/core/interfaces.ts")
        self.assertEqual(bootstrap.target_path_for("core-index.ts"), "src/core/index.ts")
        self.assertEqual(bootstrap.target_path_for("cli/index.ts"), "src/cli/index.ts")

    def test_renamed_folders(self) -> None:
        self.assertEqual(bootstrap.target_path_for("github/workflows/ci.yml"), ".github/workflows/ci.yml")
        self.assertEqual(bootstrap.target_path_for("github/CODEOWNERS"), ".github/CODEOWNERS")
        self.assertEqual(bootstrap.target_path_for("husky/pre-commit"), ".husky/pre-commit")
        self.assertEqual(bootstrap.target_path_for("github"), ".github")

    def test_everything_else_keeps_its_path(self) -> None:
        for rel in ("AGENTS.md", "docs/STYLE_GUIDE.md", "infra/docker-compose.yml", "githubx/a", "src/github/a"):
            with self.subTest(rel=rel):
                self.assertEqual(bootstrap.target_path_for(rel), rel)


class PlanTests(unittest.TestCase):
    def targets(self, *, cli: bool, infra: bool) -> list[str]:
        return [rel for _, rel in bootstrap.build_plan(TEMPLATES, with_cli=cli, with_infra=infra)]

    def test_the_library_plan_leaves_out_the_optional_groups(self) -> None:
        plan = self.targets(cli=False, infra=False)
        self.assertNotIn("src/cli/index.ts", plan)
        self.assertFalse([rel for rel in plan if rel.startswith("infra/")])
        self.assertIn("src/core/index.ts", plan)

    def test_cli_adds_the_cli_entry_point_only(self) -> None:
        extra = set(self.targets(cli=True, infra=False)) - set(self.targets(cli=False, infra=False))
        self.assertEqual(extra, {"src/cli/index.ts"})

    def test_infra_adds_the_infra_folder_only(self) -> None:
        extra = set(self.targets(cli=False, infra=True)) - set(self.targets(cli=False, infra=False))
        self.assertEqual(extra, {"infra/docker-compose.yml", "infra/litellm_config.yaml"})

    def test_every_template_file_is_planned_once_with_both_groups(self) -> None:
        plan = bootstrap.build_plan(TEMPLATES, with_cli=True, with_infra=True)
        sources = sorted(path for path in TEMPLATES.rglob("*") if path.is_file())
        self.assertEqual(sorted(src for src, _ in plan), sources)
        targets = [rel for _, rel in plan]
        self.assertEqual(len(targets), len(set(targets)), "two templates map to one target path")

    def test_no_planned_path_keeps_a_renamed_name(self) -> None:
        for rel in self.targets(cli=True, infra=True):
            with self.subTest(rel=rel):
                self.assertFalse(rel.startswith(("github/", "husky/", "cli/")))
                self.assertNotIn(rel, ("interfaces.ts", "core-index.ts"))


class SubstitutionTests(unittest.TestCase):
    def test_every_placeholder_is_filled(self) -> None:
        subs = bootstrap.build_substitutions(namespace())
        self.assertEqual(
            subs,
            {
                "<project-description>": "A test package",
                "<your-github-username>": "ada",
                "<package-name>": "@acme/my-pkg",
                "<project-name>": "my-pkg",
                "<node-version>": "24",
                "<github-owner>": "ada",
                "[Project Name]": "My Pkg",
                "<your-email>": "ada@example.com",
                "<project>": "my-pkg",
                "<author>": "Ada Lovelace <ada@example.com>",
                "<org>": "ada",
                "[@github-handle]": "@ada",
            },
        )

    def test_without_an_email_the_author_has_no_address(self) -> None:
        subs = bootstrap.build_substitutions(namespace(email=""))
        self.assertEqual(subs["<author>"], "Ada Lovelace")
        self.assertEqual(subs["<your-email>"], "")

    def test_the_longest_token_is_replaced_first(self) -> None:
        subs = {"<project>": "SHORT", "<project-name>": "LONG"}
        self.assertEqual(bootstrap.apply_substitutions("<project-name> <project>", subs, False), "LONG SHORT")

    def test_a_value_that_holds_a_token_is_written_as_given(self) -> None:
        # A value used to be scanned again by every shorter token, so '--description "use <project>"' lost its text.
        subs = bootstrap.build_substitutions(namespace(description="Wraps <project> for <org> users"))
        rendered = bootstrap.apply_substitutions('"<project-description>" by <org>', subs, False)
        self.assertEqual(rendered, '"Wraps <project> for <org> users" by ada')

    def test_main_refuses_a_value_that_holds_a_token(self) -> None:
        # Written as given, the token would trip the post-write leftover check; refuse it up front instead.
        for flag in ("--description", "--author", "--email", "--github-owner"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "out"
                argv = [str(target), "--name", "pkg", "--no-git", *IDENTITY, flag, "see <project>"]
                code, _, err = run_main(argv)
                self.assertEqual(code, 1)
                self.assertIn(f"{flag} 'see <project>' contains the template placeholder <project>", err)
                self.assertFalse(target.exists())

    def test_the_date_is_filled_only_where_allowed(self) -> None:
        today = dt.date.today().isoformat()
        self.assertEqual(bootstrap.apply_substitutions("on YYYY-MM-DD", {}, allow_date=True), f"on {today}")
        self.assertEqual(bootstrap.apply_substitutions("on YYYY-MM-DD", {}, allow_date=False), "on YYYY-MM-DD")

    def test_text_without_placeholders_is_unchanged(self) -> None:
        text = "plain <b>html</b> and [a link](x)"
        self.assertEqual(bootstrap.apply_substitutions(text, bootstrap.build_substitutions(namespace()), True), text)


class PackageJsonTests(unittest.TestCase):
    def rendered(self, **overrides: object) -> dict[str, object]:
        args = namespace(**overrides)
        raw = (TEMPLATES / "package.json").read_text(encoding="utf-8")
        text = bootstrap.finalise_package_json(
            bootstrap.apply_substitutions(raw, bootstrap.build_substitutions(args), False), args
        )
        self.assertTrue(text.endswith("}\n"))
        data = json.loads(text)
        assert isinstance(data, dict)
        return data

    def test_a_library_has_no_bin_entry(self) -> None:
        self.assertNotIn("bin", self.rendered(with_cli=False))

    def test_cli_adds_a_bin_entry_named_after_the_bare_package_name(self) -> None:
        self.assertEqual(self.rendered(with_cli=True)["bin"], {"my-pkg": "./dist/cli/index.js"})
        self.assertEqual(self.rendered(with_cli=True, resolved_name="tool")["bin"], {"tool": "./dist/cli/index.js"})

    def test_the_fields_carry_the_inputs(self) -> None:
        data = self.rendered()
        self.assertEqual(data["name"], "@acme/my-pkg")
        self.assertEqual(data["description"], "A test package")
        self.assertEqual(data["author"], "Ada Lovelace <ada@example.com>")
        self.assertEqual(data["engines"], {"node": ">=24.0.0"})

    def test_non_ascii_text_is_kept_as_written(self) -> None:
        args = namespace(description="Café ✓")
        rendered = bootstrap.finalise_package_json('{"description": "Café ✓"}', args)
        self.assertIn("Café ✓", rendered)


if __name__ == "__main__":
    unittest.main()
