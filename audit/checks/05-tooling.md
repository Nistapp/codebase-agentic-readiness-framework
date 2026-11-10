# Tooling (`TOOL`)

> Follows the anatomy in [`README.md`](README.md). Seven checks, all `method: automated`. See
> [Why These Checks §6](../engine/docs/architecture/user-overview/03-why-these-checks.md#6-tooling-tool)
> for the consequence behind this family: a tool that is installed but not reachable through the command
> surface, or configured but not strict, gives an agent false confidence. TOOL-01 to TOOL-04 are remediated
> by `configure-quality-tools`; TOOL-05 to TOOL-07 are remediated by `add-hooks-and-commit-rules`.

---

## TOOL-01 — Formatter configured

Why it matters   Formatting must be free and non-negotiable, or every diff mixes style with substance and
                  review spends attention on noise
                  ([`docs/framework/phased-approach.md` § Activities](../../docs/framework/phased-approach.md#activities)).
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
Remediation      `configure-quality-tools`
Pitfalls         A formatter config with no way to invoke it is not a formatter an agent can run — `PARTIAL`
                 is the correct verdict, not a lenient `PASS`, because the config alone gives no reachable
                 command. Conversely, crediting a bare `format` verb without a config file risks the tool's
                 behaviour drifting with its own version defaults.

## TOOL-02 — Linter configured

Why it matters   A linter catches classes of defect before tests exist to catch them, including
                  regressions an agent introduces that no test yet covers
                  ([`docs/framework/phased-approach.md` § Activities](../../docs/framework/phased-approach.md#activities)).
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
Remediation      `configure-quality-tools`
Pitfalls         A `lint` verb that runs the formatter in check mode (`prettier --check`) is not this
                 check's concern and does not earn credit here — `TOOL-02` reads for a dedicated linter
                 config, not any read-only verb that happens to exist under the `lint` name.

## TOOL-03 — Type checker configured, strict

Why it matters   A strict type checker is the cheapest correctness gate available; without it, interface
                  drift between an agent's change and its callers is discovered at runtime instead of at
                  review time
                  ([`docs/framework/phased-approach.md` § Activities](../../docs/framework/phased-approach.md#activities)).
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
Remediation      `configure-quality-tools`
Pitfalls         `UNKNOWN` for go, rust, jvm, ruby or php is not a lesser result than `PASS` — these
                 ecosystems have their own type-safety story (the compiler itself, for go/rust/jvm) that
                 this check does not model; do not read an `UNKNOWN` here as a gap to close by inventing a
                 config file the ecosystem has no concept of.

## TOOL-04 — Dependency / security scan verb

Why it matters   Third-party risk is real and agents add dependencies; without a scan, a vulnerability can
                  enter through the very change an agent just made
                  ([`docs/framework/phased-approach.md` § Activities](../../docs/framework/phased-approach.md#activities)).
Severity         DEGRADER
Engine           `TOOL-04`. Resolves every verb on every runner and tests each resolved command against a
                 fixed list of dependency-audit invocations (`npm`/`pnpm`/`yarn`/`bun audit`, `pip-audit`,
                 `safety check`, `osv-scanner`, `cargo audit`, `govulncheck`, `snyk`, `trivy`, `grype`,
                 `bundler-audit`, `composer audit`, `audit-ci`, `dotnet list package --vulnerable`, and
                 others the pattern list names). The verb is evidence; the engine never runs it (that is
                 Tier C, opt-in only). On the root `Makefile` a verb is followed the way Make runs it:
                 simple variables are expanded (`$(OSV)`, `${OSV}`), and each prerequisite target and each
                 `make <target>` or `$(MAKE) <target>` line is read in turn; a cycle ends the walk, and a
                 `make -C`/`-f` call into another Makefile is not followed. CI is read too: a workflow line
                 that runs a scanner, a runner target whose command runs one (`make security-deps`,
                 `npm run security`), a scanner action (`google/osv-scanner-action`,
                 `actions/dependency-review-action`, `aquasecurity/trivy-action`, `snyk/actions`,
                 `anchore/scan-action`, `pypa/gh-action-pip-audit`), or GitLab's Dependency-Scanning
                 template. A local verb and a CI step is `PASS`; one of the two is `PARTIAL`; a `security`
                 verb that resolves to something else, with no CI step, is `PARTIAL`; no match at all, with
                 a recognised ecosystem or runner, is `FAIL`. Distrust a `FAIL` or `PARTIAL` when the audit
                 tool used is one the pattern list does not yet name — verify by reading the resolved command directly.
Method           automated
Look for         Every verb's resolved command text, not only `security`'s — the audit invocation can sit
                 on any verb the runner exposes — and every CI workflow line.
Rubric           PASS: at least one resolved verb's command matches a known dependency-audit invocation,
                 and a CI step runs a dependency audit.
                 PARTIAL: only a local verb, or only CI, runs a dependency audit; or a `security` verb
                 resolves but runs no known audit and CI runs none.
                 FAIL: neither a verb nor CI runs a dependency audit and the repository has a recognised
                 ecosystem or runner manifest.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem, runner manifest or dependency-audit verb exists, so
                 a dependency scan cannot be ruled out.
Evidence to cite A `command` evidence item citing the matching verb and its resolved command text, and a
                 `file` item for the CI line; for `PARTIAL`, the half that was found and the files searched
                 for the other.
Absence proof    A FAIL cites every runner manifest read as the evidence that no verb on any of them
                 resolves to a known dependency-audit invocation.
Remediation      `configure-quality-tools`
Pitfalls         The audit tool does not have to live on the `security` verb by name — a `test` or `check`
                 verb that happens to run `npm audit` as one of its steps still earns `PASS`; read every
                 resolved command before concluding the repository has no dependency scan at all. The
                 Makefile walk does not read a variable set by a function (`$(shell ...)`, `$(call ...)`),
                 an included file, the environment, or a script the recipe calls; read those by hand
                 before you accept a `PARTIAL`. Dependabot and Renovate open update pull requests; they do
                 not audit, so they never count as the CI half (`HYG-09` owns them). The engine only reads
                 text and stays offline; the target's own `security` verb may need the network, which is
                 fine because `security` is not part of `check`. Whether the CI job runs on pull requests
                 is not read.

## TOOL-05 — Local hook chain active

Why it matters   Enforcement must exist where an agent actually works, not only downstream in CI; a rule
                  that lives only in CI is a rule an agent cannot honour before it commits
                  ([greenfield/README.md § 2.3 Git Hooks](../../greenfield/README.md#23-git-hooks--husky--lint-staged--commitlint)).
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
Remediation      `add-hooks-and-commit-rules`
Pitfalls         A `.husky/` directory with files in it is not itself evidence of wiring — husky only runs
                 once `npm install` (or an equivalent) has executed its `prepare` script; a repository that
                 committed the directory but never wired the install step is `PARTIAL`, not `PASS`.

## TOOL-06 — Commit convention enforced

Why it matters   Release automation reads commit messages; without an enforced convention, version bumps
                  and changelog generation silently stop working
                  ([greenfield/README.md § 2.3 Git Hooks](../../greenfield/README.md#23-git-hooks--husky--lint-staged--commitlint)).
Severity         COSMETIC
Engine           `TOOL-06`. Reads two places. Locally: a commitlint config file (`commitlint.config.*`,
                 `.commitlintrc*`, or `package.json`'s `"commitlint"` key), a `commit-msg` hook file under
                 `.husky/` or `.githooks/`, or a `commit-msg`/`commitlint`/`conventional` reference inside
                 `.pre-commit-config.yaml`/`lefthook.yml`/`.yaml`. In CI (every workflow file of a detected
                 provider): a line that runs commitlint (`npx commitlint`, `wagoid/commitlint-github-action`),
                 `cz check`, `gitlint`, `pre-commit run --hook-stage commit-msg` or `lefthook run commit-msg`; a
                 pull-request title check (`amannn/action-semantic-pull-request`); a repository script that the
                 local `commit-msg` stage also runs; or a runner target (`make commit-lint`, `npm run …`) whose
                 command does one of those. An install line (`@commitlint/cli`) and a comment do not count.
                 Distrust a `PARTIAL` or `FAIL` when CI checks commits through a reusable workflow, a
                 server-side hook or a script the local stage does not name — verify by reading the CI
                 workflow. The engine does not read whether the job runs on pull requests.
Method           automated
Look for         The commitlint config file or `package.json` key; the hook files under `.husky/` and
                 `.githooks/`; the hook-manager config's own text for a commit-message stage; the workflow line
                 that runs the same rule.
Rubric           PASS: a local rule (commitlint config, `commit-msg` hook file or equivalent pre-commit/lefthook
                 stage) and a CI step that checks commit messages or the pull-request title are both found.
                 PARTIAL: only one of the two is found. Local only: `--no-verify` or a missing hook install
                 skips the rule. CI only: an agent learns of a bad subject only after it pushes.
                 FAIL: neither is found and the repository has a detected ecosystem, or any hook chain (wired
                 or merely configured) is already present.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no recognised ecosystem and no hook configuration exists at all, so a commit
                 convention cannot be judged either way.
Evidence to cite A `file` evidence item citing the commitlint config, the `commit-msg` hook file, or the
                 hook-manager config line that matched; for CI only, the workflow line and what it runs.
Absence proof    A FAIL cites every runner manifest or detected ecosystem signal as the evidence that no
                 commitlint config, `commit-msg` hook, equivalent stage or CI step was found.
Remediation      `add-hooks-and-commit-rules`
Pitfalls         `COSMETIC` severity means this check never raises a repository's audit to BLOCKER on its
                 own — do not treat a `TOOL-06` `FAIL` as equivalent in urgency to a `DEGRADER` finding
                 elsewhere in this family.

## TOOL-07 — Local guard against commits to a protected branch

Why it matters   An agent commits on whatever branch is checked out. Without a local guard it learns that the
                  branch is protected only when the push is refused, and then has to move its commits by hand
                  ([greenfield/README.md § 2.3 Git Hooks](../../greenfield/README.md#23-git-hooks--husky--lint-staged--commitlint)).
Severity         COSMETIC
Engine           `TOOL-07`. A guard is pre-commit's `no-commit-to-branch` hook (in `.pre-commit-config.yaml`;
                 its `--branch` and `--pattern` arguments; `main` and `master` when it has no `--branch`), or a
                 hook that reads the current branch (`git symbolic-ref … HEAD`, `git branch --show-current`,
                 `git rev-parse --abbrev-ref HEAD`): a `pre-commit` or `commit-msg` command in
                 `lefthook.yml`/`.yaml` (a `pre-push` command does not stop a commit), or a `pre-commit` or
                 `commit-msg` hook script (`.husky/`, `.githooks/` or any other hook directory). A lefthook
                 guard names the branches in its own command block; a hook script names them anywhere in the
                 file. The branches it must name are the literal ones the declared rules protect (`HYG-11`
                 reads them: `.github/rulesets/`, `.github/settings.yml`, Terraform); `~DEFAULT_BRANCH` and
                 globs are not required. With no declared rules, any guard counts. A `.husky/` guard is
                 wired when a `package.json` script runs `husky`; another hook directory is wired when
                 `core.hooksPath` is set. Distrust a `FAIL` when the hook calls a script that holds the guard
                 (`.husky/pre-commit` running `node scripts/check-branch.js`) — read the script. A guard
                 that reads the branch must also exit non-zero (`exit 1`, `process.exit(1)`, a bare `false`)
                 in its lefthook command block or anywhere in its hook script; `no-commit-to-branch` always
                 does. The exit is not tied to the branch test, so read a script whose only `exit 1` is for
                 another reason.
Method           automated
Look for         `.pre-commit-config.yaml` for `no-commit-to-branch` and its `args`; the `pre-commit` and
                 `commit-msg` stages of `lefthook.yml`; the hook scripts named `pre-commit` and `commit-msg`;
                 the declared rules' branch list (`HYG-11`'s evidence).
Rubric           PASS: a guard in a wired hook chain names every branch the declared rules protect, or any
                 guard is wired and no rules are declared.
                 PARTIAL: a guard exists but its hook chain is not wired (an unreferenced `.husky/`, a
                 `.githooks/` with no `core.hooksPath`); or no wired guard exits non-zero (it reads the
                 branch, prints a warning and lets the commit go ahead); or a wired guard does not name a
                 protected branch.
                 FAIL: a hook chain exists (wired or configured) and no hook in it is a guard.
                 NOT_APPLICABLE: never.
                 UNKNOWN when: no hook chain exists at all; `TOOL-05` owns that finding.
Evidence to cite A `file` evidence item with the line of each guard; for a PARTIAL on coverage, the branches
                 the guard misses.
Absence proof    A FAIL cites the hook files that exist and states that none runs `no-commit-to-branch` or
                 reads the current branch in a `pre-commit` or `commit-msg` stage.
Remediation      `add-hooks-and-commit-rules`
Pitfalls         The guard is a convenience: the server's branch rules are the enforcement, and
                 `git commit --no-verify` skips any hook. Do not read a `TOOL-07` PASS as protection, or a
                 FAIL as an unprotected branch; `HYG-11` is where protection is judged.
