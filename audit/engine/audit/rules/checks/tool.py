# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`TOOL` pack — tooling.

Anchor: `docs/framework/phased-approach.md` § Key Deliverables.

Implemented here: `TOOL-01` … `TOOL-07`.

The pack verifies that the tools an agent leans on are configured **and reachable through the command
surface**, not merely installed. Verb evidence comes from `audit.rules.checks._common.resolve_verbs`;
config evidence is a small, documented set of filenames per concern. A config file with no way to
invoke the tool is `PARTIAL`, never `PASS` — a formatter an agent cannot run is not a formatter.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **TOOL-01** — a formatter config file (prettier/black/ruff/dprint/config-in-package.json or
  pyproject) **and** a resolvable `format` write verb. Only one of the two ⇒ `PARTIAL`.
* **TOOL-02** — a linter config file (eslint/ruff/flake8/pylint/golangci/rubocop/biome) **and** a
  resolvable `lint` read-only verb. Only one of the two ⇒ `PARTIAL`.
* **TOOL-03** — language-appropriate strict configuration: `tsconfig.json`/`jsconfig.json`,
  `mypy`/`pyright` strict, or `.NET` `<Nullable>enable</Nullable>`. Configured but non-strict ⇒
  `PARTIAL`. An ecosystem with no strict-config concept in this table (go, rust, jvm, ruby, php) ⇒
  `UNKNOWN`. It never invents a type checker for an ecosystem that has none.
* **TOOL-04** — a resolved verb whose command runs a known dependency-audit tool (`npm audit`,
  `pip-audit`, `osv-scanner`, `cargo audit`, `govulncheck`, `snyk`, …). The verb is the evidence;
  it is **not** run (that would be Tier C). A `security` verb that runs something else ⇒ `PARTIAL`.
* **TOOL-05** — a wired hook chain: `.pre-commit-config.yaml`, `lefthook.yml`, a declared
  `core.hooksPath`, or `.husky/` referenced by a `prepare`/install script. Present but unwired ⇒
  `PARTIAL`.
* **TOOL-06** — a commit-message rule in two places. Locally: a commitlint config, a `commit-msg` hook, or an
  equivalent pre-commit/lefthook stage. In CI: a workflow line that runs a commit-message linter (commitlint,
  commitizen's `cz check`, gitlint, the pre-commit or lefthook `commit-msg` stage), a pull-request title check, a
  script the local `commit-msg` stage also runs, or a runner target whose command does one of those. Both ⇒
  `PASS`; one of the two ⇒ `PARTIAL`; neither ⇒ `FAIL` (`COSMETIC`). Whether the CI job runs on pull requests is
  not read.
* **TOOL-07** — a local guard that refuses a commit on a protected branch: pre-commit's `no-commit-to-branch` hook
  (its `--branch`/`--pattern` arguments; `main` and `master` without `--branch`), or a lefthook command, a Husky hook or a
  `pre-commit`/`commit-msg` hook script that reads the current branch (`git symbolic-ref ... HEAD`,
  `git branch --show-current`, `git rev-parse --abbrev-ref HEAD`). The branches it must name are the literal ones
  the declared rules protect (:func:`audit.rules.checks._common.declared_branch_rules`); with none declared, any
  guard counts. A guard in a wired chain that names them all ⇒ `PASS`; a guard in a chain that is not wired, or one
  that misses a protected branch ⇒ `PARTIAL`; hooks but no guard ⇒ `FAIL`; no hook at all ⇒ `UNKNOWN`, which is
  `TOOL-05`'s finding. Whether the guard exits non-zero, and a guard in a script the hook calls, are not read.

Deliberate limits, recorded rather than hidden. **Config detection is filename-based** against the
documented set below; a config that lives somewhere unexpected is not seen. **Verb resolution is
v1's**: only the runner manifests `_common` understands contribute verbs. When there is no
recognised ecosystem, no runner manifest, and no relevant config, the verdict is `UNKNOWN` — an
unrecognised repository is not proof of absence.
"""

from __future__ import annotations

import json
import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.checks._common import declared_branch_rules, resolve_verbs, runner_commands, runner_target
from audit.scan import Kind
from audit.stack import CI_PROVIDERS, extract_npm_scripts
from audit.rules.payloads import Payload

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

#: Commit-message convention configuration filenames.
_COMMITLINT_CONFIG_NAMES: tuple[str, ...] = (
    "commitlint.config.js",
    "commitlint.config.cjs",
    "commitlint.config.mjs",
    "commitlint.config.ts",
    ".commitlintrc",
    ".commitlintrc.json",
    ".commitlintrc.js",
    ".commitlintrc.cjs",
    ".commitlintrc.yml",
    ".commitlintrc.yaml",
    ".commitlintrc.toml",
)

#: Hook managers whose mere presence is a wired chain.
_WIRED_HOOK_FILES: tuple[str, ...] = (".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml")

#: TOOL-06: a CI line that checks commit messages or the pull-request title, by tool. ``@commitlint/cli`` (an
#: install) is not a run; ``wagoid/commitlint-github-action`` is.
_CI_COMMIT_TOOLS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern))
    for name, pattern in (
        ("commitlint", r"(?<!@)\bcommitlint\b(?!/)"),
        ("commitizen", r"\b(?:cz|commitizen)\s+check\b"),
        ("gitlint", r"\bgitlint\b"),
        ("pre-commit commit-msg stage", r"\bpre-commit\s+run\b.*--hook-stage[=\s]+commit-msg\b"),
        ("lefthook commit-msg", r"\blefthook\s+run\s+commit-msg\b"),
        ("pull-request title check", r"\baction-semantic-pull-request\b"),
    )
)

#: TOOL-06: a token in a `commit-msg` stage that may name a repository script.
_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*")
_SCRIPT_SUFFIXES: tuple[str, ...] = (".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".ps1")

#: Ecosystems for which this pack knows a strict type-check configuration.
_TYPECHECK_ECOSYSTEMS: frozenset[str] = frozenset({"node", "python", "dotnet"})

#: Dependency-audit invocations. The verb is evidence; it is never executed.
_AUDIT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?audit\b",
        r"\bpip-audit\b",
        r"\bpip\s+audit\b",
        r"\bsafety\s+check\b",
        r"\bosv-scanner\b",
        r"\bcargo\s+audit\b",
        r"\bgovulncheck\b",
        r"\bsnyk\b",
        r"\btrivy\b",
        r"\bgrype\b",
        r"\bbundler-audit\b",
        r"\bbundle\s+audit\b",
        r"\bcomposer\s+audit\b",
        r"\baudit-ci\b",
        r"\bdotnet\s+list\s+package\b[^&|;]*--vulnerable\b",
    )
)


def _outcome(
    spec, verdict: Verdict, summary: str = "", findings: list[Finding] | None = None, data: Payload | None = None
) -> CheckOutcome:
    return CheckOutcome(
        spec.id,
        spec.title,
        spec.tier,
        spec.severity,
        spec.phase,
        verdict,
        spec.status,
        summary=summary,
        data=data,
        findings=findings or [],
    )


def _unknown(spec, reason: str) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason)


def _recognised(stack, inventory) -> bool:
    """Whether there is any basis to judge: a detected ecosystem or a recognised verb runner."""
    return bool(stack.ecosystems) or bool(runner_commands(inventory))


def _present(inventory, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if inventory.has(name)]


def _read_matches(inventory, rel: str, pattern: str) -> bool:
    text = inventory.read(rel)
    return bool(text and re.search(pattern, text))


def _finding(
    spec,
    cannot: str,
    because: str,
    verdict: Verdict,
    evidence: list[Evidence],
    remediation: str,
    path: str | None = None,
) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence,
        remediation=remediation,
        path=path,
    )


def _manifest_evidence(inventory) -> list[Evidence]:
    """Real runner manifests as evidence, so an absence finding still cites concrete paths."""
    evidence = [Evidence(runner) for runner, _cmds in runner_commands(inventory)]
    return evidence or [Evidence("<repository>", note="detected ecosystem")]


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


def _linter_config(inventory) -> list[str]:
    found = _present(inventory, _LINTER_CONFIG_NAMES)
    if _read_matches(inventory, "pyproject.toml", r"(?m)^\[tool\.(?:ruff|pylint|flake8)\]"):
        found.append("pyproject.toml [tool.*]")
    if _read_matches(inventory, "package.json", r'"eslintConfig"\s*:'):
        found.append("package.json eslintConfig")
    return found


def _strip_jsonc_comments(text: str) -> str:
    """Strip ``//`` and ``/* */`` comments outside string literals, as `tsconfig.json`/`jsconfig.json`
    readers (and TypeScript's own parser) do; ``json.loads`` alone rejects them as invalid JSON."""
    out: list[str] = []
    in_string = False
    escape = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _strip_trailing_commas(text: str) -> str:
    """Drop a ``,`` that precedes a closing ``}``/``]`` (ignoring whitespace), outside string literals —
    TypeScript's own `tsconfig.json`/`jsconfig.json` reader accepts a trailing comma the stdlib does not."""
    out: list[str] = []
    in_string = False
    escape = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _json_true(text: str, key: str) -> bool:
    try:
        data = json.loads(_strip_trailing_commas(_strip_jsonc_comments(text)))
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    options = data.get("compilerOptions")
    if isinstance(options, dict) and options.get(key) is True:
        return True
    return data.get(key) is True


def _typecheck_signals(inventory, stack) -> tuple[list[str], list[str]]:
    """Return ``(strict, nonstrict)`` config evidence for the strict type-checker check."""
    strict: list[str] = []
    nonstrict: list[str] = []

    for rel, key in (("tsconfig.json", "strict"), ("jsconfig.json", "checkJs")):
        text = inventory.read(rel)
        if text is None:
            continue
        (strict if _json_true(text, key) else nonstrict).append(f"{rel}:{key}")

    for rel in ("mypy.ini", ".mypy.ini"):
        if not inventory.has(rel):
            continue
        (strict if _read_matches(inventory, rel, r"(?im)^\s*strict\s*=\s*true") else nonstrict).append(rel)

    for rel, strict_re, present_re in (
        (
            "pyproject.toml",
            r"(?ms)^\[tool\.(?:mypy|pyright)\][^\[]*?"
            r"(?:strict\s*=\s*true|typeCheckingMode\s*=\s*\"strict\")",
            r"(?m)^\[tool\.(?:mypy|pyright)\]",
        ),
        ("setup.cfg", r"(?ms)^\[mypy\][^\[]*?strict\s*=\s*true", r"(?m)^\[mypy\]"),
    ):
        if not inventory.has(rel):
            continue
        if _read_matches(inventory, rel, strict_re):
            strict.append(f"{rel} [mypy/pyright]")
        elif _read_matches(inventory, rel, present_re):
            nonstrict.append(f"{rel} [mypy/pyright]")

    pyright = inventory.read("pyrightconfig.json")
    if pyright is not None:
        if re.search(r'"typeCheckingMode"\s*:\s*"strict"', pyright) or re.search(r'"strict"\s*:', pyright):
            strict.append("pyrightconfig.json")
        else:
            nonstrict.append("pyrightconfig.json")

    for rel in inventory.match("*.csproj") + inventory.match("Directory.Build.props", "Directory.Build.targets"):
        text = inventory.read(rel)
        if not text:
            continue
        if re.search(r"<Nullable>\s*enable\s*</Nullable>", text, re.IGNORECASE):
            strict.append(f"{rel}:Nullable")
        elif "<Nullable>" in text:
            nonstrict.append(rel)
    if inventory.has("global.json"):
        nonstrict.append("global.json")

    binding = resolve_verbs(inventory, stack).get("typecheck")
    if binding and re.search(r"--strict\b", binding.command):
        strict.append(f"{binding.runner}:typecheck --strict")

    return strict, nonstrict


def _hook_wiring(inventory) -> tuple[list[str], list[str]]:
    """Return ``(wired, configured)`` hook-chain evidence."""
    wired = _present(inventory, _WIRED_HOOK_FILES)
    configured: list[str] = []

    hooks_path = inventory.grep(
        r"core\.hooksPath",
        kinds=(Kind.MANIFEST, Kind.CONFIG, Kind.SCRIPT, Kind.CI, Kind.BUILD),
    )
    if hooks_path:
        wired.append(f"{hooks_path[0][0]} core.hooksPath")

    githooks = inventory.match(".githooks/*")
    if githooks and not hooks_path:
        configured.append(".githooks/")

    husky = inventory.match(".husky/*")
    if husky:
        if _husky_referenced(inventory):
            wired.append(".husky/ (referenced)")
        else:
            configured.append(".husky/ (not referenced)")

    return wired, configured


def _husky_referenced(inventory) -> bool:
    scripts = extract_npm_scripts(inventory)
    return any("husky" in command for command in scripts.values())


def _commit_rule(inventory) -> list[str]:
    found = _present(inventory, _COMMITLINT_CONFIG_NAMES)
    if _read_matches(inventory, "package.json", r'"commitlint"\s*:'):
        found.append("package.json commitlint")
    for rel in (".husky/commit-msg", ".githooks/commit-msg"):
        if inventory.has(rel):
            found.append(rel)
    for rel in (".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml"):
        if _read_matches(inventory, rel, r"(?i)commit-msg|commitlint|conventional"):
            found.append(f"{rel}:commit-msg")
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


# ===========================================================================
# TOOL-03 — type checker configured
# ===========================================================================


def check_tool03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    strict, nonstrict = _typecheck_signals(inventory, stack)

    if strict:
        return _outcome(spec, Verdict.PASS, f"strict config: {', '.join(sorted(set(strict)))}")

    if nonstrict:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"type checker configured but not strict: {', '.join(sorted(set(nonstrict)))}",
            [
                _finding(
                    spec,
                    "trust the type checker to catch a whole class of defects",
                    f"a type-check configuration exists but is not strict ({', '.join(sorted(set(nonstrict)))})",
                    Verdict.PARTIAL,
                    [Evidence(rel) for rel in sorted(set(nonstrict))],
                    "Turn on strict mode (tsconfig `strict: true`, mypy `strict = true`, pyright "
                    '`typeCheckingMode: "strict"`) so the checker\'s findings are trustworthy.',
                )
            ],
        )

    if set(stack.ecosystems) & _TYPECHECK_ECOSYSTEMS:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no strict type-check configuration",
            [
                _finding(
                    spec,
                    "trust the type checker to catch a whole class of defects",
                    "no strict type-check configuration is present for the detected ecosystem "
                    f"({', '.join(sorted(set(stack.ecosystems)))})",
                    Verdict.FAIL,
                    _manifest_evidence(inventory),
                    "Add a strict type-check configuration (tsconfig.json strict, mypy/pyright strict, or "
                    ".NET `<Nullable>enable</Nullable>`).",
                )
            ],
        )

    return _unknown(
        spec,
        "no recognised strict type-check configuration and no ecosystem this "
        "pack knows one for, so type-checking cannot be judged",
    )


# ===========================================================================
# TOOL-04 — dependency / security scan verb
# ===========================================================================


def _is_audit_command(command: str) -> bool:
    return any(pattern.search(command) for pattern in _AUDIT_PATTERNS)


def check_tool04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    bindings = resolve_verbs(inventory, stack)
    audits = [(verb, b) for verb, b in bindings.items() if _is_audit_command(b.command)]

    if audits:
        detail = "; ".join(f"{verb} -> {b.command}" for verb, b in sorted(audits))
        return _outcome(spec, Verdict.PASS, detail)

    security = bindings.get("security")
    if security is not None:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"security verb on {security.runner} runs no dependency audit ({security.command})",
            [
                _finding(
                    spec,
                    "know whether a dependency carries a known vulnerability",
                    "a security verb exists but it does not run a dependency-audit check",
                    Verdict.PARTIAL,
                    [Evidence(security.runner, note=security.command)],
                    "Make the security verb run a dependency audit (npm audit, pip-audit, osv-scanner, "
                    "cargo audit, govulncheck, snyk).",
                )
            ],
        )

    if _recognised(stack, inventory):
        return _outcome(
            spec,
            Verdict.FAIL,
            "no verb runs a dependency audit",
            [
                _finding(
                    spec,
                    "know whether a dependency carries a known vulnerability",
                    "no resolvable verb runs a dependency-audit check",
                    Verdict.FAIL,
                    [Evidence(runner) for runner, _cmds in runner_commands(inventory)],
                    "Add a dependency-audit verb (npm audit, pip-audit, osv-scanner, cargo audit, govulncheck, snyk).",
                )
            ],
        )

    return _unknown(
        spec,
        "no recognised ecosystem, runner manifest or dependency-audit verb, so a dependency scan cannot be ruled out",
    )


# ===========================================================================
# TOOL-05 — local hook chain active
# ===========================================================================


def check_tool05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    wired, configured = _hook_wiring(inventory)

    if wired:
        return _outcome(spec, Verdict.PASS, f"wired: {', '.join(sorted(set(wired)))}")

    if configured:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"hooks present but not wired: {', '.join(sorted(set(configured)))}",
            [
                _finding(
                    spec,
                    "rely on local hooks to run before a commit",
                    f"a hook manager is present but not wired ({', '.join(sorted(set(configured)))})",
                    Verdict.PARTIAL,
                    [Evidence(rel.split(" ")[0]) for rel in sorted(set(configured))],
                    "Wire the hooks: set `core.hooksPath`, add a `prepare`/install script, or commit a "
                    "`.pre-commit-config.yaml`.",
                )
            ],
        )

    if stack.ecosystems:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no hook chain configured",
            [
                _finding(
                    spec,
                    "rely on local hooks to run before a commit",
                    "no hook manager is configured",
                    Verdict.FAIL,
                    _manifest_evidence(inventory),
                    "Adopt a hook manager (pre-commit, lefthook, husky) and wire it so checks run before a "
                    "commit rather than only in CI.",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem and no hook configuration, so a hook chain cannot be ruled out")


# ===========================================================================
# TOOL-06 — commit convention enforced
# ===========================================================================


def _commit_msg_text(inventory) -> list[str]:
    """The lines of every local `commit-msg` stage: the hook files, lefthook's `commit-msg:` block, and each
    pre-commit hook item whose text names the `commit-msg` stage."""
    lines: list[str] = []
    for rel in (".husky/commit-msg", ".githooks/commit-msg"):
        lines.extend((inventory.read(rel) or "").splitlines())
    for rel in ("lefthook.yml", "lefthook.yaml"):
        inside = False
        for line in (inventory.read(rel) or "").splitlines():
            if line and not line[0].isspace() and not line.startswith("#"):
                inside = line.split(":", 1)[0].strip().strip("'\"") == "commit-msg"
                continue
            if inside:
                lines.append(line)
    item: list[str] = []
    for line in [*(inventory.read(".pre-commit-config.yaml") or "").splitlines(), "- id: <end>"]:
        if re.match(r"^\s*-\s+(?:id|repo)\s*:", line):
            if any("commit-msg" in text for text in item):
                lines.extend(item)
            item = []
        item.append(line)
    return lines


def _commit_msg_scripts(inventory) -> list[str]:
    """Repository scripts a local `commit-msg` stage runs, by path, so CI can be seen to run the same rule."""
    paths = set(inventory.paths())
    scripts: set[str] = set()
    for line in _commit_msg_text(inventory):
        for token in _PATH_TOKEN_RE.findall(line):
            rel = token.removeprefix("./")
            if rel in paths and rel.endswith(_SCRIPT_SUFFIXES):
                scripts.add(rel)
    return sorted(scripts)


def _commit_rule_in(text: str, scripts: list[str]) -> str | None:
    """What in ``text`` checks commit messages: a known tool, or a script the local stage runs."""
    for name, pattern in _CI_COMMIT_TOOLS:
        if pattern.search(text):
            return name
    for rel in scripts:
        if re.search(r"(?<![\w/.-])(?:\./)?" + re.escape(rel) + r"(?![\w/-])", text):
            return rel
    return None


def _ci_commit_steps(inventory, scripts: list[str]) -> list[tuple[str, int, str]]:
    """``(workflow, line, what)`` for each workflow line that checks commit messages or the pull-request title,
    directly or through a runner target (``make commit-lint``, ``npm run commitlint``)."""
    targets: dict[str, str] = {}
    for _runner, commands in reversed(runner_commands(inventory)):
        targets.update(commands)
    hits: list[tuple[str, int, str]] = []
    for globs in CI_PROVIDERS.values():
        for rel in sorted(inventory.match(*globs)):
            for number, line in enumerate((inventory.read(rel) or "").splitlines(), start=1):
                if line.lstrip().startswith("#"):
                    continue
                what = _commit_rule_in(line, scripts)
                target = runner_target(line)
                if what is None and target in targets:
                    via = _commit_rule_in(targets[target], scripts)
                    what = f"{target} ({via})" if via else None
                if what:
                    hits.append((rel, number, what))
    return hits


def check_tool06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    rules = sorted(set(_commit_rule(inventory)))
    ci_steps = _ci_commit_steps(inventory, _commit_msg_scripts(inventory))
    ci_seen = ", ".join(sorted({f"{what} ({rel})" for rel, _line, what in ci_steps}))
    detail = f"local: {', '.join(rules) or 'none'}; CI: {ci_seen or 'none'}"

    if rules and ci_steps:
        return _outcome(spec, Verdict.PASS, detail)
    if rules:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            detail,
            [
                _finding(
                    spec,
                    "rely on every commit following the convention",
                    "the commit-message rule runs only in a local hook, which `--no-verify` or a missing install "
                    "skips, and no CI step checks it",
                    Verdict.PARTIAL,
                    [Evidence(rel.split(" ")[0].split(":")[0]) for rel in rules],
                    "Run the same commit-message rule in CI over the commits a pull request adds (or check the "
                    "pull-request title when the repository squash-merges).",
                )
            ],
        )
    if ci_steps:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            detail,
            [
                _finding(
                    spec,
                    "learn that a commit message breaks the convention before it pushes",
                    "the commit-message rule runs only in CI; no local `commit-msg` stage runs it",
                    Verdict.PARTIAL,
                    [Evidence(rel, line=line, note=what) for rel, line, what in ci_steps],
                    "Run the same rule in a local `commit-msg` hook, with the type list CI uses.",
                )
            ],
        )

    wired, configured = _hook_wiring(inventory)
    if stack.ecosystems or wired or configured:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no commit-message rule",
            [
                _finding(
                    spec,
                    "rely on a consistent commit-message convention",
                    "no commitlint config, commit-msg hook, equivalent stage or CI step exists",
                    Verdict.FAIL,
                    _manifest_evidence(inventory),
                    "Add a commit-message rule to a commit-msg hook and run the same rule in CI.",
                )
            ],
        )

    return _unknown(spec, "no recognised ecosystem and no hook configuration, so a commit convention cannot be judged")


# ===========================================================================
# TOOL-07 — local guard against commits to a protected branch
# ===========================================================================

#: A hook command that reads the branch being committed to.
_BRANCH_READ_RE = re.compile(
    r"git\s+(?:symbolic-ref\b[^\n]*\bHEAD\b|branch\s+--show-current\b|rev-parse\s+--abbrev-ref\s+HEAD\b)"
)

#: Hook scripts by name: ``.husky/``, ``.githooks/`` or any ``core.hooksPath`` directory. A commit-msg hook also
#: stops the commit, so either stage counts; ``pre-push`` does not.
_GUARD_HOOK_NAMES = frozenset({"pre-commit", "commit-msg"})

#: pre-commit-hooks' ``no-commit-to-branch`` protects these when it is given no ``--branch`` argument, with or
#: without ``--pattern`` (``args.branch or ('master', 'main')`` in its source, checked at v6.0.0).
_NO_COMMIT_DEFAULTS = ("main", "master")

_ARG_SEP = r"[\s,='\"\-]+"
_BRANCH_ARG_RE = re.compile(r"(?:--branch|\B-b)" + _ARG_SEP + r"([A-Za-z0-9_][\w./-]*)")
_PATTERN_ARG_RE = re.compile(r"(?:--pattern|\B-p)" + _ARG_SEP + r"([^\s,'\"\]]+)")


class _Guard:
    """One guard: where it is, whether its hook chain is wired, and which branches it names."""

    def __init__(self, rel: str, line: int, wired: bool, text: str, patterns: tuple[str, ...] = ()) -> None:
        self.rel = rel
        self.line = line
        self.wired = wired
        self.text = text
        self.patterns = patterns

    def covers(self, branch: str) -> bool:
        for pattern in self.patterns:
            try:
                if re.match(pattern, branch):
                    return True
            except re.error:
                continue
        return re.search(rf"(?<![\w/.-]){re.escape(branch)}(?![\w/.-])", self.text) is not None


def _block(lines: list[str], start: int) -> str:
    """Line ``start`` and the lines after it indented at least as deep: the command a branch read belongs to."""
    depth = len(lines[start]) - len(lines[start].lstrip())
    out = [lines[start]]
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) < depth:
            break
        out.append(line)
    return "\n".join(out)


def _pre_commit_guards(text: str, rel: str) -> list[_Guard]:
    guards: list[_Guard] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^\s*-?\s*id:\s*['\"]?no-commit-to-branch\b", line):
            block = _block(lines, index)
            branches = _BRANCH_ARG_RE.findall(block)
            patterns = tuple(_PATTERN_ARG_RE.findall(block))
            if not branches:
                branches = list(_NO_COMMIT_DEFAULTS)
            guards.append(_Guard(rel, index + 1, True, " ".join(branches), patterns))
    return guards


def _stage(lines: list[str], index: int) -> str:
    """The top-level key above line ``index``: a lefthook stage name."""
    for line in reversed(lines[: index + 1]):
        if line.strip() and not line[0].isspace() and not line.startswith("#"):
            return line.split(":", 1)[0].strip()
    return ""


def _branch_read_guards(text: str, rel: str, wired: bool, *, whole_file: bool, staged: bool = False) -> list[_Guard]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith("#") or not _BRANCH_READ_RE.search(line):
            continue
        if staged and _stage(lines, index) not in _GUARD_HOOK_NAMES:
            continue
        return [_Guard(rel, index + 1, wired, text if whole_file else _block(lines, index))]
    return []


def _local_guards(inventory) -> list[_Guard]:
    hooks_path = bool(
        inventory.grep(r"core\.hooksPath", kinds=(Kind.MANIFEST, Kind.CONFIG, Kind.SCRIPT, Kind.CI, Kind.BUILD))
    )
    guards: list[_Guard] = []
    for rel in _present(inventory, _WIRED_HOOK_FILES):
        text = inventory.read(rel) or ""
        if rel == ".pre-commit-config.yaml":
            guards.extend(_pre_commit_guards(text, rel))
        guards.extend(_branch_read_guards(text, rel, True, whole_file=False, staged=rel.startswith("lefthook")))
    for entry in inventory.files:
        name = entry.rel.rsplit("/", 1)[-1]
        if name not in _GUARD_HOOK_NAMES or entry.rel.startswith(".git/"):
            continue
        wired = _husky_referenced(inventory) if entry.rel.startswith(".husky/") else hooks_path
        guards.extend(_branch_read_guards(inventory.read(entry.rel) or "", entry.rel, wired, whole_file=True))
    return sorted(guards, key=lambda guard: (guard.rel, guard.line))


def check_tool07(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    guards = _local_guards(inventory)
    protected = declared_branch_rules(inventory).literal_branches
    if not guards:
        wired, configured = _hook_wiring(inventory)
        if not wired and not configured:
            return _unknown(spec, "no hook chain to hold a branch guard; TOOL-05 owns that finding")
        hooks = ", ".join(sorted(set(wired + configured)))
        return _outcome(
            spec,
            Verdict.FAIL,
            f"hooks present ({hooks}) but none refuses a commit on a protected branch",
            [
                _finding(
                    spec,
                    "learn it is on a protected branch before it commits",
                    "no local hook reads the current branch or runs no-commit-to-branch",
                    Verdict.FAIL,
                    [Evidence(rel.split(" ")[0]) for rel in sorted(set(wired + configured))],
                    "Add a pre-commit guard that refuses a commit on the protected branches: pre-commit's "
                    "no-commit-to-branch, or a hook command that reads `git branch --show-current` and exits 1.",
                )
            ],
        )

    wired_guards = [guard for guard in guards if guard.wired]
    where = ", ".join(f"{guard.rel}:{guard.line}" for guard in (wired_guards or guards))
    if not wired_guards:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"branch guard at {where}, but its hook chain is not wired",
            [
                _finding(
                    spec,
                    "rely on the branch guard to run before a commit",
                    f"the guard at {where} is in a hook directory nothing installs",
                    Verdict.PARTIAL,
                    [Evidence(guard.rel, line=guard.line) for guard in guards],
                    "Wire the hook chain (TOOL-05) so the guard runs.",
                )
            ],
        )

    missing = [branch for branch in protected if not any(guard.covers(branch) for guard in wired_guards)]
    if missing:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"branch guard at {where} does not name {', '.join(missing)}, which the declared rules protect",
            [
                _finding(
                    spec,
                    f"learn before a commit that {', '.join(missing)} is protected",
                    f"the guard at {where} does not name {', '.join(missing)}",
                    Verdict.PARTIAL,
                    [Evidence(guard.rel, line=guard.line) for guard in wired_guards],
                    f"Add {', '.join(missing)} to the guard's branch list.",
                )
            ],
        )
    named = f"; names {', '.join(protected)}" if protected else ""
    return _outcome(spec, Verdict.PASS, f"branch guard at {where}{named}")


IMPLEMENTATIONS = {
    "TOOL-01": check_tool01,
    "TOOL-02": check_tool02,
    "TOOL-03": check_tool03,
    "TOOL-04": check_tool04,
    "TOOL-05": check_tool05,
    "TOOL-06": check_tool06,
    "TOOL-07": check_tool07,
}
