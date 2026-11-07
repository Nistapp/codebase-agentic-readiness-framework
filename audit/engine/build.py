#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Build the single-file distributable: dist/audit.pyz.

The package tree is the source of truth; this produces the one artifact you hand to someone else.
It needs nothing but the standard library, which is the entire reason the tool ships this way — it
must run on a machine where nothing is installed and the target's toolchain does not exist yet.

    python3 tools/build.py            # build, print size and the archive entry point
    ./dist/audit.pyz <target>         # run it

Two constraints come from zipapp and are easy to get wrong:

1. the archive root needs an entry point — passing ``main=`` makes zipapp generate a root
   ``__main__.py`` shim, so the package tree itself needs no root-level file
2. that shim calls the entry point with **no arguments** and discards what it returns, which is why
   ``audit.__main__.main`` accepts ``argv=None`` and the entry point is ``entry``, which exits with
   ``main()``'s code

Excluded from the archive: tests, docs, dist and bytecode. Nothing inside a .pyz can be read with
``Path(__file__)`` — the archive is not a directory — so shipped data must go through
``importlib.resources``. This project keeps its tables in code, so it has no such data file.
"""

from __future__ import annotations

import io
import sys
import zipapp
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "dist"
ARCHIVE = DIST / "audit.pyz"
ENTRY_POINT = "audit.__main__:entry"

EXCLUDED_PREFIXES = ("tests/", "docs/", "dist/", "tools/", ".git/")

#: Every other archive entry's timestamp comes from its source file's own mtime on disk, which is
#: stable build to build; this is the one zipapp synthesizes at build time (`zipapp.create_archive`'s
#: `main_py` writes `__main__.py` with `writestr`, which stamps it with "now"), the one that made two
#: otherwise-identical builds differ by a byte or two (ZIP's DOS date_time format packs the second
#: field to a 2-second granularity) whenever they fell either side of that boundary.
FROZEN_SHIM_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def _filter(path: Path) -> bool:
    rel = path.as_posix()
    # Excludes the directory's own entry too (not only what is under it): `dist/` in particular is
    # rewritten by this very build (it holds the archive being built), so its own mtime is "now",
    # observed making two otherwise-identical builds differ by a byte or two across a 2-second
    # DOS-time boundary. An excluded, empty directory marker ships nothing anyway.
    if any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    if "__pycache__" in rel or rel.endswith((".pyc", ".pyo")):
        return False
    return True


def _freeze_shim_timestamp(archive: Path) -> None:
    """Rewrite `archive` with its synthesized ``__main__.py`` entry's timestamp pinned to a constant.

    `zipapp` writes a shebang line before the zip data; `zipfile.ZipFile` can read that directly (it
    locates the central directory from the end of the file), but writing has to reproduce the same
    prefix by hand, since `ZipFile` itself only ever writes a zip, never one with a prefix.
    """
    shebang = archive.read_bytes().split(b"\n", 1)[0] + b"\n"
    with zipfile.ZipFile(archive) as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as rebuilt:
        for info, data in entries:
            if info.filename == "__main__.py":
                info.date_time = FROZEN_SHIM_DATE_TIME
            rebuilt.writestr(info, data)

    archive.write_bytes(shebang + buffer.getvalue())


def main() -> int:
    if sys.version_info < (3, 11):
        print("audit: needs Python 3.11+ to build", file=sys.stderr)
        return 1

    DIST.mkdir(exist_ok=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()

    zipapp.create_archive(
        source=REPO_ROOT,
        target=ARCHIVE,
        interpreter="/usr/bin/env python3",
        main=ENTRY_POINT,
        filter=_filter,
        compressed=True,
    )
    _freeze_shim_timestamp(ARCHIVE)
    ARCHIVE.chmod(0o755)

    size = ARCHIVE.stat().st_size
    print(f"built {ARCHIVE.relative_to(REPO_ROOT)}  ({size:,} bytes)")
    print(f"entry point: {ENTRY_POINT}   run: ./dist/audit.pyz <target>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
