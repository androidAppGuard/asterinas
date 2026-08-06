# Comments

### Explain why, not what (`explain-why`) {#explain-why}

Comments should explain the intent behind the code,
not restate what the code does.
If a comment merely paraphrases the code,
it adds noise without insight.

If a comment is needed to explain what code does,
first try to rewrite the code.
Do not write good comments to compensate for bad code —
rewrite it to be straightforward.

#### Steps

1. Read each added or changed comment next to the code it describes.
2. Flag comments that merely repeat names, control flow, or obvious operations.
3. When a comment explains what confusing code does, ask whether clearer names, smaller helpers, or simpler structure would remove the need.
4. Keep comments that explain intent, constraints, surprising behavior, compatibility choices, or non-local context.

See also:
_The Art of Readable Code_, Chapter 6 "Knowing What to Comment";
PR [#2265](https://github.com/asterinas/asterinas/pull/2265#discussion_r2266220943)
and [#2050](https://github.com/asterinas/asterinas/pull/2050#discussion_r2224106025).

### Document design decisions (`design-decisions`) {#design-decisions}

When the code makes a non-obvious choice —
a particular data structure, a locking strategy,
a deviation from Linux behavior —
add a comment explaining the rationale
and any alternatives considered.
Design-decision comments ("director's commentary")
are the most valuable kind of comment.

```rust
// We use a radix tree rather than a HashMap
// because lookups must be O(log n) worst-case
// for the page fault handler.
// A HashMap gives O(1) amortized
// but O(n) worst-case due to rehashing,
// which is unacceptable on the page fault path.
```

#### Steps

1. Identify non-obvious choices in the change: data structures, locking schemes, algorithms, compatibility deviations, and tradeoffs.
2. Check whether the code or nearby comments explain why this option was chosen over plausible alternatives.
3. Require a short rationale when the decision affects correctness, performance, security, compatibility, or future extension.
4. Prefer comments placed where future maintainers will encounter the decision, not only in the PR discussion.

See also:
PR [#2265](https://github.com/asterinas/asterinas/pull/2265#discussion_r2266220943)
and [#2050](https://github.com/asterinas/asterinas/pull/2050#discussion_r2224106025).

### Cite specifications and algorithm sources (`cite-sources`) {#cite-sources}

When implementing behavior defined by
an external specification or a non-trivial algorithm,
cite the source:
the relevant POSIX section, Linux man page,
hardware reference manual, or academic paper.

```rust
/// Maximum number of bytes guaranteed to be written to a pipe atomically.
///
/// For more details, see the description of `PIPE_BUF` in
/// <https://man7.org/linux/man-pages/man7/pipe.7.html>.
const PIPE_BUF: usize = 4096;
```

#### Steps

1. Find behavior copied from Linux, POSIX, hardware manuals, protocol specs, papers, or non-trivial algorithms.
2. Check whether the code cites the exact source close to the constants, rules, or algorithmic steps it implements.
3. Require a stable link, manual section, or document name precise enough for a reviewer to verify the claim.
4. Ask for a source when a magic number or compatibility behavior cannot be validated from the code alone.
