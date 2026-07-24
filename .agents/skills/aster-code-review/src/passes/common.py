# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import os
from pathlib import Path
import subprocess
import sys


PERSONA_ORDER = [
    "maintainability",
    "development",
    "security",
    "hardware",
    "documentation",
]


@dataclass
class ReviewContext:
    raw_args: str
    repo: Path
    skill: Path
    workdir: Path
    env: dict[str, str] = field(default_factory=lambda: os.environ.copy())
    today: str = field(default_factory=lambda: date.today().isoformat())
    input_file: Path | None = None
    meta_file: Path | None = None
    fragdir: Path | None = None
    output: Path | None = None
    mode: str = ""
    base: str = ""
    files: str = ""
    head: str = ""
    branch: str = ""
    overwrite: bool = False
    per_persona_context: str = "auto"
    personas: list[str] = field(default_factory=list)
    fragments: list[Path] = field(default_factory=list)


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def run_process(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    stdout=None,
    stderr=None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=stdout,
        stderr=stderr,
        check=check,
    )


def command_output(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    proc = run_process(
        argv,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"command failed: {argv}")
    return proc.stdout


def parse_meta(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        meta[key] = value
    return meta


def run_agent(ctx: ReviewContext, prompt: str) -> subprocess.CompletedProcess[str]:
    return run_process(
        [str(ctx.skill / "scripts" / "run_agent.py"), prompt],
        cwd=ctx.repo,
        env=ctx.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
