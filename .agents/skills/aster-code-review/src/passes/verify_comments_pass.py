# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from .common import ReviewContext, eprint, run_agent


VERIFY_PROMPT = """Verify the aster-code-review comments in this review file:

{review}

Follow the SKILL.md Verification step exactly:
- for each comment, isolate the key premise;
- try to refute it by re-reading cited code and using authoritative sources where needed;
- keep confirmed comments unchanged;
- prefix uncertain comments' problem text with "(unverified) ";
- remove only confidently refuted comments and append them under "## Retracted by verification" with a one-line reason.

Edit the review file in place. Do not restructure the assembled review."""


def verify_comments_pass(ctx: ReviewContext) -> ReviewContext:
    if ctx.output is None:
        raise RuntimeError("assemble_review_pass must run before verify_comments_pass")

    proc = run_agent(ctx, VERIFY_PROMPT.format(review=ctx.output))
    if proc.returncode != 0:
        eprint(proc.stderr.strip())
        raise RuntimeError("verify_comments_pass failed")
    return ctx
