# For Documentation

*Are user-facing docs and compatibility artifacts correct, current, and well-written?*

This is the index of the **documentation** guidelines.
Each subsection is its own page,
and each entry below links a stable `short-name` to its guideline,
with a one-line gist so a reader (or a review tool) can grasp the guideline before opening it.

## Index

**[General Style](general-style.md)**
- [`semantic-line-breaks`](general-style.md#semantic-line-breaks): Break prose at sentence and clause boundaries so each line carries one idea; apply when writing Markdown or doc comments, except mostly read-only RFC documents.
- [`readme-as-crate-doc`](general-style.md#readme-as-crate-doc): Use a published crate's `README.md` as its crate-level Rust doc; apply when documenting a crate published to crates.io and rendered on docs.rs.

**[Path-Specific](path-specific/)**
- [`kernel/`](path-specific/kernel.md)
    - [`linux-compat-docs`](path-specific/kernel.md#linux-compat-docs): Keep Linux Compatibility docs synchronized with syscall and kernel-parameter support; apply when a `kernel/` change adds or enhances a user-visible syscall or kernel parameter.
