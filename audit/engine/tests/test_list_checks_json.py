# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""``--list-checks --format json`` — the catalogue as data.

The brownfield recipes seed and verify their check catalogue from this output, so its shape is a
contract: one entry per registry row, in registry order, with every field the registry holds, and
the same bytes on every run. The default text table must keep working.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from audit import __ruleset_revision__, __version__  # noqa: E402
from audit.rules.registry import REGISTRY, ruleset_hash  # noqa: E402


def run_list_checks(*extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "audit", "--list-checks", *extra], cwd=str(REPO_ROOT), text=True, capture_output=True
    )


class ListChecksJsonTests(unittest.TestCase):
    def setUp(self):
        proc = run_list_checks("--format", "json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.raw = proc.stdout
        self.data = json.loads(proc.stdout)

    def test_one_entry_per_registry_row_in_registry_order(self):
        self.assertEqual([c["id"] for c in self.data["checks"]], [spec.id for spec in REGISTRY])

    def test_every_field_matches_the_registry(self):
        for entry, spec in zip(self.data["checks"], REGISTRY):
            self.assertEqual(
                entry,
                {
                    "id": spec.id,
                    "pack": spec.id.split("-")[0],
                    "title": spec.title,
                    "tier": spec.tier,
                    "severity": spec.severity.value,
                    "phase": spec.phase,
                    "scored": spec.scored,
                    "status": spec.status,
                    "ecosystems": list(spec.ecosystems),
                    "evidence_rule": spec.evidence_rule,
                },
            )

    def test_engine_identity_is_recorded(self):
        self.assertEqual(
            self.data["engine"],
            {
                "name": "python-agentic-audit",
                "version": __version__,
                "ruleset_revision": __ruleset_revision__,
                "ruleset_hash": ruleset_hash(),
            },
        )

    def test_output_is_deterministic(self):
        self.assertEqual(self.raw, run_list_checks("--format", "json").stdout)

    def test_default_output_is_still_the_text_table(self):
        for extra in ((), ("--format", "both"), ("--format", "md")):
            proc = run_list_checks(*extra)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("checks catalogued", proc.stdout)
            self.assertNotIn('"checks"', proc.stdout)


if __name__ == "__main__":
    unittest.main()
