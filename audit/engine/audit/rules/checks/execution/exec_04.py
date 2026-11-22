# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""EXEC-04: Env-var inventory complete."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Inventory, Kind
from audit.rules.payloads import EnvKeys
from audit.rules.checks.execution._shared import _outcome

SPEC = declare("EXEC-04", "Env-var inventory complete", "B", Severity.BLOCKER)


# ===========================================================================
# EXEC-04 — env-var inventory complete
# ===========================================================================

#: The leading character anchors these on the env-var convention (upper-case first); the rest of
#: the capture class permits lower-case and digits too, so an identifier such as
#: ``UDA_LOG_LEVELNumber`` is captured whole rather than truncated at its first lower-case run.
_SHELL_ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Za-z0-9_]*)(?:(:?[-=+?])[^}]*)?\}")

#: The parameter-expansion operators that give a reference a fallback, so the script runs without the variable:
#: ``${VAR:-default}``, ``${VAR-default}``, ``${VAR:=default}``, ``${VAR=default}``, ``${VAR:+alt}`` and
#: ``${VAR+alt}`` (issue #13). ``${VAR:?message}`` and ``${VAR?message}`` stop the script without it, so they are
#: required references, as a bare ``${VAR}`` is.
_SHELL_OPTIONAL_OPERATORS = frozenset({":-", "-", ":=", "=", ":+", "+"})

#: A shell assignment to the same identifier class the reference pattern above captures —
#: ``GREEN='\033[0;32m'``, optionally ``export``-ed. A file that assigns ``VAR`` itself is
#: declaring a local shell variable, not requiring it from the process environment, so a
#: ``${VAR}`` use of it is excluded from that file's contribution to the referenced-keys set.
#: Scoped per key, per file (the capture group names exactly which identifier was assigned) —
#: never a single blanket pattern that can't tell one variable name from another.
_SHELL_ASSIGN_PATTERN = re.compile(r"(?m)^[ \t]*(?:export[ \t]+)?([A-Z][A-Za-z0-9_]*)[ \t]*=")
_CODE_ENV_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"os\.environ\.get\(\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']"),
    re.compile(r"os\.environ\[\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']\s*\]"),
    re.compile(r"os\.getenv\(\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']"),
    re.compile(r"(?<!os\.)\bgetenv\(\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']"),
    re.compile(r"process\.env\.([A-Z][A-Za-z0-9_]*)"),
    re.compile(r"process\.env\[\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']\s*\]"),
    re.compile(r"ENV\[\s*[\"']([A-Z][A-Za-z0-9_]*)[\"']\s*\]"),
)

#: Files where ``${VAR}`` is an environment reference rather than a language-level string
#: interpolation. Restricting the shell pattern to these is what keeps a TypeScript template
#: literal such as ``${PIPELINE_VERSION}`` from being misread as an undeclared secret. Deployment
#: YAML (compose, Terraform) is deliberately out of scope: its ``${VAR}`` references usually name
#: host/CI values, not repository environment requirements.
_SHELL_ENV_SUFFIXES = (".sh", ".bash", ".zsh", ".fish", ".ksh", ".ps1")
_SHELL_ENV_BASENAMES = ("Dockerfile",)

#: Conventional host/CI/test variables an agent never needs a template for. Kept in code so the
#: allow-list is deterministic and reviewable rather than a per-target heuristic.
_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "CI",
        "HOME",
        "PATH",
        "PWD",
        "SHELL",
        "USER",
        "LANG",
        "LC_ALL",
        "TZ",
        "TERM",
        "TMPDIR",
        "NODE_ENV",
        "DEBUG",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "VERBOSE",
        "PORT",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "VIRTUAL_ENV",
        "PYTHONHASHSEED",
        "FORCE_COLOR",
        "NO_COLOR",
        "COLUMNS",
        "LINES",
        # Variables the shell itself sets (bash, and zsh where it shares the name), never read from a template.
        "BASHPID",
        "EPOCHREALTIME",
        "EPOCHSECONDS",
        "EUID",
        "FUNCNAME",
        "GROUPS",
        "HOSTNAME",
        "HOSTTYPE",
        "IFS",
        "LINENO",
        "MACHTYPE",
        "OLDPWD",
        "OPTARG",
        "OPTIND",
        "OSTYPE",
        "PIPESTATUS",
        "PPID",
        "RANDOM",
        "REPLY",
        "SECONDS",
        "SHELLOPTS",
        "SHLVL",
        "SRANDOM",
        "UID",
    }
)
_ENV_ALLOW_PREFIXES: tuple[str, ...] = (
    "GITHUB_",
    "CI_",
    "RUNNER_",
    "ACTIONS_",
    "npm_config_",
    "NPM_CONFIG_",
    "VITEST_",
    "PYTEST_",
    "COVERAGE_",
    "BASH_",
)
_ENV_EXAMPLE_FILES = (".env.example", ".env.sample", ".env.template", "env.example")


def _is_shell_env_file(rel: str) -> bool:
    return rel.endswith(_SHELL_ENV_SUFFIXES) or rel.rsplit("/", 1)[-1] in _SHELL_ENV_BASENAMES


def _referenced_env_keys(inv: Inventory) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """The keys the repository requires and the keys it reads only with a fallback, each with the files that read it.

    A key is optional only when every shell reference to it has a fallback operator
    (:data:`_SHELL_OPTIONAL_OPERATORS`) and no source file reads it; one required reference anywhere makes it
    required.
    """
    required: dict[str, set[str]] = {}
    optional: dict[str, set[str]] = {}
    for path in inv.paths():
        if not _is_shell_env_file(path):
            continue
        text = inv.read(path)
        if text:
            assigned_here = {m.group(1) for m in _SHELL_ASSIGN_PATTERN.finditer(text)}
            for match in _SHELL_ENV_PATTERN.finditer(text):
                key = match.group(1)
                if key in assigned_here:
                    continue
                target = optional if match.group(2) in _SHELL_OPTIONAL_OPERATORS else required
                target.setdefault(key, set()).add(path)
    for pattern in _CODE_ENV_PATTERNS:
        for rel, _line, text in inv.grep(pattern, kinds=(Kind.SOURCE, Kind.SCRIPT), limit=2000):
            for match in pattern.finditer(text):
                if match.group(1):
                    required.setdefault(match.group(1), set()).add(rel)
    return required, {key: readers for key, readers in optional.items() if key not in required}


def _declared_env_keys(inv: Inventory) -> dict[str, set[str]]:
    """Each committed example file, at any depth, shallowest first, with the keys it declares."""
    templates = sorted(
        (rel for rel in inv.paths() if rel.rsplit("/", 1)[-1] in _ENV_EXAMPLE_FILES),
        key=lambda rel: (rel.count("/"), rel),
    )
    declared: dict[str, set[str]] = {}
    for rel in templates:
        text = inv.read(rel)
        if text is None:
            continue
        keys = declared.setdefault(rel, set())
        for line in text.splitlines():
            match = re.match(r"^\s*(?:export\s+)?#?\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
            if match:
                keys.add(match.group(1))
    return declared


def _reaches(template: str, rel: str) -> bool:
    """Whether an example file documents ``rel``: it sits in ``rel``'s folder or a folder above it."""
    folder = template.rsplit("/", 1)[0] + "/" if "/" in template else ""
    return rel.startswith(folder)


def _declared_for(key: str, readers: set[str], declared: dict[str, set[str]]) -> bool:
    """Whether every file that reads ``key`` is reached by an example file that declares it."""
    holders = [template for template, keys in declared.items() if key in keys]
    return all(any(_reaches(template, rel) for template in holders) for rel in readers)


def _env_allowed(key: str) -> bool:
    return key in _ENV_ALLOWLIST or key.startswith(_ENV_ALLOW_PREFIXES)


def check_exec04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    referenced, optional = _referenced_env_keys(inventory)
    declared = _declared_env_keys(inventory)
    files = list(declared)
    missing = sorted(
        key
        for key, readers in referenced.items()
        if not _env_allowed(key) and not _declared_for(key, readers, declared)
    )
    optional_undeclared = sorted(
        key for key, readers in optional.items() if not _env_allowed(key) and not _declared_for(key, readers, declared)
    )
    keys = EnvKeys(
        referenced=tuple(sorted(referenced)),
        missing=tuple(missing),
        templates=tuple(files),
        optional=tuple(optional_undeclared),
    )
    optional_note = (
        f"; {len(optional_undeclared)} optional key(s) with a fallback, not in an example file: "
        f"{', '.join(optional_undeclared[:12])}"
        if optional_undeclared
        else ""
    )

    if not missing:
        if referenced:
            detail = f"{len(referenced)} referenced key(s) declared"
        else:
            detail = "no required environment key referenced" if optional else "no environment keys referenced"
        return _outcome(spec, Verdict.PASS, detail + optional_note, data=keys)

    because = (
        f"{len(missing)} referenced key(s) are absent from "
        + (
            f"every example file that covers the files reading them ({', '.join(files)})"
            if files
            else "any committed example file"
        )
        + f": {', '.join(missing[:12])}"
    )
    return _outcome(
        spec,
        Verdict.FAIL,
        because + optional_note,
        [
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement("know every variable the code needs before running it", because),
                evidence=[Evidence(f) for f in files] or [Evidence("(no example file)")],
                remediation="Add the missing keys to .env.example (values redacted) so the environment "
                "can be provisioned without reading the source.",
            )
        ],
        data=keys,
    )
