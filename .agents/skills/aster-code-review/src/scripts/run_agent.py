#!/usr/bin/env python3

# SPDX-License-Identifier: MPL-2.0

"""
run_agent.py - launch the ACR_AGENT_PROFILE agent with one prompt, headless.

This is the Python equivalent of run_agent.sh. It loads the selected profile,
seeds a private agent home with the merged config, copies inherited auth files,
and then replaces itself with the configured agent command.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent
PROFILES_DIR = SKILL / "agent_profiles"


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def list_profiles() -> str:
    names = []
    if PROFILES_DIR.exists():
        for path in PROFILES_DIR.glob("*/profile.json"):
            names.append(path.parent.name)
    return " ".join(sorted(names)) + (" " if names else "")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open() as file:
            value = json.load(file)
    except Exception as exc:
        eprint(f"invalid JSON {path}: {exc}")
        raise SystemExit(3)
    if not isinstance(value, dict):
        eprint(f"invalid JSON {path}: top-level value must be an object")
        raise SystemExit(3)
    return value


def toml_flat(path: Path) -> dict[str, str]:
    scalars: dict[str, str] = {}
    if not path.exists():
        return scalars

    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            break
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, value = stripped.split("=", 1)
            scalars[key.strip()] = value.strip()
    return scalars


def toml_tables(path: Path) -> list[str]:
    lines: list[str] = []
    started = False
    if not path.exists():
        return lines

    for line in path.read_text().splitlines():
        if not started and line.lstrip().startswith("["):
            started = True
        if started:
            lines.append(line)
    return lines


def seed_config(profile_dir: Path, profile_workdir: Path, smoke: bool) -> None:
    base = profile_dir / "config.toml"
    if not base.exists():
        return

    config = toml_flat(base)
    tables = toml_tables(base)

    if smoke:
        smoke_config = profile_dir / "config.smoke.toml"
        config.update(toml_flat(smoke_config))
        smoke_tables = toml_tables(smoke_config)
        if smoke_tables:
            tables = smoke_tables

    output = profile_workdir / "config.toml"
    with output.open("w") as file:
        for key, value in config.items():
            file.write(f"{key} = {value}\n")
        if tables:
            file.write("\n" + "\n".join(tables) + "\n")


def substitute(value: object, profile_workdir: Path, home: Path) -> str:
    return (
        str(value)
        .replace("{workdir}", str(profile_workdir))
        .replace("{home}", str(home))
    )


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        eprint('usage: run_agent.py "<prompt>"')
        return 2

    prompt = argv[0]

    if os.environ.get("ACR_AGENT_RUNNING"):
        eprint(
            "run_agent.py: refusing to re-enter the skill launcher from within "
            "a running agent (recursion). Spawn a persona pass as a plain "
            "'codex exec'/Task with the build_pass_prompt.sh prompt, not "
            "aster_code_review.py / run_agent.py."
        )
        return 3
    os.environ["ACR_AGENT_RUNNING"] = "1"

    profile_name = os.environ.get("ACR_AGENT_PROFILE")
    if not profile_name:
        eprint(
            "run_agent.py: ACR_AGENT_PROFILE is required "
            f"(e.g. ACR_AGENT_PROFILE=codex). Available: {list_profiles()}"
        )
        return 2

    profile_dir = Path(profile_name) if "/" in profile_name else PROFILES_DIR / profile_name
    if not (profile_dir / "profile.json").is_file():
        eprint(
            f"run_agent.py: profile not found: {profile_dir / 'profile.json'} "
            f"(available: {list_profiles()})"
        )
        return 2
    profile_dir = profile_dir.resolve()

    smoke = os.environ.get("ACR_PROFILE_VARIANT") == "smoke"
    profile_workdir = Path(tempfile.mkdtemp())
    atexit.register(lambda: shutil.rmtree(profile_workdir, ignore_errors=True))

    profile = load_json(profile_dir / "profile.json")
    if smoke:
        profile.update(load_json(profile_dir / "profile.smoke.json"))

    command = profile.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(token, str) for token in command)
    ):
        eprint("profile 'command' must be a non-empty array of strings")
        return 3

    home = Path.home()
    env_updates = {
        key: substitute(value, profile_workdir, home)
        for key, value in (profile.get("env") or {}).items()
    }
    inherit = {
        substitute(src, profile_workdir, home): substitute(dest, profile_workdir, home)
        for src, dest in (profile.get("inherit") or {}).items()
    }

    seed_config(profile_dir, profile_workdir, smoke)

    for src, dest in inherit.items():
        src_path = Path(src)
        if not src_path.is_file():
            eprint(
                "run_agent.py: profile 'inherit' source not found: "
                f"{src} (is the agent logged in?)"
            )
            return 2
        dest_path = profile_workdir / dest
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)

    exec_argv = [token.replace("{prompt}", prompt) for token in command]
    exec_env = os.environ.copy()
    exec_env.update(env_updates)

    try:
        with open(os.devnull) as stdin:
            return subprocess.run(exec_argv, env=exec_env, stdin=stdin).returncode
    except FileNotFoundError:
        eprint(f"run_agent.py: command not found: {exec_argv[0]}")
        return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
