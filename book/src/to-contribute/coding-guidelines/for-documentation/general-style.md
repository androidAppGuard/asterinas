# General Style

### Prefer semantic line breaks (`semantic-line-breaks`) {#semantic-line-breaks}

For prose in Markdown and doc comments,
insert line breaks at semantic boundaries
so each line carries one coherent idea.
At minimum, break at sentence boundaries.
For longer sentences, also consider breaking at clause boundaries.

Semantic line breaks make diffs smaller,
reviews easier,
and merge conflicts less noisy.

As an exception,
RFC documents that are mostly read-only
can use regular paragraph wrapping.

#### Steps

1. Review changed Markdown and doc-comment prose for long physical lines and unrelated ideas on the same line.
2. Require line breaks at sentence boundaries and, for long sentences, at natural clause boundaries.
3. Preserve code blocks, tables, links, generated text, and RFC-style documents when reflow would hurt readability.
4. Check that the reflow makes future diffs smaller and does not change rendered meaning.

See also:
[Semantic Line Breaks](https://sembr.org/).

### Make a crate's `README.md` its crate-level documentation (`readme-as-crate-doc`) {#readme-as-crate-doc}

A published crate's `README.md` (shown on crates.io)
and its crate-level Rust doc (shown on docs.rs)
usually carry the same content.
Keep a single source of truth:
write the `README.md`,
and include it as the crate-level doc rather than maintaining a separate copy.

```rust
#![doc = include_str!("../README.md")]
```

Write the `README.md` so it renders correctly under both a Markdown renderer and rustdoc.

#### Steps

1. For published crates, inspect the crate root and `README.md` when either one changes.
2. Check that crate-level docs include the README with `#![doc = include_str!("../README.md")]` or the path appropriate for that crate.
3. Verify that the README is valid both as standalone Markdown and as rustdoc content.
4. Reject duplicated crate-level prose that can drift from the README unless the crate has a documented reason for separate docs.

See also:
[Issue #2947](https://github.com/asterinas/asterinas/issues/2947)
for the rationale, the caveats, and a template;
the [`ostd-pod`](https://github.com/asterinas/asterinas/tree/main/ostd/libs/ostd-pod) crate
for a crate that already adopts it.
