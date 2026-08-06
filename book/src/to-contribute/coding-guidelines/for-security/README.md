# For Security

*Could an adversary breach the security of the kernel?*

This is the index of the **security** guidelines.
Each subsection is its own page,
and each entry below links a stable `short-name` to its guideline,
with a one-line gist so a reader (or a review tool) can grasp the guideline before opening it.

## Index

**[Memory Safety](memory-safety.md)**
- [`justify-unsafe-use`](memory-safety.md#justify-unsafe-use): Explain why each `unsafe` block is sound in a preceding `// SAFETY:` comment; apply whenever writing or reviewing an unsafe block.
- [`document-safety-conds`](memory-safety.md#document-safety-conds): State caller obligations in a `# Safety` section; apply when declaring an `unsafe` function or trait.
- [`deny-unsafe-kernel`](memory-safety.md#deny-unsafe-kernel): Keep `unsafe` out of `kernel/` and expose needed operations through safe OSTD APIs; apply when adding or changing kernel or OSTD code.
- [`module-boundary-safety`](memory-safety.md#module-boundary-safety): Keep unsafe abstractions and their private state in the smallest auditable module; apply when designing or reviewing an unsafe abstraction.

**[Security Properties](security-properties.md)**
- [`validate-at-boundaries`](security-properties.md#validate-at-boundaries): Validate user-supplied pointers, descriptors, sizes, flags, and strings at entry boundaries; apply when data enters the kernel through a syscall or other user-facing interface.

No **path-specific** guidelines yet.
