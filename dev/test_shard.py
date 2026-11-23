# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Runs one shard of a unittest suite, so CI can split a slow suite over jobs that run at once.

``python3 dev/test_shard.py --suite engine --shard 1/2`` finds the suite's test modules at run time, assigns them
to shards by the weights in ``dev/test_shard_weights.json`` and runs the modules of one shard. The suites are the
engine's, the audit tools' and the dev checks' (``SUITES``). Each module is loaded
as ``python3 -m unittest discover`` loads it, from the same working directory and ``sys.path``. A module with no
weight gets ``DEFAULT_WEIGHT``, so a new module is always in exactly one shard. A shard that selects no test exits 1,
so a shard cannot pass by running nothing.

Every module of a shard is imported before any of its tests runs, as ``discover`` does. A test may put another
folder first on ``sys.path`` (``audit/tools/tests/test_import_fixture_matrix.py`` adds the engine's tests, which hold
modules with the same names), so a module imported after it could come from the wrong folder.

``--measure`` runs every module of the suite one by one and rewrites the suite's weights (seconds, one decimal).
It leaves ``dev/test_shard_groups.json`` alone.

A group in that file is a set of modules that must share a shard, because they use one fixed file (the engine's
``test_smoke`` and ``test_framework_default`` both rebuild ``audit/engine/dist/audit.pyz`` in place). ``assign`` treats
a group as one unit with the sum of its weights, at every shard count. A test finds the modules that run the engine's
``build.py`` and fails when they are not in one group.

The assignment is the same on every machine: the heaviest unit (a module or a group) first, each onto the shard with
the least weight so far (ties by name and shard number). CI's jobs shard into ``TEST_SHARDS`` parts. On Linux,
``make test`` shards into ``LOCAL_SHARDS`` parts that run at once;
``make test TEST_JOBS=`` and ``make coverage`` never shard.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unittest
from collections.abc import Sequence
from pathlib import Path

DEV = Path(__file__).resolve().parent
REPO = DEV.parent
WEIGHTS = DEV / "test_shard_weights.json"
GROUPS = DEV / "test_shard_groups.json"
#: Each suite: the folder its tests run from, and the start folder of its discovery (relative to the first), as the
#: Makefile's test-<suite> target runs it.
SUITES = {
    "engine": (REPO / "audit" / "engine", "tests"),
    "audit-tools": (REPO, "audit/tools/tests"),
    "dev": (REPO, "dev/tests"),
}
#: The weight of a module that the weights file does not name yet (seconds).
DEFAULT_WEIGHT = 1.0


def parse_shard(text: str) -> tuple[int, int]:
    """``"i/N"`` as ``(i, N)``, with 1 <= i <= N."""
    index, sep, count = text.partition("/")
    if not sep or not index.isdigit() or not count.isdigit() or not 1 <= int(index) <= int(count):
        raise argparse.ArgumentTypeError(f"expected i/N with 1 <= i <= N, got {text!r}")
    return int(index), int(count)


def suite_modules(start: Path) -> list[str]:
    """The test modules ``unittest discover`` finds in ``start``: ``test*.py`` files, by name.

    ``discover`` also walks a subfolder that is a package (it has ``__init__.py``), at any depth, and nothing else, so
    a fixture repository's ``tests/test_app.py`` is never a module of the suite. Names are unique across the suite:
    the weights and ``load`` find a module by its name alone."""
    found: list[str] = []
    folders = [start]
    while folders:
        folder = folders.pop()
        found.extend(path.stem for path in folder.glob("test*.py") if path.is_file())
        folders.extend(sub for sub in folder.iterdir() if sub.is_dir() and (sub / "__init__.py").is_file())
    if len(found) != len(set(found)):
        raise SystemExit(f"test_shard: two test modules in {start} share a name; rename one")
    return sorted(found)


def load_weights(path: Path = WEIGHTS) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    data: dict[str, dict[str, float]] = json.loads(path.read_text(encoding="utf-8"))
    return data


def load_groups(suite: str, path: Path = GROUPS) -> list[list[str]]:
    """The suite's groups of modules that must share a shard (each entry's ``why`` is for the reader)."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [[str(name) for name in entry["modules"]] for entry in data.get(suite, [])]


def assign(
    modules: Sequence[str],
    weights: dict[str, float],
    count: int,
    groups: Sequence[Sequence[str]] = (),
) -> list[list[str]]:
    """Every module in exactly one of ``count`` shards, balanced by weight; each shard sorted by name.

    A group is placed as one unit with the sum of its weights. A group that names a module not in ``modules``, or a
    module in two groups, raises ``ValueError``."""
    known = set(modules)
    grouped: set[str] = set()
    for group in groups:
        missing = sorted(set(group) - known)
        if missing:
            raise ValueError(f"a shard group names modules that do not exist: {', '.join(missing)}")
        if grouped & set(group):
            raise ValueError(f"a module is in two shard groups: {', '.join(sorted(grouped & set(group)))}")
        grouped |= set(group)
    units = [sorted(group) for group in groups] + [[name] for name in modules if name not in grouped]

    def weight(unit: list[str]) -> float:
        return sum(weights.get(name, DEFAULT_WEIGHT) for name in unit)

    shards: list[list[str]] = [[] for _ in range(count)]
    loads = [0.0] * count
    for unit in sorted(units, key=lambda u: (-weight(u), u[0])):
        lightest = min(range(count), key=lambda i: (loads[i], i))
        shards[lightest].extend(unit)
        loads[lightest] += weight(unit)
    return [sorted(shard) for shard in shards]


def _use_suite_path(root: Path) -> None:
    """Make ``sys.path`` what ``python3 -m unittest`` gives: the working directory first, not ``dev/``."""
    sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != DEV]
    sys.path.insert(0, str(root))


def load(root: Path, start: str, modules: Sequence[str]) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    start_dir = str(root / start)
    return unittest.TestSuite(loader.discover(start_dir, pattern=f"{name}.py") for name in modules)


def run(root: Path, start: str, modules: Sequence[str]) -> int:
    """Runs ``modules``; 0 when they pass, 1 when one fails or when they hold no test."""
    suite = load(root, start, modules)
    if suite.countTestCases() == 0:
        print(f"test_shard: the shard's modules hold no test: {', '.join(modules) or '(none)'}", file=sys.stderr)
        return 1
    result = unittest.TextTestRunner().run(suite)
    return 0 if result.wasSuccessful() else 1


def measure(root: Path, start: str, modules: Sequence[str]) -> dict[str, float] | None:
    """Seconds per module, each run alone; None when a module fails. Every module is imported first, as in a shard."""
    times: dict[str, float] = {}
    suites = {name: load(root, start, [name]) for name in modules}
    for name, suite in suites.items():
        began = time.perf_counter()
        with open(os.devnull, "w", encoding="utf-8") as quiet:
            result = unittest.TextTestRunner(stream=quiet).run(suite)
        times[name] = round(time.perf_counter() - began, 1)
        if not result.wasSuccessful():
            print(f"test_shard: {name} failed; the weights are not written", file=sys.stderr)
            return None
    return times


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", required=True, choices=sorted(SUITES))
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--shard", type=parse_shard, help="i/N: run shard i of N")
    action.add_argument("--measure", action="store_true", help="time every module and rewrite its weights")
    args = parser.parse_args(argv)

    root, start = SUITES[args.suite]
    os.chdir(root)
    _use_suite_path(root)
    modules = suite_modules(root / start)

    if args.measure:
        times = measure(root, start, modules)
        if times is None:
            return 1
        weights = load_weights()
        weights[args.suite] = dict(sorted(times.items()))
        WEIGHTS.write_text(json.dumps(weights, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"test_shard: wrote {len(times)} weights for {args.suite} ({sum(times.values()):.1f} s in all)")
        return 0

    index, count = args.shard
    try:
        selected = assign(modules, load_weights().get(args.suite, {}), count, load_groups(args.suite))[index - 1]
    except ValueError as error:
        raise SystemExit(f"test_shard: {error}") from error
    print(f"test_shard: {args.suite} shard {index}/{count}: {len(selected)} of {len(modules)} modules", file=sys.stderr)
    return run(root, start, selected)


if __name__ == "__main__":
    sys.exit(main())
