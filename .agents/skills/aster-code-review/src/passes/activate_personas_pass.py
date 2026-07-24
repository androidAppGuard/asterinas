# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path
import subprocess

from .common import PERSONA_ORDER, ReviewContext, run_process


def _split_files(meta_files: str) -> list[str]:
    out: list[str] = []
    for item in meta_files.split(","):
        if not item:
            continue
        path = item
        if ":" in item:
            head, tail = item.rsplit(":", 1)
            if all(part.replace("-", "").isdigit() for part in tail.split(",")):
                path = head
        out.append(path)
    return out


def _diff_paths(ctx: ReviewContext) -> list[str]:
    if not ctx.base:
        return []
    proc = run_process(
        ["git", "diff", "--name-only", f"{ctx.base}..HEAD"],
        cwd=ctx.repo,
        env=ctx.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line]


def _has_asm_macro(repo: Path, relpath: str) -> bool:
    path = repo / relpath
    if not path.is_file():
        return False
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return False
    return "asm!" in text or "global_asm!" in text


def _hardware_path(repo: Path, relpath: str) -> bool:
    path = Path(relpath)
    return (
        path.suffix in {".S", ".asm"}
        or "arch" in path.parts
        or _has_asm_macro(repo, relpath)
    )


def _documentation_path(relpath: str) -> bool:
    path = Path(relpath)
    return (
        relpath.startswith("book/")
        or path.suffix == ".md"
        or path.suffix == ".scml"
        or "syscall" in relpath
        or "kernel_parameter" in relpath
        or "kernel-parameter" in relpath
    )


def activate_personas_pass(ctx: ReviewContext) -> ReviewContext:
    reviewed_paths = _diff_paths(ctx) if ctx.mode == "diff" else _split_files(ctx.files)

    personas = ["maintainability", "development", "security"]
    if any(_hardware_path(ctx.repo, path) for path in reviewed_paths):
        personas.append("hardware")
    if any(_documentation_path(path) for path in reviewed_paths):
        personas.append("documentation")

    ctx.personas = [persona for persona in PERSONA_ORDER if persona in set(personas)]
    return ctx
