# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""CON-04: Draft allow/deny emitted."""

from __future__ import annotations

from itertools import accumulate
from pathlib import Path

from audit.evaluate import CheckOutcome
from audit.findings import Severity, Verdict
from audit.rules.spec import declare
from audit.scan import Inventory, Kind
from audit.target import Target
from audit.rules.checks.con._shared import _TEST_DIR_NAMES, _names_directory, _outcome, _unknown

SPEC = declare(
    "CON-04",
    "Draft allow/deny emitted",
    "—",
    Severity.COSMETIC,
    scored=False,
    status="planned",
    rule="Emitter, not a check: writes a draft list from the scan.",
)


#: The draft artifact CON-04 writes, beside the report under ``--out``: a Markdown list to paste under the
#: prohibitions heading of the instruction file (decision 0001).
DRAFT_FILENAME = "do-not-do.draft.md"

# ---------------------------------------------------------------------------
# CON-04 emit target, configured once per process by the CLI before evaluation
# ---------------------------------------------------------------------------

_EMIT_TARGET: Path | None = None
_EMIT_FORCE = False


def draft_path(target: Target, out_path: Path) -> Path | None:
    """Where the draft goes for a run whose report is ``out_path``: beside it, and never inside the target (``None``)."""
    out_dir = out_path.parent
    try:
        out_dir.resolve().relative_to(target.path.resolve())
    except ValueError:
        return out_dir / DRAFT_FILENAME
    return None


def set_emit_target(out_path: Path | None, *, force: bool = False) -> None:
    """Record where the emitter may write for this run, and whether it may replace a draft; ``None`` disables it.

    Called by ``audit.cli`` before checks run, from the same ``--out`` resolution the report
    writer uses. It is the only module state in the pack, it is set once per process, and it is
    reset on every scan so a long-lived process cannot inherit a previous run's target.
    """
    global _EMIT_TARGET, _EMIT_FORCE
    _EMIT_TARGET = out_path
    _EMIT_FORCE = force


# ===========================================================================
# CON-04 — draft deny-list emitter (not scored)
# ===========================================================================

#: Canonical deny patterns per draft section. Emitted verbatim so the draft is useful even where the
#: scan observed no instance of a category.
_DRAFT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "secrets",
        (".aws/*", ".env", ".env.*", "id_rsa*", "*.cer", "*.crt", "*.key", "*.keystore", "*.p12", "*.pem", "*.pfx"),
    ),
    (
        "migrations",
        (
            "alembic/versions/",
            "db/migrate/",
            "flyway/",
            "liquibase/",
            "migration/",
            "migrations/",
            "prisma/migrations/",
        ),
    ),
    (
        "generated",
        ("build/", "dist/", "generated/", "vendor/", "*.designer.cs", "*.g.cs", "*.min.css", "*.min.js", "*.pb.go"),
    ),
    ("tests", ("__tests__/", "test/", "tests/")),
    ("iac", ("*.tf", "*.tf.json", "*.tfstate", "*.tfvars", "ansible/", "charts/", "helm/", "k8s/", "kubernetes/")),
    ("production", ("**/prod/**", "**/production/**", "environments/prod/", "environments/production/")),
)

_GENERATED_DIRS: frozenset[str] = frozenset({"build", "dist", "generated", "vendor"})
_IAC_DIRS: frozenset[str] = frozenset({"ansible", "charts", "helm", "k8s", "kubernetes"})
_MIGRATION_DIRS: frozenset[str] = frozenset({"migration", "migrations"})


def _is_secret_path(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    if base == ".env" or base.startswith(".env.") or base.startswith("id_rsa"):
        return True
    if base.endswith((".cer", ".crt", ".key", ".keystore", ".p12", ".pem", ".pfx")):
        return True
    return rel.startswith(".aws/")


def _is_generated_path(entry) -> bool:
    if entry.kind is Kind.GENERATED:
        return True
    base = entry.rel.rsplit("/", 1)[-1]
    if base.endswith((".designer.cs", ".g.cs", ".min.css", ".min.js", ".pb.go")):
        return True
    return any(part in _GENERATED_DIRS for part in entry.rel.split("/")[:-1])


def _is_migration_path(rel: str) -> bool:
    parts = rel.split("/")
    if any(part in _MIGRATION_DIRS for part in parts[:-1]):
        return True
    return rel.startswith(("alembic/versions/", "prisma/migrations/", "db/migrate/"))


def _is_iac_path(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    if base.endswith((".tf", ".tfvars", ".tfstate")) or base.endswith(".tf.json"):
        return True
    return any(part in _IAC_DIRS for part in rel.split("/")[:-1])


def _is_production_path(rel: str) -> bool:
    return any(part.lower() in {"prod", "production"} for part in rel.split("/")[:-1])


def _is_test_path(entry) -> bool:
    return any(part in _TEST_DIR_NAMES for part in entry.rel.split("/")[:-1])


_DRAFT_MATCHERS = {
    "secrets": lambda entry: _is_secret_path(entry.rel),
    "migrations": lambda entry: _is_migration_path(entry.rel),
    "generated": _is_generated_path,
    "tests": _is_test_path,
    "iac": lambda entry: _is_iac_path(entry.rel),
    "production": lambda entry: _is_production_path(entry.rel),
}


#: What each draft entry says an agent must not do, by category. The paths follow in code spans, because a path
#: counts as named in the prohibitions section when it stands in one.
_DRAFT_OPENINGS: dict[str, str] = {
    "secrets": "Never read, edit or commit a secret or a credential",
    "migrations": "Never edit or rewrite a database migration",
    "generated": "Never hand-edit a generated, built or vendored file",
    "tests": "Never edit, skip or delete a test to make a failing test pass",
    "iac": "Never change infrastructure as code without a review",
    "production": "Never change a production configuration or manifest without a review",
}

#: The directory names that make a path belong to a category, so that an observed path is listed as its directory.
_CATEGORY_DIRS: dict[str, frozenset[str]] = {
    "migrations": _MIGRATION_DIRS,
    "generated": _GENERATED_DIRS,
    "tests": _TEST_DIR_NAMES,
    "iac": _IAC_DIRS,
    "production": frozenset({"prod", "production"}),
}


def _observed_entry(category: str, rel: str) -> str:
    """The path to list for an observed file: its directory, from the root down to the one that made it belong."""
    parts = rel.split("/")
    for index, part in enumerate(parts[:-1]):
        if part.lower() in _CATEGORY_DIRS.get(category, frozenset()):
            return "/".join(parts[: index + 1]) + "/"
    return rel


def _covered_by_another(entry: str, entries: list[str]) -> bool:
    """Whether another entry already covers ``entry``, itself or a directory above it."""
    above = list(accumulate(entry.rstrip("/").split("/"), lambda parent, name: f"{parent}/{name}"))
    return any(other != entry and any(_names_directory(rel, other) for rel in above) for other in entries)


def build_do_not_do_draft(inventory: Inventory) -> str:
    """The Markdown draft of the prohibitions list (CON-04): one entry for each category, paths in code spans.

    Sections are fixed and entries are sorted, so the same target always yields the same bytes. An observed
    path is listed only when no other entry covers it, so the list stays as short as what it names.
    """
    lines = [
        "<!-- Generated by python-agentic-audit (CON-04). A DRAFT: review every line before you use it.",
        '     Paste the list under the prohibitions heading of AGENTS.md ("Do Not Do"), which the audit reads as',
        "     the deny list, and keep each path in a code span: a path counts as named when it stands in one.",
        "     Delete what does not apply to this repository. It is a starting point, not a conformance claim. -->",
        "",
    ]
    for name, canonical in _DRAFT_PATTERNS:
        observed = {_observed_entry(name, entry.rel) for entry in inventory.files if _DRAFT_MATCHERS[name](entry)}
        candidates = sorted(set(canonical) | {entry for entry in observed if "`" not in entry})
        entries = [entry for entry in candidates if not _covered_by_another(entry, candidates)]
        lines.append(f"- {_DRAFT_OPENINGS[name]}: " + ", ".join(f"`{entry}`" for entry in entries) + ".")
    return "\n".join(lines) + "\n"


def _write_draft(target: Target, out_path: Path, text: str, *, force: bool = False) -> Path | None:
    """Write the draft beside the report. Returns the path, or None if it would land in-target.

    An existing draft is not replaced without ``force``; ``FileExistsError`` says so. ``audit.cli`` has already
    refused such a run, so this is the second line of defence for a caller that did not go through it.
    """
    path = draft_path(target, out_path)
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise FileExistsError(str(path))
    path.write_text(text, encoding="utf-8")
    return path


def check_con04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if _EMIT_TARGET is None:
        return _unknown(spec, f"draft not emitted; pass --emit-baseline to write {DRAFT_FILENAME} beside the report")

    draft = build_do_not_do_draft(inventory)
    try:
        written = _write_draft(target, _EMIT_TARGET, draft, force=_EMIT_FORCE)
    except FileExistsError as exc:
        return _unknown(spec, f"refusing to replace {exc}; pass --force to overwrite")
    if written is None:
        return _unknown(
            spec, f"refusing to emit inside the target ({_EMIT_TARGET.parent}); pass an --out outside the repository"
        )

    return _outcome(spec, Verdict.PASS, f"draft deny list written: {written}")
