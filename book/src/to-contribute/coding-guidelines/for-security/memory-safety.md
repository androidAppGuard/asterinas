# Memory Safety

### Justify every use of `unsafe` (`justify-unsafe-use`) {#justify-unsafe-use}

Every `unsafe` block must have a preceding `// SAFETY:` comment
that justifies why the operation is sound.
For multi-condition invariants,
use a numbered list:

```rust
// SAFETY:
// 1. We have exclusive access to both the current context
//    and the next context (see above).
// 2. The next context is valid (because it is either
//    correctly initialized or written by a previous
//    `context_switch`).
unsafe {
    context_switch(next_task_ctx_ptr, current_task_ctx_ptr);
}
```

#### Steps

1. Search changed OSTD code for every `unsafe` block and unsafe operation hidden inside macros.
2. Check that each `unsafe` block has an immediately preceding `// SAFETY:` comment.
3. Verify all relevant soundness conditions: validity, aliasing, lifetimes, initialization, alignment, and concurrency.
4. Reject comments that merely restate the operation or say it is safe without proving why the preconditions hold at that point.

See also:
PR [#2958](https://github.com/asterinas/asterinas/pull/2958)
and [#836](https://github.com/asterinas/asterinas/pull/836).

### Document safety conditions (`document-safety-conds`) {#document-safety-conds}

All `unsafe` functions and traits
must include a `# Safety` section in their doc comments
describing the conditions, properties, or invariants that callers must uphold.
State exactly what the caller must guarantee —
not implementation details or side effects.

```rust
/// A marker trait for guard types that enforce the atomic mode.
///
/// # Safety
///
/// The implementer must ensure that the atomic mode is maintained while
/// the guard type is alive.
pub unsafe trait InAtomicMode: core::fmt::Debug {}
```

#### Steps

1. Find every new or changed `unsafe fn`, `unsafe trait`, and unsafe trait implementation contract.
2. Check the rustdoc for a `# Safety` section.
3. Require the section to state the caller's or implementer's obligations precisely enough to audit each call or implementation.
4. Keep implementation details, ordinary errors, and side effects outside `# Safety` unless they affect soundness.

### Deny unsafe code in `kernel/` (`deny-unsafe-kernel`) {#deny-unsafe-kernel}

All crates under `kernel/` must deny unsafe:

```rust
#![deny(unsafe_code)]
```

Only OSTD (`ostd/`) crates may contain `unsafe` code.
If a kernel crate requires an unsafe operation,
the functionality should be provided as a safe API in OSTD.

#### Steps

1. For any changed crate under `kernel/`, open the crate root and confirm it has `#![deny(unsafe_code)]`.
2. Search the kernel diff for `unsafe`, unsafe FFI, unsafe trait impls, and macros that may expand to unsafe code.
3. Reject unsafe code in `kernel/` and require the operation to move behind a safe OSTD abstraction.
4. Check that the OSTD abstraction documents and enforces the safety invariant rather than pushing it back to kernel callers.

### Reason about safety at the module boundary (`module-boundary-safety`) {#module-boundary-safety}

The safety of an `unsafe` block
depends on ALL code that can access the same private state.
Encapsulate unsafe abstractions
in the smallest possible module
to minimize the "audit surface."
Any code in the same module
that can modify relied-upon fields
is part of the safety argument.

```rust
// Good — small, focused module limits the audit surface
mod frame_allocator {
    /// Invariant: `next` is always a valid frame index.
    struct FrameAlloc {
        next: usize,
        // ...
    }

    impl FrameAlloc {
        pub fn alloc(&mut self) -> PhysAddr {
            // SAFETY: `next` is always valid (see invariant above).
            // Only code in this module can modify `next`.
            unsafe { self.alloc_frame_unchecked(self.next) }
        }
    }
}
```

#### Steps

1. For each unsafe abstraction, identify the private state and invariants its safety argument relies on.
2. List all code in the same module that can read or mutate that state, including helpers, trait impls, and tests compiled with special cfgs.
3. Check whether the module is small enough for a reviewer to audit the entire invariant.
4. Require moving unsafe state into a smaller module or narrowing visibility when unrelated code can affect the safety argument.
