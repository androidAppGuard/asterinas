# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

from passes import (
    ReviewContext,
    activate_personas_pass,
    assemble_review_pass,
    collect_fragments_pass,
    consolidate_comments_pass,
    fanout_review_pass,
    resolve_target_pass,
    verify_comments_pass,
    write_summary_pass,
)


PIPELINE_STAGES = (
    resolve_target_pass,
    activate_personas_pass,
    fanout_review_pass,
    collect_fragments_pass,
    assemble_review_pass,
    verify_comments_pass,
    consolidate_comments_pass,
    write_summary_pass,
)


def run_review_pipeline(
    raw_args: str,
    *,
    repo: Path | None = None,
    skill: Path | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    skill_dir = skill or Path(__file__).resolve().parent.parent
    repo_dir = repo or Path.cwd()

    with tempfile.TemporaryDirectory(prefix="acr-pipeline-") as tmp:
        ctx = ReviewContext(
            raw_args=raw_args,
            repo=repo_dir,
            skill=skill_dir,
            workdir=Path(tmp),
            env=env or os.environ.copy(),
        )
        for stage in PIPELINE_STAGES:
            print(f"pipeline: start {stage.__name__}", file=sys.stderr, flush=True)
            ctx = stage(ctx)
            print(f"pipeline: done {stage.__name__}", file=sys.stderr, flush=True)
        if ctx.output is None:
            raise RuntimeError("pipeline completed without an output path")
        return ctx.output
