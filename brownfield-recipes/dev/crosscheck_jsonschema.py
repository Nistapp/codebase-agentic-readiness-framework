# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Cross-check the subset validator against the reference ``jsonschema`` package. Development and CI only.

The tools validate reports with ``tools/_jsonschema_subset.py`` because they may import nothing outside the standard
library. That validator is only worth trusting if it agrees with the reference implementation, so this script holds the
two against each other. It is not a tool and nothing in a release imports it; the reference package is installed for
the run alone, in a throwaway environment, and nothing is added to the project. Run it with ``make crosscheck``, which is
part of ``make check``.

What must agree, and the run fails if any of it does not:

* both accept each of the four schemas;
* both accept every example, and the check catalogue, the intake example and the facts example;
* both give the same errors, as a set of ``(place in the document, keyword)``, on the raw engine reports, which are
  not reports of this schema and fail it in many ways;
* both give the same answer, and the same errors, on a few thousand mutants of the examples, each with one defect:
  a value of the wrong type, a value out of range, a property removed, a property added, a list made too long or
  too short, and, wherever the schema sets a bound, a value one below, at and one above it. A mutant is made for
  each kind of change at each distinct place in the schema, not at each copy of it.
  The three realistic drafts have one shape, so only the first is mutated, cut to its first few checks and findings
  because every mutant is validated whole. The engine fixture corpus's expected files (S4.2.1) likewise share one
  shape, so only the first is mutated. The engine payloads under ``data`` are an open object that the schema does
  not constrain, so only its ``kind`` is mutated.

One difference is deliberate and is not tried here. The schemas' patterns are ECMAScript, where ``$`` means the end
of the string. Python's ``re``, which the reference package uses, also lets ``$`` match before a final newline, so
the subset validator refuses a value such as ``"abc\\n"`` where the reference accepts it. ``test_jsonschema_subset.py``
holds that behaviour.

Run by hand: ``PYTHONPATH=brownfield-recipes/tools uv run --no-project --with jsonschema==4.23.0 python <this file>``.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import _jsonschema_subset as subset

RECIPES = Path(__file__).resolve().parent.parent
SCHEMAS = RECIPES / "schema"
EXAMPLES = SCHEMAS / "examples"
REFERENCE_PACKAGE = "jsonschema"
MAX_REPORTED = 25

Place = tuple[str, str]
Where = tuple[Any, ...]

# Values that replace a node: every JSON type, an empty string, and a string and a list too long for most bounds.
SENTINELS: tuple[Any, ...] = (None, True, 0, -1, 1.5, "x", "", "x" * 700, [], {}, [None] * 60)
EXTRA_ITEMS = 60
KEPT_CHECKS = 8
KEPT_FINDINGS = 6


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pointer_of(tokens: Iterable[Any]) -> str:
    return "".join("/" + subset.escape_token(str(token)) for token in tokens)


def reference_errors(validator: Any, document: Any) -> set[Place]:
    return {(pointer_of(error.absolute_path), str(error.validator)) for error in validator.iter_errors(document)}


def subset_errors(validator: subset.SubsetValidator, document: Any) -> set[Place]:
    return {(violation.pointer, violation.keyword) for violation in validator.validate(document)}


# --- Mutants ------------------------------------------------------------------------------------------


def walk(node: Any, path: Where = ()) -> Iterator[tuple[Where, Any]]:
    """Every node of a document, a parent before its children, in document order."""
    yield path, node
    if isinstance(node, dict):
        for name, child in node.items():
            yield from walk(child, (*path, name))
    elif isinstance(node, list):
        for index, child in enumerate(node):
            yield from walk(child, (*path, index))


def shape(path: Where) -> Where:
    """A place with each list index replaced, so that every copy of a place in the schema counts as one."""
    return tuple("*" if isinstance(token, int) else token for token in path)


def constant(value: Any) -> Callable[[Any], Any]:
    return lambda _old: value


def without(name: str) -> Callable[[Any], Any]:
    return lambda old: {key: value for key, value in old.items() if key != name}


def edited(document: Any, path: Where, change: Callable[[Any], Any]) -> Any:
    """A copy of `document` with the node at `path` replaced by `change(node)`. Only the containers on the path are copied."""
    if not path:
        return change(document)
    head, rest = path[0], path[1:]
    if isinstance(document, dict):
        copy_of_dict = dict(document)
        copy_of_dict[head] = edited(document[head], rest, change)
        return copy_of_dict
    copy_of_list = list(document)
    copy_of_list[head] = edited(document[head], rest, change)
    return copy_of_list


def trimmed(document: Any) -> Any:
    """A long report or catalogue cut to its first checks and findings, which hold every shape the rest hold."""
    if not isinstance(document, dict) or len(document.get("checks", [])) <= KEPT_CHECKS * 2:
        return document
    cut = {**document, "checks": document["checks"][:KEPT_CHECKS]}
    if "findings" in document:
        cut["findings"] = document["findings"][:KEPT_FINDINGS]
    return cut


def inside_open_object(where: Where) -> bool:
    """Whether a place is below `data`, the one open object in the schemas, other than its `kind`."""
    return "data" in where and where[where.index("data") + 1 :] not in ((), ("kind",))


def merged(schema: Any, node: Any) -> dict[str, Any]:
    """A subschema with the definition its `$ref` names folded in, to read its bounds and to walk down it."""
    if not isinstance(node, dict):
        return {}
    folded: dict[str, Any] = {}
    if "$ref" in node:
        folded.update(merged(schema, schema["$defs"][node["$ref"].rsplit("/", 1)[-1]]))
    folded.update({key: value for key, value in node.items() if key != "$ref"})
    return folded


def subschema_at(schema: Any, where: Where) -> dict[str, Any]:
    """The subschema that governs a place in a document, as `shape` names it."""
    node = merged(schema, schema)
    for token in where:
        node = merged(schema, node.get("items", {}) if token == "*" else node.get("properties", {}).get(token, {}))
    return node


def boundary_values(sub: dict[str, Any], node: Any) -> Iterator[tuple[str, Any]]:
    """Values for `node` one below, at and one above each bound its subschema sets, with what each one is."""
    if isinstance(node, bool):
        return
    if isinstance(node, str):
        for key in ("minLength", "maxLength"):
            for size in (sub[key] - 1, sub[key], sub[key] + 1) if key in sub else ():
                if size >= 0:
                    yield f"a string of {size} characters ({key})", "a" * size
    elif isinstance(node, list):
        for key in ("minItems", "maxItems"):
            for size in (sub[key] - 1, sub[key], sub[key] + 1) if key in sub else ():
                if size >= 0:
                    yield f"a list of {size} items ({key})", (node[:1] or [None]) * size
    elif isinstance(node, (int, float)):
        for key in ("minimum", "maximum"):
            for delta in (-1, 0, 1) if key in sub else ():
                yield f"{sub[key] + delta} ({key} {delta:+d})", sub[key] + delta


def mutants(document: Any, schema: Any) -> Iterator[tuple[str, Any]]:
    """Each distinct one-defect change of `document`, with a label that says what was changed and where."""
    seen: set[tuple[Any, ...]] = set()

    def fresh(*tag: Any) -> bool:
        if tag in seen:
            return False
        seen.add(tag)
        return True

    for path, node in walk(document):
        where = shape(path)
        if inside_open_object(where):
            continue
        if path:
            for number, sentinel in enumerate(SENTINELS):
                if fresh("replace", where, number):
                    label = f"{pointer_of(path)} replaced by {json.dumps(sentinel)[:30]}"
                    yield label, edited(document, path, constant(sentinel))
        if path:
            for what, value in boundary_values(subschema_at(schema, where), node):
                if fresh("bound", where, what):
                    yield f"{pointer_of(path)} replaced by {what}", edited(document, path, constant(value))
        if isinstance(node, dict):
            for name in node:
                if fresh("delete", where, name):
                    yield f"{pointer_of(path)} loses {name!r}", edited(document, path, without(name))
            if fresh("add", where):
                yield (
                    f"{pointer_of(path)} gains an unexpected property",
                    edited(document, path, lambda old: {**old, "unexpected_property": 1}),
                )
        elif isinstance(node, bool):
            continue
        elif isinstance(node, (int, float)):
            if fresh("raise", where):
                yield f"{pointer_of(path)} raised by a million", edited(document, path, lambda old: old + 1_000_000)
            if fresh("lower", where):
                yield f"{pointer_of(path)} made negative", edited(document, path, lambda old: -abs(old) - 1)
        elif isinstance(node, str):
            if fresh("shout", where):
                yield (
                    f"{pointer_of(path)} upper-cased and punctuated",
                    edited(document, path, lambda old: old.upper() + "!"),
                )
        elif isinstance(node, list) and node:
            if fresh("grow", where):
                yield (
                    f"{pointer_of(path)} made far too long",
                    edited(document, path, lambda old: old + old[:1] * EXTRA_ITEMS),
                )
            if fresh("shrink", where):
                yield f"{pointer_of(path)} loses its first item", edited(document, path, lambda old: old[1:])


# --- The run ------------------------------------------------------------------------------------------


def main() -> int:
    try:
        reference = importlib.import_module(REFERENCE_PACKAGE)
    except ImportError:
        print(
            f"crosscheck: the reference package {REFERENCE_PACKAGE!r} is not installed; run `make crosscheck`",
            file=sys.stderr,
        )
        return 1

    schema_files = {
        "report": "audit-report.schema.json",
        "intake": "audit-intake.schema.json",
        "catalogue": "catalogue.schema.json",
        "facts": "facts.schema.json",
        "eval_expected": "eval-expected.schema.json",
    }
    pairs: dict[str, tuple[Any, subset.SubsetValidator]] = {}
    schemas: dict[str, Any] = {}
    problems: list[str] = []
    for name, filename in schema_files.items():
        schema = load(SCHEMAS / filename)
        try:
            reference.Draft202012Validator.check_schema(schema)
        except reference.SchemaError as exc:
            problems.append(f"{filename}: the reference package refuses the schema: {exc.message}")
            continue
        lint = subset.lint_schema(schema)
        if lint:
            problems.extend(f"{filename}: the lint refuses the schema: {line}" for line in lint)
            continue
        pairs[name] = (reference.Draft202012Validator(schema), subset.SubsetValidator(schema))
        schemas[name] = schema

    valid_documents: list[tuple[str, str, Path]] = [
        ("report", "report", EXAMPLES / "minimal.json"),
        *(("report", "report", path) for path in sorted(EXAMPLES.glob("example-service.audit-report.*.json"))),
        *(("report", "report", path) for path in sorted(EXAMPLES.rglob("*.audit-draft.*.json"))),
        *(("intake", "intake", path) for path in sorted(EXAMPLES.glob("audit-intake.*.json"))),
        ("catalogue", "catalogue", RECIPES / "catalogue.json"),
        ("facts", "facts", EXAMPLES / "facts.minimal.json"),
        *(("eval_expected", "eval_expected", path) for path in sorted(EXAMPLES.glob("eval-expected.*.json"))),
        *(("eval_expected", "eval_expected", path) for path in sorted(EXAMPLES.glob("eval-expected/fixtures/*.json"))),
    ]
    invalid_documents = [("report", path) for path in sorted(EXAMPLES.rglob("*.engine-report.*.json"))]

    accepted = 0
    for _, name, path in valid_documents:
        if name not in pairs:
            continue
        ref, ours = pairs[name]
        found_ref, found_ours = reference_errors(ref, load(path)), subset_errors(ours, load(path))
        if found_ref or found_ours:
            problems.append(
                f"{path.name}: should be valid; the reference finds {len(found_ref)} errors, the subset validator {len(found_ours)}"
            )
        accepted += 1

    compared = 0
    for name, path in invalid_documents:
        if name not in pairs:
            continue
        ref, ours = pairs[name]
        found_ref, found_ours = reference_errors(ref, load(path)), subset_errors(ours, load(path))
        if not found_ref:
            problems.append(f"{path.name}: expected to be invalid, but the reference accepts it")
        for place in sorted(found_ref - found_ours):
            problems.append(f"{path.name}: {place[0] or '/'} {place[1]}: only the reference reports it")
        for place in sorted(found_ours - found_ref):
            problems.append(f"{path.name}: {place[0] or '/'} {place[1]}: only the subset validator reports it")
        compared += 1

    total = invalid = 0
    unmutated = set(sorted(EXAMPLES.rglob("*.audit-draft.*.json"))[1:])
    # One fixture's expected file stands in for the other 88 (the engine's one-defect fixture corpus,
    # S4.2.1): they all share one schema and the same shape, so mutating all of them adds runtime with
    # no new coverage.
    unmutated |= set(sorted(EXAMPLES.glob("eval-expected/fixtures/*.json"))[1:])
    for _, name, path in valid_documents:
        if name not in pairs:
            continue
        ref, ours = pairs[name]
        if path in unmutated:
            continue
        for label, mutant in mutants(trimmed(load(path)), schemas[name]):
            found_ref, found_ours = reference_errors(ref, mutant), subset_errors(ours, mutant)
            total += 1
            invalid += bool(found_ref)
            if found_ref != found_ours:
                only_ref = sorted(found_ref - found_ours)[:2]
                only_ours = sorted(found_ours - found_ref)[:2]
                problems.append(
                    f"{path.name}: {label}: only the reference {only_ref}; only the subset validator {only_ours}"
                )

    version = importlib.metadata.version(REFERENCE_PACKAGE)
    print(f"crosscheck: {len(pairs)} schemas accepted by both (reference: {REFERENCE_PACKAGE} {version})")
    print(f"crosscheck: {accepted} documents accepted by both")
    print(f"crosscheck: {compared} documents that fail the schema give the same errors in both")
    print(f"crosscheck: {total} mutants ({invalid} invalid, {total - invalid} valid) give the same errors in both")
    if problems:
        print(
            f"crosscheck: {len(problems)} disagreements; the first {min(len(problems), MAX_REPORTED)}:", file=sys.stderr
        )
        for line in problems[:MAX_REPORTED]:
            print(f"  {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
