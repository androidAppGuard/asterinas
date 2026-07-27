# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sys
from pathlib import Path

from .common import ReviewContext, command_output, parse_meta


def resolve_target_pass(ctx: ReviewContext) -> ReviewContext:
    script = ctx.skill / "src" / "scripts" / "resolve_target.sh"
    meta_text = command_output(
        [str(script), "--meta", ctx.raw_args],
        cwd=ctx.repo,
        env=ctx.env,
    )
    input_text = command_output(
        [str(script), ctx.raw_args],
        cwd=ctx.repo,
        env=ctx.env,
    )

    meta = parse_meta(meta_text)
    ctx.mode = meta.get("mode", "")
    ctx.base = meta.get("base", "")
    ctx.files = meta.get("files", "")
    ctx.head = meta.get("head", "")
    ctx.branch = meta.get("branch", "")
    ctx.output = Path(meta["output"])
    if not ctx.output.is_absolute():
        ctx.output = ctx.repo / ctx.output
    ctx.overwrite = meta.get("overwrite") == "1"
    ctx.per_persona_context = meta.get("per_persona_context", "auto")

    ctx.workdir.mkdir(parents=True, exist_ok=True)
    ctx.input_file = ctx.workdir / "review-input.txt"
    ctx.input_file.write_text(input_text)

    ctx.meta_file = ctx.workdir / "review-meta.env"
    ctx.meta_file.write_text(meta_text.rstrip() + f"\ndate={ctx.today}\n")
    print(f"resolve_target_pass: wrote {ctx.input_file} and {ctx.meta_file}\n{ctx}", file=sys.stderr, flush=True)
    return ctx
