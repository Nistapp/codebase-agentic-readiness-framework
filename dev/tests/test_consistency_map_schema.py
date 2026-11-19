# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the consistency map's JSON Schema, ``dev/consistency-map.schema.json``, on an example map."""

from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path
from typing import Any

DEV = Path(__file__).resolve().parents[1]
SCHEMA: dict[str, Any] = json.loads((DEV / "consistency-map.schema.json").read_text(encoding="utf-8"))
EXAMPLE: dict[str, Any] = json.loads(
    (DEV / "tests" / "fixtures" / "consistency-map-example.json").read_text(encoding="utf-8")
)

#: The keywords the small validator below understands. A schema keyword outside this set fails a test, so the
#: validator never passes a map because it skipped a rule.
_KNOWN_KEYWORDS = frozenset(
    {
        "$defs",
        "$id",
        "$ref",
        "$schema",
        "additionalProperties",
        "const",
        "description",
        "enum",
        "items",
        "minItems",
        "minLength",
        "minimum",
        "oneOf",
        "pattern",
        "properties",
        "required",
        "title",
        "type",
        "uniqueItems",
    }
)

_TYPES: dict[str, type[object]] = {"object": dict, "array": list, "string": str, "integer": int}


def _keywords(schema: Any) -> set[str]:
    """Every keyword the schema uses, at any depth; the names under ``properties`` and ``$defs`` are not keywords."""
    found: set[str] = set()
    if isinstance(schema, dict):
        for key, value in schema.items():
            found.add(key)
            if key in ("properties", "$defs"):
                for sub in value.values():
                    found |= _keywords(sub)
            else:
                found |= _keywords(value)
    elif isinstance(schema, list):
        for item in schema:
            found |= _keywords(item)
    return found


def _resolve(schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    prefix = "#/$defs/"
    assert isinstance(ref, str) and ref.startswith(prefix), ref
    resolved = SCHEMA["$defs"][ref[len(prefix) :]]
    assert isinstance(resolved, dict)
    return _resolve(resolved)


def _problems(value: Any, schema: dict[str, Any], where: str = "$") -> list[str]:
    """Check a value against the keywords in ``_KNOWN_KEYWORDS``; not a general JSON Schema validator."""
    schema = _resolve(schema)
    if "oneOf" in schema:
        matches = [option for option in schema["oneOf"] if not _problems(value, option, where)]
        return [] if len(matches) == 1 else [f"{where}: matches {len(matches)} of the oneOf options"]
    expected = schema.get("type")
    if expected is not None and (not isinstance(value, _TYPES[expected]) or isinstance(value, bool)):
        return [f"{where}: not of type {expected}"]
    problems: list[str] = []
    if "const" in schema and value != schema["const"]:
        problems.append(f"{where}: {value!r} is not {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{where}: {value!r} is not in the enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            problems.append(f"{where}: shorter than minLength")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append(f"{where}: {value!r} does not match {schema['pattern']!r}")
    if isinstance(value, int) and not isinstance(value, bool) and value < schema.get("minimum", value):
        problems.append(f"{where}: {value} is below the minimum")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        problems += [f"{where}: missing {key!r}" for key in schema.get("required", []) if key not in value]
        if schema.get("additionalProperties") is False:
            problems += [f"{where}: unexpected {key!r}" for key in value if key not in properties]
        for key, item in value.items():
            if key in properties:
                problems += _problems(item, properties[key], f"{where}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            problems.append(f"{where}: fewer than minItems")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            problems.append(f"{where}: repeated items")
        if "items" in schema:
            for number, item in enumerate(value):
                problems += _problems(item, schema["items"], f"{where}[{number}]")
    return problems


class SchemaShapeTest(unittest.TestCase):
    def test_the_schema_uses_only_keywords_the_validator_knows(self) -> None:
        self.assertEqual(_keywords(SCHEMA) - _KNOWN_KEYWORDS, set())

    def test_every_ref_resolves(self) -> None:
        refs = re.findall(r'"\$ref": "#/\$defs/([a-z_]+)"', json.dumps(SCHEMA))
        self.assertTrue(refs)
        self.assertEqual(set(refs) - set(SCHEMA["$defs"]), set())

    def test_the_format_and_the_five_parts_are_required(self) -> None:
        self.assertEqual(sorted(SCHEMA["required"]), ["boundaries", "keeps", "map_format", "moves", "names", "reads"])


class ExampleTest(unittest.TestCase):
    def test_the_example_is_valid(self) -> None:
        self.assertEqual(_problems(EXAMPLE, SCHEMA), [])

    def test_an_empty_map_is_valid(self) -> None:
        empty = {"map_format": 1, "reads": [], "moves": [], "keeps": [], "names": [], "boundaries": []}
        self.assertEqual(_problems(empty, SCHEMA), [])

    def test_the_example_uses_each_part(self) -> None:
        for part in ("reads", "moves", "keeps", "names", "boundaries"):
            self.assertTrue(EXAMPLE[part], part)
        self.assertEqual({keep["status"] for keep in EXAMPLE["keeps"]}, {"kept", "accepted"})


class InvalidMapTest(unittest.TestCase):
    def _assert_invalid(self, edit: Any, expected: str) -> None:
        broken = copy.deepcopy(EXAMPLE)
        edit(broken)
        problems = _problems(broken, SCHEMA)
        self.assertTrue(any(expected in problem for problem in problems), problems)

    def test_an_unknown_format_fails(self) -> None:
        self._assert_invalid(lambda m: m.update(map_format=2), "is not 1")

    def test_a_missing_part_fails(self) -> None:
        self._assert_invalid(lambda m: m.pop("names"), "missing 'names'")

    def test_an_unknown_key_fails(self) -> None:
        self._assert_invalid(lambda m: m["reads"][0].update(files=["README.md"]), "unexpected 'files'")

    def test_a_check_id_outside_the_catalogue_form_fails(self) -> None:
        self._assert_invalid(lambda m: m["reads"][0].update(check="TST4"), "does not match")

    def test_an_absolute_or_dotted_path_fails(self) -> None:
        self._assert_invalid(lambda m: m["moves"][0].update(to=["/AGENTS.md"]), "does not match")
        self._assert_invalid(lambda m: m["moves"][0].update(to=["../AGENTS.md"]), "does not match")

    def test_a_dot_folder_path_is_valid(self) -> None:
        valid = copy.deepcopy(EXAMPLE)
        valid["moves"][0]["to"] = [".github/copilot-instructions.md"]
        self.assertEqual(_problems(valid, SCHEMA), [])

    def test_an_accepted_keep_needs_a_reason(self) -> None:
        self._assert_invalid(lambda m: m["keeps"][1].pop("reason"), "oneOf")

    def test_a_kept_keep_needs_its_home(self) -> None:
        self._assert_invalid(lambda m: m["keeps"][0].pop("home"), "oneOf")

    def test_a_keep_cannot_be_both(self) -> None:
        self._assert_invalid(lambda m: m["keeps"][0].update(reason="also accepted"), "oneOf")

    def test_an_unknown_action_fails(self) -> None:
        self._assert_invalid(lambda m: m["moves"][0].update(action="delete"), "not in the enum")

    def test_a_window_of_one_line_fails(self) -> None:
        self._assert_invalid(lambda m: m["reads"][1].update(window=1), "below the minimum")

    def test_a_repeated_content_kind_fails(self) -> None:
        self._assert_invalid(lambda m: m["moves"][0].update(content=["prose", "prose"]), "repeated items")

    def test_a_read_with_no_place_fails(self) -> None:
        self._assert_invalid(lambda m: m["reads"][0].update(where=[]), "fewer than minItems")

    def test_a_boundary_without_enforcement_fails(self) -> None:
        self._assert_invalid(lambda m: m["boundaries"][0].pop("enforcement"), "missing 'enforcement'")


if __name__ == "__main__":
    unittest.main()
