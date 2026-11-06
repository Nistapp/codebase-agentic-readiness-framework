# Documentation Style Guide

There is one rule set for the documentation in this repository, and it is
[`brownfield-recipes/docs/STYLE_GUIDE.md`](../brownfield-recipes/docs/STYLE_GUIDE.md). It is the body of this page:
read it, follow it, and link to it. Do not restate its rules anywhere else, because a restated rule drifts.

It governs the pages under `docs/`, `brownfield-recipes/docs/` and the engine's `docs/`. The framework documents at the
root (`shared/`, `brownfield-legacy/`, `greenfield-bootstrap/`) are normative; change them only on purpose, and keep
the requirement ids in [`spec/`](../spec/README.md) in step.

Markdown is linted by `make docs-lint` against [`.markdownlint-cli2.jsonc`](../.markdownlint-cli2.jsonc); a path joins
the lint ratchet in the `Makefile` once it is clean.
