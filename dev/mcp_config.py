# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 K. C. Ramakrishna

"""Translate this repository's ``.mcp.json`` into each harness's own MCP config, and record the first-run answer.

    mcp_config.py detect                                            which harness the environment names, if exactly one
    mcp_config.py show   --harness <name> [--scope project|user]   print where the entry goes and the entry itself
    mcp_config.py write  --harness <name> [--scope project|user]   merge the entry into that file (needs consent)
    mcp_config.py check                                             is each server's command on PATH; how to install it
    mcp_config.py status --harness <name>                           has the first-run offer been answered for it
    mcp_config.py record --harness <name> --answer accepted|declined [--scope project|user]

``.mcp.json`` is the one source (ADR 0006). Claude Code and VS Code read it as it is, so ``write`` has nothing to
do for them. Antigravity keeps servers only at user level, through ``agy mcp add``; the tool prints that command.
``--harness other`` prints the plain entry for a harness this tool does not know. For the other harnesses, ``write`` merges the entry and never replaces an entry that differs: it
stops and prints both. The answer goes into ``.agentic-readiness/setup.json``, which git ignores. Nothing here
installs a server or runs one, except ``check``, which runs ``<command> --version`` for a command on ``PATH``.

Exit 0 on success, 1 when ``write`` refuses or ``check`` finds a missing command, 2 on a usage or file error.
Standard library only; this file runs in this repository and is never shipped.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import os
import shlex
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO = Path(__file__).resolve().parents[1]
SOURCE = ".mcp.json"
RECORD = Path(".agentic-readiness") / "setup.json"

HARNESSES = ("claude-code", "vscode", "cursor", "gemini", "opencode", "codex", "antigravity", "other")
SCOPES = ("project", "user")
ANSWERS = ("accepted", "declined")
BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")

#: The environment variable each harness sets for the commands its agent runs (checked 2026-11-09). A harness
#: started from inside another one inherits the outer one's variable too, so more than one match means "ask".
ENV_MARKERS: dict[str, str] = {
    "claude-code": "CLAUDECODE",
    "antigravity": "ANTIGRAVITY_AGENT",
    "opencode": "OPENCODE",
}

#: Install routes from each server's own documentation. ``--skip-config`` stops the upstream installer from
#: writing agent configs for every client it finds; this tool writes the one entry the person agreed to.
INSTALL_HINTS: dict[str, tuple[str, ...]] = {
    "codebase-memory-mcp": (
        "macOS or Linux: curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh"
        " | bash -s -- --skip-config",
        "With Node: npm install -g codebase-memory-mcp (downloads the native binary)",
        "Windows, and the manual route: https://github.com/DeusData/codebase-memory-mcp#quick-start",
    ),
}


class ConfigError(Exception):
    """A file cannot be read or parsed, or the request makes no sense for the harness."""


class Conflict(Exception):
    """The target file already holds a different entry under the same name."""


@dataclass(frozen=True)
class Target:
    """Where one harness keeps its MCP config, and in which format."""

    path: Path | None
    native: str = ""


def load_servers(root: Path) -> dict[str, dict[str, Any]]:
    """The ``mcpServers`` map of ``<root>/.mcp.json``."""
    path = root / SOURCE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    servers = data.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        raise ConfigError(f"{path} has no mcpServers")
    for name, entry in servers.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("command"), str):
            raise ConfigError(f"{path}: server {name!r} has no command")
    return servers


def target(harness: str, scope: str, root: Path, home: Path) -> Target:
    """The file ``harness`` reads at ``scope``. A native target has no path: the harness reads ``.mcp.json``."""
    if harness == "claude-code":
        if scope == "project":
            return Target(None, "Claude Code reads .mcp.json. On the next start it asks you to approve each server.")
        return Target(None, "Claude Code keeps user-level servers itself. Run:")
    if harness == "antigravity":
        return Target(None, "Antigravity keeps MCP servers at user level, for every repository. Run:")
    if harness == "other":
        return Target(None, "Add this entry to your harness's MCP config by hand. It is in the .mcp.json format:")
    if harness == "vscode":
        if scope == "project":
            return Target(None, "VS Code reads .mcp.json. It starts the servers once you trust the folder.")
        return Target(None, "Run 'MCP: Open User Configuration' in VS Code and add the entry under 'servers'.")
    paths = {
        ("cursor", "project"): root / ".cursor" / "mcp.json",
        ("cursor", "user"): home / ".cursor" / "mcp.json",
        ("gemini", "project"): root / ".gemini" / "settings.json",
        ("gemini", "user"): home / ".gemini" / "settings.json",
        ("opencode", "project"): root / "opencode.json",
        ("opencode", "user"): home / ".config" / "opencode" / "opencode.json",
        ("codex", "project"): root / ".codex" / "config.toml",
        ("codex", "user"): home / ".codex" / "config.toml",
    }
    try:
        return Target(paths[(harness, scope)])
    except KeyError:
        raise ConfigError(f"unknown harness or scope: {harness} {scope}") from None


def translate(harness: str, entry: dict[str, Any]) -> dict[str, Any]:
    """One ``.mcp.json`` server entry in the shape ``harness`` expects."""
    command: str = entry["command"]
    args: list[str] = list(entry.get("args", []))
    env: dict[str, str] = dict(entry.get("env", {}))
    if harness == "opencode":
        result: dict[str, Any] = {"type": "local", "command": [command, *args]}
        if env:
            result["environment"] = env
        return result
    result = {"type": "stdio", "command": command} if harness == "cursor" else {"command": command}
    if args:
        result["args"] = args
    if env:
        result["env"] = env
    return result


def native_commands(harness: str, scope: str, servers: dict[str, dict[str, Any]]) -> list[str]:
    """What the person runs or pastes for a harness that keeps its config itself; empty when there is nothing."""
    if harness == "other":
        return json.dumps({"mcpServers": servers}, indent=2).splitlines()
    if harness == "antigravity" or (harness == "claude-code" and scope == "user"):
        prefix = ["agy", "mcp", "add"] if harness == "antigravity" else ["claude", "mcp", "add", "--scope", "user"]
        lines = []
        for name, entry in servers.items():
            env = [part for key, value in entry.get("env", {}).items() for part in ("--env", f"{key}={value}")]
            lines.append(shlex.join([*prefix, *env, name, "--", entry["command"], *entry.get("args", [])]))
        return lines
    return []


def detect(environ: Mapping[str, str]) -> list[str]:
    """The harnesses whose marker variable is set, in :data:`ENV_MARKERS` order."""
    return [harness for harness, variable in ENV_MARKERS.items() if environ.get(variable)]


def _json_path(harness: str) -> tuple[str, ...]:
    """The keys that lead to the server map in a harness's JSON config."""
    return ("mcp", "servers") if harness == "opencode" else ("mcpServers",)


def render(harness: str, servers: dict[str, dict[str, Any]]) -> str:
    """The config text for ``servers`` alone, as the person would paste it."""
    translated = {name: translate(harness, entry) for name, entry in servers.items()}
    if harness == "codex":
        return "".join(_toml_table(name, entry) for name, entry in translated.items())
    document: dict[str, Any] = translated
    for key in reversed(_json_path(harness)):
        document = {key: document}
    return json.dumps(document, indent=2) + "\n"


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{json.dumps(k)} = {_toml_value(v)}" for k, v in value.items()) + " }"
    raise ConfigError(f"cannot write {value!r} as TOML")


def _toml_key(name: str) -> str:
    return name if BARE_KEY.match(name) else json.dumps(name)


def _toml_table(name: str, entry: dict[str, Any]) -> str:
    lines = [f"[mcp_servers.{_toml_key(name)}]"]
    lines += [f"{key} = {_toml_value(value)}" for key, value in entry.items()]
    return "\n".join(lines) + "\n"


def merge(harness: str, path: Path, servers: dict[str, dict[str, Any]]) -> list[str]:
    """Add each server to ``path``; return the names added. Raises :class:`Conflict` before writing anything."""
    translated = {name: translate(harness, entry) for name, entry in servers.items()}
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if harness == "codex":
        return _merge_toml(path, text, translated)
    return _merge_json(harness, path, text, translated)


def _merge_json(harness: str, path: Path, text: str, translated: dict[str, dict[str, Any]]) -> list[str]:
    try:
        document = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not plain JSON ({exc}); paste the entry by hand") from exc
    if not isinstance(document, dict):
        raise ConfigError(f"{path} does not hold a JSON object")
    if harness == "opencode" and not text.strip():
        document["$schema"] = "https://opencode.ai/config.json"
    node = document
    for key in _json_path(harness):
        child = node.setdefault(key, {})
        if not isinstance(child, dict):
            raise ConfigError(f"{path}: {key!r} is not an object")
        node = child
    added = _add(path, node, translated)
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return added


def _merge_toml(path: Path, text: str, translated: dict[str, dict[str, Any]]) -> list[str]:
    try:
        existing = tomllib.loads(text).get("mcp_servers", {})
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML ({exc})") from exc
    added = _add(path, dict(existing), translated)
    if added:
        block = "".join(_toml_table(name, translated[name]) for name in added)
        separator = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        result = text + separator + block
        try:
            tomllib.loads(result)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"adding the entry would break {path} ({exc}); paste it by hand") from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result, encoding="utf-8")
    return added


def _add(path: Path, node: dict[str, Any], translated: dict[str, dict[str, Any]]) -> list[str]:
    for name, entry in translated.items():
        if name in node and node[name] != entry:
            raise Conflict(f"{path} already has a different {name!r}:\n  has:  {node[name]}\n  want: {entry}")
    added = [name for name in translated if name not in node]
    for name in added:
        node[name] = translated[name]
    return added


def read_record(root: Path) -> dict[str, Any]:
    """The first-run answers, keyed by harness; empty when nothing was recorded."""
    path = root / RECORD
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    harnesses = data.get("harnesses", {}) if isinstance(data, dict) else {}
    return harnesses if isinstance(harnesses, dict) else {}


def write_record(root: Path, harness: str, answer: str, scope: str, servers: list[str], day: datetime.date) -> None:
    """Record one harness's answer, keeping the others."""
    harnesses = read_record(root)
    harnesses[harness] = {"answer": answer, "date": day.isoformat(), "scope": scope, "servers": sorted(servers)}
    path = root / RECORD
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"harnesses": harnesses}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_commands(servers: dict[str, dict[str, Any]]) -> list[tuple[str, str | None, str]]:
    """``(server, version line or None, note)`` for each server, from ``<command> --version``."""
    results: list[tuple[str, str | None, str]] = []
    for name, entry in servers.items():
        found = shutil.which(entry["command"])
        if found is None:
            results.append((name, None, "not on PATH"))
            continue
        try:
            run = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=15, check=False)
            line = (run.stdout or run.stderr).strip().splitlines()
            results.append((name, line[0] if line else "", found))
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append((name, None, f"found at {found}, but --version failed: {exc}"))
    return results


def main(argv: Sequence[str] | None = None, *, root: Path = REPO, home: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("show", "write", "status", "record"):
        command = sub.add_parser(action)
        command.add_argument("--harness", choices=HARNESSES, required=True)
        if action != "status":
            command.add_argument("--scope", choices=SCOPES, default="project")
        if action == "record":
            command.add_argument("--answer", choices=ANSWERS, required=True)
    sub.add_parser("check")
    sub.add_parser("detect")
    args = parser.parse_args(argv)
    home = home if home is not None else Path.home()

    try:
        if args.action == "detect":
            return _print_detect(detect(os.environ))
        if args.action == "status":
            entry = read_record(root).get(args.harness)
            print(f"asked: {entry['answer']} on {entry['date']}" if entry else "not asked")
            return 0
        servers = load_servers(root)
        if args.action == "check":
            return _print_check(servers)
        if args.action == "record":
            write_record(root, args.harness, args.answer, args.scope, list(servers), datetime.date.today())
            print(f"recorded: {args.harness} {args.answer}")
            return 0
        where = target(args.harness, args.scope, root, home)
        if where.path is None:
            print(where.native)
            for line in native_commands(args.harness, args.scope, servers):
                print(f"  {line}" if args.harness != "other" else line)
            return 0
        if args.action == "show":
            print(f"# {where.path}")
            print(render(args.harness, servers), end="")
            return 0
        added = merge(args.harness, where.path, servers)
        print(f"{where.path}: added {', '.join(added)}" if added else f"{where.path}: already set, nothing to do")
        return 0
    except Conflict as exc:
        print(f"mcp_config: {exc}", file=sys.stderr)
        return 1
    except (ConfigError, OSError) as exc:
        print(f"mcp_config: {exc}", file=sys.stderr)
        return 2


def _print_detect(found: list[str]) -> int:
    if len(found) == 1:
        print(f"{found[0]} (confirm it with what you know about yourself)")
    elif found:
        print(f"ambiguous: {', '.join(found)}; one harness may run inside another. Ask the person.")
    else:
        print("unknown: no harness variable set. Ask the person.")
    return 0


def _print_check(servers: dict[str, dict[str, Any]]) -> int:
    missing = False
    for name, version, note in check_commands(servers):
        if version is not None:
            print(f"{name}: {version} ({note})")
            continue
        missing = True
        print(f"{name}: {note}")
        for hint in INSTALL_HINTS.get(name, ("See the server's own documentation.",)):
            print(f"  install: {hint}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
