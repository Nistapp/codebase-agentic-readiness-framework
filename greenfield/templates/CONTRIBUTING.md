# Contributing

Thank you for considering a contribution to this project. This file is the home of the rules for branches,
commits and pull requests. Other files link here.

---

## 1. Getting started

1.1 Fork the repository and clone it, or create a branch if you have write access.

1.2 Set up your machine with the commands in [`README.md`](README.md), "Development". Node.js is pinned in
`.nvmrc` (`nvm use`).

---

## 2. The gate

2.1 Run `npm run check` before every commit and pull request. It runs `format:check`, `typecheck` and `test`.

2.2 Run `npm run security` before a pull request. It fails on a high-severity advisory.

2.3 CI runs the same script names, so a local pass means a CI pass. The full command list is in
[`AGENTS.md`](AGENTS.md) §1.

---

## 3. Branches

3.1 Branch from `dev`. Name the branch `<type>/<topic>`: `feat/login-timeout`, `fix/null-config`,
`docs/style-guide`.

3.2 The type is a Conventional Commits type: `feat`, `fix`, `refactor`, `test`, `docs` or `chore`.

3.3 Open each pull request into `dev`. `main` receives releases only, through a pull request from `dev`
([`RELEASE_PROCESS.md`](RELEASE_PROCESS.md)).

3.4 Never commit on `dev` or `main`. The `.husky/pre-commit` hook stops it.

---

## 4. Commits

4.1 Each commit subject follows Conventional Commits: `<type>(<scope>): <description>`. The
`.husky/commit-msg` hook runs commitlint on each one.

4.2 Make one logical change per commit, so any commit can be reverted alone.

4.3 release-please builds the changelog and the version from the commit subjects. Never edit `CHANGELOG.md` or the
version in `package.json` by hand.

---

## 5. Pull requests, review and merge

5.1 Fill in the pull request template. Link the issue, if there is one.

5.2 A maintainer reviews each pull request. CI must pass, including the `CI Gate` check.

5.3 A maintainer squash-merges the pull request. The squash commit takes the pull request title, so the title
follows Conventional Commits too.

---

## 6. Definition of done

6.1 A change is done when the gate passes and the documentation matches the code. The rule is in
[`AGENTS.md`](AGENTS.md) §3.7.

---

## 7. Code and documentation rules

7.1 Code conventions: [`CONVENTIONS.md`](CONVENTIONS.md).

7.2 Documentation rules: [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md). Decisions follow
[`docs/ADR_POLICY.md`](docs/ADR_POLICY.md).

7.3 How to write for people, in reports and pull requests: [`docs/COMMUNICATION_RULES.md`](docs/COMMUNICATION_RULES.md).
