---
date: 2026-07-30
mode: diff
base: 38c9ab061
head: 36a313263
branch: HEAD
title: "Review of diff against 38c9ab06150e2fc322357705f8c40c13b1915648"
---

# Summary

The change wires `fadvise64` into the x86-64 syscall table, adds a compact handler, updates the compatibility table, and enables related LTP cases. The intent is clear, and the new implementation follows the usual syscall-file layout.

The highest-risk issues are in the syscall boundary and advisory I/O behavior. Valid `advice` values currently reach `todo!()` and can panic the kernel; caller-controlled ranges can overflow or allocate an unbounded kernel buffer; and the implementation performs blocking file I/O while still holding the file-table lock. Fix those before relying on the newly enabled LTP coverage or marking the syscall fully implemented. The remaining issues are compatibility and hygiene gaps: preserve Linux error behavior instead of mapping all read failures to `EIO`, use the common fd lookup pattern and semantic `FileDesc` type, keep the enum private and attribute-sorted, and update the compatibility documentation/artifacts so the exposed syscall's supported behavior is documented.

## Maintainability

### `kernel/src/syscall/fadvise64.rs` line 8

> ```diff
> #[repr(i32)]
> #[derive(Debug, Clone, Copy, TryFromInt)]
> #[expect(non_camel_case_types)]
> pub enum FadviseBehavior {
> ```

`alphabetical-attrs` (nit): The outer attributes on `FadviseBehavior` are not in the project order: non-`derive` attributes should be sorted, and `#[derive(...)]` should come last with traits sorted alphabetically.

**Fix.** Order the attributes as:

```rust
#[expect(non_camel_case_types)]
#[repr(i32)]
#[derive(Clone, Copy, Debug, TryFromInt)]
```

### `kernel/src/syscall/fadvise64.rs` line 11

> ```diff
> pub enum FadviseBehavior {
>     POSIX_FADV_NORMAL = 0,
>     POSIX_FADV_RANDOM = 1,
> ```

`narrow-visibility` (minor): `FadviseBehavior` is declared `pub`, but the enum is only used inside `kernel/src/syscall/fadvise64.rs`. Exposing it through the private syscall module makes the implementation detail part of a wider interface than necessary.

**Fix.** Make `FadviseBehavior` private unless another module actually needs to name it.

### `kernel/src/syscall/fadvise64.rs` line 21

> ```diff
> pub fn sys_fadvise64(
>     fd: i32,
>     offset: usize,
>     len: usize,
> ```

`consistency` (minor): `sys_fadvise64` takes `fd` as a bare `i32`, while neighboring file-descriptor syscalls use the semantic `FileDesc` alias. That makes this syscall signature read differently from the rest of the file-descriptor syscall surface for no visible reason.

**Fix.** Import `FileDesc` from `crate::fs::file_table` and type `fd` as `FileDesc`, matching `sys_pread64`, `sys_pwrite64`, `sys_fallocate`, and similar syscalls.

### `kernel/src/syscall/fadvise64.rs` line 22

> ```diff
> pub fn sys_fadvise64(
>     fd: i32,
>     offset: usize,
>     len: usize,
>     advice: i32,
> ```

`rust-type-invariants` (major): `offset` and `len` are modeled as `usize` at the syscall entry point, but file-range syscall arguments need to preserve their signed ABI domain until the syscall validates them. Converting them to `usize` in the internal signature erases negative and boundary cases before the function can express the policy clearly.

**Fix.** Shared with the Correctness and Security range-validation comments: keep the syscall boundary types signed where the ABI is signed, validate `offset`/`len` explicitly, handle `len == 0` according to the Linux contract, and convert to `usize` only after checked range calculation.

### `kernel/src/syscall/fadvise64.rs` line 35

> ```diff
> let file_table = ctx.thread_local.borrow_file_table();
> let file_table_locked = file_table.unwrap().write();
> let file = file_table_locked.get_file(fd)?;
> ```

`dry` (major): This open-codes file-table lookup instead of using the shared `get_file_fast!` helper used by nearby fd syscalls. The helper is where this subsystem centralizes the lookup, cloning, and lock-scope policy, so reimplementing it here forces readers to audit whether this path still follows the same rules.

**Fix.** Use the common lookup path:

```rust
use crate::fs::file_table::{get_file_fast, FileDesc};

let mut file_table = ctx.thread_local.borrow_file_table_mut();
let file = get_file_fast!(&mut file_table, fd);
```

## Correctness

### `kernel/src/syscall/fadvise64.rs` line 22

> ```diff
> +pub fn sys_fadvise64(
> +    fd: i32,
> +    offset: usize,
> +    len: usize,
> +    advice: i32,
> ```

Incorrect signedness (major): `offset` and `len` are syscall `off_t`-style values, but this handler declares them as `usize`. Because the dispatcher casts raw `u64` arguments with `as _`, a caller can pass `offset = -4096` or `len = -1` and have it reinterpreted as a huge positive value instead of getting `EINVAL`.

**Fix.** Shared with the other range-validation comments: use signed syscall boundary types where the ABI is signed, reject negative values before converting to `usize`, handle `len == 0`, and perform checked end/alignment calculation.

### `kernel/src/syscall/fadvise64.rs` line 42

> ```diff
> +            let aligned_offset = offset.align_down(PAGE_SIZE);
> +            let aligned_end = (offset + len).align_up(PAGE_SIZE);
> +            let aligned_len = aligned_end - aligned_offset;
> ```

`checked-arithmetic` (major): `offset + len` and the following alignment math can overflow for user-controlled values. For example, `offset = usize::MAX - 1`, `len = 2`, and `advice = POSIX_FADV_WILLNEED` overflows before `align_up`; in release builds this can wrap into a bogus range and in debug builds it can panic.

**Fix.** Shared with the other range-validation comments: validate signed inputs first, then use `checked_add` and checked alignment or a bounded end calculation before computing `aligned_len`; return `EINVAL` on overflow.

### `kernel/src/syscall/fadvise64.rs` line 46

> ```diff
> +            if aligned_len > 0 {
> +                let mut buffer = vec![0u8; aligned_len];
> ```

Unbounded allocation (critical): `vec![0u8; aligned_len]` allocates directly from the caller-provided range. A user can call `fadvise64` with a very large `len` and force the kernel to allocate gigabytes or more just to process an advisory hint.

**Fix.** Shared with the Security allocation comment: do not materialize the whole advised range in a single buffer. Either make unsupported advice modes a no-op, use the page-cache readahead primitive directly, or process the range in a small fixed-size buffer.

### `kernel/src/syscall/fadvise64.rs` line 48

> ```diff
> +    let file_table = ctx.thread_local.borrow_file_table();
> +    let file_table_locked = file_table.unwrap().write();
> +    let file = file_table_locked.get_file(fd)?;
> ...
> +                file.read_bytes_at(aligned_offset, &mut buffer)
> ```

`no-io-under-spinlock` (major): `file_table_locked` remains live while `file.read_bytes_at(...)` runs. `RwArc::write()` holds an OSTD `RwLock` guard with preemption disabled, and the existing `get_file_fast!` helper explicitly says file operations can block and must not run while holding the file-table lock.

**Fix.** Clone or borrow the `Arc<dyn FileLike>` under the file-table lock, drop the lock guard, and only then call `read_bytes_at`; preferably use the established `borrow_file_table_mut()` plus `get_file_fast!` pattern.

### `kernel/src/syscall/fadvise64.rs` line 49

> ```diff
> +                file.read_bytes_at(aligned_offset, &mut buffer)
> +                    .map_err(|_| Error::with_message(Errno::EIO, "read failed in fadvise"))?;
> ```

Incorrect errno (major): `map_err(|_| EIO)` collapses every `read_bytes_at` failure into `EIO`. For a pipe, `FileLike::read_at` returns `ESPIPE`, but this syscall reports `EIO`; for a write-only inode handle, `read_at` returns `EBADF`, but that is also hidden.

**Fix.** Do not translate all read failures to `EIO`. Preserve the underlying errno with `?`, or avoid the normal read path and implement `fadvise64` validation so non-seekable descriptors return the contract errno directly.

### `kernel/src/syscall/fadvise64.rs` line 54

> ```diff
> +        FadviseBehavior::POSIX_FADV_SEQUENTIAL | FadviseBehavior::POSIX_FADV_WILLNEED => {
> +            ...
> +        }
> +        _ => todo!(),
> ```

Reachable panic (critical): `todo!()` is reachable from valid user input. `POSIX_FADV_NORMAL`, `POSIX_FADV_RANDOM`, `POSIX_FADV_DONTNEED`, and `POSIX_FADV_NOREUSE` are accepted by `FadviseBehavior::try_from(advice)`, then fall into `_ => todo!()` and panic the kernel.

**Fix.** Return success for valid advisory modes that are not implemented yet, or implement each mode explicitly; only unknown advice values should return `EINVAL`.

## Security

### `kernel/src/syscall/fadvise64.rs` line 22

> ```diff
> pub fn sys_fadvise64(
>     fd: i32,
>     offset: usize,
>     len: usize,
>     advice: i32,
>     ctx: &Context,
> ) -> Result<SyscallReturn> {
> ...
>             let aligned_end = (offset + len).align_up(PAGE_SIZE);
> ```

`validate-at-boundaries` (critical): `offset` and `len` are syscall-controlled values, but the boundary signature converts them to `usize`, so negative `off_t` inputs such as `len = -1` become `usize::MAX`. With `advice = POSIX_FADV_WILLNEED`, line 42 then calls `align_up()` on that value and its `checked_add(...).unwrap()` can panic, giving an unprivileged caller a kernel denial of service.

**Fix.** Shared with the Correctness range-validation comments: keep syscall ABI values signed where the ABI is signed, reject invalid negative ranges with `EINVAL`, handle `len == 0`, and use checked range arithmetic before any page alignment or cast to `usize`.

### `kernel/src/syscall/fadvise64.rs` line 46

> ```diff
>             let aligned_len = aligned_end - aligned_offset;
> 
>             if aligned_len > 0 {
>                 let mut buffer = vec![0u8; aligned_len];
> 
>                 file.read_bytes_at(aligned_offset, &mut buffer)
> ```

`validate-at-boundaries` (critical): `len` is fully controlled by the caller and `POSIX_FADV_WILLNEED`/`POSIX_FADV_SEQUENTIAL` allocate `vec![0u8; aligned_len]` for the whole advised range. A caller can pass a huge positive length and force a massive kernel allocation or OOM panic from an advisory syscall.

**Fix.** Shared with the Correctness allocation comment: do not allocate a buffer proportional to the user-supplied range. Treat the advice as a bounded no-op until page-cache readahead exists, or process it in a fixed-size bounded buffer with overflow-checked range arithmetic.

### `kernel/src/syscall/fadvise64.rs` line 54

> ```diff
>     match behavior {
>         FadviseBehavior::POSIX_FADV_SEQUENTIAL | FadviseBehavior::POSIX_FADV_WILLNEED => {
>             ...
>         }
>         _ => todo!(),
>     }
> ```

Reachable panic (critical): `FadviseBehavior::try_from()` accepts valid caller-controlled advice values such as `POSIX_FADV_NORMAL`, `POSIX_FADV_RANDOM`, `POSIX_FADV_DONTNEED`, and `POSIX_FADV_NOREUSE`, but the match falls through to `todo!()`. Any unprivileged caller can invoke `fadvise64(fd, 0, 0, POSIX_FADV_NORMAL)` on a valid fd and panic the kernel.

**Fix.** Handle every valid `FadviseBehavior` without panicking. Unsupported advisory modes should return success as a no-op, or return a normal syscall error if the contract requires one, but must not use `todo!()`.

## Hardware

### `kernel/src/syscall/fadvise64.rs` line 22

> ```diff
> pub fn sys_fadvise64(
>     fd: i32,
>     offset: usize,
>     len: usize,
>     advice: i32,
>     ctx: &Context,
> ) -> Result<SyscallReturn> {
> ```

Incorrect syscall ABI type (major): On x86-64, syscall `221` passes `offset` as signed `loff_t`, but `sys_fadvise64` declares `offset: usize`. Because the dispatcher casts the raw `u64` syscall register with `as _`, a user call with `offset = -1` reaches this handler as `usize::MAX` instead of a negative offset that can be rejected according to the syscall ABI.

**Fix.** Shared with the other range-validation comments: change `offset` to `i64`, reject `offset < 0`, and convert to `usize` only after checked range calculation. Keep ABI representation at the syscall boundary, similar to `sys_pread64`, `sys_pwrite64`, and `sys_fallocate`.

## Documentation

### `docs/src/kernel/linux-compatibility.md` line 244

> ```diff
> -| 221     | fadvise64        | ❌              |
> +| 221     | fadvise64        | ✅              |
> ```

Doc count mismatch (minor): The table now marks `fadvise64` as implemented, but the summary above still says `Asterinas implements 204 out of the 336 system calls`. That count is stale after this row changes to `✅`.

**Fix.** Update the summary count in `docs/src/kernel/linux-compatibility.md` so it matches the implemented syscall table after `fadvise64` is marked implemented.

### `kernel/src/syscall/arch/x86.rs` line 318

> ```diff
> +    SYS_FADVISE64 = 221        => sys_fadvise64(args[..4]);
> ```

`linux-compat-docs` (major): Adding `SYS_FADVISE64` exposes a new user-visible syscall, but the change only flips the top-level `docs/src/kernel/linux-compatibility.md` table. The required syscall flag coverage documentation and matching `.scml` coverage artifact for `fadvise64` are still absent, so the compatibility docs do not describe which `advice` values and argument behaviors are actually supported.

**Fix.** Add or update the `fadvise64` Syscall Flag Coverage page and its `.scml` coverage file in the Linux Compatibility docs, covering the supported `advice` values and any unsupported/partial behaviors.
