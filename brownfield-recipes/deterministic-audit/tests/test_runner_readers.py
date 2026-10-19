# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""How each verb runner is read: the spellings of ``format:check``, Gradle's built-in tasks and Maven's plugins.

The spellings are the spec's (``spec/command-surface.md``, "Spelling per runner"). S1.2 found three gaps between
that table and the engine: the aliases never resolved, Gradle's ``test`` and ``check`` were not seen, and the
Maven reader turned every ``<goal>`` into a verb. Each test below is one row of the table, or one of the gaps.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks._common import resolve_all_verbs, resolve_verbs, runner_commands  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack  # noqa: E402


def read(files: dict[str, str]):
    """``(verbs, runner_commands)`` for a directory that holds ``files``."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        inventory = build_inventory(root)
        stack = detect_stack(inventory)
        return resolve_verbs(inventory, stack), dict(runner_commands(inventory))


def verbs_of(files: dict[str, str]) -> dict[str, str]:
    verbs, _ = read(files)
    return {verb: f"{binding.runner}: {binding.command}" for verb, binding in verbs.items()}


class FormatCheckSpellingTests(unittest.TestCase):
    def test_a_pyproject_task_runner_spells_it_format_check(self):
        toml = '[tool.poe.tasks]\nformat-check = "ruff format --check ."\n'
        self.assertEqual(verbs_of({"pyproject.toml": toml}), {"format:check": "pyproject.toml: ruff format --check ."})

    def test_a_taskfile_spells_it_with_the_colon(self):
        text = "version: '3'\ntasks:\n  format:check:\n    cmds:\n      - prettier --check .\n"
        self.assertEqual(verbs_of({"Taskfile.yml": text}), {"format:check": "Taskfile.yml: prettier --check ."})

    def test_a_taskfile_with_the_yaml_extension_is_read_too(self):
        text = "version: '3'\ntasks:\n  lint:\n    cmd: eslint .\n"
        self.assertEqual(verbs_of({"Taskfile.yaml": text}), {"lint": "Taskfile.yaml: eslint ."})

    def test_gradle_spells_it_format_check_in_camel_case(self):
        build = "tasks.register('formatCheck') {\n}\n"
        self.assertEqual(
            verbs_of({"build.gradle": build, "gradlew": "#!/bin/sh\n"}),
            {"format:check": "build.gradle: ./gradlew formatCheck"},
        )

    def test_a_kotlin_gradle_build_spells_it_the_same_way(self):
        build = 'tasks.register("formatCheck") {\n}\n'
        self.assertEqual(
            verbs_of({"build.gradle.kts": build}), {"format:check": "build.gradle.kts: gradle formatCheck"}
        )

    def test_an_alias_is_not_taken_from_another_runners_table(self):
        self.assertEqual(verbs_of({"package.json": '{"scripts": {"format-check": "prettier --check ."}}'}), {})
        self.assertEqual(verbs_of({"build.gradle": "tasks.register('format-check') {\n}\n"}), {})
        self.assertEqual(verbs_of({"pyproject.toml": '[tool.poe.tasks]\nformatCheck = "x"\n'}), {})
        self.assertEqual(verbs_of({"Makefile": "formatCheck:\n\tx\n"}), {})

    def test_the_verbs_own_name_is_accepted_beside_the_alias_on_a_runner_that_can_spell_it(self):
        build = "tasks.register('format:check') {\n}\n"
        self.assertEqual(verbs_of({"build.gradle": build}), {"format:check": "build.gradle: gradle format:check"})

    def test_the_alias_is_returned_under_the_verbs_name_beside_its_own(self):
        _, commands = read({"Makefile": "format-check:\n\truff format --check .\n"})
        self.assertEqual(
            commands["Makefile"], {"format-check": "ruff format --check .", "format:check": "ruff format --check ."}
        )


class GradleTests(unittest.TestCase):
    def lifecycle(self, build: str, name: str = "build.gradle") -> dict[str, str]:
        return verbs_of({name: build, "gradlew": "#!/bin/sh\n"})

    def test_the_java_plugin_gives_a_build_test_and_check(self):
        for build in (
            "plugins {\n    id 'java'\n}\n",
            'plugins {\n    id("java")\n}\n',
            "plugins {\n    id  'java-library'\n}\n",
            "apply plugin: 'java'\n",
            "apply plugin: 'application'\n",
            "plugins {\n    id 'groovy'\n}\n",
            "plugins {\n    id 'scala'\n}\n",
            "plugins {\n    id 'war'\n}\n",
            "plugins {\n    id 'io.quarkus'\n}\n",
            "plugins {\n    id 'org.jetbrains.kotlin.jvm' version '2.0.0'\n}\n",
            'plugins {\n    kotlin("jvm") version "2.0.0"\n}\n',
            "plugins {\n    java\n}\n",
            "plugins {\n    `java-library`\n}\n",
            "plugins {\n    application\n}\n",
            "plugins {\n    id 'com.diffplug.spotless' version '6'\n    id 'java'\n}\n",
        ):
            with self.subTest(build=build):
                self.assertEqual(
                    self.lifecycle(build),
                    {"test": "build.gradle: ./gradlew test", "check": "build.gradle: ./gradlew check"},
                )

    def test_a_build_with_no_plugin_that_registers_them_has_neither(self):
        for build in (
            "plugins {\n    id 'com.diffplug.spotless' version '6'\n}\n",
            "plugins {\n    id 'base'\n}\n",
            "dependencies {\n    java\n}\n",
            "repositories {\n    mavenCentral()\n}\n",
            "",
        ):
            with self.subTest(build=build):
                self.assertEqual(self.lifecycle(build), {})

    def test_a_kotlin_build_file_is_read_the_same_way(self):
        self.assertEqual(
            self.lifecycle('plugins {\n    id("java")\n}\n', "build.gradle.kts"),
            {"test": "build.gradle.kts: ./gradlew test", "check": "build.gradle.kts: ./gradlew check"},
        )

    def test_without_a_wrapper_the_installed_gradle_is_the_launcher(self):
        self.assertEqual(
            verbs_of({"build.gradle": "plugins {\n    id 'java'\n}\n"}),
            {"test": "build.gradle: gradle test", "check": "build.gradle: gradle check"},
        )

    def test_a_task_the_build_registers_is_the_verb_and_overrides_the_built_in(self):
        build = "plugins {\n    id 'java'\n}\ntasks.register('check') {\n}\ntasks.register('lint') {\n}\n"
        verbs = verbs_of({"build.gradle": build, "gradlew": "#!/bin/sh\n"})
        self.assertEqual(verbs["check"], "build.gradle: ./gradlew check")
        self.assertEqual(verbs["lint"], "build.gradle: ./gradlew lint")
        self.assertEqual(verbs["test"], "build.gradle: ./gradlew test")

    def test_the_built_in_tasks_are_not_a_definition_the_repository_wrote(self):
        _, commands = read({"build.gradle": "plugins {\n    id 'java'\n}\n", "gradlew": "#!/bin/sh\n"})
        self.assertEqual(commands["build.gradle"], {})

    def test_a_build_that_registers_a_task_is_not_given_the_built_ins_it_has_no_plugin_for(self):
        build = "tasks.register('lint') {\n}\n"
        self.assertEqual(verbs_of({"build.gradle": build}), {"lint": "build.gradle: gradle lint"})


class MavenTests(unittest.TestCase):
    @staticmethod
    def pom(*artifacts: str, goals: tuple[str, ...] = ()) -> str:
        plugins = "".join(f"<plugin><artifactId>{a}</artifactId></plugin>" for a in artifacts)
        executions = "".join(f"<execution><goals><goal>{g}</goal></goals></execution>" for g in goals)
        return f"<project><build><plugins>{plugins}</plugins>{executions}</build></project>"

    def test_a_pom_has_the_lifecycle_verbs_with_the_wrapper_when_there_is_one(self):
        self.assertEqual(
            verbs_of({"pom.xml": self.pom(), "mvnw": "#!/bin/sh\n"}),
            {
                "test": "pom.xml: ./mvnw test",
                "typecheck": "pom.xml: ./mvnw compile test-compile",
                "check": "pom.xml: ./mvnw verify",
            },
        )

    def test_without_a_wrapper_the_installed_maven_is_the_launcher(self):
        self.assertEqual(verbs_of({"pom.xml": self.pom()})["check"], "pom.xml: mvn verify")

    def test_each_default_plugin_gives_its_verbs_in_the_specs_spelling(self):
        pom = self.pom("spotless-maven-plugin", "maven-checkstyle-plugin", "dependency-check-maven")
        self.assertEqual(
            verbs_of({"pom.xml": pom, "mvnw": "#!/bin/sh\n"}),
            {
                "format": "pom.xml: ./mvnw spotless:apply",
                "format:check": "pom.xml: ./mvnw spotless:check",
                "lint": "pom.xml: ./mvnw checkstyle:check",
                "typecheck": "pom.xml: ./mvnw compile test-compile",
                "test": "pom.xml: ./mvnw test",
                "check": "pom.xml: ./mvnw verify",
                "security": "pom.xml: ./mvnw org.owasp:dependency-check-maven:check",
            },
        )

    def test_a_plugin_gives_only_its_own_verbs(self):
        verbs = verbs_of({"pom.xml": self.pom("maven-checkstyle-plugin")})
        self.assertEqual(verbs["lint"], "pom.xml: mvn checkstyle:check")
        self.assertNotIn("format", verbs)
        self.assertNotIn("format:check", verbs)
        self.assertNotIn("security", verbs)

    def test_the_artifact_id_may_be_spaced_in_the_xml(self):
        pom = "<project><artifactId>\n  spotless-maven-plugin\n</artifactId></project>"
        self.assertIn("format:check", verbs_of({"pom.xml": pom}))

    def test_a_plugin_named_like_a_default_is_not_the_default(self):
        self.assertNotIn("format", verbs_of({"pom.xml": self.pom("spotless-maven-plugin-fork")}))

    def test_a_goal_is_not_a_verb(self):
        pom = self.pom(goals=("check", "lint", "format", "security"))
        self.assertEqual(
            verbs_of({"pom.xml": pom}),
            {
                "test": "pom.xml: mvn test",
                "typecheck": "pom.xml: mvn compile test-compile",
                "check": "pom.xml: mvn verify",
            },
        )

    def test_the_lifecycle_verbs_are_not_a_definition_the_repository_wrote(self):
        _, commands = read({"pom.xml": self.pom()})
        self.assertEqual(commands["pom.xml"], {})

    def test_the_verbs_of_a_declared_plugin_are_a_definition_the_repository_wrote(self):
        _, commands = read({"pom.xml": self.pom("spotless-maven-plugin"), "mvnw": "#!/bin/sh\n"})
        self.assertEqual(
            commands["pom.xml"], {"format": "./mvnw spotless:apply", "format:check": "./mvnw spotless:check"}
        )


class NestedManifestTests(unittest.TestCase):
    """``Inventory.has`` matches a manifest at any depth; the runner name read must follow it there.

    A monorepo whose only ``package.json`` lives under ``packages/app`` has no manifest at the literal
    name ``"package.json"`` — a caller that cites that literal name as a path is citing one that does not
    exist anywhere in the repository (the defect this leaf fixes).
    """

    def test_a_nested_only_package_json_is_named_by_its_real_path(self):
        verbs, commands = read({"packages/app/package.json": '{"scripts": {"test": "vitest run"}}'})
        self.assertEqual(verbs["test"].runner, "packages/app/package.json")
        self.assertIn("packages/app/package.json", commands)
        self.assertNotIn("package.json", commands)

    def test_the_shallowest_of_two_nested_manifests_is_named(self):
        _, commands = read(
            {
                "apps/web/package.json": '{"scripts": {"test": "jest"}}',
                "apps/web/deep/nested/package.json": '{"scripts": {"test": "mocha"}}',
            }
        )
        self.assertIn("apps/web/package.json", commands)
        self.assertNotIn("apps/web/deep/nested/package.json", commands)

    def test_a_nested_only_makefile_is_named_by_its_real_path(self):
        _, commands = read({"packages/app/Makefile": "check:\n\techo ok\n"})
        self.assertIn("packages/app/Makefile", commands)
        self.assertNotIn("Makefile", commands)

    def test_a_root_manifest_is_unaffected(self):
        """The common case: a root-level manifest's path is already its literal name."""
        _, commands = read({"package.json": '{"scripts": {"test": "vitest run"}}'})
        self.assertIn("package.json", commands)


class ResolutionTests(unittest.TestCase):
    def test_a_verb_on_two_runners_keeps_both_bindings_in_precedence_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "pom.xml", "<project/>")
            support.write(root, "package.json", '{"scripts": {"test": "vitest run"}}')
            inventory = build_inventory(root)
            bindings = resolve_all_verbs(inventory, detect_stack(inventory))
        self.assertEqual(
            [(b.runner, b.command) for b in bindings["test"]], [("package.json", "vitest run"), ("pom.xml", "mvn test")]
        )


class GradleBesideNpmTests(unittest.TestCase):
    def test_a_gradle_backend_beside_an_npm_gate_is_not_a_second_gate(self):
        npm = (
            '{"name":"x","scripts":{"format":"prettier --write .","format:check":"prettier --check .",'
            '"lint":"eslint .","typecheck":"tsc --noEmit","test":"vitest run",'
            '"check":"npm run format:check && npm run typecheck && npm test","security":"npm audit"}}'
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "package.json", npm)
            support.write(root, "build.gradle", "plugins {\n    id 'java'\n}\n")
            report = support.run_audit(root)
        self.assertEqual(support.verdicts(report)["CMD-03"], "PASS")


if __name__ == "__main__":
    unittest.main()
