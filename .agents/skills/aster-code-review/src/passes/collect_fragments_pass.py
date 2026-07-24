# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json

from .common import ReviewContext


def collect_fragments_pass(ctx: ReviewContext) -> ReviewContext:
    if ctx.fragdir is None:
        raise RuntimeError("fanout_review_pass must run before collect_fragments_pass")

    for fragment in ctx.fragments:
        try:
            data = json.loads(fragment.read_text())
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"unparseable fragment {fragment}: {exc}") from exc
        if not isinstance(data, list):
            raise RuntimeError(f"fragment {fragment} is not a JSON array")

    if (ctx.fragdir / "combined.json").exists():
        combined = json.loads((ctx.fragdir / "combined.json").read_text())
        by_persona = {persona: [] for persona in ctx.personas}
        for comment in combined:
            if not isinstance(comment, dict):
                raise RuntimeError("combined fragment contains a non-object comment")
            persona = comment.get("persona")
            if persona in by_persona:
                by_persona[persona].append(comment)
        for persona, comments in by_persona.items():
            (ctx.fragdir / f"{persona}.json").write_text(json.dumps(comments, indent=2) + "\n")

    return ctx
