# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CMD command-surface checks and the deferred AGT-05 against their one-defect fixtures.

Each defect fixture is a minimal repository that fails exactly one `CMD` check; the two `cmd-ok-*`
fixtures prove runner-independence by resolving all seven verbs on, respectively, npm scripts and a
Makefile (spelled three ways: the escaped target, the alias, and a `check` that lists its prerequisites). The audit runs as a subprocess through `tests/support.py`, so the fixtures exercise the
real end-to-end path.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

#: fixture directory -> (check id under test, expected verdict)
FIXTURES: dict[str, tuple[str, str]] = {
    "cmd-01-missing-verb": ("CMD-01", "FAIL"),
    "cmd-01-make-parse-error": ("CMD-01", "FAIL"),
    "cmd-02-weak-check": ("CMD-02", "FAIL"),
    "cmd-03-divergent": ("CMD-03", "FAIL"),
    "cmd-04-write-in-check": ("CMD-04", "FAIL"),
}

CMD_CHECKS = ("CMD-01", "CMD-02", "CMD-03", "CMD-04")

VERBS = ("format", "format:check", "lint", "typecheck", "test", "check", "security")


class CmdFixtureTests(unittest.TestCase):
    def test_each_fixture_fails_exactly_its_check(self):
        for name, (check, expected) in FIXTURES.items():
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                self.assertEqual(verdicts[check], expected, f"{name}: {check}")

                failing = sorted(cid for cid in CMD_CHECKS if verdicts[cid] == "FAIL")
                self.assertEqual(failing, [check], f"{name}: unexpected CMD FAILs {failing}")

    def test_all_seven_verbs_on_one_runner_passes_for_npm_and_make(self):
        # Two runners, the same seven verbs: CMD-01 must pass on both. This is the check that the
        # implementation is runner-independent rather than npm-specific.
        for name in ("cmd-ok-npm", "cmd-ok-make", "cmd-ok-make-prereqs", "cmd-ok-make-alias"):
            with self.subTest(fixture=name):
                report = support.run_audit(support.fixture(name))
                verdicts = support.verdicts(report)
                for check in CMD_CHECKS:
                    self.assertEqual(verdicts[check], "PASS", f"{name}: {check}")

    def test_write_in_check_names_the_write_verb(self):
        report = support.run_audit(support.fixture("cmd-04-write-in-check"))
        findings = [f for f in report["findings"] if f["check"] == "CMD-04"]
        self.assertTrue(findings, "CMD-04 failed without emitting a finding")
        self.assertIn("format", findings[0]["statement"].lower())


class CmdUnknownTests(unittest.TestCase):
    def test_no_runner_is_unknown_never_fail(self):
        # An unrecognised ecosystem is not proof that the verb surface is absent.
        report = support.run_audit(support.fixture("agt-05-verbs-named-not-resolved"))
        verdicts = support.verdicts(report)
        for check in CMD_CHECKS:
            self.assertEqual(verdicts[check], "UNKNOWN", check)

    def test_check_that_composes_only_some_verbs_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(
                root,
                "package.json",
                (
                    '{"name":"partial","scripts":{"format":"prettier --write .",'
                    '"format:check":"prettier --check .","lint":"eslint .",'
                    '"typecheck":"tsc --noEmit","test":"vitest run",'
                    '"check":"npm run typecheck && npm test",'
                    '"security":"npm audit"}}'
                ),
            )
            report = support.run_audit(root)
        self.assertEqual(support.verdicts(report)["CMD-02"], "PARTIAL")


#: A Makefile that defines the six verbs other than `check`, each running its own tool.
MAKE_VERBS = (
    "format:\n\tprettier --write .\n\n"
    "format\\:check:\n\tprettier --check .\n\n"
    "lint:\n\teslint .\n\n"
    "typecheck:\n\ttsc --noEmit\n\n"
    "test:\n\tvitest run\n\n"
    "security:\n\tnpm audit --audit-level=high\n\n"
)

NPM_VERBS = (
    '{"name":"x","scripts":{"format":"prettier --write .","format:check":"prettier --check .",'
    '"lint":"eslint .","typecheck":"tsc --noEmit","test":"vitest run",'
    '"check":"npm run format:check && npm run typecheck && npm test","security":"npm audit"}}'
)


def audit_files(files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            support.write(root, rel, text)
        return support.run_audit(root)


def findings_of(report: dict, check: str) -> list[dict]:
    return [f for f in report["findings"] if f["check"] == check]


class MakeCompositionTests(unittest.TestCase):
    def verdict(self, check_rule: str, extra: str = "") -> tuple[str, dict]:
        report = audit_files({"Makefile": MAKE_VERBS + extra + check_rule})
        return support.verdicts(report)["CMD-02"], report

    def test_check_composes_through_prerequisites(self):
        verdict, _ = self.verdict("check: format\\:check typecheck test\n")
        self.assertEqual(verdict, "PASS")

    def test_check_composes_through_the_alias_as_a_prerequisite(self):
        verdict, _ = self.verdict(
            "check: format-check typecheck test\n", extra="format-check:\n\tprettier --check .\n\n"
        )
        self.assertEqual(verdict, "PASS")

    def test_a_missing_prerequisite_is_the_missing_concern(self):
        verdict, report = self.verdict("check: format\\:check test\n")
        self.assertEqual(verdict, "PARTIAL")
        self.assertIn("missing typecheck", [c for c in report["checks"] if c["id"] == "CMD-02"][0]["summary"])

    def test_a_prerequisite_that_is_not_a_verb_is_followed_into_its_recipe(self):
        verdict, _ = self.verdict("check: format\\:check types test\n", extra="types:\n\ttsc --noEmit\n\n")
        self.assertEqual(verdict, "PASS")

    def test_a_target_followed_twice_in_a_cycle_ends(self):
        verdict, _ = self.verdict("check: a\n", extra="a: b\nb: a\n")
        self.assertEqual(verdict, "FAIL")

    def test_make_invocations_on_separate_recipe_lines_are_all_seen(self):
        verdict, _ = self.verdict("check:\n\tmake format\\:check\n\tmake typecheck\n\tmake test\n")
        self.assertEqual(verdict, "PASS")

    def test_a_quoted_target_name_is_the_target(self):
        verdict, _ = self.verdict("check:\n\tmake 'format:check' && make typecheck && make test\n")
        self.assertEqual(verdict, "PASS")

    def test_a_check_that_lists_the_writing_verb_is_a_write_in_a_read_only_verb(self):
        report = audit_files({"Makefile": MAKE_VERBS + "check: format typecheck test\n"})
        self.assertEqual(support.verdicts(report)["CMD-04"], "FAIL")
        self.assertIn("format", findings_of(report, "CMD-04")[0]["statement"])

    def test_an_escaped_colon_in_a_recipe_is_not_the_writing_verb(self):
        report = audit_files(
            {"Makefile": MAKE_VERBS + "check:\n\tmake format\\:check && make typecheck && make test\n"}
        )
        self.assertEqual(support.verdicts(report)["CMD-04"], "PASS")


class MakeSpellingTests(unittest.TestCase):
    def binding(self, makefile: str, verb: str) -> dict:
        report = audit_files({"Makefile": makefile})
        entries = [c for c in report["checks"] if c["id"] == "CMD-01"][0]["data"]["verbs"]
        return [e for e in entries if e["verb"] == verb][0]

    def test_the_verbs_own_name_wins_over_its_alias(self):
        entry = self.binding("format\\:check:\n\tone\nformat-check:\n\ttwo\n", "format:check")
        self.assertEqual((entry["runner"], entry["command"]), ("Makefile", "one"))

    def test_the_alias_binds_the_verb_when_the_verbs_own_name_has_nothing_to_run(self):
        entry = self.binding("format\\:check:\nformat-check:\n\ttwo\n", "format:check")
        self.assertEqual((entry["resolved"], entry["command"]), (True, "two"))

    def test_the_escaped_name_binds_the_verb_to_what_its_alias_runs(self):
        entry = self.binding("format\\:check: format-check\nformat-check:\n\truff format --check .\n", "format:check")
        self.assertEqual(entry["command"], "make format-check")

    def test_a_target_with_an_escaped_colon_that_is_not_a_verb_is_followed(self):
        report = audit_files(
            {
                "Makefile": MAKE_VERBS
                + "check:\n\tmake format\\:check && make test && make types\\:all\n\ntypes\\:all:\n\ttsc --noEmit\n"
            }
        )
        self.assertEqual(support.verdicts(report)["CMD-02"], "PASS")


class CmdMessageTests(unittest.TestCase):
    """The text a person reads for the two checks, pinned exactly."""

    REMEDIATION_01 = (
        "Define every verb (format, format:check, lint, typecheck, test, check, security) as a "
        "script/target so an agent never has to invent a command."
    )

    def test_a_verb_that_no_runner_defines_is_named(self):
        npm = NPM_VERBS.replace(',"security":"npm audit"', "")
        report = audit_files({"package.json": npm})
        check = [c for c in report["checks"] if c["id"] == "CMD-01"][0]
        self.assertEqual(
            check["summary"],
            "format -> package.json; format:check -> package.json; lint -> package.json; typecheck -> package.json; "
            "test -> package.json; check -> package.json; security -> missing",
        )
        entries = check["data"]["verbs"]
        self.assertEqual([e["resolved"] for e in entries], [True] * 6 + [False])
        self.assertEqual(entries[6], {"verb": "security", "resolved": False, "runner": None, "command": None})
        self.assertEqual(
            findings_of(report, "CMD-01"),
            [
                {
                    "id": "CMD-01",
                    "check": "CMD-01",
                    "phase": 1,
                    "severity": "BLOCKER",
                    "verdict": "FAIL",
                    "statement": "An agent cannot run the standardized command surface literally because 1 of 7 "
                    "framework verbs are not defined on any runner (security).",
                    "evidence": [{"path": "package.json", "line": None, "note": None}],
                    "remediation": self.REMEDIATION_01,
                }
            ],
        )

    def test_more_than_one_missing_verb_are_listed_in_the_order_of_the_surface(self):
        npm = NPM_VERBS.replace(',"security":"npm audit"', "").replace('"lint":"eslint .",', "")
        finding = findings_of(audit_files({"package.json": npm}), "CMD-01")[0]
        self.assertEqual(
            finding["statement"],
            "An agent cannot run the standardized command surface literally because 2 of 7 framework verbs are "
            "not defined on any runner (lint, security).",
        )

    def test_verbs_split_over_two_runners_are_named(self):
        report = audit_files({"package.json": NPM_VERBS, "Makefile": "check:\n\tnpm run check\n"})
        finding = findings_of(report, "CMD-01")[0]
        self.assertEqual(
            finding["statement"],
            "An agent cannot find every verb on one runner because verbs resolve across 2 runners "
            "(package.json, Makefile), so no single runner is the contract.",
        )
        self.assertEqual(finding["severity"], "DEGRADER")
        self.assertEqual(
            finding["evidence"],
            [{"path": "package.json", "line": None, "note": verb} for verb in VERBS],
        )
        self.assertEqual(
            finding["remediation"],
            "Keep one runner as the authority for all verbs; reduce any second runner to a delegation (see CMD-03).",
        )

    def test_a_check_verb_that_is_not_defined_is_named(self):
        npm = NPM_VERBS.replace(',"check":"npm run format:check && npm run typecheck && npm test"', "")
        report = audit_files({"package.json": npm})
        check = [c for c in report["checks"] if c["id"] == "CMD-02"][0]
        self.assertEqual(check["summary"], "the check verb is not defined on any runner")
        self.assertEqual(
            findings_of(report, "CMD-02"),
            [
                {
                    "id": "CMD-02",
                    "check": "CMD-02",
                    "phase": 1,
                    "severity": "BLOCKER",
                    "verdict": "FAIL",
                    "statement": "An agent cannot run one gate that composes the read-only verbs because no runner "
                    "defines a check verb.",
                    "evidence": [],
                    "remediation": "Define check as format-check, then typecheck, then test.",
                }
            ],
        )

    def test_a_check_that_composes_nothing_names_every_missing_concern(self):
        npm = NPM_VERBS.replace("npm run format:check && npm run typecheck && npm test", "npm run lint")
        report = audit_files({"package.json": npm})
        check = [c for c in report["checks"] if c["id"] == "CMD-02"][0]
        self.assertEqual(
            check["summary"], "check (package.json) composes: nothing — missing format-check, typecheck, test"
        )
        self.assertEqual(
            findings_of(report, "CMD-02"),
            [
                {
                    "id": "CMD-02",
                    "check": "CMD-02",
                    "phase": 1,
                    "severity": "BLOCKER",
                    "verdict": "FAIL",
                    "statement": "An agent cannot trust one gate to verify the change set because the package.json "
                    "check verb does not invoke format-check, typecheck, test.",
                    "evidence": [{"path": "package.json", "line": None, "note": "npm run lint"}],
                    "remediation": "Make check invoke a format-check, a typecheck and the test suite, in that order, "
                    "so one command is the gate.",
                }
            ],
        )

    def test_a_check_that_composes_some_concerns_lists_them_in_catalogue_order(self):
        npm = NPM_VERBS.replace(
            "npm run format:check && npm run typecheck && npm test", "npm test && npm run typecheck"
        )
        report = audit_files({"package.json": npm})
        check = [c for c in report["checks"] if c["id"] == "CMD-02"][0]
        self.assertEqual(check["summary"], "check (package.json) composes: typecheck, test — missing format-check")
        self.assertEqual(check["verdict"], "PARTIAL")

    def test_a_check_that_composes_everything_says_what_it_composes(self):
        report = audit_files({"package.json": NPM_VERBS})
        check = [c for c in report["checks"] if c["id"] == "CMD-02"][0]
        self.assertEqual(check["summary"], "check (package.json) composes: format-check, typecheck, test")

    def test_the_runner_less_checks_say_so(self):
        report = audit_files({"README.md": "# x\n"})
        by_id = {c["id"]: c["summary"] for c in report["checks"]}
        self.assertEqual(
            by_id["CMD-01"],
            "no recognised verb runner (package.json, Makefile, Taskfile, pyproject, gradle, maven), "
            "so no verb can be resolved",
        )
        self.assertEqual(by_id["CMD-02"], "no recognised verb runner, so no check verb can be read")
        self.assertEqual(by_id["CMD-03"], "no recognised verb runner, so no second definition can be read")
        self.assertEqual(by_id["CMD-04"], "no recognised verb runner, so read-only verbs cannot be read")


class MakeParseErrorTests(unittest.TestCase):
    BROKEN = "format:\n\tprettier --write .\n\nformat:check:\n\tprettier --check .\n"

    def test_the_parse_error_is_the_finding_and_names_its_line(self):
        report = audit_files({"Makefile": self.BROKEN})
        findings = findings_of(report, "CMD-01")
        self.assertEqual([f["id"] for f in findings], ["CMD-01:Makefile"])
        self.assertEqual(findings[0]["severity"], "BLOCKER")
        self.assertEqual(
            findings[0]["statement"],
            "An agent cannot run any verb through make because GNU Make refuses the Makefile at line 4 "
            "(target pattern contains no '%'), so no target in it can run.",
        )
        self.assertEqual(findings[0]["evidence"], [{"path": "Makefile", "line": 4, "note": "format:check:"}])
        self.assertEqual(
            findings[0]["remediation"],
            "Escape the colon of a verb's name, `format\\:check:`, and define `format-check` as the alias, so that "
            "`make format:check` and `make format-check` both run. An unescaped `format:check:` is a static pattern "
            "rule, which needs a `%`.",
        )

    def test_the_summary_says_why_and_no_verb_is_resolved(self):
        report = audit_files({"Makefile": self.BROKEN})
        check = [c for c in report["checks"] if c["id"] == "CMD-01"][0]
        self.assertEqual(
            check["summary"],
            "the Makefile does not parse (line 4: target pattern contains no '%'), so no verb on it can run",
        )
        self.assertEqual(check["data"]["resolved_count"], 0)
        self.assertEqual(check["data"]["missing"], list(VERBS))
        self.assertEqual(
            check["data"]["verbs"],
            [{"verb": verb, "resolved": False, "runner": None, "command": None} for verb in VERBS],
        )

    def test_the_checks_that_need_a_runner_say_the_makefile_is_the_reason(self):
        report = audit_files({"Makefile": self.BROKEN})
        by_id = {c["id"]: c for c in report["checks"]}
        self.assertEqual(
            by_id["CMD-02"]["summary"], "the Makefile does not parse (see CMD-01), so no check verb can be read"
        )
        self.assertEqual(
            by_id["CMD-03"]["summary"], "the Makefile does not parse (see CMD-01), so no second definition can be read"
        )
        self.assertEqual(
            by_id["CMD-04"]["summary"], "the Makefile does not parse (see CMD-01), so read-only verbs cannot be read"
        )
        for check in ("CMD-02", "CMD-03", "CMD-04"):
            self.assertEqual(by_id[check]["verdict"], "UNKNOWN", check)

    def test_beside_a_runner_that_carries_every_verb_it_is_a_degrader_and_the_check_is_partial(self):
        report = audit_files({"Makefile": self.BROKEN, "package.json": NPM_VERBS})
        self.assertEqual(support.verdicts(report)["CMD-01"], "PARTIAL")
        findings = findings_of(report, "CMD-01")
        self.assertEqual([(f["id"], f["severity"]) for f in findings], [("CMD-01:Makefile", "DEGRADER")])

    def test_beside_a_runner_with_a_missing_verb_both_defects_are_findings(self):
        npm = NPM_VERBS.replace(',"security":"npm audit"', "")
        report = audit_files({"Makefile": self.BROKEN, "package.json": npm})
        self.assertEqual(support.verdicts(report)["CMD-01"], "FAIL")
        self.assertEqual(
            [(f["id"], f["severity"]) for f in findings_of(report, "CMD-01")],
            [("CMD-01", "BLOCKER"), ("CMD-01:Makefile", "DEGRADER")],
        )

    def test_a_makefile_that_parses_adds_no_finding_beside_another_runner(self):
        report = audit_files({"Makefile": "check:\n\tnpm run check\n", "package.json": NPM_VERBS})
        self.assertEqual(support.verdicts(report)["CMD-01"], "PARTIAL")
        self.assertEqual([f["id"] for f in findings_of(report, "CMD-01")], ["CMD-01"])


class Agt05Tests(unittest.TestCase):
    def test_named_without_a_runner_is_partial_not_fail(self):
        report = support.run_audit(support.fixture("agt-05-verbs-named-not-resolved"))
        self.assertEqual(support.verdicts(report)["AGT-05"], "PARTIAL")

    def test_named_and_resolved_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support.write(
                root,
                "AGENTS.md",
                (
                    "# Rules\n\n"
                    + "Always run the tests before committing.\n" * 20
                    + "\nVerbs: "
                    + ", ".join(VERBS)
                    + "\n"
                ),
            )
            support.write(
                root,
                "package.json",
                (
                    '{"name":"x","scripts":{"format":"prettier --write .",'
                    '"format:check":"prettier --check .","lint":"eslint .",'
                    '"typecheck":"tsc --noEmit","test":"vitest run",'
                    '"check":"npm run format:check && npm run typecheck && npm test",'
                    '"security":"npm audit"}}'
                ),
            )
            report = support.run_audit(root)
        self.assertEqual(support.verdicts(report)["AGT-05"], "PASS")


if __name__ == "__main__":
    unittest.main()
