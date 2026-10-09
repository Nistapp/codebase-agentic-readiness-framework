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
- Each requirement states its verification method, one of the four below.

### Verification methods

Each requirement names the one method by which conformance is established.

| Method | Who decides | What backs the verdict | How it appears in an audit report |
|---|---|---|---|
| `automated` | A deterministic tool. The same inputs give the same verdict. | The tool's output, recorded with the tool's name and version. | A verdict (PASS, FAIL or PARTIAL; UNKNOWN when the tool could not gather its evidence), with tool-captured evidence. An agent may disagree only with counter-evidence and a recorded reason, and the report shows the tool's verdict next to the override. |
| `agent` | A model reading the repository. | Cited evidence: file, line and a short quote. Every FAIL also lists the searches that found nothing. | A verdict with agent-captured evidence. A person confirms blockers before the report is final. |
| `human` | A person, such as a reviewer or an architect. | The reviewer's recorded outcome. | Listed as pending review. It has no verdict and earns no credit until a person records one. |
| `attested` | The owner of the repository or process, by declaration. | The declaration: who made it, and when. | Listed as unattested. It is never shown as a pass and earns no credit until the owner declares it. |

Rules that apply to every method:

- Absence of evidence is not a pass. UNKNOWN, pending review and unattested items earn no credit, and a report never counts them as met.
- Prefer the more objective method. Use `automated` where a deterministic check is feasible, `agent` where the verdict needs judgment about content, `human` where it needs an accountable review, and `attested` only for facts the repository cannot show, such as a setting held in a hosting service. Do not mark a requirement `agent` merely because no tool exists yet; mark it `automated` with `Checks: none yet`.
- A person's confirmation of a finding does not change a requirement's method. It is a step of the audit process, not a way to verify a requirement.

The report format itself is defined later by the report schema in `brownfield-recipes/schema/`; this table fixes the meaning, and the schema will fix the field names.

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
