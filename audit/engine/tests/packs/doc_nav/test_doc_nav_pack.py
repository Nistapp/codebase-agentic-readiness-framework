# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""DOC and NAV checks against their one-defect fixtures.

Each fixture is a minimal repository that fails exactly its DOC/NAV check. `doc-nav-ok` is the
governed fixture: the smallest repository that passes every scored DOC/NAV check. The audit runs as
a subprocess through `tests/support.py`, so the fixtures exercise the real end-to-end path.

`DOC-05` is also run in-process on built repositories, and its prose reader (`_prose`) on its own cases, so
coverage traces both.

`DOC-03` reads git's tracked-file set, so its fixture is copied into a temporary git repository
created inside the test's own temp directory — never the audit repo. Without git the check degrades
to `UNKNOWN`, never `PASS`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402
from audit.rules.checks.nav import LARGE_FILE_BYTES, _jvm_entry, _python_entry  # noqa: E402
from audit.components import detect_components  # noqa: E402
from audit.rules.checks.nav import check_nav01 as CHECK_NAV01  # noqa: E402
from audit.rules.checks.nav import check_nav03 as CHECK_NAV03  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.rules.checks import _prose  # noqa: E402
from audit.rules.checks.doc import _adr_tombstone  # noqa: E402
from audit.rules.checks.doc import check_doc04 as CHECK_DOC04  # noqa: E402
from audit.rules.checks.doc import check_doc05 as CHECK_DOC05  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.stack import detect_stack  # noqa: E402

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "doc-01-empty": ("DOC-01", "PARTIAL"),
    "doc-02-no-style-guide": ("DOC-02", "FAIL"),
    "doc-04-adr-unindexed": ("DOC-04", "PARTIAL"),
    "doc-04-adr-tombstone": ("DOC-04", "PARTIAL"),
    "doc-05-long-sentences": ("DOC-05", "FAIL"),
    "nav-01-no-manifest": ("NAV-01", "UNKNOWN"),
    "nav-01-nested-manifest-only": ("NAV-01", "UNKNOWN"),
    "nav-02-no-entry": ("NAV-02", "FAIL"),
    "nav-02-main-guard-only": ("NAV-02", "FAIL"),
    "nav-03-red-flags": ("NAV-03", "PARTIAL"),
}

DOC_CHECKS = ("DOC-01", "DOC-02", "DOC-03", "DOC-04", "DOC-05")
NAV_SCORED = ("NAV-01", "NAV-02", "NAV-03")
SCORED_CHECKS = DOC_CHECKS + NAV_SCORED


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class DocNavFixtureTests(unittest.TestCase):
    def test_each_fixture_reports_its_documented_verdict(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                self.assertEqual(support.verdicts(report)[check], expected, f"{name}: {check}")

    def test_governed_fixture_passes_every_scored_check(self):
        report = support.run_audit(support.fixture("doc-nav-ok"))
        verdicts = support.verdicts(report)
        for check in SCORED_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"doc-nav-ok: {check}")
        self.assertEqual(verdicts["NAV-04"], "PASS", "doc-nav-ok: NAV-04")

    def test_doc_01_empty_is_partial_not_fail(self):
        report = support.run_audit(support.fixture("doc-01-empty"))
        check = next(c for c in report["checks"] if c["id"] == "DOC-01")
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("no markdown", check["summary"])

    def test_doc_04_unindexed_names_the_missing_index(self):
        report = support.run_audit(support.fixture("doc-04-adr-unindexed"))
        check = next(c for c in report["checks"] if c["id"] == "DOC-04")
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("no index", check["summary"])

    def test_nav_03_reports_the_counts_and_never_fails(self):
        report = support.run_audit(support.fixture("nav-03-red-flags"))
        check = next(c for c in report["checks"] if c["id"] == "NAV-03")
        self.assertEqual(check["verdict"], "PARTIAL")
        for label in ("oversized", "catch-all", "binaries", "minified"):
            self.assertIn(label, check["summary"])

    def test_nav_05_informational_is_reported_without_crashing(self):
        report = support.run_audit(support.fixture("nav-01-no-manifest"))
        verdicts = support.verdicts(report)
        self.assertIn(verdicts["NAV-05"], ("PASS", "PARTIAL", "FAIL", "UNKNOWN"))
        check = next(c for c in report["checks"] if c["id"] == "NAV-05")
        self.assertTrue("method" in check["summary"] or check["data"].get("method"))


class Doc03TrackedStateTests(unittest.TestCase):
    def _prepare(self, *, git: bool, force_add: bool) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "doc-03-tracked-artefacts"
        shutil.copytree(support.fixture("doc-03-tracked-artefacts"), target)
        if git:
            self.assertEqual(_git(target, "init").returncode, 0)
            self.assertEqual(_git(target, "add", "-A").returncode, 0)
            if force_add:
                # The ignore rule keeps the file out of `git add -A`; force-add it so the tracked
                # defect DOC-03 exists regardless of the ignore rules.
                self.assertEqual(_git(target, "add", "-f", "artefacts/notes.md").returncode, 0)
        return target

    def test_tracked_scratch_fails_even_when_ignored(self):
        report = support.run_audit(self._prepare(git=True, force_add=True))
        self.assertEqual(support.verdicts(report)["DOC-03"], "FAIL")

    def test_ignored_and_untracked_scratch_passes(self):
        report = support.run_audit(self._prepare(git=True, force_add=False))
        self.assertEqual(support.verdicts(report)["DOC-03"], "PASS")

    def test_tracked_state_unavailable_degrades_to_unknown_not_pass(self):
        report = support.run_audit(self._prepare(git=False, force_add=False))
        self.assertEqual(
            support.verdicts(report)["DOC-03"], "UNKNOWN", "without git the tracked set cannot be ruled out"
        )


class Nav02JvmEntryTests(unittest.TestCase):
    """`_jvm_entry` on minimal, directly-built inventories — no subprocess, no fixture directory.

    Covers the Quarkus-shaped repository that motivated widening the detector (a build dependency
    on `io.quarkus`, a `@Path`-annotated JAX-RS resource, no literal `main`), alongside the three
    conventions it already recognised, to show the addition is additive rather than a replacement.
    """

    def _inventory(self, files: dict[str, str]):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel, text in files.items():
            support.write(root, rel, text)
        return build_inventory(root)

    def test_java_public_static_void_main_is_found(self):
        inventory = self._inventory(
            {
                "build.gradle": "apply plugin: 'java'\n",
                "src/Main.java": "public class Main {\n    public static void main(String[] args) {}\n}\n",
            }
        )
        self.assertTrue(_jvm_entry(inventory))

    def test_kotlin_fun_main_is_found(self):
        inventory = self._inventory(
            {
                "build.gradle.kts": 'plugins { kotlin("jvm") version "2.0.0" }\n',
                "src/Main.kt": 'fun main() {\n    println("hi")\n}\n',
            }
        )
        self.assertTrue(_jvm_entry(inventory))

    def test_spring_boot_annotation_is_found(self):
        inventory = self._inventory(
            {
                "pom.xml": "<project></project>\n",
                "src/App.java": "@SpringBootApplication\npublic class App {}\n",
            }
        )
        self.assertTrue(_jvm_entry(inventory))

    def test_quarkus_dependency_with_no_main_is_found(self):
        """The defect this change fixes: Quarkus apps have no literal `main` at all — the Quarkus
        runtime is the entry point, declared only as a build dependency."""
        inventory = self._inventory(
            {
                "build.gradle": (
                    "plugins {\n    id 'io.quarkus' version '3.2.10.Final'\n}\n"
                    "dependencies {\n    implementation 'io.quarkus:quarkus-resteasy'\n}\n"
                ),
                "src/RestApplication.java": (
                    "import jakarta.ws.rs.ApplicationPath;\n"
                    "import jakarta.ws.rs.core.Application;\n\n"
                    '@ApplicationPath("/api")\n'
                    "public class RestApplication extends Application {}\n"
                ),
                "src/Greeting.java": (
                    "import jakarta.ws.rs.GET;\nimport jakarta.ws.rs.Path;\n\n"
                    '@Path("/hello")\npublic class Greeting {\n'
                    '    @GET\n    public String hello() { return "hi"; }\n}\n'
                ),
            }
        )
        self.assertTrue(_jvm_entry(inventory))

    def test_quarkus_pom_dependency_with_no_main_is_found(self):
        inventory = self._inventory(
            {
                "pom.xml": (
                    "<project>\n  <dependencies>\n    <dependency>\n"
                    "      <groupId>io.quarkus</groupId>\n"
                    "      <artifactId>quarkus-resteasy</artifactId>\n"
                    "    </dependency>\n  </dependencies>\n</project>\n"
                ),
                "src/RestApplication.java": '@ApplicationPath("/api")\npublic class RestApplication {}\n',
            }
        )
        self.assertTrue(_jvm_entry(inventory))

    def test_quarkus_main_annotation_is_found(self):
        inventory = self._inventory(
            {
                "build.gradle": "plugins {\n    id 'io.quarkus' version '3.2.10.Final'\n}\n",
                "src/Launcher.java": "@QuarkusMain\npublic class Launcher {}\n",
            }
        )
        self.assertTrue(_jvm_entry(inventory))

    def test_a_jvm_manifest_with_no_recognised_signal_is_not_found(self):
        """A plain JVM manifest with none of the recognised conventions — not even `io.quarkus` —
        still finds nothing, the same as before this change."""
        inventory = self._inventory(
            {
                "build.gradle": "apply plugin: 'java'\n",
                "src/Util.java": "public class Util {\n    public static int add(int a, int b) { return a + b; }\n}\n",
            }
        )
        self.assertFalse(_jvm_entry(inventory))


class Nav02PythonEntryTests(unittest.TestCase):
    """`_python_entry` reads `__main__.py`, conventional names and manifest scripts, never a guard alone."""

    GUARD = 'if __name__ == "__main__":\n    main()\n'

    def _entry(self, files: dict[str, str]) -> list[str]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for rel, text in files.items():
            support.write(Path(tmp.name), rel, text)
        return _python_entry(build_inventory(Path(tmp.name)))

    def test_a_guard_line_alone_is_not_an_entry_point(self):
        self.assertEqual(self._entry({"scripts/tool.py": "def main():\n    pass\n\n" + self.GUARD}), [])

    def test_a_guarded_file_counts_through_a_real_signal(self):
        found = self._entry(
            {
                "main.py": "def main():\n    pass\n\n" + self.GUARD,
                "pyproject.toml": '[project.scripts]\ntool = "pkg.cli:main"\n',
            }
        )
        self.assertEqual(found, ["main.py", "pyproject.toml:entry point"])

    def test_a_regex_or_docstring_that_holds_the_guard_text_is_not(self):
        text = (
            'PATTERN = r"if\\s+__name__\\s*==\\s*[\'\\"]__main__[\'\\"]"\n'
            "HINT = \"if __name__ == '__main__'\"\n"
            "# if __name__ == '__main__': in a comment\n"
        )
        self.assertEqual(self._entry({"checks.py": text}), [])


class Nav01ComponentManifestTests(unittest.TestCase):
    """`NAV-01` in-process on built repositories: the Ruby, PHP and .NET manifests declare the root.

    A .NET solution or project file has the project's own name, so it is matched by pattern, and only in the folder
    itself. A named manifest declares the root only when it sits at the root: a nested `tools/x/package.json` does
    not. The UNKNOWN summary names the recognised ecosystems instead of saying the stack is not recognised.
    """

    def nav01(self, files: dict[str, str]) -> tuple[dict, list[str]]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for rel, text in files.items():
            support.write(Path(tmp.name), rel, text)
        inventory = build_inventory(Path(tmp.name))
        components = detect_components(inventory)
        outcome = CHECK_NAV01(
            spec=REGISTRY_BY_ID["NAV-01"],
            target=None,
            inventory=inventory,
            stack=detect_stack(inventory),
            components=components,
            session=None,
        )
        return {"verdict": outcome.verdict.value, "summary": outcome.summary}, components.candidates

    def test_a_ruby_php_or_dotnet_manifest_at_the_root_passes_and_is_named(self):
        for rel in ("Gemfile", "composer.json", "App.sln", "App.slnx", "App.csproj", "App.fsproj", "App.vbproj"):
            with self.subTest(rel=rel):
                check, _ = self.nav01({rel: "{}\n"})
                self.assertEqual(check, {"verdict": "PASS", "summary": f"single-root repository declares {rel}"})

    def test_a_solution_file_is_named_before_a_project_file(self):
        check, _ = self.nav01({"App.csproj": "<Project />\n", "App.sln": "\n"})
        self.assertEqual(check["summary"], "single-root repository declares App.sln")

    def test_a_dotnet_project_file_in_a_subfolder_does_not_declare_the_root(self):
        check, _ = self.nav01({"src/App/App.csproj": "<Project />\n"})
        self.assertEqual(check["verdict"], "UNKNOWN")
        self.assertIn("ecosystems: dotnet", check["summary"])

    def test_a_named_manifest_below_the_root_does_not_declare_the_root(self):
        for rel in ("tools/x/package.json", "tools/x/go.mod", "tools/x/Gemfile", "tools/x/composer.json"):
            with self.subTest(rel=rel):
                check, _ = self.nav01({"README.md": "# x\n", rel: "{}\n"})
                self.assertEqual(check["verdict"], "UNKNOWN")
                self.assertTrue(check["summary"].startswith("no build manifest"), check["summary"])

    def test_a_root_manifest_beside_a_nested_one_names_the_root_file(self):
        check, _ = self.nav01({"tools/x/package.json": "{}\n", "Gemfile": "\n"})
        self.assertEqual(check, {"verdict": "PASS", "summary": "single-root repository declares Gemfile"})

    def test_a_member_manifest_is_read_from_the_member_folder_only(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        files = {
            "settings.gradle": "include 'web'\n",
            "web/README.md": "# web\n",
            "apps/web/build.gradle": "\n",
            "pnpm-workspace.yaml": "packages:\n  - '.tools/*'\n",
            ".tools/lint/package.json": "{}\n",
        }
        for rel, text in files.items():
            support.write(Path(tmp.name), rel, text)
        manifests = {c.path: c.manifest for c in detect_components(build_inventory(Path(tmp.name))).components}
        self.assertIsNone(manifests["web"])
        self.assertEqual(manifests[".tools/lint"], ".tools/lint/package.json")

    def test_a_manifest_that_only_ends_with_a_candidate_path_makes_no_candidate(self):
        check, candidates = self.nav01({"apps/web/README.md": "# web\n", "mirror/apps/web/package.json": "{}\n"})
        self.assertEqual(candidates, [])
        self.assertEqual(check["verdict"], "UNKNOWN")

    def test_a_dotnet_project_under_a_candidate_root_is_a_candidate(self):
        check, candidates = self.nav01({"apps/web/Web.csproj": "<Project />\n", "apps/api/Gemfile": "\n"})
        self.assertEqual(candidates, ["apps/api", "apps/web"])
        self.assertEqual(check["verdict"], "PARTIAL")

    def test_a_recognised_stack_with_no_manifest_the_detector_reads_names_its_ecosystems(self):
        check, _ = self.nav01({"requirements.txt": "requests==2.32.3\n"})
        self.assertEqual(check["verdict"], "UNKNOWN")
        self.assertEqual(
            check["summary"], "no build manifest the component detector reads declares a component; ecosystems: python"
        )

    def test_an_unrecognised_stack_says_so(self):
        check, _ = self.nav01({"README.md": "# x\n"})
        self.assertEqual(
            check, {"verdict": "UNKNOWN", "summary": "no build manifest declares a component; stack not recognised"}
        )


class Nav03LockfileTests(unittest.TestCase):
    """A lockfile over 512 KiB is large by design, so `NAV-03` leaves it out of the size count.

    Each case copies `doc-nav-ok` (which passes `NAV-03`) and adds one file just over the limit. A fixture this
    large is built in the test, never vendored. The match is by exact base name: a near name still counts.
    """

    PADDING = "x" * (LARGE_FILE_BYTES + 1)

    def check(self, rel: str, text: str = PADDING) -> dict:
        """Run `NAV-03` in-process (so coverage traces it) on `doc-nav-ok` plus one file at ``rel``."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nav-03-large-lockfile"
            shutil.copytree(support.fixture("doc-nav-ok"), root)
            support.write(root, rel, text)
            inventory = build_inventory(root)
            outcome = CHECK_NAV03(
                spec=REGISTRY_BY_ID["NAV-03"],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        return {"verdict": outcome.verdict.value, "summary": outcome.summary}

    def test_a_large_lockfile_at_the_root_passes_and_is_named(self):
        check = self.check("package-lock.json")
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("oversized(>524288 B): 0", check["summary"])
        self.assertIn("lockfiles over the size, not counted: 1 (package-lock.json)", check["summary"])

    def test_a_large_lockfile_in_a_subfolder_passes(self):
        self.assertEqual(self.check("services/api/uv.lock")["verdict"], "PASS")

    def test_a_large_file_with_a_near_lockfile_name_still_flags(self):
        for rel in ("data.json", "package-lock.json.orig", "notes/yarn.lock.md", "Package-Lock.json"):
            with self.subTest(rel=rel):
                check = self.check(rel)
                self.assertEqual(check["verdict"], "PARTIAL")
                self.assertIn("oversized(>524288 B): 1", check["summary"])
                self.assertNotIn("lockfiles over the size", check["summary"])

    def test_a_small_lockfile_is_not_named(self):
        check = self.check("package-lock.json", "{}\n")
        self.assertEqual(check["verdict"], "PASS")
        self.assertNotIn("lockfiles", check["summary"])


class Doc04TemplateEntryTests(unittest.TestCase):
    """`0000-template.md` is the blank an ADR is copied from, so it is not a numbered decision."""

    def _doc04(self, files: dict[str, str]) -> dict:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for rel, text in files.items():
            support.write(Path(tmp.name), rel, text)
        report = support.run_audit(Path(tmp.name))
        return next(c for c in report["checks"] if c["id"] == "DOC-04")

    def test_a_template_beside_the_adrs_is_not_counted_or_required_in_the_index(self):
        check = self._doc04(
            {
                "docs/architecture/adrs/0000-template.md": "# NNNN title\n",
                "docs/architecture/adrs/0001-first.md": "# 0001 first\n",
                "docs/architecture/adrs/README.md": "- [0001](0001-first.md)\n",
            }
        )
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("1 ADR(s) indexed", check["summary"])

    def test_a_directory_holding_only_a_template_has_no_numbered_adr(self):
        check = self._doc04({"docs/architecture/adrs/0000-template.md": "# NNNN title\n"})
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("holds no numbered ADR", check["summary"])


class Doc04TombstoneTests(unittest.TestCase):
    """An ADR marked superseded, deprecated or rejected is a tombstone: an agent loads it as a current rule."""

    INDEX = "| [0001](0001-a.md) | A |\n| [0002](0002-b.md) | B |\n"

    def check(self, second: str) -> dict:
        """Run DOC-04 in-process (so coverage traces it) on two indexed ADRs, the second with ``second``."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "docs/adr/0001-a.md", "# 0001. A\n\n## Decision\n\nUse A.\n")
            support.write(root, "docs/adr/0002-b.md", second)
            support.write(root, "docs/adr/README.md", self.INDEX)
            inventory = build_inventory(root)
            outcome = CHECK_DOC04(
                spec=REGISTRY_BY_ID["DOC-04"],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        return {
            "verdict": outcome.verdict.value,
            "summary": outcome.summary,
            "findings": [finding.to_dict() for finding in outcome.findings],
        }

    def test_a_current_adr_set_passes(self):
        check = self.check("# 0002. B\n\n## Decision\n\nUse B.\n")
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["findings"], [])

    def test_a_superseded_status_field_is_partial_and_cites_the_line(self):
        check = self.check("# 0002. B\n\n* **Status:** Superseded by 0001\n")
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("1 ADR(s) marked superseded, deprecated or rejected", check["summary"])
        self.assertEqual(check["findings"][0]["evidence"][0]["path"], "docs/adr/0002-b.md")
        self.assertEqual(check["findings"][0]["evidence"][0]["line"], 3)

    def test_an_unindexed_tombstone_reports_both_findings(self):
        INDEX, self.INDEX = self.INDEX, "| [0001](0001-a.md) | A |\n"
        self.addCleanup(setattr, self, "INDEX", INDEX)
        check = self.check("# 0002. B\n\nStatus: Deprecated\n")
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertEqual(len(check["findings"]), 2)
        self.assertIn("1/2 ADR(s) listed", check["summary"])

    def test_each_retiring_form_is_found(self):
        for text, line in (
            ("Status: Superseded\n", 1),
            ("# T\n\n* **Status:** Deprecated\n", 3),
            ("| Status | Rejected |\n", 1),
            ("---\nstatus: superseded by ADR-0005\n---\n", 2),
            ("# T\n\n## Status\n\nObsolete since the rewrite.\n", 3),
            ("# T\n\n> Superseded by [ADR 0007](0007-x.md)\n", 3),
            ("# T\n\nDeprecated in favour of 0009.\n", 3),
            ("# T\n\nReplaced by 0004.\n", 3),
        ):
            with self.subTest(text=text):
                self.assertEqual(_adr_tombstone(text), line)

    def test_a_current_record_that_discusses_retired_options_is_not_a_tombstone(self):
        for text in (
            "# T\n\n* **Status:** Accepted\n",
            "| Tombstone or superseded ADR stubs | Git is the archive. |\n",
            "| A status lifecycle with superseded records kept | Agents read them as current. |\n",
            "The cache entry is superseded by newer data on each write.\n",
            "## Status\n\nAccepted.\n",
        ):
            with self.subTest(text=text):
                self.assertIsNone(_adr_tombstone(text))


# -- DOC-05: docs are readable, in-process ------------------------------------------------------------

DOC05 = "DOC-05"

SHORT = "The engine reads the file. It reports the result. "
#: 30 words, one sentence.
LONG = (
    "The engine that this repository ships reads every file under the folder that it is given and then writes a "
    "report that the person who asked for it can read later. "
)


def page(short: int, long: int = 0, extra: str = "") -> str:
    return "# Page\n\n" + SHORT * short + "\n\n" + LONG * long + "\n\n" + extra


class Doc05ReadableDocsTests(unittest.TestCase):
    def check(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            inventory = build_inventory(root)
            outcome = CHECK_DOC05(
                spec=REGISTRY_BY_ID[DOC05],
                target=None,
                inventory=inventory,
                stack=detect_stack(inventory),
                components=None,
                session=None,
            )
        return {
            "verdict": outcome.verdict.value,
            "summary": outcome.summary,
            "findings": [finding.to_dict() for finding in outcome.findings],
            "data": outcome.data.to_dict() if outcome.data else None,
        }

    def test_registered_as_a_scored_cosmetic_check(self):
        spec = REGISTRY_BY_ID[DOC05]
        self.assertEqual((spec.severity.value, spec.scored, spec.status), ("COSMETIC", True, "implemented"))

    def test_no_docs_is_unknown(self):
        check = self.check({"README.md": page(10)})
        self.assertEqual(check["verdict"], "UNKNOWN")
        self.assertIn("DOC-01", check["summary"])

    def test_too_little_prose_is_unknown(self):
        check = self.check({"docs/README.md": page(2)})
        self.assertEqual(check["verdict"], "UNKNOWN")
        self.assertIn("4 sentence(s)", check["summary"])

    def test_prose_that_is_not_english_is_unknown(self):
        german = "Der Prüfer liest die Datei und meldet das Ergebnis. Die Seite bleibt kurz. " * 6
        check = self.check({"docs/README.md": "# Seite\n\n" + german})
        self.assertEqual(check["verdict"], "UNKNOWN")
        self.assertIn("does not read as English", check["summary"])

    def test_short_plain_prose_passes_with_its_counts(self):
        check = self.check({"docs/README.md": page(10)})
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["findings"], [])
        self.assertEqual(check["data"]["kind"], "counter")
        self.assertEqual(check["data"]["breakdown"]["sentences"], 20)
        self.assertEqual(check["data"]["breakdown"]["long_sentences"], 0)

    def test_a_long_share_at_the_pass_level_passes(self):
        check = self.check({"docs/README.md": page(9, 2)})
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("2/20 sentences over the limit (10.0%)", check["summary"])

    def test_a_long_share_over_the_pass_level_is_partial(self):
        check = self.check({"docs/README.md": page(8, 4)})
        self.assertEqual(check["verdict"], "PARTIAL")
        finding = check["findings"][0]
        self.assertIn("20.0% of sentences are over 25 words", finding["statement"])
        self.assertEqual({e["note"] for e in finding["evidence"]}, {"long sentence"})

    def test_a_long_share_over_the_fail_level_fails(self):
        check = self.check({"docs/README.md": page(5, 6)})
        self.assertEqual(check["verdict"], "FAIL")

    def test_vague_words_over_the_pass_level_are_partial(self):
        check = self.check({"docs/README.md": page(10, extra="Run it in order to build. It is just fine.\n")})
        self.assertEqual(check["verdict"], "PARTIAL")
        notes = [e["note"] for e in check["findings"][0]["evidence"]]
        self.assertEqual(notes, ["vague: in order to", "vague: just"])

    def test_an_explanation_page_without_a_diagram_is_partial(self):
        files = {"docs/README.md": page(10), "docs/explanation/how-it-works.md": page(2)}
        check = self.check(files)
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertIn("1 explanation or tutorial page(s) have no Mermaid diagram", check["findings"][0]["statement"])
        self.assertEqual(check["findings"][0]["evidence"][0]["path"], "docs/explanation/how-it-works.md")

    def test_a_tutorial_with_a_diagram_and_an_index_without_one_pass(self):
        mermaid = "```mermaid\nflowchart LR\n  A --> B\n```\n"
        files = {
            "docs/README.md": page(10),
            "docs/tutorials/first.md": page(2, extra=mermaid),
            "docs/explanation/README.md": page(2),
        }
        self.assertEqual(self.check(files)["verdict"], "PASS")

    def test_evidence_is_capped(self):
        check = self.check({"docs/README.md": page(1, 20)})
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(len(check["findings"][0]["evidence"]), 8)


class ProseReaderTests(unittest.TestCase):
    def measure(self, text: str, path: str = "docs/x.md") -> _prose.ProseCounts:
        return _prose.measure(path, text)[0]

    def test_code_tables_headings_and_comments_are_not_prose(self):
        text = (
            "# A heading that is long enough to be a very long sentence of more than twenty five words in all of it\n"
            "\n```\n" + LONG + "\n```\n\n| " + LONG + " |\n\n<!-- " + LONG + " -->\n\n"
            "<!--\n" + LONG + "\n-->\n\nOne short sentence.\n"
        )
        counts = self.measure(text)
        self.assertEqual((counts.sentences, counts.long_sentences), (1, 0))

    def test_an_off_region_is_skipped(self):
        text = "<!-- prose-check off -->\n\n" + LONG + "\n\n<!-- prose-check on -->\n\nShort.\n"
        self.assertEqual(self.measure(text).long_sentences, 0)

    def test_a_numbered_step_has_the_lower_limit(self):
        step = "1. Run the command that builds the package and then copy the file it writes into the folder named out on the disk.\n"
        bullet = step.replace("1. ", "- ")
        self.assertEqual(self.measure(step).long_sentences, 1)
        self.assertEqual(self.measure(bullet).long_sentences, 0)

    def test_a_code_span_link_and_url_count_as_one_word_each(self):
        counts = self.measure("Run `make check --all` from [the root page](a/b.md) or https://example.com/x.\n")
        self.assertEqual(counts.words, 8)

    def test_quotes_and_alerts_are_prose(self):
        counts = self.measure("> [!NOTE]\n> " + LONG + "\n")
        self.assertEqual(counts.long_sentences, 1)

    def test_a_mermaid_block_is_seen(self):
        self.assertTrue(_prose.measure("docs/x.md", "```mermaid\nflowchart LR\n```\n")[1])
        self.assertFalse(_prose.measure("docs/x.md", "```text\nflowchart LR\n```\n")[1])

    def test_which_pages_need_a_diagram(self):
        self.assertTrue(_prose.needs_diagram("docs/explanation/a.md"))
        self.assertTrue(_prose.needs_diagram("docs/tutorials/b.md"))
        self.assertFalse(_prose.needs_diagram("docs/explanation/README.md"))
        self.assertFalse(_prose.needs_diagram("docs/how-to/c.md"))

    def test_english_share(self):
        self.assertGreater(_prose.english_share(self.measure(SHORT * 3)), _prose.ENGLISH_MIN_SHARE)
        self.assertEqual(_prose.english_share(_prose.ProseCounts()), 0.0)


if __name__ == "__main__":
    unittest.main()
