# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from .common import ReviewContext, eprint, run_agent


SUMMARY_PROMPT = """Fill the "<!-- SUMMARY -->" placeholder in this aster-code-review file:

{review}

Write a constructive summary over the final comments:
- what the code does well;
- the top issues ranked by severity;
- any structural recommendations.

Only replace the summary placeholder. Do not restructure the assembled review."""


def write_summary_pass(ctx: ReviewContext) -> ReviewContext:
    if ctx.output is None:
        raise RuntimeError("consolidate_comments_pass must run before write_summary_pass")

    proc = run_agent(ctx, SUMMARY_PROMPT.format(review=ctx.output))
    if proc.returncode != 0:
        if proc.stderr:
            eprint(proc.stderr.strip())
        raise RuntimeError("write_summary_pass failed")
    return ctx
