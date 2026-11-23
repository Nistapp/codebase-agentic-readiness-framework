# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`EXEC-06` resolves a documented `make` target that a pattern rule builds (issue #306).

`make test-dev-local-1` ran, but `EXEC-06` reported it as unresolved: the Makefile builds the name with a static
pattern rule over a computed list (`$(LOCAL_SHARD_TARGETS): test-%:`). A target now resolves when a pattern rule
or a static pattern rule's own list builds it. A target that only a list the engine cannot expand might name is
not verified, and does not fail the check. A target that nothing could build still fails. The check runs
in-process here, so coverage traces it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import support  # noqa: E402

from audit.rules.checks.execution import check_exec06  # noqa: E402
from audit.rules.registry import REGISTRY_BY_ID  # noqa: E402
from audit.scan import build_inventory  # noqa: E402
from audit.stack import detect_stack, parse_makefile  # noqa: E402

#: The shape of this repository's own shard targets.
COMPUTED = (
    ".PHONY: test\n"
    "SUITES := engine dev\n"
    "LOCAL_SHARD_TARGETS := $(foreach s,$(SUITES),test-$(s)-local-1)\n"
    "test:\n\t@echo all\n"
    "$(LOCAL_SHARD_TARGETS): test-%:\n\t@echo $*\n"
)


def _agents(*commands: str) -> str:
    return "```bash\n" + "\n".join(commands) + "\n```\n"


def _exec06(makefile: str, *commands: str):
    """The `EXEC-06` outcome of a repository with ``makefile`` and an `AGENTS.md` that documents ``commands``."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        support.write(root, "Makefile", makefile)
        support.write(root, "AGENTS.md", _agents(*commands))
        inventory = build_inventory(root)
        return check_exec06(
            spec=REGISTRY_BY_ID["EXEC-06"],
            target=None,
            inventory=inventory,
            stack=detect_stack(inventory),
            components=None,
            session=None,
        )


def _parsed(makefile: str):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        support.write(root, "Makefile", makefile)
        return parse_makefile(build_inventory(root))


class MakePatternTargetTests(unittest.TestCase):
    def test_a_target_a_pattern_rule_builds_resolves(self):
        makefile = "test:\n\t@echo t\nbuild-%:\n\t@echo $*\n"
        outcome = _exec06(makefile, "make test", "make build-web")
        self.assertEqual((outcome.verdict.value, outcome.summary), ("PASS", "2 documented command(s) resolve"))

    def test_a_target_a_static_pattern_rule_lists_resolves(self):
        makefile = "test:\n\t@echo t\nlint-a lint-b: lint-%:\n\t@echo $*\n"
        outcome = _exec06(makefile, "make test", "make lint-b")
        self.assertEqual((outcome.verdict.value, outcome.summary), ("PASS", "2 documented command(s) resolve"))

    def test_a_target_a_computed_list_may_name_is_not_verified_and_does_not_fail(self):
        outcome = _exec06(COMPUTED, "make test", "make test-dev-local-1")
        self.assertEqual(outcome.verdict.value, "PASS")
        self.assertEqual(
            outcome.summary,
            "1 documented command(s) resolve; 1 make command(s) not verified, because the Makefile builds target "
            "names from a variable or a function (line 6) the engine does not expand: 'make test-dev-local-1' "
            "(AGENTS.md:3)",
        )
        self.assertEqual(outcome.findings, [])

    def test_an_unknown_target_in_a_plain_makefile_still_fails(self):
        outcome = _exec06("test:\n\t@echo t\n", "make test", "make nothing-here")
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual(
            outcome.summary, "1 documented command(s) name no script, verb, or file: 'make nothing-here' (AGENTS.md:3)"
        )
        self.assertEqual([e.note for f in outcome.findings for e in f.evidence], ["make nothing-here"])

    def test_a_target_no_pattern_matches_still_fails(self):
        makefile = "test:\n\t@echo t\nbuild-%:\n\t@echo $*\nlint-a: lint-%:\n\t@echo $*\n"
        outcome = _exec06(makefile, "make build-", "make lint-z", "make deploy")
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual(
            [e.note for f in outcome.findings for e in f.evidence], ["make build-", "make lint-z", "make deploy"]
        )

    def test_a_failure_beside_a_computed_list_names_both(self):
        outcome = _exec06(COMPUTED, "npm run nothing", "make test-dev-local-1")
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual([e.note for f in outcome.findings for e in f.evidence], ["npm run nothing"])
        self.assertIn("1 make command(s) not verified", outcome.summary)

    def test_a_target_the_static_pattern_of_a_computed_list_does_not_match_still_fails(self):
        # Make requires every name `$(LOCAL_SHARD_TARGETS)` lists to match `test-%`, so it cannot name `deploy`.
        outcome = _exec06(COMPUTED, "make test-dev-local-1", "make deploy")
        self.assertEqual(outcome.verdict.value, "FAIL")
        self.assertEqual([e.note for f in outcome.findings for e in f.evidence], ["make deploy"])
        self.assertIn("1 make command(s) not verified", outcome.summary)

    def test_any_target_a_computed_list_with_no_pattern_may_name_is_not_verified(self):
        makefile = "test:\n\t@echo t\nEXTRA := deploy\n$(EXTRA): test\n\t@echo $@\n"
        outcome = _exec06(makefile, "make test", "make deploy")
        self.assertEqual(outcome.verdict.value, "PASS")
        self.assertEqual(
            outcome.summary,
            "1 documented command(s) resolve; 1 make command(s) not verified, because the Makefile builds target "
            "names from a variable or a function (line 4) the engine does not expand: 'make deploy' (AGENTS.md:3)",
        )

    def test_the_summary_names_only_the_lists_that_may_name_the_target(self):
        makefile = COMPUTED + "GATES := gate-a\n$(GATES): gate-%:\n\t@echo $*\n$(OTHER): x\n"
        outcome = _exec06(makefile, "make gate-a")
        self.assertIn("(line 9, 11)", outcome.summary)


class MakefilePatternReadTests(unittest.TestCase):
    def test_the_reader_keeps_patterns_static_lists_and_computed_lines(self):
        parsed = _parsed(
            "a:\n\tx\n%.o: %.c\n\tcc\nfmt\\:%:\n\tf\nx y: %: z\n\tq\n$(OUT): b\n\tc\nall: $(DEPS)\n"
            "$(T): t-%: x\n$(U): $(P): y\n"
        )
        self.assertEqual(
            (parsed.patterns, parsed.static_targets, parsed.computed),
            (("%.o", "fmt:%"), ("x", "y"), ((9, None), (12, "t-%"), (13, None))),
        )
        self.assertEqual(sorted(parsed.rules), ["a", "all"])


if __name__ == "__main__":
    unittest.main()
