# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The check catalogue agrees with the engine, the spec and the traceability page.

`brownfield-recipes/catalogue.json` is the one machine-readable source of check metadata. These tests
keep it honest. Every engine check must appear in it exactly as the engine reports it. Every
requirement's `Checks` field must say what the catalogue says, and the other way round. Anything that
decides a verdict is covered by the fingerprint, so a change to it cannot pass without the version
being considered.

Standard library only. The engine is run as a subprocess through its own command line.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
RECIPES = REPO_ROOT / "brownfield-recipes"
ENGINE = RECIPES / "deterministic-audit"
CATALOGUE = RECIPES / "catalogue.json"
REQUIREMENTS = REPO_ROOT / "spec" / "readiness-requirements.md"
TRACEABILITY = REPO_ROOT / "spec" / "traceability.md"

CHECK_ID = re.compile(r"^[A-Z]{2,5}-[0-9]{2,3}$")
REQ_ID = re.compile(r"REQ-(?:BF|GF|SH)-[0-9]{3}")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

Check = dict[str, Any]


def load_catalogue() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    return data


def engine_checks() -> list[Check]:
    """The engine's own list of checks, from `--list-checks --format json`."""
    proc = subprocess.run(
        [sys.executable, "-m", "audit", "--list-checks", "--format", "json"],
        cwd=str(ENGINE),
        text=True,
        capture_output=True,
        check=True,
    )
    checks: list[Check] = json.loads(proc.stdout)["checks"]
    return checks


def requirement_fields() -> dict[str, tuple[str, list[str]]]:
    """Each requirement ID mapped to its `Verification` method and the check IDs in its `Checks` field."""
    found: dict[str, tuple[str, list[str]]] = {}
    current = ""
    verification = ""
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^### (REQ-[A-Z]{2}-[0-9]{3}) — ", line)
        if heading:
            current = heading.group(1)
            verification = ""
            continue
        method = re.match(r"^- \*\*Verification:\*\* (\w+)", line)
        if method and current:
            verification = method.group(1)
            continue
        checks = re.match(r"^- \*\*Checks:\*\* (.+)$", line)
        if checks and current:
            value = checks.group(1).strip()
            ids = [] if value.startswith("none") else [item.strip() for item in value.split(",")]
            found[current] = (verification, ids)
    return found


def traceability_rows() -> dict[str, set[str]]:
    """Each check ID in the traceability page's "Checks to requirements" table, with its requirement IDs."""
    text = TRACEABILITY.read_text(encoding="utf-8")
    start = text.index("## Checks to requirements")
    end = text.index("\n## ", start + 1)
    rows: dict[str, set[str]] = {}
    for line in text[start:end].splitlines():
        cell = re.match(r"^\| `([A-Z]{2,5}-[0-9]{2,3})` \|", line)
        if cell:
            rows[cell.group(1)] = set(REQ_ID.findall(line.rsplit("|", 2)[-2]))
    return rows


def fingerprint(checks: list[Check]) -> str:
    """First 16 hex digits of SHA-256 over one line per check, as `catalogue.schema.json` defines it."""
    lines = [
        "|".join(
            [
                c["id"],
                str(c["phase"]),
                c["severity"],
                str(int(c["scored"])),
                c["method"],
                ",".join(sorted(c["req_ids"])),
                c["engine_id"] or "",
            ]
        )
        for c in checks
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


class CatalogueTests(unittest.TestCase):
    catalogue: dict[str, Any]
    checks: list[Check]
    by_id: dict[str, Check]
    engine: list[Check]

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalogue = load_catalogue()
        cls.checks = cls.catalogue["checks"]
        cls.by_id = {c["id"]: c for c in cls.checks}
        cls.engine = engine_checks()

    def test_ids_are_unique_and_the_family_is_the_prefix(self) -> None:
        ids = [c["id"] for c in self.checks]
        self.assertEqual(len(ids), len(set(ids)), "duplicate check IDs in the catalogue")
        for c in self.checks:
            self.assertRegex(c["id"], CHECK_ID)
            self.assertEqual(c["family"], c["id"].split("-")[0], f"{c['id']}: family is not the ID's prefix")

    def test_version_is_well_formed_and_the_fingerprint_is_current(self) -> None:
        self.assertRegex(self.catalogue["catalogue_version"], VERSION)
        self.assertEqual(
            self.catalogue["fingerprint"],
            fingerprint(self.checks),
            "The fingerprint is stale. A check's id, phase, severity, scored flag, method, requirement IDs or "
            "engine ID changed. Decide the catalogue_version bump (the rules are in catalogue.schema.json), "
            "set the fingerprint to the current value, and run `make update-secrets-baseline`.",
        )

    def test_every_engine_check_is_catalogued_as_the_engine_reports_it(self) -> None:
        for engine in self.engine:
            entry = self.by_id.get(engine["id"])
            self.assertIsNotNone(entry, f"{engine['id']} is in the engine but not in the catalogue")
            assert entry is not None
            self.assertEqual(entry["engine_id"], engine["id"])
            self.assertEqual(entry["method"], "automated", f"{engine['id']}: an engine check is automated")
            for ours, theirs in [
                ("family", "pack"),
                ("title", "title"),
                ("phase", "phase"),
                ("severity", "severity"),
                ("scored", "scored"),
                ("status", "status"),
            ]:
                self.assertEqual(entry[ours], engine[theirs], f"{engine['id']}: {ours} differs from the engine's")

    def test_engine_checks_keep_the_engines_order(self) -> None:
        catalogued = [c["engine_id"] for c in self.checks if c["engine_id"] is not None]
        self.assertEqual(catalogued, [e["id"] for e in self.engine])

    def test_no_catalogue_check_claims_an_engine_id_the_engine_lacks(self) -> None:
        engine_ids = {e["id"] for e in self.engine}
        for c in self.checks:
            if c["engine_id"] is not None:
                self.assertIn(c["engine_id"], engine_ids, f"{c['id']} names an engine check that does not exist")

    def test_agent_only_checks_are_numbered_after_the_engines_in_their_family(self) -> None:
        engine_ids = {e["id"] for e in self.engine}
        agent = [c for c in self.checks if c["engine_id"] is None]
        self.assertTrue(agent, "expected at least one agent-only check")
        for c in agent:
            self.assertEqual(c["method"], "agent", f"{c['id']}: a check without an engine ID is judged by an agent")
            self.assertNotIn(c["id"], engine_ids, f"{c['id']} reuses an engine ID")
            family_numbers = [int(e["id"].split("-")[1]) for e in self.engine if e["pack"] == c["family"]]
            self.assertTrue(family_numbers, f"{c['id']}: the family {c['family']} has no engine checks")
            self.assertGreater(int(c["id"].split("-")[1]), max(family_numbers), f"{c['id']} is not after the engine's")

    def test_requirements_and_the_catalogue_agree_both_ways(self) -> None:
        requirements = requirement_fields()
        for req, (_, ids) in requirements.items():
            for check_id in ids:
                self.assertIn(check_id, self.by_id, f"{req} names {check_id}, which is not in the catalogue")
                self.assertIn(req, self.by_id[check_id]["req_ids"], f"{req} names {check_id}, which does not name it")
        for c in self.checks:
            for req in c["req_ids"]:
                self.assertIn(req, requirements, f"{c['id']} names {req}, which is not a requirement")
                self.assertIn(c["id"], requirements[req][1], f"{c['id']} names {req}, whose Checks field omits it")

    def test_a_check_has_the_method_of_the_requirement_it_verifies(self) -> None:
        requirements = requirement_fields()
        for c in self.checks:
            for req in c["req_ids"]:
                self.assertEqual(
                    c["method"],
                    requirements[req][0],
                    f"{c['id']} is {c['method']}, but {req} is {requirements[req][0]}",
                )

    def test_every_scored_blocker_names_a_playbook(self) -> None:
        for c in self.checks:
            if c["severity"] == "BLOCKER" and c["scored"]:
                self.assertTrue(c["playbooks"], f"{c['id']} is a scored BLOCKER with no playbook")

    def test_the_traceability_page_matches_the_catalogue(self) -> None:
        rows = traceability_rows()
        self.assertEqual(set(rows), set(self.by_id), "the traceability table and the catalogue list different checks")
        for check_id, reqs in rows.items():
            self.assertEqual(reqs, set(self.by_id[check_id]["req_ids"]), f"{check_id}: traceability.md differs")


if __name__ == "__main__":
    unittest.main()
