# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""The engine's tests for each check pack, one package per pack (`AGT`, `CMD`, `EXEC`, ...).

Cross-pack and pipeline tests (the fixture matrix, scan, report, CLI) and the shared `support` helpers stay one level
up, in `tests/`. A test here puts the engine directory and `tests/` on `sys.path` itself, as the tests there do.
"""
