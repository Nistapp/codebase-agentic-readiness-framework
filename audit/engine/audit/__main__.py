# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Process entry point.

Two invocations share this one function:

* ``python3 -m audit <target>``                (development, no install, no build)
* ``./dist/audit.pyz <target>``                (distribution, one file)

``main`` MUST be callable with no arguments: a future ``console_scripts`` entry point calls ``main()`` with no
arguments. Passing argv explicitly is supported for tests. The zipapp shim ignores the return value of what it
calls, so the archive's entry point is :func:`entry`, which exits with ``main()``'s code. See
docs/how-to/run-an-audit.md.
"""

from __future__ import annotations

import sys

from audit.cli import run


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    return run(argv)


def entry() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    raise SystemExit(main())
