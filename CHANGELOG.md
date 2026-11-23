# Changelog

This page covers the whole repository: the framework documents, the requirements, the audit and implement recipes,
the engine and the repository's own gates. Dates are UTC.

From v0.3.1 on, release-please writes each entry from the Conventional Commit subjects of the release. Do not edit
this file by hand on `dev`: write a clear commit subject instead. How it works:
[`RELEASE_PROCESS.md`](RELEASE_PROCESS.md). Two older histories stay:

- The recipes up to v0.3.0: [`audit/CHANGELOG.md`](audit/CHANGELOG.md).
- The deterministic engine's ruleset revisions (which verdicts moved and why):
  [`audit/engine/docs/reference/changelog.md`](audit/engine/docs/reference/changelog.md).

Paths in entries before v0.3.0 use the old layout. The v0.3.0 entry has a "Moved" table from each old path to its new
one.

## [0.4.2](https://github.com/Nistapp/codebase-agentic-readiness-framework/compare/v0.4.1...v0.4.2) (2026-11-23)


### Features

* **dev:** add golden.py, a byte-identity digest of every shipped output ([ef030ab](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ef030ab0bc49e5ba26c59307457cc597fbaeefb0))
* **dev:** add make gate, every gate CI needs in one command ([a685f9a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a685f9a41baf5227bdf72c4e32ee480d4de7817a))
* **dev:** add make gate, every gate CI needs in one command ([676ce3e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/676ce3edafed572f99f25e76a0c35d66060bd14c))
* **dev:** add make golden, a byte-identity digest of every shipped output ([d7a391a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d7a391af57f23151b70d4331e601e404b948ca26))
* **dev:** add make ruleset-renumber and its docs ([35fc401](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/35fc4014670e20adeba7b0f4b693efd6727b9057))
* **dev:** add make ruleset-renumber for branches that add a ruleset revision ([32a63d1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/32a63d14d866e47cad23c8f596ccc6fd23751414))
* **dev:** add the ruleset renumber tool, check and apply ([185d670](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/185d6705f847f5ec0e2d32b71d25128c15eaabf0))
* **dev:** byte-reproducible release skill zips (RF7.3) ([816b895](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/816b895875410db18430adb76f71a7bb998c01e6))
* **dev:** check that backticked repository paths in recipe pages exist ([b59a37a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b59a37a8888a0b5bbd8938840c7c6ee79956128c))
* **dev:** check that backticked repository paths in recipe pages exist ([ebb76c3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ebb76c3ae6e2d765f9fa82e662fe885a7a35474a))
* **dev:** declare the Checks-column pairs in the consistency map ([e78cfa2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e78cfa2b548d6527479c18dccab968f873ac5262))
* **dev:** declare the Checks-column pairs in the consistency map ([80dc34a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/80dc34a453375984709783bf78f19ad2580853c0))
* **dev:** fail make self-audit when the test trees gain a skip marker ([c447fcb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c447fcb8b44fd62ce311917391aee076df610fe6))
* **dev:** fail make self-audit when the test trees gain a skip marker ([dd148e7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/dd148e70dcca44f58069fc60340e46a88f9d6b9b))
* **dev:** flag broken link edges in the document index ([393f4a5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/393f4a5e9a88f47987115c729d90731ee66815a3))
* **dev:** folder-name match kind in the consistency map ([30f18cd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/30f18cd82fb5075494ea9084e0812f92db5669ab))
* **dev:** generate the check catalogue and scaffold a new check ([6ecb65e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6ecb65ef3d5a8f6e5bf46d4c0aed26f5c646da81))
* **dev:** generate the check catalogue from the engine and an overlay ([ea70c86](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ea70c8679cbaa0ee017066abd282396f93cf44f8))
* **dev:** leave raising-only touches out of the unreviewed pairs (R5) ([aa1a2af](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/aa1a2affec2edf900591499e7a5bdf6d39b16f35))
* **dev:** mark 26 add-only Commits rows as mode add ([523d155](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/523d155e421f69d59b6beaca34f1ab891674593c))
* **dev:** narrow the consistency map's touch inference (R3b, R3c, R4, R6) ([bdcdb7d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bdcdb7d9d55ad5bdc58325f6cb8aa3329d54fdc0))
* **dev:** narrow the consistency map's touch inference (R3b, R3c, R4, R6) ([54a7dc6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/54a7dc6a5ad329ed337efd565b7b95f1dbffe7e4))
* **dev:** quieter index diff for generated files and name-match links ([cffd2cd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/cffd2cd019720c2511b782d89893bd3075c248bd))
* **dev:** quieter index diff for generated files and name-match links ([840b066](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/840b066421372eb204f0e61de3016785619d07d3))
* **dev:** rule R5, add-only moves on monotone reads in the consistency map ([10258ea](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/10258ea0b082232f189a7826a0866367ec1f4527))
* **dev:** scaffold a new engine check with make new-check ([563da90](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/563da90c9f97dcda3538c655de7c825627dea276))
* **dev:** write byte-reproducible skill zips with build_skills --archive ([10c8b45](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/10c8b454c382030a8843a435e587aaee18c7459f))
* **engine:** mark the reads where added text can only raise a verdict ([bc3fa0e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bc3fa0eedf8a764f522962650a3c4a294219681a))
* **engine:** write a neutral provenance.target with --target-label ([f26dcba](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f26dcba84fc036fe5cd255514e24edd84d73f262)), closes [#49](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/49)
* **implement:** accept a base report from another checkout in check_regressions ([77d54b3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/77d54b3779f01d24f051a6fca1404ee35d8fb1bc))
* **implement:** check a theme's diff for weakened gates and unapproved dependencies ([9f70a08](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9f70a08905104c7bc394d7975e814babac9ec4da))
* **implement:** check a theme's diff for weakened gates and unapproved dependencies ([55bcdf4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/55bcdf499be7109909f5a4f8a6054fff57737ba9))
* **implement:** guard the target's history with recorded ref tips (B-14) ([fabd740](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/fabd7409036c6f98156974740a3f983ff818c793))
* **implement:** record the target's ref tips and verify them at theme close ([6091def](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6091def745f7f01b585dbd4403c72facd5975e5b))
* **implement:** refuse done and merged while a theme's lost pass is unaccepted ([8aecb22](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8aecb229b8547434c1ab87e9ef4cfad48478beba))
* **implement:** refuse done and merged while a theme's lost pass is unaccepted ([aadd8bf](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/aadd8bfc9eb51e54e4c0dbebc47aa4f22fafc9e8))
* **implement:** stop a theme that loses a passing check (RF5) ([e76edcb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e76edcb83ff7ee059dafbb0c118fb8ebb8656721))
* **implement:** take a missing base report on a resume (RF5.6) ([5c8aaac](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5c8aaacef5ad47fa4b18ccce44149125f5840ded))
* **progress:** show picks the next theme and the themes to check ([a5dae64](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a5dae64c9a955456c6e33639baff08531ac5632a))
* **progress:** show says the stage and step to go on with ([3e2646f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3e2646fae4b0a0fab8f1a2d7f4c133610552443b))
* **report:** run-engine runs the engine with the intake's flags ([9143027](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9143027fbf2207cb17706ef696e5898507d99a42))
* **report:** status says the next step and its command ([413fd3c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/413fd3c18f167520f4198b9e904bfc1e7c1a1492))
* **tools:** list every pending finding with report.py status --all ([bab43d1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bab43d12f99cefce80006f504edd711aa04d968a)), closes [#24](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/24)
* **tools:** report.py and progress.py say what comes next ([bde1625](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bde162545684e83319541af4ec6f6b37e00627b8))


### Bug fixes

* **audit:** pass the draft's label to facts.py and engine.py ([560ba11](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/560ba111bcdcfedc6f5d4d93d4bb4ddbb83d2f12)), closes [#23](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/23)
* **dev:** build every golden fixture in a temporary git repository ([12500ed](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/12500edf6347945d221c77c11eff5f2b367b9991))
* **dev:** drop script from the NAV-02 kind set of rule R3 ([f6c2bae](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f6c2baeca1a2daee24d2d751d459b5e9285e1b98))
* **dev:** keep modules that share a fixed file in one test shard ([d21ab13](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d21ab135aff31254413ff2aa8eb288677cd557b2))
* **dev:** keep modules that share a fixed file in one test shard ([2a200a7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2a200a7b6938c59b82c1132b1d6f7bbf10a527ce))
* **dev:** key the gate mapping by gate so the secrets scan passes ([d43f74b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d43f74b3fbe62270c8b9758de53c91573f0a1292))
* **dev:** match consistency-map glob places folder by folder ([e26f8e4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e26f8e4ee1d719291c6d8726f955cce381944875))
* **dev:** match consistency-map glob places folder by folder ([e653bc1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e653bc12d3a2502c45117e380a2cd984b09e3435))
* **dev:** restore the space between two phony coverage targets ([8b3b37e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8b3b37e8a017c1dafc8582a262db1bbaae3fc035))
* **dev:** widen the CI-04 read to every place its rubric reads ([ca60b63](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ca60b6393a026f365f5295eb050103002f883f52))
* **dev:** widen the native-baseline move to the files its step names ([7c56108](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7c56108286465c6485f59752067ad3ce9758354c))
* **dev:** widen the native-baseline move to the files its step names ([9be55e3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9be55e3461a1d40df14300972e93df6b57565806))
* **engine:** AGENTS.md pointers in AGT-08, prohibition-only spans in CON-01/02, Claude config and index times in IDX ([44ea4bb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/44ea4bb3921438f44fe820051a3c3b56d2032605))
* **engine:** CI checks read echo text and wrapper scripts; Node test probe finds node_modules/.bin ([b1dd927](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b1dd927b28302cfeec26a434090302de52f28aac))
* **engine:** cite &lt;repository&gt; for a missing CI workflow or test suite ([e793b0d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e793b0dde1f9a886353692c4b59e2d1cd274f655))
* **engine:** cite &lt;repository&gt; for a missing CI workflow or test suite ([95e51e3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/95e51e3dc3db84c281e14c26ff11b429165db9e7)), closes [#194](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/194)
* **engine:** close four gaps in probe output redaction ([a847357](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a84735769c7a8d1f62731d3d061038a5c28b618d))
* **engine:** composer.json as a PHP module; .tool-versions ruby, dotnet, java ([a76978c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a76978c6176990ceab77ac8556d73457260fc90a))
* **engine:** count a tracked pdm.lock as a Python lockfile in EXEC-02 ([00b3578](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/00b3578cbb5806ea6a88ac635ac537cedadccef7))
* **engine:** count a tracked pdm.lock as a Python lockfile in EXEC-02 ([921c343](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/921c343efe140731d4e483586d747324c5a4f3ae))
* **engine:** count Gradle and Maven builds as verb runners only at the root (RF4.9.7.1) ([7b72661](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7b726615f2d8ade8dc357f12ccd34b65b1fc0fab))
* **engine:** count Python methods in NAV-05 with ast ([fbcf4a9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/fbcf4a92f34aac16e21205ba3faece51cdeafd34))
* **engine:** count Python methods in NAV-05 with ast ([dfb9ca5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/dfb9ca590b72b7c8407a3013f1e42d8512fee948))
* **engine:** declare AGT-02's AGENTS.md below a component folder ([6c9fa35](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6c9fa35328b79c60b8e6fb4fd9c80b3aa4649cad))
* **engine:** declare the HYG-08 release-document read as case-folded ([3fc3682](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3fc3682ee0a7f8ee1e9f45069b58b90009787ca5))
* **engine:** evidence and rubric mismatches in HYG-01, EXEC-04, EXEC-03, TST-04, AGT-05 ([5dccc77](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5dccc770d2cfa37129c1876a61e9539742422b05))
* **engine:** fail SEC-01 and SEC-03 on files tracked past an ignore rule ([50f7a75](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/50f7a75ab8ca05d4fd09dfee4ce5f7bc669d5d36))
* **engine:** fail SEC-01 and SEC-03 on files tracked past an ignore rule ([e89b820](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e89b8206641795e9ed16b96d63533f590c9c8d3b))
* **engine:** find an AGT instruction file in a folder by its root path ([905a1a8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/905a1a89f6eca73ea944ff5673ad5ca3736ef2e1))
* **engine:** find an AGT rule file straight in its rules folder ([ace9ce2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ace9ce2e46df024153119f1315135be3964dc2b3))
* **engine:** find harness instruction files in a folder, and require a root AGENTS.md ([d1153bb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d1153bb0ad515fecf096d9a2ef0cf73db69dadaf))
* **engine:** find the root README by any name in every check ([95a8c91](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/95a8c91915f81cbbcaf7d748af80ea34dcbf9986)), closes [#6](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/6)
* **engine:** follow a package script into its command for CMD-02 ([879be6c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/879be6c72c9645ad755e22660123381aa377e669)), closes [#125](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/125)
* **engine:** follow CI wrapper scripts and never pass CI-02 vacuously ([9f01e9d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9f01e9d2288566089e28be45c3f4caf1c011f142)), closes [#14](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/14)
* **engine:** give a mis-cased AGENTS.md a PARTIAL finding, as the rubric says ([9d25b46](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9d25b46bb4b57962c3e9d27d419254a02d236d05))
* **engine:** give a mis-cased AGENTS.md a PARTIAL finding, as the rubric says ([bd5f64f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bd5f64fd6a597bc6ec06ac7e9e2d7b948c0d8d77))
* **engine:** give AGT-01 a finding when AGENTS.md exists only below the root ([b21b3c1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b21b3c1578ddfd6d711f535fc697abbfd14ccccd))
* **engine:** give every verdict a summary and find ignored lockfiles ([8341606](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8341606b5d156af80568dd6a8bb413c7b44b55ed)), closes [#21](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/21)
* **engine:** Go pin from a mise .tool-versions line; refresh the self-audit ([36b5408](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/36b54081a41a4554997a305e5acd6db024eb13d0))
* **engine:** match path globs folder by folder with one shared matcher ([e30f124](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e30f124561824ed0f272384a6b66c7baef38f095))
* **engine:** match path globs folder by folder with one shared matcher ([43c1516](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/43c15162080a3d3aaf5109e56ad7a0a6289582df))
* **engine:** match the HYG-08 and CI-04 read declarations to their checks ([e501915](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e50191515d6e5bfea2ff0527cfa2e9c1471841d8))
* **engine:** name bun, npm, pdm and pip from every file they write ([dc3b008](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/dc3b00844c36e30c7dcbafeb15a8e2efff13c13a)), closes [#205](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/205)
* **engine:** name the Amp harness without the word that makes scanners flag commit ids ([9318862](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9318862d6099988c21c83675d8d2a9d43f73a5d5)), closes [#28](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/28)
* **engine:** put node_modules/.bin on PATH for a package.json test probe ([6333c63](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6333c6336eeb33962567e0d017c5e2340af9178b)), closes [#121](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/121)
* **engine:** raise a PARTIAL finding for each unverified EXEC-02 lockfile ([8a6dcf8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8a6dcf8f6691961e63236bfca83c616e637e4a64))
* **engine:** raise a PARTIAL finding for each unverified EXEC-02 lockfile ([bf3d832](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bf3d83290a608e3ec3b05d60435b6a2aafa5afd7))
* **engine:** read .tool-versions lines for ruby, dotnet and java ([6f0f080](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6f0f0804eb2291253d1e38736950e92679358005))
* **engine:** read ~/.claude.json in IDX-01 and compare index times in IDX-03 ([e484a26](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e484a260576f41ba81ab6054fd8c99049c78c42c)), closes [#16](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/16)
* **engine:** read a component's manifest from its own folder only ([22f28a8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/22f28a8251577200aaf113d21b0d478c32551277))
* **engine:** read a Gradle check from its plugins and dependsOn wiring ([9fe1219](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9fe1219eb2884ff11142653c5b0bb95fc90271eb)), closes [#15](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/15)
* **engine:** read a HYG-01 placeholder marker by where it stands ([1b74bf8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1b74bf81afc109c2abc94bee37f8465dead8a8d3)), closes [#51](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/51)
* **engine:** read a Jest run narrowed by a test file path as a TST-04 fast path ([405ce9f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/405ce9f592258bf09f56d7886cdd181e1c07c51d)), closes [#50](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/50)
* **engine:** read a tracked build/ file as generated only with a sign ([76ea456](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/76ea456b642ed5fdd6c76e44b682f1b29b66d359))
* **engine:** read a tracked build/ file as generated only with a sign ([523f067](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/523f0677bf8244625648d1a4dc17257a81c230fa)), closes [#260](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/260)
* **engine:** read a TST-04 fast path written as an inline code span ([ac87236](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ac8723694b0b2c29485cb9c825689ce77cf84a35)), closes [#123](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/123)
* **engine:** read an AGENTS.md pointer as a pointer in AGT-08 ([3039b40](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3039b402f04ca6a4b80eab8579b817a08f3af892)), closes [#26](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/26)
* **engine:** read an AGT-10 deferral into a dot folder as written ([6097a1e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6097a1e1c3f01f148d865e2a0ffb82e9f23c0bbd))
* **engine:** read an AGT-10 deferral into a dot folder as written ([4b95236](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4b952360e6544edc87f0e6ff8cb62cf9ee88b25a)), closes [#263](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/263)
* **engine:** read an AGT-10 pointer into a dot folder as written ([8695460](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/86954601e72ebf7f7794886f85a7a7ebfff507e2))
* **engine:** read app folders below the root in five checks ([c2b20e5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c2b20e5dea703291af82dac37f8ebea329300f25))
* **engine:** read app folders below the root in five checks ([b73a6c4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b73a6c4e8c622b4c6319487ffe8501959fae88fb)), closes [#7](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/7) [#45](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/45) [#52](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/52) [#56](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/56) [#20](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/20)
* **engine:** read committed build output under dist/ and build/ ([2ac9fc3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2ac9fc326a047bcbe386b5379d5c05c143639f4d))
* **engine:** read committed build output under dist/ and build/ ([89a37dd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/89a37dd2d134375a34d41abd40ad390b95400284))
* **engine:** read compound names and short config values in SEC-02, skip sentinels and badges ([0eff94e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0eff94e2b5496649bb99ebdde8c654083ada008f)), closes [#10](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/10) [#11](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/11)
* **engine:** read coverage scripts, Gradle checks and more fast-path forms in CMD-02 and TST-04 ([91683e0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/91683e0d9d06c7c86f43173058ae9dadf2d3a5e6))
* **engine:** read each composer.json as a PHP module a pin must reach ([3132919](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/313291917222644f8510db54b8a51a59a887b3ef))
* **engine:** read echo text and heredoc bodies in CI steps as text ([ffc2417](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ffc2417f250cd6198ebeddc7f6b49bdbb932f27e)), closes [#122](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/122)
* **engine:** read inline commands and the spec's verb spellings ([50e5b7d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/50e5b7d41cacbc11becfa250672891352bd48d35)), closes [#8](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/8)
* **engine:** read mise's go plugin line as a Go pin ([199d2c0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/199d2c07deb94aeee1a023f9d0eae4894420cec4))
* **engine:** read NuGet's packages.lock.json in EXEC-02 (engine 2b) ([9a86a3b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9a86a3bcca9d6b287df5d5c47f2dd3096d18ec80))
* **engine:** read only prohibitions in a body-opened section for CON-01 and CON-02 ([a2f6cae](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a2f6caebae327fc5a13fd60cceda97f0bcb93b49)), closes [#9](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/9)
* **engine:** read packages below a JVM source root as code, not carried data (engine 1) ([2ed1e64](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2ed1e6458940fa86a731fc6b02e154c90c2288a9))
* **engine:** read Ruby, PHP and .NET manifests as NAV-01 component manifests (engine 2a) ([3d0d26f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3d0d26fd1ef78566c388c22612188274c176f1dd))
* **engine:** read the PHP toolchain pin in EXEC-01 (engine 3) ([872be3c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/872be3cf9da5fa8e0c4955c66fa1c58680311cdb))
* **engine:** redact a credential keyword inside a compound name ([0571d86](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0571d86574bcdb16ecb45ae6a40bea66c8c56c3b))
* **engine:** redact a quoted credential value up to its closing quote ([f416567](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f41656793a831a10c1c26c3513487a0a68d54f7a))
* **engine:** redact a whole PEM private key from probe output ([4198b5b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4198b5b2371f6f14d3288d0d53b4cbdf0d0365cf))
* **engine:** redact Slack tokens, and read them in SEC-02 ([6a4e648](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6a4e64818187b717924f2dee63082c783bb7bd34))
* **engine:** regenerate the cmd-ok-gradle eval expectation and wrap the changed docs ([3b18305](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3b183053c28dd19811f02e7d61cba59e5a02e382))
* **engine:** resolve make targets that pattern rules build in EXEC-06 ([b995056](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b995056e0e1b92a8c0e5978a88a831043fa3694e))
* **engine:** resolve make targets that pattern rules build in EXEC-06 ([e3e4428](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e3e44286eb6efd6bbf53382a7fed8cb67ba51b4c)), closes [#306](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/306)
* **engine:** say when AGT-08's vendor files have no canonical AGENTS.md ([b25cf03](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b25cf03ff072312ce8d8902bc7067a29248f8c57))
* **engine:** SEC-02 reads compound names and short config values, skips sentinels and badges; rename the Amp harness ([050982e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/050982e2d36b268a9a1db66d25555d0aa0ee6666))
* **engine:** stack detection signals and unused verb_runners ([#205](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/205)) ([6234262](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6234262dcc8f2c563b527612002cd2b22978e5bf))
* **engine:** take a component's manifest from its own folder only ([6979203](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6979203a4808e6bf2102efe13a3e418868dbd969))
* **engine:** take the root component's manifest from the root only ([737bbc4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/737bbc4217d4770e332179a32a6add5ed351f83d))
* **engine:** tell shell variables and optional inputs apart in EXEC-04 ([e0bb307](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e0bb307bd0603be56ac0e7448c6c1b9869a8f874)), closes [#13](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/13)
* **engine:** walk with the scoped ignore matcher and keep tracked files ([571d723](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/571d723484f22fb41be2989d46bb0bf5942df9dc)), closes [#179](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/179) [#146](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/146) [#22](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/22)
* **engine:** walk with the scoped ignore matcher; one root README finder ([740e148](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/740e148cc323037d141dabb1309f76c3b8a75abe))
* report and audit tool issues ([#49](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/49), [#23](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/23), [#24](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/24), [#18](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/18)) ([46bc172](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/46bc1724cad34f82e1ab1ecb31b43542de01b090))
* **report:** say that blockers remaining counts checks, and show the BLOCKER findings ([1eb70cb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1eb70cbfc95d3255b1f817ca39656ac474e7eb40))
* **report:** say that blockers remaining counts checks, and show the BLOCKER findings ([f2b9cc7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f2b9cc74ea5c66c76fec6f274357327c8be05c8c))
* **tools:** check cited line ranges and quotes against the file ([18961b8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/18961b8431a64e8a8dc8742eb0087f65c28b9cc5)), closes [#18](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/18)


### Performance

* **ci:** run the test-dev job as two shards ([ef227f5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ef227f593fa83afa256b9d9e43597283a30b03e5))
* **ci:** run the test-dev job as two shards ([3f90401](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3f90401f5706c8c9d216c5dc5d2353f5acba8758))
* **dev:** run the coverage suites at once inside make coverage ([9eab62a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9eab62a9429540f234478cd0f135abc1fbb2b743))
* **dev:** run the coverage suites at once inside make coverage ([b1fa7e4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b1fa7e49faa17e70b828e054a9b12feea4a260a9))
* **dev:** run the slow test suites in shards inside make test ([b476472](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b4764724bf9c8801f6e21fae32c97b4c9824bf5f))
* **dev:** run the slow test suites in shards inside make test ([80dc9f0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/80dc9f06874d5c64966b05eb53052a9fe693d849))


### Documentation

* **audit:** close recipe gaps for unattended runs, probes, clones and secrets ([ba5b7d5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ba5b7d5ceea4e7205e38e6ea97d1c0ce7eed3203)), closes [#25](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/25)
* **audit:** correct the EXEC-02 ignore and PASS-evidence lines ([1eb7c47](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1eb7c47a9f0f20d4e1fe4ff2a541ece345b2cc01))
* **audit:** describe the ast census of NAV-05 ([036b904](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/036b9044c510766ce8ae36366f7b4022d216594e))
* **audit:** drop the undefined code D50 from the A14 rubric note ([3ab917d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3ab917d8dc29ff6c46cdcdc4ffcb5b06b5ea5a88))
* **audit:** fix wrong section pointers in the audit and implement recipes ([136096d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/136096d8b4e6c4071b722ee4497274341577ca39))
* **audit:** keep the AGT-05 check page within its line budget ([e143fd8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e143fd837af22bead8a389074b58bc591767c04f))
* **audit:** keep the AGT-08 page in its line budget and regenerate the map and master list ([d232c10](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d232c10419fb940d69522db29aaf2c19d27322f8))
* **audit:** keep the EXEC-03 Engine text within the line limit ([aa28574](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/aa28574bfa314252a5d29dad89ed971b08e27b50))
* **audit:** link the implicit pointers in the audit recipe and check files ([63c3c44](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/63c3c44bb1b5ef8737a7486dab68221a6a5c5647))
* **audit:** link two audit folder rules to the audit hard rules ([ba895b9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ba895b96bfc8449eb762db91f24013b468580613))
* **audit:** list the new package-manager signals on the stack pages ([b7ff613](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b7ff613f31808dbd4e3ac37d0aa9279d68cb9301)), closes [#205](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/205)
* **audit:** match the scan-engine page to the ecosystem signals ([c7b87b8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c7b87b848678ea608abbdc1709d51826702c3d6f))
* **audit:** match the scan-engine page to the ecosystem signals ([71df70e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/71df70ecef57bfbec8892faedd6e74fe8f99c11c))
* **audit:** re-verify the Java stack profile against today's engine ([4f5f22f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4f5f22f7bfc807955ac4f4dbe932ca076e816ba9)), closes [#29](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/29)
* **audit:** replace the undefined code D29 in the Python stack profile ([f6db912](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f6db912ba5fa0037dd584d50c2da298d2fd93767))
* **audit:** replace the undefined code D46 in the checks README ([441d179](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/441d179d2b30129897cae9c80d08054c7f3490c0))
* **audit:** replace the undefined code D51 with a link to CON-04 ([e7fef4e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e7fef4e34fe8e16b50225b5fb3f9602955f63b9c))
* **audit:** replace the undefined code DP in the check and stack pages ([a1c3802](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a1c38026d9bfc451ce7d44a4ab992849e97823cc))
* **audit:** rewrap the CON-01 engine paragraph to the line limit ([1921728](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/19217284b2151d55938e40b5401af12d9b5421bc))
* **audit:** say where to run the tool commands from ([36f35d4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/36f35d4efe8f658ade054758ffce4816e582413b))
* **audit:** shorten the new CI and TST-02 check page sentences ([28f77ab](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/28f77ab1fa81d03fa18f348f3149fa4dcb89fc59))
* **audit:** shorten the sentences that describe the new CMD-02 and TST-04 reads ([24eb6b9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/24eb6b94cae3c9397abf63cdeb03fa21b26e1ed0))
* **audit:** split the long sentences added to the check pages ([4f633ce](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4f633ce38fdfc239c95774b5f69893e41a2340cd))
* **audit:** state that AGT-08 keeps three findings ([92f343d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/92f343db17fd627b7c659224be557f9ae742acc8))
* **audit:** state that AGT-08 keeps three findings ([5dae8d6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5dae8d6b19641ffdfd37e301ecd7ba624247e5fb))
* **audit:** state the three-line prohibitions rule in the AGT-07 check ([dc2087e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/dc2087e7a895ae6a3897225c5d25e9beb28a5a76))
* **audit:** wrap the CI and TST-02 check page lines at 120 columns ([0712912](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0712912f7ad70ee7a5ac84e651a6918b190a2a78))
* **audit:** wrap the EXEC-01 plugin list on its check page ([46890b0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/46890b099eaabd913614030174b6e012ffa364dd))
* **audit:** wrap the long EXEC-01 pin line ([bd70fc9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bd70fc9a31ca9b94f488a0afa542437d621dfe27))
* **audit:** wrap the SEC-02 engine paragraph at 120 characters ([4cd9840](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4cd9840198d8ba9cf7bd1ff7fd26a7a45b7c5066))
* check the stack tool lists and detect-secrets against tool currency ([ed714f5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ed714f5902f242fa3d65fbbd0f8e98f2f1178071)), closes [#249](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/249)
* **checks:** keep the agent governance page within its line budget ([cf771bc](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/cf771bcebabfab3267ff4518de4b7666cd97028e))
* close implement and audit recipe gaps ([#124](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/124), [#126](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/126), [#25](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/25), [#29](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/29)) ([3189850](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3189850ff9989a93f1708d8eb70cbf74eb13ea59))
* close the readiness leftover issues ([#246](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/246)-[#251](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/251), [#262](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/262)) ([1fd9063](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1fd9063397d70f92e9032ffa30cd5e0bc6fde838))
* **consistency-map:** declare the touches of baselines row 17 ([1c72597](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1c72597e3d0da99aa7ca547d4e9779c73c96ab43))
* **consistency-map:** declare the touches of baselines row 17 ([4f6ce89](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4f6ce89b0f82673d5160e176edb32ca740076824))
* **dev:** add make golden and document the golden digest ([98a6b9f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/98a6b9f009851a48bbb1f1e54000f562a0831c58))
* **dev:** B-16 is enforced by tests, not a tool refusal ([cf1005f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/cf1005f6b96cf36365743d0a1ab6e689b45c4776))
* **dev:** describe the sharded test-dev job ([5cc7530](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5cc7530c4b1bc389853f2c5820fcacd36baab9a4))
* **dev:** document make gate ([4e7af50](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4e7af50481f061521054078c36c2388f7d530356))
* **dev:** note the engine modules that must share a test shard ([95dba10](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/95dba10dc386930058464fe903b730cf2e3f5ba5))
* **dev:** say that make coverage shards too in the test_shard docstring ([96edc24](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/96edc2424c3b10512907e81cfebb33f7744cfe32))
* **dev:** say that make coverage shards too in the test_shard docstring ([217bde7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/217bde766b3321ad71ae13dd26fa78c52f94cfde))
* **engine:** add make security to the engine gate line ([6d1fd8c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6d1fd8c5b3fdd4fd6499c571d6d7d246e4f34c7e))
* **engine:** list the idx-01 and idx-02 fixtures in the fixture README ([070070c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/070070ce4979bfd06f6fef4df3a67848aba45e10))
* **engine:** list what probe redaction hides ([bec13f9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bec13f9b6403029fa4da0c57156bcdfeab0dde7e))
* **engine:** record ruleset 2026-11-20.2 ([86fb576](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/86fb576c948353c435eab2d84a6a724d9394755b))
* **engine:** say runners are root manifests ordered by kind ([07b39a3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/07b39a3d672e4b7bfc40e4a33cb52fbd182faa04))
* **engine:** shorten the sentences of the walk and README notes ([dc6012c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/dc6012c133205e58438dd4221d072a3caee3f00a))
* **engine:** split the Python lockfile sentence on the stack page ([7badd38](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7badd380051befc13ca5d0a4f11ade755565f2b3))
* **engine:** state that only a root manifest is a runner in ADR-0008 ([d34eb6f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d34eb6ff4a405010bff1093118760d17f81204c8))
* **engine:** state the one-module-per-check layout ([edfb0fd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/edfb0fdac7484e01ca8d5ed8fa01334162202cb7))
* **engine:** word two redaction examples so the secrets scan passes ([88be7dd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/88be7ddf00d7488a803c4462d815bf830ff37ba0))
* **eval:** split two long sentences on the framework copies ([0144a7d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0144a7da1a46b1764e6b9bd4d9f581ab581bbadb))
* fix the RF6 M0 recipe conflicts (M-C2 to M-C11) ([82590ef](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/82590ef613d661ed7fe803c0259ef11cbd4b20e0))
* **greenfield:** keep the 20-word step limit in AGENTS.md text ([e5b9900](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e5b9900227accd9ed670275fe99564765b959477))
* **greenfield:** name the DOC-05 check beside its ID in the style guide template ([89b4035](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/89b4035669ab4672b0b5bab0159acc1923dcbbc9))
* **greenfield:** say Claude Code reads AGENTS.md natively ([782b71c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/782b71c8bf69e209ca54632c9e2ac1bd045b7ea0))
* **implement:** add PHP and Ruby steps to pin-execution-environment ([aca6cde](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/aca6cde74e75fcf7729f092815ec99aca399f94a))
* **implement:** align the playbook container echoes with the Hard rule ([0c44b26](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0c44b267a85dc679eea82a8fad0425fb0ffd94ab))
* **implement:** correct the CI wrapper notes and add PHP and Ruby pin steps ([ecdaa9d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ecdaa9df6f7c3e04da64349efd105a82049680c7))
* **implement:** drop the undefined code D18 from three playbooks ([e9ce4fb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e9ce4fbcb87300c66d15eae83264606dcbc7dbd4))
* **implement:** give the pin-execution-environment Docker step the Hard rule exception ([9e44f86](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9e44f86e56bfb3f6baa23bf7971063f5d358a093)), closes [#248](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/248)
* **implement:** link the AGENTS.md line budget to the A14 rubric ([7751e80](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7751e80d5254ee6d758a5066dc5c4c426bf8ccf8))
* **implement:** link the Gradle wrapper rule to the command surface spec ([1f391e9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1f391e9aa0271de89ab99223437653db6a7bb2bc))
* **implement:** link the implicit pointers in the implement recipe and playbooks ([3a0fd08](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3a0fd0852bebc162359e7ec5673427b773fe6b63))
* **implement:** link the no-invented-rationale rule to the ADR policy ([23616f4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/23616f4a000589b786e3e834100303d4490065b0))
* **implement:** link the playbook commit kinds to What one commit holds ([2b5dcb4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2b5dcb4371772a7ba58a52da6bbec7147330794d))
* **implement:** link the preference-conflict echoes to the state contract ([a3db017](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a3db0170bb5dccf70e9910d635c27869575f2739))
* **implement:** link the private-content echoes to their hard rule ([8295153](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/82951538eee6db391cdbf9d89d90fe0a3a9bcf39))
* **implement:** link the secret-store echoes to their hard rule ([a84cda2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a84cda20c57e31a70ffd406f8045e96c96bca3ec))
* **implement:** link the template-licence rule to the playbook rules ([a0d2af6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a0d2af672ac612977887f04812fea2631dc0037a))
* **implement:** make the M1 recipe moves and links (steps 11 to 14) ([af787ec](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/af787ec2e1a382d3250e710d2ad1cc6f734e98b5))
* **implement:** move the adopt detail of Stage 0 to the state contract ([2622668](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/262266867b7703cb8911703f92f86479c093bf12))
* **implement:** move the preference key format to the state contract ([38cd0a0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/38cd0a0c0e02e21f1d00179b5badb2813f1ff1d9))
* **implement:** name only the checks that read each Commits row's write ([a17bfd6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a17bfd6e73fa9481ad5079364d76725119e62300))
* **implement:** name only the checks that read each Commits row's write ([d1db204](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d1db204927c39213ab07593854f4792b7137008c))
* **implement:** narrow the ADR 0003 claim that the recipe never stops mid-theme ([ecdfd56](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ecdfd5694358d5b628775852606c3a712daffaa9))
* **implement:** record that a lost pass stops the theme (ADR 0005) ([e6028c4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e6028c4e50c7870d6ef4d68854c9a0bf3e459503))
* **implement:** record that a lost pass stops the theme (ADR 0005) ([766defa](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/766defacf171ebcee0fd09f3f51b64003d41be5d))
* **implement:** record uncompared EXEC-02 lockfiles as engine-limit debt ([93ad175](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/93ad1754c202e7cd7d8891cc6d007d632d36c345))
* **implement:** record uncompared EXEC-02 lockfiles as engine-limit debt ([122b6a6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/122b6a612c442a7485e572f6afbd933e39df6759)), closes [#261](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/261)
* **implement:** say an unlocked Gradle build fails EXEC-02 ([9f5b61e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9f5b61ee181f37331c839197702f362b99fbb8cb))
* **implement:** say that CI-02 follows a wrapper script one script deep ([502443b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/502443b4b6faf25a53ac9b0ce9d13f7aeb1ad27f))
* **implement:** say when a theme may stack on an unmerged theme ([c9f1859](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c9f1859db22c57e0d25ce943d8ec1d4c04db6962)), closes [#126](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/126)
* **implement:** split the 44-word release-page sentence in add-repo-hygiene ([d413005](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d41300558040948dd42a1081afd195f020a66cf6)), closes [#251](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/251)
* **implement:** state one tool-currency rule in tool-choice.md ([c18daeb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c18daebae7f9033bf90f8e701e3038e0db120a12))
* **implement:** take a missing base report on a resume ([cd7b2b8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/cd7b2b867c96343719f912dcd3ee5d124cd7dd63))
* **implement:** write target ADRs to docs/architecture/adrs/ ([378f5a9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/378f5a903eb4fb36cfbdc21055e94c70beb3cf0b))
* install the skills for each harness ([7ac51e6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7ac51e62d0de475183a1441ea6146357c6c87696))
* install the skills for each harness ([3aa2561](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3aa25612250698edbf2e5bc689a35b2dfe64dc13))
* link the implicit pointers in the schema and tools references ([9e230e8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9e230e8ab21f2e2c779ff6b6a8e2f9653971efce))
* link the implicit recipe pointers and drop undefined codes (RF6 M0) ([14661f2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/14661f21b8b3fc55c8266c4d9a4627518d3781d7))
* link the section pointers in the root and engine AGENTS.md files ([a18cd9d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a18cd9dec4dd177fdb90fff5a26d6e8b622be992))
* list the consistency map's new inference rules ([461955f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/461955fc41a38fe19ede84eceaf418c5e069716c))
* name both Agent Governance check files in the contributor deep dive ([09d4067](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/09d406798c8e30988308dfe36f4b2986ab509a7f)), closes [#250](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/250)
* name the consistency map folder in ADR 0012 and the how-to page ([ac77c6b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ac77c6bc1f3b0d56950ce2306fc83bd6c1497561))
* name the engine check modules that now hold each statement ([f9c5f0d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f9c5f0d79765f104d4a362acc9a1d3e7445ac794))
* name the engine check modules that now hold each statement ([19a234a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/19a234a20ef1a8f5f3536b0654cffe0ce47755b2))
* only root manifests are runners (ADR-0008); unlocked Gradle fails EXEC-02 ([141579d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/141579d90b05c2fedaf8a78a1ed56fd3164addbf))
* re-render the worked-example and eval fixture Markdown reports ([9b4ce48](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9b4ce4882e6cf72df909b9076f181871f0cd94a7)), closes [#262](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/262)
* **reference:** describe the skip-marker ratchet in the self-audit ([f865d5e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f865d5e16484d222035cdce300164f7574e640f9))
* **reference:** name ruleset 2026-11-20.6 on the self-audit page ([f3641fc](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f3641fc56ab8a98400b4da03a2f8a4ad8a3de3d0))
* **reference:** refresh the self-audit baseline and NAV-05 row after merging dev ([bfa5c89](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bfa5c898d3adb6a3409eaf2f9f8d0e065d40ac4f))
* **reference:** refresh the self-audit baseline and NAV-05 row for ruleset .24 ([0695049](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/06950490246456e0b3c0d45010592aeab367f8ee))
* **reference:** refresh the self-audit baseline for ruleset 2026-11-20.24 ([4089023](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4089023d562668d9360fc102c52e42b60c5cf39f))
* **reference:** refresh the self-audit baseline for ruleset 2026-11-20.25 ([0764dc9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0764dc947753e3611fe051fb540b9640da660d35))
* **reference:** refresh the self-audit to ruleset 2026-11-20.15 ([9b8ffbb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9b8ffbb9672a0c6896a0308b5c1155130a59d762))
* **reference:** refresh the self-audit to ruleset 2026-11-20.7 ([ebe0c0c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ebe0c0cf099d631b2cd776f6fbbe58823cfd6232))
* replace the undefined DP §11 and review R-07 codes in the eval docs ([02a2e08](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/02a2e08ec5ff5accfd98516a23dd88d2dbd8332f)), closes [#246](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/246)
* say the owner raises the coverage floor ([8e579fd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8e579fd59b546cad85ebc8f0ba9b67448cd05c06))
* say when to run narrow tests and when to run the gate ([e742e29](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e742e29e94d739d7ff2ed2beefcb2418a59d6eb1))
* say when to run narrow tests and when to run the gate ([d05b70c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d05b70ca1d39f560e6be411444e0e75be090dd96))
* say why this repository's security verb scans secrets ([fbd4468](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/fbd4468d6fe97b1c6138d00d3db19390efd96180))
* shorten the new candidate and example-file sentences ([64ac620](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/64ac6208e659f245ad1a91d80a0d6b1b7ce2bf3d))
* split the long sentences and steps the link edits touched ([e89e09a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e89e09a8feefbd26390ffd01a93a74145bc522b7))
* wrap the changed check-page and playbook lines at 120 characters ([43bb70f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/43bb70f556ce1ec8a2a24bc4b0bfd4c9f7005dfd))


### Refactoring

* **audit:** move the AGT-12 check section to the second AGT file ([e9eb0ad](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e9eb0ad6e6f46d4add635dc31ee8d55d85ffd3cf))
* **audit:** move the pure helpers of render_report.py to private modules ([b340895](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b3408950227ba857aee3864c466bd1360d5116cb))
* **audit:** move the report sections of render_report.py to private modules ([795bcb2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/795bcb2b5573c30584a205ae1ac2a547604a5a5f))
* **audit:** move the report tool's helpers into private modules ([74a4a25](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/74a4a25b7db37a033c5d41e11937292dc6892553))
* **audit:** move the report tool's helpers into private modules ([94573bf](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/94573bf56728edfc664d50c0043f7b67ca605da8))
* **audit:** split render_report.py into private modules ([debb46c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/debb46c83ac6d633ebcac805ac06bd9b13713b38))
* **dev:** let load_map read the consistency map as a folder of files ([ab7cfc4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ab7cfc4f77b17e87e5a08599f405c9f0eb553187))
* **dev:** move the command rewrites and skill source names into skill-bundles.json ([f6c061b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f6c061bd6c43de89c68cf455ea34776a590c2fbf))
* **dev:** move the consistency map into a folder of small files ([ce0b6e9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ce0b6e9efa83144aa2e9de97dd72cbf9800520cc))
* **dev:** move the document index tests into dev/tests/docindex_tests ([176ef0c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/176ef0c867e8216287b1a444ac07941c7e9869f1))
* **dev:** move the document index tests into dev/tests/docindex_tests ([d46b3b4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d46b3b4a8665551d8c77e741191fc0d77adc6ff0))
* **dev:** read the skill bundles' shipped-file lists from skill-bundles.json ([422a93a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/422a93a5bcb0242c0eede547db09ee0c1503f1b0))
* **dev:** read the skill bundles' shipped-file lists from skill-bundles.json ([063e04c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/063e04c5817095fcd109d51cfa0332a9428b9f97))
* **dev:** split the consistency map into a folder of part files ([458354a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/458354a6cc2d09fc76a8224b44f6696f0d032bfa))
* **engine:** declare the AGT check specs in their family module ([3b658b0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3b658b068d7b36d45e711eeac0f1b0f08f1341df))
* **engine:** declare the BASE check specs in their family module ([53c7acf](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/53c7acf0a0ec10f4a698c992f4fce39b53a0a687))
* **engine:** declare the BASE reads in their check modules ([e2522e6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e2522e6cbfe4e02c536dd9a3e0d70498f31d598a))
* **engine:** declare the CI check specs in their family module ([d8d8833](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d8d8833cd8a57e199724ee2d8b1e9bf3c6254d54))
* **engine:** declare the CI reads in their check modules ([9db6fc3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9db6fc3345568fae0fdccb2230a6304af8d0c1c2))
* **engine:** declare the CMD check specs in their family module ([b6d19a7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b6d19a74391db8932fcac4901136f8a288166672))
* **engine:** declare the CMD reads in their check modules ([ad182cc](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ad182ccd56d0bf455d3091d98f6d6c6baf8a612e))
* **engine:** declare the CON check specs in their family module ([4fa0c7b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4fa0c7bdc7566b75bb17c47ad18fcf584c049064))
* **engine:** declare the CON reads in their check modules ([8a87bda](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8a87bda4afa323d97238ffa2f235567b393476cc))
* **engine:** declare the DOC check specs in their family module ([b90627a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b90627a3de145bdddf15123d53fd5dbed8f61dd0))
* **engine:** declare the DOC reads in their check modules ([5b1b8b4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5b1b8b48979d56862607249f93ef21418022e0de))
* **engine:** declare the EXEC check specs in their family module ([7739491](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/77394913f942e8b8a9ff1b7464ef83800a9ad7aa))
* **engine:** declare the EXEC reads in their check modules ([d22601a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d22601a3d1f0ffbc2537c7361cdf17ad696268ad))
* **engine:** declare the HYG check specs and assemble the catalogue ([44d7625](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/44d7625e918ecabfa026557b1eb29072eb4ca19e))
* **engine:** declare the HYG reads in their check modules ([77586ec](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/77586ecaa0bda4bf65ec943adb0fc55e1fb025cc))
* **engine:** declare the IDX check specs in their family module ([b177f8b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b177f8bd1324f715ee4b87d24eeabbb0575cebe4))
* **engine:** declare the NAV check specs in their family module ([0a3d9ca](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0a3d9ca31a8599e88291555ac456965adfac6446))
* **engine:** declare the NAV reads in their check modules ([71dd60c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/71dd60c462e9c46a90fa38e3540513991c467f41))
* **engine:** declare the SEC check specs in their family module ([b63d784](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b63d784d1385d6767b959ae8403ab06204c0401e))
* **engine:** declare the SEC reads in their check modules ([5e4d300](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5e4d300087fe3af73ce63f5785937b984a609fbc))
* **engine:** declare the TOOL check specs in their family module ([da825f9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/da825f9343537d5964162da9e1a044b1ff37514d))
* **engine:** declare the TOOL reads in their check modules ([ea24c18](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ea24c182ff3fd27ba7099c7295ae15e33cae1c77))
* **engine:** declare the TST check specs in their family module ([61e8b5b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/61e8b5b95247f9f254af2e5bc9f8e61fd5c50d3d))
* **engine:** drop the unused simple ignore matcher ([1d8a7ca](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1d8a7cab5c4ad3089616208522c14f01121a216d))
* **engine:** drop the unused simple ignore matcher ([a58742b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a58742bbe3a3b5fd0e15a5c46dca71aa3d9ec91b))
* **engine:** move the check specification type into rules/spec.py ([bbd88a0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bbd88a0141edb4b79ec56b47a3ba462992620ccc))
* **engine:** one definition per check, in the family modules ([ae2a6eb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ae2a6eb9215980acb6fd66bb629ccf3475409b35))
* **engine:** remove the unused verb_runners from stack detection ([0791bf3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0791bf3b4ea7cae52df664473ff13379ee1be6a5)), closes [#205](https://github.com/Nistapp/codebase-agentic-readiness-framework/issues/205)
* **engine:** split the AGT family into a package ([73893c9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/73893c9ba537753fd992fc60f8bc659153258979))
* **engine:** split the AGT family into a package ([0fbfbea](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0fbfbea5aa9afcd557fc61d6bfb1fc09264c99ed))
* **engine:** split the BASE family into one module per check ([ef6bbdc](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ef6bbdcbb46c68f3abe5f96dc514560e02699f25))
* **engine:** split the CI family into one module per check ([5fd7a64](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5fd7a6401ec1930d5c4eaa6f415b4656d543476d))
* **engine:** split the CMD family into one module per check ([266edcf](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/266edcfbfe567634e7e42cccfbef901828b9b35b))
* **engine:** split the CON family into one module per check ([ba4364a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ba4364a4bca6a924f4a24438326e9b1985e7fe2b))
* **engine:** split the DOC family into one module per check ([70325bb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/70325bb879beb29176657c5dbebd6f3f8f02b1b1))
* **engine:** split the EXEC family into one module per check ([640b30f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/640b30f0d792e5c8e09bb6bbd572a59f0e63a643))
* **engine:** split the fixture matrix into one table per family ([f1d0516](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f1d051616d038df931e6d00927160a82a9e11e36))
* **engine:** split the fixture matrix into one table per family ([baa66da](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/baa66da50096d90e99275340207429e45909c996))
* **engine:** split the HYG family into one module per check ([6f50ae2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6f50ae214c71d27255e78c437b20217755399678))
* **engine:** split the IDX family into a package ([9b85ffc](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9b85ffcd1f35ae759f8742fa6860b05d6ac9417b))
* **engine:** split the IDX family into a package ([93ec062](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/93ec062bb335062a29326176fda5f6596a15c64b))
* **engine:** split the NAV family into one module per check ([2a1d1d8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2a1d1d88d5c873928e38a849d92186397123a99f))
* **engine:** split the SEC family into one module per check ([4cea507](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4cea507028e6567144065af15c4b5a45d871f5e2))
* **engine:** split the TOOL family into one module per check ([eabbdc9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/eabbdc9b9a6bb30cbfd580fe7dd44200776434dc))
* **engine:** split the TST family into a package ([b9fd96e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b9fd96e4a61f9178255d6749f93a4cf7284d6b4b))
* **engine:** split the TST family into a package ([803a8af](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/803a8af46f88645ac7f9efb249352534cc87f4d9))
* **implement:** move progress.py's command handlers to private modules ([23147ba](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/23147ba23556bf66eda12a6984eab6583f9f5f4f))
* **implement:** move progress.py's pure helpers to private modules ([0507fb4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0507fb422bca1deb3692ddb7cdf4e52b914f44d3))
* **implement:** split progress.py into private modules ([87e1cc4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/87e1cc4aae704e14bcc44110cba380776f3fb14f))


### Build and dev tools

* **dev:** refresh the test shard weights ([cd4b657](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/cd4b657c100520d7951f5cb27e5e2e399635300f))


### CI and release

* **release:** build the skill zips with build_skills --archive ([1744628](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/17446280ae3ba13964e2cf18b87f609a51673576))
* run the recipe path check in make check ([944873a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/944873aae277312e780b159cd338236a6aa532c4))

## [0.4.1](https://github.com/Nistapp/codebase-agentic-readiness-framework/compare/v0.4.0...v0.4.1) (2026-11-18)

### Features

- add the conventions and contributing checks, the playbook writing rules and a greenfield prose verb ([60b5097](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/60b5097bcc1e40cdcf0b8e92dfe1bc7f731ce37a))
- **dev:** add a safety net for recipe refactors: sweep, document index and evidence comparison ([967a14b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/967a14b51b047c27bb9ea5df9fd54fefc06215a4))
- **dev:** add the bundle manifest and its diff ([d98b183](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d98b1839c396f0f88fea249c4975f8644d4335f5))
- **dev:** add the completeness sweep in report mode ([8b25068](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8b250688ae2bb6f98111f731b20e536b3f7a2701))
- **dev:** add the document index model, schema, config and command skeleton ([422ffd5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/422ffd58018796bc8c1dbebb9179deaf07cb34ec))
- **dev:** add the document index's Markdown parser ([870164b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/870164bad631c95d08c54aa23bd8633f547ec386))
- **dev:** add the evidence comparison before and after ([57e2ba6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/57e2ba6ffda2775c10e3ad07847fdd4afa8a4702))
- **dev:** add the index diff module and its tests ([6edc80e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6edc80e5bbfe014e5d71291c3bd24dae1fdc05a4))
- **dev:** add the index extractor's file and section nodes ([4d73654](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4d73654f2ce40f141cbac4166cf42dec32e58bfd))
- **dev:** add the index's id nodes and its mentions, runs and bundles edges ([0834398](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/083439889798adba556d55e7cf59d05672d8e068))
- **dev:** add the index's links edges with anchors ([2faaa50](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2faaa50f175e90ea33de7c442e4fdf248f55b46a))
- **dev:** add the quote verifier for reports ([1e3d9fb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1e3d9fb54f22e0e7a8fa85b6c191a6daae3cae6c))
- **dev:** add the sweep's diff mode, path-only filter and recall measure ([a0ae872](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a0ae87224f88f518516d31ebd00af54090d28eb5))
- **dev:** route the diff command to the index diff ([300afcf](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/300afcf791a21b1ba794a4e5a39d1c69a04b6c78))
- **dev:** route the query command to the index query ([a210c29](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a210c297292e718b1c66cab03f9ca8eb6eeb85cb))
- **dev:** wire the index extractor into the build command ([2ebf32a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2ebf32a3956abf5379731b1189d5f3842c66d992))
- **engine:** add AGT-13, a scored check that coding conventions are written ([28d435a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/28d435a8035b7657e2a1463c855b4ac0dc53d168))
- **engine:** add HYG-13, an informational check of CONTRIBUTING content ([e754dbf](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e754dbf08c2a0deb2140d87f656dd1ddee594b4a))
- **greenfield:** add a warn-only docs:prose verb ([e0aabce](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e0aabceba11da88a65a23e83ff1f92fff6fcb092))
- **greenfield:** bring the bootstrap scaffolder into the repository ([8af78a3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8af78a3e713e587bcee21f988bafb0c445e552f9))
- **greenfield:** move the bootstrap scaffolder into the repository ([36b40fe](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/36b40febfb2b48e68c63592c16e59373b3ff93d8))
- **greenfield:** read the templates beside the scaffolder by default ([b509446](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b5094461eb0ea68b41eb072ea7caeee0b01f0e8b))

### Bug fixes

- declare AGENTIC_BOOTSTRAP_TEMPLATES in a committed env.example ([e882995](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e882995028e352bb47765cd1f1d26e0ce3c3fa21))
- **dev:** make the docindex tests pass the format and type gates ([ced2a01](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ced2a016988c80ceb721ca58d18b99ecffc66c82))
- **engine:** count Aider's CONVENTIONS.md as an instruction file only with .aider.conf.yml ([7cce1d2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7cce1d26cc6b1194d8ef72907201fced662a4223))
- **engine:** point the AGT-01 remediation at the adapt-agents-md playbook ([af5af78](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/af5af78b28a7e7210ce3886ab06a3d40438bdf57))
- **engine:** read a vitest name filter as a TST-04 fast path ([0dd6e15](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0dd6e15b8abc661222aa99c813df8104ddd738cd))
- **greenfield:** escape the inputs that land in package.json ([59f78ce](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/59f78ce62b882afc750505d31ee438d095127f41))
- **greenfield:** exit 2 on a verification failure, as the scaffolder documents ([7626faa](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7626faa661582ba1c8b3e5d434beb3a879d60c07))
- **greenfield:** fall back to the default identity when git is not installed ([05a00ee](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/05a00ee287480cb69afde382ad062afaf9c3dafa))
- **greenfield:** refuse a scaffold target that is a file, with a message ([2244762](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2244762d107fcb5fb03960c3703fe13d917229e1))
- **greenfield:** stop rewriting placeholder text inside command-line values ([fafb1cb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/fafb1cbae2b8e3fa7b407d0fcee89324487cd0f4))
- point the default template path at greenfield/templates ([288dd0d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/288dd0d20a179e3a1dbd7b3cecaf4665443fdf9d))

### Documentation

- add a code conventions section to AGENTS.md ([f895aa9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f895aa93788d07f5aa23011d55644d24340e15db))
- add the form-follows-content rules and an ownership map to the style guide ([bed7a43](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bed7a436c6af0790331a07436eb2f0d191e62d20))
- add the form-follows-content writing rules and carry them into the greenfield templates ([b75de9d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b75de9d1b8783e214402803df12c972c18a4f312))
- **audit:** complete the catalogue and master lists for AGT-13 and HYG-13 ([1b95091](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1b95091862b0145c5466ffcb4fdeffae727b2247))
- create AGENTS.md from a concrete greenfield template when a repository has none ([501a34e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/501a34eb62ce991a8a2662cb8bdb3a271ae771e1))
- **greenfield:** add a communication-rules template and link it from AGENTS.md ([ea4817d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ea4817d22d5fd98a155ffbfd5c1789dd9ab2e70f))
- **greenfield:** add a conventions template and make CONTRIBUTING.md the home of Git rules ([d680388](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d680388f2fca560a76aac9594f5a2c062270a0a0))
- **greenfield:** add a naming-rules placeholder to the AGENTS.md template ([e1ca49e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e1ca49e057508837651096a2257f969f28cce0b0))
- **greenfield:** add a reference-page template and a configuration link table to the README ([06c0bf2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/06c0bf2f9e3979f0a0b9a069e51974fa3ca18464))
- **greenfield:** add the form rules, the README rule and an ownership map to the style guide ([fd137b3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/fd137b3ea4cc13cd15c44752968495b1de573c86))
- **greenfield:** make the AGENTS.md template true for a scaffolded project ([9eb426c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9eb426c88b27a681cc7f3ec4f17c3740a0105286))
- **greenfield:** number the AGENTS.md template in nested style and point topics at their homes ([7ae645d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7ae645daf8bfc2409cbc2bf976cc5b600e5e07c6))
- **greenfield:** restore three rules to the AGENTS.md template ([b3465ea](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b3465eafbb784032934b58bdcd95e89e7ec19343))
- **greenfield:** trim the AGENTS.md template to a minimal skeleton ([7545276](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7545276845ea8a6ea948f56473e14e2d9936b2b9))
- **how-to:** add the page on checking a recipe change ([f0753fe](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f0753fed6ae37a0a84deff281545bcd8e2908160))
- **implement:** add the AGT-13 conventions step to adapt-agents-md ([0b7e219](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0b7e2190c5cfcd3fe3b69552586cfe7d67c9f242))
- **implement:** add the HYG-13 contributing content step to add-repo-hygiene ([306ef77](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/306ef7753a67b31da250ccf80733c07f22f43ca6))
- **implement:** add the numbering rules to the adapt-agents-md playbook ([d3ddd22](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d3ddd225cf3846c6df74b38cf1ba20c57cf85c63))
- **implement:** add the opt-in nested renumbering to adapt-agents-md ([67a2d3a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/67a2d3a65f172dc87495b28a0bea0d4fbd1643b2))
- **implement:** add the opt-in README split to establish-docs-contract ([1df83fb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1df83fb7e3131fb8162647f66fc479c686e7d136))
- **implement:** carry the form rules to new and existing style guides ([f26ae8d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f26ae8db602d2e7b3ad4d28dc4d94811f094cb8d))
- **implement:** create AGENTS.md from the skeleton when none exists ([e021c95](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e021c95e7b512d34b015790de6b7af719b2cb1bb))
- **implement:** create the AGENTS.md skeleton in the first theme that needs it ([b8b33ab](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b8b33ab84819c1ddb5d28b943f94f29ccf0f413b))
- **implement:** point the long-form communication rules at the greenfield template ([94e911e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/94e911e2c56123eff2925a4e9bffb0447d9dcdbe))
- **implement:** put the establish-docs-contract commits in step order ([771526f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/771526fedf043d99a64f8cbd58393ef97261ee26))
- **implement:** rewrap a long line in the add-repo-hygiene Gradle notes ([38657e3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/38657e3933c3937055d29dcea2f00af181c55b25))
- **implement:** split the README before the docs baselines are set ([16dab84](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/16dab84b5222e9f7a820e3598bf77a555feb270f))
- list the greenfield scaffolder's test suite wherever the suites are named ([a8210e2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a8210e2751e36dcd84171ea3f279b30d524071df))
- record ADR 0011, the standard-library document index in dev/ ([42d09a8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/42d09a8c237864d854a93f9c143b943519aac220))
- record that the greenfield scaffolder lives beside its templates ([5ef4d72](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5ef4d7245a9f37bdc1ea434df8b99dc9f6ace65d))
- refresh the check counts and map for AGT-13 and HYG-13 ([88b15d1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/88b15d1fa0a799621cc6ed2d2248e2d88ed51809))
- **spec:** add the REQ-SH-062 coding conventions requirement ([afc1917](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/afc191732f9beb0f4dcf751733041af34f85e28e))
- **spec:** add the REQ-SH-063 contributing rules requirement ([08c59ff](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/08c59ff1c89e0f2771bbd710567f4142254ae3bb))

### Build and dev tools

- bring the greenfield scaffolder under ruff and mypy strict ([203511a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/203511a5868d4e891bdf85e68cbf1671c8b10150))
- **deps:** accept GHSA-fc5q-39xc-vjpf until picomatch has a fix ([c50bf61](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c50bf6124e154094de97a9d90c07e87d2bfa2c3a))
- **deps:** accept GHSA-fc5q-39xc-vjpf until picomatch has a fix ([988df6a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/988df6a07aafd97a5d6611e8ee01d7cb8bce7fdf))
- include the greenfield scaffolder in the pyright scope ([4df6e5c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4df6e5c7e4af088bb2d9dc7a4ef79fbbb95b938a))
- raise the coverage floor to 92 ([843e37a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/843e37a84ae7888cd3871495333dcf1a3e03337d))
- run the greenfield scaffolder's tests in make test, coverage and CI ([ca1da30](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ca1da30467917dad277fe10ccfebb59324f6c12c))

## [0.4.0](https://github.com/Nistapp/codebase-agentic-readiness-framework/compare/v0.3.4...v0.4.0) (2026-11-12)

### ⚠ BREAKING CHANGES

- **implement:** progress.py init takes the report from outside the target and writes the state beside it. show, render,
  set-status, skip, unskip, defer, undefer, pref and theme take --workspace DIR (the report's folder) instead of
  --target. A state kept in a target's docs/agentic-readiness/ is no longer found.

### Features

- **audit:** print family names and check titles beside their codes ([70a7d5a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/70a7d5a5261281f70424f704b23887aaa4443334))
- **dev:** check each playbook's Commits table in recipe-lint ([35268ab](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/35268ab8229752bca440c0dbed3fd5cf8b9f455c))
- **implement:** add progress.py adopt to move an in-repo state into a workspace ([ff3d2b3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ff3d2b31025e4044d73b9e245dc89618a912e71f))
- **implement:** keep the state beside the audit report, outside the target ([5c96be2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5c96be2a24b66dacfa0d9e164b4dd8228d6354c3))
- **implement:** name each theme and check in the state file ([2414301](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2414301dabf9a23a442fb3f2bbb8e99af0e77f1e))

### Bug fixes

- **dev:** wrap long changelog lines before the release lint ([5e3691f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5e3691f1ff6bc68539543f25ea09980bb8479b4f))
- **dev:** wrap long changelog lines before the release lint ([c209ceb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c209cebefca91c82524b0366509775361dc1a977))
- **implement:** ask the owner for each missing tool, none included ([05572d1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/05572d15921cdf33dbaf7f44064e2ac91cce42fb))
- **implement:** ask the owner for each missing tool, none included ([b0ccd80](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b0ccd804bd1a0995ddd75953fba5cbceb42ae3db))
- **implement:** check each tool's version against the target's pin ([b0005fc](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b0005fcc32352d7f97a3aac5945e796e9101c30e))
- **implement:** check each tool's version against the target's pin ([d95bd63](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d95bd63e844fed2909cb9750102d9575c1f21bcc))
- **implement:** run the repository's tests before each commit and show the result ([7079eab](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7079eab5ce364f2f48b35b68cb321b99109258e0))
- **implement:** run the target's tests at every commit and work items in small commits ([e7d7d20](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e7d7d20ed2976677ae86cb1872eed051b8d2bca9))
- **implement:** work each item in small tested commits ([f1835af](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f1835af8405052cd6bf2f2bc772ce3af0d838393))
- name every code in chat, the audit report and the state file ([d1ec456](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d1ec456b71fe630a2fb0ee195602465f46e35e21))

### Documentation

- **audit:** name the output folder as the implement workspace ([e783115](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e783115fe994bba241191d36c292b87881f09e98))
- describe the implement workspace in the reference pages ([f6f761e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f6f761e479a88a717b6bfc3960e7c7611c8eceec))
- **how-to:** implement and resume from the audit workspace ([e89515c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e89515c96207e1a69934dcd5431e9b03c4861a52))
- **implement:** describe the workspace in the state contract ([0bff0cd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0bff0cd9dd6ad5e7958befd34d273aeafd57618e))
- **implement:** keep playbook files out of the state folder ([f792448](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f792448a6c7e7af3b823774cabe53baf58d3aec9))
- **implement:** keep state commits out of theme branches ([ecea19d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ecea19d9ecdb3e77d17bf515d752cab63f90ae52))
- **implement:** keep the implement state in the audit workspace ([f118cb2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f118cb2ecf90801c43be3f63aec0f45cf43c1d07))
- **implement:** run intake and triage in the workspace ([0c7b716](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0c7b71638d27f4fd47ea5aa9473e4d476bd0d301))
- **playbooks:** give every playbook a Commits table ([ed01692](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ed016922ccc7988ea70c3fc38e7400881b2ed344))
- **readme:** say how long an audit and an implement run take ([0962c07](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0962c07399beae3d435345bc49075c1465199e95))
- **recipes:** name every code in chat and reports ([27fa2bb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/27fa2bbbc594a9a493df60419977fa1848519a9e))
- **schema:** make the state's report path relative to the workspace ([8929c65](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8929c657c0bc6bae50cea45e74269adf045047f0))
- **schema:** say the state lives in the workspace ([adc6704](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/adc670498f0415c571750187f54a51e721dfe0d1))
- **stacks:** rename "Tooling defaults" to "Tooling options" ([040ae0b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/040ae0b56f71096a0f30b98fa8201a3a3926c385))

### Refactoring

- **implement:** find the state through --workspace ([b825e16](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b825e16df462640dc91349c822b52739b0ac040e))

## [0.3.4](https://github.com/Nistapp/codebase-agentic-readiness-framework/compare/v0.3.3...v0.3.4) (2026-11-10)

### Features

- **dev:** add adr-lint to make check ([58c5307](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/58c53072ac41068885aae235d9191419ef792495))
- **dev:** adr-lint checks the engine index and mentions of missing ADRs ([2a492e5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2a492e5a73f4db965b506dbef03db77d63b454ab))
- **dev:** adr-lint checks the engine index and mentions of missing ADRs ([090de46](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/090de4644770088ab3930473c802fe6cb4b3458b))
- **engine:** DOC-04 flags superseded, deprecated or rejected ADRs ([568bc5c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/568bc5c11c5f929c00db9aac0c41181e3dfdeca1))
- **implement:** add a prose check template for target repositories ([b4e5fbe](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b4e5fbed579727bb2f9a339dd6a116e164fa7848))
- **implement:** bring the writing rules to target repositories (v0.3.6) ([8ec7fee](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8ec7fee7c5f60ba6dc4b95a1526a91b99e69aaaa))
- record the ADR policy in ADR 0009 and check it (DOC-04, adr-lint) ([c304ee5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c304ee56cbf02d52d3143b3b376f771b80b57f48))

### Bug fixes

- **engine:** add the tool-07-guard-no-exit eval file to the secrets baseline ([54c10e0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/54c10e030c14a56edef057d6f82e554eeda5e946))
- **engine:** EXEC-01 reads every module of a pinned ecosystem ([86cab41](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/86cab41d9f27e5c4a6191e45f1ecbc1855816c10))
- **engine:** TOOL-07 needs a guard that exits non-zero ([71b4e61](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/71b4e616f1ea8d48746c1c68e6ccc49a5b81cd08))
- **eval:** regenerate the eval-expected files with the current paths ([0ccd527](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0ccd527015468f70ba2221040e42f9a2b1b4709d))
- **implement:** store commit ids in the state as 12 digits ([ddf8b05](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ddf8b05d1e64eaa670239af84abfb7d4a52549cf))
- **skills:** resolve every link the audit bundle keeps ([6a98a5d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6a98a5dd6cd7acba2a95c728867d9bbe50d4a3cf))

### Documentation

- add the agent-tuned ADR policy and a lean template ([46e6577](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/46e6577ff00d522392b27fee32c5ac8c8889588d))
- an agent-tuned ADR policy, a lean template and every ADR converted ([b735040](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b73504045eacc88b6ca6efa7225ef4706986ec83))
- convert the audit ADR to the lean template ([274b16d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/274b16d9f5b88be260639bdf72841d2fbacd7662))
- convert the engine ADRs to the lean template ([a1327e5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a1327e56dbf425ac121e9577dfc1feb287d5b143))
- convert the implement ADRs to the lean template ([81ab990](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/81ab9907d80ce6387f4da2155f9842085e17c3d5))
- convert the root ADRs to the lean template ([1d3b048](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1d3b048fc46ee4b2eb331e218ed6282fcedca133))
- convert the spec decision records to the lean template ([221fff3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/221fff3c203b135307403d1cc353a9aded2a9ded))
- describe how the implement recipe brings the writing rules to a target ([907fd76](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/907fd7697b8f2b4bf848d3e0f5a0c98a8598f11c))
- give ADR 0005 the current reason to reject a back-merge from main ([111fedb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/111fedbac771f7d5618e809c0157ce5a4002b930))
- **greenfield:** ship the ADR policy and the lean template ([83ce5b8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/83ce5b83f1bfc7f471a13ab21755ea23080ae6fa))
- **implement:** add plain-language and diagram rules to the style guide ([4d78aea](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4d78aea9ed46d9b960d97fa088c2877a736b1ebd))
- **implement:** add the Dependabot pre-commit ecosystem to step 8 ([9db8c0b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9db8c0b325cab76cc281af01ed46a8e49d1d6fed))
- **implement:** confirm the GitLab variables of the source-branch job ([18ec3b3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/18ec3b3f58c48d8bd30a7591abd1b29447736839))
- **implement:** count only warnings in the target's prose ratchet ([9c7ba80](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9c7ba80b4020fa8844cb4c6c754b7d7477e804cc))
- **implement:** limit prose check copies to three permissive licences ([d2bf4ca](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d2bf4ca2a7e24b2f393cff7588f14dfdac83b51a))
- **implement:** name what triggers the AGT-12 and DOC-05 steps ([31f9a9a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/31f9a9a36cbd67052ce2f092e4cdd311347cc973))
- **implement:** record existing prose debt instead of rewriting it ([4a1f495](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4a1f49525e93d720b981d1ad9f6294e1fdd0fc6d))
- **implement:** use the shared message layouts in the two playbooks ([2aa044e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2aa044eba06793844923dfa8c9c8794a8dc8970b))
- **implement:** write a "How to write for people" section in adapt-agents-md ([87940ae](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/87940ae60a09c79d6fc2bf45f747e034841869fc))
- **implement:** write ADRs into targets under the ADR policy ([8abd227](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8abd2273a83b47cbf318d9da11da4ca8046e9d5c))
- **implement:** write the Renovate security-only form from Renovate's docs ([af0b6a1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/af0b6a1e9ea2d78326561f6faf0e61e6f7d09478))
- license the greenfield templates under MIT-0 ([786fba5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/786fba5a2c3e437e374a9a5f81e93f0bae4a1f20))
- license the greenfield templates under MIT-0 ([93c6b66](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/93c6b66c4e5482e8b86b98dd354b35a3a533cf0c))
- point every agent file and router at the ADR policy ([ad0e4b5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ad0e4b5537bd296a0c135a32a07dddf912c7b128))
- record why ADRs hold only the current decision (ADR 0009) ([30ac7e5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/30ac7e56f1e886a008146bcffd07f98284b152fa))
- replace ADR index status and date columns with summaries ([9bf7534](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9bf7534bb42f83865ddca5319f0b229310c146dd))
- restore the two style guide headings an edit merged ([c9dc09f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c9dc09f12e7cd146061d5d8c49f4c8f7354ac2d0))
- **spec:** let any verb run the dependency scan in REQ-SH-030 ([5182077](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/518207775a3653fa2ba531672b5d9728eead3526))
- word the AGENTS.md ADR pointer as a rule, not a deferral ([52fe131](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/52fe1312761ff8491a6dc7587a2e1b671ca8e32d))

### CI and release

- run the eval-expected check in make check ([d25eae4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d25eae4558695621aa9d7cd0489a860c795e780d))
- shard the dev checks in the Python 3.14 test parts ([2dd517d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2dd517d87304fe4962e5caaebb51227692a33cc7))
- shard the dev checks in the Python 3.14 test parts ([4bac0ca](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4bac0caed1a11323f6fd908be5ec16b4ecb45a7b))

## [0.3.3](https://github.com/Nistapp/codebase-agentic-readiness-framework/compare/v0.3.2...v0.3.3) (2026-11-10)

### Features

- **audit:** open the rendered report with a bottom line ([52768e2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/52768e21a7a32e417571e46dcac0df3ba5362534))
- **audit:** record a check newer than the engine's ruleset as UNKNOWN ([4c9c82d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4c9c82daf1c5f1a28cfc1e9d0a294268428e8648))
- **audit:** record the framework release and install in each report ([61d0e2d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/61d0e2de4a150e1d18fa83f676145d19e59c2d90))
- **dev:** agent tools for this repository: one .mcp.json, a first-run offer, language servers ([109e7ad](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/109e7add3e87de625db99e6f62b830d1be5ba5d0))
- **dev:** assert the pull request body layout in the implement eval ([51bddf9](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/51bddf9ed07400423430f6f475828dc016476a2a))
- **dev:** check that each recipe SKILL.md links the user prompt ([1a569d0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1a569d0acd0552329599ef2af2d9bb66f4a13749))
- **dev:** document language servers beside the code index ([07d42bb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/07d42bbf282b38b7e757c44219ca172e8eb4183f))
- **dev:** give prose-check issues a severity and always exit 0 ([d36a954](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d36a954e19b4c2ee4e8c93aeb7712e5c8cb4e319))
- **dev:** offer each contributor a one-time agent tool setup ([6dce4b1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6dce4b176ab53064d88e4a7eb237fe2947cc2f63))
- **dev:** register codebase-memory-mcp in one project .mcp.json ([683ddb3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/683ddb3b40af71788e7d09f02632eb055f4e5646))
- **dev:** translate .mcp.json into each harness's MCP config ([b0b2085](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b0b2085997260dfbc9972e05bb9611b9149576d6))
- **engine:** add AGT-12 and DOC-05, the v0.3.4 Track T checks ([1703aa2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1703aa261e6e20f286f9c3bab365c64db3547c3c))
- **engine:** add AGT-12, communication rules stated ([5d16098](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5d160986083feca76c83e17c15e8215d99584bfc))
- **engine:** add CI-05, workflow files are linted ([a86ddab](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a86ddab29fcfa308597ab2c2ff46759ea6582343))
- **engine:** add DOC-05, docs are readable ([fc80971](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/fc80971d8fe92c6e7c28e82fface7abd7ecd4a08))
- **engine:** add EXEC-08, tool versions visible to dependency automation ([7172596](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7172596bef8ea5df8674b3105e0cdf03bc2d4a14))
- **engine:** add TOOL-07, a local guard against commits to a protected branch ([17bd680](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/17bd6802b7378ca3a221191f234dfe4c710497f0))
- **engine:** add TOOL-07, a local guard against commits to a protected branch (v0.3.3 C5.2) ([2fc92ec](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2fc92ec8b8e119890a0d8bd8dc6e9ee2d29c7e5d))
- **engine:** AGT-09 names every branch the declared rules protect ([910b718](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/910b71804aaede0352da047dd59f53b9e4ac5923))
- **engine:** AGT-09 names every branch the declared rules protect ([1dc8bab](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1dc8bab562c69a3813d7f144302fb3fa44c37167))
- **engine:** HYG-09 reads ecosystem coverage and the target-branch trap ([c035331](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c03533162ec10b77f544b96245a22fe31e2092d8))
- **engine:** HYG-11 reads ruleset files and the source-branch check ([23f7146](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/23f71460c5bc2d834a69920739ffe0aff46848c6))
- **engine:** HYG-11 reads ruleset files and the source-branch check (v0.3.3 C5.1) ([4b93763](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4b93763398c3f7e06f8d786145252bfc972e2133))
- **engine:** open the Markdown report with a bottom line ([6afaba3](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6afaba37d4fa1e34ebf2cd466aff5c6e25705a94))
- **engine:** TOOL-04 reads CI as well as the local verbs ([36aa387](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/36aa3872484eb1afbfce4ee40cac3b1b2748a7a9))
- **engine:** TOOL-04 reads CI as well as the local verbs ([9dfc3ae](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9dfc3ae4e9f0be4c5cdb8eaf6b1933b313ce6114))
- **engine:** TOOL-06 also reads the commit rule in CI ([d7ad429](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d7ad4290cfcf525468f62da994ec118744c61530))
- fix the layout of the recipes' questions and reports ([3993263](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3993263c38518063a2b07170fd68d5ad3db30e6b))
- give both recipes one prompt on how to talk to the user ([cf7a101](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/cf7a101c66a80c31f1ff28e4cf6c5171d7387630))
- **greenfield:** check commit messages in CI as well as in the hook ([9f693fe](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9f693fea3e68bcf00e6fb7136ded9e577f060084))
- **implement:** record in the state which framework created and last wrote it ([23b354c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/23b354cd7d24e8fc7bdd9f19c9a494cbe5612473))
- **implement:** stop on a report from another schema or a newer release ([2309763](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2309763f2efd9a462a03998334ee035f1e4322e4))
- plain communication in the recipes and a report bottom line (v0.3.4 R, H) ([b990687](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b9906874b1310765800c576427ebc1f7dc704575))
- stack-adaptive hook guidance and CI-05 workflow lint (v0.3.3 Track C: C0, C1) ([66479e7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/66479e75b0a0596be6aafdb297cf566dc082a22d))
- stamp the framework release in reports and states, and refuse files the tools cannot read ([2047b4f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2047b4fdfd1cd801a1105fddc86fd7901814b112))
- stamp the release version in reports, state and skill bundles ([5d4ff90](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5d4ff904ea9893fe98e97e80c7d4daae6634a3e7))
- TOOL-06 reads the commit rule in CI as well as in the hook (v0.3.3 C4) ([5232740](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/52327407b023f09a578cd1fa34f39264f732d326))
- v0.3.3 Track C2 and C3 (HYG-09 reads the update policy, new check EXEC-08) ([a701a04](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a701a04b7b848ce59276bcf3124ef449b8c2ca26))

### Bug fixes

- **audit:** list what the scan could not settle as sub-bullets ([80e7bbc](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/80e7bbca65f1a1108e3af5ffe8fc1a27c19660fe))
- **dev:** ignore .env files at any depth ([f807d63](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f807d6346bdf8972e7182d79751f044f54f4799a))
- **dev:** keep each osv-scanner ignore file next to the lockfiles it covers ([8b64cc1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8b64cc18e65e980a7737f2078c44eb386a2049eb))
- **dev:** name more harnesses and move the first-run trigger to the top ([22ba4a6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/22ba4a6283cea03fd2a1bbff57eea75737e21235))
- **engine:** EXEC-01 and TOOL-04 read nested pins and Makefile chains ([4f1f1bf](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4f1f1bf4e8244ed6d530ad2040e3ed8b1fea96e3))
- **engine:** EXEC-01 reads the toolchain pin in a nested manifest ([f2ff3bd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f2ff3bda8424f74ac9010b26d7757855a65b081d))
- **engine:** EXEC-07 counts types per language and reads a pyright mirror ([26fd6f5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/26fd6f5a1b83f8a15c17e6aecc0f2c9e63abe028))
- **engine:** EXEC-07 counts types per language and reads a pyright mirror ([73fa46b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/73fa46b328828bed4b2904b2280c80b69a793228))
- **engine:** TOOL-04 follows Makefile variables and prerequisites ([2e00e34](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2e00e34d639b5196e1a353af57d257f902dd9765))

### Documentation

- add a diagram to each explanation page and tutorial ([d965909](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d9659096a716aff44834c180390fca5e8a832a5b))
- add a purpose line and a diagram to the page templates ([9506b0c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9506b0c043b956aec2fa59aa20d6c96b647ad5cd))
- add generated audit and implement master lists ([b3a9377](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b3a9377bfa9b19917d89396f47be8198976b7047))
- add generated audit and implement master lists ([01be98d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/01be98d19cbc6a214f6b0b9fcf68d07ba206bab4))
- **audit:** an opt-in live read of the branch rules for HYG-11 and CI-04 ([d83d55b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d83d55bac812f649760c2273f93fcab27aff429f))
- **audit:** rewrap the EXEC-07 engine paragraph to the line limit ([f69e70c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f69e70c0b337251de2f36a6352019e7e5e07c54c))
- count the 102 engine fixtures after the dev merge ([d749568](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d7495681cf914378e9638a867bc6e5cd1c5b688b))
- count the 103 engine fixtures after AGT-09's ([34c358b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/34c358b080f9aeb7b03335501dcc13107243cf7a))
- count the 105 engine fixtures after EXEC-01's and TOOL-04's ([4306699](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/430669958d345024692ca7abfa982b0fb45c142a))
- describe the coverage parts and the audit tools' shards ([00fdf59](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/00fdf5957afe6ed2e4649dd6ebc68179a1ef7983))
- describe the engine shards and the nightly run ([04c1df0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/04c1df0fca394b413047fa9c2bae98e176c71cbc))
- describe the prose check as advisory ([b736b0d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b736b0ddf2e4a03aab07ecdac74d77281c7f683d))
- **implement:** adapt-agents-md names the branches the rulesets protect ([8299e32](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8299e32bb522d77df93b9500e699a1350d0484ae))
- **implement:** add the workflow-lint step for CI-05 ([24a5675](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/24a56755133bec151f580234be174b60f042a0aa))
- **implement:** add-hooks-and-commit-rules adds the branch guard by stack ([6526ec0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6526ec05c4956f3df966cb5acbf0fccc88cd81d6))
- **implement:** add-repo-hygiene declares branch rules as code ([5f7ce86](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5f7ce86a5313a5212fea67d77c925f9a59104b3a))
- **implement:** add-repo-hygiene writes a routing-only CODEOWNERS by default ([9002f22](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9002f22c34ce9148c487d340f4e8796989f55634))
- **implement:** choose the hook manager by the target's stack ([304420e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/304420e69970da6ec0a7fb6a3ad592616a6cdcad))
- **implement:** configure-quality-tools runs the security verb in CI ([3650dad](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3650dad105cb9a060cd60947b268d11f616774f6))
- **implement:** move inline tool versions into a manifest for EXEC-08 ([c93011b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c93011b617981b14a4eb4688c6973ebc49387eeb))
- **implement:** register-index names the language-server inputs ([c76f357](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c76f357008c06ea4499d62251c2a623376b7512f))
- **implement:** register-index writes one .mcp.json and offers the setup ([35feab4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/35feab4486dbb67d859c586d0cc0ee6251d8f30c))
- **implement:** release provenance and language-server inputs ([5143e1e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5143e1ee02d6bc169b0f12b75e7f9b5829b7c0e6))
- **implement:** routing-only CODEOWNERS and the index setup offer ([cf065b8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/cf065b80e907ed4216f227cf68c1ccefeb4a4052))
- **implement:** run the commit rule in a local stage and in CI ([f429ae7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f429ae740b41d912bd3b9c5050259ceb4bd8758a))
- **implement:** split the ruleset sentence in adapt-agents-md step 6 ([7e1289a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7e1289a9af291fc4c180b2fae2ff8cf87f2c2e38))
- **implement:** the release page may state the release provenance ([5dd2d21](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5dd2d212ac6982a1ebab4d5af11132a4d6d6d017))
- **implement:** write or fix the dependency-update file for HYG-09 ([81b0002](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/81b00021a9d3697bfd0bc0845723c1db86375761))
- link the agent tool setup from the contributor entry points ([98a13e1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/98a13e1b84271c38f8b41c79d67eefa5e0f1f45d))
- list the two security jobs ([3fa15e5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3fa15e5a4dfc07d6e1976aaaf82907377f97e3e6))
- name the prose check in the pull request checklist ([1e9ed7e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1e9ed7e2aa6321dc9c74c531045d2119a3f71f37))
- queue a dev pull request with Merge when ready, not gh pr merge ([63434f4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/63434f40702f59013b25edac38b3387a226eff16))
- queue a dev pull request with Merge when ready, not gh pr merge ([1a1bd92](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1a1bd9204d029dd55eb74e1545476d186d80b153))
- record that dev no longer requires an up-to-date branch ([32f9374](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/32f937414dfcdfc1c35288e89ed61ea4b78b2182))
- record the dev merge queue in Current state ([651c004](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/651c004350c9f935f8922ef32d40ac465e865748))
- record the dev merge queue in Current state ([3de9d91](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3de9d91aa4bf38bea507637237cbd97a233ecf0a))
- record the version rule in ADR 0008 and a versions reference ([5f0a8db](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5f0a8db381afebb7a40d815edfd9762fdc2f2c00))
- record why make check does not run the prose check ([621c600](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/621c6007fd56e9c40b8e324a22f936a8ce6a7ef6))
- regenerate the master lists for EXEC-08 ([85a2a94](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/85a2a949fe63ea59d3bc159a35fec1f076d72fcf))
- rewrite the three worst docs pages in plain language ([5a577a5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5a577a540147b3c2957ce7510e9755954d41d112))
- say that CI tests Linux only for now ([b0b3742](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b0b37421bfe8c002bab930e6f65e63ccadb5d09a))
- **self-audit:** refresh the self-audit page and neutralise the baseline ([65024fb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/65024fb26b6cdc04d071ee448257a38c8b2bda10))
- shorten the long sentences in AGENTS.md and lint it ([3adc114](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/3adc1145f6c9f9da9388d65de803207d3fecd28a))
- split the long sentences in REQ-SH-060 and the DOC-05 rubric ([2cdddb6](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2cdddb6abc8657b7c1c33c1923a1ca3d39ca9c18))
- **stacks:** recommend each stack's own hook and commit tools ([110f2f7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/110f2f7789d9f0402d362a98511399de5383f63f))

### Refactoring

- **engine:** move the Makefile walk into _common as follow_makefile ([6296b3e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6296b3efc70612d01a569694f749045d91a1c412))
- **engine:** split the engine tests into one package per check pack ([c44aa26](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c44aa26ffc615f74a5fa5579e2aed0b7f37876d5))
- **engine:** split the engine tests into one package per check pack ([a06eab4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a06eab492557d6ef3ae4a16537c771785ddfd65c))

### Build and dev tools

- add engine shard targets and a sharded coverage combine ([55f9832](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/55f9832e07c66bffc291d655715416c6d13e4426))
- **dev:** add a shard runner for the engine's test suite ([29ca367](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/29ca367673208b60b11ab2f7d44f38d6d1f82fd6))
- **dev:** add a typos spell check to make check ([4ee9b51](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/4ee9b51057b53fac6ad161ebeeacafc92b110e09))
- **dev:** audit the dev tools' dependencies with osv-scanner in make security ([345890b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/345890bcbf2d89401a238dbbdb8e8a37b0917ff0))
- **dev:** build actionlint from a Go tool module, not from actionlint-py ([095994f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/095994f2b719bd75e855bfc2fcf28516e0fd0ed6))
- **dev:** let the shard runner split the audit tools' suite ([c9cd5aa](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c9cd5aa45f85933c7192fa0ef0868fad504aca25))
- **dev:** make the prose check advisory, with severities ([320fad8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/320fad8969a38d09331ece11634cc36e124db725))
- **dev:** run make coverage as CI does, so a local pass means a CI pass ([9101437](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/910143723090bd0b03dad4e16e89149852917faa))
- **dev:** run make coverage as CI does, so a local pass means a CI pass ([0f4a6e0](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0f4a6e063036280f2fefa82b31b2fa3d7fba639b))
- **dev:** stop gating on the prose check ([9308f0d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9308f0d3b102ea8f639a368c6a26b02cddf6fe89))
- **dev:** update mermaid-cli to 12.2.0 for a katex advisory ([a432659](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/a43265966ad5ed76032c00fecd906c19c87e5120))
- **dev:** update uv to 0.13.5 for two security advisories ([d21d061](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/d21d06140a952898527db0e1e1089c44f293a48e))
- run the test suites at once on Linux and split coverage per suite ([010b358](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/010b3586b98bac66174d8d9fcf7d9c60247ca23a))
- shard the audit tools' suite and add coverage-part ([bb7ad4e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bb7ad4e50566cc5008bcbba59e6b8a76f52bb461))
- split make security into security-secrets and security-deps ([e9f6caf](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e9f6cafd8ff5bb7e7ba8d7946bac0cba669a3082))

### CI and release

- add a nightly run of the unsharded verbs ([55b3d61](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/55b3d617efdb21889af1e3856a833f0f9a1f9c23))
- add an advisory CodeQL workflow for Python and Actions ([1a32a51](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1a32a514fdf70b19c3586df91a2c88610e92d388))
- add an advisory OpenSSF Scorecard workflow ([c0cc4a7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/c0cc4a7623d57350b3c0eafd424902322fb9a76e))
- faster CI per pull request and a merge queue for dev ([bf3b533](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bf3b533403f4c9744e29a47ef4dc137cf89d55c7))
- fix zizmor's pedantic findings and gate on the pedantic persona ([5c26847](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5c26847aef164f1787a3133978fdab5d204ff74a))
- publish the Scorecard results and fix its Vulnerabilities alert ([fcd5c7f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/fcd5c7fcbff173b989b13e8f018518b39723fa1b))
- publish the Scorecard results and record how each alert is handled ([818676d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/818676d17fb7819e21b68adc1e22a61a7884ee69))
- run CI on merge groups of the dev merge queue ([8df5231](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8df5231f739d4d7dc1e6530a06642910b38c22c5))
- run the audit tools' suite in shards and drop the test-tools job ([e8c598a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e8c598ae0aa666f915fbb8e6e2fcfac9f7e525cb))
- run the check matrix on Linux only ([5e50513](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5e50513fca567104e1b71aabefbc4feab5c2efba))
- run the coverage suites in two parts and drop the test-tools job ([9fb632a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9fb632a5ba939418e875b33dfdf049aa4c640de0))
- run the engine's suite in two shards on both Python versions ([b59be30](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/b59be30f1591da9e8d23e938a6524fcd6ff694af))
- run the engine's test suite in shards on both Python versions ([6b22dd1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6b22dd1b8749f14b75306577a24725d4bede5324))
- run the secrets scan and the dependency audit as two jobs ([0ea219d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0ea219d29b913e94e41e51d7e78f91c021d59c7f))
- run the secrets scan and the dependency audit as two jobs ([ae30d59](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ae30d59416fe2f6f196f78707d48139e3259959b))
- run the steps of make check as parallel jobs ([0dfe7eb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0dfe7eb302e867030ef93db6b966550ed5e6aca0))
- sign build provenance for the release files ([7c7cfa7](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7c7cfa78d27f34ede3b6eb799fd5104a7041ce4b))

## [0.3.2](https://github.com/Nistapp/codebase-agentic-readiness-framework/compare/v0.3.1...v0.3.2) (2026-11-09)

### Features

- Improved communication guidelines for genAI ([aa03ab8](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/aa03ab8a773f5b203c3a64227222cef9acb40e22))

### Documentation

- add communication rules and a plain-language prose check ([91bc77b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/91bc77bdb26d42a2053072f37b87760c439b77e6))
- move COMMUNICATION_RULES.md into docs/ ([7acfcab](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7acfcab58e73e9916f5bb1088544ab6f245c3c33))
- record automatic deletion of merged branches ([9034eb4](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/9034eb4df3323e5c0929161419158312186412fb))
- record automatic deletion of merged branches ([058c710](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/058c710f93a5f68119e72783c86fc8ccfaae465e))
- rename COMMUNICATIONS.md to COMMUNICATION_RULES.md ([ccf8c5c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ccf8c5c71a6fc4df2de84b16c07e4e1befd4ccd7))
- shorten the long sentences in the release process pages ([8195c59](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8195c596e72df777e8e1bfb744bea13624b95ee9))

## [0.3.1](https://github.com/Nistapp/codebase-agentic-readiness-framework/compare/v0.3.0...v0.3.1) (2026-11-08)

### Bug fixes

- **engine:** report the released version 0.3.0 instead of 0.1.0 ([1214f59](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1214f5936befeb3a086d6828e691f00b500deea4))

### Documentation

- add a development tooling reference page ([7e19468](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7e194686fe0f2a7848a1a2c75905198fdc0dcda0))
- add a step-by-step guide to contribute a change through dev ([5806e9e](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/5806e9e6936e540128a96fed73d9c7946438fb11))
- add the harness disclaimer and the report steps to the README quick start ([7a8f4eb](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/7a8f4eba2a66a70e86cb9a13a79ba47b10171286))
- clone main in the README quick start ([f1d41a2](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/f1d41a22446ff135e1f7ba1e020ba49066fecde4))
- describe the dev and main branches in the README ([bdcbe3d](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/bdcbe3d516552fb17e1606cd8c77ae86635f688d))
- describe workflow-lint, commit-lint and CODEOWNERS ([2aa6632](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/2aa66327cab3f602e1e1dd80bd0e74e494a787e6))
- fix the overview link and the skill list in the README ([00d4ffc](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/00d4ffc604a04924a99b9ba27a73a0cfd57cb8a3))
- make dev the default branch in ADR 0002 and the process docs ([1a557dd](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/1a557dde90cb1fd7351aea972ce336b7dc7f96e2))
- recommend a fresh session before the implement step in the README ([0efe17c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0efe17c35fe5c515f5e66e4d04fe6271f663c837))
- record the Dependabot policy and the dev tool pins (ADR 0003) ([df049b5](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/df049b59b6f3b9024274edef73776f2aec0454e2))
- record the dev and main branch model and the promotion release ([268ed75](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/268ed750943bd8489c89f84470733c4adb1ea45c))
- record the dev ruleset as active ([e417e1a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e417e1ac16870d0866be3cc3c8c3671fc02a2798))
- **release:** describe the release-please process ([ae0f2ed](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/ae0f2ed89099011c79c4673383607e3ec7411fb7))
- reword the README introduction ([0fdcd4a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0fdcd4aa6413eccd40911790c1e7be07a435f31c))

### Build and dev tools

- **dev:** move the dev tool pins into manifests that Dependabot reads ([6002b89](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/6002b894984a56847ef79f73d1908b5d41e6fcf0))

### CI and release

- **dependabot:** open security pull requests only, never for a major version ([0cfcc6c](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/0cfcc6c34cd46f2f870141e2f580e3c857751d29))
- lint the workflows and the commit subjects in the gate ([e83a10f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/e83a10f0a3914ab776a7df63b511040bc29fd59d))
- **release:** automate versions and releases with release-please ([be5d86f](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/be5d86fd25e16d2e3f70fb796e51cc99d65178fc))
- **release:** publish only a tag whose commit is on main ([195d76b](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/195d76b9fd4c4b680f1fa9d6d9d4ed3bc5315535))
- require pull requests into main to come from dev ([8c3c05a](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/8c3c05ad67fbc7333c7eeecc1d4659c13590cabe))
- run CI on pushes to dev and target Dependabot at dev ([58d65c1](https://github.com/Nistapp/codebase-agentic-readiness-framework/commit/58d65c17f5838bb1097a4e2ce7b0b3752b816b14))

## [Notes written by hand since 0.3.0]

These notes were written by hand before release-please took over this file. They ship in the first release that
release-please makes: the entry above this one.

### Repository

- Releases are automated with release-please
  ([ADR 0005](docs/architecture/adrs/0005-release-please-cuts-releases.md)). A push to `main` opens or updates a
  release pull request that bumps the version and writes this file. Merging it tags `vX.Y.Z`, publishes the GitHub
  release with its files and opens a back-merge pull request from `main` into `dev`. `release.yml` no longer runs on
  a pushed tag; `release-please.yml` calls it. The engine's `__version__` (it said `0.1.0`) now follows the release.

- Two protected branches ([ADR 0002](docs/architecture/adrs/0002-dev-integrates-main-releases.md)). `dev` is the
  integration branch and the default branch: it accepts pull requests from any branch and no direct commits. `main` is
  the release branch: it accepts pull requests from `dev` only. The rulesets are declared in `.github/rulesets/`.
- The quick start in `README.md` clones `--branch main`, so a user gets the latest release, not `dev`.
- New required check on pull requests into `main`: `Check source branch`
  (`.github/workflows/pr-source-branch.yml`).
- CI runs on pushes to `dev` as well as `main`. Dependabot version updates target `dev`.
- `release.yml` refuses a tag whose commit is not on `main`.
- `lefthook.yml` stops a local commit on `dev` or `main`.
- Dependabot opens security pull requests only, and never for a major version
  ([ADR 0003](docs/architecture/adrs/0003-dependabot-security-pull-requests-only.md)). A fix that needs a major
  version stays an alert. The greenfield template and the test fixtures never get a pull request.
- The dev tool versions move from the `Makefile` and the workflows to `dev/tools/pyproject.toml` (with `uv.lock`)
  and `dev/tools/package.json` (with `package-lock.json`), so Dependabot sees them. The root `.nvmrc` pins Node for
  CI. `dev/tests/test_tool_pins.py` keeps each version in one place.
- New gate `make workflow-lint`, part of `make check`: actionlint, zizmor and check-jsonschema on `.github/`, all
  offline. Each Dependabot entry has a 7-day cooldown, which zizmor asks for.
- New CI job `commits`, required through `CI Gate`: `dev/commit_lint.py` checks that each commit subject a pull
  request adds follows Conventional Commits. The lefthook `commit-msg` hook runs the same script.
- `.github/CODEOWNERS` routes review requests to the maintainer.
- New reference page: [development tooling](docs/reference/dev-tooling.md), every tool, its command, its CI job and
  where its version is pinned.
- `dev/recipe_lint.py` also checks the links in `AGENTS.md`, `CONTRIBUTING.md`, `RELEASE_PROCESS.md` and
  `SECURITY.md`.
- New how-to: [contribute a change](docs/how-to/contribute-a-change.md). `RELEASE_PROCESS.md` and
  [branch protection](docs/reference/branch-protection.md) describe the promotion from `dev` to `main`.

## [0.3.0] - 2026-11-07

The first public release for developers. One layout, one way to start, and a protected `main`.

### Start in one minute

- Clone the repository, start Claude Code in it, and say "Audit `<repo>` and write the output to `<dir>`", then
  "Start implementing the fixes on `<repo>` based on `<report>.json`". Two tracked pointer skills in
  `.claude/skills/` start the recipes `audit/SKILL.md` and `implement/SKILL.md`; `dev/tests/test_pointer_skills.py`
  keeps them in step (V03.U1).
- The root `README.md` is short and user-first: the quick start, a table of other ways in, an honest platform
  statement (Linux tested; macOS tools tested in CI; Windows not tested) and the licences (V03.B1, V03.C2).
- New how-to: [install the skills from a release](docs/how-to/install-the-skills.md), with the checksum check.
- The worked example links the public Server repository at the commit after the fixes (V03.X1).

### Repository

- New layout (V03.C1): `docs/` (framework pages and the Diátaxis docs), `spec/` (unchanged), `greenfield/`,
  `audit/` (recipe, catalogue, schemas, stacks, tools, and the engine with its own docs), `implement/` (recipe, tools,
  its ADRs) and `dev/` (build, lint, eval and CI-only checks; never shipped). Moves are `git mv`, so
  `git log --follow` keeps each file's history.
- Licence files: `LICENSE` (GFDL-1.3, documents) and `LICENSE-CODE` (AGPL-3.0-or-later, code). Each skill bundle now
  carries `LICENSE` with the AGPL text.
- Skill bundles: the engine package moves from `scripts/deterministic-audit/audit/` to `scripts/engine/audit/`, the
  same shape as the clone. Unzip a new release over the old folders. Bundles build into `dev/dist/skills/`.
- `SECURITY.md`: report a vulnerability privately through GitHub, or by email to `udan-security@nistapp.com`;
  acknowledgement within 5 working days (V03.D2).
- `main` is protected by a ruleset (pull request, `CI Gate`, up to date, no force push or deletion, merge commit), and
  private vulnerability reporting, secret scanning, push protection and Dependabot security updates are on
  ([branch protection](docs/reference/branch-protection.md), V03.D1, V03.D3).
- The `register-index` playbook recommends `.mcp.json` at the repository root as the one MCP config (V03.A1).

### Moved

| Old path | New path |
| --- | --- |
| `brownfield-recipes/audit/`, `catalogue.json`, `stacks/`, `schema/` | `audit/`, `audit/catalogue.json`, `audit/stacks/`, `audit/schema/` |
| `brownfield-recipes/schema/examples/eval-expected/` | `dev/eval/expected/` |
| `brownfield-recipes/implement/` | `implement/` |
| `brownfield-recipes/tools/` (audit tools and shared helpers) | `audit/tools/` |
| `brownfield-recipes/tools/{progress,check_drift,compare_reports}.py` | `implement/tools/` |
| `brownfield-recipes/tools/{build_skills,recipe_lint}.py`, `tools/eval/`, `brownfield-recipes/dev/` | `dev/` |
| `brownfield-recipes/deterministic-audit/` | `audit/engine/` (`tools/build.py` → `audit/engine/build.py`; `LICENSE` → `LICENSE-CODE`) |
| `brownfield-recipes/docs/` | `docs/` (`architecture/user-overview/`, `contributor-deep-dive/` → `docs/explanation/`) |
| `brownfield-recipes/docs/architecture/adrs/0001-*` | `audit/docs/architecture/adrs/` |
| `brownfield-recipes/docs/architecture/adrs/0002-*`, `0003-*` | `implement/docs/architecture/adrs/` |
| `brownfield-recipes/README.md`, `CHANGELOG.md` | `audit/README.md`, `audit/CHANGELOG.md` |
| `shared/<Name>.md` | `docs/framework/<name>.md` (lowercase, for example `tool-ecosystem.md`) |
| `brownfield-legacy/Phased-Approach.md`, `README.md` | `docs/framework/phased-approach.md`, `brownfield-track.md` |
| `greenfield-bootstrap/` | `greenfield/` |
| `docs/branch-protection.md` | `docs/reference/branch-protection.md` |

## [0.2.0] - 2026-11-06

Release notes: the implement recipe (`brownfield-recipes/implement/`) is live with Stages 0-5, thirteen playbooks and
its own skill bundle, and the release workflow attaches both bundles. A real run is published as a
[worked example](audit/schema/examples/server-worked-example/README.md) with an owner-confirmed second
audit (IR15). The engine defects found
on the way are open `audit-engine` issues on GitHub (for example #45 and #49-#52); they are known, not fixed in 0.2.0.

### Framework pages (since v0.1)

- A quality baseline for this repository, by the `add-baselines-and-ratchet` playbook: `.quality-baseline.json` and a
  compare step that fails when the ruff, mypy or Markdown lint count goes up (MR08.3).

- The framework pages say the implement recipe is in development and no longer promise features that are only
  planned; the verb count is seven everywhere; the greenfield README and `AGENTS.md` template (now 1.1.1) state what
  the scaffold satisfies (MR01.3).
- Decisions of record: the push and pull request policy ([ADR 0003](implement/docs/architecture/adrs/0003-push-and-pr-policy.md)),
  `format:check` includes the lint rules ([spec decision 0002](spec/decisions/0002-lint-in-the-gate.md)), and a note
  that monorepo component scoping is v0.3 (MR03).
- The risk register names the risks the recipes introduce, R9-R14 (MR08).
- The trust page's implementation section is a table of what the implement recipe may and never does (MR08).

### This repository's own gates

- Phase 1 for this repository (MR07): `.python-version`, lefthook hooks, `make setup`, `make coverage` with a
  floor, a root `docs/` index with a branch-protection page, issue and pull request templates, and secret and key
  material ignored by shape.
- The self-audit is published and ratcheted: `make self-audit` against `.audit-baseline.json`, a `self-audit` job in
  `CI Gate`, and [Self-Audit](docs/reference/self-audit.md) (MR07.2).
- `recipe_lint.py` checks the relative links of the root `README.md`, `shared/`, `spec/`, `greenfield-bootstrap/` and
  `brownfield-legacy/` as part of `make check` (MR08).
- `CONTRIBUTING.md`, this changelog, `RELEASE_PROCESS.md`, a Dependabot schedule for the workflow actions, and a
  release workflow that attaches `audit.pyz` and the skill bundle to a tagged release (MR08). The workflow has not
  run yet.
