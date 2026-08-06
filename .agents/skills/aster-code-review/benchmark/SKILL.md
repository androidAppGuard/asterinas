---
name: pr-comment-benchmark-case
description: Convert a GitHub pull request review comment URL into a standardized Markdown benchmark case for evaluating code-review skills. Use when the user provides a GitHub PR review comment link and wants a .md artifact with source metadata, the minimal commented problem diff plus its base commit, normalized expected review comment, acceptable fix patch, and evaluation criteria.
---

# PR Comment Benchmark Case

## Overview

Create benchmark cases from valuable GitHub PR review comments. Optimize for benchmark integrity: preserve exact source links and commits, separate benchmark input from expected answer, and avoid guessing when the comment context is insufficient.

## Workflow

1. Resolve the comment source.
   - Parse the repository, PR number, and comment identifier from the URL.
   - Fetch or inspect the PR review comment context using available GitHub tools, `gh`, browser access, or the GitHub API.
   - Record: comment URL, repository, PR number, comment ID, review ID if available, author, creation time, file path, side, line or range, diff hunk, `commit_id`, `original_commit_id`, and the PR base commit that the commented diff is against.
   - If the URL is not a PR review comment, continue only if the surrounding PR/file context is enough; otherwise emit a needs-manual-input result.

2. Reconstruct the benchmark input.
   - The benchmark input must be a minimal unified diff for the specific commented problem area, not a full source-code snippet.
   - Include the corresponding `base_commit_id` for the diff. Prefer the PR base SHA at the time of the reviewed commit, or the merge base between the PR base branch and `original_commit_id` when that is the reliable basis.
   - Prefer the GitHub review comment `diff_hunk` plus the exact commented range. If needed, reconstruct the smallest relevant hunk from `base_commit_id` to `original_commit_id` or `commit_id`.
   - Keep only the commented problematic hunk and any immediately necessary adjacent lines or hunks in the same file. Do not include the full PR diff or unrelated file changes.
   - Include enough diff context for control flow, types, invariants, or API contracts.
   - Do not include the expected review comment or fix patch in the benchmark input section.
   - If the base commit or problem hunk cannot be determined reliably, emit a needs-manual-input result instead of substituting a full PR diff or complete file content.

3. Normalize the expected review comment.
   - Preserve the original technical concern, trigger condition, impact, and requested change.
   - Remove conversational filler, personal tone, and thread-specific references that are not needed for evaluation.
   - Keep the wording general enough that semantically equivalent review-skill output can pass.

4. Derive an acceptable fix patch.
   - Prefer a minimal patch extracted from later commits in the same PR, the final merged diff, or an explicit author response that resolves the comment.
   - If no reliable resolved patch exists, synthesize the smallest plausible fix from the code and comment, and set `fix_source: synthesized`.
   - If the correct fix depends on missing project context, do not invent it. Emit a needs-manual-input result and list the missing evidence.

5. Write evaluation notes.
   - State the required semantic points a review skill must identify.
   - Include acceptable variations, false-positive boundaries, and any project-specific assumptions.
   - Mention whether the benchmark checks bug finding, maintainability, API contract adherence, concurrency, security, performance, style, or another category.

6. Write the benchmark case file.
   - Write the generated case to a Markdown file. Do not only print the case inline.
   - If the user provides an output path, use it. Otherwise write `<case_id>.md` in the current working directory.
   - In the final response, report the Markdown file path and whether any manual input is still needed.

## Output Format

Use this structure unless the user requests another format:

```yaml
- problem_id: <slug>              # REQUIRED, unique (numeric part too). number + kebab slug, e.g. 0004-semop-dead-timer-retain
  commit: <rev>                   # REQUIRED. the snapshot to check out (detached HEAD):
                                  #   diff mode -> a full 40-char SHA (fetched by SHA);
                                  #   files mode -> any local commit-ish (e.g. f4e29d67c^).
  remote: <fetch URL>             # OPTIONAL. where to fetch `commit`; defaults to https://github.com/asterinas/asterinas.
  source: >                       # REQUIRED. freeform provenance + why the problem is leak-free
    ...
  review_mode:                    # REQUIRED. EXACTLY ONE of `diff` / `files`.
    diff:                         #   diff mode: review `base..HEAD` (each commit's message + diff).
      base: <rev>                 #     REQUIRED ref relative to the checkout; HEAD^ for a single introducing commit.
    files:                        #   files mode: targets reviewed at `commit` (whole-file is the norm)
      - <path[:lines]>
  defects:                        # REQUIRED, one or more — the ground truth
    - target:                     #   REQUIRED
        kind: <kind>              #     REQUIRED: file | commit_message | whole_change
        path: <path>              #     REQUIRED iff kind: file
        lines: "<a-b>"            #     OPTIONAL, only when kind: file
      persona: <persona>          #   REQUIRED: maintainability|development|security|hardware|documentation
      grounding: <name>           #   REQUIRED: a guideline short-name, or a short plain-language defect description
      severity: <level>           #   REQUIRED: critical | major | minor | nit  (informative only)
      desc: >                     #   REQUIRED. what is wrong — context for the grader and humans
        ...
      fix: >                      #   REQUIRED unless is_negative — the concrete remedy
        ...
      expectation: >              #   REQUIRED. the criterion a review comment is matched against
        ...
      is_negative: false          #   OPTIONAL, default false. true = false-positive trap (omit fix)
```

## Benchmark Input

### Base Commit

`<base_commit_id>`

### Problem Diff

```diff
<minimal unified diff for the commented problem hunk only>
```

## Expected Review Comment

<polished comment preserving the technical concern>

## Acceptable Fix Patch

```diff
<minimal acceptable patch>
```

## Evaluation Notes

- Required finding: <what the review skill must notice>
- Impact: <why it matters>
- Acceptable fixes: <what kinds of fixes should pass>
- Non-requirements: <nearby issues that should not be required>

## Provenance

- Original comment: <url>
- Input diff basis: <comment diff hunk, reconstructed commit range, or fallback explanation>
- Base commit basis: <how base_commit_id was identified>
- Fix basis: <commit/PR diff/synthesis explanation>
````

For an incomplete case, output:

````markdown
---
case_id: "<best-effort-id>"
comment_url: "<url>"
base_commit_id: "<sha-or-unknown>"
needs_manual_input: true
fix_source: "manual-required"
---

## Missing Evidence

- <specific missing source, commit, diff hunk, or project context>

## What Can Be Extracted

<metadata, comment summary, or code context that is reliable>
````

## Integrity Rules

- Prefer exact commit and diff snapshots over current branch contents.
- Keep benchmark input as a focused problem diff plus base commit, not a full file, complete snippet, or whole-PR diff.
- Keep provenance explicit for every input diff and patch.
- Do not overfit the expected review comment to the original wording; evaluate semantics.
- Do not silently mix code from one commit with a fix from an unrelated state.
- Mark uncertainty instead of fabricating metadata, code context, or patches.
