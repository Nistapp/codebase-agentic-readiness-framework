# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""SEC-02: No key-shaped strings in tracked files."""

from __future__ import annotations

import re

from audit.evaluate import CheckOutcome
from audit.findings import Evidence, Finding, Severity, Verdict, statement
from audit.rules.spec import declare
from audit.rules.checks._common import tracked_in_scope
from audit.rules.checks._secret_allowlist import SecretAllowlist, load_secret_allowlist
from audit.probes import REDACTION_PATTERNS
from audit.scan import Inventory
from audit.rules.payloads import CredentialFile, CredentialMatrix
from audit.rules.checks.sec._shared import _MAX_SECRET_FILES, _is_template_file, _outcome

SPEC = declare("SEC-02", "No key-shaped strings in tracked files", "B", Severity.BLOCKER)


#: Values that are obviously not a secret, so a documentation line quoting a shape does not fire.
_PLACEHOLDER_RE = re.compile(
    r"(?i)<[^>]+>|your[_-]|xxx+|changeme|change[_-]?me|replace|example|placeholder|redacted|"
    r"dummy|fake|todo|none|null|\.\.\."
)


# ===========================================================================
# SEC-02 — no key-shaped strings in tracked files
# ===========================================================================

#: The keyword-assignment redaction pattern is the one that can over-fire: `id-token: write` in a CI
#: workflow is a permission, not a credential. The purely shape-based patterns (sk-, ghp_, AKIA,
#: BEGIN PRIVATE KEY, Bearer) are unambiguous and always fire.
_REDACTION_KEYWORD = next(p for p in REDACTION_PATTERNS if "api" in p.pattern)
_SHAPE_PATTERNS = tuple(p for p in REDACTION_PATTERNS if p is not _REDACTION_KEYWORD)
#: SEC-02's keyword pattern reads the redaction keywords as the last part of a compound name too:
#: ``DB_PASSWORD``, ``JWT_SECRET``, ``AUTH_TOKEN``, ``SECRET_KEY`` and ``AWS_SECRET_ACCESS_KEY``, which env-style
#: files and properties files use. ``\b`` alone missed them, because ``_`` is a word character. The keyword
#: must still be what is assigned, so ``TOKEN_URL=`` and ``password.min-length=`` are not credentials.
_KEYWORD_PATTERN = re.compile(
    r"(?i)(?:\b|(?<=_))(api[_-]?key|secret|token|password|passwd|pwd)(?:[_-]?(?:access[_-]?)?key)?\s*[:=]"
)
#: A token body that says it is not a credential: ``Bearer sanity.check.invalid`` in a test that asserts a 401.
_SENTINEL_RE = re.compile(r"(?i)invalid|example|dummy|placeholder|changeme|fake|sample|bogus|redacted|notreal")
#: A badge or shield image URL. Its ``?token=`` is a public read token for the badge, not a credential.
_BADGE_URL_RE = re.compile(r"""(?i)https?://[^\s"'<>()]*(?:badge|shields\.io)[^\s"'<>()]*""")
#: The redaction Bearer shape, and the same shape with its body captured so the body can be tested for a sentinel.
_BEARER_SHAPE = next(p for p in _SHAPE_PATTERNS if "Bearer" in p.pattern)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._\-]{16,})")
#: Files whose values are plain configuration (``key=value``): a properties file and an env-style file. A short
#: password there is still a password, so the length floor drops from 12 to 6. Commented-out lines count too:
#: ``# DB_PASSWORD=...`` is a credential kept in the file.
_SHORT_VALUE_SUFFIXES = (".properties", ".env")
_MIN_SECRET_LEN = 12
_MIN_SECRET_LEN_CONFIG = 6

#: What a keyword assignment assigns: the rest of the line after ``:``, ``=`` or ``:=``.
_ASSIGNED_VALUE_RE = re.compile(r"(?::=|[:=])\s*(.*)$")
_SECRET_VALUE_CHARSET_RE = re.compile(r"[0-9A-Z]|[^A-Za-z0-9\s]")
#: A string prefix that makes the literal a plain string (raw, bytes, unicode) and one that interpolates (f).
_STRING_PREFIX_RE = re.compile(r"^([rRbBuUfF]{1,2})(?=['\"])")
#: A value that names where a secret lives and is not the secret: a variable (``$X``, ``${X}``), a template
#: (``{{ secrets.X }}``, ``<%= X %>``, ``%(X)s``), LiteLLM's ``os.environ/NAME`` or a process-environment read.
_REFERENCE_RE = re.compile(r"^(?:\$|\{\{|<%|%\(|os\.environ/|process\.env\.|env:)")

#: A file in one of these languages assigns names and expressions, so ``token = a.b(c)`` there is code. Only a
#: quoted literal in it can be a credential. Configuration, scripts and documents assign plain values, so an
#: unquoted value in them can be one.
_CODE_SUFFIXES = (
    ".py",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".scala",
    ".go",
    ".rs",
    ".rb",
    ".cs",
    ".php",
    ".swift",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
)


def _looks_secret_value(raw: str, *, in_code: bool = False, min_len: int = _MIN_SECRET_LEN) -> bool:
    """A deterministic guard for the keyword pattern: is what the keyword is assigned a credential?

    A credential is a literal. A quoted string is one unless it is a reference to a secret store or the
    environment. An unquoted value is one only in configuration, a script or a document, where it is a single
    plain token: in source code it is a name or an expression (``token = match.group(1) or x``), never a
    literal. A literal is long (``min_len`` characters or more: 12, or 6 in a properties or env-style file) and
    mixes in a capital, a digit or a symbol, which a CI permission such as ``id-token: write`` and a bare word
    are not. A literal that names itself a sentinel (``invalid``, ``dummy``, ``fake``) is not a credential.
    """
    value = raw.strip()
    prefix = _STRING_PREFIX_RE.match(value)
    if prefix:
        if "f" in prefix.group(1).lower():
            return False
        value = value[len(prefix.group(1)) :]
    quote = value[:1]
    if quote in ("'", '"'):
        end = value.find(quote, 1)
        literal = value[1 : end if end != -1 else len(value)]
    elif in_code:
        return False
    else:
        words = value.split()
        if not words:
            return False
        literal = words[0].rstrip(",;")
        if any(char in literal for char in "()[]"):
            return False
    literal = literal.strip()
    if _REFERENCE_RE.match(literal) or len(literal) < min_len or _SENTINEL_RE.search(literal):
        return False
    return bool(_SECRET_VALUE_CHARSET_RE.search(literal))


def _is_short_value_file(rel: str) -> bool:
    """A properties file or an env-style file (``.env``, ``.env.local``, ``prod.env``): plain ``key=value``."""
    base = rel.rsplit("/", 1)[-1]
    return base.endswith(_SHORT_VALUE_SUFFIXES) or base == ".env" or base.startswith(".env.")


def _shape_hit(line: str) -> bool:
    """An unambiguous credential shape. A Bearer token whose body names itself a sentinel is not one."""
    if any(pattern.search(line) for pattern in _SHAPE_PATTERNS if pattern is not _BEARER_SHAPE):
        return True
    return any(not _SENTINEL_RE.search(match.group(1)) for match in _BEARER_RE.finditer(line))


def _line_is_secret(line: str, *, in_code: bool = False, min_len: int = _MIN_SECRET_LEN) -> bool:
    line = _BADGE_URL_RE.sub(" ", line)
    if _shape_hit(line):
        return True
    for match in _KEYWORD_PATTERN.finditer(line):
        assignment = _ASSIGNED_VALUE_RE.search(line, match.start(1))
        if assignment and _looks_secret_value(assignment.group(1), in_code=in_code, min_len=min_len):
            return True
    return False


def _scan_secrets_allowlisted(
    inventory: Inventory, tracked: set[str] | None, allowlist: SecretAllowlist | None
) -> tuple[str, list[tuple[str, int]], list[tuple[str, int, str]]]:
    """``(scope, hits, suppressed)``: hits the repository has not allowlisted, and the ones it has (with the file)."""
    if tracked is None:
        scan_rels = sorted(f.rel for f in inventory.files if f.has_text)
        source = "whole inventory (tracked state unavailable)"
    else:
        scan_rels = sorted(f.rel for f in inventory.files if f.has_text and f.rel in tracked)
        source = "tracked text files"

    hits: set[tuple[str, int]] = set()
    suppressed: set[tuple[str, int, str]] = set()
    for rel in scan_rels:
        if _is_template_file(rel):
            continue
        text = inventory.read(rel)
        if not text:
            continue
        in_code = rel.endswith(_CODE_SUFFIXES)
        min_len = _MIN_SECRET_LEN_CONFIG if _is_short_value_file(rel) else _MIN_SECRET_LEN
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not _line_is_secret(line, in_code=in_code, min_len=min_len):
                continue
            if _PLACEHOLDER_RE.search(line):
                continue
            by = allowlist.covering_source(rel, line_no, line) if allowlist else None
            if by:
                suppressed.add((rel, line_no, by))
            else:
                hits.add((rel, line_no))
    return source, sorted(hits), sorted(suppressed)


def _scan_secrets(inventory: Inventory, tracked: set[str] | None) -> tuple[str, list[tuple[str, int]]]:
    source, hits, _suppressed = _scan_secrets_allowlisted(inventory, tracked, None)
    return source, hits


def _by_file(pairs: list[tuple[str, int]]) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = {}
    for rel, line in pairs:
        grouped.setdefault(rel, []).append(line)
    return grouped


def check_sec02(*, spec, target, inventory, stack, components, session) -> CheckOutcome:
    tracked = tracked_in_scope(target, inventory)
    allowlist = load_secret_allowlist(inventory)
    source, hits, suppressed = _scan_secrets_allowlisted(inventory, tracked, allowlist)

    allowed_note = ""
    if suppressed:
        sources = sorted({by for _rel, _line, by in suppressed})
        allowed_note = f"{len(suppressed)} allowlisted by {', '.join(f'`{name}`' for name in sources)}"
    suppressed_files = tuple(
        CredentialFile(path=rel, lines=tuple(lines))
        for rel, lines in sorted(_by_file([(rel, line) for rel, line, _by in suppressed]).items())
    )
    allowlisted_by = tuple(sorted({by for _rel, _line, by in suppressed}))

    if not hits:
        summary = f"no credential-shaped strings in {source}"
        if allowed_note:
            summary = f"0 credential-shaped lines outside the allowlist in {source}; {allowed_note}"
        return _outcome(
            spec,
            Verdict.PASS,
            summary,
            data=CredentialMatrix(
                total=0,
                source=source,
                allowlisted=len(suppressed),
                allowlisted_by=allowlisted_by,
                suppressed=suppressed_files,
            ),
        )

    by_file = _by_file(hits)

    findings: list[Finding] = []
    for rel in sorted(by_file)[:_MAX_SECRET_FILES]:
        findings.append(
            Finding(
                check=spec.id,
                severity=spec.severity,
                phase=spec.phase,
                verdict=Verdict.FAIL,
                statement=statement(
                    "keep credentials out of the repository and its history",
                    f"{rel} contains {len(by_file[rel])} credential-shaped line(s)",
                ),
                evidence=[Evidence(rel, line=line, note="credential-shaped string") for line in by_file[rel]],
                path=rel,
                remediation="Remove the value from the file and its history, load it from the "
                "environment, and rotate the credential. The report never records the "
                "value itself.",
            )
        )

    matrix = CredentialMatrix(
        total=len(hits),
        source=source,
        files=tuple(CredentialFile(path=rel, lines=tuple(by_file[rel])) for rel in sorted(by_file)),
        allowlisted=len(suppressed),
        allowlisted_by=allowlisted_by,
        suppressed=suppressed_files,
    )
    because = f"{len(hits)} credential-shaped line(s) across {len(by_file)} file(s) in {source}"
    if allowed_note:
        because += f"; {allowed_note}"
    return _outcome(spec, Verdict.FAIL, because, findings, data=matrix)
