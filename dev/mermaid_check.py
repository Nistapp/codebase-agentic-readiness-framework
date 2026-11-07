# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Validate every Mermaid block in the given Markdown files with the real Mermaid parser.

    mermaid_check.py [--no-sandbox] FILE.md...

Each fenced ```` ```mermaid ```` block is written to a temporary directory and rendered with a pinned
``@mermaid-js/mermaid-cli`` (``mmdc``) through ``npx``; a block that does not render is reported with its file
and line, and the run exits 1. Files with no Mermaid block, and paths that no longer exist (a file a change
deleted), are skipped, so CI can pass the list of changed files as it is. ``--no-sandbox`` starts the headless
browser without its sandbox, which CI runners that restrict user namespaces need.

Dev-only: CI runs it, nothing in ``tools/`` or the engine imports it. Standard library only; needs Node (for
``npx``) and, the first time, the network to fetch the CLI and its browser.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

MERMAID_CLI = "@mermaid-js/mermaid-cli@12.0.0"
ERROR_LINES = 8
OPEN_FENCE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})\s*mermaid\s*$")


@dataclass(frozen=True)
class Block:
    path: Path
    line: int  # 1-based line of the opening fence
    source: str


def _closes(line: str, fence: str) -> bool:
    """A closing fence is the opening fence's character only, at least as many of it (CommonMark)."""
    stripped = line.strip()
    return len(stripped) >= len(fence) and set(stripped) == {fence[0]}


def extract_blocks(path: Path, text: str) -> list[Block]:
    """Return every fenced Mermaid block in ``text``, in order. An unclosed block runs to the end of the file."""
    blocks: list[Block] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = OPEN_FENCE.match(lines[i])
        if match is None:
            i += 1
            continue
        fence = match.group("fence")
        start = i
        body: list[str] = []
        i += 1
        while i < len(lines) and not _closes(lines[i], fence):
            body.append(lines[i])
            i += 1
        blocks.append(Block(path=path, line=start + 1, source="\n".join(body) + "\n"))
        i += 1
    return blocks


def render(block: Block, workdir: Path, index: int, puppeteer_config: Path | None) -> str | None:
    """Render one block with ``mmdc``; return ``None`` on success, else the CLI's error output."""
    source = workdir / f"block-{index}.mmd"
    source.write_text(block.source, encoding="utf-8")
    command = ["npx", "--yes", MERMAID_CLI, "--quiet", "-i", str(source), "-o", str(workdir / f"block-{index}.svg")]
    if puppeteer_config is not None:
        command += ["-p", str(puppeteer_config)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return None
    output = (result.stderr or result.stdout).strip().splitlines()
    # The parser's message comes first; the rest is a browser stack trace.
    return "\n".join(output[:ERROR_LINES]) or f"mmdc exited {result.returncode}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Mermaid blocks in Markdown files with mmdc.")
    parser.add_argument("--no-sandbox", action="store_true", help="start the headless browser without its sandbox")
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args(argv)

    blocks: list[Block] = []
    for path in args.files:
        if path.suffix != ".md" or not path.is_file():
            continue
        blocks.extend(extract_blocks(path, path.read_text(encoding="utf-8")))
    if not blocks:
        print("mermaid_check: no Mermaid blocks in the given files")
        return 0

    failures = 0
    with tempfile.TemporaryDirectory(prefix="mermaid-check-") as tmp:
        workdir = Path(tmp)
        puppeteer_config: Path | None = None
        if args.no_sandbox:
            puppeteer_config = workdir / "puppeteer.json"
            puppeteer_config.write_text(json.dumps({"args": ["--no-sandbox"]}), encoding="utf-8")
        for index, block in enumerate(blocks):
            error = render(block, workdir, index, puppeteer_config)
            if error is not None:
                failures += 1
                print(f"{block.path}:{block.line}: Mermaid block does not render:\n{error}", file=sys.stderr)
    print(f"mermaid_check: {len(blocks) - failures} of {len(blocks)} blocks valid")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
