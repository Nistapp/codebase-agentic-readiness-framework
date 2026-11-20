# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Text added to a place marked ``monotone`` never lowers the verdict of the check that marks it (rule R5).

``audit/rules/reads.py`` marks a place ``monotone`` (``MONOTONE``) when added text can only raise the check's verdict
there. The consistency map then leaves a move marked ``mode: add`` out of the unreviewed pairs for that place
(ADR 0012 in the repository's ``docs/architecture/adrs/``). This test holds the mark to the code.

Each fixture under ``tests/fixtures/``, and a greenfield scaffold, is copied to a temporary folder. For each monotone
file the copy holds, the test adds text the way ``mode: add`` allows: whole blocks at a block boundary, and a new
heading only where a section ends. A document gets each block of :data:`_BLOCKS` at its end and before each heading of
level 1 or 2. A ``package.json`` gets a new script, and a ``Makefile`` a new target. Each check that marks the file
then runs again. A verdict is lowered when a ``PASS`` turns into anything else or a ``PARTIAL`` into a ``FAIL``: the
change that ``implement/tools/check_regressions.py`` stops a theme for.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.components import detect_components  # noqa: E402
from audit.probes import ProbeSession  # noqa: E402
from audit.rules import checks, reads  # noqa: E402
from audit.rules.registry import REGISTRY  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import VERBS, detect_stack  # noqa: E402
from audit.target import resolve_target  # noqa: E402
from test_check_reads import _scaffold  # noqa: E402

#: Blocks a ``mode: add`` step may add to a document: a new section, a prohibition with a path, a fenced command and a
#: paragraph that names CI.
_BLOCKS: tuple[str, ...] = (
    "## Added notes\n\nThis section was added by a step.\n",
    "- Never edit `dist/` or `tests/` by hand; never push to `main`.\n",
    "```bash\nnpm test -- -t 'one test'\n```\n",
    "A plain paragraph: CI runs the same gate command.\n",
)
_HEADING = re.compile(r"^#{1,2}\s")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
_SPECS = {spec.id: spec for spec in REGISTRY}


def _lowered(before: str, after: str) -> bool:
    return (before == "PASS" and after != "PASS") or (before == "PARTIAL" and after == "FAIL")


def _boundaries(text: str) -> list[int]:
    """The line indexes where a block and a new level-2 section may go: before each heading of level 1 or 2 outside a
    fence, and at the end."""
    lines = text.splitlines()
    found: list[int] = []
    fenced = False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and _HEADING.match(line):
            found.append(index)
    return [*found, len(lines)]


def _document_variants(text: str) -> list[str]:
    lines = text.splitlines()
    return [
        "\n".join([*lines[:at], "", *block.splitlines(), "", *lines[at:]]) + "\n"
        for at in _boundaries(text)
        for block in _BLOCKS
    ]


def _key_variants(rel: str, text: str) -> list[str]:
    """For a ``package.json`` with a ``scripts`` object or a ``Makefile``: one variant per key the file lacks, a
    framework verb or a plain name, each added on its own. Other runner files get none."""
    names = (*(verb.replace(":", "-") for verb in VERBS), "added-key")
    if rel == "Makefile":
        return [
            text.rstrip("\n") + f"\n\n{name}:\n\techo {name}\n"
            for name in names
            if not re.search(rf"(?m)^{re.escape(name)}\s*:", text)
        ]
    if rel == "package.json":
        try:
            data = json.loads(text)
        except ValueError:
            return []
        if not (isinstance(data, dict) and isinstance(data.get("scripts"), dict)):
            return []
        variants = []
        for name in (*VERBS, "added-key"):
            if name not in data["scripts"]:
                variants.append(json.dumps({**data, "scripts": {**data["scripts"], name: f"echo {name}"}}, indent=2))
        return variants
    return []


def _monotone_files(root: Path, table: dict[str, tuple[str, ...]]) -> dict[str, list[str]]:
    """Each root file of the copy that some check of ``table`` marks monotone, with those checks."""
    by_file: dict[str, list[str]] = {}
    for check, paths in table.items():
        for pattern in paths:
            for file in sorted(root.glob(pattern)):
                if file.is_file():
                    by_file.setdefault(file.name, []).append(check)
    return by_file


def _verdicts(root: Path, wanted: list[str]) -> dict[str, str]:
    target = resolve_target(root)
    inventory = build_inventory(target.path)
    stack = detect_stack(inventory)
    components = detect_components(inventory)
    session = ProbeSession(cwd=target.path, user_config=False)
    return {
        check: _SPECS[check]
        .run(target=target, inventory=inventory, stack=stack, components=components, session=session)
        .verdict.value
        for check in wanted
    }


#: Two small targets beside the fixtures, so that the additions meet a passing verdict the fixtures rarely hold: every
#: verb on a Makefile next to a package.json with no verb, and a root AGENTS.md with a CLAUDE.md that only points at
#: it. A verb added to the package.json puts the verbs on two runners (``CMD-01``), and a line added to the pointer
#: makes it a competitor (``AGT-08``).
_CONTROL_TARGETS: dict[str, dict[str, str]] = {
    "two-runners": {
        "Makefile": "".join(f"{verb.replace(':', '-')}:\n\techo {verb}\n" for verb in VERBS),
        "package.json": '{"name": "x", "scripts": {"start": "node x.js"}}\n',
    },
    "pointer": {
        "AGENTS.md": "# Rules\n\nThis file is read by Claude Code and Codex.\n",
        "CLAUDE.md": "@AGENTS.md\n",
    },
}


def _sources(folder: Path) -> list[Path]:
    """Every fixture, a greenfield scaffold and the control targets, written under ``folder``."""
    sources = sorted(path for path in support.FIXTURES_DIR.iterdir() if path.is_dir())
    folder.mkdir()
    sources.append(_scaffold(folder / "scaffold"))
    for name, files in _CONTROL_TARGETS.items():
        for rel, text in files.items():
            (folder / name / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / name / rel).write_text(text, encoding="utf-8")
        sources.append(folder / name)
    return sources


def _lowered_by_additions(table: dict[str, tuple[str, ...]]) -> tuple[int, list[tuple[str, str, int, str, str, str]]]:
    """How many additions ran, and each ``(source, file, variant, check, before, after)`` whose verdict fell.

    Each source (:func:`_sources`) is copied before it is changed.
    """
    checks.con.set_emit_target(None)
    lowered: list[tuple[str, str, int, str, str, str]] = []
    runs = 0
    with tempfile.TemporaryDirectory() as folder:
        for source in _sources(Path(folder) / "sources"):
            root = Path(folder) / "copy"
            shutil.copytree(source, root, symlinks=True)
            for rel, wanted in _monotone_files(root, table).items():
                file = root / rel
                original = file.read_text(encoding="utf-8", errors="replace")
                before = _verdicts(root, wanted)
                runner = rel in reads._RUNNER_PATHS
                for number, text in enumerate(_key_variants(rel, original) if runner else _document_variants(original)):
                    file.write_text(text, encoding="utf-8")
                    after = _verdicts(root, wanted)
                    runs += 1
                    lowered += [
                        (source.name, rel, number, check, before[check], after[check])
                        for check in wanted
                        if _lowered(before[check], after[check])
                    ]
                file.write_text(original, encoding="utf-8")
            shutil.rmtree(root)
    return runs, lowered


class MonotonePlacesTest(unittest.TestCase):
    def test_the_table_names_implemented_checks_only(self) -> None:
        self.assertTrue(set(reads.MONOTONE) <= {spec.id for spec in REGISTRY if spec.impl is not None})
        self.assertNotIn("CMD-01", reads.MONOTONE)

    def test_each_marked_place_is_in_the_table_and_each_table_path_is_marked(self) -> None:
        marked = {
            check: {place.path for place in declared.where if place.monotone} for check, declared in reads.READS.items()
        }
        self.assertEqual(
            {check: paths for check, paths in marked.items() if paths},
            {check: set(paths) for check, paths in reads.MONOTONE.items()},
        )

    def test_a_path_that_is_no_place_is_refused(self) -> None:
        with mock.patch.dict(reads.MONOTONE, {"AGT-03": ("README.md",)}):
            with self.assertRaises(ValueError):
                reads._with_monotone("AGT-03", reads.READS["AGT-03"])

    def test_added_text_never_lowers_a_verdict(self) -> None:
        """Every fixture and a scaffold, each monotone file, each addition: no check that marks the file loses."""
        runs, lowered = _lowered_by_additions(reads.MONOTONE)
        self.assertGreater(runs, 500)
        self.assertEqual(lowered, [])

    def test_the_two_places_left_out_do_lose_a_verdict(self) -> None:
        """The control: the review left ``CMD-01`` and the ``CLAUDE.md`` place of ``AGT-08`` out, and the same
        additions lower both, so the test can see a place that is not monotone."""
        runs, lowered = _lowered_by_additions({"CMD-01": reads._RUNNER_PATHS, "AGT-08": ("CLAUDE.md",)})
        self.assertGreater(runs, 0)
        self.assertEqual({check for _source, _rel, _number, check, _before, _after in lowered}, {"CMD-01", "AGT-08"})


if __name__ == "__main__":
    unittest.main()
