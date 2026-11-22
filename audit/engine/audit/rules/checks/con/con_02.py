# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CON-02: Test directories protected."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import entry_instruction_file, prohibitions_section
from audit.scan import Inventory
from audit.target import Target
from audit.rules.payloads import PathList
from audit.rules.checks.con._shared import _TEST_DIR_NAMES, _finding, _names_directory, _outcome, _unknown

SPEC = declare("CON-02", "Test directories protected", "B", Severity.BLOCKER)


def _describe(roots: list[str], limit: int = 8) -> str:
    """A bounded, deterministic rendering of a root list for details and findings."""
    shown = ", ".join(root + "/" for root in roots[:limit])
    extra = len(roots) - limit
    return f"{shown} (+{extra} more)" if extra > 0 else shown


def _test_roots(target: Target, inventory: Inventory) -> list[str]:
    """Every test directory: a filesystem root plus any directory segment named in the scan."""
    roots: set[str] = {name for name in _TEST_DIR_NAMES if (target.path / name).is_dir()}
    for entry in inventory.files:
        parts = entry.rel.split("/")
        for index, part in enumerate(parts[:-1]):
            if part in _TEST_DIR_NAMES:
                roots.add("/".join(parts[: index + 1]))
    return sorted(roots)


def check_con02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")
    section = prohibitions_section(text)
    if section is None:
        return _unknown(spec, f"{name} has no prohibitions section to read; AGT-07 owns that finding")

    test_roots = _test_roots(target, inventory)
    if not test_roots:
        return _unknown(spec, "no test directories detected, so there is nothing for a deny list to protect")

    named = [span for _line, span in section.code_spans()]
    covered = [root for root in test_roots if any(_names_directory(root, pattern) for pattern in named)]
    uncovered = [root for root in test_roots if root not in covered]
    listed = _describe(test_roots)
    paths = PathList(paths=tuple(test_roots))
    evidence = [Evidence(name, line=line, note=title) for line, title in section.sections]

    if not uncovered:
        return _outcome(
            spec,
            Verdict.PASS,
            f"the prohibitions section of {name} names the test directories ({listed})",
            data=paths,
        )
    if covered:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"the prohibitions section covers {_describe(covered)} but not {_describe(uncovered)}",
            [
                _finding(
                    spec,
                    "rely on the deny list to keep test directories out of an agent's reach",
                    f"the prohibitions section of {name} does not name {_describe(uncovered)}",
                    Verdict.PARTIAL,
                    evidence,
                    f"Name {_describe(uncovered)} in a code span in the prohibitions section of {name}.",
                )
            ],
            data=paths,
        )
    return _outcome(
        spec,
        Verdict.FAIL,
        f"the prohibitions section names none of the test directories ({listed})",
        [
            _finding(
                spec,
                "trust that a failing test is not rewritten to pass",
                f"the prohibitions section of {name} does not name any test directory",
                Verdict.FAIL,
                evidence,
                f"Name {listed} in a code span in the prohibitions section of {name}, so test edits are bounded and "
                "reviewed.",
            )
        ],
        data=paths,
    )
