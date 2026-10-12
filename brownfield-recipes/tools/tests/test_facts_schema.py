# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The facts schema accepts its example, refuses each planted breakage with a known message, and stays in step with the engine.

`schema/facts.schema.json` is the format of the file that `tools/facts.py` writes. These tests hold the schema to what the
design says of it: the example is valid; a missing key, a wrong type, an unknown key, a negative count, an absolute path
and a list over its cap are each refused; every cap in `caps` is the cap of its list; the names the schema fixes are
the engine's own; and a file with every list at its cap still fits in 30 KB. Standard library only.
"""

from __future__ import annotations

import copy
import importlib
import json
import re
import unittest
from pathlib import Path
from typing import Any

import _paths
import _jsonschema_subset as subset
import engine

SCHEMA_DIR = _paths.TOOLS.parent / "schema"
SCHEMA_PATH = SCHEMA_DIR / "facts.schema.json"
EXAMPLE_PATH = SCHEMA_DIR / "examples" / "facts.minimal.json"

# The bound in the roadmap is 30 KB. 30,000 bytes satisfies it whether a kilobyte is 1,000 or 1,024 bytes.
BOUND_BYTES = 30_000
LARGE_NUMBER = 9_999_999_999


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def messages(schema: Any, document: Any) -> list[str]:
    return [str(found) for found in subset.SubsetValidator(schema).validate(document)]


def maximal_document(schema: dict[str, Any]) -> Any:
    """A document with every object complete, every list at its `maxItems` and every string at its `maxLength`.

    Notes are filled with a three-byte character, so that the size counts bytes and not characters. Everything else is
    ASCII, which the schema's patterns require.
    """
    defs = schema["$defs"]

    def build(node: dict[str, Any], name: str) -> Any:
        if "$ref" in node:
            merged = dict(defs[node["$ref"].rsplit("/", 1)[-1]])
            merged.update({key: value for key, value in node.items() if key != "$ref"})
            return build(merged, name)
        if "const" in node:
            return node["const"]
        if "enum" in node:
            return node["enum"][-1]
        declared = node.get("type")
        types = declared if isinstance(declared, list) else [declared]
        if "object" in types:
            return {key: build(sub, key) for key, sub in node.get("properties", {}).items()}
        if "array" in types:
            return [build(node["items"], name) for _ in range(node["maxItems"])]
        if "string" in types:
            if name == "sha":
                return "f" * 64
            fill = "\u20ac" if node.get("description", "").startswith("A sentence") else "a"
            return fill * node.get("maxLength", 8)
        if "integer" in types:
            return LARGE_NUMBER
        if "boolean" in types:
            return True
        raise AssertionError(f"no value for {name}: {node}")

    return build(schema, "")


class FactsSchemaCase(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = load(SCHEMA_PATH)
        self.example = load(EXAMPLE_PATH)

    def changed(self, change: Any) -> list[str]:
        """The messages for the example after `change(document)` has edited a copy of it."""
        document = copy.deepcopy(self.example)
        change(document)
        return messages(self.schema, document)


class AcceptanceTests(FactsSchemaCase):
    def test_the_schema_is_inside_the_keyword_subset(self) -> None:
        self.assertEqual(subset.lint_schema(self.schema), [])

    def test_the_example_is_accepted(self) -> None:
        self.assertEqual(messages(self.schema, self.example), [])

    def test_the_schema_names_its_version_and_the_example_carries_it(self) -> None:
        self.assertEqual(self.schema["$id"], "urn:codebase-agentic-readiness-framework:facts:0.1")
        self.assertEqual(self.schema["properties"]["facts_version"]["const"], "0.1")
        self.assertEqual(self.example["facts_version"], "0.1")

    def test_until_the_tool_writes_every_section_two_keys_are_enough(self) -> None:
        self.assertEqual(self.schema["required"], ["facts_version", "label"])
        self.assertEqual(messages(self.schema, {"facts_version": "0.1", "label": "x"}), [])
        self.assertEqual(messages(self.schema, {"facts_version": "0.1", "label": "x", "stack": {}, "caps": {}}), [])

    def test_a_target_that_is_not_a_git_repository_is_valid(self) -> None:
        self.assertEqual(self.changed(lambda d: d["git"].update(sha=None, dirty=False)), [])

    def test_a_component_without_a_manifest_is_valid(self) -> None:
        self.assertEqual(self.changed(lambda d: d["components"]["declared"][0].update(manifest=None)), [])

    def test_a_sha_of_either_length_is_valid(self) -> None:
        self.assertEqual(self.changed(lambda d: d["git"].update(sha="a" * 40)), [])
        self.assertEqual(self.changed(lambda d: d["git"].update(sha="a" * 64)), [])


class PlantedBreakageTests(FactsSchemaCase):
    """Each breakage is refused with exactly one message, which names the place."""

    def refused(self, change: Any, *expected: str) -> None:
        self.assertEqual(self.changed(change), list(expected))

    def test_a_missing_required_key(self) -> None:
        self.refused(lambda d: d.pop("label"), "/: missing the required property 'label'")
        self.refused(lambda d: d.pop("facts_version"), "/: missing the required property 'facts_version'")

    def test_a_missing_key_inside_a_section(self) -> None:
        self.refused(lambda d: d["inventory"].pop("truncated"), "/inventory: missing the required property 'truncated'")
        self.refused(
            lambda d: d["inventory"]["by_kind"].pop("other"),
            "/inventory/by_kind: missing the required property 'other'",
        )
        self.refused(lambda d: d["git"].pop("sha"), "/git: missing the required property 'sha'")

    def test_a_wrong_type(self) -> None:
        self.refused(lambda d: d["inventory"].update(files="214"), "/inventory/files: expected integer, got string")
        self.refused(
            lambda d: d["inventory"].update(truncated=0), "/inventory/truncated: expected boolean, got integer"
        )
        self.refused(lambda d: d["stack"].update(ecosystems="node"), "/stack/ecosystems: expected array, got string")
        self.refused(lambda d: d["git"].update(dirty=None), "/git/dirty: expected boolean, got null")

    def test_an_unknown_key(self) -> None:
        self.refused(lambda d: d.update(verdict="PASS"), "/: unexpected property: 'verdict'")
        self.refused(lambda d: d["inventory"].update(score=1), "/inventory: unexpected property: 'score'")
        self.refused(lambda d: d["caps"].update(stack={}), "/caps: unexpected property: 'stack'")
        self.refused(
            lambda d: d["instruction_files"][0].update(good=True), "/instruction_files/0: unexpected property: 'good'"
        )

    def test_a_negative_count(self) -> None:
        self.refused(lambda d: d["inventory"].update(bytes=-1), "/inventory/bytes: is below the minimum of 0")
        self.refused(
            lambda d: d["inventory"]["by_kind"].update(doc=-3), "/inventory/by_kind/doc: is below the minimum of 0"
        )
        self.refused(
            lambda d: d["caps"]["excludes"].update(omitted=-1), "/caps/excludes/omitted: is below the minimum of 0"
        )
        self.refused(
            lambda d: d["inventory"]["skipped"][0].update(count=0),
            "/inventory/skipped/0/count: is below the minimum of 1",
        )

    def test_a_path_with_a_leading_slash_or_a_drive_letter(self) -> None:
        pattern = "^(?![A-Za-z]:)(?!/)[ -~]+$"
        for path in ("/etc/AGENTS.md", "C:\\repo\\AGENTS.md", "c:/repo/AGENTS.md"):
            with self.subTest(path=path):
                self.refused(
                    lambda d: d["instruction_files"][0].update(path=path),
                    f"/instruction_files/0/path: does not match the pattern {pattern}",
                )
        self.refused(
            lambda d: d["components"]["declared"][0].update(path="/work/api"),
            f"/components/declared/0/path: does not match the pattern {pattern}",
        )
        self.refused(
            lambda d: d["components"]["declared"][0].update(manifest="/work/api/package.json"),
            f"/components/declared/0/manifest: does not match the pattern {pattern}",
        )
        self.refused(
            lambda d: d["components"].update(candidates=["/srv/worker"]),
            f"/components/candidates/0: does not match the pattern {pattern}",
        )

    def test_a_path_that_is_not_printable_ascii(self) -> None:
        pattern = "^(?![A-Za-z]:)(?!/)[ -~]+$"
        for path in ("caf\u00e9/AGENTS.md", "AGENTS.md\n", "a\tb.md"):
            with self.subTest(path=path):
                self.refused(
                    lambda d: d["instruction_files"][0].update(path=path),
                    f"/instruction_files/0/path: does not match the pattern {pattern}",
                )

    def test_a_list_over_its_cap(self) -> None:
        self.refused(
            lambda d: d["instruction_files"].extend(copy.deepcopy(d["instruction_files"][0]) for _ in range(23)),
            "/instruction_files: 26 items is above the maximum of 25",
        )
        self.refused(
            lambda d: d["inventory"].update(excludes=["x"] * 11),
            "/inventory/excludes: 11 items is above the maximum of 10",
        )
        self.refused(
            lambda d: d["components"].update(candidates=["a"] * 21),
            "/components/candidates: 21 items is above the maximum of 20",
        )

    def test_a_list_at_its_cap_is_valid(self) -> None:
        def fill(document: dict[str, Any]) -> None:
            document["instruction_files"] = [copy.deepcopy(document["instruction_files"][0]) for _ in range(25)]
            document["inventory"]["excludes"] = ["x"] * 10
            document["components"]["candidates"] = ["a"] * 20

        self.assertEqual(self.changed(fill), [])

    def test_a_string_over_its_length(self) -> None:
        self.refused(
            lambda d: d["instruction_files"][0].update(path="a" * 129),
            "/instruction_files/0/path: length 129 is above the maximum of 128",
        )
        self.assertEqual(self.changed(lambda d: d["instruction_files"][0].update(path="a" * 128)), [])
        self.refused(
            lambda d: d.update(label="a" * 33), "/label: does not match the pattern ^[a-z0-9][a-z0-9._-]{0,31}$"
        )
        self.assertEqual(self.changed(lambda d: d.update(label="a" * 32)), [])

    def test_a_wrong_version(self) -> None:
        self.refused(lambda d: d.update(facts_version="0.2"), '/facts_version: expected "0.1"')

    def test_a_label_that_could_not_name_a_file(self) -> None:
        pattern = "^[a-z0-9][a-z0-9._-]{0,31}$"
        for label in ("Example Service", "-service", "a/b", ""):
            with self.subTest(label=label):
                self.refused(lambda d: d.update(label=label), f"/label: does not match the pattern {pattern}")

    def test_a_sha_that_is_not_a_full_commit_id(self) -> None:
        pattern = "^([0-9a-f]{40}|[0-9a-f]{64})$"
        for sha in ("deadbeef", "a" * 39, "A" * 40, "g" * 40):
            with self.subTest(sha=sha):
                self.refused(lambda d: d["git"].update(sha=sha), f"/git/sha: does not match the pattern {pattern}")

    def test_a_cap_that_is_not_the_lists_cap(self) -> None:
        self.refused(lambda d: d["caps"]["excludes"].update(limit=11), "/caps/excludes/limit: expected 10")
        self.refused(
            lambda d: d["caps"]["instruction_files"].update(limit=26), "/caps/instruction_files/limit: expected 25"
        )

    def test_a_size_class_the_rule_does_not_have(self) -> None:
        self.refused(
            lambda d: d["size"].update(**{"class": "gigantic"}),
            '/size/class: expected one of ["small", "medium", "large", "huge"]',
        )

    def test_a_name_that_is_not_a_table_name(self) -> None:
        pattern = "^[a-z][a-z0-9+._-]*$"
        self.refused(
            lambda d: d["stack"].update(ecosystems=["Node"]),
            f"/stack/ecosystems/0: does not match the pattern {pattern}",
        )


KINDS = ["manifest", "build", "config", "source", "test", "doc", "ci", "script", "generated", "binary", "other"]

# The format, written out. Where an object sits ("*" is the first element of a list), and which keys it must have.
REQUIRED: dict[str, list[str]] = {
    "": ["facts_version", "label"],
    "git": ["sha", "dirty"],
    "inventory": ["files", "bytes", "by_kind", "skipped", "truncated", "max_files", "excludes"],
    "inventory.by_kind": KINDS,
    "inventory.skipped.*": ["reason", "count"],
    "instruction_files.*": ["path", "variant", "size_bytes"],
    "components": ["declared", "candidates", "notes"],
    "components.declared.*": ["name", "path", "declared_by", "manifest"],
    "size": ["class", "files", "bytes", "truncated", "thresholds"],
    "size.thresholds": ["small_below", "medium_below", "large_below"],
    "caps.excludes": ["limit", "omitted"],
    "caps.instruction_files": ["limit", "omitted"],
    "caps.declared_components": ["limit", "omitted"],
    "caps.candidate_components": ["limit", "omitted"],
}
# Objects with no required key while the tool is in development. They are closed all the same.
OPEN_ENTRIES = ["stack", "caps"]

LIST_CAPS: dict[str, int] = {
    "inventory.skipped": 8,
    "inventory.excludes": 10,
    "stack.ecosystems": 12,
    "stack.source_only": 12,
    "stack.package_managers": 24,
    "stack.ci_providers": 12,
    "stack.test_frameworks": 12,
    "stack.hook_managers": 8,
    "stack.notes": 4,
    "instruction_files": 25,
    "components.declared": 16,
    "components.candidates": 20,
    "components.notes": 4,
}
LIST_ITEMS: dict[str, Any] = {"stack.source_only": "a", "stack.notes": "n", "components.notes": "n"}

STRING_LIMITS: dict[str, int] = {
    "instruction_files.*.path": 128,
    "instruction_files.*.variant": 64,
    "components.declared.*.name": 64,
    "components.declared.*.path": 128,
    "components.declared.*.declared_by": 64,
    "components.declared.*.manifest": 128,
    "components.candidates.*": 128,
    "inventory.excludes.*": 100,
    "inventory.skipped.*.reason": 24,
    "stack.ecosystems.*": 24,
    "stack.source_only.*": 24,
    "stack.package_managers.*": 24,
    "stack.ci_providers.*": 24,
    "stack.test_frameworks.*": 24,
    "stack.hook_managers.*": 24,
    "stack.notes.*": 120,
    "components.notes.*": 120,
}
LINE_ENDINGS = ["inventory.excludes.*", "instruction_files.*.variant", "components.declared.*.name"]


def pointer_of(path: str) -> str:
    return "".join("/" + ("0" if part == "*" else part) for part in path.split(".")) if path else ""


def at_path(document: Any, path: str) -> Any:
    node = document
    for part in path.split(".") if path else []:
        node = node[0 if part == "*" else part]
    return node


def put(document: dict[str, Any], path: str, value: Any) -> None:
    """Set the value at `path`. A trailing "*" makes a list of the one value."""
    *parents, last = path.split(".")
    node = at_path(document, ".".join(parents))
    if last == "*":
        node.clear()
        node.append(value)
    else:
        node[last] = value


class FormatTableTests(FactsSchemaCase):
    """The format as data. A change to the schema is a change to a table here, so that it is made on purpose."""

    def test_each_object_requires_its_keys(self) -> None:
        for path, names in REQUIRED.items():
            for name in names:
                with self.subTest(path=path, missing=name):
                    document = copy.deepcopy(self.example)
                    del at_path(document, path)[name]
                    where = pointer_of(path) or "/"
                    self.assertEqual(
                        messages(self.schema, document), [f"{where}: missing the required property '{name}'"]
                    )

    def test_each_object_is_closed(self) -> None:
        for path in [*REQUIRED, *OPEN_ENTRIES]:
            with self.subTest(path=path):
                document = copy.deepcopy(self.example)
                at_path(document, path)["extra"] = 1
                self.assertEqual(
                    messages(self.schema, document), [f"{pointer_of(path) or '/'}: unexpected property: 'extra'"]
                )

    def test_an_open_entry_may_be_empty_until_the_tool_writes_it_whole(self) -> None:
        for path in OPEN_ENTRIES:
            with self.subTest(path=path):
                document = copy.deepcopy(self.example)
                put(document, path, {})
                self.assertEqual(messages(self.schema, document), [])

    def test_each_list_has_its_cap(self) -> None:
        for path, cap in LIST_CAPS.items():
            for count, expected in (
                (cap, []),
                (cap + 1, [f"{pointer_of(path)}: {cap + 1} items is above the maximum of {cap}"]),
            ):
                with self.subTest(path=path, count=count):
                    document = copy.deepcopy(self.example)
                    current = at_path(document, path)
                    item = copy.deepcopy(current[0]) if current else LIST_ITEMS[path]
                    put(document, path, [copy.deepcopy(item) for _ in range(count)])
                    self.assertEqual(messages(self.schema, document), expected)

    def test_each_string_has_its_length(self) -> None:
        for path, limit in STRING_LIMITS.items():
            for length, expected in (
                (limit, []),
                (limit + 1, [f"{pointer_of(path)}: length {limit + 1} is above the maximum of {limit}"]),
            ):
                with self.subTest(path=path, length=length):
                    document = copy.deepcopy(self.example)
                    put(document, path, "a" * length)
                    self.assertEqual(messages(self.schema, document), expected)

    def test_a_string_the_engine_or_operator_gives_cannot_end_in_a_line_break(self) -> None:
        for path in LINE_ENDINGS:
            with self.subTest(path=path):
                document = copy.deepcopy(self.example)
                put(document, path, "a\n")
                self.assertEqual(
                    messages(self.schema, document), [f"{pointer_of(path)}: does not match the pattern ^[ -~]+$"]
                )

    def test_a_skip_reason_is_lower_case_words_joined_by_hyphens(self) -> None:
        pattern = "^[a-z][a-z-]*$"
        for reason in ("max depth", "Ignored", "ignored\n", "1x", "symlink!", "", "max_depth"):
            with self.subTest(reason=reason):
                document = copy.deepcopy(self.example)
                put(document, "inventory.skipped.*.reason", reason)
                self.assertEqual(
                    messages(self.schema, document),
                    [f"/inventory/skipped/0/reason: does not match the pattern {pattern}"],
                )
        for reason in ("ignored", "max-depth", "a"):
            document = copy.deepcopy(self.example)
            put(document, "inventory.skipped.*.reason", reason)
            self.assertEqual(messages(self.schema, document), [])

    def test_a_note_cannot_be_empty(self) -> None:
        for path in ("stack.notes.*", "components.notes.*"):
            with self.subTest(path=path):
                document = copy.deepcopy(self.example)
                put(document, path, "")
                self.assertEqual(
                    messages(self.schema, document), [f"{pointer_of(path)}: length 0 is below the minimum of 1"]
                )

    def test_a_cap_or_threshold_below_one_is_refused(self) -> None:
        for path in (
            "inventory.max_files",
            "size.thresholds.small_below",
            "size.thresholds.medium_below",
            "size.thresholds.large_below",
        ):
            with self.subTest(path=path):
                document = copy.deepcopy(self.example)
                put(document, path, 0)
                self.assertEqual(messages(self.schema, document), [f"{pointer_of(path)}: is below the minimum of 1"])

    def test_the_paths_in_the_tables_exist_in_the_example(self) -> None:
        for path in [*REQUIRED, *OPEN_ENTRIES, *LIST_CAPS, *(p for p in STRING_LIMITS if not p.endswith(".*"))]:
            with self.subTest(path=path):
                at_path(self.example, path)


class CoherenceTests(FactsSchemaCase):
    """What the schema cannot say, held in the example and in the schema's own numbers."""

    def test_the_caps_name_the_lists_they_cut(self) -> None:
        props = self.schema["properties"]
        cuts = {
            "excludes": props["inventory"]["properties"]["excludes"],
            "instruction_files": props["instruction_files"],
            "declared_components": props["components"]["properties"]["declared"],
            "candidate_components": props["components"]["properties"]["candidates"],
        }
        entries = props["caps"]["properties"]
        self.assertEqual(sorted(entries), sorted(cuts))
        for name, lst in cuts.items():
            with self.subTest(cap=name):
                ref = entries[name]["$ref"].rsplit("/", 1)[-1]
                self.assertEqual(self.schema["$defs"][ref]["properties"]["limit"]["const"], lst["maxItems"])

    def test_the_example_counts_agree(self) -> None:
        inventory, size = self.example["inventory"], self.example["size"]
        self.assertEqual(sum(inventory["by_kind"].values()), inventory["files"])
        self.assertEqual(
            (size["files"], size["bytes"], size["truncated"]),
            (inventory["files"], inventory["bytes"], inventory["truncated"]),
        )
        self.assertLess(size["files"], size["thresholds"]["small_below"])
        self.assertEqual(size["class"], "small")

    def test_the_example_lists_are_sorted(self) -> None:
        paths = [entry["path"] for entry in self.example["instruction_files"]]
        self.assertEqual(paths, sorted(paths))
        reasons = [entry["reason"] for entry in self.example["inventory"]["skipped"]]
        self.assertEqual(reasons, sorted(reasons))
        declared = [entry["path"] for entry in self.example["components"]["declared"]]
        self.assertEqual(declared, sorted(declared))
        self.assertEqual(self.example["components"]["candidates"], sorted(self.example["components"]["candidates"]))
        for name, names in self.example["stack"].items():
            self.assertEqual(names, sorted(names), name)

    def test_a_document_keeps_the_sections_in_the_schemas_order(self) -> None:
        order = list(self.schema["properties"])
        self.assertEqual(list(self.example), [name for name in order if name in self.example])

    def test_no_value_in_the_example_is_a_time_or_an_absolute_path(self) -> None:
        strings: list[str] = []

        def collect(node: Any) -> None:
            if isinstance(node, str):
                strings.append(node)
            elif isinstance(node, list):
                for item in node:
                    collect(item)
            elif isinstance(node, dict):
                for item in node.values():
                    collect(item)

        collect(self.example)
        self.assertGreater(len(strings), 20)
        for text in strings:
            with self.subTest(text=text):
                self.assertIsNone(re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}", text), "a date")
                self.assertFalse(text.startswith("/"), "a rooted path")
                self.assertIsNone(re.match(r"^[A-Za-z]:", text), "a drive letter")


class EngineStepTests(FactsSchemaCase):
    """The names the schema fixes are the engine's, so a change in the engine fails here and not in a run."""

    def engine_module(self, name: str) -> Any:
        engine.load_engine()
        return importlib.import_module(name)

    def test_by_kind_is_the_engines_kinds_in_the_engines_order(self) -> None:
        kinds = [kind.value for kind in self.engine_module("audit.scan").Kind]
        by_kind = self.schema["properties"]["inventory"]["properties"]["by_kind"]
        self.assertEqual(list(by_kind["properties"]), kinds)
        self.assertEqual(by_kind["required"], kinds)

    def test_every_table_name_fits_its_list_and_the_name_pattern(self) -> None:
        stack = self.engine_module("audit.stack")
        stack_props = self.schema["properties"]["stack"]["properties"]
        tables = {
            "ecosystems": stack.ECOSYSTEM_SIGNALS,
            "source_only": stack.SOURCE_SIGNALS,
            "package_managers": stack.PACKAGE_MANAGERS,
            "ci_providers": stack.CI_PROVIDERS,
            "test_frameworks": stack.TEST_FRAMEWORKS,
            "hook_managers": stack.HOOK_MANAGERS,
        }
        token = subset.compile_pattern(self.schema["$defs"]["token"]["pattern"])
        longest = self.schema["$defs"]["token"]["maxLength"]
        for field, table in tables.items():
            with self.subTest(field=field):
                self.assertGreaterEqual(stack_props[field]["maxItems"], len(table))
                for name in table:
                    self.assertRegex(name, token)
                    self.assertLessEqual(len(name), longest)

    def test_the_engines_notes_fit(self) -> None:
        notes = [
            "python recognised from its source files: no manifest names it",
            "no recognised build manifest \u2014 stack-dependent checks report UNKNOWN",
            "single-root repository: no component declarations found",
        ]
        limit = self.schema["$defs"]["note"]["maxLength"]
        for note in notes:
            with self.subTest(note=note):
                self.assertLessEqual(len(note), limit)


class WorstCaseTests(FactsSchemaCase):
    def test_a_file_with_every_list_at_its_cap_and_every_string_at_its_length_is_valid(self) -> None:
        self.assertEqual(messages(self.schema, maximal_document(self.schema)), [])

    def test_that_file_fits_in_30_kb(self) -> None:
        text = json.dumps(maximal_document(self.schema), indent=2, ensure_ascii=False) + "\n"
        size = len(text.encode("utf-8"))
        self.assertLessEqual(
            size, BOUND_BYTES, f"the worst case is {size} bytes; lower a cap or a length, not the bound"
        )

    def test_the_generator_fills_a_list_to_its_cap(self) -> None:
        document = maximal_document(self.schema)
        self.assertEqual(len(document["instruction_files"]), 25)
        self.assertEqual(len(document["components"]["candidates"]), 20)
        self.assertEqual(len(document["instruction_files"][0]["path"]), 128)
        self.assertEqual(len(document["stack"]["notes"][0]), 120)


if __name__ == "__main__":
    unittest.main()
