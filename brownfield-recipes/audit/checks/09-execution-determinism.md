# Execution determinism (`EXEC`)

> Follows the anatomy in [`README.md`](README.md). Seven checks, all `method: automated`. See
> [Why These Checks §10](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#10-execution-determinism-exec)
> for the consequence behind this family: this is where brownfield repositories fail hardest, and where
> the framework's Phase 1 is thinnest. Every check reads the engine's `EXEC` pack
> (`deterministic-audit/audit/rules/checks/execution.py`), whose module docstring names each check's own
> `UNKNOWN` conditions and its one documented limitation (manifest↔lockfile parsing beyond
> node/python/rust/go is not attempted, so those ecosystems report the tracked fact and `PARTIAL`
> consistency rather than a false `PASS`).

---

## EXEC-01 — Toolchain pinned / wrapper committed

Why it matters   An agent's runtime must be the repository's, not whatever happens to be on the host —
                  otherwise the gate passes locally and fails in CI, or an agent reproduces nothing
                  ([greenfield-bootstrap/README.md § File Tree — What Gets Created](../../../greenfield-bootstrap/README.md#file-tree--what-gets-created)).
Severity         BLOCKER
Engine           `EXEC-01`. For every detected ecosystem among node, python, jvm, dotnet, rust and ruby
                 (go is pinnable too but has no dedicated pin file of its own), looks for that
                 ecosystem's pin: a version file (`.nvmrc`, `.python-version`, `.ruby-version`,
                 `rust-toolchain.toml`/`rust-toolchain`), a wrapper (`gradlew`, `mvnw`), `global.json`
                 for dotnet, a matching line in a shared `.tool-versions`, `package.json`'s
                 `engines.node`, `pyproject.toml`'s `requires-python`, or `go.mod`'s `go` directive. No
                 ecosystem from this pinnable set is detected at all ⇒ `UNKNOWN` — there is no toolchain
                 to choose a pin for. php is a recognised ecosystem the table does not assert a pin for,
                 so a php-only repository is also `UNKNOWN` on this check. Distrust a `FAIL` when the
                 pin lives in a convention the engine's table does not yet carry (a newer per-ecosystem
                 version manager) — verify by reading the repository's own tool documentation before
                 treating the gap as real.
Method           automated
Look for         Each detected pinnable ecosystem's own pin file or declaration, named above; absent any
                 of them, `.tool-versions` for a matching line.
Rubric           PASS: every detected pinnable ecosystem has at least one of its own pin files, or a
                 matching `.tool-versions` line, or (node/python/go) the manifest-level constraint.
                 PARTIAL: not used by this check — any one ecosystem left unpinned fails the whole check.
                 FAIL: at least one detected pinnable ecosystem has none of its pin evidence.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no ecosystem from the pinnable set (node, python, jvm, dotnet, rust, ruby,
                 go) is detected at all.
Evidence to cite A `file` evidence item per unpinned ecosystem, citing the pin file names that were
                 searched for and not found; for PASS, cite the pin file or declaration actually found
                 for each ecosystem.
Absence proof    A FAIL names, for each unpinned ecosystem, every pin file the engine looked for (the
                 full tuple from the table above, plus `.tool-versions`), so the absence is a named list,
                 not an assertion.
Remediation      `pin-execution-environment`
Pitfalls         A monorepo where only one of several ecosystems is pinned still reads `FAIL` overall —
                 the engine fails the whole check on the first unpinned ecosystem, so a `FAIL` summary
                 naming one ecosystem does not mean the others are also unpinned; read which ecosystem
                 the finding actually names before writing remediation.

## EXEC-02 — Lockfile committed and consistent

Why it matters   Every run must resolve identical dependencies; a lockfile that is missing, untracked, or
                  stale turns "works on my machine" into a problem the agent inherits too
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         BLOCKER
Engine           `EXEC-02`. For each detected ecosystem with a package manager the engine recognises
                 (node, python, jvm, rust, go, ruby, php), finds that manager's lockfile at any depth,
                 prefers the shallowest, and requires it to be git-tracked; for node/python/rust/go it
                 then compares the lockfile's own declared packages against the root manifest's. No
                 ecosystem with a recognised manager is detected ⇒ `UNKNOWN`; an ecosystem recognised only
                 from its source files, with no manifest (`Stack.source_only`), is also `UNKNOWN` — it
                 declares no dependencies, so no lockfile is expected. Git unable to report tracked files
                 (no repository, or the command failed) makes the tracked half `UNKNOWN` for the whole
                 check, never inferred as passing. A lockfile found only in a subdirectory is tracked but
                 its consistency is left `PARTIAL`, because only the root manifest is read. Distrust a
                 `FAIL` for "no lockfile" when the manager is one the engine does not recognise for that
                 ecosystem — verify against `PACKAGE_MANAGERS` in `audit/stack.py` before concluding the
                 project truly has none. Distrust a `PARTIAL` citing "consistency unverified" when the
                 lockfile is larger than `CONTENT_READ_LIMIT` (`audit/scan.py`, 2 MiB) — the engine never
                 read the file at all, so this is a tooling limit, not evidence of drift; compare the
                 manifest's and lockfile's declared dependency names directly before accepting the gap.
Method           automated
Look for         Every lockfile name for each detected package manager, at any depth; `git ls-files` (or
                 equivalent) for whether the shallowest one is tracked; for node/python/rust/go, the
                 manifest's declared dependency names against the lockfile's own.
Rubric           PASS: every detected ecosystem's lockfile exists, is tracked, and (where parsing is
                 attempted) agrees with the manifest.
                 PARTIAL: every detected ecosystem's lockfile exists and is tracked, but consistency could
                 not be verified for at least one (an ecosystem beyond node/python/rust/go, an unparsable
                 manifest or lockfile, or a lockfile found only below the root).
                 FAIL: at least one detected ecosystem has no lockfile, has one that is not tracked, or
                 has one whose declared dependencies omit manifest dependencies.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no ecosystem with a recognised package manager is detected; an ecosystem
                 is recognised only from source with no manifest; or git could not report tracked files.
Evidence to cite A `file` evidence item citing the lockfile path for a missing/untracked finding, or the
                 lockfile path plus the omitted dependency names for a mismatch; for PASS, the tracked
                 lockfile path for each ecosystem.
Absence proof    A "no lockfile" FAIL names every lockfile filename that manager uses and that none was
                 found at any depth; an "untracked" FAIL cites the untracked path directly; a mismatch
                 FAIL lists the specific manifest dependencies the lockfile omits.
Remediation      `pin-execution-environment`
Pitfalls         A lockfile that exists and is tracked but lives in a subdirectory reads `PARTIAL`, not
                 `PASS` — the engine only ever compares the root manifest, so a nested lockfile's
                 consistency is genuinely unverified, not a false negative to argue away.

## EXEC-03 — Non-interactive setup path

Why it matters   An agent cannot answer an interactive prompt or provision a database by guessing; with no
                  non-interactive path it is blocked before it can run anything
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         BLOCKER
Engine           `EXEC-03`. First looks for a documented, non-interactive install command (one whose
                 head tool and subcommand the engine recognises, such as `npm install` or `make setup`)
                 inside a fenced block of README/`AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md` — found ⇒
                 `PASS` outright. Failing that, looks for a setup artifact (a devcontainer, a compose
                 file, a Dockerfile, or a `setup`/`bootstrap`/`install`/`dev`/`dev-setup` Makefile or
                 npm-script target) and whether any doc file names it in prose. No ecosystem detected at
                 all ⇒ `UNKNOWN` — with no build manifest there is no provisioning to characterise.
                 Distrust a `FAIL` when the setup instructions live in a doc file outside the four this
                 check reads — verify by reading whatever onboarding doc the repository actually points
                 to before treating the absence as real.
Method           automated
Look for         A fenced install command in README.md, AGENTS.md, CLAUDE.md or CONTRIBUTING.md first;
                 failing that, a devcontainer/compose/Dockerfile/setup-script/setup-target artifact, and
                 whether any of those four docs names it.
Rubric           PASS: a documented non-interactive install command exists, or a setup artifact exists
                 and is named by one of the four doc files.
                 PARTIAL: a setup artifact exists but no doc file names it.
                 FAIL: no documented install command and no setup artifact exist at all.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no ecosystem is detected in the repository at all.
Evidence to cite A `file` evidence item citing the documented command's location for PASS; the
                 undocumented artifact's path(s) for PARTIAL; nothing to cite for FAIL beyond the
                 absence proof.
Absence proof    A FAIL states explicitly that none of the devcontainer, compose file, Dockerfile, setup
                 target/script, or documented install command forms was found, naming the exact file
                 names searched for (the full `_SETUP_FILES` and `_SETUP_TARGETS` lists).
Remediation      `define-command-surface`
Pitfalls         A setup script that exists but is named only by its filename inside a code block that is
                 not itself a shell command (a file tree listing, say) does not count as "documented" —
                 the engine's text-containment check still passes it, so verify the mention is genuinely
                 instructional before trusting a borderline PASS.

## EXEC-04 — Env-var inventory complete

Why it matters   A variable the code needs but nobody wrote down fails at runtime, mid-task, and the agent
                  debugs an environment problem it has no way to see coming
                  ([greenfield-bootstrap/README.md § File Tree — What Gets Created](../../../greenfield-bootstrap/README.md#file-tree--what-gets-created)).
Severity         BLOCKER
Engine           `EXEC-04`. Collects every `${VAR}` reference in shell-family files (`.sh`, `.bash`,
                 `.zsh`, `.fish`, `.ksh`, `.ps1`, `Dockerfile`) and every `os.environ`/`os.getenv`/
                 `process.env`/`ENV[...]`-style reference in source and script files, then subtracts the
                 keys declared in a committed example file (`.env.example`, `.env.sample`,
                 `.env.template`, `env.example`) and a fixed, in-code allow-list of conventional host/CI
                 variables (`CI`, `HOME`, `GITHUB_*`, `VITEST_*`, and the like). This check runs
                 regardless of detected ecosystem — there is no `UNKNOWN` path. Distrust a `FAIL` that
                 names a key your own reading recognises as a CI/host convention the allow-list has not
                 yet caught — verify against `_ENV_ALLOWLIST`/`_ENV_ALLOW_PREFIXES` in
                 `audit/rules/checks/execution.py` before writing a false "missing variable" finding.
Method           automated
Look for         `${VAR}`-style references in shell/`Dockerfile` files, and language-level environment
                 reads in source and script files generally; the keys declared in whichever committed
                 example file exists.
Rubric           PASS: every referenced key not on the allow-list is declared in a committed example
                 file (including the case of no references at all).
                 PARTIAL: not used by this check — any undeclared key fails the whole check.
                 FAIL: at least one referenced, non-allow-listed key is absent from every committed
                 example file.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — the reference scan runs whether or not an ecosystem is detected.
Evidence to cite A `file` evidence item per committed example file read (for PASS, when references
                 exist); for FAIL, the same file list (or "(no example file)" when none exists) plus the
                 missing key names in the finding statement.
Absence proof    A FAIL names every missing key explicitly and states which example file(s), if any, were
                 read and found not to declare them — "(no example file)" when none exists at all is
                 itself the absence proof.
Remediation      `env-inventory-and-secrets`
Pitfalls         A `${PIPELINE_VERSION}`-style template literal inside a `.ts`/`.js` file is never misread
                 as an environment reference — the shell pattern is scoped to shell-family files on
                 purpose — but the same literal inside a `.sh` script is read as one; do not treat a
                 finding against a shell file as a false positive without checking whether the reference
                 is genuinely an environment variable there.

## EXEC-05 — No generated artifacts committed in-tree

Why it matters   An agent that edits a file the build regenerates loses its work silently, often not until
                  the next CI run or review
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         DEGRADER
Engine           `EXEC-05`. Looks at every path the scan already classifies `GENERATED` (including
                 vendored paths) and, of those that are git-tracked, whether its first 20 lines carry a
                 generated-file marker (`@generated`, `do not edit`, `generated by`, `code generated`,
                 `auto-generated`, `autogenerated`, `this file is generated`, case-insensitive). Git
                 unable to report tracked files ⇒ `UNKNOWN` — generated-file state cannot be read without
                 it. No tracked generated path at all, or every one carrying a header, is `PASS`.
                 Distrust a `FAIL` when the header lives past line 20 of the file — verify by reading
                 further into the file before trusting the absence.
Method           automated
Look for         Paths the scan classifies `GENERATED`, limited to those git reports as tracked; the
                 first 20 lines of each for one of the marker phrases above.
Rubric           PASS: no tracked path is classified `GENERATED`, or every tracked `GENERATED` path
                 carries a generated-file header in its first 20 lines.
                 PARTIAL: not used by this check — any header-less tracked generated path fails the
                 whole check.
                 FAIL: at least one tracked `GENERATED` path carries no generated-file header.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: git could not report the repository's tracked files.
Evidence to cite A `file` evidence item per offending path (up to 12) for FAIL; for PASS, the count of
                 tracked generated paths found, with headers.
Absence proof    A FAIL lists every offending tracked path explicitly (up to 12, with the total count
                 stated when there are more), so the missing-header claim is checkable path by path.
Remediation      `untrack-generated` (untrack the path with the owner's yes, or add a generated-file
                 header where the file type carries one; both resolve the check).
Pitfalls         The scan's own `GENERATED` classification, not this check, decides what counts — a
                 hand-written file that merely looks machine-produced (a long data table, say) is not
                 reclassified here; if a finding looks wrong, question the scan's classification, not
                 this check's header search.

## EXEC-06 — Documented commands resolve

Why it matters   An agent runs the documented command literally; a command that does not resolve is the
                  most expensive brownfield trap there is, discovered only after the agent has already
                  acted on it
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         DEGRADER
Engine           `EXEC-06`. Extracts every fenced shell command from README.md, AGENTS.md and CLAUDE.md
                 (deliberately not `docs/**`, whose fences routinely mix languages), joins trailing-`\`
                 line continuations, de-duplicates, skips lines carrying an obvious placeholder marker
                 (`<...>`, `...`, `your-`, `tbd`, `xxx`, `placeholder`), and checks each remaining
                 command's head token against a fixed table of known tools and shell builtins, the
                 command surface's own verbs, `npm`/`pnpm`/`yarn` scripts, Makefile targets, declared
                 package binaries, or a real repository path. This check runs regardless of detected
                 ecosystem — there is no `UNKNOWN` path. Distrust a `FAIL` naming a tool the fixed table
                 does not yet carry — verify the tool is genuinely unresolvable, not merely missing from
                 `_KNOWN_TOOLS` in `audit/rules/checks/execution.py`, before treating the finding as a
                 real documentation defect.
Method           automated
Look for         Fenced shell commands in README.md, AGENTS.md and CLAUDE.md; each one's head token
                 against known tools/builtins, command-surface verbs, package scripts, Makefile targets,
                 declared binaries, and real paths.
Rubric           PASS: every documented command resolves, or no fenced shell command is documented at
                 all.
                 PARTIAL: not used by this check — any one unresolved command fails the whole check.
                 FAIL: at least one documented command's head token names no known tool, verb, script,
                 target, binary, or path.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — the extraction and resolution run unconditionally.
Evidence to cite A `file` evidence item per unresolved command (up to 12), citing the doc file, line
                 number and the command text itself; for PASS, the count of documented commands that
                 resolved.
Absence proof    A FAIL names every unresolved command verbatim with its doc file and line number (up to
                 8 in the summary, up to 12 as evidence), so "does not resolve" is checkable command by
                 command.
Remediation      none in the current catalogue (`catalogue.json` lists no playbook for `EXEC-06`); the
                 fix is specific to the one command named in the finding, so note it inline rather than
                 pointing at a generic playbook.
Pitfalls         A command that mixes a Python snippet inside a fenced ```bash``` block is a documentation
                 defect this check is not chartered to police — the engine reads README/AGENTS.md/
                 CLAUDE.md only for exactly this reason; do not extend the absence search into `docs/**`
                 to manufacture additional findings.

## EXEC-07 — No competing configs for one concern

Why it matters   One concern, one authoritative answer; with two configs for the same concern an agent
                  (or a human) picks whichever result turns up first, which is not the same thing as
                  picking correctly
                  ([Phased-Approach.md § Phase 1: Agentic Bootstrap](../../../brownfield-legacy/Phased-Approach.md#phase-1-agentic-bootstrap-)).
Severity         DEGRADER
Engine           `EXEC-07`. For each of five concerns (lint, format, test, types, security), matches a
                 fixed set of root-level config file globs, plus (for a root `pyproject.toml`) specific
                 `[tool.*]` section headers mapped to the same concerns. Only repository-root configs are
                 counted on purpose, so a monorepo's per-component configs are never mistaken for
                 competition. This check runs regardless of detected ecosystem — there is no `UNKNOWN`
                 path. Distrust a `FAIL` where two matched configs are a deliberate, documented delegation
                 (a `biome.json` that only re-exports to a nested project, say) — verify the files are
                 genuinely two authorities for the same concern, not one authority and one pointer to it.
Method           automated
Look for         Root-level files matching each concern's glob set; a root `pyproject.toml`'s `[tool.*]`
                 section headers for the same five concerns.
Rubric           PASS: each of the five concerns has at most one matching root config (including zero).
                 PARTIAL: not used by this check — any one concern with more than one config fails the
                 whole check.
                 FAIL: at least one concern has more than one matching root config.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: never — the glob and section-header scan runs unconditionally.
Evidence to cite A `file` evidence item per competing path, grouped by concern, for FAIL; for PASS, the
                 single authoritative config path found for each concern that has one.
Absence proof    A FAIL names every concern with more than one config and lists every competing path
                 found for it, so "competing" is the literal file list, not an inference.
Remediation      `untrack-generated` (detection and documentation only: keep one config per concern and
                 document any deliberate delegation; the playbook never deletes a config).
Pitfalls         `biome.json` matches both the `lint` and `format` globs by design (Biome itself combines
                 the two); a repository with only `biome.json` for both concerns is not competition —
                 only a second file matching the same single concern is.
