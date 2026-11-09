# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The dev tool versions live in three manifests only: ``dev/tools/pyproject.toml``, ``dev/tools/package.json`` and,
for osv-scanner, the Go module ``dev/tools/osv/go.mod``.

Dependabot reads those files and their lockfiles (``.github/dependabot.yml``). A version that is also written
somewhere else would not move with a Dependabot pull request, so these tests fail when a pin is not exact, when a
lockfile disagrees with its manifest, or when a file that runs a tool repeats its version.
"""

from __future__ import annotations

import datetime
import json
import re
import shutil
import subprocess
import tomllib
import unittest

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
from _dev_paths import REPO

TOOLS = REPO / "dev" / "tools"
TOOL_PINS = TOOLS / "pyproject.toml"
TOOL_LOCK = TOOLS / "uv.lock"
NODE_PINS = TOOLS / "package.json"
NODE_LOCK = TOOLS / "package-lock.json"
GO_MOD = TOOLS / "osv" / "go.mod"
GO_SUM = TOOLS / "osv" / "go.sum"
OSV_CONFIG = TOOLS / "osv-scanner.toml"
OSV_MODULE = "github.com/google/osv-scanner/v2"
EXACT_GO = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
#: The longest an accepted vulnerability may stay accepted before someone looks again.
MAX_IGNORE_DAYS = 183

# The files that run a dev tool. Each one must read the version from a manifest, never write it.
CONSUMERS = [
    "Makefile",
    "lefthook.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/workflows/release-please.yml",
    ".quality-baseline.json",
    "dev/mermaid_check.py",
    "dev/crosscheck_jsonschema.py",
    "audit/schema/SCHEMA.md",
]

REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[0-9][0-9A-Za-z.+-]*)$")
EXACT_NPM = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$")


def python_pins() -> dict[str, str]:
    data = tomllib.loads(TOOL_PINS.read_text(encoding="utf-8"))
    pins: dict[str, str] = {}
    for line in data["dependency-groups"]["tools"]:
        match = REQUIREMENT.match(line)
        if match is None:
            raise AssertionError(f"{TOOL_PINS.name}: not an exact pin: {line!r}")
        pins[match["name"]] = match["version"]
    return pins


def node_pins() -> dict[str, str]:
    data = json.loads(NODE_PINS.read_text(encoding="utf-8"))
    pins: dict[str, str] = data["devDependencies"]
    return pins


class ManifestsHoldExactPins(unittest.TestCase):
    def test_every_python_pin_is_exact(self) -> None:
        pins = python_pins()
        for tool in ("ruff", "mypy", "detect-secrets", "coverage", "jsonschema", "skills-ref", "typos", "uv"):
            self.assertIn(tool, pins)

    def test_every_node_pin_is_exact(self) -> None:
        pins = node_pins()
        self.assertEqual(set(pins), {"markdownlint-cli2", "@mermaid-js/mermaid-cli"})
        for name, version in pins.items():
            self.assertRegex(version, EXACT_NPM, f"{name} is not an exact version")

    def test_python_project_installs_nothing(self) -> None:
        data = tomllib.loads(TOOL_PINS.read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["dependencies"], [])

    def test_node_manifest_has_no_runtime_dependencies(self) -> None:
        data = json.loads(NODE_PINS.read_text(encoding="utf-8"))
        self.assertTrue(data.get("private"))
        self.assertNotIn("dependencies", data)


class LockfilesAgreeWithTheManifests(unittest.TestCase):
    """A pin changed without a new lockfile fails here. Fix: `uv lock --directory dev/tools`, or
    `npm install --package-lock-only --ignore-scripts` in dev/tools."""

    def test_uv_lock_records_the_pins(self) -> None:
        lock = tomllib.loads(TOOL_LOCK.read_text(encoding="utf-8"))
        root = next(p for p in lock["package"] if p.get("source", {}).get("virtual") == ".")
        recorded = {d["name"]: d["specifier"] for d in root["metadata"]["requires-dev"]["tools"]}
        self.assertEqual(recorded, {name: f"=={version}" for name, version in python_pins().items()})
        locked = {p["name"]: p["version"] for p in lock["package"] if "version" in p}
        for name, version in python_pins().items():
            self.assertEqual(locked.get(name), version, f"uv.lock holds another {name}")

    def test_package_lock_records_the_pins(self) -> None:
        lock = json.loads(NODE_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(lock["packages"][""]["devDependencies"], node_pins())
        for name, version in node_pins().items():
            self.assertEqual(lock["packages"][f"node_modules/{name}"]["version"], version)


def go_requirements() -> dict[str, str]:
    """``module -> version`` for each ``require`` line of the osv-scanner tool module."""
    text = GO_MOD.read_text(encoding="utf-8")
    block = re.search(r"^require \((.*?)^\)", text, re.S | re.M)
    lines = block.group(1).splitlines() if block else []
    lines += [m.group(1) for m in re.finditer(r"^require (\S+ \S+)", text, re.M)]
    requirements: dict[str, str] = {}
    for line in lines:
        fields = line.split("//")[0].split()
        if len(fields) == 2:
            requirements[fields[0]] = fields[1]
    return requirements


class GoModulePinsOsvScanner(unittest.TestCase):
    """osv-scanner is a Go program. Its version is a Go `tool` requirement, so Dependabot's gomod entry sees it."""

    def test_go_mod_declares_osv_scanner_as_a_tool(self) -> None:
        text = GO_MOD.read_text(encoding="utf-8")
        self.assertRegex(text, rf"(?m)^tool {re.escape(OSV_MODULE)}/cmd/osv-scanner$")

    def test_osv_scanner_is_an_exact_release(self) -> None:
        version = go_requirements().get(OSV_MODULE)
        self.assertIsNotNone(version, f"{GO_MOD.name} does not require {OSV_MODULE}")
        self.assertRegex(version or "", EXACT_GO, "osv-scanner must be a tagged release, not a pseudo-version")

    def test_go_sum_holds_the_pinned_osv_scanner(self) -> None:
        version = go_requirements()[OSV_MODULE]
        self.assertIn(f"{OSV_MODULE} {version} h1:", GO_SUM.read_text(encoding="utf-8"))


class AcceptedVulnerabilitiesAreReviewed(unittest.TestCase):
    """Each entry of dev/tools/osv-scanner.toml says why, and expires within six months."""

    def entries(self) -> list[dict[str, object]]:
        data = tomllib.loads(OSV_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(set(data) - {"IgnoredVulns"}, set(), "only IgnoredVulns belongs in the config")
        entries: list[dict[str, object]] = data.get("IgnoredVulns", [])
        return entries

    def test_each_entry_has_an_id_a_reason_and_a_date(self) -> None:
        for entry in self.entries():
            with self.subTest(entry=entry.get("id")):
                self.assertIsInstance(entry.get("id"), str)
                self.assertGreaterEqual(len(str(entry.get("reason", "")).strip()), 40, "write a real reason")
                self.assertIsInstance(entry.get("ignoreUntil"), datetime.date)

    def test_no_entry_is_accepted_for_more_than_six_months(self) -> None:
        latest = datetime.date.today() + datetime.timedelta(days=MAX_IGNORE_DAYS)
        for entry in self.entries():
            until = entry["ignoreUntil"]
            assert isinstance(until, datetime.date)
            day = until.date() if isinstance(until, datetime.datetime) else until
            with self.subTest(entry=entry["id"]):
                self.assertLessEqual(day, latest)

    def test_ids_are_unique(self) -> None:
        ids = [entry["id"] for entry in self.entries()]
        self.assertEqual(len(ids), len(set(ids)))


class NoOtherFileRepeatsAVersion(unittest.TestCase):
    def test_consumers_do_not_write_a_pinned_version(self) -> None:
        pins = {**python_pins(), **node_pins()}
        for relative in CONSUMERS:
            text = (REPO / relative).read_text(encoding="utf-8")
            for name, version in pins.items():
                for spelled in (f"{name}@{version}", f"{name}=={version}", f'version: "{version}"'):
                    with self.subTest(file=relative, pin=spelled):
                        self.assertNotIn(spelled, text)


@unittest.skipUnless(shutil.which("make"), "make is not on PATH")
class MakefileReadsTheManifests(unittest.TestCase):
    def dry_run(self, *targets: str) -> str:
        result = subprocess.run(
            ["make", "-n", "-s", "-C", str(REPO), *targets], capture_output=True, text=True, check=True
        )
        return result.stdout

    def test_tool_commands_carry_the_manifest_versions(self) -> None:
        python = python_pins()
        node = node_pins()
        output = self.dry_run("lint", "typecheck", "security", "docs-lint", "coverage", "spell")
        self.assertIn(f"ruff@{python['ruff']}", output)
        self.assertIn(f"mypy@{python['mypy']}", output)
        self.assertIn(f"detect-secrets=={python['detect-secrets']}", output)
        self.assertIn(f"coverage@{python['coverage']}", output)
        self.assertIn(f"typos@{python['typos']}", output)
        self.assertIn(f"markdownlint-cli2@{node['markdownlint-cli2']}", output)

    def test_check_runs_the_spell_check(self) -> None:
        self.assertIn(f"typos@{python_pins()['typos']}", self.dry_run("check"))

    def test_security_audits_every_dev_tool_lockfile(self) -> None:
        output = self.dry_run("security")
        self.assertIn("go -C dev/tools/osv tool osv-scanner scan source", output)
        self.assertIn(f"--config={REPO}/dev/tools/osv-scanner.toml", output)
        for lockfile in (TOOL_LOCK, NODE_LOCK, GO_MOD):
            with self.subTest(lockfile=lockfile.name):
                self.assertIn(f"--lockfile={lockfile}", output)
        self.assertNotIn(go_requirements()[OSV_MODULE], output, "the Makefile must not write the osv-scanner version")

    def test_a_missing_pin_stops_make(self) -> None:
        result = subprocess.run(
            ["make", "-n", "-s", "-C", str(REPO), "lint", "TOOL_PINS=/dev/null"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no pin for ruff", result.stderr)


if __name__ == "__main__":
    unittest.main()
