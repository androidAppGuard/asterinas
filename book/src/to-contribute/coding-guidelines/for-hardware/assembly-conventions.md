# Assembly Conventions

### Use the correct section directive (`asm-section-directives`) {#asm-section-directives}

For built-in sections, use the short directive (e.g., `.text`).
For custom sections,
use the `.section` directive with flags and type
(e.g., `.section ".bsp_boot", "awx", @progbits`).

A blank line should follow each section definition
to visually separate it from the code that follows.

```asm
.section ".bsp_boot.stack", "aw", @nobits

boot_stack_bottom:
    .balign 4096
    .skip 0x40000  # 256 KiB
boot_stack_top:
```

#### Steps

1. Inspect each changed assembly section declaration in `.S` files and `global_asm!` blocks.
2. Require short built-in directives such as `.text` when using built-in sections.
3. Require `.section "name", "flags", @type` when defining a custom section, with flags and type matching linker and runtime expectations.
4. Check that a blank line separates the section definition from labels or instructions that follow.

### Place code-width directives after the section definition (`asm-code-width`) {#asm-code-width}

In x86-64, if an executable section contains only 64-bit code,
place the `.code64` directive directly after the section definition.
The same applies to `.code32` for 32-bit code.
In mixed sections, treat `.code64` and `.code32`
as function attributes (see below).

```asm
.text
.code64

.global foo
foo:
    mov rax, 1
    ret
```

#### Steps

1. Review x86 assembly sections that use `.code64` or `.code32`.
2. If the whole executable section uses one mode, require the code-width directive immediately after the section directive.
3. If a section mixes 32-bit and 64-bit code, treat the directive as part of the specific function or code block it applies to.
4. Verify that the directive placement matches the processor mode expected at entry to that code.

### Place attributes directly before the function (`asm-function-attributes`) {#asm-function-attributes}

Function attributes (`.global`, `.balign`, `.type`)
should be placed directly before the function label
and should not be indented.
Prefer `.global` over `.globl` for clarity.

```asm
.balign 4
.global foo
foo:
    mov rax, 1
    ret
```

#### Steps

1. For every changed assembly function label, inspect the preceding directives.
2. Require `.global`, `.balign`, `.type`, and mode directives that apply to a single function to appear directly before that function label.
3. Check that these directives are not indented as instructions.
4. Prefer `.global` spelling over `.globl` unless the file already has a strong local reason for the alternate spelling.

### Add `.type` and `.size` for Rust-callable functions (`asm-type-and-size`) {#asm-type-and-size}

Functions that can be called from Rust code
should include the `.type` and `.size` directives.
This gives debuggers a better understanding of the function.

```asm
.global bar
.type bar, @function
bar:
    mov rax, 2
    ret
.size bar, .-bar
```

This does not apply to boot entry points,
exception trampolines, or interrupt trampolines —
they may not fit the typical definition of "function"
and their sizes may be ill-defined.

#### Steps

1. Identify assembly labels that Rust or C code can call as functions.
2. Require `.type label, @function` before the label and `.size label, .-label` after the function body.
3. Exempt boot entry points, exception trampolines, and interrupt trampolines only when their control flow or boundaries are not ordinary functions.
4. Check that `.size` uses the matching label and still covers the intended body after local labels or fall-through code.

See also:
PR [#2320](https://github.com/asterinas/asterinas/pull/2320).

### Use unique label prefixes to avoid name clashes (`asm-label-prefixes`) {#asm-label-prefixes}

A Rust crate is a single translation unit,
so `global_asm!` labels in different modules
within the same crate share the same global namespace.
Add custom prefixes to labels to avoid name clashes
(e.g., `bsp_` for BSP boot code, `ap_` for AP boot code).

```asm
# Good — prefixed to avoid clashes
bsp_boot_stack_top:
ap_boot_stack_top:

# Bad — generic names risk duplication
boot_stack_top:
```

#### Steps

1. List labels introduced by changed `global_asm!` blocks.
2. Check whether the label name could collide with another label in the same Rust crate translation unit.
3. Require a subsystem, path, or purpose prefix for non-local labels in `global_asm!`.
4. Compare with nearby assembly files to keep prefix conventions consistent.

See also:
PR [#2571](https://github.com/asterinas/asterinas/pull/2571)
and [#2573](https://github.com/asterinas/asterinas/pull/2573).

### Prefer `.balign` over `.align` (`asm-prefer-balign`) {#asm-prefer-balign}

The `.align` directive's behavior varies across architectures —
on some it specifies a byte count,
on others a power of two.
Use `.balign` for unambiguous byte-count alignment.

```asm
# Good — unambiguous
.balign 4096

# Bad — architecture-dependent meaning
.align 12
```

#### Steps

1. Search changed assembly for `.align`.
2. Require `.balign` with an explicit byte count for alignment.
3. If the old value was a power-of-two exponent, require conversion to the equivalent byte count.
4. Verify stack, page, and function alignment values against the relevant ABI or hardware requirement.

See also:
PR [#2368](https://github.com/asterinas/asterinas/pull/2368).
