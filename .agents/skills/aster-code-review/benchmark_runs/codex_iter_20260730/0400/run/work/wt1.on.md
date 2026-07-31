---
date: 2026-07-30
mode: files
files: kernel/src/syscall/chdir.rs,kernel/src/syscall/chown.rs,kernel/src/syscall/chroot.rs,kernel/src/syscall/stat.rs
head: 374110492-dirty
branch: HEAD
title: "Working-tree syscall review"
---

# Summary

The reviewed syscall entry points have several high-impact Linux compatibility and security gaps. The most serious issue is that `chown` and `fchownat` mutate ownership without enforcing `CAP_CHOWN` or the owner/group rules, while also preserving set-ID bits. `fchown` and `fchownat` additionally return success for `-1, -1` requests before validating their targets.

Other major correctness issues affect `AT_EMPTY_PATH`: the direct `sys_fstat`/`sys_fchown` shortcuts mishandle `AT_FDCWD`, and `fstatat` rejects the Linux-supported `NULL` pathname form. `chdir`, `fchdir`, and `chroot` do not check search permission on the final directory. Ownership updates also need one atomic metadata operation and matching attribute notifications.

The remaining findings are maintainability nits around duplicated path validation, inconsistent pathname limits, and import/name conventions. The compatibility documentation should record the `CAP_SYS_CHROOT` requirement.

## Maintainability

### `kernel/src/syscall/chdir.rs` line 13

> ```diff
> syscall::constants::MAX_FILENAME_LEN,
> ```

`qualified-fn-imports` (nit): The constant `MAX_FILENAME_LEN` is imported directly, hiding its defining module at the use site.

**Fix.** Import the `constants` module and use `constants::MAX_FILENAME_LEN` at the call site.

### `kernel/src/syscall/chdir.rs` line 17

> ```diff
> let path_name = ctx.user_space().read_cstring(path_ptr, MAX_FILENAME_LEN)?;
> ```

`accurate-names` (minor): `MAX_FILENAME_LEN` names a filename component, but this value limits a full pathname and duplicates the resolver's `PATH_MAX` contract.

**Fix.** Use the shared `PATH_MAX` constant, or rename the syscall constant to a pathname-specific name and update its callers.

### `kernel/src/syscall/chdir.rs` line 24

> ```diff
> if path_name.is_empty() {
>     return_errno_with_message!(Errno::ENOENT, "path is empty");
> }
> ```

`dry` (minor): This `path_name.is_empty()` check duplicates the `EmptyPathStr::Reject` policy already enforced by `FsPath::try_from`, so empty-path behavior is represented in two places.

**Fix.** Shared with the other `dry` comments: route the syscall through the shared `FsPath` empty-path policy and remove the duplicated local check.

### `kernel/src/syscall/chown.rs` line 8

> ```diff
> utils::PATH_MAX,
> vfs::path::{AT_FDCWD, EmptyPathStr, FsPath},
> ```

`qualified-fn-imports` (nit): The constants `AT_FDCWD` and `PATH_MAX` are imported directly, hiding their defining modules at the use sites.

**Fix.** Import the `path` and `utils` modules and use `path::AT_FDCWD` and `utils::PATH_MAX` where they are consumed.

### `kernel/src/syscall/chown.rs` line 66

> ```diff
> if flags.contains(ChownFlags::AT_EMPTY_PATH) && path_name.is_empty() {
>     return sys_fchown(dirfd, uid, gid, ctx);
> }
> ```

`dry` (minor): The `AT_EMPTY_PATH` branch bypasses the shared `FsPath::from_fd_at` and `PathResolver` flow immediately below, duplicating empty-path dispatch and allowing the two paths to drift.

**Fix.** Shared with the `stat.rs` `dry` comment: route the empty-path case through `FsPath::from_fd_at(dirfd, &path_name, EmptyPathStr::AllowIfFlag(flags.bits()))?` and the common resolver.

### `kernel/src/syscall/chown.rs` line 99

> ```diff
> fn to_optional_id<T>(id: i32, f: impl Fn(u32) -> T) -> Result<Option<T>> {
> ```

`closure-fn-suffix` (nit): The callable parameter `f` is an opaque single-letter name and does not signal that it holds a function or closure.

**Fix.** Rename `f` to a descriptive callable name such as `id_fn`, and invoke `id_fn(id as u32)`.

### `kernel/src/syscall/chroot.rs` line 9

> ```diff
> syscall::constants::MAX_FILENAME_LEN,
> ```

`qualified-fn-imports` (nit): The constant `MAX_FILENAME_LEN` is imported directly, hiding its defining module at the use site.

**Fix.** Import the `constants` module and use `constants::MAX_FILENAME_LEN` at the call site.

### `kernel/src/syscall/chroot.rs` line 13

> ```diff
> let path_name = ctx.user_space().read_cstring(path_ptr, MAX_FILENAME_LEN)?;
> ```

`accurate-names` (minor): `MAX_FILENAME_LEN` names a filename component, but this value limits a full pathname and duplicates the resolver's `PATH_MAX` contract.

**Fix.** Use the shared `PATH_MAX` constant, or rename the syscall constant to a pathname-specific name and update its callers.

### `kernel/src/syscall/chroot.rs` line 20

> ```diff
> if path_name.is_empty() {
>     return_errno_with_message!(Errno::ENOENT, "path is empty");
> }
> ```

`dry` (minor): This `path_name.is_empty()` check duplicates the `EmptyPathStr::Reject` policy already enforced by `FsPath::try_from`, so empty-path behavior is represented in two places.

**Fix.** Shared with the other `dry` comments: route the syscall through the shared `FsPath` empty-path policy and remove the duplicated local check.

### `kernel/src/syscall/stat.rs` line 11

> ```diff
> path::{AT_FDCWD, EmptyPathStr, FsPath},
> ...
> syscall::constants::MAX_FILENAME_LEN,
> ```

`qualified-fn-imports` (nit): The constants `AT_FDCWD` and `MAX_FILENAME_LEN` are imported directly, hiding their defining modules at the use sites.

**Fix.** Import the `path` and `constants` modules and use `path::AT_FDCWD` and `constants::MAX_FILENAME_LEN` where they are consumed.

### `kernel/src/syscall/stat.rs` line 53

> ```diff
> let filename = user_space.read_cstring(filename_ptr, MAX_FILENAME_LEN)?;
> ```

`accurate-names` (minor): `MAX_FILENAME_LEN` names a filename component, but `filename` is a full pathname and the resolver enforces the separate `PATH_MAX` contract.

**Fix.** Use `PATH_MAX` for pathname reads, or rename the shared syscall constant to a pathname-specific name and update its callers.

### `kernel/src/syscall/stat.rs` line 61

> ```diff
> if flags.contains(StatFlags::AT_EMPTY_PATH) && filename.is_empty() {
>     return sys_fstat(dirfd, stat_buf_ptr, ctx);
> }
> ```

`dry` (minor): The `AT_EMPTY_PATH` branch bypasses the shared `FsPath::from_fd_at` and `PathResolver` flow immediately below, duplicating empty-path dispatch and allowing the two paths to drift.

**Fix.** Shared with the `chown.rs` `dry` comment: route the empty-path case through `FsPath::from_fd_at(dirfd, &filename, EmptyPathStr::AllowIfFlag(flags.bits()))?` and the common resolver.

## Correctness

### `kernel/src/syscall/chown.rs` line 19

> ```diff
> if uid.is_none() && gid.is_none() {
>     return Ok(SyscallReturn::Return(0));
> }
> ```

Invalid target accepted (major): When both `uid` and `gid` are `-1`, `sys_fchown()` returns success before validating `raw_fd`; `fchown(-1, -1, -1)` therefore succeeds instead of reporting `EBADF`.

**Fix.** Validate and resolve `raw_fd` before applying the no-op optimization.

### `kernel/src/syscall/chown.rs` line 30

> ```diff
> if let Some(gid) = gid {
>     path.set_group(gid)?;
> }
> Ok(SyscallReturn::Return(0))
> ```

Missing filesystem notification (minor): Successful ownership changes never call `fs::vfs::notify::on_attr_change()`, so inotify watchers do not receive the attribute-change event emitted by sibling metadata syscalls.

**Fix.** Shared with the pathname-form notification comment: after the combined ownership update succeeds, call `fs::vfs::notify::on_attr_change(path)` once.

### `kernel/src/syscall/chown.rs` line 30

> ```diff
> if let Some(uid) = uid {
>     path.set_owner(uid)?;
> }
> if let Some(gid) = gid {
>     path.set_group(gid)?;
> }
> ```

Non-atomic update (major): `uid` and `gid` are updated through separate lock acquisitions. A concurrent `stat()` can observe only the new owner or the new group, and a failure from `set_group()` leaves the owner changed.

**Fix.** Shared with the pathname-form atomicity comment: add one inode operation that updates both fields under a single metadata lock and use it for both entry points.

### `kernel/src/syscall/chown.rs` line 67

> ```diff
> if flags.contains(ChownFlags::AT_EMPTY_PATH) && path_name.is_empty() {
>     return sys_fchown(dirfd, uid, gid, ctx);
> }
> ```

Incorrect empty-path dispatch (major): For `fchownat(AT_FDCWD, "", ..., AT_EMPTY_PATH)`, this branch calls `sys_fchown(-100, ...)`; `sys_fchown()` converts `AT_FDCWD` to a regular fd and returns `EBADF` instead of resolving the current working directory.

**Fix.** Resolve the empty path through `FsPath::from_fd_at()` and the resolver, or explicitly map `AT_FDCWD` to the current directory before applying ownership changes.

### `kernel/src/syscall/chown.rs` line 72

> ```diff
> if uid.is_none() && gid.is_none() {
>     return Ok(SyscallReturn::Return(0));
> }
> ```

Path validation bypassed (major): When both ownership arguments are `-1`, `sys_fchownat()` returns success before validating `dirfd` or resolving `path_name`; nonexistent paths and invalid directory descriptors are silently accepted.

**Fix.** Shared with the `sys_fchown` no-op comment: resolve and validate the target before returning success for the no-op ownership request.

### `kernel/src/syscall/chown.rs` line 94

> ```diff
> if let Some(gid) = gid {
>     path.set_group(gid)?;
> }
> Ok(SyscallReturn::Return(0))
> ```

Missing filesystem notification (minor): `sys_fchownat()` does not emit an attribute-change notification after changing ownership, so pathname-based chown operations are invisible to inotify watchers.

**Fix.** Shared with the fd-form notification comment: after the combined ownership update succeeds, call `fs::vfs::notify::on_attr_change(&path)` once.

### `kernel/src/syscall/chown.rs` line 94

> ```diff
> if let Some(uid) = uid {
>     path.set_owner(uid)?;
> }
> if let Some(gid) = gid {
>     path.set_group(gid)?;
> }
> ```

Non-atomic update (major): The pathname form repeats the separate `set_owner()` and `set_group()` calls, allowing `stat()` to observe a mixed owner/group pair and leaving a partial update if the second call fails.

**Fix.** Shared with the fd-form atomicity comment: use one combined inode ownership-update operation and hold one metadata lock across both fields.

### `kernel/src/syscall/stat.rs` line 53

> ```diff
> let filename = user_space.read_cstring(filename_ptr, MAX_FILENAME_LEN)?;
> ```

Null pathname rejected (major): `read_cstring(filename_ptr, MAX_FILENAME_LEN)` executes before the `AT_EMPTY_PATH` branch, so `fstatat(fd, NULL, ..., AT_EMPTY_PATH)` returns `EFAULT` instead of statting `dirfd`.

**Fix.** Accept a null `filename_ptr` as the empty-path form when `AT_EMPTY_PATH` is present, and retain `EFAULT` otherwise.

### `kernel/src/syscall/stat.rs` line 62

> ```diff
> if flags.contains(StatFlags::AT_EMPTY_PATH) && filename.is_empty() {
>     return sys_fstat(dirfd, stat_buf_ptr, ctx);
> }
> ```

Incorrect empty-path dispatch (major): For `fstatat(AT_FDCWD, "", ..., AT_EMPTY_PATH)`, this branch calls `sys_fstat(-100, ...)`; the fd conversion rejects `AT_FDCWD` with `EBADF` instead of statting the current working directory.

**Fix.** Resolve the empty path through `FsPath::from_fd_at()` and the resolver, or explicitly map `AT_FDCWD` to the current directory before collecting metadata.

## Security

### `kernel/src/syscall/chdir.rs` line 30

> ```diff
> if path.type_() != InodeType::Dir {
>     return_errno_with_message!(Errno::ENOTDIR, "must be directory");
> }
> path_resolver.set_cwd(path);
> ```

Missing directory search permission check (major): `lookup()` checks execute permission on traversed directories, but not the final target. This branch only checks `InodeType::Dir`, allowing a caller to `sys_chdir` into a directory without `Permission::MAY_EXEC`.

**Fix.** Shared with the `fchdir` and `chroot` permission comments: add a helper or common check for `path.inode().check_permission(Permission::MAY_EXEC)?` before changing the resolver state.

### `kernel/src/syscall/chdir.rs` line 45

> ```diff
> if path.type_() != InodeType::Dir {
>     return_errno_with_message!(Errno::ENOTDIR, "must be directory");
> }
> let fs_ref = ctx.thread_local.borrow_fs();
> ```

Missing directory search permission check (major): `sys_fchdir` validates only that the descriptor refers to a directory. A caller holding a descriptor for a directory without `Permission::MAY_EXEC` can still install it as the current working directory.

**Fix.** Shared with the `chdir` and `chroot` permission comments: require `path.inode().check_permission(Permission::MAY_EXEC)?` before installing the directory as the current working directory.

### `kernel/src/syscall/chown.rs` line 27

> ```diff
> if let Some(uid) = uid {
>     path.set_owner(uid)?;
> }
> if let Some(gid) = gid {
>     path.set_group(gid)?;
> }
> ```

Missing ownership authorization (critical): `sys_fchown` and `sys_fchownat` call `path.set_owner` and `path.set_group` without checking ownership, permitted groups, or `CapSet::CHOWN`. The concrete inode setters directly update metadata, so any unprivileged process with a usable path or descriptor can assign arbitrary `uid` and `gid`, including `0`.

**Fix.** Route both entry points through one authorization helper that enforces the owner/group rules and `CapSet::CHOWN` before either metadata mutation.

### `kernel/src/syscall/chown.rs` line 27

> ```diff
> if let Some(uid) = uid {
>     path.set_owner(uid)?;
> }
> if let Some(gid) = gid {
>     path.set_group(gid)?;
> }
> ```

Privilege bits preserved after ownership change (major): The ownership setters update only `uid` or `gid` and leave `S_ISUID` and `S_ISGID` untouched. Consequently, changing a file with mode `0o4755` to owner `0` preserves its set-user-ID transition; combined with the missing authorization above, an attacker can create a set-user-ID file, chown it to `0`, and execute it with elevated credentials.

**Fix.** Make ownership/group mutation apply the privilege-clearing rules atomically: clear `S_ISUID`, `S_ISGID`, and any file privilege metadata whenever ownership changes.

### `kernel/src/syscall/chroot.rs` line 27

> ```diff
> if path.type_() != InodeType::Dir {
>     return_errno_with_message!(Errno::ENOTDIR, "must be directory");
> }
> 
> lsm_hooks::on_capable
> ```

Missing directory search permission check (major): `sys_chroot` checks the target type and `CapSet::SYS_CHROOT`, but never checks `Permission::MAY_EXEC` on the final directory. A capable caller can therefore select a directory whose search permission is denied.

**Fix.** Shared with the `chdir` and `fchdir` permission comments: require `path.inode().check_permission(Permission::MAY_EXEC)?` before the capability check and `set_root`.

## Documentation

### `kernel/src/syscall/chroot.rs` line 31

> ```diff
>     lsm_hooks::on_capable(lsm_hooks::CapableContext::new(
>         ctx.thread_local.borrow_user_ns().as_ref(),
>         ctx.posix_thread,
>         CapSet::SYS_CHROOT,
>     ))?;
> ```

`linux-compat-docs` (minor): The `CapSet::SYS_CHROOT` check changes the observable `chroot(path)` behavior, but the Linux Compatibility documentation still lists only `chroot(path);` as fully covered and does not document the capability requirement or resulting error.

**Fix.** Update the `chroot` compatibility entry and its `.scml` coverage to state that `chroot(path)` requires `CAP_SYS_CHROOT` and may fail when the capability is absent.

## Retracted by verification

- `kernel/src/syscall/chown.rs` line 58: retracted the `NULL` pathname finding because the available Linux contract documents the `NULL` form for `fstatat()` with `AT_EMPTY_PATH`, but not for `fchownat()`.
