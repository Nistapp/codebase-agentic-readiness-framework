# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The map's reads part equals what ``dev/consistency_map_reads.py`` generates from the engine (ADR 0012).

The engine declares each check's reads in ``audit/rules/reads.py``; the map's ``reads`` part is written from that
table. This test fails when the two drift, so a changed declaration needs ``--write`` in the same change.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import _dev_paths
import consistency_map_reads as cmr

import consistency_map

MAP: dict[str, Any] = consistency_map.load_map()
CATALOGUE_IDS: list[str] = [
    check["id"]
    for check in json.loads((_dev_paths.REPO / "audit" / "catalogue.json").read_text(encoding="utf-8"))["checks"]
]
DECLARED = cmr.engine_declarations()


def _run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cmr.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class GeneratedTest(unittest.TestCase):
    def test_the_map_reads_equal_the_engine_declarations(self) -> None:
        generated = cmr.generated_reads(MAP["reads"], CATALOGUE_IDS, DECLARED)
        self.assertEqual(cmr.differing_checks(MAP["reads"], generated), [])
        self.assertEqual(MAP["reads"], generated)

    def test_the_check_mode_passes_on_this_tree(self) -> None:
        code, out, _ = _run()
        self.assertEqual(code, 0)
        self.assertIn("78 reads entries match the engine", out)

    def test_every_engine_entry_comes_from_the_engine_and_the_agent_entries_stay(self) -> None:
        sources = {read["check"]: read["source"] for read in MAP["reads"]}
        self.assertEqual(sorted(check for check, source in sources.items() if source == "agent"), ["AGT-11", "CI-04"])
        self.assertEqual(sorted(check for check, source in sources.items() if source == "engine"), sorted(DECLARED))

    def test_an_entry_names_constants_only_when_they_hold_its_whole_list(self) -> None:
        (cmd01,) = [read for read in MAP["reads"] if read["check"] == "CMD-01"]
        (tst01,) = [read for read in MAP["reads"] if read["check"] == "TST-01"]
        self.assertEqual(cmd01["constants"], ["audit.rules.checks._common:RUNNER_PRECEDENCE"])
        self.assertNotIn("constants", tst01)

    def test_a_place_read_upstream_carries_its_step_and_others_carry_none(self) -> None:
        (nav01,) = [read for read in MAP["reads"] if read["check"] == "NAV-01"]
        (cmd01,) = [read for read in MAP["reads"] if read["check"] == "CMD-01"]
        self.assertEqual({where.get("via") for where in nav01["where"]}, {"components"})
        self.assertEqual([where for where in cmd01["where"] if "via" in where], [])

    def test_a_folded_place_and_a_text_named_read_reach_the_map(self) -> None:
        reads = {read["check"]: read for read in MAP["reads"]}
        self.assertEqual(
            [w["path"] for w in reads["AGT-12"]["where"] if w.get("case") == "fold"], ["**/*communicat*.md"]
        )
        self.assertEqual([w.get("case") for w in reads["HYG-08"]["where"]], ["fold"])
        self.assertEqual(
            sorted(c for c, read in reads.items() if "named_by_text" in read),
            ["AGT-06", "AGT-10", "CI-02", "CI-04", "CON-01"],
        )
        self.assertNotIn("case", reads["CMD-01"]["where"][0])

    def test_the_ci04_entry_names_every_place_its_rubric_reads(self) -> None:
        # audit/checks/06-ci.md, CI-04: the workflows and the actions they use, the declared branch rules (the
        # HYG-11 files) and a committed counts file. Wrapper scripts and the CI doc are named by the target's text.
        (ci04,) = [read for read in MAP["reads"] if read["check"] == "CI-04"]
        paths = {where["path"] for where in ci04["where"]}
        self.assertLessEqual(
            {
                ".github/workflows/*.yml",
                ".github/actions/**/action.yml",
                ".github/rulesets/**/*.json",
                ".github/settings.yml",
                "**/*branch-protection*",
                "*baseline*.json",
            },
            paths,
        )
        self.assertIn("wrapper script", ci04["named_by_text"])
        self.assertIn("CI doc", ci04["named_by_text"])

    def test_an_unexercised_place_carries_its_reason_and_others_carry_none(self) -> None:
        reads = {read["check"]: read for read in MAP["reads"]}
        marked = sorted(
            (check, where["path"])
            for check, read in reads.items()
            for where in read.get("where", [])
            if where.get("unexercised")
        )
        self.assertEqual(
            marked,
            [
                ("EXEC-02", "go.mod"),
                ("EXEC-07", "gradlew"),
                ("EXEC-07", "mvnw"),
                ("EXEC-08", "go.mod"),
                ("IDX-03", ".codebase-memory/graph.db.zst"),
            ],
        )
        self.assertNotIn("unexercised", reads["CMD-01"]["where"][0])


class DriftTest(unittest.TestCase):
    def _copy(self, cmap: dict[str, Any]) -> Path:
        folder = Path(tempfile.mkdtemp(prefix="cmap-reads-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = folder / "consistency-map.json"
        path.write_text(cmr.render(cmap), encoding="utf-8")
        return path

    def test_a_changed_entry_fails_and_write_restores_it(self) -> None:
        cmap = json.loads(json.dumps(MAP))
        cmap["reads"][0]["note"] = "edited by hand"
        path = self._copy(cmap)
        code, _, err = _run("--map", str(path))
        self.assertEqual(code, 1)
        self.assertIn(cmap["reads"][0]["check"], err)
        code, out, _ = _run("--map", str(path), "--write")
        self.assertEqual((code, out.strip()), (0, "consistency_map_reads.py: 1 reads entries rewritten"))
        self.assertEqual(path.read_text(encoding="utf-8"), cmr.render(MAP))

    def test_write_leaves_the_other_parts_as_they_are(self) -> None:
        cmap = json.loads(json.dumps(MAP))
        cmap["reads"] = cmap["reads"][1:]
        cmap["moves"] = cmap["moves"][:1]
        path = self._copy(cmap)
        self.assertEqual(_run("--map", str(path), "--write")[0], 0)
        written = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(written["moves"], MAP["moves"][:1])
        self.assertEqual(written["reads"], MAP["reads"])

    def _copy_folder(self) -> Path:
        """A copy of this tree's map folder."""
        path = Path(tempfile.mkdtemp(prefix="cmap-reads-")) / "consistency-map"
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)
        shutil.copytree(consistency_map.MAP_PATH, path)
        return path

    def test_write_restores_the_reads_files_of_the_folder_form(self) -> None:
        path = self._copy_folder()
        # The two agent entries, AGT-11 and CI-04, are written in the map, so their files stay.
        (path / "reads" / "BASE.json").unlink()
        (path / "reads" / "TOOL.json").write_text("[]\n", encoding="utf-8")
        index = json.loads((path / "index.json").read_text(encoding="utf-8"))
        index["parts"]["reads"].remove("reads/BASE.json")
        (path / "index.json").write_text(json.dumps(index), encoding="utf-8")
        code, _, err = _run("--map", str(path))
        self.assertEqual(code, 1)
        self.assertIn("BASE-01", err)
        code, out, _ = _run("--map", str(path), "--write")
        self.assertEqual(code, 0)
        self.assertIn("reads entries rewritten", out)
        for original in sorted(consistency_map.MAP_PATH.rglob("*.json")):
            copied = path / original.relative_to(consistency_map.MAP_PATH)
            self.assertEqual(copied.read_text(encoding="utf-8"), original.read_text(encoding="utf-8"), original.name)
        self.assertEqual(_run("--map", str(path))[0], 0)

    def test_write_in_the_folder_form_leaves_the_other_parts_alone(self) -> None:
        path = self._copy_folder()
        before = {p.name: p.read_bytes() for part in ("moves", "keeps", "names") for p in (path / part).glob("*.json")}
        (path / "reads" / "TOOL.json").write_text("[]\n", encoding="utf-8")
        self.assertEqual(_run("--map", str(path), "--write")[0], 0)
        after = {p.name: p.read_bytes() for part in ("moves", "keeps", "names") for p in (path / part).glob("*.json")}
        self.assertEqual(before, after)

    def test_a_missing_agent_entry_is_an_error(self) -> None:
        cmap = json.loads(json.dumps(MAP))
        cmap["reads"] = [read for read in cmap["reads"] if read["check"] != "AGT-11"]
        code, _, err = _run("--map", str(self._copy(cmap)))
        self.assertEqual(code, 2)
        self.assertIn("AGT-11", err)

    def test_an_engine_declaration_the_catalogue_does_not_list_is_an_error(self) -> None:
        with self.assertRaisesRegex(cmr.ReadsError, "TOOL-99"):
            cmr.generated_reads(MAP["reads"], CATALOGUE_IDS, {**DECLARED, "TOOL-99": DECLARED["TOOL-01"]})

    def test_an_order_change_alone_is_a_difference(self) -> None:
        swapped = [MAP["reads"][1], MAP["reads"][0], *MAP["reads"][2:]]
        self.assertEqual(cmr.differing_checks(swapped, MAP["reads"]), ["(order)"])


if __name__ == "__main__":
    unittest.main()
