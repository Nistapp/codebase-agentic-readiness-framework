# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""`CON` pack — constraints.

Anchor: `brownfield-legacy/Phased-Approach.md` § Key Deliverables ("Allow/deny lists").

Implemented here: `CON-01`, `CON-02`, `CON-03`, and the `CON-04` emitter.

The framework requires initial allow/deny lists as a Phase-1 deliverable, and the spec names the artifact: the
prohibitions section of the instruction file (decision 0001, ``spec/decisions/0001-constraint-artifact.md``).
`CON-01` and `CON-02` read it through ``_common.prohibitions_section``; a path or a pattern is *named* when it
stands in a code span of the section.

What each check reads and what makes it `UNKNOWN` rather than `FAIL`:

* **CON-01** — *the deny list names paths*. The section names at least one path or pattern that matches a file
  or directory of the repository ⇒ `PASS`. It names paths and none of them matches anything ⇒ `PARTIAL`. It
  names no path or pattern ⇒ `FAIL`. No instruction file or no prohibitions section ⇒ `UNKNOWN` (`AGT-01` and
  `AGT-07` report that once). A code span is a path or pattern when it has no command syntax and holds a slash,
  a glob or a dot, or is a bare word that exists; ``git push --force`` and ``main`` are not paths. A literal
  path is also looked for on disk, because the scan leaves out ``node_modules/`` and the like, which a deny
  list often names.
* **CON-02** — *test directories protected*. Reads the prohibitions section of the entry instruction file
  (``_common.prohibitions_section``; decision 0001, ``spec/decisions/0001-constraint-artifact.md``): a test
  directory is protected when the section names it, or a pattern that covers it, in a code span. Test
  directories are located from the scan (a directory segment named ``test``/``tests``/``__tests__``; ``spec``
  and ``specs`` hold feature specifications, not tests) plus the filesystem. The section names every one ⇒
  `PASS`; some ⇒ `PARTIAL`; none ⇒ `FAIL`. No instruction file or no prohibitions section ⇒ `UNKNOWN`, since
  `AGT-01` and `AGT-07` report that once and the check does not pile on, and so is a repository with no test
  directory. Constraint files, ignore rules and CI text are not read: they are not the artifact.
* **CON-03** — *`artefacts/` excluded from the index and agent reads*. Candidate roots are the
  scratch spellings (``artefacts``, ``artifacts``) and the agent/tool state directories
  (``.codebase-memory``, ``.opencode``, ``.agentic-tdd``). A root that exists is covered when an
  ignore rule matches it; a **tracked** member of any root is a `FAIL`. When the roots are covered
  but git cannot report the tracked set, the untracked half is `UNKNOWN` — never inferred — while
  the rule-coverage half still evaluates (the same degradation `SEC-01`/`DOC-03` use).
* **CON-04** — the emitter, not a scored check. It returns a `CheckOutcome` like every other check,
  but it becomes `PASS` only when the operator asked for the draft with ``--emit-baseline``; without
  the flag it is `UNKNOWN`, and it is refused outright if the resolved output would land inside the
  target (ADR-0002). The draft is deterministic: fixed sections, sorted entries.

CON-04's output location is a contract choice not yet ratified by the framework (the framework
defines no artifact contract — see CON-01). The least-surprising option is taken: the same ``--out``
directory the report is written to, gated by the already-reserved ``--emit-baseline`` flag, with the
filename the remediation how-to already names (``docs/how-to/hand-findings-to-remediation.md``).
The emitter writes to a module-level target set by the CLI before the scan; nothing else reads it.

Deliberate limits, recorded rather than hidden. Ignore matching (``CON-03``) is the documented subset in
``audit.ignore`` (anchoring and ``**`` approximated). The prohibitions section is prose, so ``CON-02`` is a
heuristic: a path written without backticks is not seen, and a pattern is read like an ignore entry (a
leading ``/`` anchors it, a leading ``**/`` is any depth, one with no inner slash names a directory of that
name at any depth, ``fnmatch`` globs). Test-directory discovery is directory-based; a suite laid out as
loose ``*_test.py`` files with no test-named directory is not seen and degrades to `UNKNOWN`, and so is a
Ruby ``spec/`` directory. The emitter writes exactly one artifact (``constraints.draft.yaml``); the other S12
remediation inputs are out of scope for this pack.
"""

from __future__ import annotations

import fnmatch
import json
from itertools import accumulate
from pathlib import Path

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Verdict, statement
from audit.ignore import load_ignore_rules
from audit.rules.checks._common import entry_instruction_file, prohibitions_section, tracked_in_scope
from audit.scan import Inventory, Kind
from audit.target import Target
from audit.rules.payloads import PathList, Payload

#: Directory names that make a directory a test directory. `spec` and `specs` are not among them: the framework's own
#: `specs/` folder holds feature specifications (spec-driven development), not tests, so a repository that follows
#: it has no test directory there to protect.
_TEST_DIR_NAMES: frozenset[str] = frozenset({"test", "tests", "__tests__"})

#: Scratch spellings and agent/tool state directories CON-03 requires to be ignored.
_SCRATCH_ROOTS: tuple[str, ...] = ("artefacts", "artifacts")
_STATE_ROOTS: tuple[str, ...] = (".codebase-memory", ".opencode", ".agentic-tdd")
_CON_ROOTS: tuple[str, ...] = _SCRATCH_ROOTS + _STATE_ROOTS

#: The draft artifact CON-04 writes, beside the report under ``--out``.
DRAFT_FILENAME = "constraints.draft.yaml"

# ---------------------------------------------------------------------------
# CON-04 emit target, configured once per process by the CLI before evaluation
# ---------------------------------------------------------------------------

_EMIT_TARGET: Path | None = None


def set_emit_target(out_path: Path | None) -> None:
    """Record where the emitter may write for this run; ``None`` disables it.

    Called by ``audit.cli`` before checks run, from the same ``--out`` resolution the report
    writer uses. It is the only module state in the pack, it is set once per process, and it is
    reset on every scan so a long-lived process cannot inherit a previous run's target.
    """
    global _EMIT_TARGET
    _EMIT_TARGET = out_path


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


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


def _unknown(spec, reason: str, data: Payload | None = None) -> CheckOutcome:
    return _outcome(spec, Verdict.UNKNOWN, reason, data=data)


def _finding(spec, cannot: str, because: str, verdict: Verdict, evidence: list[Evidence], remediation: str) -> Finding:
    return Finding(
        check=spec.id,
        severity=spec.severity,
        phase=spec.phase,
        verdict=verdict,
        statement=statement(cannot, because),
        evidence=evidence,
        remediation=remediation,
    )


def _pattern_covers(rel: str, pattern: str) -> bool:
    """Whether one ignore/constraint pattern covers a directory path ``rel``.

    Mirrors the documented subset: a rule may name the directory itself (``artefacts``), its glob
    (``artefacts/*``) or its descendants. Anchoring and ``**`` are not interpreted.
    """
    p = pattern.strip().rstrip("/")
    if not p:
        return False
    core = p
    for suffix in ("/*", "/**"):
        if core.endswith(suffix):
            core = core[: -len(suffix)]
    core = core.rstrip("/")
    return (
        rel == core
        or fnmatch.fnmatch(rel, p)
        or fnmatch.fnmatch(rel, core)
        or fnmatch.fnmatch(rel, core + "/*")
        or fnmatch.fnmatch(rel, core + "/**")
    )


def _covered(rel: str, patterns: list[str]) -> bool:
    return any(_pattern_covers(rel, pattern) for pattern in patterns)


def _describe(roots: list[str], limit: int = 8) -> str:
    """A bounded, deterministic rendering of a root list for details and findings."""
    shown = ", ".join(root + "/" for root in roots[:limit])
    extra = len(roots) - limit
    return f"{shown} (+{extra} more)" if extra > 0 else shown


def _test_roots(target: Target, inventory: Inventory) -> list[str]:
    """Every test directory: a filesystem root plus any directory segment named in the scan."""
    roots: set[str] = {name for name in _TEST_DIR_NAMES if (target.path / name).is_dir()}
    for entry in inventory.files:
        parts = entry.rel.split("/")
        for index, part in enumerate(parts[:-1]):
            if part in _TEST_DIR_NAMES:
                roots.add("/".join(parts[: index + 1]))
    return sorted(roots)


def _present_roots(target: Target, inventory: Inventory) -> list[str]:
    """The candidate scratch/state roots that exist, from the filesystem and from the scan."""
    present = {root for root in _CON_ROOTS if (target.path / root).is_dir()}
    present.update(entry.rel.split("/", 1)[0] for entry in inventory.files)
    return sorted(root for root in present if root in _CON_ROOTS)


# ===========================================================================
# CON-01 — the deny list names paths
# ===========================================================================

_GLOB_CHARS = "*?["
#: A code span with one of these in it is a command, a flag or an expression, not a path.
_NOT_A_PATH_CHARS = frozenset(" \t$|;&<>()'\"=")


def _path_like(span: str) -> bool:
    """Whether a code span reads as a path or a pattern: no command syntax, and a slash, a glob or a dot in it."""
    if not span or span.startswith("-") or any(char in _NOT_A_PATH_CHARS for char in span):
        return False
    return "/" in span or any(char in span for char in _GLOB_CHARS) or "." in span


def _repository_paths(inventory: Inventory) -> list[str]:
    """Every file of the scan and every directory above one, as paths from the root."""
    paths: set[str] = set()
    for entry in inventory.files:
        paths.update(accumulate(entry.rel.split("/"), lambda above, name: f"{above}/{name}"))
    return sorted(paths)


def _exists_in_repository(span: str, target: Target, paths: list[str]) -> bool:
    """Whether the path or pattern matches a file or directory of the repository.

    The scan leaves out what an ignore rule or the hard excludes name (``node_modules/``, ``dist/``), and those
    are the paths a deny list most often names, so a literal path is also looked for on disk.
    """
    if any(_names_directory(rel, span) for rel in paths):
        return True
    core, _anchored, _anywhere = _split_pattern(span)
    return bool(core) and not any(char in core for char in _GLOB_CHARS) and (target.path / core).exists()


def _listed(items: list[str], limit: int = 8) -> str:
    shown = ", ".join(items[:limit])
    extra = len(items) - limit
    return f"{shown} (+{extra} more)" if extra > 0 else shown


def check_con01(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")
    section = prohibitions_section(text)
    if section is None:
        return _unknown(spec, f"{name} has no prohibitions section to read; AGT-07 owns that finding")

    paths = _repository_paths(inventory)
    named: list[tuple[int, str]] = []
    for line, span in section.code_spans():
        if (line, span) not in named and (_path_like(span) or _exists_in_repository(span, target, paths)):
            named.append((line, span))
    names = [span for _line, span in named]
    present = [span for span in dict.fromkeys(names) if _exists_in_repository(span, target, paths)]
    data = PathList(paths=tuple(dict.fromkeys(names)))

    if present:
        return _outcome(
            spec,
            Verdict.PASS,
            f"the prohibitions section of {name} names paths that exist: {_listed(present)}",
            data=data,
        )
    if named:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"the prohibitions section of {name} names {_listed(list(dict.fromkeys(names)))}, and none of it matches "
            "a file or directory of the repository",
            [
                _finding(
                    spec,
                    "trust the deny list to bound what an agent may change",
                    f"none of the paths the prohibitions section of {name} names "
                    f"({_listed(list(dict.fromkeys(names)))}) matches a file or directory of this repository",
                    Verdict.PARTIAL,
                    [Evidence(name, line=line, note=span) for line, span in named[:12]],
                    "Name paths that exist in this repository, or patterns that match some of it, in code spans "
                    f"in the prohibitions section of {name}.",
                )
            ],
            data=data,
        )
    return _outcome(
        spec,
        Verdict.FAIL,
        f"the prohibitions section of {name} names no path or pattern",
        [
            _finding(
                spec,
                "trust the deny list to bound what an agent may change",
                f"the prohibitions section of {name} names no path or pattern in a code span",
                Verdict.FAIL,
                [Evidence(name, line=section.first_line, note=section.headings[0])],
                "Name each path an agent must not change in a code span in the prohibitions section, for example "
                "`dist/`, `tests/` and `.env`.",
            )
        ],
        data=data,
    )


# ===========================================================================
# CON-02 — test directories protected
# ===========================================================================


def _split_pattern(pattern: str) -> tuple[str, bool, bool]:
    """``(core, anchored, anywhere)`` of a path or pattern named in the prohibitions section.

    A leading ``/`` anchors it to the repository root, a leading ``**/`` lets it start at any depth, and a
    trailing ``/``, ``/*`` or ``/**`` only says that the path is a directory. What is left is the ``core``.
    """
    core = pattern.strip()
    anchored = core.startswith("/")
    core = core.lstrip("/")
    anywhere = core.startswith("**/")
    if anywhere:
        core = core[3:]
    changed = True
    while changed:
        changed = False
        for suffix in ("/**", "/*", "/"):
            if core.endswith(suffix):
                core = core[: -len(suffix)]
                changed = True
    return core, anchored, anywhere


def _names_directory(rel: str, pattern: str) -> bool:
    """Whether a path or pattern named in the prohibitions section covers the path ``rel``.

    Read as an ignore entry is: anchored by a leading ``/``, at any depth after ``**/``, and, with no slash
    inside it, naming a path of that name at any depth, so ``tests/`` covers ``tests`` and
    ``packages/api/tests``. A path covers every path under it. A glob is matched with ``fnmatch``.
    """
    core, anchored, anywhere = _split_pattern(pattern)
    if not core:
        return False
    if fnmatch.fnmatch(rel, core) or fnmatch.fnmatch(rel, core + "/*"):
        return True
    if anchored:
        return False
    if anywhere:
        return fnmatch.fnmatch(rel, "*/" + core) or fnmatch.fnmatch(rel, core)
    return fnmatch.fnmatch(rel.split("/")[-1], core)


def check_con02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    name, text = entry_instruction_file(inventory)
    if not text:
        return _unknown(spec, "no instruction file to read; AGT-01 owns that finding")
    section = prohibitions_section(text)
    if section is None:
        return _unknown(spec, f"{name} has no prohibitions section to read; AGT-07 owns that finding")

    test_roots = _test_roots(target, inventory)
    if not test_roots:
        return _unknown(spec, "no test directories detected, so there is nothing for a deny list to protect")

    named = [span for _line, span in section.code_spans()]
    covered = [root for root in test_roots if any(_names_directory(root, pattern) for pattern in named)]
    uncovered = [root for root in test_roots if root not in covered]
    listed = _describe(test_roots)
    paths = PathList(paths=tuple(test_roots))
    evidence = [Evidence(name, line=section.first_line, note=section.headings[0])]

    if not uncovered:
        return _outcome(
            spec,
            Verdict.PASS,
            f"the prohibitions section of {name} names the test directories ({listed})",
            data=paths,
        )
    if covered:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"the prohibitions section covers {_describe(covered)} but not {_describe(uncovered)}",
            [
                _finding(
                    spec,
                    "rely on the deny list to keep test directories out of an agent's reach",
                    f"the prohibitions section of {name} does not name {_describe(uncovered)}",
                    Verdict.PARTIAL,
                    evidence,
                    f"Name {_describe(uncovered)} in a code span in the prohibitions section of {name}.",
                )
            ],
            data=paths,
        )
    return _outcome(
        spec,
        Verdict.FAIL,
        f"the prohibitions section names none of the test directories ({listed})",
        [
            _finding(
                spec,
                "trust that a failing test is not rewritten to pass",
                f"the prohibitions section of {name} does not name any test directory",
                Verdict.FAIL,
                evidence,
                f"Name {listed} in a code span in the prohibitions section of {name}, so test edits are bounded and "
                "reviewed.",
            )
        ],
        data=paths,
    )


# ===========================================================================
# CON-03 — artefacts/ and agent state excluded from index and reads
# ===========================================================================


def check_con03(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    tracked = tracked_in_scope(target, inventory)
    tracked_members = sorted(rel for rel in (tracked or set()) if rel.split("/", 1)[0] in _CON_ROOTS)

    if tracked_members:
        roots = sorted({rel.split("/", 1)[0] for rel in tracked_members})
        return _outcome(
            spec,
            Verdict.FAIL,
            f"tracked: {', '.join(tracked_members[:8])}",
            [
                _finding(
                    spec,
                    "treat scratch and agent-state directories as transient",
                    f"{len(tracked_members)} path(s) under {', '.join(roots)}/ are tracked by git",
                    Verdict.FAIL,
                    [Evidence(rel) for rel in tracked_members[:12]],
                    "Untrack the contents (git rm --cached) — an ignore rule only keeps future files out.",
                )
            ],
        )

    present = _present_roots(target, inventory)
    if not present:
        return _outcome(spec, Verdict.PASS, "no scratch or agent-state directory in use")

    rules = load_ignore_rules(target.path)
    patterns = [rule.pattern for rule in rules]
    covered = [root for root in present if _covered(root, patterns)]
    uncovered = [root for root in present if not _covered(root, patterns)]

    if uncovered and not covered:
        return _outcome(
            spec,
            Verdict.FAIL,
            f"{', '.join(root + '/' for root in uncovered)} present but matched by no ignore rule",
            [
                _finding(
                    spec,
                    "keep scratch and agent-state directories out of the index and out of reads",
                    f"{', '.join(root + '/' for root in uncovered)} exists but no ignore rule covers it",
                    Verdict.FAIL,
                    [Evidence(root + "/") for root in uncovered],
                    f"Add {', '.join(root + '/' for root in uncovered)} to .gitignore so agents and the "
                    f"index do not read transient state as source of truth.",
                )
            ],
        )

    if uncovered:
        return _outcome(
            spec,
            Verdict.PARTIAL,
            f"ignore rules cover {', '.join(root + '/' for root in covered)} but not "
            f"{', '.join(root + '/' for root in uncovered)}",
            [
                _finding(
                    spec,
                    "keep every scratch and agent-state directory out of the index and reads",
                    f"ignore rules do not cover {', '.join(root + '/' for root in uncovered)}",
                    Verdict.PARTIAL,
                    [Evidence(root + "/") for root in uncovered],
                    f"Add {', '.join(root + '/' for root in uncovered)} to .gitignore.",
                )
            ],
        )

    if tracked is None:
        covered_list = ", ".join(root + "/" for root in covered)
        return _unknown(spec, f"ignore rules cover {covered_list}, but git could not report the tracked set")

    return _outcome(spec, Verdict.PASS, f"{', '.join(root + '/' for root in covered)} present, ignored, and untracked")


# ===========================================================================
# CON-04 — draft allow/deny emitter (not scored)
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


def _allow_roots(inventory: Inventory) -> list[str]:
    """Top-level roots that hold no denied path: the draft's read-allowed surface."""
    denied: set[str] = set()
    for entry in inventory.files:
        if any(matcher(entry) for matcher in _DRAFT_MATCHERS.values()):
            denied.add(entry.rel.split("/", 1)[0])
    roots = {entry.rel.split("/", 1)[0] for entry in inventory.files if "/" in entry.rel}
    return [
        f"{root}/"
        for root in sorted(roots)
        if not root.startswith(".") and root not in denied and root != "node_modules"
    ]


def build_constraint_draft(inventory: Inventory) -> str:
    """The deterministic YAML text of the draft allow/deny list (CON-04).

    Sections are fixed and entries are sorted, so the same target always yields the same bytes.
    """
    lines = [
        "# Generated by python-agentic-audit (CON-04) — DRAFT, review before use.",
        "# The readiness framework defines no schema for allow/deny lists; this is a",
        "# starting point derived deterministically from the scan. Treat it as reviewed",
        "# infrastructure, not a conformance claim.",
        "version: 1",
        "deny:",
    ]
    for name, canonical in _DRAFT_PATTERNS:
        observed = [entry.rel for entry in inventory.files if _DRAFT_MATCHERS[name](entry)]
        entries = sorted(set(canonical) | set(observed))
        lines.append(f"  {name}:")
        lines.extend(f"    - {json.dumps(entry)}" for entry in entries)

    lines.append("allow:")
    allow = _allow_roots(inventory)
    if allow:
        lines.extend(f"  - {json.dumps(entry)}" for entry in allow)
    else:
        lines.append("  []")
    return "\n".join(lines) + "\n"


def _write_constraint_draft(target: Target, out_path: Path, text: str) -> Path | None:
    """Write the draft beside the report. Returns the path, or None if it would land in-target."""
    out_dir = out_path.parent
    try:
        out_dir.resolve().relative_to(target.path.resolve())
    except ValueError:
        pass
    else:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / DRAFT_FILENAME
    path.write_text(text, encoding="utf-8")
    return path


def check_con04(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    if _EMIT_TARGET is None:
        return _unknown(spec, f"draft not emitted; pass --emit-baseline to write {DRAFT_FILENAME} beside the report")

    draft = build_constraint_draft(inventory)
    written = _write_constraint_draft(target, _EMIT_TARGET, draft)
    if written is None:
        return _unknown(
            spec, f"refusing to emit inside the target ({_EMIT_TARGET.parent}); pass an --out outside the repository"
        )

    return _outcome(spec, Verdict.PASS, f"draft allow/deny list written: {written}")


IMPLEMENTATIONS = {
    "CON-01": check_con01,
    "CON-02": check_con02,
    "CON-03": check_con03,
    "CON-04": check_con04,
}
