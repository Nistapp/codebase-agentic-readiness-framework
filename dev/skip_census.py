# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Count the skip markers in this repository's test trees; fail when the count goes above the baseline.

    skip_census.py check  [--root DIR] [--baseline FILE]
    skip_census.py record [--root DIR] [--baseline FILE]

A skip marker is a place where a test can stop without passing or failing. The census parses each Python file under
the five test trees (``TEST_TREES``; any ``fixtures`` folder is left out, because fixtures are data) and counts:

* a decorator whose last name is ``skip``, ``skipIf``, ``skipUnless``, ``expectedFailure``, ``skipif`` or ``xfail``
  (``@unittest.skipIf(...)``, ``@skip(...)``, ``@pytest.mark.xfail``);
* a call to ``.skipTest(...)`` or ``pytest.skip(...)``;
* a ``raise`` of ``SkipTest`` (``raise unittest.SkipTest(...)``).

It reads the syntax tree, so a marker inside a string (a test that writes a fixture file) is not counted.

``check`` compares the count with ``counts.skips.count`` in ``.quality-baseline.json``:

* count above the baseline: exit 1, listing every marker. AGENTS.md says never skip a test to get green; raising the
  number needs the owner;
* count equal: exit 0;
* count below the baseline: exit 0, with a request to run ``record`` in the same change so the gain is kept.

``record`` writes today's count into the baseline. It creates the entry when it is missing and lowers it when the
count fell, and it refuses (exit 1) to raise it: a baseline only goes down. The engine's own skip census, "``TST-03``
skip / xfail census" in ``make self-audit``, is a narrower regex count (it does not see ``self.skipTest``), so this
census is the gate. Dev-only: the Makefile runs it from ``make self-audit``; nothing in ``tools/`` or the engine
imports it. Standard library only.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASELINE = Path(".quality-baseline.json")
KEY = "skips"
TEST_TREES = (
    "audit/engine/tests",
    "audit/tools/tests",
    "implement/tools/tests",
    "greenfield/bootstrap/tests",
    "dev/tests",
)
_DECORATOR_NAMES = frozenset({"skip", "skipIf", "skipUnless", "expectedFailure", "skipif", "xfail"})
_CALL_NAMES = frozenset({"skipTest"})
_ENTRY = {
    "what": "skip markers (skip, skipIf, skipUnless, expectedFailure decorators, skipTest calls, raise SkipTest) in "
    "the five test trees, fixtures excluded",
    "command": "python3 dev/skip_census.py check",
    "verb": "make self-audit",
}


@dataclass(frozen=True)
class Marker:
    path: str
    line: int
    kind: str


def _last_name(node: ast.expr) -> str | None:
    """``unittest.skipIf`` -> ``skipIf``; ``skip`` -> ``skip``; a call is read through to what it calls."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def markers_in(source: str, path: str) -> list[Marker]:
    """Every skip marker in one Python source; raises ``SyntaxError`` for a file that does not parse."""
    found: list[Marker] = []
    for node in ast.walk(ast.parse(source, filename=path)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                name = _last_name(decorator)
                if name in _DECORATOR_NAMES:
                    found.append(Marker(path, decorator.lineno, f"@{name}"))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in _CALL_NAMES:
                found.append(Marker(path, node.lineno, f".{func.attr}()"))
            elif (
                isinstance(func, ast.Attribute)
                and func.attr == "skip"
                and isinstance(func.value, ast.Name)
                and func.value.id == "pytest"
            ):
                found.append(Marker(path, node.lineno, "pytest.skip()"))
        elif isinstance(node, ast.Raise) and node.exc is not None and _last_name(node.exc) == "SkipTest":
            found.append(Marker(path, node.lineno, "raise SkipTest"))
    return sorted(found, key=lambda m: (m.line, m.kind))


def census(root: Path) -> list[Marker]:
    """Every skip marker under the test trees of ``root``, in path order."""
    found: list[Marker] = []
    for tree in TEST_TREES:
        base = root / tree
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(root)
            if "fixtures" in rel.parts or "__pycache__" in rel.parts:
                continue
            found.extend(markers_in(path.read_text(encoding="utf-8"), rel.as_posix()))
    return found


def load_count(path: Path) -> int | None:
    """``counts.skips.count``, or ``None`` when the entry is not there yet."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data.get("counts", {}).get(KEY)
    if entry is None:
        return None
    count = entry.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError(f"{path}: counts.{KEY}.count must be a non-negative integer")
    return count


def compare(current: int, baseline: int) -> tuple[int, str]:
    """Exit code and message for ``check``."""
    if current > baseline:
        return 1, (
            f"skip census: {current} skip markers in the test trees, the baseline allows {baseline}. "
            "Never skip a test to get green (AGENTS.md): remove the new marker; raising the baseline needs the owner."
        )
    if current < baseline:
        return 0, (
            f"skip census: down to {current} skip markers (baseline {baseline}). "
            "Run `make update-skip-baseline` in the same change so the gain is kept."
        )
    return 0, f"skip census: holds at {current} skip markers."


def record(path: Path, current: int) -> tuple[int, str]:
    """Write ``current`` as the baseline unless that would raise it."""
    data = json.loads(path.read_text(encoding="utf-8"))
    counts = data.setdefault("counts", {})
    previous = load_count(path)
    if previous is not None and current > previous:
        return 1, (
            f"skip census: {current} skip markers is above the baseline of {previous}; record only lowers it. "
            "Raising the baseline needs the owner."
        )
    if previous == current:
        return 0, f"skip census: the baseline already holds {current}."
    counts[KEY] = {"count": current, **_ENTRY}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    was = "no entry" if previous is None else str(previous)
    return 0, f"skip census: recorded {current} skip markers in {path} (was {was})."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("verb", choices=("check", "record"))
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root (default: %(default)s)")
    parser.add_argument(
        "--baseline", type=Path, default=None, help="counts file (default: ROOT/.quality-baseline.json)"
    )
    args = parser.parse_args(argv)
    baseline_path = args.baseline if args.baseline is not None else args.root / DEFAULT_BASELINE
    try:
        found = census(args.root)
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        print(f"skip census: cannot read a test file: {exc}", file=sys.stderr)
        return 2
    try:
        if args.verb == "record":
            code, message = record(baseline_path, len(found))
        else:
            baseline = load_count(baseline_path)
            if baseline is None:
                print(f"skip census: {baseline_path} has no counts.{KEY} entry; run `record` once", file=sys.stderr)
                return 2
            code, message = compare(len(found), baseline)
    except (OSError, ValueError, AttributeError) as exc:
        print(f"skip census: cannot read the {KEY} entry of {baseline_path}: {exc}", file=sys.stderr)
        return 2
    if code:
        for marker in found:
            print(f"  {marker.path}:{marker.line}: {marker.kind}", file=sys.stderr)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
