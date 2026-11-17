# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The project entry point of the document index: ``python3 dev/doc_index.py <command> ...``.

It puts ``dev/`` on ``sys.path``, loads this repository's config, ``dev/docindex.config.json``, and calls
:func:`docindex.cli.main`. The ``docindex`` package is the generic core and imports no other ``dev/`` module; this
file is the one place that may (ADR 0011 in ``docs/architecture/adrs/``). The subcommands are in
:mod:`docindex.cli`.

For the sweep, :func:`bundle_sources` loads the module that ``sweep.bundle_references.module`` names
(``dev/build_skills.py``) and reads the constants that ``sweep.bundle_references.constants`` names
(``AUDIT_REFERENCES`` and ``IMPLEMENT_REFERENCES``, each a tuple of ``(source, place in the bundle)`` pairs). The
sources, files and folders, are the bundle part of the sweep scope. They are read from the working tree's module even
with ``--at``; the core then resolves them in the tree at the ref.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

DEV = Path(__file__).resolve().parent
REPO = DEV.parent
CONFIG = DEV / "docindex.config.json"

if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))

from docindex import cli  # noqa: E402


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    """The project config: a JSON object."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return data


def bundle_sources(config: Mapping[str, Any]) -> list[str]:
    """The repository paths of every file and folder the skill bundles carry, sorted, from the bundle module."""
    references = config.get("sweep", {}).get("bundle_references")
    if not references:
        return []
    path = REPO / references["module"]
    name = f"_doc_index_{path.stem}"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {references['module']}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    sources: set[str] = set()
    for constant in references["constants"]:
        for source, _place in getattr(module, constant):
            sources.add(str(source))
    return sorted(sources)


def main(argv: Sequence[str] | None = None) -> int:
    config = load_config()
    return cli.main(argv, config, root=REPO, bundle_sources=lambda: bundle_sources(config))


if __name__ == "__main__":
    raise SystemExit(main())
