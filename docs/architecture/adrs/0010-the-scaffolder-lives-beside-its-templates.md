# 0010. The Greenfield Scaffolder Lives in This Repository, Beside Its Templates

## Context

The greenfield scaffolder, [`bootstrap.py`](../../../greenfield/bootstrap/bootstrap.py), renders
[`greenfield/templates/`](../../../greenfield/templates/) into a new npm project. Its one rule is that the templates
own every byte of file content; the script owns structure, substitution and verification only
([`DESIGN.md`](../../../greenfield/bootstrap/DESIGN.md), D4).

The script and the templates change together. When the script lived apart from the templates, it found them by a
fixed path to a clone of this repository, and that path drifted from the template layout. The engine's
positive-fixture test, [`test_positive_fixture.py`](../../../audit/engine/tests/test_positive_fixture.py), runs the
scaffolder and audits its output. With the scaffolder outside this repository, CI had no scaffolder, so the test
skipped there.

## Decision

1. The scaffolder lives in this repository under `greenfield/bootstrap/`, with its own history.
2. `bootstrap.py` reads `greenfield/templates/` beside it by default (`Path(__file__).resolve().parent.parent /
   "templates"`). `--templates` and `AGENTIC_BOOTSTRAP_TEMPLATES` still point it at another copy.
3. The positive-fixture test finds the scaffolder in this checkout and runs in CI with no skip. `AUDIT_BOOTSTRAP`
   overrides the path. The test runs the scaffolder with `--no-git` and no `--install`, so it needs no git or npm.
4. `bootstrap.py` follows this repository's code rules. It carries the AGPL licence header. It is in the ruff
   scope and the mypy-strict scope (`TYPED_SOURCES` in the [`Makefile`](../../../Makefile)). Its `README.md` and
   `DESIGN.md` are documentation ([Licensing](../../reference/licensing.md)).

## Alternatives Considered

| Alternative | Why it is rejected |
| --- | --- |
| A separate repository with a remote | The script and the templates still change in two places, and CI here still needs a second checkout to run the positive fixture |
| Leave it a local-only repository | Only one machine has it, the default path drifts, and the positive fixture cannot run in CI |

## Consequences

### Positive

- One commit changes a template and the script together, so they cannot drift.
- The positive fixture runs in every CI run: a template change that breaks a scaffold fails the gate.
- A clone of this repository can scaffold a project with no other checkout.

### Negative / Trade-offs

- The repository holds a second Python tool with its own conventions: one file, no package
  ([engine ADR 0005](../../../audit/engine/docs/architecture/adrs/0005-module-layout-and-zipapp-distribution.md),
  rule 7).
- A future npm package of the scaffolder (`DESIGN.md`, D2) needs a publish path from this repository.
