# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""NAV-02: Obvious entry points."""

from __future__ import annotations

import json
import re

from audit.evaluate import CheckOutcome
from audit.findings import Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Inventory, Kind
from audit.rules.checks.nav._shared import _outcome, _unknown

SPEC = declare("NAV-02", "Obvious entry points", "B", Severity.DEGRADER)


def _has_exact(inventory: Inventory, rel: str) -> bool:
    """Exact path membership: unlike ``Inventory.has``, never a suffix match at any depth."""
    return any(f.rel == rel for f in inventory.files)


# ===========================================================================
# NAV-02 — obvious entry points
# ===========================================================================

_NODE_INDEX_FILES = (
    "index.js",
    "index.ts",
    "index.mjs",
    "index.cjs",
    "src/index.js",
    "src/index.ts",
    "src/index.mjs",
    "server.js",
    "server.ts",
    "src/server.js",
    "src/server.ts",
    "main.js",
    "main.ts",
    "main.mjs",
    "main.cjs",
    "src/main.js",
    "src/main.ts",
    "app.js",
    "app.ts",
    "src/app.js",
    "src/app.ts",
)

_ENTRY_NAMES: dict[str, tuple[str, ...]] = {
    "dotnet": ("Program.cs", "program.cs", "src/Program.cs"),
    "ruby": ("config.ru", "app.rb", "main.rb", "bin/rails", "bin/setup"),
    "php": ("index.php", "public/index.php", "bin/console"),
}


def _node_entry(inventory: Inventory) -> list[str]:
    found: list[str] = []
    text = inventory.read("package.json")
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            if data.get("main"):
                found.append(f"package.json:main={data['main']}")
            if data.get("bin"):
                found.append("package.json:bin")
            if data.get("exports"):
                found.append("package.json:exports")
    for rel in _NODE_INDEX_FILES:
        if _has_exact(inventory, rel):
            found.append(rel)
    return found


def _python_entry(inventory: Inventory) -> list[str]:
    """A `__main__.py`, a conventional main/app/manage file, or a manifest script entry.

    An `if __name__ == "__main__"` guard alone is not an entry point: every helper script and dev tool
    carries one (the playbooks' own check templates do), so it gave a library or a tooling folder false
    credit. A guarded file that is the real entry point is named by one of the signals above.
    """
    found: list[str] = []
    for entry in inventory.files:
        if entry.rel.endswith("__main__.py"):
            found.append(entry.rel)
    for rel in ("main.py", "app.py", "src/main.py", "src/app.py", "manage.py"):
        if _has_exact(inventory, rel):
            found.append(rel)
    for manifest in ("pyproject.toml", "setup.py", "setup.cfg"):
        text = inventory.read(manifest)
        if text and re.search(r"(?i)console_scripts|\[project\.scripts\]|entry_points", text):
            found.append(f"{manifest}:entry point")
    return found


def _grep_sources(inventory: Inventory, pattern: str, limit: int = 10) -> list[str]:
    return [rel for rel, _line, _text in inventory.grep(pattern, kinds=(Kind.SOURCE,), limit=limit)]


def _jvm_entry(inventory: Inventory) -> list[str]:
    found = _grep_sources(
        inventory,
        r"public\s+static\s+void\s+main\s*\(|fun\s+main\s*\(|"
        r"@SpringBootApplication|@QuarkusMain",
    )
    # Quarkus apps conventionally have no literal main method at all: the Quarkus runtime itself
    # is the entry point, launched by its own build plugin/dependency. A build dependency on
    # `io.quarkus` is that framework's own bootstrap convention, the same way `@SpringBootApplication`
    # is Spring Boot's — so it is read from the build manifest, not guessed from source shape.
    found += [rel for rel, _line, _text in inventory.grep(r"io\.quarkus", kinds=(Kind.BUILD,), limit=5)]
    return found


def _go_entry(inventory: Inventory) -> list[str]:
    return _grep_sources(inventory, r"^func\s+main\s*\(")


def _rust_entry(inventory: Inventory) -> list[str]:
    found: list[str] = []
    for rel in ("src/main.rs", "src/bin/main.rs", "main.rs"):
        if _has_exact(inventory, rel):
            found.append(rel)
    cargo = inventory.read("Cargo.toml")
    if cargo and re.search(r"\[\[\s*bin\s*\]\]", cargo):
        found.append("Cargo.toml:[[bin]]")
    return found


_DETECTORS = {
    "node": _node_entry,
    "python": _python_entry,
    "jvm": _jvm_entry,
    "go": _go_entry,
    "rust": _rust_entry,
}


def _entry_points(inventory: Inventory, ecosystems: set[str]) -> list[str]:
    found: list[str] = []
    for eco in sorted(ecosystems):
        detector = _DETECTORS.get(eco)
        if detector:
            found += detector(inventory)
        for rel in _ENTRY_NAMES.get(eco, ()):
            if _has_exact(inventory, rel):
                found.append(rel)
    seen: set[str] = set()
    unique: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def check_nav02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if not stack.ecosystems:
        return _unknown(spec, "no recognised ecosystem, so an entry point cannot be located")

    found = _entry_points(inventory, stack.ecosystems)
    ecosystems = ", ".join(sorted(stack.ecosystems))
    if found:
        return _outcome(spec, Verdict.PASS, f"entry point(s): {', '.join(found[:6])}")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"no entry point found for {ecosystems}",
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "find where execution begins",
                    f"the {ecosystems} project declares no entry point (main, bin, __main__, Application or func main)",
                ),
                remediation="Declare the entry point in the manifest (package.json main/bin, "
                "pyproject scripts, a Gradle main class) or name the executable file so "
                "an agent can tell live code from dead code.",
            ),
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, ROOT, Reads, What, _at

    return Reads(
        where=(
            *_at(
                ROOT,
                "package.json",
                "index.js",
                "index.ts",
                "index.mjs",
                "index.cjs",
                "src/index.js",
                "src/index.ts",
                "src/index.mjs",
                "server.js",
                "server.ts",
                "src/server.js",
                "src/server.ts",
                "main.js",
                "main.ts",
                "main.mjs",
                "main.cjs",
                "src/main.js",
                "src/main.ts",
                "app.js",
                "app.ts",
                "src/app.js",
                "src/app.ts",
                "main.py",
                "app.py",
                "src/main.py",
                "src/app.py",
                "manage.py",
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "src/main.rs",
                "src/bin/main.rs",
                "main.rs",
                "Cargo.toml",
                "Program.cs",
                "program.cs",
                "src/Program.cs",
                "config.ru",
                "app.rb",
                "main.rb",
                "bin/rails",
                "bin/setup",
                "index.php",
                "public/index.php",
                "bin/console",
            ),
            *_at(ANY_DEPTH, "__main__.py"),
            *_at(GLOB, "**"),
        ),
        what=What("exists"),
        binding="line",
        note=(
            "Fixed names are matched by exact path per detected ecosystem; source files (glob **) are grepped"
            " for a line that starts with func main(, a JVM main method or a Spring Boot or Quarkus marker,"
            " and build files for io.quarkus. A Python __main__ guard alone is not read."
        ),
    )
