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
