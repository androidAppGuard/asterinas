# Comments

### Follow RFC 1574 summary line conventions (`rfc1574-summary`) {#rfc1574-summary}

The first line of a doc comment should be concise and one sentence.
Its grammatical form depends on what the item is:

- **Functions and methods** — third-person singular present indicative verb
  ("Returns", "Creates", "Acquires"), describing the action performed.
- **Types (structs, enums, traits, type aliases), modules, and fields** —
  a noun phrase naming the thing, not describing an action.
  This matches the Rust standard library convention
  (e.g., `Vec` is "A contiguous growable array type").

```rust
/// Returns the mapping's start address.
pub fn map_to_addr(&self) -> Vaddr {
    self.map_to_addr
}

/// A policy for how [`FsPath::from_fd_at`] treats an empty `path_str`.
pub enum EmptyPathStr { /* ... */ }

/// A guard that releases a [`SpinLock`] when dropped.
pub struct SpinLockGuard<'a, T> { /* ... */ }
```

#### Steps

1. Inspect the first sentence of each added or changed `///` and `//!` comment.
2. Check that function and method summaries start with a third-person verb such as "Returns", "Creates", or "Acquires".
3. Check that type, trait, module, and field summaries are noun phrases rather than actions.
4. Require the first line to be a concise sentence that can stand alone in rustdoc summaries.

### End sentence comments with punctuation (`comment-punctuation`) {#comment-punctuation}

If a comment line is a full sentence,
end it with proper punctuation.
This improves readability in dense code
and avoids fragmented prose.

```rust
// Good — complete sentence with punctuation.
// SAFETY: The pointer is derived from a live allocation.

// Bad — complete sentence without punctuation
// SAFETY: The pointer is derived from a live allocation
```

#### Steps

1. Review changed `//`, `///`, `//!`, and block comments.
2. Decide whether each line is a complete sentence or a fragment, label, list item, or short note.
3. Require terminal punctuation for complete sentences, including `SAFETY:` comments.
4. Leave fragments unpunctuated when punctuation would make them look like full prose.

### Wrap identifiers in backticks (`backtick-identifiers`) {#backtick-identifiers}

Type names, method names,
and code identifiers in doc comments
should be wrapped in backticks for rustdoc rendering.
When referring to types,
prefer rustdoc links (`[TypeName]`) where possible.

```rust
/// Acquires the [`SpinLock`] and returns a guard
/// that releases the lock on [`Drop`].
///
/// Callers must not call `acquire` while holding
/// a [`RwMutex`] to avoid deadlock.
pub fn acquire(&self) -> SpinLockGuard<'_, T> { ... }
```

#### Steps

1. Scan doc comments for references to types, traits, methods, fields, modules, constants, macros, parameters, and keywords used as code.
2. Require backticks around code identifiers that are not linked.
3. Prefer rustdoc links for types, traits, and important APIs when the target is in scope and stable.
4. Do not backtick ordinary English words that are not identifiers in the documented API.

### Do not disclose implementation details in doc comments (`no-impl-in-docs`) {#no-impl-in-docs}

Doc comments should describe _what_ the API does
and _how to use it_,
not _how it is implemented internally_.

```rust
// Good — behavior-oriented
/// Returns the number of active connections.

// Bad — leaks implementation details
/// Returns the length of the internal `HashMap`
/// that tracks connections by socket address.
```

#### Steps

1. Read each public doc comment as an API user rather than as an implementer.
2. Separate behavior, guarantees, parameters, errors, and usage from internal storage, helper calls, caches, and algorithms.
3. Flag implementation details unless they are part of the public contract, performance guarantee, or safety requirement.
4. If the implementation detail is useful for maintainers only, move it to an internal comment near the code.
