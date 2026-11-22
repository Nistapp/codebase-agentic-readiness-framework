# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""EXEC-08: Tool versions visible to dependency automation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.scan import Inventory
from audit.rules.checks.execution._shared import _outcome, _unknown

SPEC = declare("EXEC-08", "Tool versions visible to dependency automation", "B", Severity.DEGRADER)


# ===========================================================================
# EXEC-08 — tool versions visible to dependency automation
# ===========================================================================

#: Basenames of the command-runner and hook files whose lines are read.
_INLINE_SURFACE_NAMES = frozenset(
    {
        "Makefile",
        "makefile",
        "GNUmakefile",
        "justfile",
        "Justfile",
        ".justfile",
        "Taskfile.yml",
        "Taskfile.yaml",
        "package.json",
        "lefthook.yml",
        "lefthook.yaml",
        ".lefthook.yml",
        ".lefthook.yaml",
        ".gitlab-ci.yml",
    }
)

_LITERAL_VERSION = r"v?\d[\w.+-]*"
_SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")

#: ``(ecosystem, launcher pattern)``. The tokens after a launcher are read for ``name@version`` or
#: ``name==version``; a version is a literal only when it starts with a digit (or ``v`` and a digit).
_INLINE_LAUNCHERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("node", re.compile(r"(?:^|[\s(\"'])(?:npx|bunx|pnpx|pnpm\s+dlx|yarn\s+dlx|npm\s+exec)\s")),
    ("node", re.compile(r"(?:^|[\s(\"'])npm\s+(?:install|i)\s+(?:\S+\s+)*?(?:-g|--global)\b")),
    ("python", re.compile(r"(?:^|[\s(\"'])(?:uvx|uv\s+tool\s+(?:run|install)|pipx\s+(?:run|install))\s")),
    ("python", re.compile(r"(?:^|[\s(\"'])uv\s+run\s")),
    ("python", re.compile(r"(?:^|[\s(\"'])(?:pip3?|uv\s+pip|python3?\s+-m\s+pip)\s+install\s")),
    ("go", re.compile(r"(?:^|[\s(\"'])go\s+(?:run|install)\s")),
    ("rust", re.compile(r"(?:^|[\s(\"'])cargo\s+(?:install|binstall)\s")),
)

_NODE_TOKEN = re.compile(rf"^(@?[A-Za-z0-9][\w./-]*)@({_LITERAL_VERSION})$")
_PYTHON_TOKEN = re.compile(rf"^([A-Za-z0-9][\w.-]*)(?:\[[^\]]*\])?(?:==|@)({_LITERAL_VERSION})$")
_GO_TOKEN = re.compile(r"^([\w.-]+(?:/[\w.-]+)+)@(v\d[\w.+-]*)$")
_RUST_TOKEN = re.compile(rf"^([A-Za-z0-9][\w-]*)@({_LITERAL_VERSION})$")
_TOKEN_PATTERNS = {"node": _NODE_TOKEN, "python": _PYTHON_TOKEN, "go": _GO_TOKEN, "rust": _RUST_TOKEN}

#: Tool-installer actions whose input names a tool version: ``action -> (input, ecosystem, tool name)``.
_INSTALLER_ACTIONS: dict[str, tuple[str, str, str]] = {
    "astral-sh/setup-uv": ("version", "python", "uv"),
    "pnpm/action-setup": ("version", "node", "pnpm"),
    "oven-sh/setup-bun": ("bun-version", "node", "bun"),
    "golangci/golangci-lint-action": ("version", "go", "github.com/golangci/golangci-lint"),
}
_USES_RE = re.compile(r"^(\s*)(?:-\s+)?uses:\s*['\"]?([\w.-]+/[\w.-]+)(?:/[\w./-]*)?@")

_RENOVATE_FILES = ("renovate.json", ".renovaterc", ".renovaterc.json", ".github/renovate.json")


@dataclass(frozen=True)
class _InlineVersion:
    path: str
    line: int
    ecosystem: str
    tool: str
    version: str


def _inline_surfaces(inv: Inventory) -> list[str]:
    out = []
    for rel in inv.paths():
        base = rel.rsplit("/", 1)[-1]
        if (
            base in _INLINE_SURFACE_NAMES
            or base.endswith(".mk")
            or (rel.startswith(".github/workflows/") and base.endswith((".yml", ".yaml")))
            or (rel.startswith(".husky/") and rel.count("/") == 1)
        ):
            out.append(rel)
    return sorted(out)


def _token(raw: str) -> str:
    token = raw.strip().strip("\"'`,)")
    for prefix in ("--from=", "--with=", "--spec=", "--package="):
        if token.startswith(prefix):
            return token[len(prefix) :]
    return token


def _versions_in_segment(segment: str) -> list[tuple[str, str, str]]:
    """``(ecosystem, tool, version)`` for each literal-versioned token after a launcher in one command."""
    found: list[tuple[str, str, str]] = []
    for ecosystem, launcher in _INLINE_LAUNCHERS:
        match = launcher.search(segment)
        if not match:
            continue
        tokens = [_token(raw) for raw in segment[match.end() :].split()]
        pattern = _TOKEN_PATTERNS[ecosystem]
        for index, token in enumerate(tokens):
            hit = pattern.match(token)
            if hit:
                found.append((ecosystem, hit.group(1), hit.group(2)))
            elif ecosystem == "rust" and token in ("--version", "--vers") and index + 1 < len(tokens):
                name = next((t for t in tokens[:index] if not t.startswith("-")), None)
                if name and re.match(rf"^{_LITERAL_VERSION}$", tokens[index + 1]):
                    found.append((ecosystem, name, tokens[index + 1]))
    return sorted(set(found))


def _installer_versions(lines: list[str]) -> list[tuple[int, str, str, str]]:
    """``(line, ecosystem, tool, version)`` for a literal ``version`` input of a known tool-installer action."""
    found: list[tuple[int, str, str, str]] = []
    for index, line in enumerate(lines):
        uses = _USES_RE.match(line)
        if not uses or uses.group(2) not in _INSTALLER_ACTIONS:
            continue
        key, ecosystem, tool = _INSTALLER_ACTIONS[uses.group(2)]
        step_indent = len(uses.group(1))
        for number in range(index + 1, len(lines)):
            text = lines[number]
            if text.strip() and len(text) - len(text.lstrip()) <= step_indent:
                break
            value = re.match(rf"^\s*{re.escape(key)}:\s*['\"]?({_LITERAL_VERSION})['\"]?\s*(#.*)?$", text)
            if value:
                found.append((number + 1, ecosystem, tool, value.group(1)))
    return found


def _inline_versions(inv: Inventory, rel: str) -> list[_InlineVersion]:
    text = inv.read(rel) or ""
    lines = text.splitlines()
    out: list[_InlineVersion] = []
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("#"):
            continue
        for segment in _SEGMENT_SPLIT.split(line):
            for ecosystem, tool, version in _versions_in_segment(segment):
                out.append(_InlineVersion(rel, number, ecosystem, tool, version))
    if rel.startswith(".github/workflows/"):
        out.extend(_InlineVersion(rel, n, eco, tool, ver) for n, eco, tool, ver in _installer_versions(lines))
    return sorted(set(out), key=lambda v: (v.path, v.line, v.tool, v.version))


def _renovate_patterns(inv: Inventory) -> list[re.Pattern[str]]:
    """The file patterns of every Renovate custom manager: files Renovate reads versions from by regex."""
    patterns: list[re.Pattern[str]] = []
    for rel in _RENOVATE_FILES:
        try:
            config = json.loads(inv.read(rel) or "")
        except ValueError:
            continue
        if not isinstance(config, dict):
            continue
        for key in ("customManagers", "regexManagers"):
            managers = config.get(key)
            for manager in managers if isinstance(managers, list) else []:
                if not isinstance(manager, dict):
                    continue
                for field_name in ("fileMatch", "managerFilePatterns"):
                    raw = manager.get(field_name)
                    for item in raw if isinstance(raw, list) else []:
                        text = str(item)
                        if len(text) > 1 and text.startswith("/") and text.endswith("/"):
                            text = text[1:-1]
                        try:
                            patterns.append(re.compile(text))
                        except re.error:
                            continue
    return patterns


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _bare(version: str) -> str:
    return version[1:] if version.startswith("v") else version


def _node_manifest_holds(inv: Inventory, tool: str, version: str) -> bool:
    for rel in inv.paths():
        if rel.rsplit("/", 1)[-1] != "package.json":
            continue
        try:
            manifest = json.loads(inv.read(rel) or "")
        except ValueError:
            continue
        if not isinstance(manifest, dict):
            continue
        if manifest.get("packageManager") == f"{tool}@{_bare(version)}":
            return True
        for key in ("dependencies", "devDependencies", "optionalDependencies"):
            deps = manifest.get(key)
            if isinstance(deps, dict) and str(deps.get(tool, "")).lstrip("^~=v") == _bare(version):
                return True
    return False


def _python_manifest_holds(inv: Inventory, tool: str, version: str) -> bool:
    wanted = _normalise(tool)
    pin = re.compile(r"([A-Za-z0-9][\w.-]*)(?:\[[^\]]*\])?\s*==\s*([\w.+-]+)")
    for rel in inv.paths():
        base = rel.rsplit("/", 1)[-1]
        if base != "pyproject.toml" and not (base.startswith("requirements") and base.endswith(".txt")):
            continue
        for name, pinned in pin.findall(inv.read(rel) or ""):
            if _normalise(name) == wanted and pinned == version:
                return True
    return False


def _go_manifest_holds(inv: Inventory, tool: str, version: str) -> bool:
    for rel in inv.paths():
        if rel.rsplit("/", 1)[-1] != "go.mod":
            continue
        for line in (inv.read(rel) or "").splitlines():
            parts = line.split("//", 1)[0].split()
            if parts and parts[0] == "require":
                parts = parts[1:]
            if len(parts) >= 2 and (tool == parts[0] or tool.startswith(parts[0] + "/")):
                if _bare(parts[1]) == _bare(version):
                    return True
    return False


def _rust_manifest_holds(inv: Inventory, tool: str, version: str) -> bool:
    pin = re.compile(rf"^\s*{re.escape(tool)}\s*=\s*(?:\{{[^}}]*version\s*=\s*)?\"[=^~]?{re.escape(version)}\"", re.M)
    return any(pin.search(inv.read(rel) or "") for rel in inv.paths() if rel.rsplit("/", 1)[-1] == "Cargo.toml")


def _manifest_holds(inv: Inventory, found: _InlineVersion) -> bool:
    """Whether a manifest that dependency automation reads names the same tool at the same version."""
    lookup = {
        "node": _node_manifest_holds,
        "python": _python_manifest_holds,
        "go": _go_manifest_holds,
        "rust": _rust_manifest_holds,
    }[found.ecosystem]
    return lookup(inv, found.tool, found.version)


def check_exec08(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    surfaces = _inline_surfaces(inventory)
    if not surfaces:
        return _unknown(spec, "no command runner, workflow or hook file to read for tool versions")
    patterns = _renovate_patterns(inventory)
    visible = [rel for rel in surfaces if any(pattern.search(rel) for pattern in patterns)]
    inline = [v for rel in surfaces if rel not in visible for v in _inline_versions(inventory, rel)]
    if not inline:
        note = f"; {len(visible)} file(s) read by a Renovate custom manager" if visible else ""
        return _outcome(spec, Verdict.PASS, f"no literal tool version in {len(surfaces)} command file(s){note}")

    unheld = [v for v in inline if not _manifest_holds(inventory, v)]
    held = [v for v in inline if v not in unheld]

    def evidence(items: list[_InlineVersion]) -> list[Evidence]:
        return [Evidence(v.path, line=v.line, note=f"{v.tool} {v.version}") for v in items]

    findings: list[Finding] = []
    if unheld:
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "rely on dependency automation to patch the tools the gate runs",
                    f"{len(unheld)} tool version(s) are written into commands and no manifest holds them "
                    f"({', '.join(sorted({v.tool for v in unheld}))})",
                ),
                evidence=evidence(unheld),
                path=unheld[0].path,
                remediation="Move each version into a manifest the dependency-update tool reads (a dev-tools "
                "package.json or pyproject.toml with a lockfile, a go.mod tool directive) and have the "
                "command read it from there.",
            )
        )
    if held:
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.PARTIAL,
                statement=statement(
                    "trust that one update changes every copy of a tool version",
                    f"{len(held)} tool version(s) written into commands repeat a manifest pin "
                    f"({', '.join(sorted({v.tool for v in held}))}), so the copy drifts when the manifest is updated",
                ),
                evidence=evidence(held),
                path=f"{held[0].path}:duplicate",
                remediation="Have the command read the version from the manifest instead of repeating it.",
            )
        )
    verdict = Verdict.FAIL if unheld else Verdict.PARTIAL
    summary = (
        f"{len(unheld)} literal tool version(s) no manifest holds"
        if unheld
        else f"{len(held)} literal tool version(s) repeat a manifest pin"
    )
    return _outcome(spec, verdict, summary, findings)


def reads():
    """What this check reads in a target; ``audit/rules/reads.py`` gathers it into ``READS``."""
    from audit.rules.reads import ANY_DEPTH, GLOB, ROOT, Reads, What, _GO_FIXTURE, _at

    return Reads(
        where=(
            *_at(
                ANY_DEPTH,
                ".gitlab-ci.yml",
                ".justfile",
                ".lefthook.yaml",
                ".lefthook.yml",
                "GNUmakefile",
                "Justfile",
                "Makefile",
                "Taskfile.yaml",
                "Taskfile.yml",
                "justfile",
                "lefthook.yaml",
                "lefthook.yml",
                "makefile",
                "package.json",
            ),
            *_at(GLOB, "**/*.mk", ".github/workflows/**/*.yml", ".github/workflows/**/*.yaml", ".husky/*"),
            *_at(ROOT, "renovate.json", ".renovaterc", ".renovaterc.json", ".github/renovate.json"),
            *_at(ANY_DEPTH, "pyproject.toml"),
            *_at(ANY_DEPTH, "go.mod", unexercised=_GO_FIXTURE),
            *_at(ANY_DEPTH, "Cargo.toml"),
            *_at(GLOB, "**/requirements*.txt"),
        ),
        what=What("word-list"),
        binding="line",
        threshold="no literal tool version outside a manifest",
        note=(
            "Each non-comment line, split at shell operators: a launcher (npx, uvx, pip install, go install, "
            "cargo install and others) then a name@version or name==version token in the same segment; in a "
            "workflow also the version input of four installer actions. A file a Renovate custom manager "
            "matches is skipped, and every package.json, pyproject.toml, requirements*.txt, go.mod and "
            "Cargo.toml is read to see whether a manifest holds the version."
        ),
    )
