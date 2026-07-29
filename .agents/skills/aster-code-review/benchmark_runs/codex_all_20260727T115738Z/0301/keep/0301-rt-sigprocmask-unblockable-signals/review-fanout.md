---
date: 2026-07-27
mode: files
files: kernel/src/syscall/rt_sigprocmask.rs
head: 2154124dc
branch: HEAD
---

# Summary

`sys_rt_sigprocmask` has the expected high-level structure: it separates argument validation from mask update logic, keeps the syscall body small, and uses the existing `SigMask` abstraction. The highest-risk issues are in the syscall semantics around user-provided masks. `SIG_SETMASK` can persist `SIGKILL`/`SIGSTOP` bits even though Linux requires attempts to block them to be ignored, and the signal delivery path consults the stored blocked mask directly. The handler also parses `how` before checking whether `set_ptr` is null, so a mask-query call can fail incorrectly, and it writes `oldset` before reading `set`, which breaks valid aliasing of the two user pointers.

Fixing the mask flow should be the first priority: read the optional input mask before writing `oldset`, ignore `how` when `set_ptr == 0`, and sanitize every path that installs a new blocked mask. The remaining findings are maintainability cleanups around naming the ABI size, citing the exact `sigprocmask(2)` source, and narrowing/formatting the private `MaskOp` enum.

## Maintainability

### `kernel/src/syscall/rt_sigprocmask.rs` line 26

> ```diff
>     if sigset_size != 8 {
>         return_errno_with_message!(Errno::EINVAL, "sigset size is not equal to 8");
>     }
> ```

`no-magic-number` (minor): `8` embeds the expected `SigMask` byte size directly in `sys_rt_sigprocmask`; the ABI size has to be inferred at the call site and updated by hand if `SigMask` changes.

**Fix.** Compare against `size_of::<SigMask>()`, matching nearby signal-mask syscall code, or introduce a named `SIGMASK_SIZE_BYTES` constant if this value needs to be shared.

### `kernel/src/syscall/rt_sigprocmask.rs` line 51

> ```diff
>             MaskOp::Block => {
>                 // According to man pages, "it is not possible to block SIGKILL or SIGSTOP.
>                 // Attempts to do so are silently ignored."
> ```

`cite-sources` (nit): The comment says `man pages` and quotes the `SIGKILL`/`SIGSTOP` behavior, but it does not identify which man page defines the rule; the next reader has to search for the source.

**Fix.** Cite the exact source in the comment, for example `sigprocmask(2)`, instead of the vague `man pages` reference.

### `kernel/src/syscall/rt_sigprocmask.rs` line 68

> ```diff
> #[derive(Debug, Clone, Copy, PartialEq, Eq, TryFromInt)]
> #[repr(u32)]
> pub enum MaskOp {
> ```

`alphabetical-attrs` (minor): `MaskOp` places `#[derive(...)]` before `#[repr(u32)]`, and the traits inside `#[derive(...)]` are not alphabetical.

**Fix.** Shared with the `narrow-visibility` finding on `MaskOp`: make the enum private, put non-derive attributes first, and sort the derive list:

```rust
#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq, TryFromInt)]
enum MaskOp {
```

### `kernel/src/syscall/rt_sigprocmask.rs` line 70

> ```diff
> #[derive(Debug, Clone, Copy, PartialEq, Eq, TryFromInt)]
> #[repr(u32)]
> pub enum MaskOp {
> ```

`narrow-visibility` (minor): `MaskOp` is declared `pub`, but it is only used inside `kernel/src/syscall/rt_sigprocmask.rs`; exposing it widens the module interface with an implementation detail.

**Fix.** Shared with the `alphabetical-attrs` finding on `MaskOp`: make the enum private while also putting `#[repr(u32)]` before `#[derive(...)]` and sorting the derived traits.

## Correctness

### `kernel/src/syscall/rt_sigprocmask.rs` line 21

> ```diff
> 21	    let mask_op = MaskOp::try_from(how)?;
> ...
> 47	    if set_ptr != 0 {
> 48	        let mut read_mask = ctx.user_space().read_val::<SigMask>(set_ptr)?;
> ```

Incorrect syscall semantics (major): `rt_sigprocmask` rejects an invalid `how` even when `set_ptr == 0`, but Linux `sigprocmask(2)` ignores `how` when `set` is `NULL` and only returns the old mask. A caller such as `rt_sigprocmask(999, 0, oldset, 8)` should succeed, but this returns `EINVAL` before copying `oldset`.

**Fix.** Only parse `how` when `set_ptr != 0`; when `set_ptr == 0`, skip mask modification and just copy `oldset` if requested.

### `kernel/src/syscall/rt_sigprocmask.rs` line 42

> ```diff
> 41	    if oldset_ptr != 0 {
> 42	        ctx.user_space()
> 43	            .write_val(oldset_ptr, &old_sig_mask_value)?;
> 44	    }
> ...
> 47	    if set_ptr != 0 {
> 48	        let mut read_mask = ctx.user_space().read_val::<SigMask>(set_ptr)?;
> ```

Incorrect user buffer ordering (major): `oldset_ptr` is written before `set_ptr` is read. If the caller passes the same address for `set_ptr` and `oldset_ptr`, the old mask overwrites the requested new mask before line `48` reads it, so `SIG_SETMASK` silently uses the old value. The same ordering also writes `oldset` even when a later invalid `set_ptr` makes the syscall fail with `EFAULT`.

**Fix.** Read and normalize the optional new `SigMask` into a local first, then update the kernel mask, and only copy `old_sig_mask_value` to `oldset_ptr` after the input copy has succeeded.

### `kernel/src/syscall/rt_sigprocmask.rs` line 60

> ```diff
> 57	            MaskOp::Unblock => {
> 58	                sig_mask_ref.store(old_sig_mask_value - read_mask, Ordering::Relaxed)
> 59	            }
> 60	            MaskOp::SetMask => sig_mask_ref.store(read_mask, Ordering::Relaxed),
> ```

Incorrect signal masking (major): `MaskOp::SetMask` stores the user mask without clearing `SIGKILL` and `SIGSTOP`. A caller can pass a full mask with `SIG_SETMASK`, after which signal delivery sees those bits in the blocked mask and can defer `SIGKILL` or `SIGSTOP`, even though `sigprocmask(2)` says attempts to block them must be silently ignored.

**Fix.** Shared with the Security finding on this line: clear `SIGKILL` and `SIGSTOP` from `read_mask` for every operation that can install bits, including `MaskOp::SetMask`, before storing it in `sig_mask_ref`.

## Security

### `kernel/src/syscall/rt_sigprocmask.rs` line 60

> ```diff
>     57	            MaskOp::Unblock => {
>     58	                sig_mask_ref.store(old_sig_mask_value - read_mask, Ordering::Relaxed)
>     59	            }
>     60	            MaskOp::SetMask => sig_mask_ref.store(read_mask, Ordering::Relaxed),
> ```

`validate-at-boundaries` (major): `SIG_SETMASK` stores the user-supplied `read_mask` without clearing `SIGKILL` and `SIGSTOP`. An attacker can call `rt_sigprocmask(SIG_SETMASK, &mask_with_SIGKILL, NULL, 8)` and persist those bits in `sig_mask`; later delivery checks use `blocked.contains(SIGKILL)` and skip the signal, making the process able to block signals that must be unblockable.

**Fix.** Shared with the Correctness finding on this line: sanitize the mask at the syscall boundary for `MaskOp::SetMask` too, for example by clearing `SIGKILL` and `SIGSTOP` before the `store` in that arm or by normalizing `read_mask` for both `MaskOp::Block` and `MaskOp::SetMask`.
