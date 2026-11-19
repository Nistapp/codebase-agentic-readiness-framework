# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Split the Bash commands of an eval transcript into simple commands, for the implement and audit evals.

``shell_segments`` splits one command on the shell's separators and keeps quoted text together. ``all_segments``
also splits the scripts a command hands to ``sh -c``, ``bash -c`` or ``eval``. ``subcommand`` names what a segment
asks ``git`` or ``gh`` to do. ``implement_eval.py`` and ``audit_eval.py`` both import this module; it parses text
only and runs nothing. Standard library only.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

#: The tokens that end one simple command and start the next.
SEPARATORS = frozenset({"&&", "||", ";", "|", "&", "(", ")"})
#: The shells whose `-c` script `all_segments` splits too.
SHELLS = frozenset({"sh", "bash", "zsh", "dash"})
#: The global flags of `git` and `gh` that take a value, so the word after them is not the subcommand.
VALUE_FLAGS = frozenset({"-C", "-c", "-R", "--repo"})


def shell_segments(command: str) -> list[list[str]]:
    """The simple commands of `command`, split on the shell's separators; quotes are kept together.

    A command that does not lex (an open quote) falls back to a plain split on the separators and on whitespace.
    """
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return [line.split() for line in re.split(r"&&|\|\||;|\|", command)]
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SEPARATORS or (set(token) <= set("&|;()") and token):
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def all_segments(command: str) -> list[list[str]]:
    """The simple commands of `command`, and of every script it hands to `sh -c`, `bash -c` or `eval`."""
    found: list[list[str]] = []
    for segment in shell_segments(command):
        found.append(segment)
        for index, token in enumerate(segment[:-1]):
            if token == "eval":
                found += all_segments(" ".join(segment[index + 1 :]))
                break
            if Path(token).name in SHELLS and segment[index + 1] == "-c" and index + 2 < len(segment):
                found += all_segments(segment[index + 2])
                break
    return found


def subcommand(segment: list[str], program: str) -> tuple[str, list[str]] | None:
    """The subcommand and its arguments when `segment` runs `program` (`git` or `gh`), else None."""
    for start, token in enumerate(segment):
        if token != program and not token.endswith(f"/{program}"):
            continue
        index = start + 1
        while index < len(segment) and segment[index].startswith("-"):
            index += 2 if segment[index] in VALUE_FLAGS else 1
        if index < len(segment):
            return segment[index], segment[index + 1 :]
    return None
