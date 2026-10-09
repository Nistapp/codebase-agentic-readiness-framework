# spec/

Normative requirements for the Codebase Agentic Readiness Framework: what a repository MUST, SHOULD, or MAY have to count as agentic-ready.

The recipes in `greenfield-bootstrap/` and `brownfield-legacy/` explain *how*. This folder states *what* and is the source of truth for conformance. Recipes should link to requirement IDs instead of restating rules.

## Conventions

### Requirement language

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are interpreted as in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they appear in capitals.

### Requirement IDs

Every requirement has a stable ID and is written as one testable statement:

```markdown
### REQ-GF-012 — Six-verb command surface
The repository MUST expose `format`, `lint`, `typecheck`, `test`, `check`, and `security` as single commands.
```

- Format: `REQ-<AREA>-<NNN>`. Areas: `GF` greenfield, `BF` brownfield, `SH` shared.
- IDs are never reused or renumbered. A withdrawn requirement is marked `Withdrawn`, not deleted.
- Each requirement states its verification method: `automated`, `review`, or `attested`.

### Supporting formats

| Need | Format |
|---|---|
| Config or manifest shape | JSON Schema, under `schemas/` |
| Behavioural acceptance criteria | Gherkin |
| Diagrams | Mermaid |
| Terminology | `shared/Glossary.md` |

## Planned contents

- `readiness-requirements.md`: the normative requirements, extracted from the existing docs.
- `schemas/`: only if a readiness manifest or report format is defined.
