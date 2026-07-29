---
date: 2026-07-27
mode: files
files: ostd/src/arch/x86/trap/mod.rs,ostd/src/arch/x86/trap/trap.S
head: a64f44ce3-dirty
branch: HEAD
---

# Summary

The trap entry code is compact and keeps the Rust/assembly boundary narrow, but the review found two major ABI/layout defects in `trap.S`: several modern x86 exceptions that push error codes are treated as no-error-code vectors, and the Rust handler can be called with a misaligned stack. A third hardware issue leaves the exported handler table with only 1-byte input-section alignment even though Rust reads it as a `usize` array.

The remaining findings are mostly maintainability/documentation cleanups around guideline conformance: qualify free-function imports through their parent modules, avoid single-letter names in the central trap path, keep IRQ-state conditionals explicit or guard-based, document the unsafe trap-handler contract, correct the user-page-fault helper summary, and name the TSS offsets used by assembly.

## Maintainability

### `ostd/src/arch/x86/trap/mod.rs` line 30

> ```diff
> use crate::{
>     arch::{
>         cpu::context::CpuException,
>         irq::{HwIrqLine, disable_local, enable_local},
>     },
>     irq::call_irq_callback_functions,
> };
> ...
> enable_local();
> disable_local();
> call_irq_callback_functions(
> ```

`qualified-fn-imports` (minor): `disable_local`, `enable_local`, `handle_virtual_exception`, and `call_irq_callback_functions` are imported as bare free functions, so call sites like `enable_local()` and `call_irq_callback_functions(...)` do not show which module owns the operation.

**Fix.** Import the parent modules instead, using an alias where the two `irq` modules would collide, and call the functions as `arch_irq::enable_local()`, `arch_irq::disable_local()`, `tdx_guest::handle_virtual_exception(...)`, and `irq::call_irq_callback_functions(...)`.

### `ostd/src/arch/x86/trap/mod.rs` line 135

> ```diff
> unsafe extern "sysv64" fn trap_handler(f: &mut TrapFrame) {
> ...
> fn handle_user_page_fault(f: &mut TrapFrame, exception: &CpuException) {
> ```

`descriptive-names` (minor): `f` is a single-letter parameter name for a central trap path, and readers have to infer at each use that `f.rflags`, `f.trap_num`, and `f.rip` are fields of the current trap frame.

**Fix.** Rename `f` to `trap_frame` in `trap_handler` and in `handle_user_page_fault`, then update the call sites and panic formatting to use the descriptive name.

### `ostd/src/arch/x86/trap/mod.rs` line 136

> ```diff
> fn enable_local_if(cond: bool) {
>     if cond {
>         enable_local();
>     }
> }
> 
> fn disable_local_if(cond: bool) {
>     if cond {
>         disable_local();
>     }
> }
> ```

`no-bool-args` (minor): `enable_local_if(cond: bool)` and `disable_local_if(cond: bool)` hide a control-flow decision behind a boolean argument, so each call site has to remember that `true` means "perform the IRQ-state transition" and `false` means "do nothing".

**Fix.** Keep the condition visible at the call sites, or replace the paired helpers with a small typed guard that restores the previous IRQ state on drop.

### `ostd/src/arch/x86/trap/mod.rs` line 206

> ```diff
> /// Handles page fault from user space.
> fn handle_user_page_fault(f: &mut TrapFrame, exception: &CpuException) {
> ```

`accurate-names` (minor): The doc comment says `handle_user_page_fault` handles a page fault "from user space", but this helper is reached from the kernel trap handler for a kernel-mode fault on a user-space address.

**Fix.** Change the summary to describe the actual case, for example `/// Handles a kernel page fault on a user-space address.`

### `ostd/src/arch/x86/trap/trap.S` line 88

> ```diff
> mov gs:12, rax          # store user rsp -> scratch at TSS.sp1
> ...
> mov rax, gs:4           # rax = kernel stack
> ```

`no-magic-number` (minor): `gs:12` and `gs:4` encode TSS slot offsets directly in the trap path. The comments say `TSS.sp1` and `kernel stack`, but the numeric contract still has to be re-derived from the x86 TSS layout whenever this code is read or changed.

**Fix.** Define named assembly constants such as `TSS_RSP0_OFFSET` and `TSS_RSP1_OFFSET`, then use `gs:TSS_RSP1_OFFSET` and `gs:TSS_RSP0_OFFSET` at these loads and stores.

## Correctness

### `ostd/src/arch/x86/trap/trap.S` line 30

> ```diff
> .macro DEF_HANDLER, i
> _trap_handler_\i:
> .if \i == 8 || (\i >= 10 && \i <= 14) || \i == 17
>     # error code pushed by CPU
>     push    \i          # interrupt vector
> ```

Incorrect exception frame layout (major): `#CP` (`21`), `#VC` (`29`), and `#SX` (`30`) all push a CPU error code, but `DEF_HANDLER` sends them through the no-error-code path and adds a synthetic `0`. For a user `#CP`, `trap_common` then reads the saved `rip` as `cs`; depending on the low bits of `rip`, it either treats the interrupted user stack as the `UserContext` pointer or builds a corrupt kernel `TrapFrame`.

**Fix.** Handle all error-code exceptions in the first branch, e.g. include `\i == 21 || \i == 29 || \i == 30` alongside `8`, `10..=14`, and `17`, so the live stack layout matches what `trap_common` expects.

## Security

### `ostd/src/arch/x86/trap/mod.rs` line 135

> ```diff
> /// Handles traps (only from kernel).
> // SAFETY: The name does not collide with other symbols.
> #[unsafe(no_mangle)]
> unsafe extern "sysv64" fn trap_handler(f: &mut TrapFrame) {
> ```

`document-safety-conds` (minor): `trap_handler` is an `unsafe extern` function but its doc comment does not include a `# Safety` section. The assembly caller must supply a valid, uniquely borrowed `TrapFrame` matching the `trap.S` layout, so the caller obligations should be explicit at this unsafe boundary.

**Fix.** Add a `# Safety` section documenting the required trap-frame pointer/layout invariants before `unsafe extern "sysv64" fn trap_handler`.

## Hardware

### `ostd/src/arch/x86/trap/trap.S` line 55

> ```diff
> .rodata
> 
> .macro DEF_TABLE_ENTRY, i
>     .quad _trap_handler_\i
> .endm
> 
> .global trap_handler_table
> trap_handler_table:
> ```

Rust assembly ABI alignment (major): `trap_handler_table` is exposed to Rust as `VECTORS: [usize; NUM_INTERRUPTS]`, but the assembly emits it in `.rodata` without any `.balign 8`. LLVM emits this input section with 1-byte alignment, so if the linker places another odd-sized `.rodata` input section before it, Rust can form a misaligned `[usize]` reference while initializing the IDT.

**Fix.** Add `.balign 8` immediately before `trap_handler_table` so the input section advertises the alignment required by Rust's `usize` array ABI.

### `ostd/src/arch/x86/trap/trap.S` line 133

> ```diff
>     mov rdi, rsp
>     call trap_handler
> 
>     pop rax
> ```

`16b-align-rsp-before-call` (major): `call trap_handler` can execute with `%rsp % 16 == 8`. For example, if a kernel interrupt lands just before a compiler-emitted `call`, the interrupted `%rsp` is 16-byte aligned; the normalized CPU/stub frame adds 5 qwords and this path saves 16 more qwords, leaving `%rsp` misaligned before calling Rust.

**Fix.** Align a temporary call stack before `call trap_handler` while keeping `rdi` pointing at the original `TrapFrame`, then undo the padding before popping the frame.

## Retracted by verification

- `ostd/src/arch/x86/trap/mod.rs` line 202: retracted `closure-fn-suffix`; the cited local rule applies to closure variables, but the reviewed binding is a plain function pointer parameter/local.
