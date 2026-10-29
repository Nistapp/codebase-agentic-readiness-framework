# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""A validator for the small subset of JSON Schema 2020-12 that this repository's schemas use, and a lint for it.

The standard library has no JSON Schema validator, and the tools may import nothing else. The four schemas
(report, intake, catalogue, facts) are therefore limited to the keywords below, which are listed under "The keyword
subset" in schema/SCHEMA.md. :func:`lint_schema` rejects any other keyword, so that a constraint can never be written
and silently ignored. :class:`SubsetValidator` applies a linted schema to a document.

Behaviour follows the reference ``jsonschema`` package, which a dev-only check in CI compares against on every
example and on mutations of each (brownfield-recipes/dev/crosscheck_jsonschema.py). Two deliberate points:

* ``integer`` accepts ``2.0`` and refuses ``True``; JSON booleans are never numbers. ``enum`` and ``const`` compare by
  JSON equality, so ``1`` is not ``True``.
* ``pattern`` is ECMAScript syntax. ``$`` means the end of the string, as in ECMAScript, so a value that ends with a
  newline does not satisfy ``^...$``. Python's ``re`` would accept it, and so does the reference package.

A violation never echoes the value it found, only its JSON type or length, so a secret that sits in a wrong place
does not travel into an error list.

Standard library only. This file must parse as Python 3.9 (the preflight in ``_common.py`` runs on an old interpreter).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "title",
        "description",
        "$defs",
        "$ref",
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "pattern",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
    }
)
ROOT_ONLY = frozenset({"$schema", "$id", "$defs"})
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
TYPE_NAMES = frozenset({"object", "array", "string", "integer", "number", "boolean", "null"})
REF_FORM = re.compile(r"^#/\$defs/([A-Za-z0-9_-]+)$")

# `\d \w \s \b` and their negations, and the escapes that mean the same in Python and ECMAScript.
SAFE_LETTER_ESCAPES = frozenset("dDwWsSbBnrtfxu")


class SchemaError(ValueError):
    """A schema that is outside the subset. `problems` lists every reason, each starting with where it is."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Violation:
    """One way an instance fails a schema. `pointer` is a JSON Pointer to the place in the instance."""

    pointer: str
    keyword: str
    message: str

    def __str__(self) -> str:
        return f"{self.pointer or '/'}: {self.message}"


def escape_token(token: str) -> str:
    """One JSON Pointer reference token: `~` is written `~0` and `/` is written `~1`."""
    return token.replace("~", "~0").replace("/", "~1")


# --- Patterns -----------------------------------------------------------------------------------------


def _scan_pattern(pattern: str) -> tuple[str, str | None]:
    """Translate an ECMAScript-style pattern for Python and find constructs the two do not share.

    Returns the translated pattern and the first problem found, or None. The only translation is `$` outside a
    character class, which becomes `\\Z`: ECMAScript's `$` matches only at the end of the string, while Python's
    also matches before a final newline.
    """
    out: list[str] = []
    in_class = False
    quantified = False  # the previous token was a quantifier, so a following `+` would be possessive
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            if index + 1 >= len(pattern):
                return pattern, "the pattern ends with a lone backslash"
            following = pattern[index + 1]
            if following.isdigit():
                return (
                    pattern,
                    f"the escape \\{following} is a back-reference or an octal, which the two flavours read differently",
                )
            if following.isalpha() and following not in SAFE_LETTER_ESCAPES:
                return pattern, f"the escape \\{following} is not shared by Python and ECMAScript"
            out.append(char + following)
            index += 2
            quantified = False
            continue
        if in_class:
            in_class = char != "]"
            out.append(char)
            index += 1
            continue
        if char == "[":
            in_class = True
            quantified = False
            out.append(char)
            index += 1
            # A `]` right after `[` or `[^` is a literal in Python and ends an empty class in ECMAScript.
            rest = pattern[index:]
            if rest.startswith("]") or rest.startswith("^]"):
                return pattern, "a class that starts with a literal `]` is read differently by the two flavours"
            continue
        if char == "(" and pattern.startswith("(?", index) and pattern[index + 2 : index + 3] not in (":", "=", "!"):
            return pattern, "only (?:, (?= and (?! groups are shared by Python and ECMAScript"
        if char == "+" and quantified:
            return pattern, "possessive quantifiers are not shared by Python and ECMAScript"
        quantified = char in "*+?}"
        out.append("\\Z" if char == "$" else char)
        index += 1
    return "".join(out), None


@lru_cache(maxsize=256)
def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile a schema pattern, translated as `_scan_pattern` says. Raises `SchemaError` when it cannot be used."""
    translated, problem = _scan_pattern(pattern)
    if problem is None:
        try:
            return re.compile(translated)
        except re.error as exc:
            problem = f"the pattern does not compile: {exc}"
    raise SchemaError([f"pattern {pattern!r}: {problem}"])


# --- The lint -----------------------------------------------------------------------------------------


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == value
        and abs(value) != float("inf")
    )


def lint_schema(schema: Any) -> list[str]:
    """Every reason `schema` is outside the subset, each starting with a pointer (`#/properties/x`). Empty when it is in."""
    problems: list[str] = []
    if not isinstance(schema, dict):
        return ["#: a schema must be a JSON object"]
    raw_defs = schema.get("$defs", {})
    names = set(raw_defs) if isinstance(raw_defs, dict) else set()
    _lint_node(schema, "#", True, names, problems)
    if isinstance(raw_defs, dict):
        _lint_reference_cycles(raw_defs, problems)
    return problems


def _lint_node(node: Any, where: str, root: bool, names: set[str], problems: list[str]) -> None:
    if not isinstance(node, dict):
        problems.append(f"{where}: a schema must be a JSON object (true and false are outside the subset)")
        return
    for keyword in node:
        if keyword not in KEYWORDS:
            problems.append(f"{where}: unsupported keyword {keyword!r}")
        elif keyword in ROOT_ONLY and not root:
            problems.append(f"{where}: {keyword!r} is allowed only at the root of the schema")

    if "$schema" in node and node["$schema"] != DRAFT_2020_12:
        problems.append(f"{where}/$schema: must be {DRAFT_2020_12!r}")
    for keyword in ("$id", "title", "description"):
        if keyword in node and not isinstance(node[keyword], str):
            problems.append(f"{where}/{keyword}: must be a string")
    if "$ref" in node:
        ref = node["$ref"]
        found = REF_FORM.match(ref) if isinstance(ref, str) else None
        if found is None:
            problems.append(f"{where}/$ref: must have the form '#/$defs/<name>'")
        elif found.group(1) not in names:
            problems.append(f"{where}/$ref: {ref!r} names no definition")
    if "type" in node:
        declared = node["type"]
        listed = declared if isinstance(declared, list) else [declared]
        valid = bool(listed) and all(isinstance(name, str) and name in TYPE_NAMES for name in listed)
        if not valid or len(set(map(str, listed))) != len(listed):
            problems.append(f"{where}/type: must be one of {sorted(TYPE_NAMES)} or a list of them without repeats")
    if "enum" in node and not (isinstance(node["enum"], list) and node["enum"]):
        problems.append(f"{where}/enum: must be a non-empty list")
    if "additionalProperties" in node and not isinstance(node["additionalProperties"], bool):
        problems.append(f"{where}/additionalProperties: must be true or false")
    if "pattern" in node:
        if not isinstance(node["pattern"], str):
            problems.append(f"{where}/pattern: must be a string")
        else:
            try:
                compile_pattern(node["pattern"])
            except SchemaError as exc:
                problems.extend(f"{where}/pattern: {problem}" for problem in exc.problems)
    for keyword in ("minLength", "maxLength", "minItems", "maxItems"):
        if keyword in node and not _is_count(node[keyword]):
            problems.append(f"{where}/{keyword}: must be a whole number of at least 0")
    for keyword in ("minimum", "maximum"):
        if keyword in node and not _is_number(node[keyword]):
            problems.append(f"{where}/{keyword}: must be a finite number")
    for low, high in (("minLength", "maxLength"), ("minItems", "maxItems"), ("minimum", "maximum")):
        if _is_number(node.get(low)) and _is_number(node.get(high)) and node[low] > node[high]:
            problems.append(f"{where}: {low} is larger than {high}, so nothing can satisfy it")

    properties = node.get("properties")
    if "properties" in node and not isinstance(properties, dict):
        problems.append(f"{where}/properties: must be an object that maps names to schemas")
    if "required" in node:
        required = node["required"]
        if not (isinstance(required, list) and all(isinstance(name, str) for name in required)):
            problems.append(f"{where}/required: must be a list of strings")
        elif len(set(required)) != len(required):
            problems.append(f"{where}/required: names a property twice")
        else:
            known = properties if isinstance(properties, dict) else {}
            problems.extend(
                f"{where}/required: {name!r} is not in properties" for name in required if name not in known
            )

    if isinstance(properties, dict):
        for name, sub in properties.items():
            _lint_node(sub, f"{where}/properties/{escape_token(name)}", False, names, problems)
    if "items" in node:
        _lint_node(node["items"], f"{where}/items", False, names, problems)
    if "$defs" in node:
        defs = node["$defs"]
        if not isinstance(defs, dict):
            problems.append(f"{where}/$defs: must be an object that maps names to schemas")
        else:
            for name, sub in defs.items():
                if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                    problems.append(f"{where}/$defs: the name {name!r} cannot be the target of a $ref")
                _lint_node(sub, f"{where}/$defs/{escape_token(name)}", False, names, problems)


def _lint_reference_cycles(defs: Mapping[str, Any], problems: list[str]) -> None:
    """A definition that is only a `$ref` chain leading back to itself would never end when validating."""
    for start in defs:
        seen = [start]
        node = defs[start]
        while isinstance(node, dict) and isinstance(node.get("$ref"), str):
            found = REF_FORM.match(node["$ref"])
            if found is None or found.group(1) not in defs:
                break
            name = found.group(1)
            if name in seen:
                problems.append(f"#/$defs/{start}: a chain of $ref leads back to {name!r} without consuming any input")
                break
            seen.append(name)
            node = defs[name]


# --- Validation ---------------------------------------------------------------------------------------


def json_type(value: Any) -> str:
    """The JSON type name of a Python value, for messages."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def is_type(value: Any, name: str) -> bool:
    """Whether `value` is of the JSON Schema type `name`. A boolean is never a number."""
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if name == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and value.is_integer()
        )
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def json_equal(left: Any, right: Any) -> bool:
    """JSON equality: `1` equals `1.0`, `True` equals only `True`, and containers compare member by member."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return bool(left == right)
    if isinstance(left, list):
        return (
            isinstance(right, list) and len(left) == len(right) and all(json_equal(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, dict):
        return (
            isinstance(right, dict)
            and left.keys() == right.keys()
            and all(json_equal(left[key], right[key]) for key in left)
        )
    return bool(left == right) and type(left) is type(right)


def _show(value: Any, width: int = 100) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= width else text[: width - 3] + "..."


class _Full(Exception):
    """Raised inside a run to stop once `limit` violations are collected."""


class SubsetValidator:
    """Validates documents against one schema. The schema is linted when the validator is built."""

    def __init__(self, schema: Mapping[str, Any]) -> None:
        problems = lint_schema(schema)
        if problems:
            raise SchemaError(problems)
        self.schema = schema
        self._defs: Mapping[str, Any] = schema.get("$defs", {})

    def validate(self, instance: Any, *, limit: int | None = None) -> list[Violation]:
        """Every violation, in a fixed order: by keyword as written below, then by the instance's own order.

        With `limit`, stops after that many; a caller that gets exactly `limit` back should say there may be more.
        """
        found: list[Violation] = []
        try:
            self._check(instance, self.schema, "", found, limit)
        except _Full:
            pass
        return found

    def _add(self, found: list[Violation], limit: int | None, pointer: str, keyword: str, message: str) -> None:
        found.append(Violation(pointer, keyword, message))
        if limit is not None and len(found) >= limit:
            raise _Full

    def _check(
        self, value: Any, schema: Mapping[str, Any], pointer: str, found: list[Violation], limit: int | None
    ) -> None:
        def add(keyword: str, message: str) -> None:
            self._add(found, limit, pointer, keyword, message)

        if "$ref" in schema:
            name = REF_FORM.match(schema["$ref"])
            assert name is not None  # the lint has proved the form and the target
            self._check(value, self._defs[name.group(1)], pointer, found, limit)

        if "type" in schema:
            declared = schema["type"]
            names = declared if isinstance(declared, list) else [declared]
            if not any(is_type(value, name) for name in names):
                add("type", f"expected {' or '.join(names)}, got {json_type(value)}")
        if "enum" in schema and not any(json_equal(value, member) for member in schema["enum"]):
            add("enum", f"expected one of {_show(schema['enum'])}")
        if "const" in schema and not json_equal(value, schema["const"]):
            add("const", f"expected {_show(schema['const'])}")

        if isinstance(value, str):
            if "pattern" in schema and compile_pattern(schema["pattern"]).search(value) is None:
                add("pattern", f"does not match the pattern {schema['pattern']}")
            if "minLength" in schema and len(value) < schema["minLength"]:
                add("minLength", f"length {len(value)} is below the minimum of {schema['minLength']}")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                add("maxLength", f"length {len(value)} is above the maximum of {schema['maxLength']}")

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                add("minimum", f"is below the minimum of {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                add("maximum", f"is above the maximum of {schema['maximum']}")

        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                add("minItems", f"{len(value)} items is below the minimum of {schema['minItems']}")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                add("maxItems", f"{len(value)} items is above the maximum of {schema['maxItems']}")
            if "items" in schema:
                for index, item in enumerate(value):
                    self._check(item, schema["items"], f"{pointer}/{index}", found, limit)

        if isinstance(value, dict):
            for name in schema.get("required", []):
                if name not in value:
                    add("required", f"missing the required property {name!r}")
            properties = schema.get("properties", {})
            for name, sub in properties.items():
                if name in value:
                    self._check(value[name], sub, f"{pointer}/{escape_token(name)}", found, limit)
            if schema.get("additionalProperties") is False:
                extra = [name for name in value if name not in properties]
                if extra:
                    add(
                        "additionalProperties",
                        f"unexpected {'property' if len(extra) == 1 else 'properties'}: {', '.join(map(repr, extra))}",
                    )
