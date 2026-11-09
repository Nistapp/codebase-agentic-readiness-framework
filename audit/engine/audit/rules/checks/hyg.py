# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`HYG` pack — repository hygiene (informational, never scored).

Anchor: `docs/framework/phased-approach.md` § Phase 1: Agentic Bootstrap.

Implemented here: `HYG-01` … `HYG-11`. Every check reads its artifact through
:class:`audit.scan.Inventory`; none writes to the target and none runs a command in the target's
toolchain — `HYG-07` reads git metadata, read-only, through :func:`_git_output`.

Verdict contract for this pack — **absent artifacts are `FAIL`**. These checks are informational
(`scored=False` in the registry), so a `FAIL` is a reported fact and does not move the readiness
number. ``UNKNOWN`` is reserved for "the artifact is present but its quality cannot be settled":
an unreadable README, an undatable changelog, or an unrecognisable CI provider for branch
protection. It is never used merely because an artifact is absent.

* **HYG-01** — a root `README*` is the evidence. Present and at least
  :data:`MIN_README_CHARS` characters of body, free of a :data:`STUB_MARKERS` marker and not a bare
  title, is `PASS`. Present but below the bar is `FAIL` (with the file as evidence); present but
  unreadable (binary or oversized) is ``UNKNOWN``; absent is `FAIL`.
* **HYG-02** — `CODEOWNERS` at the root, under `.github/`, `.gitlab/` or `docs/`.
* **HYG-03** — any `pull_request_template*` (case-insensitive), normally under `.github/`.
* **HYG-04** — at least one file under `.github/ISSUE_TEMPLATE/`, or `.github/ISSUE_TEMPLATE.md`.
* **HYG-05** — a `CONTRIBUTING*` document at the root or under `.github/`, `.gitlab/` or `docs/`.
* **HYG-06** — a `SECURITY*` document at the same places.
* **HYG-07** — a `CHANGELOG*` document, **dated recently**. This is the only time-sensitive rule.
  Recency is derived from the repository's own git history, never from wall-clock time (AGENTS.md §5):
  the changelog's last commit date is compared with the `HEAD` commit date and is "recent" when it
  falls within :data:`RECENT_WINDOW`. When git cannot supply either date — no repository, git absent,
  or the changelog untracked — the verdict is ``UNKNOWN``, not ``FAIL`` and never ``date.today()``.
* **HYG-08** — a text/markdown document whose filename contains "release" (a release process or
  release-notes page), at the same places. CI workflow files named `release.yml` are not documents and do
  not count.
* **HYG-09** — Dependabot or Renovate configuration at any of its conventional locations, read for two defects
  that hold whatever update policy the owner chose. (1) **Coverage:** every ecosystem the stack names from a
  manifest, plus `github-actions` when GitHub CI is detected, has a Dependabot entry of an accepted
  `package-ecosystem` (:data:`_DEPENDABOT_ECOSYSTEMS`); Renovate covers every manager unless `enabledManagers`
  leaves one out (:data:`_RENOVATE_MANAGERS`). (2) **The `target-branch` trap:** a Dependabot entry that sets
  `target-branch` together with `ignore` or `groups`, whose options then do not apply to security updates. Either
  defect is `PARTIAL`. A configuration whose content cannot be read (no `updates:` list, invalid JSON) is
  ``UNKNOWN`` when it is the only one or when an ecosystem is uncovered; `renovate.json5` and `renovate.config.js`
  count on presence. Coverage is per ecosystem, not per directory.
* **HYG-10** — a root license file: `LICENSE*`, `LICENCE*`, `COPYING*`, `COPYRIGHT*` or `UNLICENSE*`
  (case-insensitive, bare name or document suffix).
* **HYG-11** — branch protection declared as code, where the provider allows it. A
  `*branch-protection*`/`*branch_protection*` file, a `*branch_protection*` Terraform resource, or a
  document describing the provider's config is `PASS`. None found is `FAIL` when the CI provider is
  one that offers config-as-code (GitHub, GitLab); it is ``UNKNOWN`` when no such provider is
  recognised, because whether protection *can* be declared as code is provider-dependent.

Presence is repository-level (ADR-0008): a hygiene file counts at the root or under `.github/`, `.gitlab/` or
`docs/` (:func:`_repository_level`), never in a component's or a template's directory. Carried data
(`templates/`, `examples/`, `fixtures/`) is not in the inventory at all.

Deliberate limit, recorded rather than hidden: "recently" is always relative to the repository's
latest commit, so an abandoned repository is judged on its own clock, not the audit machine's.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.rules.checks._common import _indent
from audit.scan import Inventory
from audit.stack import Stack
from audit.rules.payloads import Payload

#: A README below this many characters of trimmed text is present but not documentation.
MIN_README_CHARS = 200

#: Case-insensitive markers that make a README a stub rather than a description.
STUB_MARKERS = ("todo", "tbd", "placeholder", "lorem ipsum", "coming soon", "fill this in", "<describe")

#: Suffixes treated as documents for the presence checks that accept "any name plus a doc suffix".
_DOC_SUFFIXES = (".md", ".rst", ".txt", ".markdown", ".adoc")

#: How recent a changelog change must be, measured against the `HEAD` commit date — never wall clock.
RECENT_WINDOW = dt.timedelta(days=365)

#: CI providers that expose branch protection as configuration-as-code.
_PROTECTION_PROVIDERS = frozenset({"github", "gitlab"})

_DEPENDENCY_AUTOMATION = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    "dependabot.yml",
    "dependabot.yaml",
    "renovate.json",
    "renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".github/renovate.json",
    "renovate.config.js",
)

#: Renovate files the engine can parse with the standard library; the others count on presence.
_RENOVATE_JSON = frozenset({"renovate.json", ".renovaterc", ".renovaterc.json"})
_RENOVATE_UNPARSED = frozenset({"renovate.json5", "renovate.config.js"})

#: Stack ecosystem (or ``github`` for the CI provider) -> the Dependabot ``package-ecosystem`` values that cover it.
_DEPENDABOT_ECOSYSTEMS: dict[str, tuple[str, ...]] = {
    "node": ("npm", "bun"),
    "python": ("pip", "uv"),
    "jvm": ("maven", "gradle"),
    "go": ("gomod",),
    "rust": ("cargo",),
    "dotnet": ("nuget",),
    "ruby": ("bundler",),
    "php": ("composer",),
    "github": ("github-actions",),
}

#: The same, as Renovate manager names for ``enabledManagers``.
_RENOVATE_MANAGERS: dict[str, tuple[str, ...]] = {
    "node": ("npm", "bun"),
    "python": ("pep621", "pip_requirements", "pip_setup", "pip-compile", "pipenv", "poetry", "setuptools"),
    "jvm": ("maven", "gradle"),
    "go": ("gomod",),
    "rust": ("cargo",),
    "dotnet": ("nuget",),
    "ruby": ("bundler",),
    "php": ("composer",),
    "github": ("github-actions",),
}

#: The Dependabot entry options that the owner expects to bind security updates, and that ``target-branch`` drops.
_TRAPPED_OPTIONS = frozenset({"ignore", "groups"})


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


def _finding(
    spec,
    verdict: Verdict,
    cannot: str,
    because: str,
    *,
    evidence: list[Evidence] | None = None,
    path: str | None = None,
    remediation: str | None = None,
) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence or [],
        path=path,
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# artifact locators (all read the inventory; none touches the filesystem directly)
# ---------------------------------------------------------------------------


def _basename(rel: str) -> str:
    return rel.rsplit("/", 1)[-1]


#: The top-level directories where a repository-level file may live besides the root itself.
_REPOSITORY_LEVEL_DIRS = frozenset({".github", ".gitlab", "docs"})


def _repository_level(rel: str) -> bool:
    """Whether ``rel`` is at the root or under ``.github/``, ``.gitlab/`` or ``docs/`` (ADR-0008)."""
    return "/" not in rel or rel.split("/", 1)[0] in _REPOSITORY_LEVEL_DIRS


def _present(inventory: Inventory, *names: str) -> list[str]:
    """Repository-level files whose path equals, or ends with, one of ``names``."""
    wanted = tuple(name.strip("/") for name in names)
    return sorted(
        f.rel
        for f in inventory.files
        if _repository_level(f.rel)
        and (f.rel.strip("/") in wanted or any(f.rel.strip("/").endswith("/" + name) for name in wanted))
    )


def _named_documents(inventory: Inventory, prefixes: tuple[str, ...], *, root_only: bool = False) -> list[str]:
    """Repository-level files whose basename starts with a prefix and is a bare name or a document suffix."""
    out: list[str] = []
    for entry in inventory.files:
        if root_only and "/" in entry.rel:
            continue
        if not _repository_level(entry.rel):
            continue
        base = _basename(entry.rel).lower()
        if not any(base.startswith(prefix) for prefix in prefixes):
            continue
        if base.endswith(_DOC_SUFFIXES) or "." not in base:
            out.append(entry.rel)
    return sorted(out)


def _documents_containing(inventory: Inventory, needle: str) -> list[str]:
    return sorted(
        f.rel
        for f in inventory.files
        if _repository_level(f.rel)
        and needle in _basename(f.rel).lower()
        and _basename(f.rel).lower().endswith(_DOC_SUFFIXES)
    )


def _git_output(target_path: Path, *args: str) -> str | None:
    """Run a read-only git query. ``None`` when git is absent, fails, or the path is not a repo."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(target_path), *args],
            text=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _commit_date(target_path: Path, *pathspec: str) -> dt.datetime | None:
    """The committer date of the last commit touching ``pathspec`` (or ``HEAD``)."""
    raw = _git_output(target_path, "log", "-1", "--format=%cI", *pathspec)
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


# ===========================================================================
# HYG-01 — README present and non-placeholder
# ===========================================================================


def _readme_reason(text: str) -> str | None:
    stripped = text.strip()
    if len(stripped) < MIN_README_CHARS:
        return f"only {len(stripped)} characters (minimum {MIN_README_CHARS})"
    lowered = stripped.lower()
    for marker in STUB_MARKERS:
        if marker in lowered:
            return f"contains the placeholder marker {marker!r}"
    body = [line.strip() for line in stripped.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not body:
        return "a title with no body"
    return None


def check_hyg01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = sorted(f.rel for f in inventory.files if "/" not in f.rel and _basename(f.rel).lower().startswith("readme"))
    if not found:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no README at the repository root",
            [
                _finding(
                    spec,
                    Verdict.FAIL,
                    "orient itself in this project in seconds",
                    "no README exists at the repository root",
                    remediation="Add a root README that says what the project is, how to run it, "
                    "and how to contribute.",
                ),
            ],
        )

    primary = min(found, key=lambda rel: (0 if _basename(rel).lower() == "readme.md" else 1, rel.lower()))
    text = inventory.read(primary)
    if text is None:
        return _outcome(spec, Verdict.UNKNOWN, f"{primary} present but not readable as text (binary or oversized)")

    reason = _readme_reason(text)
    if reason is None:
        return _outcome(spec, Verdict.PASS, f"{primary} present and non-placeholder")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"{primary} is a placeholder — {reason}",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "learn what this project is",
                f"{primary} exists but is a placeholder — {reason}",
                evidence=[Evidence(primary)],
                path=primary,
                remediation="Replace the stub with a description, a quick-start, and a link to the documentation.",
            ),
        ],
    )


# ===========================================================================
# HYG-02 — CODEOWNERS
# ===========================================================================


def check_hyg02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _present(inventory, "CODEOWNERS")
    if found:
        return _outcome(spec, Verdict.PASS, f"CODEOWNERS present at {', '.join(found[:3])}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no CODEOWNERS file",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "know who owns a path before changing it",
                "no CODEOWNERS file exists at the root, under .github/, .gitlab/ or docs/",
                remediation="Add .github/CODEOWNERS mapping paths to owners so review routing is machine-readable.",
            ),
        ],
    )


# ===========================================================================
# HYG-03 — pull-request template
# ===========================================================================


def check_hyg03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = sorted(
        f.rel
        for f in inventory.files
        if _repository_level(f.rel) and _basename(f.rel).lower().startswith("pull_request_template")
    )
    if found:
        return _outcome(spec, Verdict.PASS, f"pull-request template present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no pull-request template",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "file a change with the information reviewers need",
                "no .github/pull_request_template file exists",
                remediation="Add .github/pull_request_template.md describing what a good change records.",
            ),
        ],
    )


# ===========================================================================
# HYG-04 — issue templates
# ===========================================================================


def check_hyg04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = sorted(
        f.rel
        for f in inventory.files
        if f.rel.startswith(".github/ISSUE_TEMPLATE/") or f.rel == ".github/ISSUE_TEMPLATE.md"
    )
    if found:
        return _outcome(spec, Verdict.PASS, f"{len(found)} issue template(s) present")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no issue templates",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "report a bug or request in a structured way",
                "no .github/ISSUE_TEMPLATE entry exists",
                remediation="Add at least one file under .github/ISSUE_TEMPLATE/ (a bug report "
                "and a feature request are a good start).",
            ),
        ],
    )


# ===========================================================================
# HYG-05 — CONTRIBUTING
# ===========================================================================


def check_hyg05(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("contributing",))
    if found:
        return _outcome(spec, Verdict.PASS, f"CONTRIBUTING present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no CONTRIBUTING document",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "contribute without reverse-engineering the process",
                "no CONTRIBUTING document exists",
                remediation="Add CONTRIBUTING.md covering setup, the gate, and the review flow.",
            ),
        ],
    )


# ===========================================================================
# HYG-06 — SECURITY
# ===========================================================================


def check_hyg06(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("security",))
    if found:
        return _outcome(spec, Verdict.PASS, f"SECURITY present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no SECURITY document",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "report a vulnerability responsibly",
                "no SECURITY document exists at the root, under .github/, .gitlab/ or docs/",
                remediation="Add SECURITY.md with a private disclosure channel and a response expectation.",
            ),
        ],
    )


# ===========================================================================
# HYG-07 — CHANGELOG present and recent
# ===========================================================================


def check_hyg07(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("changelog", "changes", "history"))
    if not found:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no CHANGELOG document",
            [
                _finding(
                    spec,
                    Verdict.FAIL,
                    "see what changed between two versions",
                    "no CHANGELOG (or CHANGES/HISTORY) document exists",
                    remediation="Add CHANGELOG.md and record notable changes under a version heading.",
                ),
            ],
        )

    primary = found[0]
    head_date = _commit_date(target.path, "HEAD")
    changelog_date = _commit_date(target.path, "--", primary)
    if head_date is None or changelog_date is None:
        return _outcome(spec, Verdict.UNKNOWN, f"{primary} present, but git could not date it against HEAD")

    age = head_date - changelog_date
    if age <= RECENT_WINDOW:
        return _outcome(spec, Verdict.PASS, f"{primary} last changed {age.days} day(s) before HEAD")

    return _outcome(
        spec,
        Verdict.FAIL,
        f"{primary} last changed {age.days} day(s) before HEAD (window {RECENT_WINDOW.days})",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "trust that the changelog reflects the current release",
                f"{primary} has not changed in {age.days} days of repository history",
                evidence=[Evidence(primary)],
                path=primary,
                remediation="Record the current release in the changelog in the same change set that cuts it.",
            ),
        ],
    )


# ===========================================================================
# HYG-08 — release document
# ===========================================================================


def check_hyg08(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _documents_containing(inventory, "release")
    if found:
        return _outcome(spec, Verdict.PASS, f"release document present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no release document",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "know how a release is cut",
                "no text or markdown document describing the release process exists",
                remediation="Add docs/releasing.md (or RELEASE.md) describing how a version is cut and published.",
            ),
        ],
    )


# ===========================================================================
# HYG-09 — dependency update automation
# ===========================================================================


@dataclass
class _UpdateEntry:
    """One item of a Dependabot ``updates:`` list: its ecosystem, its option keys and their line numbers."""

    line: int
    ecosystem: str | None = None
    keys: dict[str, int] = field(default_factory=dict)


@dataclass
class _AutomationConfig:
    """What one dependency-update file tells the check. ``covers`` is ``None`` when it covers every ecosystem."""

    path: str
    readable: bool = True
    covers: set[str] | None = None
    traps: list[_UpdateEntry] = field(default_factory=list)


def _scalar(value: str) -> str:
    value = re.sub(r"\s+#.*$", "", value).strip()
    return value.strip("\"'")


def _dependabot_entries(text: str) -> list[_UpdateEntry] | None:
    """Minimal reader for the ``updates:`` list of a Dependabot file; ``None`` when there is no such list.

    No YAML library is available (stdlib only), so this understands block style: ``- key: value`` items and
    their sibling keys. Anchors, flow-style items and multi-document files are not interpreted.
    """
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if re.match(r"^updates:\s*(#.*)?$", line))
    except StopIteration:
        return None
    entries: list[_UpdateEntry] = []
    item_indent: int | None = None
    key_indent = 0
    for number, line in enumerate(lines[start + 1 :], start=start + 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = _indent(line)
        stripped = line.strip()
        if stripped.startswith("- ") and (item_indent is None or indent == item_indent):
            item_indent = indent
            key_indent = indent + 2
            entries.append(_UpdateEntry(line=number))
            stripped = stripped[2:].strip()
            indent = key_indent
        elif item_indent is None or indent <= item_indent:
            break
        key = re.match(r"^([A-Za-z0-9_-]+):(.*)$", stripped)
        if entries and key and indent == key_indent:
            name, value = key.group(1), key.group(2)
            entries[-1].keys.setdefault(name, number)
            if name == "package-ecosystem":
                entries[-1].ecosystem = _scalar(value)
    return entries


def _read_dependabot(rel: str, text: str | None) -> _AutomationConfig:
    entries = _dependabot_entries(text or "")
    if entries is None:
        return _AutomationConfig(rel, readable=False, covers=set())
    named = {entry.ecosystem for entry in entries if entry.ecosystem}
    covers = {eco for eco, accepted in _DEPENDABOT_ECOSYSTEMS.items() if named & set(accepted)}
    traps = [entry for entry in entries if "target-branch" in entry.keys and _TRAPPED_OPTIONS & set(entry.keys)]
    return _AutomationConfig(rel, covers=covers, traps=traps)


def _read_renovate(rel: str, text: str | None) -> _AutomationConfig:
    if _basename(rel) in _RENOVATE_UNPARSED:
        return _AutomationConfig(rel)
    try:
        config = json.loads(text or "")
    except ValueError:
        return _AutomationConfig(rel, readable=False, covers=set())
    if not isinstance(config, dict):
        return _AutomationConfig(rel, readable=False, covers=set())
    enabled = config.get("enabledManagers")
    if not isinstance(enabled, list):
        return _AutomationConfig(rel)
    names = {str(name) for name in enabled}
    return _AutomationConfig(rel, covers={eco for eco, accepted in _RENOVATE_MANAGERS.items() if names & set(accepted)})


def _required_coverage(stack: Stack) -> set[str]:
    """The ecosystems a dependency-update policy must reach: those a manifest names, plus GitHub Actions."""
    required = {eco for eco in stack.ecosystems - stack.source_only if eco in _DEPENDABOT_ECOSYSTEMS}
    if "github" in stack.ci_providers:
        required.add("github")
    return required


def _coverage_label(eco: str) -> str:
    return "github-actions" if eco == "github" else eco


def check_hyg09(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _present(inventory, *_DEPENDENCY_AUTOMATION)
    if not found:
        return _outcome(
            spec,
            Verdict.FAIL,
            "no dependency update automation",
            [
                _finding(
                    spec,
                    Verdict.FAIL,
                    "keep dependencies patched without manual sweeps",
                    "no Dependabot or Renovate configuration exists",
                    remediation="Add .github/dependabot.yml (or renovate.json) with an update schedule.",
                ),
            ],
        )

    configs = [
        _read_renovate(rel, inventory.read(rel)) if "renovate" in rel else _read_dependabot(rel, inventory.read(rel))
        for rel in found
    ]
    required = _required_coverage(stack)
    covered: set[str] = set()
    for config in configs:
        covered |= required if config.covers is None else config.covers
    missing = sorted(required - covered)
    unreadable = [config.path for config in configs if not config.readable]

    findings = [
        _finding(
            spec,
            Verdict.PARTIAL,
            "rely on the update policy reaching security updates",
            f"the `{entry.ecosystem or 'unnamed'}` entry sets `target-branch` together with "
            f"`{'`, `'.join(sorted(_TRAPPED_OPTIONS & set(entry.keys)))}`, and Dependabot drops those options for "
            "security updates, which always go to the default branch",
            evidence=[Evidence(config.path, line=entry.keys["target-branch"], note="target-branch")],
            path=f"{config.path}:{entry.keys['target-branch']}",
            remediation="Remove `target-branch` when it names the default branch; otherwise make that branch the "
            "default, so the entry's options apply to security updates too.",
        )
        for config in configs
        for entry in config.traps
    ]
    if missing and not unreadable:
        labels = ", ".join(_coverage_label(eco) for eco in missing)
        accepted = "; ".join(f"{_coverage_label(eco)}: {' or '.join(_DEPENDABOT_ECOSYSTEMS[eco])}" for eco in missing)
        findings.append(
            _finding(
                spec,
                Verdict.PARTIAL,
                "keep every ecosystem's dependencies under the update policy",
                f"the dependency-update configuration has no entry for {labels}",
                evidence=[Evidence(config.path) for config in configs],
                path=configs[0].path,
                remediation=f"Add an update entry for each detected ecosystem (Dependabot `package-ecosystem` "
                f"{accepted}), or the matching Renovate manager to `enabledManagers`.",
            )
        )
    if findings:
        return _outcome(
            spec, Verdict.PARTIAL, f"dependency automation at {found[0]} has {len(findings)} defect(s)", findings
        )
    if missing or len(unreadable) == len(configs):
        return _outcome(
            spec,
            Verdict.UNKNOWN,
            f"dependency automation at {', '.join(unreadable)} could not be read; coverage is not settled",
        )
    reach = ", ".join(_coverage_label(eco) for eco in sorted(required)) or "no ecosystem with a manifest"
    return _outcome(spec, Verdict.PASS, f"dependency automation configured at {found[0]}; covers {reach}")


# ===========================================================================
# HYG-10 — license
# ===========================================================================


def check_hyg10(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    found = _named_documents(inventory, ("license", "licence", "copying", "copyright", "unlicense"), root_only=True)
    if found:
        return _outcome(spec, Verdict.PASS, f"license present at {found[0]}")
    return _outcome(
        spec,
        Verdict.FAIL,
        "no license file at the repository root",
        [
            _finding(
                spec,
                Verdict.FAIL,
                "know the terms under which the code may be used",
                "no LICENSE (or COPYING) file exists at the repository root",
                remediation="Add a LICENSE file; choose one deliberately rather than defaulting "
                "to all rights reserved.",
            ),
        ],
    )


# ===========================================================================
# HYG-11 — branch protection declared as code
# ===========================================================================


def _branch_protection_config(inventory: Inventory) -> list[str]:
    named = [
        f.rel for f in inventory.files if "branch-protection" in f.rel.lower() or "branch_protection" in f.rel.lower()
    ]
    terraform = sorted(
        rel for rel in inventory.with_suffix(".tf") if "branch_protection" in (inventory.read(rel) or "").lower()
    )
    return sorted(set(named) | set(terraform))


def check_hyg11(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    config = _branch_protection_config(inventory)
    if config:
        return _outcome(spec, Verdict.PASS, f"branch protection declared as code at {config[0]}")

    recognised = sorted(_PROTECTION_PROVIDERS & set(stack.ci_providers))
    if recognised:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"{', '.join(recognised)} offers branch protection as code, none found",
            [
                _finding(
                    spec,
                    Verdict.FAIL,
                    "reproduce the protected-branch rules as code",
                    f"the {', '.join(recognised)} provider is detected but no branch-protection configuration exists",
                    remediation="Declare branch protection in code (a Terraform resource or "
                    ".github/branch-protection) so it is reviewed like any other "
                    "change.",
                ),
            ],
        )

    return _outcome(
        spec,
        Verdict.UNKNOWN,
        "no CI provider recognised; whether branch protection can be declared as code is provider-dependent",
    )


IMPLEMENTATIONS = {
    "HYG-01": check_hyg01,
    "HYG-02": check_hyg02,
    "HYG-03": check_hyg03,
    "HYG-04": check_hyg04,
    "HYG-05": check_hyg05,
    "HYG-06": check_hyg06,
    "HYG-07": check_hyg07,
    "HYG-08": check_hyg08,
    "HYG-09": check_hyg09,
    "HYG-10": check_hyg10,
    "HYG-11": check_hyg11,
}
