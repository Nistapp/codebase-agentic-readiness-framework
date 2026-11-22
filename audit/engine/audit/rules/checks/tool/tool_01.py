# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TOOL-01: Formatter configured."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import resolve_verbs, runner_commands
from audit.rules.checks.tool._shared import _finding, _outcome, _present, _read_matches, _recognised, _unknown

SPEC = declare("TOOL-01", "Formatter configured", "B", Severity.DEGRADER)


#: Formatter configuration filenames, across the ecosystems the catalogue names.
_FORMATTER_CONFIG_NAMES: tuple[str, ...] = (
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.json5",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    ".prettierrc.toml",
    ".prettierrc.js",
    ".prettierrc.cjs",
    ".prettierrc.mjs",
    "prettier.config.js",
    "prettier.config.cjs",
    "prettier.config.mjs",
    "biome.json",
    "biome.jsonc",
    ".dprint.json",
    "dprint.json",
    "ruff.toml",
    ".ruff.toml",
    "black.toml",
    ".black.toml",
    "rustfmt.toml",
    ".rustfmt.toml",
    ".clang-format",
    "pint.json",
    ".php-cs-fixer.php",
    ".php-cs-fixer.dist.php",
)


# ===========================================================================
# config readers
# ===========================================================================


def _formatter_config(inventory) -> list[str]:
    found = _present(inventory, _FORMATTER_CONFIG_NAMES)
    if _read_matches(inventory, "pyproject.toml", r"(?m)^\[tool\.(?:black|ruff|autopep8|yapf)\]"):
        found.append("pyproject.toml [tool.*]")
    if _read_matches(inventory, "package.json", r'"prettier"\s*:'):
        found.append("package.json prettier")
    return found


# ===========================================================================
# TOOL-01 — formatter configured
# ===========================================================================


def check_tool01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    configs = _formatter_config(inventory)
    binding = resolve_verbs(inventory, stack).get("format")

    if configs and binding:
        return _outcome(spec, Verdict.PASS, f"formatter {', '.join(configs)} + {binding.runner} format verb")

    if configs:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"formatter config present ({', '.join(configs)}) but no resolvable format write verb",
            [
                _finding(
                    spec,
                    "format a change set the same way every time",
                    "a formatter is configured but no runner exposes a format verb",
                    Verdict.PARTIAL,
                    [Evidence(configs[0])],
                    "Add a format verb (for example `prettier --write .`) to the runner so the configured "
                    "formatter is reachable by name.",
                )
            ],
        )

    if binding:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"format verb on {binding.runner} but no formatter config file",
            [
                _finding(
                    spec,
                    "format a change set the same way every time",
                    "a format verb exists but no formatter configuration file is present",
                    Verdict.PARTIAL,
                    [Evidence(binding.runner, note=binding.command)],
                    "Commit a formatter config (for example `.prettierrc.json`) so the tool's behaviour "
                    "does not depend on defaults.",
                )
            ],
        )

    if _recognised(stack, inventory):
        return _outcome(
            spec,
            Verdict.FAIL,
            "no formatter config and no format verb",
            [
                _finding(
                    spec,
                    "format a change set the same way every time",
                    "no formatter is configured and no format verb is defined",
                    Verdict.FAIL,
                    [Evidence(runner) for runner, _cmds in runner_commands(inventory)],
                    "Add a formatter config and a format write verb (prettier, black, ruff format, …).",
                )
            ],
        )

    return _unknown(
        spec, "no recognised ecosystem, runner manifest or formatter config, so a formatter cannot be ruled out"
    )
