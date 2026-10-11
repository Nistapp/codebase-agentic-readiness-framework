# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""SEC security-hygiene checks against their one-defect fixtures.

`SEC-01` and `SEC-02` read git's tracked-file set, so their fixtures are copied into a temporary git
repository created inside the test's own temp directory — never the audit repo. The same fixtures
are also exercised *without* git to prove the tracked half degrades to `UNKNOWN`, never `PASS`.

The `SEC-02` fixture carries a clearly synthetic value; a test asserts that value never reaches the
report, only the path and line.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402
from audit.rules.checks.sec import _CODE_SUFFIXES, _line_is_secret, _looks_secret_value, _scan_secrets  # noqa: E402
from audit.scan import build_inventory  # noqa: E402

#: fixture directory -> (check id under test, expected verdict, needs git, force-add .env)
FIXTURES: dict[str, tuple[str, str, bool, bool]] = {
    "sec-01-tracked-env": ("SEC-01", "FAIL", True, True),
    "sec-02-key-shaped": ("SEC-02", "FAIL", True, False),
    "sec-03-thin-ignore": ("SEC-03", "FAIL", False, False),
}

SEC_CHECKS = ("SEC-01", "SEC-02", "SEC-03")

#: The synthetic value in `sec-02-key-shaped/config.py`. Deliberately not a usable credential.
SYNTHETIC_SECRET = "sk-0123456789abcdefghij"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


class SecFixtureTests(unittest.TestCase):
    def _prepare(self, name: str, *, git: bool, force_env: bool = False) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / name
        shutil.copytree(support.fixture(name), target)
        if git:
            self.assertEqual(_git(target, "init").returncode, 0)
            self.assertEqual(_git(target, "add", "-A").returncode, 0)
            if force_env:
                # `.env` is ignored by the compiled-in rule; force-add it so the tracked blocker
                # exists regardless of the ignore rules SEC-03 checks.
                self.assertEqual(_git(target, "add", "-f", ".env").returncode, 0)
        return target

    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected, needs_git, force_env) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(self._prepare(name, git=needs_git, force_env=force_env))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in SEC_CHECKS if verdicts[cid] == "FAIL")
                expected_failing = [check] if expected == "FAIL" else []
                self.assertEqual(failing, expected_failing, f"{name}: unexpected SEC FAILs {failing}")

    def test_sec_01_ok_passes_all_three(self):
        report = support.run_audit(self._prepare("sec-01-ok", git=True))
        verdicts = support.verdicts(report)
        for check in SEC_CHECKS:
            self.assertEqual(verdicts[check], "PASS", f"sec-01-ok: {check}")

    def test_tracked_state_unavailable_degrades_to_unknown_not_pass(self):
        report = support.run_audit(self._prepare("sec-01-tracked-env", git=False))
        self.assertEqual(
            support.verdicts(report)["SEC-01"], "UNKNOWN", "without git the tracked .env cannot be ruled out"
        )


class Sec02ReportHygieneTests(unittest.TestCase):
    def _prepare(self, name: str, *, git: bool) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / name
        shutil.copytree(support.fixture(name), target)
        if git:
            self.assertEqual(_git(target, "init").returncode, 0)
            self.assertEqual(_git(target, "add", "-A").returncode, 0)
        return target

    def test_the_matched_value_never_reaches_the_report(self):
        report = support.run_audit(self._prepare("sec-02-key-shaped", git=True))
        self.assertNotIn(SYNTHETIC_SECRET, json.dumps(report), "SEC-02 leaked the matched value into the report")

        findings = [f for f in report["findings"] if f["check"] == "SEC-02"]
        self.assertTrue(findings, "SEC-02 failed without emitting a finding")
        for finding in findings:
            for evidence in finding["evidence"]:
                self.assertTrue(evidence["path"])
                self.assertIsNotNone(evidence["line"])
                self.assertNotIn(SYNTHETIC_SECRET, evidence.get("note") or "")

    def test_whole_inventory_fallback_is_stated_when_git_is_absent(self):
        report = support.run_audit(self._prepare("sec-02-key-shaped", git=False))
        check = next(c for c in report["checks"] if c["id"] == "SEC-02")
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("tracked state unavailable", check["data"]["source"])


class Sec03CoverageTests(unittest.TestCase):
    def test_detail_names_covered_and_missing_shapes(self):
        report = support.run_audit(support.fixture("sec-03-thin-ignore"))
        check = next(c for c in report["checks"] if c["id"] == "SEC-03")
        self.assertEqual(check["verdict"], "FAIL")
        self.assertEqual(check["data"]["kind"], "secret_shapes")
        self.assertTrue(check["data"]["missing"], "no missing shapes were named")

    def test_comprehensive_ignore_passes_with_coverage_named(self):
        report = support.run_audit(support.fixture("sec-01-ok"))
        check = next(c for c in report["checks"] if c["id"] == "SEC-03")
        self.assertEqual(check["verdict"], "PASS")
        self.assertEqual(check["data"]["missing"], [])
        self.assertTrue(check["data"]["covered"], "no covered shapes were named")


# Credential-shaped text is built here, at run time, so that no file of this repository holds a literal that a
# scanner would read as one. Nothing below is a usable credential.
KEY = "api" + "_key"
PASS = "pass" + "word"
TOKEN = "to" + "ken"
KEEP = "sec" + "ret"
LITERAL = "Hunter2" * 3


class KeywordValueTests(unittest.TestCase):
    """What a keyword such as `api_key` or `token` is assigned: a literal is a credential, a name is not."""

    def test_a_quoted_literal_is_a_credential_in_code_and_in_configuration(self):
        for in_code in (True, False):
            for quote in ('"', "'"):
                with self.subTest(in_code=in_code, quote=quote):
                    self.assertTrue(_looks_secret_value(f"{quote}{LITERAL}{quote}", in_code=in_code))

    def test_an_unquoted_token_is_a_credential_in_configuration_and_not_in_code(self):
        self.assertTrue(_looks_secret_value(LITERAL, in_code=False))
        self.assertTrue(_looks_secret_value(LITERAL))
        self.assertFalse(_looks_secret_value(LITERAL, in_code=True))

    def test_an_unquoted_value_is_its_first_word(self):
        self.assertTrue(_looks_secret_value(LITERAL + "  # a comment"))
        self.assertFalse(_looks_secret_value("Hunter2 " + LITERAL))

    def test_a_trailing_comma_or_semicolon_is_not_part_of_the_literal(self):
        eleven = "Hunter2Hunt"
        self.assertEqual(len(eleven), 11)
        for tail in (",", ";", ",;"):
            with self.subTest(tail=tail):
                self.assertFalse(_looks_secret_value(eleven + tail))
        self.assertTrue(_looks_secret_value(eleven + "x,"))

    def test_a_bracket_makes_an_unquoted_value_an_expression(self):
        for char in "()[]":
            with self.subTest(char=char):
                self.assertFalse(_looks_secret_value(f"Hunter2Hunter2{char}Hunter2"))
        self.assertTrue(_looks_secret_value("Hunter2Hunter2{Hunter2}"))

    def test_a_reference_to_a_secret_store_or_the_environment_is_not_a_credential(self):
        for reference in (
            "os.environ/PRIMARY_PROVIDER_KEY",
            "${DATABASE_PASSWORD_VALUE}",
            "$DATABASE_PASSWORD_VALUE",
            "{{ secrets.DEPLOY_TOKEN_VALUE }}",
            "<%= ENV_DEPLOY_TOKEN_VALUE %>",
            "%(deploy_token_value)s",
            "process.env.DEPLOY_TOKEN_VALUE",
            "env:DEPLOY_TOKEN_VALUE",
        ):
            for form in (reference, f'"{reference}"', f"'{reference}'"):
                with self.subTest(value=form):
                    self.assertFalse(_looks_secret_value(form))

    def test_a_value_that_only_starts_like_a_reference_is_a_value(self):
        for value in ("os.environment/Abc123Abc123", "environment:Abc123Abc123", "process.environ.Abc123Abc123"):
            with self.subTest(value=value):
                self.assertTrue(_looks_secret_value(f'"{value}"'))

    def test_the_literal_is_twelve_characters_or_more(self):
        self.assertFalse(_looks_secret_value("Abcdefghijk"))
        self.assertTrue(_looks_secret_value("Abcdefghijkl"))
        self.assertFalse(_looks_secret_value('"Abcdefghijk"'))
        self.assertTrue(_looks_secret_value('"Abcdefghijkl"'))

    def test_the_literal_mixes_in_a_capital_a_digit_or_a_symbol(self):
        self.assertFalse(_looks_secret_value("abcdefghijkl"))
        self.assertTrue(_looks_secret_value("abcdefghijk1"))
        self.assertTrue(_looks_secret_value("abcdefghijkL"))
        self.assertTrue(_looks_secret_value("abcdefghij-k"))
        self.assertFalse(_looks_secret_value("abcdefghij kl"))
        self.assertFalse(_looks_secret_value('"abcdefghijkl"'))

    def test_a_raw_bytes_or_unicode_prefix_leaves_a_literal_and_an_f_prefix_makes_an_expression(self):
        for prefix in ("r", "R", "b", "B", "u", "U", "rb", "Rb", "bR", "BR"):
            with self.subTest(prefix=prefix):
                self.assertTrue(_looks_secret_value(f'{prefix}"{LITERAL}"', in_code=True))
        for prefix in ("f", "F", "fr", "Rf", "rF"):
            with self.subTest(prefix=prefix):
                self.assertFalse(_looks_secret_value(f"{prefix}'{LITERAL}'", in_code=True))
        self.assertFalse(_looks_secret_value(f'xyz"{LITERAL}"', in_code=True))

    def test_the_first_quote_ends_the_literal_and_an_open_quote_runs_to_the_end(self):
        self.assertFalse(_looks_secret_value(f"'short' {LITERAL}"))
        self.assertTrue(_looks_secret_value(f'"{LITERAL}'))
        self.assertTrue(_looks_secret_value(f"'{LITERAL} and more words'"))

    def test_an_empty_quoted_value_ends_at_its_own_closing_quote(self):
        self.assertFalse(_looks_secret_value('"" + ' + LITERAL + ' + "x"'))
        self.assertFalse(_looks_secret_value("'' or " + LITERAL + " or 'x'"))

    def test_an_open_quote_keeps_every_character_to_the_end_of_the_value(self):
        self.assertTrue(_looks_secret_value('"Abcdefghijkl'))
        self.assertFalse(_looks_secret_value('"Abcdefghijk'))

    def test_nothing_assigned_is_not_a_credential(self):
        for value in ("", "   ", '""', "''"):
            with self.subTest(value=value):
                self.assertFalse(_looks_secret_value(value))


class KeywordLineTests(unittest.TestCase):
    def test_each_keyword_assigned_a_quoted_literal_with_each_separator_is_a_credential(self):
        for keyword in (KEY, PASS, TOKEN, KEEP, "api-key", "passwd", "pwd"):
            for separator in ("=", ": ", " = ", " := ", ":"):
                with self.subTest(keyword=keyword, separator=separator):
                    self.assertTrue(_line_is_secret(f'{keyword}{separator}"{LITERAL}"', in_code=True))

    def test_a_comparison_is_not_an_assignment(self):
        self.assertFalse(_line_is_secret(f'if {TOKEN} == "{LITERAL}":', in_code=True))

    def test_the_value_is_read_to_the_end_of_the_line_so_that_a_quoted_phrase_counts(self):
        self.assertTrue(_line_is_secret(f'{PASS} = "{LITERAL} {LITERAL}"', in_code=True))

    def test_an_expression_assigned_in_source_is_not_a_credential(self):
        self.assertFalse(_line_is_secret(f"{TOKEN} = match.group(1) or settings.default_name", in_code=True))
        self.assertFalse(
            _line_is_secret(f"{PASS} = settings.get('db_value') or os.environ['APP_DB_VALUE']", in_code=True)
        )
        self.assertFalse(_line_is_secret(f"{KEY} = self.config.provider_name_long", in_code=True))

    def test_a_line_is_read_as_configuration_unless_it_is_said_to_be_code(self):
        self.assertTrue(_line_is_secret(f"{PASS}={LITERAL}"))
        self.assertFalse(_line_is_secret(f"{PASS}={LITERAL}", in_code=True))

    def test_a_shape_fires_in_code_and_in_configuration(self):
        shape = "sk" + "-" + "a1" * 10
        for in_code in (True, False):
            with self.subTest(in_code=in_code):
                self.assertTrue(_line_is_secret(f"endpoint = {shape}", in_code=in_code))

    def test_a_line_without_the_keyword_assigned_is_not_a_credential(self):
        for line in (f"{TOKEN}", f"the {TOKEN} is long", f"{TOKEN}_hash: {LITERAL}", "id-token: write", ""):
            with self.subTest(line=line):
                self.assertFalse(_line_is_secret(line))


class KeywordScanTests(unittest.TestCase):
    def hits(self, files: dict[str, str]) -> list[tuple[str, int]]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                support.write(root, rel, text)
            return _scan_secrets(build_inventory(root), None)[1]

    def test_an_unquoted_value_is_a_credential_in_configuration_scripts_and_documents_not_in_source(self):
        line = f"{PASS}={LITERAL}\n"
        for name in ("settings.properties", "deploy.sh", "notes.md", ".env.test", "config.yaml", "x.ini"):
            with self.subTest(file=name):
                self.assertEqual(self.hits({name: line}), [(name, 1)])
        for suffix in _CODE_SUFFIXES:
            with self.subTest(suffix=suffix):
                self.assertEqual(self.hits({f"module{suffix}": line}), [])

    def test_the_tracked_set_decides_what_is_scanned_and_is_named(self):
        line = f"{PASS}={LITERAL}\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(root, "a.properties", line)
            support.write(root, "b.properties", line)
            inventory = build_inventory(root)
            self.assertEqual(_scan_secrets(inventory, {"a.properties"}), ("tracked text files", [("a.properties", 1)]))
            self.assertEqual(
                _scan_secrets(inventory, None),
                ("whole inventory (tracked state unavailable)", [("a.properties", 1), ("b.properties", 1)]),
            )
            self.assertEqual(_scan_secrets(inventory, set()), ("tracked text files", []))

    def test_a_template_file_and_a_placeholder_line_are_not_scanned_for_a_credential(self):
        line = f"{PASS}={LITERAL}\n"
        self.assertEqual(self.hits({"settings.properties.example": line, "x.sample": line}), [])
        self.assertEqual(self.hits({"a.properties": f"{PASS}=Your_Hunter2Hunter2\n"}), [])

    def test_a_quoted_literal_is_a_credential_in_source_too(self):
        for suffix in _CODE_SUFFIXES:
            with self.subTest(suffix=suffix):
                self.assertEqual(self.hits({f"module{suffix}": f'{PASS} = "{LITERAL}"\n'}), [(f"module{suffix}", 1)])

    def test_source_in_a_test_directory_is_still_source(self):
        self.assertEqual(self.hits({"tests/test_x.py": f"{TOKEN} = a.b(c)\n"}), [])
        self.assertEqual(self.hits({"tests/data.properties": f"{TOKEN}={LITERAL}\n"}), [("tests/data.properties", 1)])

    def test_the_code_suffixes_are_the_languages_the_scanner_calls_source(self):
        self.assertEqual(
            sorted(_CODE_SUFFIXES),
            sorted(
                [
                    ".py",
                    ".js",
                    ".jsx",
                    ".mjs",
                    ".cjs",
                    ".ts",
                    ".tsx",
                    ".java",
                    ".kt",
                    ".scala",
                    ".go",
                    ".rs",
                    ".rb",
                    ".cs",
                    ".php",
                    ".swift",
                    ".c",
                    ".h",
                    ".cc",
                    ".cpp",
                    ".hpp",
                ]
            ),
        )


class Sec02FalsePositiveFixtureTests(unittest.TestCase):
    def test_names_and_lookups_assigned_in_source_pass(self):
        report = support.run_audit(support.fixture("sec-02-expression-assignment"))
        self.assertEqual(support.verdicts(report)["SEC-02"], "PASS")
        self.assertEqual([f for f in report["findings"] if f["check"] == "SEC-02"], [])

    def test_references_to_the_environment_and_a_secret_store_pass(self):
        report = support.run_audit(support.fixture("sec-02-env-reference"))
        self.assertEqual(support.verdicts(report)["SEC-02"], "PASS")
        self.assertEqual([f for f in report["findings"] if f["check"] == "SEC-02"], [])


if __name__ == "__main__":
    unittest.main()
