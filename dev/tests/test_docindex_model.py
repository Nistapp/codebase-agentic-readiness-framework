# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Unit tests for the document index's model, its JSON Schema, its config and its command-line skeleton."""

from __future__ import annotations

import ast
import io
import json
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable

import _dev_paths  # noqa: F401  (puts dev/ on sys.path)
import doc_index
import docindex
from docindex import cli, model

DEV = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((DEV / "docindex" / "index.schema.json").read_text(encoding="utf-8"))

HASH_A = model.content_hash("a")
HASH_B = model.content_hash("b")


def _sample_nodes() -> list[model.Node]:
    return [
        model.IdNode(address="CMD-01", kind="check", title="Command surface", defined_by="audit/catalogue.json"),
        model.SectionNode(
            address="docs/README.md#docs/start", title="Start", level=2, own_hash=HASH_A, tree_hash=HASH_B
        ),
        model.FileNode(path="docs/README.md", kind="markdown", zone="docs"),
        model.FileNode(path="audit/catalogue.json", kind="json", zone="recipe"),
        model.SectionNode(address="docs/README.md#docs", title="Docs", level=1, own_hash=HASH_B, tree_hash=HASH_A),
    ]


def _sample_edges() -> list[model.Edge]:
    return [
        model.Edge(kind="mentions", source="docs/README.md#docs/start", target="CMD-01", confidence="name-match"),
        model.Edge(kind="contains", source="docs/README.md", target="docs/README.md#docs"),
        model.Edge(kind="links", source="docs/README.md#docs", target="audit/catalogue.json", anchor="top"),
        model.Edge(kind="contains", source="docs/README.md#docs", target="docs/README.md#docs/start"),
        model.Edge(kind="links", source="docs/README.md#docs", target="audit/catalogue.json"),
    ]


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
    """A small check of the schema keywords the index schema uses; not a general JSON Schema validator."""
    schema = _resolve(schema)
    if "oneOf" in schema:
        matches = [option for option in schema["oneOf"] if not _problems(value, option, where)]
        return [] if len(matches) == 1 else [f"{where}: matches {len(matches)} of the oneOf options"]
    problems: list[str] = []
    kinds: dict[str, type[object]] = {"object": dict, "array": list, "string": str, "integer": int}
    expected = schema.get("type")
    if expected is not None and (not isinstance(value, kinds[expected]) or isinstance(value, bool)):
        return [f"{where}: not of type {expected}"]
    if "const" in schema and value != schema["const"]:
        problems.append(f"{where}: {value!r} is not {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{where}: {value!r} is not in the enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            problems.append(f"{where}: shorter than minLength")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append(f"{where}: {value!r} does not match {schema['pattern']!r}")
    if isinstance(value, int) and not isinstance(value, bool):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            problems.append(f"{where}: {value} is out of range")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        problems += [f"{where}: missing {key!r}" for key in schema.get("required", []) if key not in value]
        if schema.get("additionalProperties") is False:
            problems += [f"{where}: unexpected {key!r}" for key in value if key not in properties]
        for key, item in value.items():
            if key in properties:
                problems += _problems(item, properties[key], f"{where}.{key}")
    if isinstance(value, list) and "items" in schema:
        for number, item in enumerate(value):
            problems += _problems(item, schema["items"], f"{where}[{number}]")
    return problems


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = doc_index.main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue(), err.getvalue()


class SerialisationTest(unittest.TestCase):
    def test_two_runs_are_byte_identical(self) -> None:
        first = model.to_json(model.Index(nodes=tuple(_sample_nodes()), edges=tuple(_sample_edges())))
        second = model.to_json(model.Index(nodes=tuple(_sample_nodes()), edges=tuple(_sample_edges())))
        self.assertEqual(first.encode("utf-8"), second.encode("utf-8"))

    def test_input_order_does_not_change_the_output(self) -> None:
        forward = model.Index(nodes=tuple(_sample_nodes()), edges=tuple(_sample_edges()))
        backward = model.Index(nodes=tuple(reversed(_sample_nodes())), edges=tuple(reversed(_sample_edges())))
        self.assertEqual(model.to_json(forward), model.to_json(backward))

    def test_nodes_and_edges_are_sorted(self) -> None:
        data = json.loads(model.to_json(model.Index(nodes=tuple(_sample_nodes()), edges=tuple(_sample_edges()))))
        self.assertEqual(
            [node["address"] for node in data["nodes"]],
            ["CMD-01", "audit/catalogue.json", "docs/README.md", "docs/README.md#docs", "docs/README.md#docs/start"],
        )
        keys = [(e["source"], e["kind"], e["target"], e.get("anchor", "")) for e in data["edges"]]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(keys[0], ("docs/README.md", "contains", "docs/README.md#docs", ""))

    def test_keys_are_sorted_and_the_text_ends_with_a_newline(self) -> None:
        text = model.to_json(model.Index(nodes=tuple(_sample_nodes()), edges=tuple(_sample_edges())))
        self.assertTrue(text.endswith("}\n"))
        self.assertEqual(text, json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def test_no_timestamp_absolute_path_or_line_number(self) -> None:
        text = model.to_json(model.Index(nodes=tuple(_sample_nodes()), edges=tuple(_sample_edges())))
        self.assertNotIn(str(DEV), text)
        for key in ("line", "lines", "line_number", "timestamp", "generated_at", "date"):
            self.assertNotIn(f'"{key}"', text)

    def test_round_trip(self) -> None:
        index = model.Index(nodes=tuple(_sample_nodes()), edges=tuple(_sample_edges()))
        text = model.to_json(index)
        self.assertEqual(model.to_json(model.from_json(text)), text)

    def test_another_format_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            model.from_dict({"edges": [], "index_format": 0, "nodes": []})

    def test_the_package_exports_the_model(self) -> None:
        self.assertIs(docindex.Index, model.Index)
        self.assertEqual(docindex.INDEX_FORMAT, 1)


class ValidationTest(unittest.TestCase):
    def test_a_bad_value_is_refused(self) -> None:
        cases: list[Callable[[], object]] = [
            lambda: model.FileNode(path="/abs/file.md", kind="markdown", zone="docs"),
            lambda: model.FileNode(path="docs/../x.md", kind="markdown", zone="docs"),
            lambda: model.FileNode(path="docs/x.md", kind="toml", zone="docs"),
            lambda: model.FileNode(path="docs/x.md", kind="markdown", zone="elsewhere"),
            lambda: model.SectionNode(address="docs/x.md", title="X", level=1, own_hash=HASH_A, tree_hash=HASH_A),
            lambda: model.SectionNode(address="docs/x.md#a//b", title="X", level=1, own_hash=HASH_A, tree_hash=HASH_A),
            lambda: model.SectionNode(address="docs/x.md#a", title="X", level=7, own_hash=HASH_A, tree_hash=HASH_A),
            lambda: model.SectionNode(address="docs/x.md#a", title="X", level=1, own_hash="abc", tree_hash=HASH_A),
            lambda: model.IdNode(address="CMD-01", kind="rule", title="", defined_by="audit/catalogue.json"),
            lambda: model.IdNode(address="CMD-01", kind="check", title="", defined_by=""),
            lambda: model.Edge(kind="cites", source="a", target="b"),
            lambda: model.Edge(kind="links", source="a", target="b", confidence="maybe"),
            lambda: model.Edge(kind="mentions", source="a", target="b", anchor="x"),
            lambda: model.Index(nodes=(model.FileNode("a.md", "markdown", "docs"),) * 2),
            lambda: model.Index(edges=(model.Edge("contains", "a", "b"),) * 2),
        ]
        for number, case in enumerate(cases):
            with self.subTest(case=number), self.assertRaises(ValueError):
                case()

    def test_section_path(self) -> None:
        section = model.SectionNode(address="a/b.md#x/y", title="Y", level=2, own_hash=HASH_A, tree_hash=HASH_A)
        self.assertEqual(section.path, "a/b.md")


class SchemaTest(unittest.TestCase):
    def test_the_schema_is_draft_2020_12(self) -> None:
        self.assertEqual(SCHEMA["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_the_empty_index_validates(self) -> None:
        data = json.loads(model.to_json(model.Index()))
        self.assertEqual(data, {"edges": [], "index_format": model.INDEX_FORMAT, "nodes": []})
        self.assertEqual(set(data), set(SCHEMA["required"]))
        self.assertEqual(_problems(data, SCHEMA), [])

    def test_an_index_with_each_node_and_edge_validates(self) -> None:
        data = json.loads(model.to_json(model.Index(nodes=tuple(_sample_nodes()), edges=tuple(_sample_edges()))))
        self.assertEqual(_problems(data, SCHEMA), [])

    def test_each_serialised_node_has_exactly_its_schema_keys(self) -> None:
        for node in _sample_nodes():
            definition = SCHEMA["$defs"][node.to_dict()["node"]]
            with self.subTest(node=node.address):
                self.assertEqual(set(node.to_dict()), set(definition["required"]))

    def test_the_schema_enums_match_the_model(self) -> None:
        defs = SCHEMA["$defs"]
        self.assertEqual(tuple(defs["file"]["properties"]["kind"]["enum"]), model.FILE_KINDS)
        self.assertEqual(tuple(defs["file"]["properties"]["zone"]["enum"]), model.ZONES)
        self.assertEqual(tuple(defs["id"]["properties"]["kind"]["enum"]), model.ID_KINDS)
        self.assertEqual(tuple(defs["edge"]["properties"]["kind"]["enum"]), model.EDGE_KINDS)
        self.assertEqual(tuple(defs["edge"]["properties"]["confidence"]["enum"]), model.CONFIDENCES)
        self.assertEqual(SCHEMA["properties"]["index_format"]["const"], model.INDEX_FORMAT)

    def test_a_broken_index_does_not_validate(self) -> None:
        cases: list[dict[str, Any]] = [
            {"edges": [], "nodes": []},
            {"edges": [], "index_format": 1, "nodes": [], "built_at": "today"},
            {"edges": [], "index_format": 1, "nodes": [{"address": "x.md", "node": "file", "kind": "markdown"}]},
            {"edges": [{"kind": "links", "source": "a", "target": "b"}], "index_format": 1, "nodes": []},
            {
                "edges": [],
                "index_format": 1,
                "nodes": [{"address": "/x.md", "kind": "other", "node": "file", "zone": "dev"}],
            },
        ]
        for number, data in enumerate(cases):
            with self.subTest(case=number):
                self.assertNotEqual(_problems(data, SCHEMA), [])


class ConfigTest(unittest.TestCase):
    def test_the_config_keys_are_sorted(self) -> None:
        text = doc_index.CONFIG.read_text(encoding="utf-8")
        self.assertEqual(text, json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def test_the_config_uses_the_model_values(self) -> None:
        config = doc_index.load_config()
        self.assertIn(config["default_zone"], model.ZONES)
        self.assertLessEqual(set(config["zones"].values()), set(model.ZONES))
        self.assertLessEqual(set(config["file_kinds"].values()), set(model.FILE_KINDS))
        self.assertLessEqual(set(config["ids"]), set(model.ID_KINDS))

    def test_each_id_pattern_finds_its_example(self) -> None:
        examples = {
            "adr": ("see ADR 0011 here", "0011"),
            "check": ("the check CMD-01 fails", "CMD-01"),
            "playbook": ("follow implement/playbooks/register-index.md", "register-index"),
            "requirement": ("REQ-SH-060 says", "REQ-SH-060"),
            "schema": ("read catalogue.schema.json", "catalogue.schema.json"),
            "tool": ("run python3 audit/tools/engine.py", "audit/tools/engine.py"),
        }
        ids = doc_index.load_config()["ids"]
        self.assertEqual(set(ids), set(examples))
        for kind, (text, expected) in examples.items():
            with self.subTest(kind=kind):
                match = re.search(ids[kind]["pattern"], text)
                self.assertIsNotNone(match)
                assert match is not None
                self.assertEqual(match.group(1), expected)

    def test_artefacts_are_skipped_and_engine_fixtures_listed_only(self) -> None:
        exclude = doc_index.load_config()["exclude"]
        self.assertIn("artefacts/", exclude["skip"])
        self.assertIn("audit/engine/tests/fixtures/", exclude["list_only"])

    def test_the_sweep_scope(self) -> None:
        sweep = doc_index.load_config()["sweep"]
        self.assertEqual(sweep["bundle_references"]["module"], "dev/build_skills.py")
        self.assertIn("greenfield/templates/", sweep["paths"])
        self.assertIn("AGENTS.md", sweep["file_names"])


class CliTest(unittest.TestCase):
    def test_build_writes_a_valid_index_and_a_summary(self) -> None:
        code, out, err = _run(["build"])
        self.assertEqual(code, 0)
        index = json.loads(out)
        self.assertEqual(_problems(index, SCHEMA), [])
        self.assertTrue(any(node["node"] == "file" for node in index["nodes"]))
        self.assertTrue(err.startswith("doc_index.py build: "), err)
        self.assertIn(" Markdown files parsed, ", err)

    def test_the_other_commands_are_not_implemented_yet(self) -> None:
        for argv in ():
            with self.subTest(argv=argv):
                code, out, err = _run(argv)
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertIn("not implemented yet", err)

    def test_a_usage_error_exits_2(self) -> None:
        for argv in ([], ["nothing"], ["diff"], ["query"]):
            with self.subTest(argv=argv):
                self.assertEqual(_run(argv)[0], 2)

    def test_cli_main_without_a_config(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(cli.main(["build"], root=doc_index.REPO), 0)
        index = json.loads(out.getvalue())
        self.assertEqual(_problems(index, SCHEMA), [])
        self.assertTrue(any(node["node"] == "file" for node in index["nodes"]))
        self.assertTrue(err.getvalue().startswith("doc_index.py build: "), err.getvalue())
        self.assertIn(" Markdown files parsed, ", err.getvalue())


class BoundaryTest(unittest.TestCase):
    def test_the_core_imports_the_standard_library_and_itself_only(self) -> None:
        for path in sorted((DEV / "docindex").glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    with self.subTest(file=path.name, module=name):
                        self.assertIn(name.partition(".")[0], sys.stdlib_module_names | {"__future__"})


if __name__ == "__main__":
    unittest.main()
