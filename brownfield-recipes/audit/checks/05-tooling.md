# Tooling (`TOOL`)

> Follows the anatomy in [`README.md`](README.md). Six checks, all `method: automated`. See
> [Why These Checks §6](../../deterministic-audit/docs/architecture/user-overview/03-why-these-checks.md#6-tooling-tool)
> for the consequence behind this family: a tool that is installed but not reachable through the command
> surface, or configured but not strict, gives an agent false confidence. No MVP playbook covers this
> family yet (S5.2–S5.3 ship seven playbooks, none of them `TOOL`'s); each check's **Remediation** names
> the backlog playbook and says what to create directly in the meantime.

---

## TOOL-01 — Formatter configured

Why it matters   Formatting must be free and non-negotiable, or every diff mixes style with substance and
                  review spends attention on noise
                  ([`brownfield-legacy/Phased-Approach.md` § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `TOOL-01`. Reads a fixed set of formatter config filenames (prettier, black, ruff,
                 dprint, biome, rustfmt, clang-format, and others the engine's own list names, including
                 `pyproject.toml`'s `[tool.black]`/`[tool.ruff]`/`[tool.autopep8]`/`[tool.yapf]` tables and
                 `package.json`'s `"prettier"` key) and resolves the `format` write verb
                 (`audit.rules.checks._common.resolve_verbs`). Both present is `PASS`; either alone is
                 `PARTIAL`; neither, with a recognised ecosystem or runner, is `FAIL`. Distrust a `FAIL` or
                 `PARTIAL` when the project formats through a config file the engine's filename list does
                 not yet carry, or a verb defined on a runner the engine does not resolve — verify by
                 reading the project's own documentation for how formatting is actually invoked.
Method           automated
Look for         The formatter config file itself; the runner manifest's `format` verb and the command it
                 resolves to.
Rubric           PASS: a formatter config file is present and a `format` verb resolves on some runner.
                 PARTIAL: only the config file is present, or only the verb.
                 FAIL: neither is present and the repository has a recognised ecosystem or runner manifest.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem, runner manifest or formatter config exists, so a
                 formatter cannot be ruled out.
Evidence to cite A `file` evidence item citing the config file found, or the runner and resolved `format`
                 command, matching whichever side of the pair is present.
Absence proof    A FAIL cites every runner manifest read as evidence that no `format` verb resolves on any
                 of them, alongside the absence of every config filename the engine's list checked.
Remediation      No MVP playbook yet (backlog: `add-formatter-config`). Add a formatter config file and a
                 `format` write verb on the project's runner so the two are both present and the pair
                 resolves to `PASS`.
Pitfalls         A formatter config with no way to invoke it is not a formatter an agent can run — `PARTIAL`
                 is the correct verdict, not a lenient `PASS`, because the config alone gives no reachable
                 command. Conversely, crediting a bare `format` verb without a config file risks the tool's
                 behaviour drifting with its own version defaults.

## TOOL-02 — Linter configured

Why it matters   A linter catches classes of defect before tests exist to catch them, including
                  regressions an agent introduces that no test yet covers
                  ([`brownfield-legacy/Phased-Approach.md` § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `TOOL-02`. Reads a fixed set of linter config filenames (eslint, biome, ruff, flake8,
                 pylint, golangci-lint, clippy, rubocop, checkstyle, stylelint, phpcs, and others the
                 engine's own list names, including `pyproject.toml`'s `[tool.ruff]`/`[tool.pylint]`/
                 `[tool.flake8]` tables and `package.json`'s `"eslintConfig"` key) and resolves the `lint`
                 read-only verb. Both present is `PASS`; either alone is `PARTIAL`; neither, with a
                 recognised ecosystem or runner, is `FAIL`. Distrust a `FAIL` or `PARTIAL` when the
                 project's linter config or verb lives outside the engine's filename list or resolvable
                 runners — verify by reading the project's own documentation.
Method           automated
Look for         The linter config file itself; the runner manifest's `lint` verb and the command it
                 resolves to.
Rubric           PASS: a linter config file is present and a `lint` verb resolves on some runner.
                 PARTIAL: only the config file is present, or only the verb.
                 FAIL: neither is present and the repository has a recognised ecosystem or runner manifest.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem, runner manifest or linter config exists, so a
                 linter cannot be ruled out.
Evidence to cite A `file` evidence item citing the config file found, or the runner and resolved `lint`
                 command, matching whichever side of the pair is present.
Absence proof    A FAIL cites every runner manifest read as evidence that no `lint` verb resolves on any of
                 them, alongside the absence of every config filename the engine's list checked.
Remediation      No MVP playbook yet (backlog: `add-linter-config`). Add a linter config file and a `lint`
                 read-only verb on the project's runner so the two are both present.
Pitfalls         A `lint` verb that runs the formatter in check mode (`prettier --check`) is not this
                 check's concern and does not earn credit here — `TOOL-02` reads for a dedicated linter
                 config, not any read-only verb that happens to exist under the `lint` name.

## TOOL-03 — Type checker configured, strict

Why it matters   A strict type checker is the cheapest correctness gate available; without it, interface
                  drift between an agent's change and its callers is discovered at runtime instead of at
                  review time
                  ([`brownfield-legacy/Phased-Approach.md` § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `TOOL-03`. For `node`, `python` and `dotnet`, reads the language's strict-mode setting
                 directly: `tsconfig.json`/`jsconfig.json` (`strict`/`checkJs`), `mypy.ini`/`.mypy.ini`/
                 `pyproject.toml`'s `[tool.mypy]`/`setup.cfg`'s `[mypy]` (`strict = true`),
                 `pyrightconfig.json` or `pyproject.toml`'s `[tool.pyright]` (`typeCheckingMode: "strict"`),
                 `.csproj`/`Directory.Build.props`/`.targets` (`<Nullable>enable</Nullable>`), or a
                 resolved `typecheck` verb whose command carries `--strict`. Strict found anywhere is
                 `PASS`; configured but not strict is `PARTIAL`; a `node`/`python`/`dotnet` ecosystem with
                 neither is `FAIL`. An ecosystem this table has no strict-config concept for at all (go,
                 rust, jvm, ruby, php) is `UNKNOWN` — the engine never invents a type checker for an
                 ecosystem that has none. Distrust a `FAIL` when the project enables strictness through a
                 config key or file the engine's readers do not parse — verify by reading the actual
                 config file.
Method           automated
Look for         The language's own strict-mode config key, read directly rather than inferred from the
                 file's mere presence; for a mixed-ecosystem repository, every file the engine's reader
                 checks, not just the first one found.
Rubric           PASS: at least one strict-mode signal is found (`tsconfig.json: strict`, mypy/pyright
                 strict, `<Nullable>enable</Nullable>`, or a `typecheck` verb with `--strict`).
                 PARTIAL: a type-check configuration exists but none of it is strict.
                 FAIL: the ecosystem is `node`, `python` or `dotnet` and no type-check configuration exists
                 at all.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no strict-config signal is found and the detected ecosystem is one this
                 pack has no strict-config concept for (go, rust, jvm, ruby, php), so type-checking cannot
                 be judged either way.
Evidence to cite A `file` evidence item per config file read, citing the exact key or file (`tsconfig.json:
                 strict`, `mypy.ini`, `pyrightconfig.json`, `foo.csproj:Nullable`) that decided strict or
                 non-strict.
Absence proof    A FAIL cites every runner manifest and detected ecosystem as the evidence that no
                 type-check configuration of any kind was found for it.
Remediation      No MVP playbook yet (backlog: `enable-strict-typecheck`). Turn on strict mode
                 (`tsconfig.json` `strict: true`, mypy/pyright `strict = true` /
                 `typeCheckingMode: "strict"`, or `.NET` `<Nullable>enable</Nullable>`) so the checker's
                 findings can be trusted.
Pitfalls         `UNKNOWN` for go, rust, jvm, ruby or php is not a lesser result than `PASS` — these
                 ecosystems have their own type-safety story (the compiler itself, for go/rust/jvm) that
                 this check does not model; do not read an `UNKNOWN` here as a gap to close by inventing a
                 config file the ecosystem has no concept of.

## TOOL-04 — Dependency / security scan verb

Why it matters   Third-party risk is real and agents add dependencies; without a scan, a vulnerability can
                  enter through the very change an agent just made
                  ([`brownfield-legacy/Phased-Approach.md` § Activities](../../../brownfield-legacy/Phased-Approach.md#activities)).
Severity         DEGRADER
Engine           `TOOL-04`. Resolves every verb on every runner and tests each resolved command against a
                 fixed list of dependency-audit invocations (`npm`/`pnpm`/`yarn`/`bun audit`, `pip-audit`,
                 `safety check`, `osv-scanner`, `cargo audit`, `govulncheck`, `snyk`, `trivy`, `grype`,
                 `bundler-audit`, `composer audit`, `audit-ci`, `dotnet list package --vulnerable`, and
                 others the pattern list names). The verb is evidence; the engine never runs it (that is
                 Tier C, opt-in only). Any resolved verb matching is `PASS`; a `security` verb that resolves
                 to something else is `PARTIAL`; no match at all, with a recognised ecosystem or runner, is
                 `FAIL`. Distrust a `FAIL` or `PARTIAL` when the audit tool used is one the pattern list
                 does not yet name — verify by reading the resolved command directly.
Method           automated
Look for         Every verb's resolved command text, not only `security`'s — the audit invocation can sit
                 on any verb the runner exposes.
Rubric           PASS: at least one resolved verb's command matches a known dependency-audit invocation.
                 PARTIAL: a `security` verb resolves but its command does not match any known audit
                 invocation.
                 FAIL: no verb resolves to a dependency-audit invocation and the repository has a
                 recognised ecosystem or runner manifest.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem, runner manifest or dependency-audit verb exists, so
                 a dependency scan cannot be ruled out.
Evidence to cite A `command` evidence item citing the matching verb and its resolved command text, or, for
                 `PARTIAL`, the `security` verb's own non-matching command.
Absence proof    A FAIL cites every runner manifest read as the evidence that no verb on any of them
                 resolves to a known dependency-audit invocation.
Remediation      No MVP playbook yet (backlog: `add-dependency-audit`). Add a dependency-audit verb (`npm
                 audit`, `pip-audit`, `osv-scanner`, `cargo audit`, `govulncheck`, `snyk`) on `security` or
                 another resolvable verb.
Pitfalls         The audit tool does not have to live on the `security` verb by name — a `test` or `check`
                 verb that happens to run `npm audit` as one of its steps still earns `PASS`; read every
                 resolved command before concluding the repository has no dependency scan at all.

## TOOL-05 — Local hook chain active

Why it matters   Enforcement must exist where an agent actually works, not only downstream in CI; a rule
                  that lives only in CI is a rule an agent cannot honour before it commits
                  ([greenfield-bootstrap/README.md § 2.3 Git Hooks](../../../greenfield-bootstrap/README.md#23-git-hooks--husky--lint-staged--commitlint)).
Severity         DEGRADER
Engine           `TOOL-05`. The presence of `.pre-commit-config.yaml`, `lefthook.yml`/`.yaml`, or a
                 declared `core.hooksPath` counts as wired directly. `.githooks/*` or `.husky/*` present
                 without being referenced is configured but not wired; `.husky/*` is wired only when a
                 `prepare`/install script in `package.json` actually invokes `husky`
                 (`audit.stack.extract_npm_scripts`). Wired is `PASS`; configured-but-unwired is `PARTIAL`;
                 neither, with a detected ecosystem, is `FAIL`. Distrust a `FAIL` when the project wires
                 hooks through a mechanism the engine's fixed list does not check (a custom `.git/hooks`
                 script committed and symlinked by a setup step) — verify by reading the project's own
                 setup documentation.
Method           automated
Look for         The hook-manager config file or `core.hooksPath` setting itself; for `.husky/`, the
                 `package.json` script that would actually invoke it.
Rubric           PASS: a hook chain is wired (`.pre-commit-config.yaml`, `lefthook.yml`/`.yaml`,
                 `core.hooksPath`, or a referenced `.husky/`).
                 PARTIAL: a hook manager's files exist (`.githooks/`, an unreferenced `.husky/`) but nothing
                 wires them in.
                 FAIL: no hook chain is configured and the repository has a detected ecosystem.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem and no hook configuration exists, so a hook chain
                 cannot be ruled out.
Evidence to cite A `file` evidence item citing the wiring file (`.pre-commit-config.yaml`, the
                 `core.hooksPath` entry, or the referencing `package.json` script), or, for `PARTIAL`, the
                 unwired hook directory found.
Absence proof    A FAIL cites every runner manifest or detected ecosystem signal as the evidence that no
                 hook-manager file, `core.hooksPath` entry, or referenced `.husky/` was found.
Remediation      No MVP playbook yet (backlog: `wire-local-hooks`). Adopt a hook manager (pre-commit,
                 lefthook, husky) and wire it — set `core.hooksPath`, add a `prepare`/install script, or
                 commit a `.pre-commit-config.yaml` — so checks run before a commit, not only in CI.
Pitfalls         A `.husky/` directory with files in it is not itself evidence of wiring — husky only runs
                 once `npm install` (or an equivalent) has executed its `prepare` script; a repository that
                 committed the directory but never wired the install step is `PARTIAL`, not `PASS`.

## TOOL-06 — Commit convention enforced

Why it matters   Release automation reads commit messages; without an enforced convention, version bumps
                  and changelog generation silently stop working
                  ([greenfield-bootstrap/README.md § 2.3 Git Hooks](../../../greenfield-bootstrap/README.md#23-git-hooks--husky--lint-staged--commitlint)).
Severity         COSMETIC
Engine           `TOOL-06`. Reads for a commitlint config file (`commitlint.config.*`, `.commitlintrc*`, or
                 `package.json`'s `"commitlint"` key), a `commit-msg` hook file under `.husky/` or
                 `.githooks/`, or a `commit-msg`/`commitlint`/`conventional` reference inside
                 `.pre-commit-config.yaml`/`lefthook.yml`/`.yaml`. Any found is `PASS`; none found, with a
                 detected ecosystem or any hook wiring already present, is `FAIL`. Distrust a `FAIL` when
                 the convention is enforced through a server-side hook or a CI-only check this check does
                 not read (CI enforcement is `TOOL-06`'s own blind spot, not a reason to call the finding
                 wrong without checking CI first) — verify by reading the CI workflow.
Method           automated
Look for         The commitlint config file or `package.json` key; the hook files under `.husky/` and
                 `.githooks/`; the hook-manager config's own text for a commit-message stage.
Rubric           PASS: a commitlint config, a `commit-msg` hook file, or an equivalent pre-commit/lefthook
                 stage is found.
                 PARTIAL: not used by this check (the engine's outcome is binary: the rule exists locally
                 or it does not).
                 FAIL: none of the above is found and the repository has a detected ecosystem, or any hook
                 chain (wired or merely configured) is already present.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem and no hook configuration exists at all, so a commit
                 convention cannot be judged either way.
Evidence to cite A `file` evidence item citing the commitlint config, the `commit-msg` hook file, or the
                 hook-manager config line that matched.
Absence proof    A FAIL cites every runner manifest or detected ecosystem signal as the evidence that no
                 commitlint config, `commit-msg` hook, or equivalent stage was found.
Remediation      No MVP playbook yet (backlog: `enforce-commit-convention`). Add a commitlint config or a
                 `commit-msg` hook so commit messages follow one convention that release automation can
                 parse.
Pitfalls         `COSMETIC` severity means this check never raises a repository's audit to BLOCKER on its
                 own — do not treat a `TOOL-06` `FAIL` as equivalent in urgency to a `DEGRADER` finding
                 elsewhere in this family.
