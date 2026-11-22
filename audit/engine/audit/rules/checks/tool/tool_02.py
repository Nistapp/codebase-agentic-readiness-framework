# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""TOOL-02: Linter configured."""

from __future__ import annotations

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Severity, Verdict
from audit.rules.spec import declare
from audit.rules.checks._common import resolve_verbs, runner_commands
from audit.rules.checks.tool._shared import _finding, _outcome, _present, _read_matches, _recognised, _unknown

SPEC = declare("TOOL-02", "Linter configured", "B", Severity.DEGRADER)


#: Linter configuration filenames.
_LINTER_CONFIG_NAMES: tuple[str, ...] = (
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.mjs",
    ".eslintrc.yml",
    ".eslintrc.yaml",
    "eslint.config.js",
    "eslint.config.cjs",
    "eslint.config.mjs",
    "eslint.config.ts",
    "biome.json",
    "biome.jsonc",
    "ruff.toml",
    ".ruff.toml",
    ".flake8",
    ".pylintrc",
    "pylintrc",
    ".golangci.yml",
    ".golangci.yaml",
    ".golangci.toml",
    "clippy.toml",
    ".clippy.toml",
    ".rubocop.yml",
    "checkstyle.xml",
    ".stylelintrc",
    ".stylelintrc.json",
    "phpcs.xml",
    ".phpcs.xml",
)


def _linter_config(inventory) -> list[str]:
    found = _present(inventory, _LINTER_CONFIG_NAMES)
    if _read_matches(inventory, "pyproject.toml", r"(?m)^\[tool\.(?:ruff|pylint|flake8)\]"):
        found.append("pyproject.toml [tool.*]")
    if _read_matches(inventory, "package.json", r'"eslintConfig"\s*:'):
        found.append("package.json eslintConfig")
    return found


# ===========================================================================
# TOOL-02 — linter configured
# ===========================================================================


def check_tool02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    configs = _linter_config(inventory)
    binding = resolve_verbs(inventory, stack).get("lint")

    if configs and binding:
        return _outcome(spec, Verdict.PASS, f"linter {', '.join(configs)} + {binding.runner} lint verb")

    if configs:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"linter config present ({', '.join(configs)}) but no resolvable lint verb",
            [
                _finding(
                    spec,
                    "catch lint regressions before they land",
                    "a linter is configured but no runner exposes a lint verb",
                    Verdict.PARTIAL,
                    [Evidence(configs[0])],
                    "Add a lint verb (for example `eslint .` or `ruff check`) to the runner so the "
                    "configured linter is reachable by name.",
                )
            ],
        )

    if binding:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"lint verb on {binding.runner} but no linter config file",
            [
                _finding(
                    spec,
                    "catch lint regressions before they land",
                    "a lint verb exists but no linter configuration file is present",
                    Verdict.PARTIAL,
                    [Evidence(binding.runner, note=binding.command)],
                    "Commit a linter config (for example `.eslintrc.json` or `[tool.ruff]`) so the rule set "
                    "does not depend on defaults.",
                )
            ],
        )

    if _recognised(stack, inventory):
        return _outcome(
            spec,
            Verdict.FAIL,
            "no linter config and no lint verb",
            [
                _finding(
                    spec,
                    "catch lint regressions before they land",
                    "no linter is configured and no lint verb is defined",
                    Verdict.FAIL,
                    [Evidence(runner) for runner, _cmds in runner_commands(inventory)],
                    "Add a linter config and a lint read-only verb (eslint, ruff, flake8, golangci-lint, …).",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem, runner manifest or linter config, so a linter cannot be ruled out")
