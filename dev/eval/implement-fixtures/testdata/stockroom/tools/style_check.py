"""House style check: no line longer than 100 characters. Prints one line per violation and exits 1 if any."""

from __future__ import annotations

import sys
from pathlib import Path

LIMIT = 100


def main(paths: list[str]) -> int:
    found = 0
    for root in paths or ["."]:
        for path in sorted(Path(root).rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if len(line) > LIMIT:
                    found += 1
                    print(f"{path}:{number}: line too long ({len(line)} > {LIMIT})")
    print(f"{found} violation(s)")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
