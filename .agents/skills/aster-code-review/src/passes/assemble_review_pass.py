# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import subprocess

from .common import ReviewContext, eprint, run_process


def assemble_review_pass(ctx: ReviewContext) -> ReviewContext:
    if ctx.meta_file is None or ctx.fragdir is None or ctx.output is None:
        raise RuntimeError("resolve, fanout, and collect passes must run before assemble")

    argv = [str(ctx.skill / "scripts" / "assemble_review.sh")]
    if ctx.overwrite:
        argv.append("--overwrite")
    argv.extend([str(ctx.meta_file), str(ctx.fragdir), str(ctx.output)])

    proc = run_process(
        argv,
        cwd=ctx.repo,
        env=ctx.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        eprint(proc.stderr.strip())
        raise RuntimeError("assemble_review_pass failed")
    return ctx
