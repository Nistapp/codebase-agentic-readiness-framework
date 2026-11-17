#!/usr/bin/env python3
"""
bootstrap.py — scaffold an agentic-ready npm package skeleton from the framework templates.

Reads the template set from the Codebase Agentic Readiness Framework
(greenfield/templates/**) and writes a new project into an empty directory:
TypeScript strict harness, AGENTS.md governance, docs/STYLE_GUIDE.md contract, GitHub
CI/CD + release automation, husky hooks, and the standardized six-verb command surface.

The templates own every byte of file content; this script owns structure, substitution,
and verification only. It never carries a second copy of a template, and it never rewrites
template content — if a template is wrong, fix it in the framework repo.

Usage:
    python3 bootstrap.py <target-dir> --name my-pkg --org myorg --install
    python3 bootstrap.py --dry-run --name my-pkg

Exit codes: 0 = success, 1 = usage/template problem, 2 = verification failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATES = (
    SCRIPT_DIR.parent.parent
    / "codebase-agentic-readiness-framework"
    / "greenfield"
    / "templates"
)

# Template path (relative, POSIX) -> target path (relative, POSIX). Anything not listed
# keeps its name, except the top-level dirs handled by DIR_RENAMES below.
FILE_RENAMES = {
    "interfaces.ts": "src/core/interfaces.ts",
    "core-index.ts": "src/core/index.ts",
    "cli/index.ts": "src/cli/index.ts",
}
DIR_RENAMES = {
    "github": ".github",
    "husky": ".husky",
}
# Optional groups, copied only when the matching flag is passed.
OPTIONAL_GROUPS = {
    "cli": ("cli/",),
    "infra": ("infra/",),
}
# Document templates keep their fill-in-later examples, so they are exempt from both
# placeholder substitution and the residual-token gate.
SUBSTITUTION_EXEMPT_PREFIXES = ("docs/templates/",)

# Files that must exist in every generated project. The full planned file set is also
# verified after writing; this list catches silent template-set regressions.
MANDATORY_FILES = (
    "AGENTS.md",
    "CONVENTIONS.md",
    "README.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "RELEASE_PROCESS.md",
    "package.json",
    ".gitignore",
    ".editorconfig",
    ".env.example",
    ".nvmrc",
    "biome.json",
    "commitlint.config.js",
    "tsconfig.json",
    "tsconfig.test.json",
    "vitest.config.ts",
    ".husky/pre-commit",
    ".husky/commit-msg",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/enforce-dev-base.yml",
    ".github/workflows/release-and-sync.yml",
    "docs/STYLE_GUIDE.md",
    "docs/COMMUNICATION_RULES.md",
    "docs/architecture/README.md",
    "docs/architecture/glossary.md",
    "docs/architecture/adrs/0001-initial-architecture.md",
    "docs/templates/adr-template.md",
    "docs/templates/architecture-doc-template.md",
    "docs/templates/how-to-template.md",
    "docs/templates/reference-template.md",
    "src/core/interfaces.ts",
    "src/core/index.ts",
    "scripts/docs-prose.mjs",
    "artefacts/.gitkeep",
    "specs/.gitkeep",
)

EXECUTABLE_FILES = (".husky/pre-commit", ".husky/commit-msg")


# ---------------------------------------------------------------------------
# input validation
# ---------------------------------------------------------------------------

NPM_NAME_RE = re.compile(r"^(?!\.|_)[a-z0-9._~-]+$")


def fail(message: str, code: int = 1) -> "None":
    print(f"\n  ✗ {message}\n", file=sys.stderr)
    raise SystemExit(code)


def validate_package_name(name: str) -> str:
    """Enforce npm's naming rules so the generated package can actually be published."""
    if name != name.lower():
        fail(f"package name '{name}' must be lowercase (npm rejects uppercase).")
    if len(name) > 214:
        fail(f"package name '{name}' is longer than npm's 214-character limit.")
    if name.startswith("@"):
        if "/" not in name:
            fail(f"scoped name '{name}' must be '@scope/name'.")
        scope, _, bare = name[1:].partition("/")
        for part, label in ((scope, "scope"), (bare, "name")):
            if not part or not NPM_NAME_RE.match(part):
                fail(
                    f"invalid {label} in '{name}': use lowercase letters, digits, "
                    "and - _ . ~ only, and do not start with '.' or '_'."
                )
    elif "/" in name:
        fail(f"'{name}' contains '/'. Pass --org to build a scoped name, or drop the slash.")
    elif not NPM_NAME_RE.match(name):
        fail(
            f"invalid package name '{name}': use lowercase letters, digits, and - _ . ~ only, "
            "and do not start with '.' or '_'."
        )
    return name


def validate_node_version(value: str) -> str:
    if not re.fullmatch(r"\d{1,2}", value):
        fail(f"--node '{value}' must be a major version number, e.g. 24")
    return value


def pretty_name(name: str) -> str:
    """'@acme/my-cool-pkg' -> 'My Cool Pkg' for prose placeholders."""
    bare = name.rsplit("/", 1)[-1]
    return " ".join(word.capitalize() for word in re.split(r"[-_.]+", bare) if word)


# ---------------------------------------------------------------------------
# planning
# ---------------------------------------------------------------------------

def resolve_templates(explicit: str | None) -> Path:
    candidate = Path(explicit).expanduser().resolve() if explicit else None
    if candidate is None:
        env = os.environ.get("AGENTIC_BOOTSTRAP_TEMPLATES")
        candidate = Path(env).expanduser().resolve() if env else DEFAULT_TEMPLATES
    if not candidate.is_dir():
        fail(
            f"template directory not found: {candidate}\n"
            "    Pass --templates <path> or set AGENTIC_BOOTSTRAP_TEMPLATES."
        )
    for required in ("package.json", "AGENTS.md", "docs/STYLE_GUIDE.md"):
        if not (candidate / required).is_file():
            fail(f"template directory {candidate} is missing {required} — wrong directory?")
    return candidate


def target_path_for(rel_posix: str) -> str | None:
    """Map a template-relative path to its target-relative path."""
    if rel_posix in FILE_RENAMES:
        return FILE_RENAMES[rel_posix]
    head, _, tail = rel_posix.partition("/")
    if head in DIR_RENAMES:
        return f"{DIR_RENAMES[head]}/{tail}" if tail else DIR_RENAMES[head]
    return rel_posix


def build_plan(templates: Path, with_cli: bool, with_infra: bool) -> list[tuple[Path, str]]:
    enabled = {"cli": with_cli, "infra": with_infra}
    plan: list[tuple[Path, str]] = []
    for src in sorted(templates.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(templates).as_posix()
        skip = False
        for group, prefixes in OPTIONAL_GROUPS.items():
            if rel.startswith(prefixes) and not enabled[group]:
                skip = True
        if rel.startswith(".gitkeep") or skip:
            continue
        mapped = target_path_for(rel)
        if mapped is None:
            continue
        plan.append((src, mapped))
    return plan


def build_substitutions(args: argparse.Namespace) -> dict[str, str]:
    name = args.resolved_name
    owner = args.github_owner
    author = args.author + (f" <{args.email}>" if args.email else "")
    return {
        # longest tokens first: '<project-name>' must not be eaten by '<project>'
        "<project-description>": args.description,
        "<your-github-username>": owner,
        "<package-name>": name,
        "<project-name>": name.rsplit("/", 1)[-1],
        "<node-version>": args.node_version,
        "<github-owner>": owner,
        "[Project Name]": pretty_name(name),
        "<your-email>": args.email,
        "<project>": name.rsplit("/", 1)[-1],
        "<author>": author,
        "<org>": owner,
        "[@github-handle]": f"@{owner}",
    }


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def apply_substitutions(text: str, subs: dict[str, str], allow_date: bool) -> str:
    for token in sorted(subs, key=len, reverse=True):
        text = text.replace(token, subs[token])
    if allow_date:
        text = text.replace("YYYY-MM-DD", dt.date.today().isoformat())
    return text


def write_project(args: argparse.Namespace, templates: Path, plan: list[tuple[Path, str]]) -> list[str]:
    target: Path = args.target
    written: list[str] = []
    subs = build_substitutions(args)

    for src, rel in plan:
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        exempt = rel.startswith(SUBSTITUTION_EXEMPT_PREFIXES)
        try:
            raw = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(src, dest)
            written.append(rel)
            continue
        rendered = raw if exempt else apply_substitutions(
            raw, subs, allow_date=rel.startswith("docs/architecture/")
        )
        if rel == "package.json":
            rendered = finalise_package_json(rendered, args)
        dest.write_text(rendered, encoding="utf-8")
        if rel in EXECUTABLE_FILES:
            dest.chmod(0o755)
        written.append(rel)

    for keep in ("artefacts/.gitkeep", "specs/.gitkeep"):
        path = target / keep
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        written.append(keep)

    return written


def finalise_package_json(rendered: str, args: argparse.Namespace) -> str:
    """Conditional structure the template cannot express: the CLI bin entry."""
    data = json.loads(rendered)
    if args.with_cli:
        data["bin"] = {args.resolved_name.rsplit("/", 1)[-1]: "./dist/cli/index.js"}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# verification of the generated tree
# ---------------------------------------------------------------------------

def verify_tree(target: Path, written: list[str]) -> None:
    """Fail loudly: a scaffold that ships <your-email> is worse than one that fails."""
    missing = [rel for rel in written if not (target / rel).is_file()]
    missing += [rel for rel in MANDATORY_FILES if not (target / rel).is_file()]
    if missing:
        fail("generated project is incomplete, missing: " + ", ".join(sorted(set(missing))))

    empty = [
        rel for rel in written
        if (target / rel).stat().st_size == 0
        and not rel.endswith(".gitkeep")
        and (target / rel).read_text(encoding="utf-8", errors="replace").strip() == ""
    ]
    if empty:
        fail("generated files are unexpectedly empty: " + ", ".join(sorted(set(empty))))

    tokens = ("<package-name>", "<project-name>", "<project-description>", "<github-owner>",
              "<node-version>", "<your-github-username>", "<your-email>", "<author>",
              "<org>", "<project>", "[Project Name]", "[@github-handle]")  # noqa: RUF001
    leftovers: list[str] = []
    for path in sorted(target.rglob("*")):
        if not path.is_file() or ".git/" in path.as_posix():
            continue
        rel = path.relative_to(target).as_posix()
        if rel.startswith(SUBSTITUTION_EXEMPT_PREFIXES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in tokens:
            if token in text:
                leftovers.append(f"{rel}: {token}")
    if leftovers:
        fail("unsubstituted placeholders survived:\n      " + "\n      ".join(leftovers))

    try:
        json.loads((target / "package.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"generated package.json is not valid JSON: {exc}")


# ---------------------------------------------------------------------------
# git / npm
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: Path, *, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    if not quiet:
        print(f"    $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if check and result.returncode != 0:
        tail = (result.stdout + result.stderr).strip().splitlines()[-15:]
        fail(f"command failed ({result.returncode}): {' '.join(cmd)}\n      " + "\n      ".join(tail))
    return result


def init_git(target: Path) -> None:
    if (target / ".git").exists():
        print("  · existing git repository detected — leaving it alone")
        return
    run(["git", "init", "-b", "dev"], target, quiet=True)
    run(["git", "add", "-A"], target, quiet=True)
    run(["git", "commit", "-q", "-m", "chore: scaffold project with world-class standards"], target, quiet=True)
    print("  ✓ git initialised on branch 'dev' with the scaffold commit")


def install_deps(target: Path, *, ignore_scripts: bool) -> None:
    print("\n  npm install")
    cmd = ["npm", "install"]
    if ignore_scripts:
        cmd.append("--ignore-scripts")
    run(cmd, target)


SECRET_HINTS = (".env", ".npmrc", "id_rsa", ".pem", ".key", "credentials")


def check_publish_payload(raw: str) -> None:
    """Inspect the tarball npm would publish: required files present, nothing leaked."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        print("    ! could not parse `npm pack --json` output — skipping payload check")
        return
    payload = json.loads(raw[start:end + 1])[0]
    files = payload.get("files", [])
    print(f"    {payload.get('filename')}: {len(files)} files, {payload.get('size', 0) / 1024:.1f} kB packed")
    for entry in sorted(files, key=lambda f: f["path"]):
        print(f"      {entry['path']}  ({entry['size']}b)")

    published = {entry["path"] for entry in files}
    required = ("package.json", "README.md", "dist/core/index.js", "dist/core/index.d.ts")
    missing = [rel for rel in required if rel not in published]
    if missing:
        fail("the published tarball is missing: " + ", ".join(missing))

    leaked = sorted(
        path for path in published
        if any(hint in path for hint in SECRET_HINTS) or path.endswith(".tsbuildinfo")
    )
    if leaked:
        fail("the published tarball would include non-package files: " + ", ".join(leaked))
    print("    ✓ payload contains no secrets, build caches, or stray files")


def verify_toolchain(target: Path, name: str) -> int:
    """Prove the generated project works: gate, build, pack, name availability."""
    print("\n  npm run check  (the gate: format:check → typecheck → test)")
    run(["npm", "run", "check"], target)
    print("\n  npm run build")
    run(["npm", "run", "build"], target)
    print("\n  npm pack --dry-run  (what would be published)")
    packed = run(["npm", "pack", "--dry-run", "--json"], target)
    check_publish_payload(packed.stdout)

    print(f"\n  npm view {name}  (name availability)")
    probe = run(["npm", "view", name, "version"], target, check=False)
    if probe.returncode == 0:
        print(f"    ! '{name}' already exists on npm (v{probe.stdout.strip()}) — pick another name or expect a conflict")
    else:
        print(f"    ✓ '{name}' is unclaimed on npm")
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bootstrap.py",
        description="Scaffold an agentic-ready npm package skeleton from the framework templates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Templates are read from the framework repo; override with --templates.",
    )
    parser.add_argument("target", nargs="?", default=".", help="target directory (default: current)")
    parser.add_argument("--name", help="npm package name (default: target directory name)")
    parser.add_argument("--org", help="npm scope / GitHub org, e.g. nistapp -> @nistapp/<name>")
    parser.add_argument("--description", default="TODO: one-line package description",
                        help="package description")
    parser.add_argument("--author", default=None, help="author name (default: git config user.name)")
    parser.add_argument("--email", default=None, help="author email (default: git config user.email)")
    parser.add_argument("--github-owner", default=None,
                        help="GitHub owner for CODEOWNERS/URLs (default: git config user.name)")
    parser.add_argument("--node", dest="node_version", default="24", help="target Node major (default: 24)")
    parser.add_argument("--cli", dest="with_cli", action="store_true",
                        help="also generate src/cli/index.ts and the package 'bin' entry")
    parser.add_argument("--lib", dest="with_cli", action="store_false", help="library only (default)")
    parser.add_argument("--with-infra", action="store_true",
                        help="also copy infra/ (LiteLLM gateway, Phase 7 — not fully implemented)")
    parser.add_argument("--templates", help="template source directory")
    parser.add_argument("--install", action="store_true", help="run npm install after generating")
    parser.add_argument("--no-verify", dest="verify", action="store_false",
                        help="skip npm run check / build / pack after installing")
    parser.add_argument("--no-git", dest="git", action="store_false", help="skip git init + commit")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and write nothing")
    parser.add_argument("--force", action="store_true", help="write into a non-empty directory")
    parser.set_defaults(with_cli=False, git=True, verify=True)
    return parser.parse_args(argv)


def git_config(key: str) -> str:
    result = subprocess.run(["git", "config", key], text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    args.target = Path(args.target).expanduser().resolve()

    templates = resolve_templates(args.templates)

    raw_name = args.name or args.target.name
    if raw_name.startswith("@"):
        if args.org:
            print(f"  · --name '{raw_name}' is already scoped; ignoring --org")
        resolved = raw_name
    else:
        resolved = f"@{args.org}/{raw_name}" if args.org else raw_name
    args.resolved_name = validate_package_name(resolved)
    args.author = args.author or git_config("user.name") or "TODO: author"
    args.email = args.email or git_config("user.email") or ""
    args.github_owner = args.github_owner or git_config("user.name") or "TODO-owner"
    args.node_version = validate_node_version(args.node_version)

    if args.target.exists() and any(args.target.iterdir()) and not args.force:
        fail(f"{args.target} is not empty. Use an empty directory, or pass --force to overwrite files.")

    plan = build_plan(templates, args.with_cli, args.with_infra)

    print(f"\n  agentic bootstrap  ·  {args.resolved_name}")
    print(f"  templates   {templates}")
    print(f"  target      {args.target}")
    print(f"  files       {len(plan) + 2} ({len(plan)} from templates, 2 .gitkeep)")
    print(f"  node        {args.node_version}   cli: {'yes' if args.with_cli else 'no'}"
          f"   infra: {'yes' if args.with_infra else 'no'}")

    if args.dry_run:
        print("\n  plan (dry run, nothing written):")
        for _, rel in plan:
            print(f"    {rel}")
        return 0

    args.target.mkdir(parents=True, exist_ok=True)
    written = write_project(args, templates, plan)
    verify_tree(args.target, written)
    print(f"  ✓ wrote {len(written)} files; placeholders resolved, structure verified")

    if args.git:
        init_git(args.target)

    if args.install:
        if not args.git:
            # husky's 'prepare' lifecycle script needs a git repo; skip it when there is none.
            print("  · --no-git: installing with --ignore-scripts (husky needs a repo)")
        install_deps(args.target, ignore_scripts=not args.git)
        if args.verify:
            verify_toolchain(args.target, args.resolved_name)

    print("\n  next steps")
    print(f"    1. cd {args.target}")
    if args.git:
        print("    2. set the remote default branch to 'dev' after the first push")
        print("       gh api -X PATCH repos/<owner>/<repo> -f default_branch=dev")
    else:
        print("    2. git init -b dev && git add -A && git commit -m 'chore: scaffold project'")
    print("    3. npm run check   (green today; add your first real test, then remove")
    print("       passWithNoTests in vitest.config.ts and uncomment the coverage thresholds)")
    print("    4. choose a license + add LICENSE, then enable npm Trusted Publishing")
    print("       for release-and-sync.yml (see RELEASE_PROCESS.md)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
