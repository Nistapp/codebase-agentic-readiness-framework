# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``build_masters.py``: link rebasing, field parsing, the stale check and malformed sources."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import build_masters
from _dev_paths import REPO


class RebaseLinks(unittest.TestCase):
    def test_relative_link_is_rewritten_from_the_output_folder(self) -> None:
        text = "see [x](../../greenfield/README.md#61-agentsmd)"
        got = build_masters.rebase_links(text, Path("audit/checks/02-agent-governance.md"))
        self.assertEqual(got, "see [x](../../greenfield/README.md#61-agentsmd)")

    def test_sibling_link_gains_the_source_folder(self) -> None:
        got = build_masters.rebase_links("[r](README.md)", Path("implement/playbooks/add-ci-parity.md"))
        self.assertEqual(got, "[r](../../implement/playbooks/README.md)")

    def test_same_page_anchor_points_at_the_source_page(self) -> None:
        got = build_masters.rebase_links("[c](#continue-on-error)", Path("implement/playbooks/add-ci-parity.md"))
        self.assertEqual(got, "[c](../../implement/playbooks/add-ci-parity.md#continue-on-error)")

    def test_external_link_and_image_are_left_alone(self) -> None:
        text = "[a](https://example.com/x) ![i](pic.png)"
        self.assertEqual(build_masters.rebase_links(text, Path("audit/checks/01-x.md")), text)


class FieldText(unittest.TestCase):
    def test_continuation_lines_join_and_the_next_field_stops_it(self) -> None:
        body = "\nWhy it matters   first line\n                  second line\nSeverity         BLOCKER\n"
        self.assertEqual(build_masters.field_text(body, "Why it matters"), "first line second line")
        self.assertEqual(build_masters.field_text(body, "Severity"), "BLOCKER")

    def test_missing_field_is_empty(self) -> None:
        self.assertEqual(build_masters.field_text("Severity  BLOCKER\n", "Rubric"), "")


class RepositoryPages(unittest.TestCase):
    def test_committed_pages_match_the_sources(self) -> None:
        for path, text in build_masters.render(REPO).items():
            with self.subTest(page=str(path)):
                self.assertEqual((REPO / path).read_text(encoding="utf-8"), text, "run `make update-masters`")

    def test_every_catalogue_check_and_playbook_appears(self) -> None:
        pages = build_masters.render(REPO)
        catalogue = json.loads((REPO / build_masters.CATALOGUE).read_text(encoding="utf-8"))
        audit = pages[build_masters.AUDIT_PAGE]
        implement = pages[build_masters.IMPLEMENT_PAGE]
        for check in catalogue["checks"]:
            self.assertIn(f"#### `{check['id']}` ", audit)
            for playbook in check["playbooks"]:
                self.assertIn(f"### `{playbook}`", implement)


class Sandbox(unittest.TestCase):
    """A copy of the sources in a temporary root, so a test can break one."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        for folder in (build_masters.CHECKS_DIR, build_masters.PLAYBOOKS_DIR):
            shutil.copytree(REPO / folder, self.root / folder)
        (self.root / build_masters.OUT_DIR).mkdir(parents=True)
        shutil.copy(REPO / build_masters.CATALOGUE, self.root / build_masters.CATALOGUE)

    def run_main(self, *argv: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = build_masters.main(list(argv), root=self.root)
        return code, err.getvalue()

    def test_missing_pages_are_stale_until_written(self) -> None:
        self.assertEqual(self.run_main("--check")[0], 1)
        self.assertEqual(self.run_main("--write")[0], 0)
        self.assertEqual(self.run_main("--check")[0], 0)

    def test_a_source_change_makes_the_page_stale(self) -> None:
        self.run_main("--write")
        path = self.root / build_masters.CHECKS_DIR / "06-ci.md"
        path.write_text(path.read_text(encoding="utf-8").replace("Verification must", "Checking must", 1))
        code, err = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("audit-master.md is stale", err)

    def test_a_family_with_no_area_is_refused(self) -> None:
        path = self.root / build_masters.CATALOGUE
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        catalogue["checks"][0]["family"] = "NEW"
        path.write_text(json.dumps(catalogue), encoding="utf-8")
        code, err = self.run_main("--check")
        self.assertEqual(code, 2)
        self.assertIn("NEW has no area", err)

    def test_a_check_with_no_section_is_refused(self) -> None:
        path = self.root / build_masters.CATALOGUE
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        catalogue["checks"][0]["id"] = "IDX-99"
        path.write_text(json.dumps(catalogue), encoding="utf-8")
        code, err = self.run_main("--check")
        self.assertEqual(code, 2)
        self.assertIn("IDX-99 has no section", err)

    def test_a_playbook_missing_from_the_list_is_refused(self) -> None:
        (self.root / build_masters.PLAYBOOKS_DIR / "new-playbook.md").write_text("# Playbook\n", encoding="utf-8")
        code, err = self.run_main("--check")
        self.assertEqual(code, 2)
        self.assertIn("new-playbook", err)


if __name__ == "__main__":
    unittest.main()
