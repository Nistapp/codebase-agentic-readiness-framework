# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The document index: a deterministic graph of a repository's files, sections, IDs and the edges between them.

This package is the generic core (ADR 0011 in ``docs/architecture/adrs/``). It uses the standard library only and
imports nothing from ``audit/``, ``implement/`` or another ``dev/`` module. What is project-specific (the zones,
the ID patterns, the exclusions, the sweep scope) comes from the config that the entry point, ``dev/doc_index.py``,
reads from ``dev/docindex.config.json`` and passes in.

- :mod:`docindex.model`: the frozen nodes and edges and their one JSON form (``index.schema.json``).
- :mod:`docindex.cli`: the command line, ``build``, ``diff``, ``sweep``, ``query``, ``verify-quotes``,
  ``manifest``, ``manifest-diff`` and ``evidence``. Its module docstring lists each one's arguments.
"""

from __future__ import annotations

from .model import (
    CONFIDENCES,
    EDGE_KINDS,
    FILE_KINDS,
    ID_KINDS,
    INDEX_FORMAT,
    ZONES,
    Edge,
    FileNode,
    IdNode,
    Index,
    Node,
    SectionNode,
    content_hash,
    from_json,
    to_json,
)

__all__ = [
    "CONFIDENCES",
    "EDGE_KINDS",
    "FILE_KINDS",
    "ID_KINDS",
    "INDEX_FORMAT",
    "ZONES",
    "Edge",
    "FileNode",
    "IdNode",
    "Index",
    "Node",
    "SectionNode",
    "content_hash",
    "from_json",
    "to_json",
]
