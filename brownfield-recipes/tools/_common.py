# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Shared helpers that give every tool the same contract (README.md in this folder).

A tool describes itself with a :class:`ToolInfo`, writes a handler that returns a :class:`Result`, and ends
with ``raise SystemExit(run_tool(INFO, handler, sys.argv[1:]))``. :func:`run_tool` does the rest: the Python
preflight, ``--describe``, one JSON envelope on stdout, a short summary on stderr, and the exit code.

The module also holds the helpers a tool needs to keep its promises: paths that cannot leave the target,
output directories that cannot be inside it, an atomic write, a bound on how much a tool prints, and the names
of output files, which carry the repository's name and are never replaced.

Failure behaviour: a :class:`ToolError` becomes an envelope with ``ok: false`` and the error's exit code.
Any other exception becomes exit code 3 with the traceback on stderr. The envelope is always printed.

Standard library only. This file and every file it imports must parse as Python 3.9, so that the preflight can
run on an old interpreter and say what to do. Keep to syntax and import-time behaviour that 3.9 has.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import stat
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, NoReturn, Sequence, TextIO

TOOLS_VERSION = "0.1.0"

MINIMUM_PYTHON: tuple[int, int] = (3, 11)
SUGGESTED_PYTHON = "3.12"

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_INVALID = 2
EXIT_INTERNAL = 3

EXIT_CODES = {
    str(EXIT_OK): "ok",
    str(EXIT_USAGE): "usage or input error",
    str(EXIT_INVALID): "the input was read and failed validation",
    str(EXIT_INTERNAL): "internal error",
}

# The envelope may not exceed this many bytes. `bound_items` keeps a tool well under it.
MAX_OUTPUT_BYTES = 64 * 1024
ITEM_BUDGET_BYTES = 48 * 1024
MAX_MESSAGE_CHARS = 2000


class ToolError(Exception):
    """An error a tool expects. `run_tool` turns it into an envelope and the exit code of its class."""

    exit_code = EXIT_INTERNAL

    def __init__(self, message: str, *, errors: Sequence[str] = (), hint: str = "") -> None:
        super().__init__(message)
        self.errors = list(errors)
        self.hint = hint


class UsageError(ToolError):
    """A bad argument, a missing file, a path that is not allowed, or an interpreter that is too old."""

    exit_code = EXIT_USAGE


class PathNotAllowed(UsageError):
    """A path that leaves the target, or an output path that lands inside it."""


class ValidationFailed(ToolError):
    """The input was read and is invalid. `errors` lists what to fix."""

    exit_code = EXIT_INVALID


class OutputTooLarge(ToolError):
    """A tool built more output than the envelope may hold. That is a bug in the tool."""

    exit_code = EXIT_INTERNAL


@dataclass
class Result:
    """What a handler returns. `summary` is the one or two lines for stderr."""

    data: dict[str, Any]
    summary: str = ""
    warnings: list[str] = field(default_factory=list)
    truncated: bool = False


@dataclass(frozen=True)
class ToolInfo:
    """A tool's identity. `manifest` is what `--describe` prints."""

    name: str
    summary: str
    synopsis: tuple[str, ...]
    writes: str
    version: str = TOOLS_VERSION

    def manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "summary": self.summary,
            "synopsis": list(self.synopsis),
            "writes": self.writes,
            "network": False,
            "writes_inside_target": False,
            "exit_codes": dict(EXIT_CODES),
        }


Handler = Callable[[Sequence[str]], Result]


class ToolParser(argparse.ArgumentParser):
    """An argument parser whose errors are a `UsageError`, so they exit with 1 and an envelope, not with 2.

    It refuses abbreviations: `--out` must not quietly mean `--out-dir`, and a flag added later must not change
    what an abbreviation in an old recipe means.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> NoReturn:
        raise UsageError(message)


# --- The envelope -------------------------------------------------------------------------------------


def make_envelope(
    info: ToolInfo,
    *,
    ok: bool,
    data: dict[str, Any],
    warnings: Sequence[str] = (),
    truncated: bool = False,
) -> dict[str, Any]:
    return {
        "tool": info.name,
        "version": info.version,
        "ok": ok,
        "data": data,
        "warnings": list(warnings),
        "truncated": truncated,
    }


def encode_envelope(envelope: dict[str, Any], *, limit: int = MAX_OUTPUT_BYTES) -> str:
    """The envelope as text, or `OutputTooLarge` when it does not fit. Key order is the order given."""
    text = json.dumps(envelope, indent=2, ensure_ascii=False) + "\n"
    size = len(text.encode("utf-8"))
    if size > limit:
        raise OutputTooLarge(f"the output is {size} bytes and the limit is {limit}; the tool must bound its lists")
    return text


def bound_items(items: Sequence[Any], *, limit_bytes: int = ITEM_BUDGET_BYTES) -> tuple[list[Any], int]:
    """Keep leading items while their JSON size fits `limit_bytes`. Returns the kept items and how many were left out.

    The size is an estimate that counts each item once, indented, plus its separator. It sits below
    `MAX_OUTPUT_BYTES` so that the rest of the envelope still fits. The order is the order given, so the same
    input drops the same items.
    """
    kept: list[Any] = []
    used = 0
    for item in items:
        size = len(json.dumps(item, indent=2, ensure_ascii=False).encode("utf-8")) + 2
        if used + size > limit_bytes:
            break
        kept.append(item)
        used += size
    return kept, len(items) - len(kept)


def _clip(message: str) -> str:
    return message if len(message) <= MAX_MESSAGE_CHARS else message[:MAX_MESSAGE_CHARS] + "..."


# --- Running a tool -----------------------------------------------------------------------------------


def check_python(version: Sequence[int] | None = None, *, script: str = "") -> None:
    """Raise `UsageError` with a `uv run` hint when the interpreter is older than `MINIMUM_PYTHON`."""
    found = tuple(sys.version_info[:3]) if version is None else tuple(version)
    if tuple(found[:2]) >= MINIMUM_PYTHON:
        return
    wanted = ".".join(str(part) for part in MINIMUM_PYTHON)
    seen = ".".join(str(part) for part in found)
    raise UsageError(
        f"needs Python {wanted} or newer, found {seen}",
        hint=f"run it with:  uv run --python {SUGGESTED_PYTHON} python3 {script or sys.argv[0]} ...",
    )


def run_tool(
    info: ToolInfo,
    handler: Handler,
    argv: Sequence[str],
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    python_version: Sequence[int] | None = None,
) -> int:
    """Run `handler` under the contract and return the exit code. The streams and version are for tests."""
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        check_python(python_version)
        if "--describe" in argv:
            result = Result(data=info.manifest(), summary=f"{info.name} {info.version}: {info.summary}")
        else:
            result = handler(argv)
        text = encode_envelope(
            make_envelope(info, ok=True, data=result.data, warnings=result.warnings, truncated=result.truncated)
        )
        code = EXIT_OK
        lines = [result.summary] if result.summary else []
    except ToolError as exc:
        kept, omitted = bound_items(exc.errors)
        data: dict[str, Any] = {"error": _clip(str(exc))}
        if kept:
            data["errors"] = kept
        if omitted:
            data["errors_omitted"] = omitted
        text = encode_envelope(make_envelope(info, ok=False, data=data, truncated=bool(omitted)))
        code = exc.exit_code
        lines = [f"{info.name}: {data['error']}"]
        lines += [f"  {line}" for line in kept[:5]]
        if exc.hint:
            lines.append(f"  {exc.hint}")
    except Exception as exc:
        traceback.print_exc(file=err)
        data = {"error": _clip(f"internal error: {type(exc).__name__}: {exc}")}
        text = encode_envelope(make_envelope(info, ok=False, data=data))
        code = EXIT_INTERNAL
        lines = [f"{info.name}: {data['error']}"]
    out.write(text)
    out.flush()
    for line in lines:
        print(line, file=err)
    return code


# --- Paths: stay inside the target, write outside it --------------------------------------------------


def is_within(root: Path, path: Path) -> bool:
    """Whether `path` is `root` or below it. Both must already be resolved."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_target(path: str | Path) -> Path:
    """The target directory, resolved. It must exist and be a directory."""
    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise UsageError(f"target not found: {candidate}") from None
    if not resolved.is_dir():
        raise UsageError(f"target is not a directory: {resolved}")
    return resolved


def resolve_within(root: Path, candidate: str | Path) -> Path:
    """Resolve `candidate` (relative to `root`, or absolute) and require the result to be inside `root`.

    Symlinks are followed before the check, so a link that points out of the target is refused, and so is
    a path that climbs out with `..`.
    """
    root = root.resolve()
    given = Path(candidate)
    try:
        resolved = (given if given.is_absolute() else root / given).resolve()
    except (OSError, RuntimeError):
        raise PathNotAllowed(f"cannot resolve the path: {candidate}") from None
    if not is_within(root, resolved):
        raise PathNotAllowed(f"the path leaves the target: {candidate}")
    return resolved


def output_directory(path: str | Path, *, target: Path) -> Path:
    """An output directory that is outside `target`, created if it does not exist.

    The check is made on the resolved path, so a directory that reaches the target through a symlink is
    refused. Nothing is created until the check has passed.
    """
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError):
        raise PathNotAllowed(f"cannot resolve the output directory: {path}") from None
    if is_within(target.resolve(), resolved):
        raise PathNotAllowed(f"refusing to write inside the target: {resolved}")
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UsageError(f"cannot use the output directory {resolved}: {exc.strerror or exc}") from None
    return resolved


# --- Writing ------------------------------------------------------------------------------------------


def atomic_write_text(path: str | Path, text: str) -> None:
    """Replace `path` with `text` in one step, so a reader sees the old file or the new one and never half of it.

    Use it only for a file the run itself owns, such as its own draft report. A file another run wrote must
    never be passed here.
    """
    target = Path(path)
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
    fd, temp = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp)
        raise


# --- Output files: names that carry the repository, and files that are never replaced -------------------
#
# The contract is "Output files" in brownfield-recipes/schema/SCHEMA.md. A name is
# `<label>.<kind>.<stamp>.<ext>`; when it is taken, `-2`, `-3` and so on follow the stamp.

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
DERIVED_LABEL_CHARS = 24
MAX_NAME_ATTEMPTS = 1000

# The same pattern as `repo_label` in schema/audit-intake.schema.json. Each ends in `\Z` and not `$`, because
# Python's `$` also matches before a final newline, and a newline must never reach a file name.
EXPLICIT_LABEL = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}\Z")
_STAMP = re.compile(r"^[0-9]{8}T[0-9]{6}Z\Z")
_KIND = re.compile(r"^[a-z]+(-[a-z]+)*\Z")
_EXTENSION = re.compile(r"^[a-z]+\Z")


def derive_label(directory_name: str) -> str:
    """A short label from a directory name: lower case, each run of other characters one hyphen, 24 characters."""
    label = re.sub(r"[^a-z0-9]+", "-", directory_name.lower()).strip("-")
    return label[:DERIVED_LABEL_CHARS].rstrip("-") or "repo"


def repo_label(directory: str | Path, explicit: str | None = None) -> str:
    """The label for a repository's output files: the explicit `repo_label`, or one derived from the directory."""
    if explicit is not None:
        if not EXPLICIT_LABEL.match(explicit):
            raise UsageError(
                f"repo_label {explicit!r} is not allowed: use up to 32 of a-z, 0-9, dot, underscore and hyphen, "
                "starting with a letter or digit"
            )
        return explicit
    return derive_label(Path(directory).resolve().name)


def utc_stamp(moment: datetime | None = None) -> str:
    """The UTC time as `YYYYMMDDTHHMMSSZ`. Without an argument, now. A given time must carry a timezone."""
    if moment is None:
        moment = datetime.now(timezone.utc)
    elif moment.tzinfo is None:
        raise ValueError("the time must carry a timezone")
    return moment.astimezone(timezone.utc).strftime(STAMP_FORMAT)


def output_name(label: str, kind: str, stamp: str, ext: str, attempt: int = 1) -> str:
    """`<label>.<kind>.<stamp>.<ext>`, with `-<attempt>` after the stamp from the second attempt on."""
    if not EXPLICIT_LABEL.match(label):
        raise ValueError(f"not a label: {label!r}")
    if not _KIND.match(kind):
        raise ValueError(f"not a kind: {kind!r}")
    if not _STAMP.match(stamp):
        raise ValueError(f"not a stamp: {stamp!r}")
    if not _EXTENSION.match(ext):
        raise ValueError(f"not an extension: {ext!r}")
    suffix = "" if attempt == 1 else f"-{attempt}"
    return f"{label}.{kind}.{stamp}{suffix}.{ext}"


def free_name(directory: Path, label: str, kind: str, stamp: str, ext: str) -> Path:
    """The first of the numbered names that nothing occupies. It creates nothing.

    A dangling symlink occupies its name. Another run can take the name before the caller uses it, so a
    caller that can must use `create_new`, or hand the name to a program that itself refuses to replace a file.
    """
    for attempt in range(1, MAX_NAME_ATTEMPTS + 1):
        path = directory / output_name(label, kind, stamp, ext, attempt)
        if not os.path.lexists(path):
            return path
    raise UsageError(f"no free name for {label}.{kind}.{stamp} in {directory}")


def _payload(data: str | bytes) -> bytes:
    return data.encode("utf-8") if isinstance(data, str) else data


def _claim(path: Path) -> int:
    """Create `path` with `O_EXCL` and return its descriptor.

    `FileExistsError` when anything is there: a file, a directory, or a symlink, dangling or not. The call never
    follows a link, so a name that points elsewhere is never written through.
    """
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)


def _give_back(claimed: Sequence[tuple[int, Path]], *, from_index: int = 0) -> None:
    """Close the descriptors from `from_index` on, and remove every file in `claimed`.

    The files are ones this process created a moment ago and has not shown to anyone, so they are the only files
    that a failed creation ever removes. A descriptor that a file object took over is not in the closing range,
    because closing one number twice could close a descriptor that another thread has opened since.
    """
    for descriptor, _ in claimed[from_index:]:
        with contextlib.suppress(OSError):
            os.close(descriptor)
    for _, path in claimed:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(path)


def _fill(claimed: Sequence[tuple[int, Path]], payloads: Sequence[bytes]) -> None:
    """Write each payload to the file claimed for it and flush it to disk. On any failure none of the files is left."""
    taken = 0
    try:
        for (descriptor, _), payload in zip(claimed, payloads):
            taken += 1
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
    except BaseException:
        _give_back(claimed, from_index=taken)
        raise


def create_file(path: str | Path, data: str | bytes) -> Path:
    """Write `data` to `path`, which must not exist, and return it. Anything already there stops the call.

    This is for a file the caller named itself, such as an `--out` path. A file the tool names is made with
    `create_new` or `create_new_group`, which number a taken name instead of refusing it. Any other `OSError`, such
    as a missing folder, reaches the caller. A write that fails removes the partial file it created and nothing else.
    """
    target = Path(path)
    try:
        descriptor = _claim(target)
    except FileExistsError:
        raise UsageError(f"{target} already exists, and a tool never replaces a file") from None
    _fill([(descriptor, target)], [_payload(data)])
    return target


def create_new_group(
    directory: Path, label: str, kind: str, stamp: str, files: Sequence[tuple[str, str | bytes]]
) -> list[Path]:
    """Write files that share one name apart from the extension, as one group, and return their paths in order.

    The group takes the first number at which every name is free, so `<label>.<kind>.<stamp>.json` and its `.md`
    never come apart: if either name is taken, both move to `-2`, and so on. A name that was claimed before the
    clash is found is given back. No existing file is touched, and a write that fails removes the files this call
    created and nothing else. The caller gets `directory` from `output_directory`, which has kept it outside the target.
    """
    extensions = [ext for ext, _ in files]
    if not extensions or len(set(extensions)) != len(extensions):
        raise ValueError("a group needs at least one file, and each must have its own extension")
    payloads = [_payload(data) for _, data in files]
    for attempt in range(1, MAX_NAME_ATTEMPTS + 1):
        claimed: list[tuple[int, Path]] = []
        try:
            for ext in extensions:
                path = directory / output_name(label, kind, stamp, ext, attempt)
                claimed.append((_claim(path), path))
        except FileExistsError:
            _give_back(claimed)
            continue
        except BaseException:
            _give_back(claimed)
            raise
        _fill(claimed, payloads)
        return [path for _, path in claimed]
    raise UsageError(f"no free name for {label}.{kind}.{stamp} in {directory}")


def create_new(directory: Path, label: str, kind: str, stamp: str, ext: str, data: str | bytes) -> Path:
    """Write `data` to a new file named by `output_name` and return its path. No existing file is touched.

    The file is created with `O_EXCL`, so when two runs reach one name in the same second, each gets its own
    and neither replaces the other. A write that fails removes the partial file it created and nothing else.
    The caller gets `directory` from `output_directory`, which has kept it outside the target.
    """
    return create_new_group(directory, label, kind, stamp, [(ext, data)])[0]
