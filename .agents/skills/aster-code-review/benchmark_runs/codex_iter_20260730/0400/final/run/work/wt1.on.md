---
date: 2026-07-30
mode: files
files: kernel/src/syscall/chdir.rs,kernel/src/syscall/chown.rs,kernel/src/syscall/chroot.rs,kernel/src/syscall/stat.rs
head: 374110492-dirty
branch: HEAD
title: "Syscall path and ownership review"
---

# Summary

The strongest issues are in `chown`: both descriptor and pathname entry points mutate inode ownership without the Linux authorization checks, and the all-`-1` fast paths skip descriptor/path validation that Linux still performs. The `chdir`/`fchdir` paths also need final-directory execute permission checks; `lookup` checks search permission while traversing parents, but these handlers accept the resolved target after only a type check.

Several smaller issues are cleanup-oriented: empty-path handling is duplicated outside the shared `FsPath` policy, `chown` updates miss `IN_ATTRIB` notification, and the new `chroot` capability behavior should be reflected in compatibility docs. One Linux-contract candidate was retracted during verification because `fchownat(NULL, AT_EMPTY_PATH)` is not accepted by Linux.

## Maintainability

### `kernel/src/syscall/chdir.rs` line 24

> ```diff
> if path_name.is_empty() {
>     return_errno_with_message!(Errno::ENOENT, "path is empty");
> }
> ```

`dry` (minor): The explicit empty-path check duplicates `FsPath::try_from`, which already applies `EmptyPathStr::Reject` and returns `ENOENT`; keeping two copies allows validation and error messages to drift.

**Fix.** Remove the local `path_name.is_empty()` branch and let `FsPath::try_from` own empty-path handling.

### `kernel/src/syscall/chown.rs` line 66

> ```diff
> if flags.contains(ChownFlags::AT_EMPTY_PATH) && path_name.is_empty() {
>     return sys_fchown(dirfd, uid, gid, ctx);
> }
> ```

`dry` (minor): `FsPath::from_fd_at(..., EmptyPathStr::AllowIfFlag(...))` already converts an allowed empty path into an fd-targeted path, and `PathResolver::lookup` resolves it; this early dispatch duplicates that shared normalization and bypasses it.

**Fix.** Remove the special-case return and resolve the path through `FsPath::from_fd_at` and the resolver uniformly.

### `kernel/src/syscall/chown.rs` line 99

> ```diff
> fn to_optional_id<T>(id: i32, f: impl Fn(u32) -> T) -> Result<Option<T>> {
>     let id = if id >= 0 {
>         Some(f(id as u32))
> ```

`closure-fn-suffix` (minor): `f` is a callable `impl Fn(u32) -> T` parameter, but its name does not signal that it is a function as required by the local Rust naming convention.

**Fix.** Rename the parameter to `id_fn` and call `id_fn(id as u32)`.

### `kernel/src/syscall/chroot.rs` line 21

> ```diff
> if path_name.is_empty() {
>     return_errno_with_message!(Errno::ENOENT, "path is empty");
> }
> ```

`dry` (minor): The explicit empty-path check duplicates `FsPath::try_from`'s `EmptyPathStr::Reject` policy, creating a second implementation that can drift from the shared resolver contract.

**Fix.** Remove the local check and rely on `FsPath::try_from` to reject empty paths.

### `kernel/src/syscall/stat.rs` line 61

> ```diff
> if flags.contains(StatFlags::AT_EMPTY_PATH) && filename.is_empty() {
>     return sys_fstat(dirfd, stat_buf_ptr, ctx);
> }
> ```

`dry` (minor): `FsPath::from_fd_at(..., EmptyPathStr::AllowIfFlag(...))` already represents an allowed empty path as the target fd, so this separate `sys_fstat` dispatch duplicates the resolver's policy and creates another path for the same operation.

**Fix.** Remove the special-case return and use the normal `FsPath::from_fd_at` plus resolver path for empty and non-empty names.

### `kernel/src/syscall/stat.rs` line 94

> ```diff
> /// This is the x86_64-specific version.
> ```

`backtick-identifiers` (nit): The rustdoc refers to the architecture identifier `x86_64` as plain prose; the corresponding generic-architecture comment below has the same issue.

**Fix.** Format both architecture identifiers as code in the rustdoc, including `x86_64` in the x86-specific comment and the generic-architecture comment.

## Correctness

### `kernel/src/syscall/chown.rs` line 14

> ```diff
> pub fn sys_fchown(raw_fd: RawFileDesc, uid: i32, gid: i32, ctx: &Context) -> Result<SyscallReturn> {
> fn to_optional_id<T>(id: i32, f: impl Fn(u32) -> T) -> Result<Option<T>> {
> ```

(unverified) Signed ID interpretation (major): The `chown` arguments use `i32`, so valid unsigned `uid_t`/`gid_t` encodings such as `0x80000000` are interpreted as negative and rejected with `EINVAL`; only `0xffffffff` should mean unchanged.

**Fix.** Use `u32` for `uid` and `gid`, and treat only `u32::MAX` as the unchanged sentinel.

### `kernel/src/syscall/chown.rs` line 19

> ```diff
> if uid.is_none() && gid.is_none() {
>     return Ok(SyscallReturn::Return(0));
> }
> 
> let mut file_table = ctx.thread_local.borrow_file_table_mut();
> ```

Skipped descriptor validation (major): When both IDs are `-1`, this returns success before validating `raw_fd`; `fchown(-1, -1, -1)` therefore succeeds instead of returning `EBADF`.

**Fix.** Shared with the corresponding `validate-at-boundaries` comment: validate and resolve `raw_fd` before applying the no-op return, while skipping the ownership setters when both IDs are unchanged.

### `kernel/src/syscall/chown.rs` line 31

> ```diff
> if let Some(uid) = uid {
>     path.set_owner(uid)?;
> }
> if let Some(gid) = gid {
>     path.set_group(gid)?;
> }
> ```

Missing attribute notification (major): Successful `set_owner`/`set_group` calls in `sys_fchown` and `sys_fchownat` do not call `fs::vfs::notify::on_attr_change`, so `inotify` watchers miss ownership changes even though `chmod`, `utimens`, and xattr updates publish `IN_ATTRIB`.

**Fix.** Route both ownership entry points through a helper that calls `fs::vfs::notify::on_attr_change` after each successful ownership mutation, including a partial update before a later setter fails.

### `kernel/src/syscall/chown.rs` line 72

> ```diff
> let uid = to_optional_id(uid, Uid::new)?;
> let gid = to_optional_id(gid, Gid::new)?;
> if uid.is_none() && gid.is_none() {
>     return Ok(SyscallReturn::Return(0));
> }
> ```

Skipped path validation (major): When both IDs are `-1`, this returns success before resolving `dirfd` and `path`; `fchownat(AT_FDCWD, "missing", -1, -1, 0)` therefore succeeds instead of returning `ENOENT`.

**Fix.** Shared with the corresponding `validate-at-boundaries` comment: resolve and validate the target path before returning the no-op result, then skip only the actual ownership updates.

### `kernel/src/syscall/stat.rs` line 53

> ```diff
> let user_space = ctx.user_space();
> let filename = user_space.read_cstring(filename_ptr, MAX_FILENAME_LEN)?;
> let flags = StatFlags::from_bits(flags)
> ```

Incorrect NULL handling (major): With `AT_EMPTY_PATH`, a `NULL` pathname is accepted as the empty path for a real `dirfd`, but `read_cstring(0, ...)` returns `EFAULT` before the flag is parsed, so `fstatat(fd, NULL, ..., AT_EMPTY_PATH)` fails instead of statting `fd`.

**Fix.** Parse `flags` before reading `filename` and handle `filename_ptr == 0` as the empty pathname only in the permitted `AT_EMPTY_PATH` case.

## Security

### `kernel/src/syscall/chdir.rs` line 30

> ```diff
>     if path.type_() != InodeType::Dir {
>         return_errno_with_message!(Errno::ENOTDIR, "must be directory");
>     }
>     path_resolver.set_cwd(path);
> ```

Missing execute permission check (major): `lookup` checks search permission on parent directories but does not check the final `path`; this branch checks only its type. Thus `chdir("/private")` succeeds for a directory with no execute permission when its parent is searchable, violating the directory search boundary.

**Fix.** After the type check, require `path.inode().check_permission(Permission::MAY_EXEC)?` before calling `set_cwd`.

### `kernel/src/syscall/chdir.rs` line 45

> ```diff
>     if path.type_() != InodeType::Dir {
>         return_errno_with_message!(Errno::ENOTDIR, "must be directory");
>     }
>     let fs_ref = ctx.thread_local.borrow_fs();
> ```

Missing execute permission check (major): `sys_fchdir` accepts a directory descriptor, including an `O_PATH` descriptor, and checks only `InodeType::Dir`. An unprivileged caller holding a descriptor for a mode-`000` directory can change its working directory without the required search permission.

**Fix.** Check `path.inode().check_permission(Permission::MAY_EXEC)?` after verifying that the descriptor refers to a directory and before `set_cwd`.

### `kernel/src/syscall/chroot.rs` line 27

> ```diff
>     if path.type_() != InodeType::Dir {
>         return_errno_with_message!(Errno::ENOTDIR, "must be directory");
>     }
> 
>     lsm_hooks::on_capable(lsm_hooks::CapableContext::new(
> ```

Missing execute permission check (major): `sys_chroot` has the same final-directory gap as `sys_chdir`: `lookup` checks execute permission on parent directories while traversing, but this handler checks only that the resolved target is a directory before installing it as the new root. A caller with `CAP_SYS_CHROOT` can therefore chroot into a directory that is not searchable by the caller.

**Fix.** Shared with the `chdir` final-directory checks: after the `InodeType::Dir` check and before `set_root`, require `path.inode().check_permission(Permission::MAY_EXEC)?`.

### `kernel/src/syscall/chown.rs` line 19

> ```diff
>     if uid.is_none() && gid.is_none() {
>         return Ok(SyscallReturn::Return(0));
>     }
> 
>     let mut file_table = ctx.thread_local.borrow_file_table_mut();
> ```

`validate-at-boundaries` (minor): The `uid == -1 && gid == -1` fast path returns before `raw_fd.try_into()` and `get_file_fast`, so `fchown` with an invalid descriptor reports success instead of validating the user-controlled resource handle.

**Fix.** Shared with the Correctness comment on this branch: validate and resolve `raw_fd` first, then return the no-op success only after descriptor validation succeeds.

### `kernel/src/syscall/chown.rs` line 27

> ```diff
>     if let Some(uid) = uid {
>         path.set_owner(uid)?;
>     }
>     if let Some(gid) = gid {
>         path.set_group(gid)?;
>     }
> ```

Missing authorization (critical): `sys_fchown` mutates ownership through `path.set_owner` and `path.set_group` without checking `CapSet::CHOWN` or the caller's ownership rules. An unprivileged process with an `O_PATH` descriptor can take ownership of a protected file and bypass DAC.

**Fix.** Shared with the path-based ownership comment: authorize the operation before mutation using the Linux `chown` rules, then apply the validated owner and group changes atomically where possible.

### `kernel/src/syscall/chown.rs` line 72

> ```diff
>     let uid = to_optional_id(uid, Uid::new)?;
>     let gid = to_optional_id(gid, Gid::new)?;
>     if uid.is_none() && gid.is_none() {
>         return Ok(SyscallReturn::Return(0));
>     }
> 
>     let path = {
> ```

`validate-at-boundaries` (minor): For a non-empty pathname, `uid == -1 && gid == -1` returns before `FsPath::from_fd_at` and lookup. Calls such as `chown("/missing", -1, -1)` therefore succeed without validating the pathname or `dirfd`.

**Fix.** Shared with the Correctness comment on this branch: resolve and validate the pathname and `dirfd` before applying the all-sentinel no-op return.

### `kernel/src/syscall/chown.rs` line 91

> ```diff
>     if let Some(uid) = uid {
>         path.set_owner(uid)?;
>     }
>     if let Some(gid) = gid {
>         path.set_group(gid)?;
>     }
> ```

Missing authorization (critical): `sys_fchownat`, and therefore `sys_chown` and `sys_lchown`, also call `set_owner` and `set_group` without any authorization check. A caller without `CapSet::CHOWN` can change ownership of any path it can resolve.

**Fix.** Shared with the descriptor-based ownership comment: perform the same ownership authorization check before either inode mutation, including the `AT_SYMLINK_NOFOLLOW` path.

## Documentation

### `kernel/src/syscall/chroot.rs` line 31

> ```diff
>     lsm_hooks::on_capable(lsm_hooks::CapableContext::new(
>         ctx.thread_local.borrow_user_ns().as_ref(),
>         ctx.posix_thread,
>         CapSet::SYS_CHROOT,
>     ))?;
> ```

`linux-compat-docs` (minor): The added `lsm_hooks::on_capable(...)` check changes the user-visible `chroot()` behavior by requiring `CAP_SYS_CHROOT`, but the Linux Compatibility documentation still only records `chroot(path)` and marks coverage as complete.

**Fix.** Update `book/src/kernel/linux-compatibility/syscall-flag-coverage/file-systems-and-mount-control/fully_covered.scml` and its documentation to describe the `CAP_SYS_CHROOT` requirement and resulting failure behavior.

## Retracted by verification

- `kernel/src/syscall/chown.rs` line 58: retracted because Linux accepts `AT_EMPTY_PATH` with an empty string for `fchownat`, but not with a `NULL` pathname; a host syscall check returned `EFAULT` for `fchownat(fd, NULL, ..., AT_EMPTY_PATH)`.
- `kernel/src/syscall/chown.rs` line 103: retracted because `backtick-identifiers` is scoped to doc comments, while the cited line is an ordinary implementation comment.
