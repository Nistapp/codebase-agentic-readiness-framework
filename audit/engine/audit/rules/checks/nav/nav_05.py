# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""NAV-05: Public-symbol documentation coverage."""

from __future__ import annotations

import ast
import re
import warnings

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.payloads import Ratio
from audit.rules.checks.nav._shared import _outcome, _unknown

SPEC = declare("NAV-05", "Public-symbol documentation coverage", "B", Severity.COSMETIC, scored=False)


# ===========================================================================
# NAV-05 — public-symbol documentation coverage (informational)
# ===========================================================================

_PY_PUBLIC_RE = re.compile(r"^(?:async\s+)?def\s+([A-Za-z_]\w*)|^class\s+([A-Za-z_]\w*)")
_TS_EXPORT_RE = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?"
    r"(?:function|class|const|let|var|interface|type|enum)\s+([A-Za-z_$][\w$]*)"
)
_TS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

#: A `.py` file under a directory with one of these names is a test file, left out of the census (NAV-05).
_PY_TEST_DIRS = frozenset({"tests", "test"})


def _language(inventory: Inventory, stack) -> str | None:
    counts = {"python": 0, "typescript": 0}
    for entry in inventory.files:
        if entry.rel.endswith(".py"):
            counts["python"] += 1
        elif entry.rel.endswith(_TS_SUFFIXES):
            counts["typescript"] += 1
    if "python" in stack.ecosystems and counts["python"]:
        return "python"
    if "node" in stack.ecosystems and counts["typescript"]:
        return "typescript"
    if counts["python"] >= counts["typescript"] and counts["python"]:
        return "python"
    if counts["typescript"]:
        return "typescript"
    return None


def _next_code_line(lines: list[str], start: int) -> str | None:
    index = start
    while index < len(lines) and not lines[index].strip():
        index += 1
    return lines[index] if index < len(lines) else None


def _python_test_file(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    return any(part in _PY_TEST_DIRS for part in parts[:-1]) or name.startswith("test_") or name.endswith("_test.py")


def _python_line_census(text: str) -> tuple[int, int]:
    """The fallback for a file `ast` cannot parse: column-0 `def`/`class`, docstring on the next code line."""
    total = documented = 0
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = _PY_PUBLIC_RE.match(line)
        if not match:
            continue
        name = match.group(1) or match.group(2)
        if name.startswith("_"):
            continue
        total += 1
        following = _next_code_line(lines, index + 1)
        if following is not None and following.lstrip().startswith(('"""', "'''")):
            documented += 1
    return total, documented


def _python_ast_census(body: list[ast.stmt]) -> tuple[int, int]:
    total = documented = 0
    for node in body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name.startswith("_"):
            continue
        total += 1
        if ast.get_docstring(node) is not None:
            documented += 1
        if isinstance(node, ast.ClassDef):
            inner_total, inner_documented = _python_ast_census(node.body)
            total += inner_total
            documented += inner_documented
    return total, documented


def _python_census(inventory: Inventory) -> tuple[int, int, int]:
    """Count (public symbols, documented ones, files read by the line fallback) over non-test `.py` files."""
    total = documented = fallback = 0
    for entry in inventory.files:
        if not entry.rel.endswith(".py") or not entry.has_text or _python_test_file(entry.rel):
            continue
        text = inventory.read(entry.rel) or ""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(text, filename=entry.rel)
        except (SyntaxError, ValueError):
            fallback += 1
            file_total, file_documented = _python_line_census(text)
        else:
            file_total, file_documented = _python_ast_census(tree.body)
        total += file_total
        documented += file_documented
    return total, documented, fallback


def _ts_census(inventory: Inventory) -> tuple[int, int]:
    total = documented = 0
    for entry in inventory.files:
        if not entry.rel.endswith(_TS_SUFFIXES) or not entry.has_text:
            continue
        lines = (inventory.read(entry.rel) or "").splitlines()
        for index, line in enumerate(lines):
            if not _TS_EXPORT_RE.match(line):
                continue
            total += 1
            cursor = index - 1
            while cursor >= 0 and not lines[cursor].strip():
                cursor -= 1
            if cursor >= 0 and lines[cursor].strip().endswith("*/"):
                while cursor >= 0 and "/**" not in lines[cursor]:
                    cursor -= 1
                if cursor >= 0:
                    documented += 1
    return total, documented


def check_nav05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    language = _language(inventory, stack)
    if language is None:
        return _unknown(spec, "no recognised source language, so 'public' cannot be defined")

    fallback = 0
    if language == "python":
        total, documented, fallback = _python_census(inventory)
        method = (
            "python: module-level def/class and the methods of public classes, names not starting with '_', "
            "test files left out (ast; a file that does not parse falls back to column-0 def/class)"
        )
    else:
        total, documented = _ts_census(inventory)
        method = "typescript: exported declarations (class members not counted)"
    if total == 0:
        return _unknown(spec, f"{language}: no public symbols detected ({method})")

    ratio = documented / total
    detail = f"{documented}/{total} public symbols documented ({ratio:.0%}); method: {method}"
    if fallback:
        detail += f"; {fallback} file(s) did not parse and were read by the column-0 rule"
    verdict = Verdict.PASS if documented == total else Verdict.PARTIAL
    return _outcome(
        spec, verdict, detail, data=Ratio(numerator=documented, denominator=total, unit="public symbols", method=method)
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, Reads, What, _at

    return Reads(
        where=(*_at(ANY_DEPTH, "*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.mjs", "*.cjs"),),
        what=What("phrase"),
        binding="file",
        note=(
            "Python, parsed with ast: a module-level def, async def or class and a method of a public class, "
            "each with a public name, is documented when ast finds its docstring; a test file (a tests or test "
            "folder, a test_*.py or *_test.py name) is not read, and a file that does not parse falls back to "
            "column-0 lines with the docstring on the next non-blank line. TypeScript or JavaScript: an export "
            "declaration is documented when the line before (blank lines skipped) ends a /** */ block. Only the "
            "main language is read."
        ),
    )
