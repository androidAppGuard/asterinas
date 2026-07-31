---
date: 2026-07-30
mode: diff
base: c56aee92f
head: b6cc68ac3
branch: HEAD
title: "Review of futex compare-and-block changes"
---

# Summary

The change moves futex behavior closer to Linux by fixing wake/requeue count handling and adding a `FUTEX_WAKE_OP` path, with the tests unblocked accordingly. The serious issues are all in the new `FUTEX_WAKE_OP` implementation: the encoded operands are decoded with the wrong signedness, `FUTEX_OP_ANDN` computes the operands in reverse order, large shifted operands can overflow, and the operation is not performed as one atomic read-modify-wake sequence.

Fix the Linux semantic mismatches before relying on the newly unblocked gVisor coverage. After that, the remaining work is mostly local cleanup: keep nonnegative waiter counts typed as `usize` below the syscall ABI boundary, name the `FUTEX_WAKE_OP` bitfield constants, apply the attribute/doc-comment style rules, and update the Linux compatibility documentation for the newly exposed futex operation.

## Maintainability

### `commit a9b9f559e message`

> ```diff
> Adjust and correct parts of the futex implementation code
> ```

`imperative-subject` (nit): The subject `Adjust and correct parts of the futex implementation code` is too vague for commit archaeology; it does not say which `futex` behavior or interface is being changed.

**Fix.** Use a concrete imperative subject, for example:
```text
Fix `FUTEX_WAKE` and `FUTEX_REQUEUE` count handling
```

### `commit b6cc68ac3 message`

> ```diff
> Enable FUTEX_WAKE_OP
> ```

`imperative-subject` (nit): The subject `Enable FUTEX_WAKE_OP` names the `FUTEX_WAKE_OP` operation without Markdown code formatting.

**Fix.** Write the subject as:
```text
Enable `FUTEX_WAKE_OP`
```

### `kernel/src/process/posix_thread/futex.rs` line 93

> ```diff
> pub fn futex_wake(futex_addr: Vaddr, max_count: usize, pid: Option<Pid>) -> Result<isize> {
> ...
> ) -> Result<isize> {
> ...
> ) -> Result<isize> {
> ```

`rust-type-invariants` (major): `futex_wake`, `futex_wake_bitset`, `futex_wake_op`, and `futex_requeue` now return `Result<isize>`, but these process-layer helpers only produce nonnegative waiter counts. Pulling the signed syscall ABI type into this layer weakens the count invariant and makes negative counts representable internally.

**Fix.** Keep these helpers returning `Result<usize>` and convert to `isize` only at the `SyscallReturn::Return` boundary in `sys_futex`.

### `kernel/src/process/posix_thread/futex.rs` line 122

> ```diff
> /// This struct encodes the operation and comparison that are to be performed during
> /// the futex operation with `FUTEX_WAKE_OP`.
> ```

`rfc1574-summary` (nit): The doc summary for `FutexWakeOpEncode` starts with `This struct encodes...`; type summaries should be noun phrases, and this wording reads like implementation commentary.

**Fix.** Use a noun-phrase summary such as `/// A decoded \`FUTEX_WAKE_OP\` operation and comparison.`

### `kernel/src/process/posix_thread/futex.rs` line 146

> ```diff
> #[derive(Debug, Copy, Clone, TryFromInt, PartialEq)]
> #[repr(u32)]
> #[expect(non_camel_case_types)]
> enum FutexWakeOp {
> ```

`alphabetical-attrs` (nit): `FutexWakeOp` puts `#[derive(...)]` before non-derive attributes and lists derive traits as `Debug, Copy, Clone, TryFromInt, PartialEq`, which does not follow the required attribute and derive ordering.

**Fix.** Order the attributes and derive list as:
```rust
#[expect(non_camel_case_types)]
#[repr(u32)]
#[derive(Clone, Copy, Debug, PartialEq, TryFromInt)]
```

### `kernel/src/process/posix_thread/futex.rs` line 150

> ```diff
> /// res = oparg;
> FUTEX_OP_SET = 0,
> /// res = oparg + oldval;
> FUTEX_OP_ADD = 1,
> ```

`backtick-identifiers` (nit): The `FutexWakeOp` variant docs are code formulas, but identifiers such as `res`, `oparg`, and `oldval` are left as prose.

**Fix.** Format these formulas as code spans or fenced code blocks, for example `/// \`res = oparg;\``; apply the same formatting to each operation variant.

### `kernel/src/process/posix_thread/futex.rs` line 162

> ```diff
> #[derive(Debug, Copy, Clone, TryFromInt, PartialEq)]
> #[repr(u32)]
> #[expect(non_camel_case_types)]
> enum FutexWakeCmp {
> ```

`alphabetical-attrs` (nit): `FutexWakeCmp` repeats the same nonstandard attribute order and unsorted derive list as `FutexWakeOp`.

**Fix.** Order the attributes and derive list as:
```rust
#[expect(non_camel_case_types)]
#[repr(u32)]
#[derive(Clone, Copy, Debug, PartialEq, TryFromInt)]
```

### `kernel/src/process/posix_thread/futex.rs` line 182

> ```diff
> let is_oparg_shift = (bits >> 31) & 1 == 1;
> let op = FutexWakeOp::try_from((bits >> 28) & 0x7)?;
> let cmp = FutexWakeCmp::try_from((bits >> 24) & 0xf)?;
> let oparg = (bits >> 12) & 0xfff;
> let cmparg = bits & 0xfff;
> ```

`no-magic-number` (minor): `FutexWakeOpEncode::from_u32` embeds the `FUTEX_WAKE_OP` bit layout with bare literals such as `31`, `28`, `0x7`, `24`, `0xf`, `12`, and `0xfff`; these are external ABI field offsets and masks.

**Fix.** Introduce named constants for the `FUTEX_WAKE_OP` shift flag, field shifts, and field masks, then parse through those constants.

## Correctness

### `kernel/src/process/posix_thread/futex.rs` line 185

> ```diff
> let oparg = (bits >> 12) & 0xfff;
> let cmparg = bits & 0xfff;
> ```

Incorrect signed decoding (major): `oparg` and `cmparg` are decoded as unsigned `u32`, but the 12-bit fields must be sign-extended. With encoded `oparg = 0xfff` and old value `10`, `FUTEX_OP_ADD` produces `4105` here instead of `9`; signed comparisons are also wrong. ([code.googlesource.com](https://code.googlesource.com/linux/torvalds/linux/%2B/de758035702576ac0e5ac0f93e3cce77144c3bd3/kernel/futex.c?utm_source=openai))

**Fix.** Sign-extend both fields to `i32` before arithmetic and comparisons, while preserving the resulting 32-bit bit pattern when writing the futex word.

### `kernel/src/process/posix_thread/futex.rs` line 199

> ```diff
> 1 << self.oparg
> ```

`checked-arithmetic` (major): The shift amount is syscall-controlled. Setting the shift flag with `oparg >= 32` reaches `1 << self.oparg` and can panic in checked builds.

**Fix.** Shared with the security `validate-at-boundaries` comment: validate or normalize the shift count before the shift. For Linux compatibility, mask it into the `u32` shift domain before `1u32 << shift`; otherwise reject it with `Errno::EINVAL` while parsing `FutexWakeOpEncode`.

### `kernel/src/process/posix_thread/futex.rs` line 208

> ```diff
> FutexWakeOp::FUTEX_OP_ANDN => oparg & !old_val,
> ```

Reversed bit operation (major): `FUTEX_OP_ANDN` must compute `oldval & !oparg`, but this code computes `oparg & !old_val`. For `old_val = 0b1111` and `oparg = 0b0011`, it writes `0` instead of `0b1100`. ([man7.org](https://man7.org/linux/man-pages/man2/futex_wake_op.2const.html?utm_source=openai))

**Fix.** Implement the operation as `old_val & !oparg`.

### `kernel/src/process/posix_thread/futex.rs` line 237

> ```diff
> let old_val = ctx.user_space().read_val(futex_new_addr)?;
> let new_val = wake_op.calculate_new_val(old_val);
> ctx.user_space().write_val(futex_new_addr, &new_val)?;
> ```

`atomic-critical-sections` (major): The user futex word is updated with separate `read_val` and `write_val` calls. Two concurrent `FUTEX_OP_ADD` callers can both read `0` and write `1`, losing an update and making `should_wake` use stale state. `FUTEX_WAKE_OP` requires an atomic read-modify-write. ([man7.org](https://man7.org/linux/man-pages/man2/futex_wake_op.2const.html?utm_source=openai))

**Fix.** Shared with the other `atomic-critical-sections` comment: implement a combined `FUTEX_WAKE_OP` path that keeps the operation's user-memory read/modify/write and both futex-bucket wake decisions in one total order, using the returned old value for the comparison.

### `kernel/src/process/posix_thread/futex.rs` line 241

> ```diff
> let mut res = futex_wake(futex_addr, max_count, pid)?;
> 
> if wake_op.should_wake(old_val) {
>     res += futex_wake(futex_new_addr, new_max_count, pid)?;
> }
> ```

`atomic-critical-sections` (major): The operation calls `futex_wake` twice, and each helper releases its bucket lock before returning. Another futex operation can interleave between the two wakes, violating the requirement that the update, first wake, comparison, and second wake be atomically and totally ordered. ([man7.org](https://man7.org/linux/man-pages/man2/futex_wake_op.2const.html?utm_source=openai))

**Fix.** Shared with the other `atomic-critical-sections` comment: implement a combined `FUTEX_WAKE_OP` path that keeps the operation's user-memory read/modify/write and both futex-bucket wake decisions in one total order, instead of using two independent `futex_wake` calls.

## Security

### `kernel/src/process/posix_thread/futex.rs` line 199

> ```diff
> fn calculate_new_val(&self, old_val: u32) -> u32 {
>     let oparg = if self.is_oparg_shift {
>         1 << self.oparg
>     } else {
>         self.oparg
>     };
> ```

`validate-at-boundaries` (major): `wake_op_bits` is fully user-controlled, and when `FUTEX_OP_ARG_SHIFT` is set the 12-bit `oparg` can be any value up to `4095`. Passing an encoded `FUTEX_WAKE_OP` with `oparg >= 32` reaches `1 << self.oparg`, so the syscall can trigger a shift overflow instead of returning a user error or applying the Linux-compatible mask.

**Fix.** Shared with the correctness shift-overflow comment: validate or normalize the shift count before the shift. For Linux compatibility, mask it into the `u32` shift domain before `1u32 << shift`; otherwise reject it with `Errno::EINVAL` while parsing `FutexWakeOpEncode`.

## Documentation

### `kernel/src/syscall/futex.rs` line 123

> ```diff
> +        FutexOp::FUTEX_WAKE_OP => {
> +            let futex_new_val = utime_addr as u32;
> +
> +            futex_wake_op(
> +                futex_addr,
> +                futex_new_addr,
> +                futex_val_to_max_count(futex_val),
> +                futex_val_to_max_count(futex_new_val),
> +                bitset,
> +                ctx,
> +                pid,
> +            )
> +        }
> ```

`linux-compat-docs` (major): This adds user-visible support for `FUTEX_WAKE_OP` through `sys_futex`, and the same commit unblocks the corresponding gVisor `WakeOp` tests, but the change does not update the Linux Compatibility documentation or syscall coverage artifacts for the newly supported `futex` operation.

**Fix.** Update the Linux Compatibility syscall coverage for `futex` in the same change, documenting `FUTEX_WAKE_OP` and its relevant arguments/behavior, and update the matching coverage artifact if this tree has one for syscall flag coverage.
