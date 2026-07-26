# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from .common import ReviewContext, eprint, run_agent


CONSOLIDATE_PROMPT = """Consolidate related comments in this aster-code-review file:

{review}

Follow the SKILL.md Consolidation step exactly:
- find clusters that share one root cause or one fix;
- write a single unified fix for each cluster;
- repoint each member's "**Fix.**" paragraph at that shared fix;
- never remove a comment.

Edit the review file in place. Do not restructure the assembled review."""


def consolidate_comments_pass(ctx: ReviewContext) -> ReviewContext:
    if ctx.output is None:
        raise RuntimeError("verify_comments_pass must run before consolidate_comments_pass")

    proc = run_agent(ctx, CONSOLIDATE_PROMPT.format(review=ctx.output))
    if proc.returncode != 0:
        if proc.stderr:
            eprint(proc.stderr.strip())
        raise RuntimeError("consolidate_comments_pass failed")
    return ctx
