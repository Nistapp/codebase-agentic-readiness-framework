# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The subset validator: every keyword passes and fails, the lint rejects what is outside the subset, and the three
real schemas and their examples are held to both. Standard library only.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

import _paths
import _jsonschema_subset as subset

ROOT = _paths.TOOLS.parent
SCHEMA_DIR = ROOT / "schema"
EXAMPLES = SCHEMA_DIR / "examples"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_of(**keywords: Any) -> dict[str, Any]:
    return {"$schema": DRAFT, **keywords}


def violations(schema: dict[str, Any], value: Any) -> list[tuple[str, str]]:
    found = subset.SubsetValidator(schema).validate(value)
    return [(v.pointer, v.keyword) for v in found]


class LintTests(unittest.TestCase):
    def problems(self, **keywords: Any) -> list[str]:
        return subset.lint_schema(schema_of(**keywords))

    def test_a_schema_inside_the_subset_has_no_problems(self) -> None:
        schema = schema_of(
            type="object",
            required=["a"],
            additionalProperties=False,
            properties={"a": {"$ref": "#/$defs/name"}, "b": {"type": ["integer", "null"], "minimum": 0, "maximum": 9}},
            **{"$defs": {"name": {"type": "string", "pattern": "^[a-z]+$", "minLength": 1, "maxLength": 9}}},
        )
        self.assertEqual(subset.lint_schema(schema), [])

    def test_every_keyword_outside_the_subset_is_named(self) -> None:
        for keyword in ("oneOf", "anyOf", "allOf", "not", "if", "format", "uniqueItems", "$comment", "prefixItems"):
            with self.subTest(keyword=keyword):
                self.assertIn(f"unsupported keyword {keyword!r}", " ".join(self.problems(**{keyword: []})))

    def test_an_unsupported_keyword_is_found_deep_inside_the_schema(self) -> None:
        schema = schema_of(type="object", properties={"a": {"type": "array", "items": {"format": "uri"}}})
        self.assertEqual(subset.lint_schema(schema), ["#/properties/a/items: unsupported keyword 'format'"])

    def test_a_boolean_schema_is_outside_the_subset(self) -> None:
        schema = schema_of(type="object", properties={"a": True})
        self.assertIn("#/properties/a: a schema must be a JSON object", subset.lint_schema(schema)[0])
        self.assertEqual(subset.lint_schema([]), ["#: a schema must be a JSON object"])

    def test_the_draft_must_be_2020_12(self) -> None:
        self.assertEqual(len(subset.lint_schema({"$schema": "http://json-schema.org/draft-07/schema#"})), 1)

    def test_root_only_keywords_are_refused_below_the_root(self) -> None:
        for keyword, value in (("$id", "urn:x"), ("$schema", DRAFT), ("$defs", {})):
            with self.subTest(keyword=keyword):
                schema = schema_of(properties={"a": {keyword: value}})
                self.assertEqual(
                    subset.lint_schema(schema),
                    [f"#/properties/a: {keyword!r} is allowed only at the root of the schema"],
                )

    def test_a_ref_must_be_local_and_must_resolve(self) -> None:
        self.assertIn("form '#/$defs/<name>'", " ".join(self.problems(properties={"a": {"$ref": "other.json"}})))
        self.assertIn("form '#/$defs/<name>'", " ".join(self.problems(properties={"a": {"$ref": "#/properties/b"}})))
        self.assertIn("names no definition", " ".join(self.problems(properties={"a": {"$ref": "#/$defs/missing"}})))

    def test_a_chain_of_refs_that_leads_back_to_itself_is_refused(self) -> None:
        defs = {"a": {"$ref": "#/$defs/b"}, "b": {"$ref": "#/$defs/a"}}
        self.assertTrue(any("leads back" in problem for problem in self.problems(**{"$defs": defs})))
        self.assertTrue(
            any("leads back" in problem for problem in self.problems(**{"$defs": {"a": {"$ref": "#/$defs/a"}}}))
        )

    def test_a_recursive_definition_that_consumes_input_is_allowed(self) -> None:
        defs = {"tree": {"type": "object", "properties": {"child": {"$ref": "#/$defs/tree"}}}}
        self.assertEqual(self.problems(**{"$defs": defs}), [])

    def test_type_must_name_known_types_without_repeats(self) -> None:
        for bad in ("str", ["string", "string"], [], 3, ["string", 4]):
            with self.subTest(bad=bad):
                self.assertEqual(len(self.problems(type=bad)), 1)
        self.assertEqual(self.problems(type=["string", "null"]), [])

    def test_enum_must_be_a_non_empty_list(self) -> None:
        self.assertEqual(len(self.problems(enum=[])), 1)
        self.assertEqual(len(self.problems(enum="abc")), 1)

    def test_additional_properties_must_be_a_boolean(self) -> None:
        self.assertEqual(len(self.problems(additionalProperties={"type": "string"})), 1)
        self.assertEqual(self.problems(additionalProperties=True), [])

    def test_counts_and_bounds_must_be_numbers_of_the_right_kind(self) -> None:
        for keyword in ("minLength", "maxLength", "minItems", "maxItems"):
            for bad in (-1, 1.5, "1", True):
                with self.subTest(keyword=keyword, bad=bad):
                    self.assertEqual(len(self.problems(**{keyword: bad})), 1)
        for keyword in ("minimum", "maximum"):
            for bad in ("1", True, float("nan"), float("inf")):
                with self.subTest(keyword=keyword, bad=bad):
                    self.assertEqual(len(self.problems(**{keyword: bad})), 1)
        self.assertEqual(self.problems(minimum=-0.5, maximum=1.5), [])

    def test_a_range_that_nothing_can_satisfy_is_refused(self) -> None:
        for low, high in (("minLength", "maxLength"), ("minItems", "maxItems"), ("minimum", "maximum")):
            with self.subTest(low=low):
                self.assertEqual(len(self.problems(**{low: 5, high: 4})), 1)

    def test_required_names_must_be_properties_and_must_not_repeat(self) -> None:
        self.assertEqual(len(self.problems(properties={"a": {}}, required=["b"])), 1)
        self.assertEqual(len(self.problems(properties={"a": {}}, required=["a", "a"])), 1)
        self.assertEqual(len(self.problems(properties={"a": {}}, required="a")), 1)
        self.assertEqual(len(self.problems(required=["a"])), 1)

    def test_a_definition_name_that_a_ref_cannot_reach_is_refused(self) -> None:
        self.assertEqual(len(self.problems(**{"$defs": {"has space": {}}})), 1)

    def test_a_pattern_that_python_and_ecmascript_read_differently_is_refused(self) -> None:
        refused = {
            r"(?i)abc": "(?:, (?= and (?!",
            r"(?P<n>a)": "(?:, (?= and (?!",
            r"(?<=a)b": "(?:, (?= and (?!",
            r"a(?>b)": "(?:, (?= and (?!",
            r"\Aabc": r"\A",
            r"abc\Z": r"\Z",
            r"\p{L}": r"\p",
            r"\h": r"\h",
            r"(a)\1": "back-reference",
            r"a*+": "possessive",
            r"a++": "possessive",
            r"a{2}+": "possessive",
            "abc\\": "lone backslash",
            r"[]a]": "literal `]`",
            r"(": "does not compile",
        }
        for pattern, reason in refused.items():
            with self.subTest(pattern=pattern):
                joined = " ".join(self.problems(type="string", pattern=pattern))
                self.assertIn(reason, joined)

    def test_a_pattern_the_two_flavours_share_is_accepted(self) -> None:
        for pattern in (
            r"^[A-Z]{2,5}-[0-9]{2,3}(:[^\s]+)?$",
            r"^[0-9]+\.[0-9]+\.[0-9]+$",
            r"^(Z|[+-][0-9]{2}:[0-9]{2})$",
            r"^An agent cannot .+ because .+$",
            r"^(?:a|b)(?=c)(?!d)\d\w\s\b\/\-\+$",
            r"a+?b*?c??",
        ):
            with self.subTest(pattern=pattern):
                self.assertEqual(self.problems(type="string", pattern=pattern), [])

    def test_a_validator_cannot_be_built_from_a_schema_outside_the_subset(self) -> None:
        with self.assertRaises(subset.SchemaError) as caught:
            subset.SubsetValidator(schema_of(oneOf=[]))
        self.assertEqual(caught.exception.problems, ["#: unsupported keyword 'oneOf'"])


class PatternTests(unittest.TestCase):
    def test_a_dollar_means_the_end_of_the_string_and_not_before_a_final_newline(self) -> None:
        pattern = subset.compile_pattern("^abc$")
        self.assertIsNotNone(pattern.search("abc"))
        self.assertIsNone(pattern.search("abc\n"))

    def test_an_escaped_dollar_and_a_dollar_in_a_class_stay_literal(self) -> None:
        self.assertIsNotNone(subset.compile_pattern(r"^a\$$").search("a$"))
        self.assertIsNone(subset.compile_pattern(r"^a\$$").search("a"))
        self.assertIsNotNone(subset.compile_pattern(r"^[$]+$").search("$$"))

    def test_a_pattern_is_not_anchored_unless_it_says_so(self) -> None:
        self.assertIsNotNone(subset.compile_pattern("b").search("abc"))


class KeywordTests(unittest.TestCase):
    def test_type_passes_and_fails_for_every_type(self) -> None:
        samples = {
            "object": ({}, 1),
            "array": ([], {}),
            "string": ("a", 1),
            "integer": (3, "3"),
            "number": (2.5, "2.5"),
            "boolean": (False, 0),
            "null": (None, 0),
        }
        for name, (good, bad) in samples.items():
            with self.subTest(type=name):
                schema = schema_of(type=name)
                self.assertEqual(violations(schema, good), [])
                self.assertEqual(violations(schema, bad), [("", "type")])

    def test_a_boolean_is_never_a_number_and_a_whole_float_is_an_integer(self) -> None:
        self.assertEqual(violations(schema_of(type="integer"), True), [("", "type")])
        self.assertEqual(violations(schema_of(type="number"), False), [("", "type")])
        self.assertEqual(violations(schema_of(type="integer"), 2.0), [])
        self.assertEqual(violations(schema_of(type="integer"), 2.5), [("", "type")])

    def test_a_list_of_types_accepts_any_of_them(self) -> None:
        schema = schema_of(type=["string", "null"])
        self.assertEqual(violations(schema, None), [])
        self.assertEqual(violations(schema, "x"), [])
        self.assertEqual(violations(schema, 1), [("", "type")])

    def test_enum_compares_by_json_equality(self) -> None:
        schema = schema_of(enum=["a", 1, None, [1, 2], {"k": True}])
        for good in ("a", 1, 1.0, None, [1, 2], {"k": True}):
            self.assertEqual(violations(schema, good), [], good)
        for bad in ("b", True, 2, [2, 1], [1], {"k": 1}, {"k": True, "j": 1}, False):
            self.assertEqual(violations(schema, bad), [("", "enum")], bad)

    def test_const_compares_by_json_equality(self) -> None:
        self.assertEqual(violations(schema_of(const=True), True), [])
        self.assertEqual(violations(schema_of(const=True), 1), [("", "const")])
        self.assertEqual(violations(schema_of(const="0.1"), "0.1"), [])
        self.assertEqual(violations(schema_of(const="0.1"), "0.2"), [("", "const")])
        self.assertEqual(violations(schema_of(const=0), False), [("", "const")])

    def test_pattern_applies_to_strings_only(self) -> None:
        schema = schema_of(pattern="^[a-z]+$")
        self.assertEqual(violations(schema, "abc"), [])
        self.assertEqual(violations(schema, "ab1"), [("", "pattern")])
        self.assertEqual(violations(schema, "abc\n"), [("", "pattern")])
        self.assertEqual(violations(schema, 5), [])

    def test_string_length_bounds_are_inclusive_and_count_characters(self) -> None:
        schema = schema_of(minLength=2, maxLength=3)
        self.assertEqual(violations(schema, "ab"), [])
        self.assertEqual(violations(schema, "abc"), [])
        self.assertEqual(violations(schema, "a"), [("", "minLength")])
        self.assertEqual(violations(schema, "abcd"), [("", "maxLength")])
        self.assertEqual(violations(schema, "é€"), [])
        self.assertEqual(violations(schema, 5), [])

    def test_number_bounds_are_inclusive_and_skip_booleans(self) -> None:
        schema = schema_of(minimum=0, maximum=1)
        for good in (0, 1, 0.5):
            self.assertEqual(violations(schema, good), [])
        self.assertEqual(violations(schema, -0.1), [("", "minimum")])
        self.assertEqual(violations(schema, 1.1), [("", "maximum")])
        self.assertEqual(violations(schema, True), [])
        self.assertEqual(violations(schema, "5"), [])

    def test_item_count_bounds_are_inclusive(self) -> None:
        schema = schema_of(minItems=1, maxItems=2)
        self.assertEqual(violations(schema, [1]), [])
        self.assertEqual(violations(schema, [1, 2]), [])
        self.assertEqual(violations(schema, []), [("", "minItems")])
        self.assertEqual(violations(schema, [1, 2, 3]), [("", "maxItems")])
        self.assertEqual(violations(schema, "abc"), [])

    def test_required_names_each_missing_property(self) -> None:
        schema = schema_of(properties={"a": {}, "b": {}, "c": {}}, required=["a", "b"])
        self.assertEqual(violations(schema, {"a": 1, "b": 2}), [])
        self.assertEqual(violations(schema, {"a": 1}), [("", "required")])
        found = subset.SubsetValidator(schema).validate({})
        self.assertEqual(
            [v.message for v in found], ["missing the required property 'a'", "missing the required property 'b'"]
        )
        self.assertEqual(violations(schema, [1]), [])

    def test_properties_are_checked_where_they_are_found(self) -> None:
        schema = schema_of(properties={"a": {"type": "string"}, "b": {"type": "integer"}})
        self.assertEqual(violations(schema, {"a": "x", "b": 1, "other": None}), [])
        self.assertEqual(violations(schema, {"a": 1, "b": "x"}), [("/a", "type"), ("/b", "type")])

    def test_additional_properties_false_names_what_is_unexpected(self) -> None:
        schema = schema_of(properties={"a": {}}, additionalProperties=False)
        self.assertEqual(violations(schema, {"a": 1}), [])
        self.assertEqual(violations(schema, {"a": 1, "z": 2, "y": 3}), [("", "additionalProperties")])
        found = subset.SubsetValidator(schema).validate({"a": 1, "z": 2, "y": 3})
        self.assertEqual(found[0].message, "unexpected properties: 'z', 'y'")
        self.assertEqual(violations(schema_of(properties={"a": {}}, additionalProperties=True), {"z": 1}), [])
        self.assertEqual(violations(schema_of(properties={"a": {}}), {"z": 1}), [])

    def test_items_applies_to_every_element_and_the_pointer_names_the_index(self) -> None:
        schema = schema_of(type="array", items={"type": "integer"})
        self.assertEqual(violations(schema, [1, 2, 3]), [])
        self.assertEqual(violations(schema, [1, "x", 3, None]), [("/1", "type"), ("/3", "type")])

    def test_a_ref_applies_the_definition_and_keeps_its_siblings(self) -> None:
        schema = schema_of(
            properties={"a": {"$ref": "#/$defs/name", "maxLength": 3}},
            **{"$defs": {"name": {"type": "string", "pattern": "^[a-z]+$"}}},
        )
        self.assertEqual(violations(schema, {"a": "abc"}), [])
        self.assertEqual(violations(schema, {"a": "ab1"}), [("/a", "pattern")])
        self.assertEqual(violations(schema, {"a": "abcd"}), [("/a", "maxLength")])
        self.assertEqual(violations(schema, {"a": 5}), [("/a", "type")])

    def test_a_recursive_definition_is_followed_as_deep_as_the_input_goes(self) -> None:
        schema = schema_of(
            **{"$ref": "#/$defs/tree"},
            **{
                "$defs": {
                    "tree": {
                        "type": "object",
                        "properties": {"n": {"type": "integer"}, "kid": {"$ref": "#/$defs/tree"}},
                    }
                }
            },
        )
        self.assertEqual(violations(schema, {"n": 1, "kid": {"n": 2, "kid": {"n": 3}}}), [])
        self.assertEqual(violations(schema, {"n": 1, "kid": {"n": 2, "kid": {"n": "3"}}}), [("/kid/kid/n", "type")])

    def test_a_pointer_escapes_slashes_and_tildes_in_property_names(self) -> None:
        schema = schema_of(properties={"a/b": {"type": "string"}, "c~d": {"type": "string"}})
        self.assertEqual(violations(schema, {"a/b": 1, "c~d": 1}), [("/a~1b", "type"), ("/c~0d", "type")])

    def test_a_keyword_that_does_not_fit_the_instance_type_is_skipped(self) -> None:
        schema = schema_of(required=["a"], properties={"a": {}}, minItems=3, minLength=3, minimum=3)
        for value in (None, True, [1, 2, 3], "abc", 5):
            self.assertNotIn("required", [kw for _, kw in violations(schema, value)], value)

    def test_a_violation_never_repeats_the_value_it_found(self) -> None:
        leaked = "sk-" + "A1b2C3d4" * 4
        schema = schema_of(
            properties={
                "a": {"type": "integer"},
                "b": {"pattern": "^[0-9]+$"},
                "c": {"enum": ["x"]},
                "d": {"maxLength": 3},
            }
        )
        found = subset.SubsetValidator(schema).validate({"a": leaked, "b": leaked, "c": leaked, "d": leaked, "e": 1})
        self.assertEqual(len(found), 4)
        self.assertNotIn(leaked, " ".join(str(v) for v in found))

    def test_a_limit_stops_the_run_and_the_order_is_fixed(self) -> None:
        schema = schema_of(type="array", items={"type": "integer"})
        instance = ["a"] * 10
        validator = subset.SubsetValidator(schema)
        self.assertEqual(len(validator.validate(instance)), 10)
        limited = validator.validate(instance, limit=3)
        self.assertEqual([v.pointer for v in limited], ["/0", "/1", "/2"])
        self.assertEqual(validator.validate(instance), validator.validate(instance))

    def test_a_violation_prints_with_its_pointer_and_the_root_as_a_slash(self) -> None:
        schema = schema_of(properties={"a": {"type": "string"}}, type="object")
        self.assertEqual(
            [str(v) for v in subset.SubsetValidator(schema).validate({"a": 1})], ["/a: expected string, got integer"]
        )
        self.assertEqual(
            [str(v) for v in subset.SubsetValidator(schema).validate(5)], ["/: expected object, got integer"]
        )


class TheRealSchemasTests(unittest.TestCase):
    def validator(self, name: str) -> subset.SubsetValidator:
        return subset.SubsetValidator(load(SCHEMA_DIR / name))

    def test_each_schema_is_inside_the_subset(self) -> None:
        for name in ("audit-report.schema.json", "audit-intake.schema.json", "catalogue.schema.json"):
            with self.subTest(schema=name):
                self.assertEqual(subset.lint_schema(load(SCHEMA_DIR / name)), [])

    def test_the_catalogue_validates(self) -> None:
        self.assertEqual(self.validator("catalogue.schema.json").validate(load(ROOT / "catalogue.json")), [])

    def test_the_intake_example_validates(self) -> None:
        examples = sorted(EXAMPLES.glob("audit-intake.*.json"))
        self.assertTrue(examples)
        for path in examples:
            with self.subTest(example=path.name):
                self.assertEqual(self.validator("audit-intake.schema.json").validate(load(path)), [])

    def report_examples(self) -> list[Path]:
        return [EXAMPLES / "minimal.json", *sorted(EXAMPLES.rglob("*.audit-*.json"))]

    def test_every_report_example_validates(self) -> None:
        examples = self.report_examples()
        self.assertGreaterEqual(len(examples), 5)
        for path in examples:
            with self.subTest(example=path.name):
                self.assertEqual(self.validator("audit-report.schema.json").validate(load(path)), [])

    def test_the_raw_engine_reports_are_not_reports_of_this_schema(self) -> None:
        raw = sorted(EXAMPLES.rglob("*.engine-report.*.json"))
        self.assertTrue(raw)
        for path in raw:
            with self.subTest(example=path.name):
                self.assertNotEqual(self.validator("audit-report.schema.json").validate(load(path)), [])

    def test_a_defect_in_an_example_is_found_at_its_place(self) -> None:
        report = copy.deepcopy(load(EXAMPLES / "minimal.json"))
        report["checks"][0]["verdict"] = "MAYBE"
        report["provenance"]["target"]["label"] = "Bad Label"
        report["surprise"] = 1
        found = [(v.pointer, v.keyword) for v in self.validator("audit-report.schema.json").validate(report)]
        self.assertEqual(
            sorted(found),
            sorted(
                [
                    ("", "additionalProperties"),
                    ("/checks/0/verdict", "enum"),
                    ("/provenance/target/label", "pattern"),
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
