# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""EXEC-03 and EXEC-04 in a repository whose apps live below the root (issues #7, #52 and #56).

A framework keeps its Dockerfile below the root (Quarkus writes ``src/main/docker/Dockerfile.jvm``), and an app per
folder keeps its own ``.env.example``. The checks run in-process, so coverage traces them.
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
from audit.rules.checks.execution import check_exec03, check_exec04  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

GRADLE = "plugins { id 'java' }\n"


def _run(check, check_id: str, files: dict[str, str]):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        inventory = build_inventory(root)
        return check(
            spec=REGISTRY_BY_ID[check_id],
            target=None,
            inventory=inventory,
            stack=detect_stack(inventory),
            components=detect_components(inventory),
            session=None,
        )


class Exec03DockerfileBelowTheRootTests(unittest.TestCase):
    def exec03(self, files: dict[str, str]):
        return _run(check_exec03, "EXEC-03", files)

    def test_a_quarkus_dockerfile_below_the_root_is_a_setup_file(self):
        outcome = self.exec03({"build.gradle": GRADLE, "src/main/docker/Dockerfile.jvm": "FROM eclipse-temurin\n"})
        self.assertEqual(outcome.verdict.value, "PARTIAL")
        self.assertEqual(outcome.summary, "present but undocumented: src/main/docker/Dockerfile.jvm")
        self.assertEqual([e.path for e in outcome.findings[0].evidence], ["src/main/docker/Dockerfile.jvm"])

    def test_a_named_variant_dockerfile_passes_when_a_doc_names_it(self):
        for name in ("Dockerfile.dev", "dev.Dockerfile", "api.dockerfile"):
            with self.subTest(name=name):
                outcome = self.exec03(
                    {"build.gradle": GRADLE, f"api/{name}": "FROM node\n", "README.md": f"# App\n\nBuild {name}.\n"}
                )
                self.assertEqual(outcome.verdict.value, "PASS")
                self.assertEqual(outcome.summary, f"documented setup artifact: api/{name}")

    def test_a_file_that_only_mentions_docker_is_no_setup_file(self):
        outcome = self.exec03({"build.gradle": GRADLE, "docs/docker-notes.md": "# Docker\n"})
        self.assertEqual(outcome.verdict.value, "FAIL")


class Exec04ExampleFileBelowTheRootTests(unittest.TestCase):
    def exec04(self, files: dict[str, str]):
        outcome = _run(check_exec04, "EXEC-04", files)
        return outcome.verdict.value, list(outcome.data.missing), list(outcome.data.templates)

    def test_an_example_file_in_the_app_folder_declares_the_keys_that_app_reads(self):
        verdict, missing, templates = self.exec04(
            {
                "web/src/index.js": "process.env.WEB_SECRET;\n",
                "web/.env.example": "WEB_SECRET=\n",
                "scripts/ci/run.sh": 'echo "${CI_DEPLOY_TOKEN}"\n',
                "scripts/ci/env.example": "CI_DEPLOY_TOKEN=\n",
            }
        )
        self.assertEqual((verdict, missing), ("PASS", []))
        self.assertEqual(templates, ["web/.env.example", "scripts/ci/env.example"])

    def test_an_example_file_in_a_sibling_folder_does_not_declare_a_key(self):
        verdict, missing, _ = self.exec04(
            {"api/src/index.js": "process.env.API_SECRET;\n", "web/.env.example": "API_SECRET=\n"}
        )
        self.assertEqual((verdict, missing), ("FAIL", ["API_SECRET"]))

    def test_a_root_example_file_declares_a_key_for_every_folder(self):
        verdict, missing, templates = self.exec04(
            {"api/src/index.js": "process.env.API_SECRET;\n", ".env.example": "API_SECRET=\n"}
        )
        self.assertEqual((verdict, missing, templates), ("PASS", [], [".env.example"]))

    def test_a_key_read_in_two_apps_needs_an_example_file_for_each(self):
        files = {
            "api/src/index.js": "process.env.SHARED_URL;\n",
            "web/src/index.js": "process.env.SHARED_URL;\n",
            "api/.env.example": "SHARED_URL=\n",
        }
        verdict, missing, _ = self.exec04(files)
        self.assertEqual((verdict, missing), ("FAIL", ["SHARED_URL"]))
        verdict, missing, _ = self.exec04({**files, "web/.env.example": "SHARED_URL=\n"})
        self.assertEqual((verdict, missing), ("PASS", []))

    def test_the_summary_names_the_example_files_it_read(self):
        outcome = _run(
            check_exec04, "EXEC-04", {"api/src/index.js": "process.env.API_SECRET;\n", "web/.env.example": "X=\n"}
        )
        self.assertEqual(
            outcome.summary,
            "1 referenced key(s) are absent from every example file that covers the files reading them "
            "(web/.env.example): API_SECRET",
        )


if __name__ == "__main__":
    unittest.main()
