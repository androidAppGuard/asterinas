# Process

### Write imperative, descriptive subject lines (`imperative-subject`) {#imperative-subject}

Write commit messages in imperative mood
with the subject line at or below 72 characters.
Wrap identifiers in backticks.

Common prefixes used in the Asterinas commit log:

- `Fix` — correct a bug
- `Add` — introduce new functionality
- `Remove` — delete code or features
- `Refactor` — restructure without changing behavior
- `Rename` — change names of files, modules, or symbols
- `Implement` — add a new subsystem or feature
- `Enable` — turn on a previously disabled capability
- `Clean up` — minor tidying without functional change
- `Bump` — update a dependency version

Examples:

```
Fix deadlock in `Vmar::protect` when holding the page table lock

Add initial support for the io_uring subsystem

Refactor `TcpSocket` to separate connection state from I/O logic
```

If the commit requires further explanation,
add a blank line after the subject
followed by a body paragraph
describing the _why_ behind the change.

#### Steps

1. Inspect every commit subject in the reviewed range.
2. Check that it starts with an imperative verb, describes the change, wraps identifiers in backticks, and stays at or below 72 characters.
3. Require a body when the reason for the change is not obvious from the diff.
4. Ask for vague subjects such as "Update code" or "Fix issue" to be rewritten around the concrete action.

See also:
PR [#2877](https://github.com/asterinas/asterinas/pull/2877)
and [#2700](https://github.com/asterinas/asterinas/pull/2700).

### One logical change per commit (`atomic-commits`) {#atomic-commits}

Each commit should represent one logical change.
Do not mix unrelated changes in a single commit.
When fixing an issue discovered during review
on a local or private branch,
use `git rebase -i` to amend the commit
that introduced the issue
rather than appending a fixup commit at the end.

#### Steps

1. Review each commit independently, not only the final diff.
2. Check whether every commit builds one logical change with its own coherent purpose.
3. Flag commits that mix refactoring, behavior changes, tests for unrelated features, formatting churn, or review fixups.
4. Ask for fixups to be folded into the commit that introduced the issue when the branch history is still editable.

See also:
PR [#2791](https://github.com/asterinas/asterinas/pull/2791)
and [#2260](https://github.com/asterinas/asterinas/pull/2260).

### Separate refactoring from features (`refactor-then-feature`) {#refactor-then-feature}

If a feature requires preparatory refactoring,
put the refactoring in its own commit(s)
before the feature commit.
This makes each commit easier to review and bisect.

#### Steps

1. Identify commits or diff hunks that move, rename, extract, or reformat existing code.
2. Check whether those edits are required to understand a later functional change.
3. Require behavior-preserving refactoring to appear in earlier commit(s) with no feature logic mixed in.
4. Verify that the feature commit is then reviewable as a semantic change rather than a structural reshuffle.

See also:
PR [#2877](https://github.com/asterinas/asterinas/pull/2877).

### Keep pull requests focused (`focused-prs`) {#focused-prs}

Keep pull requests focused on a single topic.
A PR that mixes a bug fix, a refactoring,
and a new feature is difficult to review.

Ensure that CI passes before requesting review.
If CI fails on an unrelated flake,
note it in the PR description.

#### Steps

1. Read the PR title, description, commit list, and touched paths to identify the topic.
2. Check whether all commits serve that topic directly.
3. Flag unrelated cleanups, opportunistic refactors, dependency bumps, or extra features for separate PRs.
4. Verify that CI status is reported; if failures are claimed to be flakes, require a note explaining why they are unrelated.
