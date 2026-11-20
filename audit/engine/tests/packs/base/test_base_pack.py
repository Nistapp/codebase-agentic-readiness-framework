# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""BASE checks against their one-defect fixtures.

Each fixture is a small node project that isolates one baseline/ratchet defect; `base-ok` passes all
four. The isolation invariant the pack tests for is: **exactly one** BASE check returns `FAIL` on
each defect fixture, and the expected check is that one.

`BASE-02` is a `PARTIAL`-only check by design (the audit cannot run the target's tools to prove no
count exists), so its fixture is asserted `PARTIAL` rather than `FAIL`.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.components import detect_components  # noqa: E402
from audit.rules.checks.base import check_base04  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

BASE_CHECKS = ("BASE-01", "BASE-02", "BASE-03", "BASE-04")

#: fixture directory -> (check under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "base-01-no-baseline": ("BASE-01", "FAIL"),
    "base-02-no-count": ("BASE-02", "PARTIAL"),
    "base-03-no-ratchet": ("BASE-03", "FAIL"),
    "base-04-no-coverage-floor": ("BASE-04", "FAIL"),
}


class BaseFixtureTests(unittest.TestCase):
    def test_each_fixture_isolates_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in BASE_CHECKS if verdicts[cid] == "FAIL")
                expected_failing = [check] if expected == "FAIL" else []
                self.assertEqual(failing, expected_failing, f"{name}: unexpected BASE FAILs {failing}")

    def test_positive_fixture_passes_all_four(self):
        report = support.run_audit(support.fixture("base-ok"))
        verdicts = support.verdicts(report)
        for check in BASE_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"base-ok: {check}")


class BaseInlineTests(unittest.TestCase):
    def _scan(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return support.run_audit(root)

    def test_no_ecosystem_is_unknown_not_fail(self):
        report = self._scan({"NOTES.txt": "no build system here\n"})
        verdicts = support.verdicts(report)
        for check in BASE_CHECKS:
            self.assertEqual(verdicts[check], "UNKNOWN", f"unrecognised repo: {check}")

    def test_commented_out_threshold_is_not_coverage_configuration(self):
        report = self._scan(
            {
                "package.json": '{"name": "x", "scripts": {"test": "vitest run"}}',
                "vitest.config.ts": ("export default {\n  test: {\n    // thresholds: { lines: 80 },\n  },\n};\n"),
            }
        )
        self.assertEqual(support.verdicts(report)["BASE-04"], "FAIL")

    def test_ci_baseline_reference_counts_as_ratchet(self):
        report = self._scan(
            {
                "package.json": '{"name": "x", "scripts": {"test": "vitest run"}}',
                "baseline.json": '{"findings": []}\n',
                ".github/workflows/ci.yml": (
                    "on: [pull_request]\njobs:\n  r:\n    steps:\n"
                    "      - run: python3 -m audit . --baseline baseline.json\n"
                ),
                "vitest.config.ts": "export default { test: { coverage: { thresholds: { lines: 80 } } } };\n",
            }
        )
        self.assertEqual(support.verdicts(report)["BASE-03"], "PASS")

    def test_documented_baseline_satisfies_base01(self):
        report = self._scan(
            {
                "package.json": '{"name": "x", "scripts": {"test": "vitest run"}}',
                "AGENTS.md": "# Rules\n\nA quality baseline file records current violations.\n",
                "vitest.config.ts": "export default { test: { coverage: { thresholds: { lines: 80 } } } };\n",
            }
        )
        self.assertEqual(support.verdicts(report)["BASE-01"], "PASS")


GRADLE_GROOVY = """plugins { id 'jacoco' }
jacocoTestCoverageVerification {
    violationRules {
        rule {
            limit {
                minimum = 0.80
            }
        }
    }
}
"""
GRADLE_KOTLIN = """plugins { jacoco }
tasks.jacocoTestCoverageVerification {
    violationRules {
        rule { limit { minimum = "0.80".toBigDecimal() } }
    }
}
"""
POM_JACOCO = """<project>
  <build><plugins><plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <executions><execution>
      <id>check</id>
      <goals><goal>check</goal></goals>
      <configuration><rules><rule><limits><limit>
        <counter>LINE</counter><value>COVEREDRATIO</value><minimum>0.80</minimum>
      </limit></limits></rule></rules></configuration>
    </execution></executions>
  </plugin></plugins></build>
</project>
"""


class Base04BuildFileFloorTests(unittest.TestCase):
    """BASE-04 reads a JaCoCo floor in a Gradle or Maven build and a Jest floor in any package.json (issue #45)."""

    def base04(self, files: dict[str, str]):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            inventory = build_inventory(root)
            outcome = check_base04(
                spec=REGISTRY_BY_ID["BASE-04"],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=detect_components(inventory),
                session=None,
            )
        return outcome.verdict.value, outcome.summary

    def test_a_jacoco_floor_in_a_gradle_build_passes(self):
        for name, text in (("build.gradle", GRADLE_GROOVY), ("build.gradle.kts", GRADLE_KOTLIN)):
            for rel in (name, f"server/{name}"):
                with self.subTest(rel=rel):
                    self.assertEqual(self.base04({rel: text}), ("PASS", f"coverage threshold configured: {rel}"))

    def test_a_jacoco_check_goal_in_a_maven_build_passes(self):
        for rel in ("pom.xml", "server/pom.xml"):
            with self.subTest(rel=rel):
                self.assertEqual(self.base04({rel: POM_JACOCO}), ("PASS", f"coverage threshold configured: {rel}"))

    def test_jacoco_without_a_minimum_is_no_floor(self):
        gradle = "plugins { id 'jacoco' }\njacocoTestCoverageVerification {\n    // minimum = 0.80\n}\n"
        self.assertEqual(self.base04({"build.gradle": gradle})[0], "FAIL")
        pom = POM_JACOCO.replace("<minimum>0.80</minimum>", "<!-- <minimum>0.80</minimum> -->")
        self.assertEqual(self.base04({"pom.xml": pom})[0], "FAIL")
        report_only = POM_JACOCO.replace("<goal>check</goal>", "<goal>report</goal>")
        self.assertEqual(self.base04({"pom.xml": report_only})[0], "FAIL")

    def test_a_coverage_threshold_in_an_app_package_json_passes(self):
        manifest = '{"name": "web", "jest": {"coverageThreshold": {"global": {"lines": 80}}}}\n'
        self.assertEqual(
            self.base04({"web/package.json": manifest, "api/package.json": '{"name": "api"}\n'}),
            ("PASS", "coverage threshold configured: web/package.json"),
        )


if __name__ == "__main__":
    unittest.main()
