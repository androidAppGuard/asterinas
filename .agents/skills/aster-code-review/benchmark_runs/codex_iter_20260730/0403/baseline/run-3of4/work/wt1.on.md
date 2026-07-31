---
date: 2026-07-30
mode: diff
base: 38c9ab061
head: 36a313263
branch: HEAD
---

# Summary

This change wires up x86-64 syscall 221 and adds a first `fadvise64` implementation, but the handler is not yet safe enough to expose as an implemented syscall. The most severe issues are all in `kernel/src/syscall/fadvise64.rs`: valid advice values can reach `todo!()` and panic the kernel, user-controlled ranges can overflow before validation, and the syscall can allocate an arbitrary kernel `Vec` based directly on `len`.

The implementation also performs file I/O while holding the file-table guard, collapses `read_at` errors such as `ESPIPE` into `EIO`, and treats the signed Linux `off_t`/`loff_t` offset as `usize` at the syscall boundary. Structurally, this should probably start as a no-op compatibility syscall for all valid advice values, or use a bounded readahead path after fixing signed offset validation, checked range arithmetic, and file lookup through `get_file_fast!`.

The documentation update is ahead of the implementation: the compatibility table marks `fadvise64` as implemented even though only two advice values are handled, and the aggregate syscall count remains inconsistent with the table.

## Maintainability

### `commit 36a313263 message`

> ```diff
> Add fadvise64 syscall
> ```

`imperative-subject` (nit): The subject names the syscall as plain prose: `Add fadvise64 syscall`. The commit-message guideline asks identifiers to be wrapped in backticks, so the syscall name is less visually distinct in history.

**Fix.** Use `fadvise64` as a code identifier in the subject, for example: Add `fadvise64` syscall.

### `kernel/src/syscall/fadvise64.rs` line 8

> ```diff
> #[repr(i32)]
> #[derive(Debug, Clone, Copy, TryFromInt)]
> #[expect(non_camel_case_types)]
> pub enum FadviseBehavior {
> ```

`alphabetical-attrs` (nit): The new `FadviseBehavior` attributes put `#[derive(...)]` before another outer attribute, and the derive list is not alphabetized. The guideline requires non-derive attributes first in alphabetical order, with `#[derive(...)]` last and its traits sorted.

**Fix.** Order the attributes and derive traits consistently:
```rust
#[expect(non_camel_case_types)]
#[repr(i32)]
#[derive(Clone, Copy, Debug, TryFromInt)]
```

### `kernel/src/syscall/fadvise64.rs` line 11

> ```diff
> pub enum FadviseBehavior {
>     POSIX_FADV_NORMAL = 0,
> ```

`narrow-visibility` (minor): `FadviseBehavior` is declared `pub`, but `rg` shows it is only used inside `kernel/src/syscall/fadvise64.rs`. Exposing this enum widens the module interface without a consumer.

**Fix.** Make `FadviseBehavior` private until another module actually needs to name it.

### `kernel/src/syscall/fadvise64.rs` line 21

> ```diff
> pub fn sys_fadvise64(
>     fd: i32,
>     offset: usize,
> ```

`consistency` (minor): `sys_fadvise64` takes `fd` as a raw `i32`, while nearby file-descriptor syscalls use the shared `FileDesc` alias. This makes the syscall interface less self-describing and diverges from the local file-table convention.

**Fix.** Import `FileDesc` from `crate::fs::file_table` and type `fd` as `FileDesc`, matching callers such as `sys_fallocate`, `sys_pread64`, and `sys_fsync`.

### `kernel/src/syscall/fadvise64.rs` line 22

> ```diff
> pub fn sys_fadvise64(
>     fd: i32,
>     offset: usize,
>     len: usize,
>     advice: i32,
> ```

`rust-type-invariants` (major): `offset` is typed as `usize`, so the syscall boundary converts the raw argument into an unsigned domain before `sys_fadvise64` can represent or validate negative file offsets. Other byte-offset syscalls such as `sys_pread64`, `sys_pwrite64`, and `sys_fallocate` keep offsets as `i64` until validation.

**Fix.** Shared with the range-validation comments: accept `offset` as `i64`, reject negative values explicitly, validate `offset + len` with checked arithmetic, and only convert to `usize` after validation.

### `kernel/src/syscall/fadvise64.rs` line 28

> ```diff
> let behavior = FadviseBehavior::try_from(advice)
>     .map_err(|_| Error::with_message(Errno::EINVAL, "invalid fadvise behavior:"))?;
> ```

`error-message-format` (nit): The `EINVAL` message ends with a stray colon: `invalid fadvise behavior:`. That punctuation makes the diagnostic look unfinished and does not match the surrounding syscall error-message style.

**Fix.** Drop the trailing colon, for example `invalid fadvise behavior`.

### `kernel/src/syscall/fadvise64.rs` line 35

> ```diff
> let file_table = ctx.thread_local.borrow_file_table();
> let file_table_locked = file_table.unwrap().write();
> let file = file_table_locked.get_file(fd)?;
> ```

`dry` (major): `sys_fadvise64` reimplements file-table lookup instead of using `get_file_fast!`. That helper owns the lock-lifetime policy for file operations and documents why the shared-table lock must be released before blocking file I/O; this local version holds `file_table_locked` through `file.read_bytes_at`.

**Fix.** Shared with the `no-io-under-spinlock` comment: use the shared helper, as nearby file syscalls do, so any shared-table lock is released before `read_bytes_at`:
```rust
let mut file_table = ctx.thread_local.borrow_file_table_mut();
let file = get_file_fast!(&mut file_table, fd);
```

## Correctness

### `kernel/src/syscall/fadvise64.rs` line 42

> ```diff
> let aligned_offset = offset.align_down(PAGE_SIZE);
> let aligned_end = (offset + len).align_up(PAGE_SIZE);
> let aligned_len = aligned_end - aligned_offset;
> ```

`checked-arithmetic` (major): `offset + len` and the following page alignment are unchecked. A caller can pass a huge `len` such as `usize::MAX` with `POSIX_FADV_WILLNEED`, making the syscall panic in debug builds or wrap in release before computing `aligned_len`.

**Fix.** Shared with the signed-offset comments: keep the syscall offset in a signed type until negative offsets have been rejected, then use checked arithmetic for both the end calculation and page rounding, returning `EINVAL`/`EOVERFLOW` instead of wrapping.

### `kernel/src/syscall/fadvise64.rs` line 46

> ```diff
> if aligned_len > 0 {
>     let mut buffer = vec![0u8; aligned_len];
> ```

Unbounded allocation (major): `aligned_len` is fully controlled by the syscall arguments, so `posix_fadvise(fd, 0, 1 << 40, POSIX_FADV_WILLNEED)` tries to allocate a terabyte-sized `Vec` in the kernel. This turns an advisory syscall into an OOM/panic path.

**Fix.** Shared with the security allocation comment: do not allocate the entire advised range. Either treat the advice as a no-op, or prefetch in a bounded page-sized/windowed buffer with a hard cap.

### `kernel/src/syscall/fadvise64.rs` line 48

> ```diff
> let file_table_locked = file_table.unwrap().write();
> let file = file_table_locked.get_file(fd)?;
> ...
> file.read_bytes_at(aligned_offset, &mut buffer)
> ```

`no-io-under-spinlock` (major): `file_table_locked` is an `ostd::sync::RwArc` write guard backed by a spin-based `RwLock`, and it is still held when `file.read_bytes_at(...)` runs. File reads can block, while the file-table helper documentation says these locks must be released before operating on files.

**Fix.** Shared with the `get_file_fast!` maintainability comment: fetch or clone `file` while holding the file-table lock, then drop the guard before calling `read_bytes_at`. Prefer the existing `get_file_fast!` pattern used by other syscalls.

### `kernel/src/syscall/fadvise64.rs` line 49

> ```diff
> file.read_bytes_at(aligned_offset, &mut buffer)
>     .map_err(|_| Error::with_message(Errno::EIO, "read failed in fadvise"))?;
> ```

Wrong errno (major): `map_err(|_| EIO)` collapses all errors from `read_bytes_at`. For example, advising a pipe with `POSIX_FADV_WILLNEED` should preserve `ESPIPE`, but this code reports `EIO`; a write-only file can similarly become `EIO` instead of the underlying access error.

**Fix.** Do not replace every `read_bytes_at` error with `EIO`. Propagate the original error with `?`, or avoid the read entirely for advice values that can be implemented as no-ops.

### `kernel/src/syscall/fadvise64.rs` line 54

> ```diff
> match behavior {
>     FadviseBehavior::POSIX_FADV_SEQUENTIAL | FadviseBehavior::POSIX_FADV_WILLNEED => {
>         ...
>     }
>     _ => todo!(),
> }
> ```

Reachable panic (major): `todo!()` is reachable for valid `fadvise64` advice values: `POSIX_FADV_NORMAL`, `POSIX_FADV_RANDOM`, `POSIX_FADV_DONTNEED`, and `POSIX_FADV_NOREUSE`. A normal userspace call such as `posix_fadvise(fd, 0, 1, POSIX_FADV_NORMAL)` will panic the kernel instead of returning success.

**Fix.** Shared with the security panic and documentation-coverage comments: handle every valid `FadviseBehavior` without panicking. Unsupported advisory modes should be harmless no-ops that return `0`; only invalid numeric advice should return `EINVAL`.

## Security

### `kernel/src/syscall/fadvise64.rs` line 42

> ```diff
> +            let aligned_offset = offset.align_down(PAGE_SIZE);
> +            let aligned_end = (offset + len).align_up(PAGE_SIZE);
> +            let aligned_len = aligned_end - aligned_offset;
> ```

`validate-at-boundaries` (critical): `offset` and `len` come directly from syscall registers, but `sys_fadvise64()` uses `offset + len` before validating the range. A hostile call such as `fadvise64(fd, usize::MAX - 1, 2, POSIX_FADV_WILLNEED)` can overflow here and then drive a panic or wrapped range calculation inside the kernel.

**Fix.** Shared with the signed-offset comments: validate the user-supplied range at the syscall boundary before doing arithmetic, using `checked_add()` and returning `EINVAL` on overflow. Also reject values that cannot represent the Linux `off_t` domain before converting to unsigned internal offsets.

### `kernel/src/syscall/fadvise64.rs` line 46

> ```diff
> +            if aligned_len > 0 {
> +                let mut buffer = vec![0u8; aligned_len];
> +
> +                file.read_bytes_at(aligned_offset, &mut buffer)
> ```

`validate-at-boundaries` (critical): `aligned_len` is derived from the user-controlled `len` and is passed directly to `vec![0u8; aligned_len]`. An unprivileged caller can request an arbitrarily large `POSIX_FADV_WILLNEED` or `POSIX_FADV_SEQUENTIAL` range and force the kernel to allocate that much memory, turning the syscall into a kernel-memory exhaustion path.

**Fix.** Shared with the correctness allocation comment: do not allocate the full advised range. Either treat these advices as a no-op until real readahead support exists, or process the range in a fixed-size bounded buffer/page loop after validating the range.

### `kernel/src/syscall/fadvise64.rs` line 54

> ```diff
> +        _ => todo!(),
> ```

Reachable panic (critical): `FadviseBehavior::try_from()` accepts `POSIX_FADV_NORMAL`, `POSIX_FADV_RANDOM`, `POSIX_FADV_DONTNEED`, and `POSIX_FADV_NOREUSE`, but those valid syscall inputs fall into `todo!()`. Any unprivileged process can call `fadvise64(fd, 0, 0, POSIX_FADV_NORMAL)` and panic the kernel.

**Fix.** Shared with the correctness panic and documentation-coverage comments: handle every valid `FadviseBehavior` without panicking. Unsupported no-op advices should return success if that matches the compatibility target, or return an errno explicitly instead of using `todo!()`.

## Hardware

### `kernel/src/syscall/fadvise64.rs` line 22

> ```diff
> pub fn sys_fadvise64(
>     fd: i32,
>     offset: usize,
> ```

Negative offsets accepted as huge positives (major): The x86-64 `fadvise64` ABI supplies a signed `loff_t` offset, but `offset: usize` converts a syscall argument of `-1` into a huge positive value instead of preserving the required negative-offset validation.

**Fix.** Shared with the range-validation comments: use `offset: i64`, reject `offset < 0`, and perform checked arithmetic before converting to the filesystem's unsigned offset type.

## Documentation

### `docs/src/kernel/linux-compatibility.md` line 244

> ```diff
> +| 221     | fadvise64        | ✅              |
> ```

Incorrect count (minor): This commit changes syscall `221` (`fadvise64`) from `❌` to `✅`, but the prose total at the top of the same table still says `Asterinas implements 204 out of the 336 system calls`. The table count was already inconsistent before this patch and now has 211 `✅` rows, so the aggregate count is still stale after adding `fadvise64`.

**Fix.** Update the total in `docs/src/kernel/linux-compatibility.md` to match the table after adding `fadvise64`, or leave `fadvise64` as `❌` if the syscall is not meant to count as implemented.

### `docs/src/kernel/linux-compatibility.md` line 244

> ```diff
> +| 221     | fadvise64        | ✅              |
> +
> +        FadviseBehavior::POSIX_FADV_SEQUENTIAL | FadviseBehavior::POSIX_FADV_WILLNEED => {
> +            ...
> +        }
> +        _ => todo!(),
> ```

`linux-compat-docs` (major): The compatibility table marks `fadvise64` as fully implemented with `✅`, but the added syscall body only handles `POSIX_FADV_SEQUENTIAL` and `POSIX_FADV_WILLNEED`; `POSIX_FADV_NORMAL`, `POSIX_FADV_RANDOM`, `POSIX_FADV_DONTNEED`, and `POSIX_FADV_NOREUSE` fall into `todo!()`. The Linux Compatibility docs therefore overstate the supported `fadvise64` behavior instead of documenting the newly supported advice values and unsupported cases.

**Fix.** Shared with the reachable-panic comments: update the Linux Compatibility coverage for `fadvise64` to spell out which `advice` values are supported, including the matching syscall coverage artifact if this tree has one, or keep the aggregate table entry as `❌` until all valid `fadvise64` advice values are handled without panicking.
