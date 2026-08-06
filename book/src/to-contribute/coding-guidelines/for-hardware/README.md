# For Hardware

*Is the low-level / arch-specific code correct against the hardware and ABI contract?*

This is the index of the **hardware** guidelines.
Each subsection is its own page,
and each entry below links a stable `short-name` to its guideline,
with a one-line gist so a reader (or a review tool) can grasp the guideline before opening it.

## Index

**[Assembly Conventions](assembly-conventions.md)**
- [`asm-section-directives`](assembly-conventions.md#asm-section-directives): Use short directives for built-in sections and flagged `.section` directives for custom ones; apply when declaring an assembly section and leave a blank line after it.
- [`asm-code-width`](assembly-conventions.md#asm-code-width): Put `.code64` or `.code32` after a single-mode section definition; apply when declaring an x86 section containing only one code width.
- [`asm-function-attributes`](assembly-conventions.md#asm-function-attributes): Put `.global`, `.balign`, and `.type` directly before the function label and prefer `.global`; apply when defining an assembly function.
- [`asm-type-and-size`](assembly-conventions.md#asm-type-and-size): Add `.type @function` and `.size` to Rust-callable assembly functions; apply when defining them, except boot and trap trampolines.
- [`asm-label-prefixes`](assembly-conventions.md#asm-label-prefixes): Prefix `global_asm!` labels to keep names unique; apply when defining labels in a crate-wide assembly namespace.
- [`asm-prefer-balign`](assembly-conventions.md#asm-prefer-balign): Use `.balign` for unambiguous byte-count alignment; apply whenever assembly code needs alignment across architectures.

**[CPU Architecture-Specific](cpu-architecture-specific/)**
- [x86-64](cpu-architecture-specific/x86-64.md)
    - [`16b-align-rsp-before-call`](cpu-architecture-specific/x86-64.md#16b-align-rsp-before-call): Keep `%rsp` 16-byte aligned immediately before `call`; apply when x86-64 assembly calls Rust or C code.
