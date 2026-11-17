# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The project entry point of the document index: ``python3 dev/doc_index.py <command> ...``.

It puts ``dev/`` on ``sys.path``, loads this repository's config, ``dev/docindex.config.json``, and calls
:func:`docindex.cli.main`. The ``docindex`` package is the generic core and imports no other ``dev/`` module; this
file is the one place that may (ADR 0011 in ``docs/architecture/adrs/``). The subcommands are in
:mod:`docindex.cli`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Sequence

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


def main(argv: Sequence[str] | None = None) -> int:
    return cli.main(argv, load_config())


if __name__ == "__main__":
    raise SystemExit(main())
