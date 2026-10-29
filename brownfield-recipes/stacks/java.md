# Java

> Follows the anatomy in [`README.md`](README.md). Covers Gradle, with a Quarkus section under its own
> heading (§1 there). The Maven section is untested and says so. `shipped`, per `run_context.stack_profile`
> (DP §5.6).

---

## Detection signals

`facts.json`'s `stack` section already read this: `ecosystems: ["jvm"]` from a `build.gradle`,
`build.gradle.kts` or `pom.xml` anywhere in the tree; the engine has no `package_managers` signal for
Gradle or Maven, so that field is empty for this stack regardless of the build tool used —
state that plainly rather than reading an empty value as "no build tool." `ci_providers` reads
`.github/workflows/*.yml` whether or not a workflow actually runs a Gradle or Maven verb (see Pitfalls).
Gradle has no single manifest name: `build.gradle` (Groovy DSL) and `build.gradle.kts` (Kotlin DSL) are
both read; a `gradlew`/`gradlew.bat` pair signals the wrapper.

## Command-surface map

Gradle has no verb table (unlike npm scripts): a verb resolves only when the build file registers a task
of that exact name (`tasks.register('format', …)`, `task format { … }`), always invoked through the
committed wrapper (`./gradlew <task>`), never a bare `gradle`. Two verbs are the exception: `test` and
`check` resolve for free when the build applies a plugin that registers them (`java`, `java-library`,
`application`, `groovy`, `scala`, `war`, the Kotlin JVM plugin, or `io.quarkus`, which applies `java`
itself) — but that lifecycle `check` is not read as this pack's `check` (`CMD-03`'s point: a build tool's
own gate is not a second definition of the seven-verb `check`). `format`, `format:check`, `lint`,
`typecheck` and `security` have no Gradle lifecycle equivalent at all and must be registered as named
tasks, usually by a plugin (Spotless for `format`/`format:check`, Checkstyle or PMD for `lint`, the OWASP
Dependency-Check plugin for `security` — none of these were seen in the one repository checked; see
Pitfalls). `typecheck` has no idiom in Java: the compiler's own type checking runs inside `compileJava`,
which no verb name surfaces on its own.

## Tooling defaults

Formatter: Spotless (`com.diffplug.spotless`), with Google Java Format or an Eclipse config as its
backing formatter — not seen in the one repository checked. Linter: Checkstyle or PMD, run through their
own Gradle tasks (`checkstyleMain`, `pmdMain`) — again a named-task registration, not a lifecycle verb;
SpotBugs is a static-analysis alternative. Type checker: none separate from the compiler; `javac`'s own
`-Xlint` flags are the closest analogue and are not a distinct verb. Test runner: JUnit 5 through
Gradle's built-in `test` task (`useJUnitPlatform()` in the build file). Dependency scanner: the OWASP
Dependency-Check Gradle plugin (`org.owasp.dependencycheck`), registering `dependencyCheckAnalyze` — a
task name that does not match `security` literally, so a repository applying the plugin still reads
`CMD-01` `FAIL` for that verb unless a `security` task delegates to it (see Pitfalls).

## Execution determinism

The Gradle wrapper (`gradlew`, `gradlew.bat`, `gradle/wrapper/gradle-wrapper.properties`,
`gradle/wrapper/gradle-wrapper.jar`, all git-tracked) pins the exact Gradle version through
`distributionUrl` — the wrapper is this stack's `EXEC-01` pin, not a language-version file. A Java
toolchain block (`java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }`) pins the JDK
version read by the build itself; its absence leaves the JDK to whatever `JAVA_HOME` resolves to, which
`EXEC-01` cannot see from the manifest alone. Gradle has no project-level lockfile analogous to
`package-lock.json` by default: dependency locking is an opt-in feature
(`dependencyLocking { lockAllConfigurations() }`, writing `gradle.lockfile` files) that `EXEC-02`'s
three-lockfile-name list does not recognise, so an unlocked Gradle build reads `UNKNOWN`, not `FAIL`, for
that check (see Pitfalls).

## CI idiom

GitHub Actions is the provider that `ci_providers` detects from workflow file presence alone; a repository
can carry workflow files that never invoke a build verb (see Pitfalls), so presence is not proof of a
build gate. The idiomatic job is `actions/checkout`, `actions/setup-java` with `distribution` and
`java-version` pinned, Gradle's own dependency cache (`actions/setup-java`'s `cache: gradle` input, or
`gradle/actions/setup-gradle`), then `./gradlew check` (never a bare `gradle check`, which bypasses the
pinned wrapper version).

## Baseline / ratchet

Checkstyle and PMD both support a suppressions file (`config/checkstyle/suppressions.xml`,
`config/pmd/exclude.xml`) that silences existing violations while a repository migrates; SpotBugs has an
equivalent exclude filter. None of these establish a true "no new violations" ratchet on their own — each
needs an incremental, changed-files-only invocation wired into CI to behave like one, mirroring the
pattern described in `typescript-node.md`'s own Baseline / ratchet section. Not seen in the one repository
checked; `BASE-01` reads `FAIL` or `UNKNOWN` there, not verified further here.

## Boundaries

A multi-module Gradle build (`settings.gradle`'s `include()` calls) expresses boundaries through each
module's own dependency declarations (`implementation project(':core')`); a module that is not listed as a
dependency cannot see another's `api`-visible classes at compile time, which is Gradle's own enforcement,
not a lint rule. The one repository checked is single-module (`rootProject.name` alone, no `include()`),
so module boundaries are untested here.

## Engine coverage

Reliable as the engine reads it: `CMD-01` for `test`/`check` through the lifecycle-plugin path, and for
any task the build file registers by a literal `tasks.register(...)`/`task <name> {...}` line; `EXEC-01`
reading `gradle-wrapper.properties`'s `distributionUrl`. Needs independent agent verification: `CMD-01` for
`format`, `format:check`, `lint`, `typecheck` and `security`, none of which Gradle gives for free — a
`FAIL` here usually means "not registered as a task," which is accurate, but a repository that wires one of
these through a plugin task with a different name (`dependencyCheckAnalyze` rather than `security`) needs
a human read of the build file to see the gap the engine's literal-name match cannot bridge; `CMD-02`,
which is `UNKNOWN` outright whenever `check` resolves only through the Gradle/Maven lifecycle path, by the
engine's own documented rule, so this pack's check-composition question is never answered for an
unmodified Gradle build and needs the agent's own read of what plugins (and their tasks) `check` actually
depends on; `EXEC-02`, which recognises no Gradle lockfile convention at all, so `UNKNOWN` here means
"the engine cannot see dependency locking," not "there is none" — confirm by reading the build file for a
`dependencyLocking` block.

## Pitfalls

The one repository checked ships four GitHub Actions workflows, all of which run a Gemini Code Assist
action (PR review, CLI, issue triage) and none of which runs `./gradlew check`, `./gradlew test`, or any
other build verb — `ci_providers` reads `github_actions` correctly from file presence, but a human read
confirms there is no build-verifying CI gate at all, a real finding this pack's CI checks must surface
rather than credit on file presence alone. The repository's own `AGENTS.md` documents a command surface
(`mvn verify`, `mvn test`, subdirectories `quarkus-app` and `embedding-service`) that does not match the
actual repository layout at all (a single-module Gradle/Quarkus build at the root, no `pom.xml`, no
`quarkus-app` or `embedding-service` directory) — a genuine `DOC`-family defect (stale, contradicted
instructions), not an engine false positive, and a sharp illustration of why `DOC`'s checks read the
instruction file's content, not just its presence. No formatter, linter or dependency-scanner task is
registered by name anywhere in the build file beyond the OWASP plugin's own default task name
(`dependencyCheckAnalyze`), so `CMD-01` correctly reads `FAIL` for `format`, `format:check`, `lint` and
`security` — this is the stack's own gap, not a detection miss, and the remediation is to register the
missing tasks (Spotless, Checkstyle, a `security` task that depends on `dependencyCheckAnalyze`), not to
distrust the verdict.

## Maven

Untested: no Maven repository is in this pack's corpus; read from the engine's own Maven reader
(`_parse_maven_plugins`, `_maven_lifecycle` in `_common.py`), not checked against a real build.
Detection: `pom.xml` maps to the same `jvm` ecosystem as `build.gradle`, so `facts.json` does not
distinguish the two build tools. Command surface: Maven's lifecycle gives three verbs for free, no
plugin needed — `test` → the `test` phase, `typecheck` → `compile test-compile`, `check` → `verify`,
richer than Gradle's test/check-only pair — invoked through the wrapper (`./mvnw`) when committed.
`format`, `format:check`, `lint` and `security` still need a named plugin, but the engine recognises
three directly by `artifactId`: `spotless-maven-plugin`, `maven-checkstyle-plugin`,
`dependency-check-maven`. `CMD-02` is `UNKNOWN` for a `check` resolved only through `verify`, the same
rule as Gradle. A real engine gap, found by reading the check rather than a repository: `EXEC-02`'s
lockfile table recognises only `gradle.lockfile` for `jvm`, never a Maven convention, so a pure-Maven
project is still told it is missing `gradle.lockfile` — read the finding's own evidence before repeating
that name.

## Verified

2026-10-13, against the Digital-Assistant-Server (`/home/kc/Projects/UDAN/Digital-Assistant-Server`,
`dev` at `7f351b0`): Gradle 8.12.1 via the committed wrapper, Groovy DSL `build.gradle`, plugins `java`,
`io.quarkus` (3.2.10.Final) and `org.owasp.dependencycheck` (9.0.9), no Checkstyle/PMD/Spotless, no Java
toolchain block, no `dependencyLocking` block, single-module (`settings.gradle` sets only
`rootProject.name`), four GitHub Actions workflows (all Gemini AI review/triage, none running a Gradle
verb), `AGENTS.md` and `CONVENTIONS.md` present at the root but describing a Maven/multi-service layout
the repository does not have. Read via `tools/facts.py` and direct inspection of `build.gradle`,
`settings.gradle`, `gradle.properties`, `gradle/wrapper/gradle-wrapper.properties`, `.github/workflows/`
and `AGENTS.md`; no target command was run. Tooling defaults checked against current docs the same day:
dependency locking is opt-in, through a `dependencyLocking { lockAllConfigurations() }` block and
`--write-locks`, per [Gradle's own user guide](https://docs.gradle.org/current/userguide/dependency_locking.html);
the OWASP Dependency-Check Gradle plugin's own task is named `dependencyCheckAnalyze`, not `security`, confirmed
against [the plugin's configuration page](https://github.com/jeremylong/DependencyCheck/blob/main/src/site/markdown/dependency-check-gradle/configuration.md).
The `## Maven` section above is **not** verified against a repository — flagged untested throughout, and the first thing to re-check once a Maven repository joins the corpus.
