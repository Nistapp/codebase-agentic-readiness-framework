# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for ``build_catalogue.py``: the committed catalogue is current, and a malformed overlay is refused."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import build_catalogue
from _dev_paths import REPO

ENGINE = build_catalogue.engine_checks(REPO)


class RepositoryCatalogue(unittest.TestCase):
    def test_committed_catalogue_matches_the_sources(self) -> None:
        committed = (REPO / build_catalogue.CATALOGUE).read_text(encoding="utf-8")
        self.assertEqual(committed, build_catalogue.render(REPO, ENGINE), "run `make update-catalogue`")

    def test_every_engine_check_has_an_overlay_entry(self) -> None:
        overlay = json.loads((REPO / build_catalogue.OVERLAY).read_text(encoding="utf-8"))
        for check in ENGINE:
            self.assertIn(check["id"], overlay["checks"])


class Sandbox(unittest.TestCase):
    """A copy of the overlay and the check files in a temporary root, so a test can break one."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        shutil.copytree(REPO / build_catalogue.CHECKS_DIR, self.root / build_catalogue.CHECKS_DIR)
        shutil.copy(REPO / build_catalogue.OVERLAY, self.root / build_catalogue.OVERLAY)

    def overlay(self) -> dict[str, Any]:
        data: dict[str, Any] = json.loads((self.root / build_catalogue.OVERLAY).read_text(encoding="utf-8"))
        return data

    def save(self, overlay: dict[str, Any]) -> None:
        (self.root / build_catalogue.OVERLAY).write_text(json.dumps(overlay), encoding="utf-8")

    def run_main(self, *argv: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = build_catalogue.main(list(argv), root=self.root, engine=ENGINE)
        return code, err.getvalue()

    def catalogue(self) -> dict[str, Any]:
        data: dict[str, Any] = json.loads((self.root / build_catalogue.CATALOGUE).read_text(encoding="utf-8"))
        return data

    def test_a_missing_catalogue_is_stale_until_written(self) -> None:
        self.assertEqual(self.run_main("--check")[0], 1)
        self.assertEqual(self.run_main("--write")[0], 0)
        self.assertEqual(self.run_main("--check")[0], 0)
        self.assertEqual(
            (self.root / build_catalogue.CATALOGUE).read_text(encoding="utf-8"),
            (REPO / build_catalogue.CATALOGUE).read_text(encoding="utf-8"),
        )

    def test_an_overlay_change_makes_the_catalogue_stale(self) -> None:
        self.run_main("--write")
        overlay = self.overlay()
        overlay["checks"]["IDX-01"]["playbooks"] = ["another-playbook"]
        self.save(overlay)
        code, err = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("catalogue.json is stale", err)

    def test_a_requirement_change_moves_the_fingerprint(self) -> None:
        self.run_main("--write")
        before = self.catalogue()["fingerprint"]
        overlay = self.overlay()
        overlay["checks"]["IDX-01"]["req_ids"] = ["REQ-SH-999"]
        self.save(overlay)
        self.run_main("--write")
        self.assertNotEqual(self.catalogue()["fingerprint"], before)

    def test_an_engine_check_with_no_entry_is_refused(self) -> None:
        overlay = self.overlay()
        del overlay["checks"]["CMD-02"]
        self.save(overlay)
        code, err = self.run_main("--check")
        self.assertEqual(code, 2)
        self.assertIn("CMD-02 is in the engine but has no entry", err)

    def test_an_unknown_field_on_an_engine_check_is_refused(self) -> None:
        overlay = self.overlay()
        overlay["checks"]["CMD-02"]["title"] = "A second title"
        self.save(overlay)
        code, err = self.run_main("--check")
        self.assertEqual(code, 2)
        self.assertIn("unknown overlay field(s) title", err)

    def test_an_entry_with_no_engine_check_must_be_agent_only(self) -> None:
        overlay = self.overlay()
        overlay["checks"]["CMD-09"] = {"req_ids": [], "playbooks": []}
        self.save(overlay)
        code, err = self.run_main("--check")
        self.assertEqual(code, 2)
        self.assertIn("CMD-09 is in audit/catalogue-overlay.json but not in the engine", err)

    def test_an_agent_only_check_states_every_field(self) -> None:
        overlay = self.overlay()
        del overlay["checks"]["CI-04"]["status"]
        self.save(overlay)
        code, err = self.run_main("--check")
        self.assertEqual(code, 2)
        self.assertIn("CI-04: an agent-only check states exactly", err)

    def test_an_agent_only_check_sits_after_the_lower_numbered_engine_checks(self) -> None:
        overlay = self.overlay()
        overlay["checks"]["CMD-09"] = dict(overlay["checks"]["CI-04"])
        self.save(overlay)
        self.assertEqual(self.run_main("--write")[0], 0)
        ids = [check["id"] for check in self.catalogue()["checks"]]
        self.assertEqual(ids[ids.index("CMD-04") + 1], "CMD-09")
        self.assertEqual(ids[ids.index("CI-03") + 1], "CI-04")

    def test_a_family_with_no_heading_is_refused(self) -> None:
        for path in (self.root / build_catalogue.CHECKS_DIR).glob("??-ci.md"):
            path.unlink()
        code, err = self.run_main("--check")
        self.assertEqual(code, 2)
        self.assertIn("heading in audit/checks for CI", err)

    def test_an_overlay_without_a_version_is_refused(self) -> None:
        overlay = self.overlay()
        del overlay["catalogue_version"]
        self.save(overlay)
        self.assertEqual(self.run_main("--check")[0], 2)


if __name__ == "__main__":
    unittest.main()
