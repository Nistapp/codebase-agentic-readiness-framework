# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TOOL-03: Type checker configured."""

from __future__ import annotations

import json
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import resolve_verbs
from audit.rules.checks.tool._shared import _finding, _manifest_evidence, _outcome, _read_matches, _unknown

SPEC = declare("TOOL-03", "Type checker configured", "A", Severity.DEGRADER)


#: Ecosystems for which this pack knows a strict type-check configuration.
_TYPECHECK_ECOSYSTEMS: frozenset[str] = frozenset({"node", "python", "dotnet"})


def _strip_jsonc_comments(text: str) -> str:
    """Strip ``//`` and ``/* */`` comments outside string literals, as `tsconfig.json`/`jsconfig.json`
    readers (and TypeScript's own parser) do; ``json.loads`` alone rejects them as invalid JSON."""
    out: list[str] = []
    in_string = False
    escape = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _strip_trailing_commas(text: str) -> str:
    """Drop a ``,`` that precedes a closing ``}``/``]`` (ignoring whitespace), outside string literals —
    TypeScript's own `tsconfig.json`/`jsconfig.json` reader accepts a trailing comma the stdlib does not."""
    out: list[str] = []
    in_string = False
    escape = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _json_true(text: str, key: str) -> bool:
    try:
        data = json.loads(_strip_trailing_commas(_strip_jsonc_comments(text)))
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    options = data.get("compilerOptions")
    if isinstance(options, dict) and options.get(key) is True:
        return True
    return data.get(key) is True


def _typecheck_signals(inventory, stack) -> tuple[list[str], list[str]]:
    """Return ``(strict, nonstrict)`` config evidence for the strict type-checker check."""
    strict: list[str] = []
    nonstrict: list[str] = []

    for rel, key in (("tsconfig.json", "strict"), ("jsconfig.json", "checkJs")):
        text = inventory.read(rel)
        if text is None:
            continue
        (strict if _json_true(text, key) else nonstrict).append(f"{rel}:{key}")

    for rel in ("mypy.ini", ".mypy.ini"):
        if not inventory.has(rel):
            continue
        (strict if _read_matches(inventory, rel, r"(?im)^\s*strict\s*=\s*true") else nonstrict).append(rel)

    for rel, strict_re, present_re in (
        (
            "pyproject.toml",
            r"(?ms)^\[tool\.(?:mypy|pyright)\][^\[]*?"
            r"(?:strict\s*=\s*true|typeCheckingMode\s*=\s*\"strict\")",
            r"(?m)^\[tool\.(?:mypy|pyright)\]",
        ),
        ("setup.cfg", r"(?ms)^\[mypy\][^\[]*?strict\s*=\s*true", r"(?m)^\[mypy\]"),
    ):
        if not inventory.has(rel):
            continue
        if _read_matches(inventory, rel, strict_re):
            strict.append(f"{rel} [mypy/pyright]")
        elif _read_matches(inventory, rel, present_re):
            nonstrict.append(f"{rel} [mypy/pyright]")

    pyright = inventory.read("pyrightconfig.json")
    if pyright is not None:
        if re.search(r'"typeCheckingMode"\s*:\s*"strict"', pyright) or re.search(r'"strict"\s*:', pyright):
            strict.append("pyrightconfig.json")
        else:
            nonstrict.append("pyrightconfig.json")

    for rel in inventory.match("*.csproj") + inventory.match("Directory.Build.props", "Directory.Build.targets"):
        text = inventory.read(rel)
        if not text:
            continue
        if re.search(r"<Nullable>\s*enable\s*</Nullable>", text, re.IGNORECASE):
            strict.append(f"{rel}:Nullable")
        elif "<Nullable>" in text:
            nonstrict.append(rel)
    if inventory.has("global.json"):
        nonstrict.append("global.json")

    binding = resolve_verbs(inventory, stack).get("typecheck")
    if binding and re.search(r"--strict\b", binding.command):
        strict.append(f"{binding.runner}:typecheck --strict")

    return strict, nonstrict


# ===========================================================================
# TOOL-03 — type checker configured
# ===========================================================================


def check_tool03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    strict, nonstrict = _typecheck_signals(inventory, stack)

    if strict:
        return _outcome(spec, Verdict.PASS, f"strict config: {', '.join(sorted(set(strict)))}")

    if nonstrict:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"type checker configured but not strict: {', '.join(sorted(set(nonstrict)))}",
            [
                _finding(
                    spec,
                    "trust the type checker to catch a whole class of defects",
                    f"a type-check configuration exists but is not strict ({', '.join(sorted(set(nonstrict)))})",
                    Verdict.PARTIAL,
                    [Evidence(rel) for rel in sorted(set(nonstrict))],
                    "Turn on strict mode (tsconfig `strict: true`, mypy `strict = true`, pyright "
                    '`typeCheckingMode: "strict"`) so the checker\'s findings are trustworthy.',
                )
            ],
        )

    if set(stack.ecosystems) & _TYPECHECK_ECOSYSTEMS:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no strict type-check configuration",
            [
                _finding(
                    spec,
                    "trust the type checker to catch a whole class of defects",
                    "no strict type-check configuration is present for the detected ecosystem "
                    f"({', '.join(sorted(set(stack.ecosystems)))})",
                    Verdict.FAIL,
                    _manifest_evidence(inventory),
                    "Add a strict type-check configuration (tsconfig.json strict, mypy/pyright strict, or "
                    ".NET `<Nullable>enable</Nullable>`).",
                )
            ],
        )

    return _unknown(
        spec,
        "no recognised strict type-check configuration and no ecosystem this "
        "pack knows one for, so type-checking cannot be judged",
    )
