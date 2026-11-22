# Java

> Follows the anatomy in [`README.md`](README.md). Covers Gradle, with Quarkus notes where Quarkus
> differs. The Maven section is untested and says so. `shipped`, per `run_context.stack_profile`
> ([§4 Shipped versus derived](README.md#4-shipped-versus-derived)).

---

## Detection signals

`facts.json`'s `stack` section already read this: `ecosystems: ["jvm"]` from a `build.gradle`,
`build.gradle.kts` or `pom.xml` anywhere in the tree. `package_managers` reads `maven` from a `pom.xml`
and `gradle` from a `gradle.lockfile` only, so a Gradle build without dependency locking leaves it empty —
state that plainly rather than reading an empty value as "no build tool." `ci_providers` reads
`.github/workflows/*.yml` whether or not a workflow actually runs a Gradle or Maven verb (see Pitfalls).
Gradle has no single manifest name: `build.gradle` (Groovy DSL) and `build.gradle.kts` (Kotlin DSL) are
both read; a `gradlew`/`gradlew.bat` pair signals the wrapper.

## Command-surface map

Gradle has no verb table (unlike npm scripts): a verb resolves only when the build file registers a task of that
exact name (`tasks.register('format', …)`, `task format { … }`), always invoked through the committed wrapper
(`./gradlew <task>`), never a bare `gradle`. Two verbs are the exception: `test` and `check` resolve for free when
the build applies a plugin that registers them (`java`, `java-library`, `application`, `groovy`, `scala`, `war`, the
Kotlin JVM plugin, or `io.quarkus`, which applies `java` itself) — but that lifecycle `check` is not read as this
pack's `check` (`CMD-03`'s point: a build tool's own gate is not a second definition of the seven-verb `check`).
`format`, `format:check`, `lint`, `typecheck` and `security` have no Gradle lifecycle equivalent at all and must be
registered as named tasks, usually by a plugin (Spotless for `format`/`format:check`, Checkstyle or PMD for `lint`,
the OWASP Dependency-Check plugin for `security`; the reference repository registers all five, see Verified).
`typecheck` has no idiom in Java: the compiler's own type checking runs inside `compileJava`, which no verb name
surfaces on its own.

## Tooling options

Formatter: Spotless (`com.diffplug.spotless`), with Google Java Format or an Eclipse config as its
backing formatter — the reference repository uses an Eclipse config. Linter: Checkstyle or PMD, run through their
own Gradle tasks (`checkstyleMain`, `pmdMain`) — again a named-task registration, not a lifecycle verb;
SpotBugs is a static-analysis alternative. Type checker: none separate from the compiler; `javac`'s own
`-Xlint` flags are the closest analogue and are not a distinct verb. Test runner: JUnit 5 through
Gradle's built-in `test` task (`useJUnitPlatform()` in the build file). Dependency scanner: the OWASP
Dependency-Check Gradle plugin (`org.owasp.dependencycheck`), registering `dependencyCheckAnalyze` — a
task name that does not match `security` literally, so a repository applying the plugin still reads
`CMD-01` `FAIL` for that verb unless a `security` task delegates to it (see Pitfalls). Hook manager: none
is standard; a committed `.githooks/` with `core.hooksPath` set by a build task, or lefthook (no JVM plugin
needed). Commit rule: a `commit-msg` script or lefthook stage, with
the same script run over the pull request's commits in CI (`TOOL-06`). Branch guard (`TOOL-07`): a
`git branch --show-current` check in `.githooks/pre-commit` or a lefthook `pre-commit` command. Dependency updates:
Dependabot
`package-ecosystem: gradle` or `maven`; Renovate's `gradle` and `maven` managers. Language-server inputs
(`register-index`, advisory): the Gradle or Maven build with its wrapper; nothing more.

## Execution determinism

The Gradle wrapper (`gradlew`, `gradlew.bat`, `gradle/wrapper/gradle-wrapper.properties`,
`gradle/wrapper/gradle-wrapper.jar`, all git-tracked) pins the exact Gradle version through
`distributionUrl` — the wrapper is this stack's `EXEC-01` pin, not a language-version file. A Java
toolchain block (`java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }`) pins the JDK
version read by the build itself; its absence leaves the JDK to whatever `JAVA_HOME` resolves to, which
`EXEC-01` cannot see from the manifest alone. Gradle has no project-level lockfile analogous to
`package-lock.json` by default: dependency locking is an opt-in feature
(`dependencyLocking { lockAllConfigurations() }`, writing `gradle.lockfile` files). `EXEC-02` recognises
`gradle.lockfile`, at any depth, as the one lockfile name for `jvm`, so a Gradle build without it reads
`FAIL` for that check. With it, the check reads `PARTIAL`: the engine does not compare a `gradle.lockfile` with
the build file.
Tool versions (`EXEC-08`) are usually Gradle or Maven plugins in the build file, which Dependabot reads, so the
check fires here only on an `npx` or `uvx` call with a typed version in a runner file or workflow.

## CI idiom

GitHub Actions is the provider that `ci_providers` detects from workflow file presence alone; a repository
can carry workflow files that never invoke a build verb (see Pitfalls), so presence is not proof of a
build gate. The idiomatic job is `actions/checkout`, `actions/setup-java` with `distribution` and
`java-version` pinned, Gradle's own dependency cache (`actions/setup-java`'s `cache: gradle` input, or
`gradle/actions/setup-gradle`), then `./gradlew check` (never a bare `gradle check`, which bypasses the
pinned wrapper version). Workflow lint (`CI-05`): actionlint from a Gradle task, `.githooks/` or lefthook.
Dependency audit (`TOOL-04`): a `security` job that runs `./gradlew security`, beside the `check` job.
Release provenance (optional, `add-repo-hygiene` step 6): `actions/attest` on the published jars, beside the
signatures Maven Central asks for.

## Baseline / ratchet

Checkstyle and PMD both support a suppressions file (`config/checkstyle/suppressions.xml`,
`config/pmd/exclude.xml`) that silences existing violations while a repository migrates; SpotBugs has an
equivalent exclude filter. None of these establish a true "no new violations" ratchet on their own — each
needs an incremental, changed-files-only invocation wired into CI to behave like one, mirroring the
pattern described in `typescript-node.md`'s own Baseline / ratchet section. The reference repository keeps
its counts in a committed JSON file that an `Exec` task (`baselineCheck`) compares; `BASE-01` reads that file.

Coverage: the core `jacoco` plugin gives `jacocoTestReport` and `jacocoTestCoverageVerification` (a
`violationRules` `minimum` is the floor). Quarkus `@QuarkusTest` classes need `io.quarkus:quarkus-jacoco`
(version from the platform BOM); Gradle's agent alone reports them wrongly low. `BASE-04` reads the floor from a
`build.gradle(.kts)` with `jacocoTestCoverageVerification` and a `minimum`, or from a `pom.xml` whose
`jacoco-maven-plugin` runs `check` with a `<minimum>`, at any depth. The implement playbook
`add-baselines-and-ratchet` covers both.

Prose (`DOC-05`): the `establish-docs-contract` prose check is a stdlib Python script, copied only under a licence
the owner names. It needs Python 3.11 or newer on the developer machine and the CI runner; the Gradle build does not
change. Run it from the docs CI job, or wrap it in a Gradle `Exec` task (`docsProse`) if the team wants one verb.

## Boundaries

A multi-module Gradle build (`settings.gradle`'s `include()` calls) expresses boundaries through each
module's own dependency declarations (`implementation project(':core')`); a module that is not listed as a
dependency cannot see another's `api`-visible classes at compile time, which is Gradle's own enforcement,
not a lint rule. The reference repository is single-module (`rootProject.name` alone, no `include()`),
so module boundaries are untested here.

## Engine coverage

Reliable as the engine reads it: `CMD-01` for `test`/`check` through the lifecycle-plugin path, and for
any task the build file registers by a literal `tasks.register(...)`/`task <name> {...}` line; `EXEC-01`
reading `gradle-wrapper.properties`'s `distributionUrl`. Needs independent agent verification: `CMD-01` for
`format`, `format:check`, `lint`, `typecheck` and `security`, none of which Gradle gives for free — a
`FAIL` here usually means "not registered as a task," which is accurate, but a repository that wires one of
these through a plugin task with a different name (`dependencyCheckAnalyze` rather than `security`) needs
a human read of the build file to see the gap the engine's literal-name match cannot bridge; `CMD-02`,
which reads a Gradle `check` from the build file: a JVM plugin gives the compile (the typecheck) and
`test`, Spotless or ktlint the format check, and `check.dependsOn` adds the verbs and known tasks it names.
An unknown plugin, a version-catalog alias, `apply from`, subprojects in `settings.gradle` or an unknown
task make a check that still misses a concern `UNKNOWN`; read what those wire into `check` yourself;
`EXEC-02`, which reads only whether a `gradle.lockfile` exists and is tracked. It cannot compare
the lock with the build file, so a tracked lock reads `PARTIAL` at best, never `PASS` — confirm by reading the
build file for a `dependencyLocking` block and the lockfile itself.
`TOOL-01` and `TOOL-02` look for a formatter or linter config file by name; `checkstyle.xml` is the one JVM name.
A Spotless block in the build file or a PMD ruleset under `config/pmd/` therefore reads `PARTIAL` (seen on the
reference repository): read the build file. `TOOL-04` reads `PARTIAL` when `security` is an `Exec` task that calls
a script, because the engine does not follow the script: read the script.

## Pitfalls

A workflow file is not a build gate. `ci_providers` reads `github_actions` from file presence alone, and the
reference repository once shipped four workflows that ran only AI review and triage, never a Gradle verb. Read
what each job runs before you credit a `CI` check. Its `AGENTS.md` then described a Maven, multi-service layout
the repository did not have: a `DOC`-family defect (stale instructions), not an engine false positive. A build
that applies the OWASP plugin but registers no `security` task reads `CMD-01` `FAIL` for that verb, as it does
for `format`, `format:check` and `lint` without a named task. That is the stack's own gap, not a detection miss:
register the tasks (Spotless, Checkstyle or PMD, a `security` task), do not distrust the verdict.

A package named `example`, `samples` or `fixtures` is read as code below a source root,
`src/<source set>/<java|kotlin|scala|groovy>/`. Spring Initializr's default group, `com.example`, is one such
package. The engine sets aside the same names everywhere else: `src/main/resources/templates/`,
`src/test/resources/fixtures/` and a top-level `examples/` folder are carried data, and the report lists them in
`inventory.set_aside`
([engine ADR-0008](../engine/docs/architecture/adrs/0008-what-counts-as-the-repository.md)). Code kept outside
the standard layout is set aside by such a name; check `inventory.set_aside` before you trust a `NAV-02` or `TST`
verdict on it.

## Maven

Untested: no Maven repository is in this pack's corpus; read from the engine's own Maven reader
(`_parse_maven_plugins`, `_maven_lifecycle` in `_common.py`), not checked against a real build.
Detection: `pom.xml` maps to the same `jvm` ecosystem as `build.gradle`, so `facts.json` does not
distinguish the two build tools. Command surface: Maven's lifecycle gives three verbs for free, no
plugin needed — `test` → the `test` phase, `typecheck` → `compile test-compile`, `check` → `verify`,
richer than Gradle's test/check-only pair — invoked through the wrapper (`./mvnw`) when committed.
`format`, `format:check`, `lint` and `security` still need a named plugin, but the engine recognises
three directly by `artifactId`: `spotless-maven-plugin`, `maven-checkstyle-plugin`,
`dependency-check-maven`. `CMD-02` is `UNKNOWN` for a `check` resolved only through `verify`: unlike a
Gradle build, the engine does not read which plugin goals a pom binds to that phase. A real engine gap,
found by reading the check rather than a repository: `EXEC-02`'s lockfile table recognises
only `gradle.lockfile` for `jvm` (`_lockfiles_for` in
`audit/rules/checks/execution/exec_02.py`, fed by `PACKAGE_MANAGERS` in `audit/stack.py`), never a Maven convention,
so a pure-Maven project is still told it is missing `gradle.lockfile` — read the finding's own evidence
before repeating that name.

## Verified

2026-11-20, against the reference repository, `Nistapp/Digital-Assistant-Server` (`dev` at `c1fdcce`), after its
implement runs. It is still a single-module Groovy DSL `build.gradle` on Gradle 8.12.1 through the committed wrapper,
with `io.quarkus` 3.2.10.Final. It now has a Java 21 toolchain block and `dependencyLocking { lockAllConfigurations() }`
with a tracked `gradle.lockfile`. It adds Spotless 8.10.4 (Eclipse config, ratchet from `origin/dev`), PMD 7.29.0
and JaCoCo with `quarkus-jacoco`. It has named tasks for all seven verbs (`format`, `formatCheck`, `lint`, `typecheck`,
`security` as an `Exec` task, and the lifecycle `test` and `check`). Its CI workflow runs Gradle through
`scripts/ci/` with `actions/setup-java` and `cache: gradle`, beside secret, CodeQL, workflow-lint and docs-lint jobs;
hooks are lefthook. Today's engine (ruleset `2026-11-20.1`) gives `CMD-01`, `EXEC-01`, `CI-01`, `CI-05`,
`BASE-01` and `BASE-03` `PASS`; `CMD-02` `UNKNOWN`; and `EXEC-02`, `TOOL-01`, `TOOL-02`, `TOOL-04` and `BASE-04`
`PARTIAL` for the reasons in Engine coverage. Read via the engine on a clean clone of `dev` and by reading
`build.gradle`, `settings.gradle`, `gradle/wrapper/gradle-wrapper.properties` and `.github/workflows/ci.yml`; no
target command was run.

2026-10-13, the first check, against the same repository (`dev` at `7f351b0`), before any implement run: Gradle
8.12.1 via the committed wrapper, Groovy DSL `build.gradle`, plugins `java`, `io.quarkus` (3.2.10.Final) and
`org.owasp.dependencycheck` (9.0.9), no Checkstyle/PMD/Spotless, no Java toolchain block, no `dependencyLocking`
block, single-module (`settings.gradle` sets only `rootProject.name`), four GitHub Actions workflows (all Gemini AI
review/triage, none running a Gradle verb), `AGENTS.md` and `CONVENTIONS.md` present at the root but describing a
Maven/multi-service layout the repository did not have. Read via `tools/facts.py` and direct inspection of
`build.gradle`, `settings.gradle`, `gradle.properties`, `gradle/wrapper/gradle-wrapper.properties`,
`.github/workflows/` and `AGENTS.md`; no target command was run. Tooling options checked against current docs the
same day: dependency locking is opt-in, through a `dependencyLocking { lockAllConfigurations() }` block and
`--write-locks`, per [Gradle's own user guide](https://docs.gradle.org/current/userguide/dependency_locking.html);
the OWASP Dependency-Check Gradle plugin's own task is named `dependencyCheckAnalyze`, not `security`, confirmed
against [the plugin's configuration page](https://github.com/jeremylong/DependencyCheck/blob/main/src/site/markdown/dependency-check-gradle/configuration.md).
The `## Maven` section above is **not** verified against a repository — flagged untested throughout, and the first thing to re-check once a Maven repository joins the corpus.
