# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""EXEC-03: Non-interactive setup path."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import extract_documented_commands, README, entry_documents
from audit.scan import Inventory
from audit.stack import extract_npm_scripts, parse_makefile_targets
from audit.rules.checks.execution._shared import _outcome, _tokenise, _unknown

SPEC = declare("EXEC-03", "Non-interactive setup path", "A", Severity.BLOCKER)


# ===========================================================================
# EXEC-03 — non-interactive setup path
# ===========================================================================

_SETUP_FILES = (
    ".devcontainer/devcontainer.json",
    ".devcontainer.json",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "Dockerfile",
    "setup.sh",
    "bootstrap.sh",
    "dev-setup.sh",
)
#: Dockerfiles with a variant in the name (``Dockerfile.jvm``, ``dev.Dockerfile``), found at any depth by base name:
#: frameworks keep them below the root (Quarkus writes ``src/main/docker/Dockerfile.jvm``).
_DOCKERFILE_PATTERNS = ("Dockerfile.*", "*.Dockerfile", "*.dockerfile")
#: The dev container spec reads ``.devcontainer/devcontainer.json`` and one configuration per subfolder,
#: ``.devcontainer/<name>/devcontainer.json``.
_DEVCONTAINER_PATTERNS = (".devcontainer/*.json", ".devcontainer/*/devcontainer.json")
_DOC_FILES = (README, "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md")
_SETUP_TARGETS = ("setup", "bootstrap", "install", "dev", "dev-setup")


def _setup_signals(inv: Inventory) -> list[str]:
    signals = [name for name in _SETUP_FILES if inv.has(name)]
    signals += inv.match(*_DEVCONTAINER_PATTERNS)
    signals += inv.match(*_DOCKERFILE_PATTERNS)

    make_targets = parse_makefile_targets(inv)
    signals += [f"Makefile:{t}" for t in _SETUP_TARGETS if t in make_targets]

    scripts = extract_npm_scripts(inv)
    signals += [f"package.json:{t}" for t in _SETUP_TARGETS if t in scripts]
    return sorted(dict.fromkeys(signals))


_INSTALL_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "npm": frozenset({"install", "ci", "i"}),
    "pnpm": frozenset({"install", "i"}),
    "yarn": frozenset({"install"}),
    "bun": frozenset({"install"}),
    "pip": frozenset({"install"}),
    "pip3": frozenset({"install"}),
    "poetry": frozenset({"install"}),
    "pipenv": frozenset({"install", "sync"}),
    "uv": frozenset({"sync", "pip"}),
    "bundle": frozenset({"install"}),
    "gem": frozenset({"install"}),
    "composer": frozenset({"install"}),
    "make": frozenset(_SETUP_TARGETS),
    "task": frozenset(_SETUP_TARGETS),
    "cargo": frozenset({"fetch", "build"}),
    "go": frozenset({"mod", "build", "install"}),
    "dotnet": frozenset({"restore"}),
    "gradle": frozenset({"build", "assemble"}),
    "gradlew": frozenset({"build", "assemble"}),
    "mvn": frozenset({"install", "package"}),
    "mvnw": frozenset({"install", "package"}),
    "docker": frozenset({"compose", "build"}),
    "docker-compose": frozenset({"up", "build"}),
    "nvm": frozenset({"use"}),
}


def _documented_setup(inv: Inventory) -> list[str]:
    found: set[str] = set()
    for name in entry_documents(inv, _DOC_FILES):
        text = inv.read(name)
        if not text:
            continue
        for _lang, _line, command in extract_documented_commands(text):
            tokens = _tokenise(command)
            if not tokens:
                continue
            head = tokens[0].lstrip("./")
            subcommands = _INSTALL_SUBCOMMANDS.get(head)
            if subcommands and len(tokens) > 1 and tokens[1] in subcommands:
                found.add(f"{name}: {command}")
    return sorted(found)


def _is_documented(signal: str, text: str) -> bool:
    name = signal.split(":", 1)[1] if ":" in signal else signal
    name = name.rsplit("/", 1)[-1]
    if name.endswith((".json", ".yml", ".yaml", ".sh")):
        return name in text or signal in text
    return name in text


def check_exec03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if not stack.ecosystems:
        return _unknown(spec, "no recognised ecosystem, so no setup path can be characterised")

    doc_text = "\n".join(filter(None, (inventory.read(n) for n in entry_documents(inventory, _DOC_FILES))))
    documented_commands = _documented_setup(inventory)
    if documented_commands:
        return _outcome(spec, Verdict.PASS, f"documented setup command: {documented_commands[0]}")

    signals = _setup_signals(inventory)
    documented = [s for s in signals if _is_documented(s, doc_text)]
    if documented:
        return _outcome(spec, Verdict.PASS, f"documented setup artifact: {', '.join(documented)}")
    if signals:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"present but undocumented: {', '.join(signals)}",
            [
                Finding(
                    check=spec.id,
                    severity=spec.severity,
                    phase=spec.phase,
                    verdict=Verdict.PARTIAL,
                    statement=statement(
                        "provision the environment from the repository alone",
                        f"{', '.join(signals)} exists but no doc names it",
                    ),
                    evidence=[Evidence(s) for s in signals],
                    remediation="Reference the setup path in README.md or AGENTS.md so an "
                    "agent finds it without guessing.",
                )
            ],
        )

    return _outcome(
        spec,
        Verdict.FAIL,
        "no setup path found",
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "prepare the environment non-interactively",
                    "no devcontainer, compose file, Dockerfile, setup target/script, or documented "
                    "install command exists",
                ),
                remediation="Add a committed setup path (a devcontainer, compose file, or a documented "
                "install command in README.md) that runs with no prompts.",
            )
        ],
    )


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, ROOT, Reads, What, _at

    return Reads(
        where=(
            *_at(ROOT, "README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"),
            *_at(GLOB, "README*"),
            *_at(
                ANY_DEPTH,
                ".devcontainer/devcontainer.json",
                ".devcontainer.json",
                "docker-compose.yml",
                "docker-compose.yaml",
                "compose.yml",
                "compose.yaml",
                "Dockerfile",
                "setup.sh",
                "bootstrap.sh",
                "dev-setup.sh",
                "Dockerfile.*",
                "*.Dockerfile",
                "*.dockerfile",
            ),
            *_at(GLOB, ".devcontainer/*.json", ".devcontainer/*/devcontainer.json"),
            *_at(ROOT, "Makefile", "package.json"),
        ),
        what=What("fenced-command"),
        binding="line",
        threshold="a documented non-interactive setup command",
        note=(
            "A fenced shell command or an inline code span in the four docs whose tool and first argument "
            "install or set up passes. "
            "Else a setup file (at any depth, a Dockerfile with a variant in its name included) or a setup "
            "target (setup, bootstrap, install, dev, dev-setup) of the root Makefile or package.json named "
            "anywhere in the four docs passes; present but not named is PARTIAL."
        ),
    )
