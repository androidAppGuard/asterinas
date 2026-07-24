# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import subprocess

from .common import ReviewContext, command_output, eprint, run_agent


def _build_pass_prompt(ctx: ReviewContext, personas: list[str]) -> str:
    if ctx.input_file is None:
        raise RuntimeError("resolve_target_pass must run before fanout_review_pass")
    return command_output(
        [str(ctx.skill / "scripts" / "build_pass_prompt.sh"), str(ctx.input_file), *personas],
        cwd=ctx.repo,
        env=ctx.env,
    )


def _run_persona_group(ctx: ReviewContext, personas: list[str], output_name: str) -> bool:
    if ctx.fragdir is None:
        raise RuntimeError("fragdir is not initialized")

    prompt = _build_pass_prompt(ctx, personas)
    proc = run_agent(ctx, prompt)
    if proc.returncode != 0:
        eprint(proc.stderr.strip())
        return False

    fragment = ctx.fragdir / output_name
    fragment.write_text(proc.stdout.strip() + "\n")
    ctx.fragments.append(fragment)
    return True


def fanout_review_pass(ctx: ReviewContext) -> ReviewContext:
    if not ctx.personas:
        raise RuntimeError("activate_personas_pass selected no personas")

    ctx.fragdir = ctx.workdir / "fragments"
    ctx.fragdir.mkdir(parents=True, exist_ok=True)
    ctx.fragments = []

    if ctx.per_persona_context == "no":
        if not _run_persona_group(ctx, ctx.personas, "combined.json"):
            raise RuntimeError("combined review pass failed")
        return ctx

    for persona in ctx.personas:
        if not _run_persona_group(ctx, [persona], f"{persona}.json"):
            raise RuntimeError(f"{persona} review pass failed")
    return ctx
