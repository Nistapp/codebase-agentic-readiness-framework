# Security hygiene (`SEC`)

> Follows the anatomy in [`README.md`](README.md). Three checks, all `method: automated`. See
> [Why These Checks §13](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#13-security-hygiene-sec)
> for the consequence behind this family: an agent's context is transmitted and logged by the tooling
> around it, so a secret an agent reads is a secret exposed through the very tool added for safety.
> Every check reads the engine's `SEC` pack (`deterministic-audit/audit/rules/checks/sec.py`), whose
> redaction happens at capture time, never at render time (`deterministic-audit/AGENTS.md` §9).
>
> **Never quote a secret value, in a finding, a summary, or anywhere else in the report.** `SEC-02`'s
> own evidence records a path and a line number only, with the note `"credential-shaped string"` — never
> the matched text. This file's checks, and the agent writing them up, follow the same rule the root
> `AGENTS.md` states for the recipe as a whole: never open, print or quote a `.env` file or any other
> secret store. A `.env`-like file is data you may not read at all, even to confirm a finding; cite its
> path and nothing from its contents.

---

## SEC-01 — `.env` untracked and ignored

Why it matters   An agent's context is transmitted and logged; a tracked `.env` file is a credential
                  exposed through the tool added for safety, not despite it
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         BLOCKER
Engine           `SEC-01`. Two independent halves: whether `.env`/`.env.*` (excluding committed templates
                 such as `.env.example`, `.env.sample`, `.env.template`, `.env.dist`, `.env.defaults`,
                 `env.example`) is git-tracked, read from `tracked_files`; and whether the ignore rules
                 cover the `.env` shape, read from the ignore files directly — so a tracked `.env` that
                 is *also* git-ignored is still caught, because tracked state and ignore coverage are
                 checked independently, not inferred from one another. A tracked `.env`/`.env.*` is the
                 blocker (`FAIL`) regardless of ignore coverage. No tracked `.env`, but the ignore rules
                 miss the shape, is `PARTIAL`. Git unable to report tracked files makes the blocker half
                 `UNKNOWN` — never inferred as a pass — whatever the ignore coverage reads as. Distrust a
                 `PARTIAL`/`FAIL` on ignore coverage when the repository uses an ignore mechanism beyond
                 `.gitignore` that the engine's loader does not yet read — verify by checking
                 `audit.ignore.load_ignore_rules`'s own source list before treating the gap as real.
Method           automated
Look for         `tracked_files` for any path named `.env` or `.env.*` (excluding the committed-template
                 basenames); the loaded ignore rules for coverage of the `.env` and `.env.*` shapes. Cite
                 only the path of any tracked `.env`-like file found — never open or quote it.
Rubric           PASS: no `.env`/`.env.*` file is tracked, and ignore rules cover both shapes.
                 PARTIAL: no `.env`/`.env.*` file is tracked, but ignore rules miss one or both shapes.
                 FAIL: a `.env`/`.env.*` file (not a committed template) is tracked, regardless of
                 ignore coverage.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: git could not report the repository's tracked files, so a tracked `.env`
                 cannot be ruled out.
Evidence to cite A `file` evidence item citing the tracked path only (never its contents) for FAIL; for
                 PARTIAL, the ignore rule(s) read (source file and pattern) as the coverage evidence; for
                 PASS, the same ignore rule(s) that do cover the shape.
Absence proof    A PARTIAL names exactly which shape (`.env` or `.env.*`, or both) no ignore rule covers;
                 a FAIL cites the tracked path directly as the proof, since the path's own existence in
                 `tracked_files` is the finding.
Remediation      `env-inventory-and-secrets`
Pitfalls         A tracked `.env.example`-style committed template is not a finding here — it is the
                 documented exemption (REQ-SH-054), not an oversight; do not flag a template file as a
                 tracked secret just because its name starts with `.env`.

## SEC-02 — No key-shaped strings in tracked files

Why it matters   A hardcoded credential is the same exposure as a tracked `.env` file, just inside source
                  or configuration instead of a dedicated file
                  ([Phased-Approach.md § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         BLOCKER
Engine           `SEC-02`. Scans tracked text files (falling back to the whole inventory, stated in
                 `detail`, when git cannot report tracked state) against `audit.probes.REDACTION_PATTERNS`:
                 unambiguous shape patterns (`sk-...`, `ghp_...`, `AKIA...`, a `Bearer` token, and the PEM
                 private-key header `BEGIN PRIVATE KEY`) <!-- pragma: allowlist secret -->
                 that always fire, plus one keyword-assignment pattern (`token`,
                 `password`, `api_key`, and the like) that fires only when a deterministic guard judges
                 the assigned value to actually look like a secret — a quoted literal that is not a
                 reference to the environment or a secret store (`${NAME}`, `os.environ/NAME`,
                 `{{ secrets.NAME }}`), or, outside source code, a single plain unquoted token at least 12
                 characters long with a mixed charset; in source code an unquoted value is a name or an
                 expression, never counted. Committed templates (`*.example`/`*.sample`/`*.template`) and
                 lines matching an obvious placeholder pattern (`<...>`, `your-`, `changeme`, `xxx`, and
                 similar) are skipped deterministically. **No verdict ever names the matched value** — a
                 `Finding`'s evidence carries path, line number and the fixed note `"credential-shaped
                 string"` only. Distrust a `FAIL` on the keyword pattern specifically (never the
                 unambiguous shape patterns, which are unconditional) when the line is a CI permission
                 grant (`id-token: write`), or a short, descriptive mock literal assigned to a credential-
                 shaped keyword inside the target's own test code (confirmed twice in real audits: a test
                 suite's `token`/`apikey` assignments to hyphenated placeholder labels, none matching the
                 deterministic placeholder filter's fixed word list) — verify by reading the line's own
                 context (the file's role, the variable's name, a nearby comment), never its literal value
                 in the report. The unambiguous shape patterns stay unconditional even inside a test file:
                 a real credential pasted there by accident is exactly the case this check exists to
                 catch, and the engine's own test fixtures for this very detector are a known,
                 self-referential exception specific to auditing this engine's own repository, not a
                 reason to distrust a shape match anywhere else.
Method           automated
Look for         Every tracked text file (or the whole inventory, when tracked state is unavailable) for
                 a line matching `REDACTION_PATTERNS`; the matched line's path and line number only.
Rubric           PASS: no tracked text file (or, with tracked state unavailable, no file in the whole
                 inventory) contains a credential-shaped line.
                 PARTIAL: not used by this check — any credential-shaped line fails the whole check.
                 FAIL: at least one tracked text file contains a credential-shaped line.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — the scan runs against tracked files when available and the whole
                 inventory otherwise, so there is always a defined scope to report against.
Evidence to cite A `file` evidence item per offending path (up to 25 files), each citing every matching
                 line number for that path and the note `"credential-shaped string"` — never the line's
                 own text or the matched substring.
Absence proof    A FAIL states the total hit count and the file count, and names every offending path
                 with its line numbers, so "contains a credential-shaped line" is a checkable location
                 list, not a claim about content nobody can re-verify without reopening the secret.
Remediation      `env-inventory-and-secrets`
Pitfalls         **Never add the matched value to a finding, an evidence note, or any other part of the
                 report, even to argue a false positive** — if a flagged line needs discussion, describe
                 its shape or context ("a 32-character hex string assigned to API_KEY"), not its literal
                 content; this applies whether the agent is confirming the engine's `FAIL` or arguing it
                 should be downgraded.

## SEC-03 — Ignore patterns cover secret shapes

Why it matters   The guard must exist before the accident — ignore rules that do not cover a secret shape
                  let a single careless commit become permanent history
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         DEGRADER
Engine           `SEC-03`. Checks ignore-rule coverage of eleven documented secret/certificate/credential
                 shapes (dotenv and its variants, SSH private keys, PEM, generic `.key`, PKCS#12, PFX,
                 keystore, `.crt`/`.cer` certificates, AWS credentials), each probed by a representative
                 sample path (`_SECRET_SHAPES`) against the loaded ignore rules. No ignore file at all is
                 `FAIL` outright — there is no coverage to measure. Every shape covered is `PASS`; some
                 covered is `PARTIAL`; an ignore file exists but covers none of the eleven is `FAIL`.
                 There is no `UNKNOWN` path — the presence and coverage of ignore rules is always
                 determinable. Distrust a `PARTIAL`/`FAIL` for a shape covered by a broader rule the
                 engine's documented ignore-matching subset does not recognise (full gitignore semantics
                 beyond simple glob anchoring and `**`) — verify by reading the ignore file's own rule
                 directly before treating the gap as real.
Method           automated
Look for         The loaded ignore rules (`.gitignore` or equivalent) for coverage of each of the eleven
                 documented shapes' representative sample path.
Rubric           PASS: ignore rules cover every one of the eleven documented secret shapes.
                 PARTIAL: ignore rules cover some of the eleven shapes but not all, and at least one
                 ignore file exists.
                 FAIL: no ignore file exists at all, or one exists but covers none of the eleven shapes.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — ignore-rule presence and coverage are always determinable.
Evidence to cite A `file` evidence item per covered shape (the ignore rule's source and pattern) for
                 PASS/PARTIAL; for a FAIL with no ignore file, cite the absence of any ignore file as the
                 evidence directly.
Absence proof    A FAIL or PARTIAL names every missing shape by its label (for example "PKCS#12",
                 "AWS credentials"), with the suggested `.gitignore` entry (`_SECRET_SHAPE_SUGGEST`)
                 ready to paste, so the gap is a checkable, fixable list rather than a general impression.
Remediation      `env-inventory-and-secrets`
Pitfalls         `SEC-01` and `SEC-03` share the dotenv shapes but read different scope — `SEC-01` is
                 `.env`/`.env.*` specifically (tracked state and ignore coverage both), `SEC-03` is eleven
                 shapes including dotenv but never reads tracked state — a `PASS` on one does not predict
                 the other, and the dotenv shape itself can read `PASS` on `SEC-03` while `SEC-01` is
                 `FAIL` (a tracked `.env` with an otherwise-correct ignore rule added too late).
